"""Four requested diagnostics. No optimizer, model fitting, or deployment writes."""
import argparse,collections,gc,gzip,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PARENT=HERE.parent/'device_context_evaluation_v1_20261105';PHASE='PREFLIGHT';PEAK=0
import attribution as at
import geometry as geo
import physical

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(n,v):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):
 global PEAK
 PEAK=max(PEAK,psutil.Process().memory_info().rss);assert PEAK<7*1024**3,'RSS_LIMIT'
 write(PHASE+'_PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),rss_mib=PEAK/2**20,updated_unix=time.time(),**kw))
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(v) for v in f]
def save_array(name,**data):
 p=HERE/(name+'.npz');np.savez(p,**data);return dict(file=p.name,sha256=sha(p),bytes=p.stat().st_size)
def pinned_asset(c,spec):
 for root in [c.ROOT,c.PROJECT]:
  p=root/spec['path']
  if p.is_file() and sha(p)==spec['sha256']:return c.pin(p,spec['sha256'])
 raise RuntimeError('MISSING_PINNED_ASSET:'+spec['path'])
def initialize():
 for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,n
 import dependency_gate
 dependency_gate.verify(ROOT,read(HERE/'INPUT_PINS.json'))
 sys.path.insert(0,str(PARENT));import common as c
 c.verify();c.progress=progress
 import inputs,edge_context,reporting,metrics
 inputs.progress=edge_context.progress=progress
 k,norm,arms=c.models()
 import constrained_onboarding_core_v3 as core
 return c,k,norm,arms,inputs,edge_context,core,reporting,metrics

def source_calibration(c,inputs,core,geom):
 refs=rows(HERE/'SOURCE_REFS.jsonl.gz');assert len(refs)==104
 expected={u for r in geom['source_roster'] for u in r['reference_uids']};assert {r['uid'] for r in refs}==expected
 physicalrefs,replay=physical.source_refs(refs,c,progress)
 rr,z,q,xc=inputs.source_role('LEARN');ix=[i for i,r in enumerate(rr) if r.get('fit_role')=='FIT' and r['label']==0]
 normal=[rr[i] for i in ix];assert len(normal)==134493
 radii,dist=geo.fit_context(normal,c.extra_normalized(xc[ix]),refs,c.extra_normalized(physicalrefs),core,geom,progress)
 artifact=save_array('SOURCE_CONTEXT_CALIBRATION',uid=np.asarray([r['uid'] for r in normal]),second_dc=dist,reference_uid=np.asarray([r['uid'] for r in refs]),reference_context=physicalrefs)
 del rr,z,q,xc;gc.collect()
 return dict(protocols=radii,artifact=artifact,replay=replay,fit_role='LEARN/FIT normal only',target_data_used=False)

def load(pool,c,inputs,context):
 d=inputs.edge() if pool=='EDGE' else inputs.ab(pool)
 for r in d['rows']:
  r.setdefault('scenario',r.get('activity',r.get('source_role','UNKNOWN')))
 if pool=='EDGE':
  ix,d['context']=context.join(d['rows']);assert len(ix)==60000
 result=read(PARENT/('EDGE_RESULT.json' if pool=='EDGE' else 'AB_RESULT.json'));spec=result['scores'] if pool=='EDGE' else result['pools'][pool]['scores']
 a=np.load(c.pin(spec['path'],spec['sha256']),allow_pickle=False);assert a['uid'].tolist()==[r['uid'] for r in d['rows']]
 d['raw']=a['FUSION790_RAW'].copy();d['old_c5']=a['FUSION790_C5_P3'].copy();d['stats8']=a['STATS8_RAW'].copy();a.close()
 return d

def reference_bank(pool,d,c):
 if pool=='EDGE':return d['refs'],d['rz'],d['rq']
 spec=read(PARENT/'OLD_ASSETS.json')['pools'][pool]['dense_bank'];rr=rows(pinned_asset(c,spec['rows']));a=np.load(pinned_asset(c,spec['e3']),allow_pickle=False)
 assert a['uid'].tolist()==[r['uid'] for r in rr]
 assert len(rr)==spec['expected_rows'];return rr,a[spec['e3']['key']].copy(),a[spec['q14']['key']].copy()

