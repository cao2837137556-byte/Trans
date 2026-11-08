import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 checks=0
 def ck(v,label):
  nonlocal checks
  assert v,label
  checks+=1
 for n,h in read('RETRIEVAL.json')['sha256'].items():ck(sha(HERE/n)==h,'receipt:'+n)
 d=read('DELIVERY.json')
 for n,h in d['pins'].items():ck(sha(HERE/n)==h,'package:'+n)
 ck(sha(HERE/'receiver.py')==d['receiver_sha256'],'receiver')
 ck(sha(HERE.parents[1]/'runs/paper_results_freeze_v1_20261107/METHOD_FREEZE.json')==sha(HERE/'METHOD_FREEZE.json'),'main freeze')
 ck('182752|COMPLETED|0:0|00:50:29|' in read('SCHEDULER.json')['stdout'],'scheduler')
 result=read('RESULT.json');spec=read('SPEC.json');ck(set(result['results'])==set(spec['phases']),'phases')
 for phase in spec['phases']:
  r=read(phase+'_RESULT.json');ck(r==result['results'][phase] and r['status']=='PASS',phase)
  ck(r['seconds']<spec['phase_caps_seconds'][phase] and r['rss_peak_mib']<6656,phase+' resources')
 s=read('SPLIT_RESULT.json');ck(s['training_rows']==457120 and s['validation_rows']==160788,'split counts')
 ck(s['device_class_coverage'] and s['capture_session_component_disjoint'],'isolation')
 ck(len(s['strata'])==12 and all(v['train_rows']>0 and v['validation_rows']>0 for v in s['strata']),'device class coverage')
 ck(s['strata']==read('SOURCE_SPLIT_PROPOSAL.json')['strata'],'proposal parity')
 missing=s['activity_protocol_missing'];ck(len(missing)==57 and sum(v['field']=='protocol' for v in missing)==5,'coverage gaps')
 ck(s['secondary_coverage_gate']=='NEEDS_REVIEW' and not s['target_scores_used'],'coverage not released')
 enc=read('PIPELINE_RESULT.json')['encoder'];ck(enc['encoded_rows']==112 and enc['e3_max_abs_error']==enc['fresh_support_error']==enc['cached_support_error']==0,'real pipeline')
 for phase,batch,n in [('DTE_EPOCH',64,134493),('TABM_EPOCH',256,617908)]:
  r=read(phase+'_RESULT.json');ck(r['train_rows']==n and r['steps']==math.ceil(n/batch) and r['full_epoch'],phase+' epoch')
  ck(r['same_process_optimizer_rng_cursor_replay_exact'] is True and r['fresh_process_resume_gate']=='PENDING',phase+' resume scope')
 for phase in ['DTE_EPOCH','SLAD_EPOCH','TABM_EPOCH']:
  r=read(phase+'_RESULT.json');ck(r['validation_rows']==160788 and not r['formal_training'] and 'validation overlap' in r['purpose'],phase+' score scope')
 ck(read('SLAD_EPOCH_RESULT.json')['same_process_optimizer_rng_cursor_replay_exact']=='PENDING_AUTHOR_TRANSFORM_RNG_STATE','SLAD resume pending')
 out=dict(status='ENGINEERING_ACCEPTED_TUNING_RELEASE_BLOCKED',checks=checks,job_id='182752',scheduler_seconds=3029,worker_seconds=result['seconds'],peak_gib=max(3355060/1024**2,max(v['rss_peak_mib'] for v in result['results'].values())/1024),device_class_and_isolation_gate='PASS',activity_protocol_gate='NEEDS_FEASIBILITY_AUDIT',coverage_gap_slices=len(missing),protocol_gap_slices=5,formal_training_ready=False,main_model_changed=False,new_jobs_submitted=False,large_artifacts='HPC_ONLY',next=['Audit independent group counts by device/label/protocol/activity before redesigning splits','Prioritize protocol-aware whole-group coverage; single-group strata cannot be split across both sides without leakage','Fresh-process resume and remaining methods resource qualification','Freeze explicit tuning configurations and final hardware budgets'],receipt_sha256=read('RETRIEVAL.json')['sha256'])
 (HERE/'ACCEPTANCE.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='receipt_sha256'},ensure_ascii=False))
if __name__=='__main__':main()
