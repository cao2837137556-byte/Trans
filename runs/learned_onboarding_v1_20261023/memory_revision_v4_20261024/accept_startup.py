"""One ordinary bounded startup wait, ending at preflight or an exception."""
from datetime import datetime, timezone
import json
import execute_authorized_v4 as deploy

CODE = r'''import datetime,json,pathlib,subprocess,time
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4');state=root/'state'
package=root/'runs/learned_onboarding_v1_20261023'
unit='paper04-learned-onboarding-20261024-v4'
def read(path):return json.loads(path.read_text()) if path.is_file() else None
def properties():
 q=subprocess.run(['systemctl','show',unit,'--property=ActiveState,SubState,MainPID,InvocationID,MemoryCurrent,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,Environment,NRestarts,ExecMainStatus,Result'],capture_output=True,text=True,check=True,timeout=5)
 return dict(line.split('=',1) for line in q.stdout.splitlines() if '=' in line)
deadline=time.monotonic()+600
while True:
 status=read(state/'status.json');exception=read(state/'EXCEPTION_STOP.json');props=properties()
 plan=read(package/'results/preflight/resource_plan.json')
 if exception or (status and status.get('status') in ('EXCEPTION_STOP','COMPLETE')):break
 if props.get('ActiveState') not in ('active','activating'):break
 if status and 'preflight' in status.get('completed_stages',[]) and plan:break
 if time.monotonic()>=deadline:break
 time.sleep(5)
result=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),ordinary_program_wait=True,
 properties=props,status=status,exception=exception,preflight=plan,
 tests=read(state/'stages/tests/tests.json'),adapter=read(state/'stages/tests/adapter_validation.json'),
 runtime=read(state/'stages/tests/runtime.json'),launch=read(root/'LAUNCH_RECEIPT.json'),
 deployment=read(root/'DEPLOYMENT_VERIFIED.json'),hard_limits=read(root/'SERVICE_HARD_LIMIT_RECEIPT.json'),
 source_archive=read(root/'inputs/source_head_archive/BACKUP_INDEX.json'))
if status and status.get('stage'):
 result['stage_exception']=read(state/'stages'/status['stage']/'child_exception.json')
 result['worker']=read(package/'results'/status['stage']/'status.json')
 result['stage_process_exit']=read(state/'stages'/status['stage']/'process_exit.json')
for name in ('service.stdout.log','service.stderr.log'):
 path=root/name
 if path.is_file():
  with path.open('rb') as stream:
   stream.seek(max(0,path.stat().st_size-3000));result[name]=stream.read().decode('utf-8','replace')
print(json.dumps(result))
'''


def main():
    assert not (deploy.OUT/'EXECUTION_RECEIPT.json').exists(), 'STARTUP_ALREADY_ACCEPTED'
    snapshot = deploy.remote(CODE, 'STARTUP_ACCEPTANCE_SNAPSHOT.json', timeout=650)
    properties, status = snapshot['properties'], snapshot['status']
    assert properties['ActiveState'] == 'active' and properties['SubState'] == 'running', 'SERVICE_NOT_RUNNING'
    assert snapshot['exception'] is None and snapshot.get('stage_exception') is None, 'STARTUP_EXCEPTION'
    assert status['status'] == 'RUNNING' and 'preflight' in status['completed_stages'], 'PREFLIGHT_NOT_COMPLETED'
    tests, adapter, plan = snapshot['tests'], snapshot['adapter'], snapshot['preflight']
    assert tests['status'] == 'PASS' and tests['tests_run'] == 63, 'REMOTE_TESTS_NOT_ACCEPTED'
    assert tests['failures'] == tests['errors'] == tests['skipped'] == 0
    assert adapter['status'] == 'PASS' and adapter['tests_run'] == 4 and adapter['real_target_queries_read'] == 0
    assert plan['status'] == 'READY' and plan['full_scale_memory_validation']['status'] == 'VERIFIED'
    package = json.loads((deploy.OUT/'PACKAGE_RECEIPT.json').read_text(encoding='utf-8'))
    assert plan['full_scale_memory_validation']['receipt_sha256'] == package['full_scale_memory_receipt_sha256']
    assert properties['MemoryMax'] == str(16*1024**3) and properties['MemorySwapMax'] == '0'
    assert properties['CPUQuotaPerSecUSec'] == '8s' and properties['Restart'] == 'no'
    assert properties['KillMode'] == 'control-group' and properties['NRestarts'] == '0'
    assert status['rss_guard_bytes'] == 8*1024**3 and status['peak_process_tree_rss'] <= 8*1024**3
    assert snapshot['runtime']['runtime']['torch_threads'] == 4 and snapshot['runtime']['runtime']['deterministic']
    assert properties['InvocationID'] == snapshot['hard_limits']['properties']['InvocationID']
    receipt = dict(schema='learned-onboarding-independent-v4-execution-receipt-v1',
        status='STARTUP_ACCEPTED_PREFLIGHT_READY_FULL_CHAIN_RUNNING',
        recorded_at=datetime.now(timezone.utc).isoformat(), checked_at=snapshot['checked_at'],
        authorization='\u53ef\u4ee5\u52a8\u624b\u8fd0\u884c\u3002', remote_root=deploy.REMOTE, unit=deploy.UNIT,
        invocation_id=properties['InvocationID'], started_at=snapshot['launch']['at'], stage=status['stage'],
        completed_stages=status['completed_stages'], remote_unittests=tests, adapter_validation=adapter,
        preflight_status=plan['status'], full_scale_memory_validation=plan['full_scale_memory_validation'],
        estimated_peak_rss=plan['estimated_peak_rss'], current_memory_bytes=int(properties['MemoryCurrent']),
        peak_process_tree_rss=status['peak_process_tree_rss'], prior_attempts_preserved=True,
        automatic_retry=False, full_chain_authorized=True,
        fit_completed='fit' in status['completed_stages'], calibration_completed='calibration' in status['completed_stages'],
        target_evaluation_completed='evaluation' in status['completed_stages'], scientific_results='PENDING',
        future_phase_results='UNKNOWN_NOT_POLLED', progress_url='http://127.0.0.1:18765/',
        evidence='operations/STARTUP_ACCEPTANCE_SNAPSHOT.json')
    deploy.write(deploy.OUT/'EXECUTION_RECEIPT.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
