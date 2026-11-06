"""Accept the complete fixed diagnostic matrix without selecting by outcome."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def accept():
 r=read('RETRIEVAL.json');assert r['state']['stage']=='DIAGNOSIS_COMPLETE'
 for n,h in r['sha256'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h
 for phase in ['PREFLIGHT','DIAGNOSE']:
  assert read(phase+'_RESULT.json')['status']=='PASS';j=read(phase+'_JOB.json');assert j['job_id']+'|COMPLETED|0:0|' in read(phase+'_SCHEDULER.json')['stdout']
 result=read('DIAGNOSE_RESULT.json');assert set(result['pools'])=={'CIC_DEV','UNSW_DEV','EDGE'}
 for pool,n in [('CIC_DEV',179886),('UNSW_DEV',148316),('EDGE',60000)]:
  v=result['pools'][pool];assert v['rows']==n and set(v['forward_checks'])=={'OLD782','REFIT782','STATS8','FUSION790'}
  for arm,report in v['functional_summary'].items():assert set(report['coalitions'])=={str(i) for i in range(8)} and len(report['permutations'])==6
 a=dict(result='PASS',scope='DIAGNOSTIC_EXECUTION_ONLY',interpretation_pending=True,receipt_sha256=r['sha256'],training=False,threshold_fitting=False,large_artifacts='HPC_ONLY')
 (HERE/'FINAL_DIAGNOSIS_ACCEPTANCE.json').write_bytes((json.dumps(a,indent=2)+'\n').encode());return a
if __name__=='__main__':print(accept()['result'])
