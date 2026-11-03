"""Run bounded implementation checks; never starts a real fit or target replay."""
import ast
import contextlib
from datetime import datetime, timezone
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE/'src'))
import common as c
import pipeline


def main():
    receipt_path = HERE/'validation/engineering_validation.json'
    log_path = HERE/'validation/test_output.txt'
    c.require(not receipt_path.exists() and not log_path.exists(), 'VALIDATION_OUTPUT_EXISTS')
    c.check_spec()
    old = c.ROOT/'runs/learned_onboarding_pilot_v1_20261023'
    preparation = c.read(old/'PREPARATION_RECEIPT.json')
    preserved = {}
    for name, item in preparation['artifacts'].items():
        c.pin(old/name, item['sha256'])
        preserved[name] = dict(sha256=item['sha256'], unchanged=True)
    source_path = HERE/'validation/source_adapter_receipt.json'
    source = c.read(source_path)
    c.require(source['adapter_sha256'] == c.sha(HERE/'src/source_inputs.py'),
              'SOURCE_VALIDATION_CODE_CHANGED')
    readiness = HERE/'validation/source_readiness_v1'
    c.verify_seal(readiness)
    coverage = c.read(readiness/'source_task_receipt.json')
    isolation = c.read(readiness/'isolation.json')
    c.require(coverage['status'] == isolation['status'] == 'READY', 'SOURCE_READINESS_NOT_READY')
    syntax_files = sorted(list((HERE/'src').glob('*.py'))+list((HERE/'tests').glob('*.py')))
    for path in syntax_files:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path), feature_version=(3, 9))
    started = time.perf_counter()
    with log_path.open('x', encoding='utf-8', newline='\n') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            suite = unittest.defaultTestLoader.discover(str(HERE/'tests'), pattern='test_*.py')
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    test_result = dict(tests_run=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), successful=result.wasSuccessful(),
        failure_ids=[str(test) for test, _ in result.failures],
        error_ids=[str(test) for test, _ in result.errors], elapsed_seconds=time.perf_counter()-started,
        log_sha256=c.sha(log_path), command='python -m unittest discover -s '+str(HERE/'tests')+' -v')
    qualified = {(label, reason): sum(g['rows'] for g in coverage['groups']
        if g['label'] == label and g['reason'] == reason) for label in (0, 1)
        for reason in ('ELIGIBLE', 'FEWER_THAN_TWO_LEGAL_COMPONENTS')}
    receipt = c.record('learned-onboarding-engineering-validation-v1',
        status='PASS' if result.wasSuccessful() else 'FAIL',
        created_at=datetime.now(timezone.utc).isoformat(), tests=test_result,
        runtime=c.environment(), code_sha256=pipeline.implementation_hashes(),
        python39_syntax=dict(status='PASS', files=len(syntax_files),
            runtime_execution='Python 3.10 only; this grammar check is not Python 3.9 runtime acceptance'),
        frozen_preparation_files=preserved,
        source_adapter_receipt_sha256=c.sha(source_path),
        source_readiness_seal_sha256=c.sha(readiness/'SEAL.json'),
        source_frame_qualification=dict(fit_rows=coverage['fit_rows'],
            normal_devices=coverage['normal_devices'], attack_own_bank_devices=coverage['attack_own_bank_devices'],
            eligible_normal_rows=qualified[(0, 'ELIGIBLE')], eligible_attack_rows=qualified[(1, 'ELIGIBLE')],
            fallback_normal_rows=qualified[(0, 'FEWER_THAN_TWO_LEGAL_COMPONENTS')],
            fallback_attack_rows=qualified[(1, 'FEWER_THAN_TWO_LEGAL_COMPONENTS')],
            independent_new_group_capture_overlap=len(isolation['new_group_capture_overlap']),
            numerical_and_frame_checks=True),
        real_model_optimizer_updates=0, real_target_queries_read=0,
        remote_operations=0, running_jobs_modified=False, ai_polling_added=False,
        synthetic_endpoint_note='Short optimizer fixtures only. COMPLETE-chain fixture mocks residual_signal READY; real signal is unknown.',
        unrun=['production auxiliary/module training', 'synthetic timing resource preflight',
            'true auxiliary residual-signal gate', 'CAL attack lambda protection',
            'production target manifest assembly and evaluation', 'remote runtime acceptance'])
    c.write(receipt_path, receipt)
    print('tests=%d failures=%d errors=%d status=%s' %
          (result.testsRun, len(result.failures), len(result.errors), receipt['status']))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
