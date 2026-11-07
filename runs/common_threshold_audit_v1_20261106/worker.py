import argparse,gc,hashlib,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
from core import analyze
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=HERE.parent/'pilot_transfer_evaluation_v1_20261106';PHASE='PREFLIGHT';PEAK=0
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,v):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):
 global PEAK
 PEAK=max(PEAK,psutil.Process().memory_info().rss);assert PEAK<7*1024**3
 write(PHASE+'_PROGRESS.json',dict(stage=stage,done=done,total=total,rss_mib=PEAK/2**20,**kw))
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 start=time.monotonic()
 for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,n
 import dependency_gate
 dependency_gate.verify(ROOT,read(HERE/'INPUT_PINS.json'))
 sys.path.insert(0,str(OLD));w=module('frozen_eval',OLD/'worker.py');w.progress=progress
 c,k,norm,arms,inputs,ctx,metrics,reporting=w.initialize();inputs.progress=progress
 if PHASE=='PREFLIGHT':
  import preflight_encoder
  preflight_encoder.progress=progress;d=inputs.edge();encoder=preflight_encoder.run(d,norm);del d;gc.collect()
 else:assert read(HERE/'PREFLIGHT_RESULT.json')['status']=='PASS'
 data={};parity=0
 for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
  progress('LOAD_'+pool);d=inputs.edge() if pool=='EDGE' else inputs.ab(pool)
  rec=read(OLD/('EDGE_RESULT.json' if pool=='EDGE' else 'AB_RESULT.json'));part=rec if pool=='EDGE' else rec['pools'][pool]
  path=c.pin(part['scores']['path'],part['scores']['sha256']);a=np.load(path,allow_pickle=False)
  assert a['uid'].tolist()==[r['uid'] for r in d['rows']]
  rows=d['rows'];specs={}
  if pool=='EDGE':
   expansion,_=reporting._weights(rows);hier=reporting._hierarchical_weights(rows)
   for role in ['NORMAL','HTTP','UDP']:
    ix=np.array([i for i,r in enumerate(rows) if r['source_role']==role]);N=rec['arms']['FUSION790']['methods']['RAW']['heads']['ensemble']['roles'][role]['population_count']
    for basis,weights,den in [('sample',np.ones(len(ix)),len(ix)),('hierarchical',hier[ix],float(hier[ix].sum())),('HT',expansion[ix],N)]:specs[basis+'/'+role]=(ix,weights,den)
  else:
   keep,weights=d['views']['primary']
   for role,label in [('NORMAL',0),('ATTACK',1)]:
    ix=np.array([i for i in keep if rows[int(i)]['label']==label])
    specs['sample/'+role]=(ix,np.ones(len(ix)),len(ix));specs['hierarchical/'+role]=(ix,weights[ix],float(weights[ix].sum()))
  scores={key:a[key].copy() for key in a.files if key!='uid' and not key.startswith('OLD782')};a.close()
  for arm in ['FUSION790','RISK_UNIFORM','RISK_STRATIFIED','RISK_GUARDED']:
   for method in ['RAW','C5_P3']:
    for j,head in enumerate(['27','127','227','ensemble']):
     for key,(ix,weights,den) in specs.items():
      basis,role=key.split('/');pred=scores[arm+'_'+method][ix,j]>arms[arm]['cuts'][j]
      if pool=='EDGE':
       r=rec['arms'][arm]['methods'][method]['heads'][head]['roles'][role];expected=r[{'sample':'exact_selected_sample_alarm_rate','hierarchical':'selected_hierarchical_alarm_rate','HT':'ht_population_alarm_estimate'}[basis]]
      else:expected=part['primary'][arm][method][head]['groups']['pool']['normal' if role=='NORMAL' else 'attack']['unweighted_rate' if basis=='sample' else 'weighted_rate']
      assert abs(float(weights[pred].sum())/den-expected)<2e-11;parity+=1
  data[pool]=(scores,specs);del d,rows;gc.collect()
 out={};completed=0
 for arm in ['FUSION790','RISK_UNIFORM','RISK_STRATIFIED','RISK_GUARDED']:
  out[arm]={}
  for method in ['RAW','C5_P3']:
   out[arm][method]={}
   for j,head in enumerate(['27','127','227','ensemble']):
    groups={}
    for pool,(scores,specs) in data.items():
     for key,(ix,weights,den) in specs.items():
      if PHASE=='PREFLIGHT':ix=ix[:31];weights=weights[:31];den=float(weights.sum())
      groups[pool+'/'+key]=dict(scores=scores[arm+'_'+method][ix,j],weights=weights,denominator=den)
    out[arm][method][head]=analyze(groups,float(arms[arm]['cuts'][j]));completed+=1;progress('COMMON_THRESHOLD_SCAN',completed,32)
 if PHASE=='SCAN':write('BOARD.json',{'threshold_diagnostic':out})
 result=dict(status='PASS',phase=PHASE,seconds=time.monotonic()-start,rss_peak_bytes=PEAK,original_rate_parity_checks=parity,results=out,training=False,deployment_threshold_changed=False,scope='CONSUMED_DATA_EMPIRICAL_FEASIBILITY_NOT_DEPLOYMENT')
 if PHASE=='PREFLIGHT':result['real_encoder_distance']=encoder
 write(PHASE+'_RESULT.json',result);progress(PHASE+'_COMPLETE',1,1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['PREFLIGHT','SCAN'],required=True);PHASE=p.parse_args().phase
 try:main()
 except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
