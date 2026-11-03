"""Run one explicitly approved A/B evaluation stage; never encode or train.

Package and scope authorization precede target-asset assembly. Completed source
CAL and encodings are consumed by immutable pins. All failures preserve evidence
and terminate; there is no resume, requeue, retry, or parameter selection here.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import sys
import time

import numpy as np
import psutil

import matrix
from common import assemble_view, read, require, sha, verify_package, write
from supervisor import run_stage


GIB = 1024**3
MAX_WALL_SECONDS = 7200
EXPECTED_NUMPY_ROOT = Path('/public/home/jiangxinwei.zr/work/paper04/runs/'
    'dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201')


def validate_stage_approval(manifest, manifest_sha, source_sha, approval, package_sha):
    matrix.check_authorization(manifest, manifest_sha, source_sha, approval, False)
    require(approval.get('package_sha256') == package_sha, 'AB_STAGE_PACKAGE_APPROVAL_REQUIRED')
    require(type(approval.get('total_wall_seconds')) is int and
            0 < approval['total_wall_seconds'] <= MAX_WALL_SECONDS, 'AB_STAGE_TOTAL_WALL_BUDGET')
    require(type(approval.get('retries')) is int and approval['retries'] == 0,
            'AB_STAGE_ZERO_RETRIES_REQUIRED')


def validate_numpy_runtime():
    actual = Path(np.__file__).resolve()
    require(np.__version__ == '2.0.1' and actual.is_relative_to(EXPECTED_NUMPY_ROOT.resolve()),
            'EXACT_NUMPY201_VERIFIED_OVERLAY_REQUIRED')
    return dict(version=np.__version__, module_path=actual.as_posix(),
                expected_overlay=EXPECTED_NUMPY_ROOT.as_posix())


def stage_limits(total_wall_seconds, elapsed_seconds):
    require(type(total_wall_seconds) is int and 0 < total_wall_seconds <= MAX_WALL_SECONDS,
            'AB_STAGE_TOTAL_WALL_BUDGET')
    remaining = total_wall_seconds - elapsed_seconds
    require(remaining > 0, 'AB_STAGE_TOTAL_WALL_LIMIT')
    return dict(wall_seconds=remaining, rss_bytes=8*GIB, output_bytes=2*GIB,
                min_free_bytes=12*GIB, poll_seconds=2)


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument('--package', required=True)
    value.add_argument('--assets-root', required=True)
    value.add_argument('--manifest', required=True)
    value.add_argument('--source-cal-result', required=True)
    value.add_argument('--approval-file', required=True)
    value.add_argument('--output', required=True)
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    package = Path(args.package).resolve()
    output = Path(args.output).resolve()
    manifest_path = Path(args.manifest).resolve()
    source_path = Path(args.source_cal_result).resolve()
    require(package.is_dir(), 'PACKAGE_DIRECTORY_REQUIRED')
    require(manifest_path.is_relative_to(package), 'SEALED_PACKAGE_MANIFEST_REQUIRED')
    require(not output.exists() and not output.is_relative_to(package) and
            not package.is_relative_to(output), 'FRESH_EXTERNAL_OUTPUT_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    status = dict(schema='paper04-dense-ab-stage-progress-v1', status='RUNNING', stage='preflight',
        evaluation_scope=matrix.STAGE_SCOPE, original_registered_matrix_complete=False,
        third_pool_deferred=matrix.THIRD_POOL, scientific_status='NOT_EVALUATED',
        started_utc=datetime.now(timezone.utc).isoformat(), retries=0,
        automatic_retry=False, scientific_fail_continues=True,
        stages=[dict(name='matrix', state='PENDING')])

    def emit(**changes):
        status.update(changes, updated_utc=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=time.monotonic()-started)
        write(output/'status.json', status)

    try:
        emit(stage='package_identity')
        package_sha = verify_package(package)
        manifest, approval = read(manifest_path), read(args.approval_file)
        require(manifest.get('schema') == matrix.SCHEMA, 'AB_STAGE_INPUT_SCHEMA')
        manifest_sha, source_sha = sha(manifest_path), sha(source_path)
        # This gate runs before any target dataset/score or target-asset view.
        validate_stage_approval(manifest, manifest_sha, source_sha, approval, package_sha)
        require(manifest.get('stage_matrix_ready') is True and
                manifest.get('supplement_encoding_complete') is True and
                manifest.get('dense_source_cal_complete') is True, 'AB_STAGE_MATERIALIZATION_REQUIRED')
        derived = matrix.Inputs(args.assets_root, manifest.get('derived_runtime_roots', ()))
        require(derived.pin(manifest['source_cal_result']) == source_path,
                'SOURCE_RESULT_MANIFEST_BINDING')
        runtime = validate_numpy_runtime()
        emit(stage='authorized_input_preflight', package_sha256=package_sha,
             manifest_sha256=manifest_sha, numpy_runtime=runtime)
        require(psutil.disk_usage(str(output)).free >= 12*GIB, 'FREE_SPACE_LIMIT')
        runtime_assets = read(package/'config/RUNTIME_ASSET_MANIFEST.json')
        view = output/'readonly_view'
        receipt = assemble_view(runtime_assets, args.assets_root, package/'assets', view)
        write(output/'ASSET_VIEW_RECEIPT.json', receipt)
        write(output/'RUNTIME_IDENTITY.json', runtime)
        env = dict(os.environ)
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            env[name] = '4'
        env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUDA_VISIBLE_DEVICES='')
        env['PYTHONPATH'] = os.pathsep.join((str(EXPECTED_NUMPY_ROOT), str(package/'src'),
            str(package/'vendor/encoding_v2/repo/ood'), env.get('PYTHONPATH', '')))
        status['stages'][0]['state'] = 'RUNNING'
        emit(stage='matrix')
        command = [sys.executable, '-B', '-u', str(package/'src/matrix.py'),
            '--root', str(view), '--manifest', str(manifest_path),
            '--source-cal-result', str(source_path), '--authorization', str(Path(args.approval_file).resolve()),
            '--output', str(output/'matrix')]
        limits = stage_limits(approval['total_wall_seconds'], time.monotonic()-started)
        supervised = run_stage(command, output=output/'matrix', control=output/'control/matrix',
            limits=limits, env=env, stop_file=output/'STOP_REQUESTED',
            expected=('AB_STAGE_COMPLETE_THIRD_POOL_PENDING',),
            notify=lambda worker: emit(stage='matrix', worker=worker))
        result = read(output/'matrix/RESULT.json')
        derived.immutable()
        require(sha(manifest_path) == manifest_sha and sha(source_path) == source_sha,
                'APPROVED_INPUT_IDENTITY_CHANGED')
        status['stages'][0].update(state='COMPLETE', elapsed_seconds=supervised['elapsed_seconds'])
        final = dict(status='COMPLETE', evaluation_scope=matrix.STAGE_SCOPE,
            matrix_result_status=result['status'], scientific_status=result['scientific_status'],
            stage_scientific_status=result['stage_scientific_status'],
            original_registered_matrix_complete=False,
            original_registered_matrix_scientific_status='NOT_EVALUATED_MISSING_THIRD_POOL',
            third_pool_deferred=manifest['third_pool_deferred'], package_sha256=package_sha,
            manifest_sha256=manifest_sha, source_cal_result_sha256=source_sha,
            model_forward_calls=0, training_updates=0, new_encoding_rows=0,
            new_source_cal_runs=0, retries=0, automatic_retry=False,
            total_wall_seconds=approval['total_wall_seconds'], matrix_result_sha256=sha(output/'matrix/RESULT.json'))
        write(output/'RESULT.json', final)
        emit(status='COMPLETE', stage='AB_STAGE_TERMINAL', terminal=True, worker_alive=False,
             scientific_status=result['scientific_status'], stage_scientific_status=result['stage_scientific_status'])
        return 0
    except BaseException as exc:
        for item in status['stages']:
            if item['state'] == 'RUNNING':
                item['state'] = 'EXCEPTION_STOP'
        emit(status='EXCEPTION_STOP', terminal=True, worker_alive=False,
             error_type=type(exc).__name__, reason=str(exc), evidence_preserved=True)
        return 70


if __name__ == '__main__':
    def terminate(signum, frame):
        raise RuntimeError('TERMINATION_SIGNAL:' + str(signum))
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    sys.exit(main())
