"""Mechanical artifact gate; scientific interpretation remains explicit review."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text(encoding='utf-8-sig'))
def sha(n):return hashlib.sha256((HERE/n).read_bytes()).hexdigest()
def accept():
 retrieval=read('RETRIEVAL.json');assert retrieval['state']['stage']=='PASS'
 for name,value in retrieval['sha256'].items():assert sha(name)==value
 for phase in ['PREFLIGHT','FULL']:
  result=read(phase+'_RESULT.json');assert result['status']=='PASS' and result['plan_sha256']==sha('PLAN.json')
  job=retrieval['state'][phase+'_JOB']['job_id'];scheduler=retrieval['state'][phase+'_SCHEDULER']['stdout'];assert job+'|COMPLETED|0:0|' in scheduler
  for name,value in result['summary_pins'].items():assert sha(name)==value
  assert result['training']==result['threshold_fit']==result['source_writes']==0
  ab=read(phase+'_ABLATION_SUMMARY.json');cross=read(phase+'_CROSS_SUMMARY.json')
  assert ab['status']==cross['status']=='PASS' and ab['baseline_max_e3_error']<=.0002 and ab['baseline_max_head_error']<=.002
  assert cross['real_brute_force_queries_checked']>=8
 full=read('FULL_RESULT.json');assert full['ablation_rows']==200 and full['cross_queries']=={'NORMAL':20000,'HTTP':20000,'UDP':20000}
 result=dict(status='DIAGNOSTIC_ARTIFACT_PASS_PENDING_SCIENTIFIC_REVIEW',result='Real preflight and full diagnostic completed with source/summary SHA verification',impact='Mechanism evidence ready; not repaired model acceptance',next='Review paired margins and protocol/segment matched separability before choosing a repair',sha256=retrieval['sha256'])
 (HERE/'ARTIFACT_ACCEPTANCE.json').write_text(json.dumps(result,indent=2));return result
if __name__=='__main__':print(json.dumps(accept()))
