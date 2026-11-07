"""Accept only measured engineering results and unchanged delivery bytes."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def main():
 retrieval=read('RETRIEVAL.json')
 for n,h in retrieval['sha256'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h
 for n,h in read('DELIVERY.json')['pins'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h
 result=read('RESULT.json');assert result['status']=='PASS' and result['scope']=='ENGINEERING_ONLY' and result['full_training_authorized'] is False
 assert '182677|COMPLETED|0:0|' in read('SCHEDULER.json')['stdout']
 assert read('JOB.json')==dict(job_id='182677',cpu=1,memory_gib=8,wall_seconds=7200)
 phases={p:read(p+'_RESULT.json') for p in ['PIPELINE','TabM','ModernNCA','DisentAD']}
 for p,v in phases.items():
  assert v==result['results'][p] and v['status']=='PASS' and v['rss_peak_mib']<7168 and v['seconds']<(1800 if p=='PIPELINE' else 1500)
  if p!='PIPELINE':assert v['updates']==16 and v['seed']==27 and v['reload_exact'] and v['source_cal_weighted_fpr']<=.010000000001 and not v['full_training_qualified']
 r=phases['PIPELINE'];assert r['fit_rows']==r['cal_normal_rows']==1024 and r['target_rows']==dict(CIC_DEV=64,UNSW_DEV=64,EDGE=32)
 assert r['encoder']['encoded_rows']==112 and r['encoder']['encoded_batches']==7
 assert all(r['encoder'][k]==0 for k in ['e3_max_abs_error','cached_support_error','fresh_support_error'])
 assert phases['TabM']['fit_rows']==phases['ModernNCA']['fit_rows']==1024 and phases['DisentAD']['fit_rows']==564
 out=dict(status='PASS',scope='REAL_INPUT_ENGINEERING_QUALIFICATION_ONLY',job_id='182677',full_training_authorized=False,main_model_changed=False,seconds=result['seconds'],scheduler_elapsed='00:03:36',peak_sampled_tree_rss_mib=max(v['rss_peak_mib'] for v in phases.values()),scheduler_maxrss='1819208K',causal_frames=sum(v['frames'] for v in r['causal'].values()),real_encoded_rows=112,qualified_pilot_methods=['TabM','ModernNCA','DisentAD'],other_candidates_pending=True,formal_training_scaling_pending=True,receipt_sha256=retrieval['sha256'])
 (HERE/'ACCEPTANCE.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in out.items() if k!='receipt_sha256'}))
if __name__=='__main__':main()
