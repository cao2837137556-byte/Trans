"""Take one bounded startup acceptance snapshot; do not poll the experiment."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

REV=Path(__file__).resolve().parent
ROOT=REV.parents[2]
PACKAGE=Path('runs/learned_onboarding_v1_20261023')
OPS=REV/'deployment_20261024/operations'
helper_path=ROOT/PACKAGE/'deployment_20261024/local_ops/deploy.py'
spec=importlib.util.spec_from_file_location('v3_startup_acceptance_helper',helper_path)
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.OPS=OPS
code=r'''import datetime,json,pathlib,subprocess
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v3')
state=root/'state'
def read(path):
 return json.loads(path.read_text()) if path.is_file() else None
show=subprocess.run(['systemctl','show','paper04-learned-onboarding-20261024-v3',
 '--property=ActiveState,SubState,MainPID,InvocationID,MemoryCurrent,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,Environment'],
 capture_output=True,text=True,check=True).stdout
properties=dict(line.split('=',1) for line in show.splitlines() if '=' in line)
status=read(state/'status.json')
result=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),properties=properties,
 status=status,exception=read(state/'EXCEPTION_STOP.json'),
 tests=read(state/'stages/tests/tests.json'),adapter=read(state/'stages/tests/adapter_validation.json'),
 test_runtime=read(state/'stages/tests/runtime.json'),
 launch=read(root/'LAUNCH_RECEIPT.json'),slot=read(root/'EXECUTION_SLOT_RECEIPT.json'),
 deployment=read(root/'DEPLOYMENT_VERIFIED.json'),hard_limits=read(root/'SERVICE_HARD_LIMIT_RECEIPT.json'))
if status and status.get('stage'):
 result['stage_exception']=read(state/'stages'/status['stage']/'child_exception.json')
 result['worker']=read(root/'runs/learned_onboarding_v1_20261023/results'/status['stage']/'status.json')
print(json.dumps(result))
'''
body=helper.remote(code,'STARTUP_ACCEPTANCE_SNAPSHOT.json',timeout=30)
snapshot=json.loads(body)
assert snapshot['properties']['ActiveState']=='active' and snapshot['properties']['SubState']=='running','SERVICE_NOT_RUNNING'
assert snapshot['exception'] is None and snapshot.get('stage_exception') is None,'STARTUP_EXCEPTION'
assert snapshot['status']['status']=='RUNNING','CHAIN_NOT_RUNNING'
assert snapshot['tests']['status']=='PASS' and snapshot['tests']['tests_run']==54,'REMOTE_TESTS_NOT_ACCEPTED'
assert snapshot['tests']['failures']==snapshot['tests']['errors']==snapshot['tests']['skipped']==0
assert snapshot['adapter']['status']=='PASS' and snapshot['adapter']['tests_run']==4
assert snapshot['adapter']['real_target_queries_read']==0
assert snapshot['test_runtime']['runtime']['network_inference_backend']=='learned-onboarding-rowwise-float32-v3-20261024'
assert snapshot['properties']['MemoryMax']==str(16*1024**3) and snapshot['properties']['MemorySwapMax']=='0'
assert snapshot['properties']['CPUQuotaPerSecUSec']=='8s' and snapshot['properties']['Restart']=='no'
receipt=dict(schema='learned-onboarding-independent-v3-execution-receipt-v1',
 status='STARTUP_ACCEPTED_FULL_CHAIN_RUNNING',recorded_at=datetime.now(timezone.utc).isoformat(),
 checked_at=snapshot['checked_at'],authorization='修复好了，就可以启动实验了。',
 remote_root='/srv/paper04/learned_onboarding_20261024_v3',unit='paper04-learned-onboarding-20261024-v3',
 invocation_id=snapshot['properties']['InvocationID'],
 started_at=snapshot['launch']['at'],stage=snapshot['status']['stage'],
 completed_stages=snapshot['status']['completed_stages'],
 remote_unittests=snapshot['tests'],adapter_validation=snapshot['adapter'],
 numerical_backend=snapshot['test_runtime']['runtime']['network_inference_backend'],
 prior_attempts_preserved=True,automatic_retry=False,full_chain_authorized=True,
 current_memory_bytes=int(snapshot['properties']['MemoryCurrent']),
 peak_process_tree_rss=snapshot['status']['peak_process_tree_rss'],
 fit_completed='fit' in snapshot['status']['completed_stages'],
 calibration_completed='calibration' in snapshot['status']['completed_stages'],
 target_evaluation_completed='evaluation' in snapshot['status']['completed_stages'],
 scientific_results='PENDING',future_phase_results='UNKNOWN_NOT_POLLED',
 progress_url='http://127.0.0.1:18765/',evidence='operations/STARTUP_ACCEPTANCE_SNAPSHOT.json')
helper.write(REV/'deployment_20261024/EXECUTION_RECEIPT.json',receipt)
print(json.dumps(receipt))
