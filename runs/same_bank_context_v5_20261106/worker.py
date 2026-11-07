"""Same-bank historical context comparison, frozen head/cuts/radii, no training."""
import argparse,gc,json,time,traceback,collections
from pathlib import Path
import numpy as np
import base_worker as w
import history_context as hist
import geometry as geo
import attribution as at
import geometry_frozen
import fast_geometry
import support_contract
HERE=Path(__file__).resolve().parent;PRIOR=HERE.parent/'context_geometry_attribution_v2_20261106'

def views(pool,d,reporting):
 if pool!='EDGE':return {'post_window_primary':d['views']['primary'],'full':d['views']['full']}
 weights=reporting.hierarchical_weights(d['rows']);return {'full':(np.arange(len(d['rows'])),weights)}

def measures(rows,scores,cuts,view_weights,raw):
 out={}
 for method,sc in scores.items():
  pp=sc>cuts;out[method]={}
  for j,h in enumerate(['27','127','227','ensemble']):
   groups={'NORMAL':np.asarray([i for i,r in enumerate(rows) if r['label']==0],dtype=int),'ATTACK':np.asarray([i for i,r in enumerate(rows) if r['label']==1],dtype=int)}
   if any(r.get('source_role')=='HTTP' for r in rows):groups.update({role:np.asarray([i for i,r in enumerate(rows) if r.get('source_role')==role],dtype=int) for role in ['HTTP','UDP']})
   for dev in sorted({r['device'] for r in rows}):
    for label in [0,1]:groups['device:'+dev+(' / NORMAL' if label==0 else ' / ATTACK')]=np.asarray([i for i,r in enumerate(rows) if r['device']==dev and r['label']==label],dtype=int)
   out[method][h]={}
   for name,ix in groups.items():
    if not len(ix):continue
    mass=float(view_weights[ix].sum());assert mass>0
    out[method][h][name]=dict(rows=len(ix),alarm_count=int(pp[ix,j].sum()),sample_rate=float(pp[ix,j].mean()),hierarchical_rate=float(view_weights[ix][pp[ix,j]].sum()/mass),added_vs_RAW=int((pp[ix,j]&~raw[ix,j]).sum()),removed_vs_RAW=int((~pp[ix,j]&raw[ix,j]).sum()))
 return out

def all_metrics(pool,d,variants,cuts,reporting):
 if pool=='EDGE':
  # Use sealed Edge weighting and population denominators via the previously audited implementation.
  import common as c
  arms={'FUSION790':{'cuts':cuts}}
  primary=w.metrics_summary(pool,d,variants,arms,reporting)
  return {'full':primary}
 out={}
 for view,(ix,weights) in views(pool,d,reporting).items():
  rr=[d['rows'][i] for i in ix];ww=weights[ix] if len(weights)==len(d['rows']) else weights
  out[view]=measures(rr,{m:s[ix] for m,s in variants.items()},cuts,ww,variants['RAW'][ix]>cuts)
 return out

def retention(pool,d,old,new,dc,refs,rhoc,variants,cuts):
 origin={r['uid']:('HIST' if 'historical_reference_end' in r else 'DENSE') for r in refs};groups=collections.defaultdict(list);guard=(d['q'][:,0]==1)&(d['q'][:,2]==1)&(d['q'][:,5]==0)
 for i,r in enumerate(d['rows']):
  if r['label']!=0:continue
  pair=old['matched_reference_uids'][i]
  if any(u is None for u in pair):name='NO_TWO_LEGAL_MATCHES'
  else:
   a,b=[origin[u] for u in pair];name='BOTH_'+a if a==b else 'MIXED_DENSE_HIST'
  groups['all/'+name].append(i);groups['device:'+r['device']+'/'+name].append(i)
 out={}
 for key,ii in groups.items():
  ix=np.asarray(ii);ratio=np.asarray([dc[i]/rhoc[str(d['rows'][i]['protocol'])]['rho_c'] for i in ix]);finite=np.isfinite(ratio).all(1);positive=old['support'][ix]>0
  a=dict(rows=len(ix),guarded_rows=int(guard[ix].sum()),support2=at.quant(old['support'][ix]),support3=at.quant(new[ix]),positive2=int(positive.sum()),positive3=int((new[ix]>0).sum()),lost_positive=int((positive&(new[ix]==0)).sum()),support_fraction_retained=at.quant(new[ix][positive]/old['support'][ix][positive]),matched_pairs_with_context=int(finite.sum()),either_dc_over_rho_gt1=int((ratio[finite]>1).any(1).sum()),both_dc_over_rho_gt1=int((ratio[finite]>1).all(1).sum()),dc_over_rho=at.quant(ratio[finite].ravel()),false_alarms={})
  for method,sc in variants.items():a['false_alarms'][method]={h:int((sc[ix,j]>cuts[j]).sum()) for j,h in enumerate(['27','127','227','ensemble'])}
  out[key]=a
 return out

