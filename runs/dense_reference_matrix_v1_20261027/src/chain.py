"""Approved HPC stages, in order; no job submission and no automatic retry."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import sys
import time

from common import assemble_view, read, require, sha, validate_approval, verify_package, write
from supervisor import run_stage

STAGES = ('runtime', 'encode', 'source_cal', 'matrix')
GIB = 1024**3
LIMITS = {
    'runtime': dict(wall_seconds=480, output_bytes=256*1024**2),
    'encode': dict(wall_seconds=36000, output_bytes=4*GIB),
    'source_cal': dict(wall_seconds=7200, output_bytes=128*1024**2),
    'matrix': dict(wall_seconds=7200, output_bytes=2*GIB),
}


def validate_stages(stages):
    require(tuple(stages) == STAGES[:len(stages)] and bool(stages), 'ORDERED_STAGE_PREFIX_REQUIRED')


def stage_limits(stage, total_wall_seconds, elapsed_seconds):
    require(type(total_wall_seconds) is int and 0 < total_wall_seconds <= 43200,
            'AUTHORIZED_TOTAL_WALL_BUDGET')
    remaining = total_wall_seconds - elapsed_seconds
    require(remaining > 0, 'TOTAL_WALL_LIMIT')
    return dict(LIMITS[stage], wall_seconds=min(LIMITS[stage]['wall_seconds'], remaining),
                rss_bytes=8*GIB, min_free_bytes=12*GIB, poll_seconds=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--assets-root', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--approval-file', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--stages', nargs='+', choices=STAGES, default=list(STAGES))
    args = parser.parse_args(argv)
    package, output = Path(args.package).resolve(), Path(args.output).resolve()
    require(not output.exists() and not output.is_relative_to(package)
            and not package.is_relative_to(output), 'FRESH_EXTERNAL_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    started = time.monotonic()
    record = dict(schema='paper04-dense-chain-progress-v1', status='RUNNING',
        stages=[dict(name=s, state='PENDING') for s in args.stages],
        evaluation_scope='FULL_MATRIX' if 'matrix' in args.stages else 'AUTHORIZED_STAGE_PREFIX_ONLY',
        started_utc=datetime.now(timezone.utc).isoformat(), retries=0,
        automatic_retry=False, scientific_fail_continues=True)
    def emit(**changes):
        record.update(changes, updated_utc=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=time.monotonic() - started)
        write(output / 'status.json', record)
    try:
        emit(stage='preflight')
        validate_stages(args.stages)
        package_sha = verify_package(package)
        approval = read(args.approval_file)
        validate_approval(approval, package_sha, args.stages)
        require(type(approval.get('total_wall_seconds')) is int and
                0 < approval['total_wall_seconds'] <= 43200, 'AUTHORIZED_TOTAL_WALL_BUDGET')
        # Bound the scientific snapshot before loading target scores or starting E3.
        config = read(package / 'config/chain.json')
        if 'matrix' in args.stages:
            require(not config.get('matrix_execution_blockers'),
                    'MATRIX_PREFLIGHT_BLOCKED:' + repr(config['matrix_execution_blockers']))
        require(sha(args.checkpoint) == config['checkpoint_sha256'], 'CHECKPOINT_SHA')
        sources = read(package / ('config/ASSET_MANIFEST.json' if 'matrix' in args.stages
                                  else 'config/SOURCE_ASSET_MANIFEST.json'))
        view_receipt = assemble_view(sources, args.assets_root, package / 'assets', output / 'readonly_view')
        write(output / 'ASSET_VIEW_RECEIPT.json', view_receipt)
        old = package / 'vendor/encoding_v2'
        encoder_sha = sha(old / 'SHA256SUMS')
        # The frozen encoder accepts either delegated scope and does not check
        # an encode=False flag. A runtime-only run must mint no encoder token.
        if 'encode' in args.stages:
            delegated = dict(user_authorized=True,
                scope='R2_SUPPLEMENT_AND_SOURCE_CAL' if 'source_cal' in args.stages else 'SUPPLEMENT_E3_ONLY',
                package_sha256=encoder_sha, dense_source_cal='source_cal' in args.stages, encode=True,
                source_plan_sha256=sha(old / 'data/SOURCE_REFS/DENSE_PLAN.json'),
                outer_package_sha256=package_sha, outer_approval_sha256=sha(args.approval_file),
                evidence=approval.get('evidence'), matrix=False)
            write(output / 'ENCODER_CAL_APPROVAL.json', delegated)
        env = dict(os.environ)
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            env[name] = '4'
        env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUDA_VISIBLE_DEVICES='')
        inherited = env.get('PYTHONPATH', '')
        env['PYTHONPATH'] = os.pathsep.join([str(package / 'src'), str(old / 'repo/ood'), inherited])
        emit(stage='preflight', package_sha256=package_sha, asset_view='PASS')
        for item in record['stages']:
            stage = item['name']
            item['state'] = 'RUNNING'
            emit(stage=stage)
            stage_output = output / stage
            if stage == 'runtime':
                command = [sys.executable, '-B', str(package / 'src/prepare_runtime.py'),
                           '--package', str(package), '--output', str(stage_output)]
                expected = ('COMPLETE',)
            elif stage == 'encode':
                command = [sys.executable, '-B', '-u', str(old / 'repo/ood/onboarding_supplement_encoder_r2.py'),
                    '--package', str(old), '--checkpoint', str(Path(args.checkpoint).resolve()),
                    '--output', str(stage_output), '--mode', 'encode',
                    '--approval-file', str(output / 'ENCODER_CAL_APPROVAL.json')]
                expected = ('COMPLETE',)
            elif stage == 'source_cal':
                command = [sys.executable, '-B', '-u', str(package / 'src/source_cal.py'),
                    '--root', str(output / 'readonly_view'),
                    '--dense-bank', str(output / 'encode/banks/SOURCE_REFS'),
                    '--encoding-result', str(output / 'encode/RESULT.json'),
                    '--source-plan', str(old / 'data/SOURCE_REFS/DENSE_PLAN.json'),
                    '--approval-file', str(output / 'ENCODER_CAL_APPROVAL.json'),
                    '--output', str(stage_output)]
                expected = ('SOURCE_CAL_COMPLETE',)
            else:
                from materialize import materialize_runtime
                runtime_manifest = output / 'MATRIX_RUNTIME_MANIFEST.json'
                materialize_runtime(package / config['matrix_template'], output / 'encode',
                                    output / 'source_cal', runtime_manifest,
                                    asset_root=output / 'readonly_view')
                matrix_approval = dict(schema='dense-reference-matrix-authorization-v1',
                    status='AUTHORIZED', scope='REGISTERED_DENSE_MATRIX',
                    manifest_sha256=sha(runtime_manifest),
                    source_cal_result_sha256=sha(output / 'source_cal/RESULT.json'),
                    allow_target_evaluation=True, evidence=approval.get('evidence'),
                    outer_package_sha256=package_sha, outer_approval_sha256=sha(args.approval_file))
                write(output / 'MATRIX_APPROVAL.json', matrix_approval)
                command = [sys.executable, '-B', '-u', str(package / 'src/matrix.py'),
                    '--root', str(output / 'readonly_view'), '--manifest', str(runtime_manifest),
                    '--source-cal-result', str(output / 'source_cal/RESULT.json'),
                    '--authorization', str(output / 'MATRIX_APPROVAL.json'), '--output', str(stage_output)]
                expected = ('COMPLETE',)
            def heartbeat(stage_record):
                emit(stage=stage, worker=stage_record)
            limits = stage_limits(stage, approval['total_wall_seconds'], time.monotonic() - started)
            result = run_stage(command, output=stage_output, control=output / 'control' / stage,
                limits=limits, env=env, stop_file=output / 'STOP_REQUESTED',
                expected=expected, notify=heartbeat)
            item.update(state='COMPLETE', elapsed_seconds=result['elapsed_seconds'])
            if stage == 'runtime':
                env['PYTHONPATH'] = str(output / 'runtime/numpy201') + os.pathsep + env['PYTHONPATH']
            emit(stage=stage)
        scientific = read(output / 'matrix/RESULT.json').get('scientific_status') if 'matrix' in args.stages else 'NOT_EVALUATED'
        final = dict(status='COMPLETE', stages=args.stages, scientific_status=scientific,
            package_sha256=package_sha, optimizer_updates=0, retries=0,
            evaluation_scope='FULL_MATRIX' if 'matrix' in args.stages else 'AUTHORIZED_STAGE_PREFIX_ONLY')
        write(output / 'RESULT.json', final)
        emit(status='COMPLETE', scientific_status=scientific, worker_alive=False)
        return 0
    except BaseException as exc:
        current = record.get('stage')
        for item in record['stages']:
            if item['state'] == 'RUNNING':
                item['state'] = 'EXCEPTION_STOP'
        emit(status='EXCEPTION_STOP', stage=current, error_type=type(exc).__name__,
             reason=str(exc), evidence_preserved=True, worker_alive=False)
        return 70


if __name__ == '__main__':
    def stopped(signum, frame):
        raise RuntimeError('TERMINATION_SIGNAL:' + str(signum))
    signal.signal(signal.SIGTERM, stopped)
    sys.exit(main())
