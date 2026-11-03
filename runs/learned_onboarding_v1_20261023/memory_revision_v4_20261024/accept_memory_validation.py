"""Accept completed source proof, then run one bounded direct preflight.

--self-test performs only synthetic decision tests; it never calls SSH.
No experiment is restarted and no failed acceptance is retried.
"""
import ast
import base64
import hashlib
import inspect
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

import execute_source_validation as run

RSS_LIMIT = 8*1024**3


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_source_final(unit, status, exceptions, proof, source_code):
    require(unit.get('ActiveState') == 'inactive' and str(unit.get('MainPID')) == '0'
            and unit.get('Result') == 'success' and str(unit.get('ExecMainStatus')) == '0',
            'SOURCE_UNIT_NOT_SUCCESSFULLY_EXITED')
    require(not exceptions, 'SOURCE_EXCEPTION_ARTIFACT_PRESENT')
    require(status.get('status') == 'PASS_FULL_SOURCE_MEMORY_NO_TRAINING', 'SOURCE_FINAL_STATUS_NOT_PASS')
    require(proof.get('schema') == 'paper04-learned-memory-source-validation-v4'
            and proof.get('status') == 'PASS_FULL_SOURCE_MEMORY_NO_TRAINING'
            and proof.get('full_workload_complete') is True, 'SOURCE_PROOF_INCOMPLETE')
    require(proof.get('production_optimizer_updates') == 0
            and proof.get('target_queries_read') == 0
            and proof.get('original_experiment_resumed') is False, 'SOURCE_SCOPE_VIOLATION')
    require(type(proof.get('peak_process_tree_rss')) is int
            and 0 < proof['peak_process_tree_rss'] < RSS_LIMIT, 'SOURCE_PEAK_RSS_INVALID')
    require(proof.get('source_code_sha256') == source_code and bool(source_code), 'VALIDATED_CODE_DRIFT')
    require(proof.get('fit_rows') == 617908 and proof.get('tasks', 0) > 0, 'SOURCE_FULL_SCALE_MISSING')


def verify_preflight(returncode, plan, proof, proof_sha256):
    require(returncode == 0, 'PREFLIGHT_NONZERO_EXIT')
    require(plan.get('status') == 'READY' and plan.get('synthetic_timing_complete') is True,
            'PREFLIGHT_NOT_READY')
    full = plan.get('full_scale_memory_validation') or {}
    require(full.get('status') == 'VERIFIED' and full.get('receipt_sha256') == proof_sha256
            and full.get('measured_peak_rss') == proof['peak_process_tree_rss'],
            'PREFLIGHT_FULL_SCALE_PROOF_MISMATCH')
    require(type(plan.get('estimated_peak_rss')) is int
            and 0 < plan['estimated_peak_rss'] <= RSS_LIMIT, 'PREFLIGHT_ESTIMATED_PEAK_INVALID')
    require(plan.get('rss_guard_bytes') == RSS_LIMIT and plan.get('cpu_threads') == 4
            and plan.get('heavy_workers') == 1, 'PREFLIGHT_RESOURCE_CONTRACT_CHANGED')