def evaluate(pool,d,refs,rz,rq,rc,c,norm,arms,geom,rhoc,reporting):
 guard=(d['q'][:,0]==1)&(d['q'][:,2]==1)&(d['q'][:,5]==0)
 parity=np.ones(len(d['rows']),bool)
 d['parity_mask']=parity;d['support']=d['support_frozen']
 w.progress('EXPANDED_2D_DISTANCE_'+pool,0,len(d['rows']));start=time.monotonic()
 old,new,dc,second=fast_geometry.evaluate(d,refs,rz,rq,rc,norm,geom,rhoc,c.core,w.progress)
 support_audit=support_contract.audit(pool,d['rows'],d['q'],old['support'],d['support_frozen'])
 w.write(pool+'_PARITY_AUDIT.json',support_audit)
 assert support_audit['status']=='PASS','EXPANDED_2D_FROZEN_PARITY_GATE'
 if w.PHASE=='PREFLIGHT':
  oi=w.select_small(d,per_group=8);od=w.subset(d,oi);od['parity_mask']=parity[oi]
  # The frozen geometry oracle expects raw geometric support, whereas the
  # archived replay uses the historically guarded storage schema checked above.
  od['support']=old['support'][oi]
  expected=geometry_frozen.evaluate(od,refs,rz,rq,rc,norm,geom,rhoc,c.core,w.progress)
  actual=({key:value[oi] for key,value in old.items()},new[oi],dc[oi],second[oi])
  d['_optimization_parity']=fast_geometry.compare(expected,actual)
 current=arms['FUSION790'];raw=d['raw'];variants={'RAW':raw,'C5_FROZEN':d['old_c5']}
 for dim,sup in [('2D',old['support']),('3D',new)]:
  for label,scales in [('FUSION',current['scales']),('OLD',arms['OLD782']['scales'])]:variants['C5_'+dim+'_'+label]=c.four(c.correction(raw[:,:3],sup,d['q'],scales))
 err=float(np.max(np.abs(variants['C5_2D_FUSION']-d['old_c5'])));flips=int(np.count_nonzero((variants['C5_2D_FUSION']>current['cuts'])!=(d['old_c5']>current['cuts'])))
 assert err<=2e-10 and flips==0,'EXPANDED_2D_FROZEN_PARITY_GATE_SCORE'
 for v in variants.values():assert not np.any((v>current['cuts'])&~(raw>current['cuts']))
 for label in ['FUSION','OLD']:assert np.all(variants['C5_3D_'+label]>=variants['C5_2D_'+label]-2e-10)
 gate=dict(status='PASS',support_max_abs_error=support_audit['max_abs_error'],score_max_abs_error=err,decision_differences=flips,support_compared_rows=len(parity),support_excluded_rows=0,support_storage_contract=support_audit,score_compared_rows=len(parity),untouched_devices_included=True)
 return old,new,dc,second,variants,gate,time.monotonic()-start

