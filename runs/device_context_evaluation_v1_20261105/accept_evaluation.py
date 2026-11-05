"""Accept execution separately from scientific efficacy; small receipts only."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def accept():
 receipts=read('RETRIEVAL.json');pins=receipts['sha256'];assert receipts['state']['stage']=='EVALUATION_COMPLETE'
 for n,h in pins.items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h
 for phase in ['PREFLIGHT','CONTEXT','AB','EDGE']:
  assert read(phase+'_RESULT.json')['status']=='PASS'
  job=read(phase+'_JOB.json');assert job['cpu']==1 and job['memory_gib']==8
  assert job['job_id']+'|COMPLETED|0:0|' in read(phase+'_SCHEDULER.json')['stdout']
 edge=read('EDGE_RESULT.json');assert edge['rows']==60000 and set(edge['arms'])=={'OLD782','REFIT782','STATS8','FUSION790'}
 for arm,r in edge['arms'].items():
  assert set(r['methods'])==({'RAW'} if arm=='STATS8' else {'RAW','C5_P3'})
  for m in r['methods'].values():assert set(m['heads'])=={'27','127','227','ensemble'}
 ab=read('AB_RESULT.json');gates={k:v['gates']['status'] for k,v in ab['pools'].items()};gates['CAL']=ab['source_cal']['gates']['status']
 result=dict(result='PASS',scope='ENGINEERING_COMPLETION_NOT_EFFICACY',scientific_gates=gates,receipt_sha256=pins,large_artifacts='HPC_ONLY',next='Review all arms, RAW/C5 margins and regression failures; no automatic tuning')
 (HERE/'FINAL_EVALUATION_ACCEPTANCE.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());return result
if __name__=='__main__':print(accept()['result'])
