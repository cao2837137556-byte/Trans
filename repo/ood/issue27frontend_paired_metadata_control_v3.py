"""Observable, one-attempt controller for B metadata acquisition, never training."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import issue27frontend_paired_metadata_v1 as s
from types import SimpleNamespace
from issue27frontend_paired_metadata_monitor_fix_v2 import directory_bytes as stable_directory_bytes
from issue27frontend_paired_metadata_io_fix_v3 import atomic_json
s = SimpleNamespace(**vars(s))
s.atomic_json = atomic_json
s.PACKAGE = "runs/frontend_paired_metadata_implementation_v3_20260909"
s.REAL = "runs/frontend_paired_metadata_v3_20260909"
from issue27frontend_inheritance_outer_control_v1 import Job, pid_alive
from issue27frontend_inheritance_n1_support_v1 import peak_memory


def readiness():
    package = s.ROOT / s.PACKAGE
    s.verify_manifest(package)
    config = s.read_json(package / 'execution_config.json')
    accept = s.read_json(package / 'synthetic_acceptance.json')
    s.require(accept['status'] == 'PAIRED_METADATA_IMPLEMENTATION_ACCEPTANCE_PASS' and
              accept['config_sha256'] == s.sha_file(package / 'execution_config.json') and
              accept['tests_passed'] == accept['tests_run'] and accept['tests_run'] >= 20 and
              accept['real_packets_decoded'] == accept['model_calls'] == 0, 'IMPLEMENTATION_ACCEPTANCE')
    for rel, h in config['code_and_document_pins'].items():
        s.require(s.sha_file(s.ROOT / rel) == h, 'IMPLEMENTATION_PIN_' + Path(rel).name)
    s.require(config['caps'] == dict(s.CAPS, controller_reserve_bytes=256 * 1024**2), 'RESOURCE_CAP_DRIFT')
    s.require(Path(sys.executable).resolve() == Path(config['python_path']).resolve(), 'PYTHON_PATH')
    for path, h in config['runtime_pins'].items():
        s.require(s.sha_file(Path(path)) == h, 'RUNTIME_IDENTITY')
    targets, members = s.load_inputs()
    containers = {m['container_path']: m['container_bytes'] for m in members}
    s.require(sum(containers.values()) == config['raw_identity_bytes'] and len(containers) == config['raw_identity_files'], 'RAW_ENVELOPE')
    # Does not stat, hash or open raw project containers.
    return config


def directory_bytes(folder):
    return stable_directory_bytes(folder)


def supervise(command, output, config, synthetic=False, validator=None):
    output.mkdir(parents=True, exist_ok=False)
    started, process, job, reason, peak = time.monotonic(), None, None, None, 0
    caps = config['caps']
    s.atomic_json(output / 'attempt.json', {'controller_pid': os.getpid(), 'started_unix': time.time(),
        'caps': caps, 'synthetic': synthetic, 'restarts': 0})
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='2705')
        process = subprocess.Popen(command, cwd=str(s.ROOT), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        job = Job(process, caps['memory_bytes'] - caps['controller_reserve_bytes'])
        s.atomic_json(output / 'worker_gate.json', {'worker_pid': process.pid, 'parent_pid': os.getpid(), 'started': started})
        while process.poll() is None:
            controller_peak = peak_memory()
            peak = max(peak, job.peak() + controller_peak)
            if controller_peak > caps['controller_reserve_bytes'] or peak > caps['memory_bytes']:
                reason = 'AGGREGATE_MEMORY_CAP'
            if time.monotonic() - started > caps['wall_seconds'] - 2:
                reason = 'WALL_CAP'
            if directory_bytes(output) > caps['output_bytes'] - caps['reserve_bytes']:
                reason = 'OUTPUT_CAP'
            if reason:
                job.terminate(); break
            time.sleep(0.1)
        process.wait(timeout=10)
        peak = max(peak, job.peak() + peak_memory())
    except Exception as exc:
        reason = type(exc).__name__ + ': ' + str(exc)[:1000]
    finally:
        if process is not None and process.poll() is None:
            if job is not None: job.terminate()
            else: process.kill()
            process.wait(timeout=10)
        if job is not None: job.close()
    verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': reason or 'WORKER_TERMINAL_MISSING', 'scientific_capability': 'NOT_TESTED'}
    if not reason and process is not None and process.returncode == 0:
        try:
            path = output / 'worker_terminal.json'
            s.require(path.stat().st_size <= 65536, 'WORKER_TERMINAL_SIZE')
            if validator is None:
                from issue27frontend_paired_metadata_runner_v3 import verify_worker
                validator = verify_worker
            verdict = validator(s.read_json(path), output, config, synthetic)
        except Exception as exc:
            verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': type(exc).__name__ + ': ' + str(exc)[:1000], 'scientific_capability': 'NOT_TESTED'}
    peak = max(peak, peak_memory())
    try:
        if (time.monotonic() - started > caps['wall_seconds'] or peak > caps['memory_bytes']
                or directory_bytes(output) > caps['output_bytes'] - caps['reserve_bytes']):
            verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'FINAL_RESOURCE_CAP', 'scientific_capability': 'NOT_TESTED'}
    except Exception as exc:
        verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'FINAL_OUTPUT_SNAPSHOT: ' + str(exc)[:1000],
                   'scientific_capability': 'NOT_TESTED'}
    s.atomic_json(output / 'supervisor_terminal.json', {'verdict': verdict, 'synthetic': synthetic,
        'worker_count': int(process is not None), 'worker_exit_code': None if process is None else process.returncode,
        'restarts': 0, 'elapsed_seconds': time.monotonic() - started, 'aggregate_peak_bytes_upper_bound': peak,
        'enforcement': 'Windows job worker+decoder, reserved controller memory, external wall/output monitor; no retry'})
    s.seal(output)
    return verdict


def status(output):
    if not output.exists():
        return {'status': 'NOT_STARTED', 'final': False}
    try:
        if (output / 'supervisor_terminal.json').exists() and (output / 'SHA256SUMS').exists():
            s.verify_manifest(output)
            terminal = s.read_json(output / 'supervisor_terminal.json')
            v = terminal['verdict']['status']
            return {**terminal, 'status': v, 'final': True, 'seal_verified': True}
        attempt = s.read_json(output / 'attempt.json')
        if not pid_alive(attempt['controller_pid']):
            return {'status': 'INTERRUPTED_DO_NOT_RESTART', 'final': False}
        if (output / 'worker_terminal.json').exists():
            return {'status': 'SEALING', 'final': False}
        if (output / 'progress.json').exists():
            return {**s.read_json(output / 'progress.json'), 'final': False}
        return {'status': 'STARTING', 'final': False}
    except (OSError, ValueError, KeyError, s.Stop):
        return {'status': 'RECEIPT_OR_SEAL_INVALID_DO_NOT_RESTART', 'final': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('status', 'check-readiness', 'run-real', 'worker'))
    parser.add_argument('--authorization')
    args = parser.parse_args()
    output = s.ROOT / s.REAL
    if args.mode == 'status':
        print(s.canonical(status(output)).decode('utf-8'), flush=True); return
    if args.mode == 'check-readiness':
        readiness(); s.require(not output.exists(), 'ATTEMPT_ALREADY_EXISTS')
        print('{"status":"READY_FOR_SEPARATELY_AUTHORIZED_B_METADATA_PASS","real_started":false}'); return
    s.require(args.authorization == s.AUTH, 'EXPLICIT_B_HEADER_READ_AUTHORIZATION_REQUIRED')
    if args.mode == 'worker':
        deadline = time.monotonic() + 30
        while not (output / 'worker_gate.json').exists():
            s.require(time.monotonic() < deadline, 'WORKER_GATE_TIMEOUT'); time.sleep(0.05)
        gate = s.read_json(output / 'worker_gate.json')
        s.require(gate['worker_pid'] == os.getpid() and gate['parent_pid'] == os.getppid(), 'WORKER_GATE_IDENTITY')
        config = readiness()
        from issue27frontend_paired_metadata_runner_v3 import worker
        worker(output, config, gate['started']); return
    config = readiness()
    command = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--authorization', s.AUTH]
    print(s.canonical(supervise(command, output, config)).decode('utf-8'), flush=True)


if __name__ == '__main__':
    main()