def main(phase):
 w.PHASE=phase;c,k,norm,arms,inputs,context,core,reporting,metrics=w.initialize();c.core=core
 start=time.monotonic();spec=w.read(HERE/'SPEC.json');prior=w.read(c.pin(PRIOR/'PREFLIGHT_RESULT.json',spec['prior_preflight_sha256']));oldresult=w.read(c.pin(PRIOR/'DIAGNOSE_RESULT.json',spec['prior_result_sha256']))
 rhoc=prior['calibration']['protocols'];geom=c.read(c.HERE/'METHOD_FREEZE.json')['calibration']['geometry'];out=dict(status='PASS',training=False,deployment_change=False,phase=phase,pools={},calibration=prior['calibration']['protocols']);forecast=0
 if phase!='PREFLIGHT':pre=w.read(HERE/'PREFLIGHT_RESULT.json');assert pre['status']=='PASS'
 for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
  w.progress('LOAD_'+pool);d=w.load(pool,c,inputs,context);dense=w.reference_bank(pool,d,c);refs,rz,rq=dense
  cache=prior['pools'][pool]['reference_context'];a=np.load(c.pin(PRIOR/cache['file'],cache['sha256']));assert a['uid'].tolist()==[r['uid'] for r in refs];dense_x=a['features'].copy();a.close()
  if pool!='EDGE':
   history=hist.load_history(pool,c);hr=history[0];refs,rz,rq=hist.union(dense,history)
   assert not set(r['uid'] for r in hr)&set(r['uid'] for r in d['rows'])
   if phase=='PREFLIGHT':
    oracle,oracle_receipts=hist.contexts(pool,hr,c,w.progress,small=True)
    full,receipts=hist.contexts(pool,hr,c,w.progress)
    assert all(np.array_equal(x,full[u]) for u,x in oracle.items()),'SMALL_FULL_CONTEXT_PARITY'
    hx=np.asarray([full[r['uid']] for r in hr]);hc=w.save_array(pool+'_HISTORY_CONTEXT',uid=np.asarray([r['uid'] for r in hr]),features=hx)
   else:
    hc=pre['pools'][pool]['history_context'];a=np.load(c.pin(HERE/hc['file'],hc['sha256']));assert a['uid'].tolist()==[r['uid'] for r in hr];hx=a['features'].copy();a.close()
   rc=c.extra_normalized(np.concatenate([dense_x,hx]))
  else:rc=c.extra_normalized(dense_x)
  total=len(d['rows']);full_d=d
  if phase=='PREFLIGHT':
   ix=w.select_small(d);d=w.subset(d,ix)
   if pool=='EDGE':
    import preflight_encoder
    preflight_encoder.progress=w.progress;out['real_encoder']=preflight_encoder.run(full_d,norm)
  old,new,dc,second,variants,gate,elapsed=evaluate(pool,d,refs,rz,rq,rc,c,norm,arms,geom,rhoc,reporting)
  rec=dict(rows=len(d['rows']),full_rows=total,reference_rows=len(refs),reference_uid_sha256=core._uid_hash([r['uid'] for r in refs]),parity_gate=gate,distance_seconds=elapsed)
  if phase=='PREFLIGHT':
   rec['history_rows']=0 if pool=='EDGE' else len(hr)
   if pool!='EDGE':rec.update(history_context=hc,history_replay=receipts,oracle_replay=oracle_receipts)
   timing=d['_distance_timing'];counts=collections.Counter((r['partition'],r['device'],r['protocol']) for r in full_d['rows'])
   assert {tuple(v['key']) for v in timing['groups']}==set(counts),'FORECAST_GROUP_COVERAGE'
   for item in timing['groups']:
    item['full_rows']=counts[tuple(item['key'])];item['projected_seconds']=item['seconds']*item['full_rows']/item['rows']
   projected=timing['setup_seconds']+sum(item['projected_seconds'] for item in timing['groups'])
   forecast+=projected*1.5;rec['timing']=timing;rec['projected_seconds_with_margin']=projected*1.5;rec['optimization_parity']=d['_optimization_parity']
   for arm,expected in [('FUSION790',d['raw']),('STATS8',d['stats8'])]:assert np.max(np.abs(c.four(c.score(k,norm,arms[arm],d['z'],d['q'],d['context']))-expected))<.002
  else:
   rec['views']=all_metrics(pool,d,variants,arms['FUSION790']['cuts'],reporting)
   rec['metrics']=rec['views']['full' if pool=='EDGE' else 'post_window_primary']
   if pool!='EDGE':rec['donor_retention']=retention(pool,d,old,new,dc,refs,rhoc,variants,arms['FUSION790']['cuts'])
   else:
    for name,hh in rec['metrics'].items():
     for head,rr in hh.items():
      for role,v in rr.items():
       expected=oldresult['pools']['EDGE']['metrics'][name][head][role]
       assert v['rows']==expected['rows'] and v['alarm_count']==expected['alarm_count']
       for key in ['sample_rate','hierarchical_rate','HT_rate']:assert abs(v[key]-expected[key])<=2e-10,'EDGE_UNCHANGED_GATE'
    rec['edge_unchanged_gate']='PASS'
   stored2,stored_zero=support_contract.stored_view(pool,d['rows'],d['q'],old['support'])
   rec['artifact']=w.save_array(pool+'_SAME_BANK',uid=np.asarray([r['uid'] for r in d['rows']]),support2=old['support'],support2_stored_view=stored2,support_frozen=d['support_frozen'],c2_stored_zero_mask=stored_zero,support3=new,matched_context_distance=dc,matched_reference_uid=np.asarray(old['matched_reference_uids'],dtype='U64'),**variants)
  out['pools'][pool]=rec
  if phase=='PREFLIGHT':w.write('PREFLIGHT_PARTIAL.json',out)
  if phase!='PREFLIGHT':w.write(pool+'_RESULT.json',rec);w.write('BOARD.json',{p:r['metrics'] for p,r in out['pools'].items()})
  del d,full_d,dense,refs,rz,rq,rc,old,new,dc,second,variants;gc.collect()
 if phase=='PREFLIGHT':
  forecast+=600;out['forecast_seconds']=forecast;w.write('RUNTIME_FORECAST.json',dict(status='PASS' if forecast<5400 else 'STOP',seconds=forecast,budget=5400,setup_counted_once=True,pools={p:r['timing'] for p,r in out['pools'].items()}));assert forecast<5400,'FULL_RUNTIME_FORECAST_EXCEEDS_BUDGET'
 out.update(seconds=time.monotonic()-start,rss_peak_bytes=w.PEAK,scope='CONSUMED_DATA_SAME_BANK_POSTPROCESSING_ONLY');w.write(phase+'_RESULT.json',out);w.progress(phase+'_COMPLETE',1,1)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--phase',choices=['PREFLIGHT','DIAGNOSE'],required=True);args=a.parse_args();w.PHASE=args.phase
 try:main(args.phase)
 except BaseException as e:
  w.write(args.phase+'_STOP.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
