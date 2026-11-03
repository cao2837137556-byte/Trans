"""Bounded local real-slice E2E entrypoint with durable failure receipts.

Local Windows PASS never satisfies the final Linux/Python3.11 delivery gate.
The supervisor terminates the process tree at 600s and never retries.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
if platform.system() == 'Windows':
    sys.path.insert(0, str(ROOT / 'runs/diagnostics_step2_r2_v1_20261025/benchmark_deps'))
sys.path.insert(0, str(HERE))
from engine import read, require, sha


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


class Progress:
    def __init__(self, out, seconds=600):
        self.out = Path(out)
        self.started = time.monotonic()
        self.seconds = seconds
        self.peak = 0
        self.stages = []

    def guard(self):
        import psutil
        require(time.monotonic() - self.started < self.seconds, 'PREFLIGHT_WALL_LIMIT')
        tree = [psutil.Process()] + psutil.Process().children(recursive=True)
        rss = 0
        for process in tree:
            try:
                rss += process.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        self.peak = max(self.peak, rss)
        require(rss < 6 * 1024 ** 3, 'PREFLIGHT_MEMORY_LIMIT')

    def save(self, stage, **extra):
        self.guard()
        write(self.out / 'STATUS.json', dict(status='RUNNING', stage=stage,
              elapsed_seconds=time.monotonic() - self.started, peak_tree_rss_bytes=self.peak,
              stages=self.stages, **extra))

    @contextmanager
    def stage(self, name):
        item = dict(name=name, status='STARTED', started_utc=datetime.now(timezone.utc).isoformat())
        self.stages.append(item)
        self.save(name)
        started = time.monotonic()
        try:
            yield item
        except BaseException as exc:
            item.update(status='FAIL', error=repr(exc), seconds=time.monotonic() - started)
            raise
        else:
            item.update(status='PASS', seconds=time.monotonic() - started)
            self.save(name + '_COMPLETE')


def environment(tshark=None):
    versions = {}
    for package in ('numpy', 'torch', 'transformers', 'safetensors', 'psutil'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    tshark = tshark or ('C:/Program Files/Wireshark/tshark.exe' if platform.system() == 'Windows'
                        else shutil.which('tshark'))
    decoder = dict(path=tshark, available=False)
    if tshark:
        try:
            observed = subprocess.run([str(tshark), '--version'], capture_output=True,
                text=True, check=True, timeout=30).stdout.splitlines()[0]
            decoder.update(available=True, version_line=observed, sha256=sha(tshark),
                           expected_4_6_6=('4.6.6' in observed))
        except (OSError, subprocess.SubprocessError) as error:
            decoder['error'] = repr(error)
    exact = (platform.system() == 'Linux' and platform.python_version() == '3.11.11'
             and versions['numpy'] == '2.0.1' and versions['torch'].split('+')[0] == '2.5.1'
             and versions['transformers'] == '4.57.3' and decoder.get('expected_4_6_6', False)) if versions['torch'] else False
    return dict(system=platform.system(), python=platform.python_version(), executable=sys.executable,
                versions=versions, tshark=decoder, expected_linux_hpc_runtime_exact=exact,
                expected=dict(system='Linux', python='3.11.11', numpy='2.0.1', torch='2.5.1', transformers='4.57.3', tshark='4.6.6'))


def worker(args):
    from engine import frozen_assets, encode_snapshots, source_parity, evaluate_fixture
    out = Path(args.output)
    progress = Progress(out)
    result = dict(schema='EDGE_ENGINEERING_REAL_SLICE_PREFLIGHT_V1',
                  scope='ENGINEERING_ONLY_NOT_EXTERNAL_EVALUATION', training=False,
                  cloud_jobs_submitted=0, external_quality_metrics=False,
                  automatic_retry=False, budget_seconds=600, budget_cpu_threads=1)
    try:
        with progress.stage('ENVIRONMENT'):
            env = environment(args.tshark)
            result['environment'] = env
            if args.strict_runtime:
                require(env['expected_linux_hpc_runtime_exact'], 'SAME_RUNTIME_REQUIRED')
        with progress.stage('INPUT_PINS'):
            freeze, assets, normalizer, pins = frozen_assets()
            result['input_pins'] = pins
            slice_spec = read(args.slice)
            require(slice_spec['mode'] == 'FIXED_HEADER_ONLY_ENGINEERING_SLICE', 'SLICE_SCOPE')
            require(sum(len(s['frames']) for s in slice_spec['slices']) <= 100, 'SLICE_ROW_CAP')
            result['slice_sha256'] = sha(args.slice)
            code_paths = [Path(__file__), HERE / 'engine.py', HERE.parent / 'adapter/edge_adapter.py',
                HERE.parent / 'evaluation.py', HERE.parent / 'baselines/knn5.py',
                ROOT / 'repo/ood/constrained_onboarding_core_v3.py',
                ROOT / 'repo/ood/constrained_onboarding_reference_v2.py',
                ROOT / 'repo/ood/continuous_input_v3.py',
                ROOT / 'repo/ood/issue27ckda_d1_representation_probe_v1.py']
            code_pins = {str(path.relative_to(ROOT)).replace('\\', '/'): sha(path) for path in code_paths}
            result['code_pins_before_execution'] = code_pins
            card = read(ROOT / 'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json')
            if args.raw_directory:
                for item in card['raw_inputs'].values():
                    item['path'] = str(Path(args.raw_directory) / Path(item['path'].replace('\\', '/')).name)
            raw_before = {}
            for role in sorted({s['role'] for s in slice_spec['slices']}):
                item = card['raw_inputs'][role]
                path = Path(item['path'])
                require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'RAW_INPUT_PIN:' + role)
                raw_before[role] = dict(path=str(path), bytes=item['bytes'], sha256=item['sha256'],
                                        mtime_ns=path.stat().st_mtime_ns)
            result['raw_input_pins'] = raw_before
        with progress.stage('REAL_UNFILTERED_DECODE_CONTEXT_DESCRIPTOR'):
            sys.path.insert(0, str(HERE.parent / 'adapter'))
            from edge_adapter import selected_snapshots
            entries = []
            for index, spec in enumerate(slice_spec['slices']):
                work = out / ('decode_%02d' % index)
                entries.extend(selected_snapshots(spec['role'], set(spec['frames']), work,
                    reference_frames=spec.get('reference_frames', ()),
                    value=card, tshark=Path(env['tshark']['path']),
                    deadline=progress.started + progress.seconds))
                progress.guard()
            require(len(entries) > 0 and len({e['uid'] for e in entries}) == len(entries), 'REAL_SLICE_UIDS')
            require(len(entries) <= 100, 'ACTUAL_ROW_CAP')
            result['decoded_snapshots'] = len(entries)
        # Decode ends before the frozen encoder is imported/resident.
        with progress.stage('REAL_FROZEN_ENCODER'):
            budget = dict(logical_reserved=0, physical_reserved=0)
            e3, q14, encoded = encode_snapshots(entries, budget, progress)
            result['encoding'] = encoded
        with progress.stage('SOURCE_HEAD_PARITY'):
            result['source_parity'] = source_parity(assets, normalizer, freeze, progress)
            require(result['source_parity']['four_head_decision_exact'], 'SOURCE_FOUR_HEAD_PARITY')
            require(result['source_parity']['tolerance_1e_4_pass'], 'SOURCE_SCORE_ERROR')
        with progress.stage('REAL_DISTANCE_FOUR_HEAD_EVALUATE_RECEIPT'):
            result['fixture'] = evaluate_fixture(entries, e3, q14, assets, normalizer, freeze, progress)
        with progress.stage('IMMUTABLE_RAW_READBACK'):
            for role, item in raw_before.items():
                path = Path(item['path'])
                require(path.stat().st_size == item['bytes'] and path.stat().st_mtime_ns == item['mtime_ns']
                        and sha(path) == item['sha256'], 'RAW_INPUT_CHANGED_DURING_PREFLIGHT:' + role)
            result['raw_inputs_immutable_after_run'] = True
            require(all(sha(ROOT / path) == digest for path, digest in code_pins.items()),
                    'CODE_CHANGED_DURING_PREFLIGHT')
            result['code_immutable_after_run'] = True
        result.update(status='SAME_RUNTIME_REAL_SLICE_E2E_PASS' if env['expected_linux_hpc_runtime_exact']
                      else 'LOCAL_REAL_SLICE_E2E_PASS_FINAL_RUNTIME_GATE_PENDING',
                      final_linux_runtime_gate_pass=env['expected_linux_hpc_runtime_exact'],
                      elapsed_seconds=time.monotonic() - progress.started,
                      peak_tree_rss_bytes=progress.peak, stages=progress.stages)
    except BaseException as exc:
        result.update(status='STOPPED_NO_RETRY', error=repr(exc), traceback=traceback.format_exc(),
                      final_linux_runtime_gate_pass=False,
                      elapsed_seconds=time.monotonic() - progress.started,
                      peak_tree_rss_bytes=progress.peak, stages=progress.stages)
        write(out / 'RESULT.json', result)
        write(out / 'STATUS.json', result)
        return 1
    write(out / 'RESULT.json', result)
    write(out / 'STATUS.json', result)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slice', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--strict-runtime', action='store_true')
    parser.add_argument('--tshark')
    parser.add_argument('--raw-directory')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        return worker(args)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__)), '--worker',
               '--slice', str(Path(args.slice).resolve()), '--output', str(out.resolve())]
    if args.strict_runtime:
        command.append('--strict-runtime')
    if args.tshark:
        command += ['--tshark', args.tshark]
    if args.raw_directory:
        command += ['--raw-directory', args.raw_directory]
    with (out / 'worker.log').open('x', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            import psutil
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            process.wait()
            write(out / 'SUPERVISOR_FAILURE.json', dict(status='HARD_TIMEOUT_STOPPED_NO_RETRY', wall_seconds=600))
            return 1
    result = out / 'RESULT.json'
    require(result.exists(), 'PREFLIGHT_WORKER_NO_RESULT')
    result.with_name('RESULT.json.sha256').write_text(sha(result) + '  RESULT.json\n', encoding='utf-8')
    print(json.dumps(read(result), ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
