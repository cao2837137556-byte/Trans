"""Fail-closed specification freeze after successful scheduler receipts; no training."""
import copy,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
FILES=['PREFLIGHT_RESULT.json','FULL_RESULT.json','PREFLIGHT_SCHEDULER.json','FULL_SCHEDULER.json','TRAINING_SPEC_PROPOSED.json','VALIDATION_PLAN.json','SLICES.json','stream_core.py','worker.py','packet_reader.py','test_core.py']
def read(n):return json.loads((HERE/n).read_text())
def sha(n):return hashlib.sha256((HERE/n).read_bytes()).hexdigest()
def freeze():
 config=read('.private.json')
 for n,h in config['pins'].items():assert sha(n)==h,'SOURCE_CHANGED:'+n
 for phase in ['PREFLIGHT','FULL']:
  r=read(phase+'_RESULT.json');job=read(phase+'_JOB.json')['job_id'];assert r['status']=='PASS' and not r['failures'] and r['real_training']==0
  assert job+'|COMPLETED|0:0|' in read(phase+'_SCHEDULER.json')['stdout']
  assert r['plan_sha256']==sha('VALIDATION_PLAN.json') and r['stream_source_sha256']==sha('stream_core.py')
  assert not (HERE/(phase+'_STOP.json')).exists()
 plan=read('VALIDATION_PLAN.json');full=read('FULL_RESULT.json')
 assert full['stress']['events_per_second']>=plan['gates']['synthetic_core_min_events_per_second']
 for role,v in full['roles'].items():
  assert v['oracle']['queries_checked']==plan['slice_counts'][role]
  assert all(v['oracle'][k]==0 for k in ['integer_mismatches','float_mismatches','restart_mismatches'])
  assert v['stream']['frames_per_second']>=plan['gates']['full_real_min_frames_per_second']
  assert v['stream']['max_clock_debt_ns']<=plan['gates']['max_real_clock_debt_ns']
  assert v['stream']['rss_peak_bytes']<=plan['limits']['rss_limit_bytes']
 value=copy.deepcopy(read('TRAINING_SPEC_PROPOSED.json'));value['status']='FROZEN_TRAINING_SPEC_NOT_STARTED'
 value['validation_pins']={n:sha(n) for n in FILES}
 value['execution']['wall_seconds_per_head']={d:v['proposed_wall_seconds'] for d,v in full['cost']['dimensions'].items()}
 value['execution']['estimate_limitations']=full['cost']['limitations']
 value['execution']['source_asset_execution_admission']='PENDING: specification freeze does not establish complete source raw availability or feature readiness'
 payload=(json.dumps(value,indent=2)+'\n').encode();target=HERE/'TRAINING_SPEC_FROZEN.json';assert not target.exists(),'FREEZE_ALREADY_EXISTS';target.write_bytes(payload)
 receipt=dict(result='PASS_SPECIFICATION_FROZEN',impact='Engineering streaming gate passed; no new detection-quality claim or training execution',next='Source asset/feature admission and same-runtime training smoke before separate training submission',status='PASS',spec_sha256=hashlib.sha256(payload).hexdigest(),evidence_pins=value['validation_pins'],automatic_training_jobs=0,training_started=False,big_artifacts='HPC only')
 (HERE/'TRAINING_FREEZE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':print(json.dumps(freeze()))