# Reuse these exact predicates remotely and in the no-network synthetic tests.
CODE = ('RSS_LIMIT = 8*1024**3\n' + inspect.getsource(require) + '\n'
        + inspect.getsource(verify_source_final) + '\n' + inspect.getsource(verify_preflight) + '\n') + r'''
import base64,hashlib,json,pathlib,subprocess,time,traceback
here=pathlib.Path('/srv/paper04/learned_onboarding_memory_validation_20261024_v4')
root=here/'staging';package=root/'runs/learned_onboarding_v1_20261023'
receipt=here/'PREFLIGHT_ACCEPTANCE.json'
require(not receipt.exists(),'ACCEPTANCE_ALREADY_ATTEMPTED_NO_RETRY')
source_unit='paper04-onboarding-memory-validation-20261024-v4'
preflight_unit='paper04-onboarding-memory-preflight-20261024-v4'
result=dict(status='ACCEPTANCE_FAILED',production_optimizer_updates=0,target_queries_read=0,
    original_experiment_restarted=False,automatic_retry=False)
started_preflight=False

def unit_state(name,allow_missing=False):
    query=subprocess.run(['systemctl','show',name,'--property=LoadState,ActiveState,SubState,Result,MainPID,ExecMainStatus'],capture_output=True,text=True,timeout=5)
    state=dict(line.split('=',1) for line in query.stdout.splitlines() if '=' in line)
    require(query.returncode==0 or (allow_missing and state.get('LoadState')=='not-found'),
            'UNIT_STATE_QUERY_FAILED:'+name+':'+query.stderr[-2000:])
    return state

def stop_owned_preflight():
    # Only this one-shot acceptance unit belongs to this script.
    cleanup={}
    try:
        stopped=subprocess.run(['systemctl','stop',preflight_unit],capture_output=True,text=True,timeout=20)
        cleanup=dict(returncode=stopped.returncode,stderr=stopped.stderr[-2000:],unit=unit_state(preflight_unit,allow_missing=True))
    except BaseException as error:
        cleanup=dict(error_type=type(error).__name__,error=str(error))
    cleanup['runtime_max_seconds']=600
    return cleanup

try:
    # SOURCE_VALIDATION is published before the final status/process exit. Wait
    # for the independent diagnostic to finish; never stop or restart it here.
    deadline=time.monotonic()+120
    while True:
        source_state=unit_state(source_unit)
        if source_state.get('ActiveState') not in ('active','activating','deactivating'):
            break
        require(time.monotonic()<deadline,'SOURCE_FINAL_EXIT_WAIT_TIMEOUT')
        time.sleep(2)
    result['source_unit']=source_state
    folder=here/'source_validation'
    exceptions=[name for name in ('RESOURCE_EXCEPTION.json','VALIDATION_EXCEPTION.json') if (folder/name).exists()]
    proof_bytes=(folder/'SOURCE_VALIDATION.json').read_bytes()
    proof=json.loads(proof_bytes)
    final_status=json.loads((folder/'status.json').read_text())
    actual_code={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (package/'src').glob('*.py')}
    verify_source_final(source_state,final_status,exceptions,proof,actual_code)
    result['source_final_status']=final_status
    result['source_exception_artifacts']=exceptions
    proof_sha=hashlib.sha256(proof_bytes).hexdigest()
    target=root/'MEMORY_RESOURCE_VALIDATION.json'
    out=package/'validation/memory_preflight_acceptance'
    require(not target.exists(),'MEMORY_PROOF_ALREADY_INSTALLED_NO_RETRY')
    require(not out.exists(),'PREFLIGHT_ALREADY_ATTEMPTED')
    require(unit_state(preflight_unit,allow_missing=True).get('LoadState')=='not-found','PREFLIGHT_UNIT_ALREADY_EXISTS_NO_RETRY')
    with target.open('xb') as stream:stream.write(proof_bytes)
    command=['/opt/paper04-venv/bin/python','-B',str(package/'src/service.py'),'preflight','--config',str(package/'deployment_20261024/remote_config.json'),'--source-assets','/srv/paper04/learned_onboarding_20261024_v3/runs/learned_onboarding_v1_20261023/results/source_assets','--output',str(out),'--execution-slot','exclusive-existing-remote']
    command=['systemd-run','--wait','--collect','--pipe','--unit='+preflight_unit,'--property=Type=exec','--property=Restart=no','--property=RuntimeMaxSec=600','--property=TimeoutStopSec=15','--property=KillMode=control-group','--property=MemoryMax=16G','--property=MemorySwapMax=0','--property=CPUQuota=800%','--property=WorkingDirectory='+str(root)]+['--setenv='+key+'=4' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['--setenv=PYTHONDONTWRITEBYTECODE=1']+command
    result['command']=command
    with (here/'preflight_acceptance.log').open('xb') as stream:
        started_preflight=True
        completed=subprocess.run(command,cwd=root,stdout=stream,stderr=subprocess.STDOUT,timeout=650)
    result['returncode']=completed.returncode
    plan_path=out/'resource_plan.json'
    plan=json.loads(plan_path.read_text()) if plan_path.is_file() else {}
    result['resource_plan']=plan
    verify_preflight(completed.returncode,plan,proof,proof_sha)
    result.update(status='PASS_ACTUAL_PREFLIGHT',source_proof_sha256=proof_sha,
        source_proof_bytes_base64=base64.b64encode(proof_bytes).decode('ascii'))
except BaseException as error:
    result.update(status='ACCEPTANCE_FAILED',error_type=type(error).__name__,error=str(error),
        traceback=traceback.format_exc())
    if started_preflight:result['cleanup']=stop_owned_preflight()
finally:
    log=here/'preflight_acceptance.log'
    if log.is_file():result['log_tail']=log.read_text(errors='replace')[-6000:]
    with receipt.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(result))
'''


def main():
    folder = run.HERE/'remote_validation'
    receipt = folder/'PREFLIGHT_ACCEPTANCE.json'
    target = run.HERE/'staging/MEMORY_RESOURCE_VALIDATION.json'
    require(folder.is_dir(), 'COLLECTED_SOURCE_EVIDENCE_REQUIRED')
    require(not receipt.exists() and not target.exists(), 'LOCAL_ACCEPTANCE_ALREADY_ATTEMPTED_NO_RETRY')
    try:
        result = run.ssh(CODE, timeout=850)
        require(result.get('status') == 'PASS_ACTUAL_PREFLIGHT',
                'REMOTE_ACCEPTANCE_FAILED:'+str(result.get('error')))
        proof_bytes = base64.b64decode(result['source_proof_bytes_base64'], validate=True)
        proof = json.loads(proof_bytes)
        proof_sha = hashlib.sha256(proof_bytes).hexdigest()
        require(proof_sha == result['source_proof_sha256'], 'ACCEPTED_PROOF_TRANSPORT_HASH')
        local_code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (run.HERE/'staging/runs/learned_onboarding_v1_20261023/src').glob('*.py')}
        verify_source_final(result['source_unit'], result['source_final_status'],
                            result['source_exception_artifacts'], proof, local_code)
        verify_preflight(result['returncode'], result['resource_plan'], proof, proof_sha)
        collected = json.loads((folder/'SOURCE_VALIDATION.json').read_text())
        require(collected == proof, 'COLLECTED_REMOTE_SOURCE_PROOF_MISMATCH')
        with target.open('xb') as stream:
            stream.write(proof_bytes)
        result['local_proof_installed'] = True
    except BaseException as error:
        remote = locals().get('result')
        result = dict(status='ACCEPTANCE_FAILED', error_type=type(error).__name__, error=str(error),
                      automatic_retry=False, local_proof_installed=False,
                      original_experiment_restarted=False, remote_result=remote)
    with receipt.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(status=result['status'],
        local_proof_installed=result.get('local_proof_installed', False),
        error=result.get('error'),
        estimated_peak_rss=result.get('resource_plan', {}).get('estimated_peak_rss'))))
    return 0 if result['status'] == 'PASS_ACTUAL_PREFLIGHT' else 1


class SyntheticAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.unit = dict(ActiveState='inactive', MainPID='0', Result='success', ExecMainStatus='0')
        self.status = dict(status='PASS_FULL_SOURCE_MEMORY_NO_TRAINING')
        self.code = {'service.py': 'a'*64}
        self.proof = dict(schema='paper04-learned-memory-source-validation-v4',
            status=self.status['status'], full_workload_complete=True,
            production_optimizer_updates=0, target_queries_read=0,
            original_experiment_resumed=False, peak_process_tree_rss=3*1024**3,
            source_code_sha256=self.code, fit_rows=617908, tasks=1000000)
        self.plan = dict(status='READY', synthetic_timing_complete=True,
            full_scale_memory_validation=dict(status='VERIFIED', receipt_sha256='b'*64,
                measured_peak_rss=self.proof['peak_process_tree_rss']),
            estimated_peak_rss=6*1024**3, rss_guard_bytes=RSS_LIMIT, cpu_threads=4, heavy_workers=1)

    def test_valid_source_and_preflight(self):
        verify_source_final(self.unit, self.status, [], self.proof, self.code)
        verify_preflight(0, self.plan, self.proof, 'b'*64)

    def test_pass_artifact_cannot_override_active_or_failed_unit(self):
        for change in (dict(ActiveState='active', MainPID='12'), dict(Result='exit-code'), dict(ExecMainStatus='73')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_source_final(dict(self.unit, **change), self.status, [], self.proof, self.code)

    def test_any_exception_artifact_rejects_pass(self):
        for name in ('RESOURCE_EXCEPTION.json', 'VALIDATION_EXCEPTION.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify_source_final(self.unit, self.status, [name], self.proof, self.code)

    def test_scope_partial_source_and_code_drift_are_rejected(self):
        for change in (dict(target_queries_read=1), dict(production_optimizer_updates=1),
                       dict(full_workload_complete=False), dict(fit_rows=3),
                       dict(source_code_sha256={'old.py': 'a'*64}), dict(peak_process_tree_rss=RSS_LIMIT)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_source_final(self.unit, self.status, [], dict(self.proof, **change), self.code)

    def test_preflight_failure_is_not_accepted(self):
        for returncode, change in ((1, {}), (0, dict(status='RESOURCE_NOT_READY')),
                (0, dict(estimated_peak_rss=RSS_LIMIT+1)), (0, dict(synthetic_timing_complete=False)),
                (0, dict(full_scale_memory_validation=dict(status='UNVERIFIED')))):
            with self.subTest(returncode=returncode, change=change), self.assertRaises(ValueError):
                verify_preflight(returncode, dict(self.plan, **change), self.proof, 'b'*64)

    def test_remote_code_compiles_and_service_has_finite_lifetime(self):
        compile(CODE, '<accept-memory-validation-remote>', 'exec')
        self.assertIn('--property=RuntimeMaxSec=600', CODE)
        self.assertIn('--property=KillMode=control-group', CODE)
        self.assertIn('stop_owned_preflight()', CODE)

    def test_missing_unit_nonzero_query_is_only_allowed_for_missing_preflight(self):
        function = next(node for node in ast.parse(CODE).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'unit_state')
        answer = SimpleNamespace(returncode=1, stdout='LoadState=not-found\n', stderr='unit missing')
        namespace = dict(require=require, subprocess=SimpleNamespace(run=lambda *a, **kw: answer))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<unit-state-fixture>', 'exec'), namespace)
        state = namespace['unit_state']
        self.assertEqual(state('candidate-preflight', allow_missing=True)['LoadState'], 'not-found')
        with self.assertRaises(ValueError):
            state('diagnostic-source')
        answer.stdout = 'LoadState=loaded\n'
        with self.assertRaises(ValueError):
            state('candidate-preflight', allow_missing=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        unittest.main(argv=[sys.argv[0]])
    else:
        require(not sys.argv[1:], 'UNEXPECTED_ARGUMENTS')
        raise SystemExit(main())
