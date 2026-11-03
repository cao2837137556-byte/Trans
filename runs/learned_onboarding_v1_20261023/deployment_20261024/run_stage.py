"""One explicit child stage; the parent provides resource and process guards."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time
import traceback
import unittest


PACKAGE = 'runs/learned_onboarding_v1_20261023'


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--source-assets', type=Path, required=True)
    parser.add_argument('--stage', required=True, choices=(
        'tests', 'prepare', 'validate', 'preflight', 'fit', 'calibration', 'target', 'evaluation'))
    parser.add_argument('--expected-runtime-file', type=Path)
    parser.add_argument('--target-manifest', type=Path)
    parser.add_argument('--target-manifest-sha256')
    args = parser.parse_args(argv)
    stage_state = args.state / 'stages' / args.stage
    stage_state.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        root = args.root.resolve()
        package = root / PACKAGE
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            os.environ[name] = '4'
        sys.path.insert(0, str(root / 'repo/ood'))
        sys.path.insert(0, str(package / 'src'))
        # service sets thread environment before importing numerical libraries.
        import service
        import learning
        import common
        learning._setup()
        common.check_spec()
        runtime = common.environment()
        atomic_json(stage_state / 'runtime.json', dict(
            schema='learned-onboarding-deployment-runtime-v1', stage=args.stage,
            runtime=runtime, executable=sys.executable))
        if args.expected_runtime_file is not None:
            previous = json.loads(args.expected_runtime_file.read_text(encoding='utf-8'))
            common.require(previous['runtime'] == runtime, 'DEPLOYMENT_RUNTIME_CHANGED')
        if args.stage == 'tests':
            (package / 'validation').mkdir(exist_ok=True)
            suite = unittest.defaultTestLoader.discover(str(package / 'tests'))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            atomic_json(stage_state / 'tests.json', dict(
                schema='learned-onboarding-deployment-tests-v1',
                status='PASS' if result.wasSuccessful() and result.testsRun > 0 else 'FAIL',
                tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                unexpected_successes=len(result.unexpectedSuccesses),
                elapsed_seconds=time.monotonic() - started))
            if not result.wasSuccessful() or result.testsRun == 0:
                return 1
            # Keep the new adapter fixture separate from the frozen unittest count.
            adapter = package / 'deployment_20261024/target_manifest_adapter.py'
            fixture_started = time.monotonic()
            fixture_log = stage_state / 'adapter_self_test.log'
            try:
                common.require(adapter.is_file(), 'TARGET_ADAPTER_NOT_READY_FOR_SELF_TEST')
                with fixture_log.open('x', encoding='utf-8', newline='\n') as stream:
                    with contextlib.redirect_stdout(stream):
                        namespace = runpy.run_path(str(adapter), run_name='onboarding_adapter_self_test')
                        fixture_exit = namespace['main'](['--self-test'])
                report = json.loads(fixture_log.read_text(encoding='utf-8').strip().splitlines()[-1])
                common.require(fixture_exit in (None, 0) and report['status'] == 'PASS' and
                               isinstance(report['tests'], list) and len(report['tests']) > 0 and
                               report['real_target_queries_read'] == 0, 'TARGET_ADAPTER_SELF_TEST_FAILED')
                atomic_json(stage_state / 'adapter_validation.json', dict(
                    schema='learned-onboarding-target-adapter-validation-v1', status='PASS',
                    adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest(),
                    tests_run=len(report['tests']), tests=report['tests'],
                    real_target_queries_read=report['real_target_queries_read'],
                    elapsed_seconds=time.monotonic() - fixture_started,
                    unittest_count_is_separate=True))
            except BaseException as error:
                atomic_json(stage_state / 'adapter_validation.json', dict(
                    schema='learned-onboarding-target-adapter-validation-v1', status='FAIL',
                    error_type=type(error).__name__, error=str(error),
                    traceback=traceback.format_exc(), unittest_count_is_separate=True,
                    elapsed_seconds=time.monotonic() - fixture_started))
                raise
            return 0
        results = package / 'results'
        if args.stage == 'target':
            adapter = package / 'deployment_20261024/target_manifest_adapter.py'
            common.require(adapter.is_file(), 'TARGET_ADAPTER_NOT_READY')
            sys.argv = [str(adapter), '--deployment-root', str(root),
                        '--fit-dir', str(results / 'fit'), '--cal-dir', str(results / 'calibration'),
                        '--output', str(root / 'inputs/target_bundle')]
            runpy.run_path(str(adapter), run_name='__main__')
            return 0
        service_stage = {'validate': 'validate-source', 'calibration': 'calibrate',
                         'evaluation': 'evaluate'}.get(args.stage, args.stage)
        command = [service_stage, '--config', str(args.config),
                   '--source-assets', str(args.source_assets),
                   '--output', str(results / args.stage)]
        if args.stage in ('preflight', 'fit', 'calibration', 'evaluation'):
            command += ['--execution-slot', 'exclusive-existing-remote']
        if args.stage in ('fit', 'calibration', 'evaluation'):
            command += ['--preflight-receipt', str(results / 'preflight/resource_plan.json')]
        if args.stage in ('calibration', 'evaluation'):
            command += ['--fit-dir', str(results / 'fit')]
        if args.stage == 'evaluation':
            common.require(args.target_manifest is not None and args.target_manifest_sha256,
                           'TARGET_MANIFEST_REQUIRED')
            command += ['--calibration-dir', str(results / 'calibration'),
                        '--target-manifest', str(args.target_manifest),
                        '--target-manifest-sha256', args.target_manifest_sha256]
        return service.main(command)
    except SystemExit as error:
        if error.code in (None, 0):
            return 0
        atomic_json(stage_state / 'child_exception.json', dict(
            status='EXCEPTION_STOP', stage=args.stage, error=str(error),
            traceback=traceback.format_exc(), automatic_retry=False))
        return int(error.code) if isinstance(error.code, int) else 1
    except BaseException as error:
        atomic_json(stage_state / 'child_exception.json', dict(
            status='EXCEPTION_STOP', stage=args.stage, error_type=type(error).__name__,
            error=str(error), traceback=traceback.format_exc(), automatic_retry=False))
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