def subset(d,ix):
 return {k:([v[int(i)] for i in ix] if k=='rows' else v[ix]) for k,v in d.items() if k in ['rows','z','q','context','support','raw','old_c5','stats8']}

def select_small(d):
 groups=collections.defaultdict(list)
 for i,r in enumerate(d['rows']):groups[(r['device'],r['protocol'],r['label'],r.get('source_role',''))].append(i)
 return np.asarray(sorted(i for ids in groups.values() for i in sorted(ids,key=lambda i:d['rows'][i]['uid'])[:8]))

def reference_context(pool,refs,c):
 if pool=='EDGE':
  # Replay only the legal commissioning prefix, not later NORMAL queries.
  card=read(PARENT/'EDGE_CARD.json');paths=read(c.PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json')
  assert all(r['source_role']=='NORMAL' and r['timestamp_ns']<=card['reference']['cutoff_ns'] for r in refs)
  a,receipt=physical.replay(refs,paths['NORMAL'],card['raw_inputs']['NORMAL']['sha256'],c,progress,card['capture_boundaries']['normal_segments'])
  return a['features'],receipt
 return physical.source_refs(refs,c,progress)

def run_contributions(d,k,norm,arms):
 n=len(d['rows']);out={};artifacts={}
 for arm in ['STATS8','FUSION790']:
  a=arms[arm];score=np.zeros((n,3));base=score.copy();ig=np.empty((n,3,8));grad=ig.copy()
  for start in range(0,n,1024):
   ix=np.arange(start,min(n,start+1024));x=k.normalized((d['z'],d['context']),d['q'],ix,norm,a['dimension']).numpy()
   for j,model in enumerate(a['models']):score[ix,j],base[ix,j],ig[ix,j],grad[ix,j]=at.exact(model,x)
   if start%32768==0:progress('SIGNED_CONTRIBUTIONS_'+arm,start,n)
  saved=d['stats8'] if arm=='STATS8' else d['raw'];err=float(np.max(np.abs(score-saved[:,:3])));assert err<.002
  keep=d['views']['primary'][0] if 'views' in d else np.arange(n);groups={'pool':keep,'full_pool':np.arange(n)}
  for role in ['NORMAL','HTTP','UDP']:
   ids=[i for i,r in enumerate(d['rows']) if r.get('source_role')==role]
   if ids:groups[role]=np.asarray(ids)
  for label in [0,1]:groups['label_'+str(label)]=np.asarray([i for i in keep if d['rows'][i]['label']==label])
  for role in ['HTTP','UDP']:
   if role in groups:groups[role+'_FUSION_RAW_MISS']=groups[role][d['raw'][groups[role],3]<=arms['FUSION790']['cuts'][3]]
  out[arm]=dict(score_max_error=err,groups={})
  for j,head in enumerate(['27','127','227','ensemble']):
   sc=score[:,j] if j<3 else score.mean(1);ba=base[:,j] if j<3 else base.mean(1);ii=ig[:,j] if j<3 else ig.mean(1);gg=grad[:,j] if j<3 else grad.mean(1)
   out[arm]['groups'][head]={name:at.contribution_summary(sc,ba,ii,gg,a['cuts'][j],ix) for name,ix in groups.items()}
  artifacts[arm]=dict(score=score,baseline=base,ig=ig,gradient=grad)
 return out,artifacts

def metrics_summary(pool,d,variants,arms,reporting):
 rows0=d['rows'];labels=np.asarray([r['label'] for r in rows0]);pred={name:values>arms['FUSION790']['cuts'] for name,values in variants.items()};out={}
 if pool=='EDGE':
  weights=reporting._hierarchical_weights(rows0);expansion,_=reporting._weights(rows0);old=read(PARENT/'EDGE_RESULT.json');groups={role:np.asarray([i for i,r in enumerate(rows0) if r['source_role']==role]) for role in ['NORMAL','HTTP','UDP']}
 else:
  keep,weights=d['views']['primary'];groups={name:keep[labels[keep]==lab] for name,lab in [('NORMAL',0),('ATTACK',1)]}
 for name,pp in pred.items():
  out[name]={}
  for j,head in enumerate(['27','127','227','ensemble']):
   out[name][head]={}
   for role,ix in groups.items():
    r=dict(rows=len(ix),alarm_count=int(pp[ix,j].sum()),sample_rate=float(pp[ix,j].mean()),hierarchical_rate=float(weights[ix][pp[ix,j]].sum()/weights[ix].sum()),added_vs_RAW=int((pp[ix,j]&~pred['RAW'][ix,j]).sum()),removed_vs_RAW=int((~pp[ix,j]&pred['RAW'][ix,j]).sum()))
    if pool=='EDGE':
     N=old['arms']['FUSION790']['methods']['RAW']['heads'][head]['roles'][role]['population_count'];r['HT_rate']=float(expansion[ix][pp[ix,j]].sum()/N)
    out[name][head][role]=r
   assert not np.any(pp[:,j]&~pred['RAW'][:,j]),'SUBTRACTIVE_CEILING'
 return out

def main():
 start=time.monotonic();c,k,norm,arms,inputs,context,core,reporting,metrics=initialize();geom=read(PARENT/'METHOD_FREEZE.json')['calibration']['geometry'];result=dict(status='PASS',phase=PHASE,training=False,deployment_change=False,pools={})
 if PHASE=='PREFLIGHT':
  # Real snapshot decode, encoder, original geometry, and current model startup gate.
  d=inputs.edge();import preflight_encoder
  preflight_encoder.progress=progress;result['real_encoder_distance']=preflight_encoder.run(d,norm)
  _,result['physical_oracle']=physical.edge(d['rows'],c,progress,small=True);del d;gc.collect()
  calibration=source_calibration(c,inputs,core,geom);write('SOURCE_CALIBRATION.json',calibration);result['calibration']=calibration
 else:
  pre=read(HERE/'PREFLIGHT_RESULT.json');assert pre['status']=='PASS'
  calibration=pre['calibration'];assert sha(HERE/calibration['artifact']['file'])==calibration['artifact']['sha256']
 result['calibration']=calibration
 rhoc=calibration['protocols'];forecast=0
 for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
  progress('LOAD_'+pool);d=load(pool,c,inputs,context);refs,rz,rq=reference_bank(pool,d,c)
  if PHASE=='PREFLIGHT':
   refphys,receipt=reference_context(pool,refs,c);cache=save_array(pool+'_REF_CONTEXT',uid=np.asarray([r['uid'] for r in refs]),features=refphys)
   ix=select_small(d);total=len(d['rows']);d=subset(d,ix)
  else:
   cache=pre['pools'][pool]['reference_context'];a=np.load(c.pin(HERE/cache['file'],cache['sha256']));assert a['uid'].tolist()==[r['uid'] for r in refs];refphys=a['features'].copy();a.close()
  rc=c.extra_normalized(refphys);t=time.monotonic();old,new,matchdc,seconddc=geo.evaluate(d,refs,rz,rq,rc,norm,geom,rhoc,core,progress);distance_seconds=time.monotonic()-t
  raw=d['raw'];current=arms['FUSION790'];variants={'RAW':raw}
  for name,support in [('2D',old['support']),('3D',new)]:
   for scale_label,scale in [('FUSION',current['scales']),('OLD',arms['OLD782']['scales'])]:variants['C5_'+name+'_'+scale_label]=c.four(c.correction(raw[:,:3],support,d['q'],scale))
  assert np.max(np.abs(variants['C5_2D_FUSION']-d['old_c5']))<2e-10,'FROZEN_C5_REPRODUCTION'
  for name in ['FUSION','OLD']:assert np.all(variants['C5_3D_'+name]>=variants['C5_2D_'+name]-2e-9)
  if PHASE=='PREFLIGHT':
   for arm,expected in [('FUSION790',raw),('STATS8',d['stats8'])]:assert np.max(np.abs(c.four(c.score(k,norm,arms[arm],d['z'],d['q'],d['context']))-expected))<.002
   # Conservatively extrapolate a small real legal-bank pass with a 2x margin.
   forecast+=distance_seconds*total/max(1,len(d['rows']))*2
   result['pools'][pool]=dict(rows=len(d['rows']),full_rows=total,distance_seconds=distance_seconds,reference_context=cache,reference_replay=receipt)
  else:
   m=metrics_summary(pool,d,variants,arms,reporting);out=dict(metrics=m,rows=len(d['rows']),distance_seconds=distance_seconds)
   signed,arrays=run_contributions(d,k,norm,arms);out['signed_contributions']=signed
   out['large_artifacts']=save_array(pool+'_ATTRIBUTION',uid=np.asarray([r['uid'] for r in d['rows']]),support2=old['support'],support3=new,matched_context_distance=matchdc,second_dc=seconddc,**{name:v for name,v in variants.items()},**{arm+'_'+name:v for arm,a in arrays.items() for name,v in a.items()})
   if pool=='EDGE':
    physical_rows,replay=physical.edge(d['rows'],c,progress);phys=np.asarray([physical_rows[r['uid']]['features'] for r in d['rows']]);assert np.array_equal(c.extra_normalized(phys),d['context']),'EDGE_CONTEXT_REPRODUCTION'
    out['physical_replay']=replay;out['task1_raw_misses']=at.physical_misses(d,physical_rows,refs,refphys,raw,current['cuts'])
    out['task2_false_alarms']=at.false_alarm_trace(d['rows'],raw,variants['C5_2D_FUSION'],current['cuts'],current['scales'],old,geom)
    assert out['task2_false_alarms']['ensemble']['rows']==1158
    http=np.asarray([r['source_role']=='HTTP' for r in d['rows']]);ix=np.flatnonzero(http&(raw[:,3]>current['cuts'][3])&(variants['C5_2D_FUSION'][:,3]<=current['cuts'][3]));assert len(ix)==967
    rho=np.asarray([rhoc[str(d['rows'][i]['protocol'])]['rho_c'] for i in ix]);rat=core._ratio(matchdc[ix],rhoc['6']['rho_c'])
    out['task2_http_withdrawals']=dict(rows=len(ix),strata=at.counts(d['rows'],ix,'stratum'),support2=at.quant(old['support'][ix]),support3=at.quant(new[ix]),matched_dc=at.quant(matchdc[ix].ravel()),matched_dc_over_rhoc=at.quant(rat.ravel()),both_old_matches_outside_context_radius=int((rat>1).all(1).sum()),raw_margin=at.quant(raw[ix,3]-current['cuts'][3]),recovered_3d_current=int((variants['C5_3D_FUSION'][ix,3]>current['cuts'][3]).sum()),recovered_3d_old=int((variants['C5_3D_OLD'][ix,3]>current['cuts'][3]).sum()),bank_internal_context_distances=geo.reference_context_profile(refs,rc,core))
    out['physical_artifact']=save_array('EDGE_PHYSICAL',uid=np.asarray([r['uid'] for r in d['rows']]),context=phys,age_seconds=np.asarray([physical_rows[r['uid']]['age_seconds'] for r in d['rows']]),inbound=np.asarray([physical_rows[r['uid']]['inbound'] for r in d['rows']]))
   result['pools'][pool]=out;write(pool+'_RESULT.json',out);write('BOARD.json',{p:v['metrics'] for p,v in result['pools'].items()})
  del d,refs,rz,rq,rc,old,new,matchdc,seconddc,variants;gc.collect()
 if PHASE=='PREFLIGHT':
  result['forecast_seconds']=forecast+1200;assert forecast+1200<5400,'FULL_RUNTIME_FORECAST_EXCEEDS_BUDGET';write('RUNTIME_FORECAST.json',dict(status='PASS',seconds=forecast+1200,budget=5400))
 result.update(seconds=time.monotonic()-start,rss_peak_bytes=PEAK,scope='CONSUMED_DATA_READONLY_ATTRIBUTION_AND_OFFLINE_COUNTERFACTUAL',all_input_pins=c.PINS)
 write(PHASE+'_RESULT.json',result);progress(PHASE+'_COMPLETE',1,1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['PREFLIGHT','DIAGNOSE'],required=True);PHASE=p.parse_args().phase
 try:main()
 except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
