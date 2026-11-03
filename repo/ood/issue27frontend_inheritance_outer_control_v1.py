"""Explicit one-attempt supervisor and read-only progress for the outer pool."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import issue27frontend_inheritance_outer_support_v1 as s


class Job:
    """Worker plus at most one decoder, aggregate committed-memory cap."""
    def __init__(self, process, limit):
        s.require(os.name == 'nt', 'WINDOWS_JOB_REQUIRED')
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount',
                'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]
        class Basic(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', ctypes.c_ulong), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', ctypes.c_ulong),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', ctypes.c_ulong), ('SchedulingClass', ctypes.c_ulong)]
        class Extended(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', IO), ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
        self.Extended = Extended
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self.kernel.CreateJobObjectW.restype = ctypes.c_void_p
        self.kernel.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
        self.kernel.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
        self.kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        s.require(bool(self.handle), 'JOB_CREATE')
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2308
        info.BasicLimitInformation.ActiveProcessLimit = 2
        info.ProcessMemoryLimit = info.JobMemoryLimit = limit
        try:
            s.require(self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)), 'JOB_LIMIT')
            s.require(self.kernel.AssignProcessToJobObject(self.handle, ctypes.c_void_p(int(process._handle))), 'JOB_ASSIGN')
        except Exception:
            self.close(); raise

    def peak(self):
        info = self.Extended()
        s.require(self.kernel.QueryInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info), None), 'JOB_QUERY')
        return int(info.PeakJobMemoryUsed)

    def terminate(self):
        s.require(self.kernel.TerminateJobObject(self.handle, 124), 'JOB_TERMINATE')

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle); self.handle = None


def readiness(root=s.ROOT):
    folder = root / s.PACKAGE
    s.verify_seal(folder)
    config = json.loads((folder / 'execution_config.json').read_text(encoding='utf-8'))
    acceptance = json.loads((folder / 'synthetic_acceptance.json').read_text(encoding='utf-8'))
    s.require(acceptance['status'] == 'OUTER_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS'
              and acceptance['config_sha256'] == s.sha_file(folder / 'execution_config.json')
              and acceptance['real_model_forwards'] == acceptance['raw_replays'] == 0
              and acceptance['tests_passed'] == acceptance['tests_run'] >= 30, 'IMPLEMENTATION_ACCEPTANCE')
    for path, sha in config['code_pins'].items():
        s.require(s.sha_file(root / path) == sha, 'CODE_DRIFT_' + Path(path).name)
    for path, sha in config['document_pins'].items():
        s.require(s.sha_file(root / path) == sha, 'DOCUMENT_DRIFT')
    s.require(s.sha_file(root / s.DESIGN) == s.DESIGN_SHA, 'DESIGN_DRIFT')
    s.verify_seal(root / s.METADATA, config['metadata_manifest_sha256'])
    s.require(s.sha_file(root / s.METADATA / 'qualified_metadata.json') == config['metadata_sha256'], 'METADATA_DRIFT')
    runtime = Path(config['runtime_root'])
    s.require(Path(sys.executable).resolve() == (runtime / 'python.exe').resolve(), 'PYTHON_IDENTITY')
    for name, sha in config['runtime_pins'].items():
        s.require(s.sha_file(runtime / name) == sha, 'RUNTIME_DRIFT')
    s.require(s.sha_file(Path(config['tshark']['executable_path'])) == config['tshark']['executable_sha256'], 'TSHARK_DRIFT')
    return config


def validate_worker(receipt, folder, config):
    verdict = receipt['verdict']
    s.require(verdict['status'] in ('OUTER_COMPARISON_COMPLETE', 'INPUT_OR_EXECUTION_STOP'), 'WORKER_STATUS')
    if verdict['status'] != 'OUTER_COMPARISON_COMPLETE':
        return {**verdict, **s.CLAIMS}
    s.require(verdict['complete'] is True and verdict['targets'] == 4400 and verdict['contexts'] == 3582
              and all(verdict.get(k) == v for k, v in s.CLAIMS.items()), 'WORKER_COMPLETE')
    counts = receipt['resource']['counts']
    s.require(counts == config['expected_actions'], 'WORKER_ACTION_COUNTS')
    s.require(all(receipt['access'].get(k) == 0 for k in ('optimizer_steps', 'backward_steps', 'LP_calls',
                                                       'teacher_forwards', 'historical_model_replays', 'retries')), 'FORBIDDEN_ACTION')
    required = {'runtime_receipt.json', 'outer_features.f32le', 'input_target_receipts.json', 'prepared_input_receipt.json',
                'candidate_before.json', 'candidate_after.json', 'all_target_predictions.json', 'comparison.json', 'access_receipt.json'}
    s.require(set(receipt['output_hashes']) == required, 'WORKER_OUTPUT_SET')
    for name, sha in receipt['output_hashes'].items():
        s.require(s.sha_file(folder / name) == sha, 'WORKER_OUTPUT_HASH')
    def read(name):
        return json.loads((folder / name).read_text(encoding='utf-8'))
    before, after = read('candidate_before.json'), read('candidate_after.json')
    s.require(before['assembled_state'] == after['assembled_state'] == config['candidate_state_sha256'], 'WORKER_CANDIDATE_STATE')
    metadata = json.loads(s.read_pinned(s.ROOT, s.METADATA + '/qualified_metadata.json', config['metadata_sha256']))
    rows = read('all_target_predictions.json')
    s.require(len(rows) == 4400 and len({r['uid'] for r in rows}) == 4400, 'RESULT_UIDS')
    recomputed, attachments = s.measurements(metadata['contexts'], {r['uid']: r['logit'] for r in rows})
    s.require(attachments == rows and read('comparison.json') == recomputed, 'RESULT_RECOMPUTATION')
    s.require(all(verdict[k] == recomputed[k] for k in ('A_retention', 'B_utility')), 'RESULT_VERDICT')
    prepared = read('prepared_input_receipt.json')
    s.require(prepared['status'] == 'INPUT_PREPARED' and prepared['targets'] == 4400 and prepared['contexts'] == 3582
              and prepared['events'] == 5164 and prepared['L0_prefix_mismatches'] == 0
              and prepared['features_sha256'] == s.sha_file(folder / 'outer_features.f32le')
              and (folder / 'outer_features.f32le').stat().st_size == 2705936, 'PREPARED_EVIDENCE')
    return verdict


def directory_bytes(folder):
    return sum(p.stat().st_size for p in folder.iterdir() if p.is_file())


def supervise(command, output, config, synthetic=False):
    output.mkdir(parents=True, exist_ok=False)
    start, process, job, peak, reason = time.monotonic(), None, None, 0, None
    caps = config['caps']
    s.atomic_json(output / 'attempt.json', {'controller_pid': os.getpid(), 'started_unix': time.time(),
        'caps': caps, 'synthetic': synthetic, 'restarts': 0})
    try:
        environment = dict(os.environ, PYTHONHASHSEED='2705', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
                           PYTHONDONTWRITEBYTECODE='1', TORCH_FORCE_WEIGHTS_ONLY_LOAD='1')
        process = subprocess.Popen(command, cwd=str(s.ROOT), env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        job = Job(process, caps['memory_bytes'])
        s.atomic_json(output / 'worker_gate.json', {'worker_pid': process.pid, 'parent_pid': os.getpid(), 'started': start})
        while process.poll() is None:
            peak = max(peak, job.peak())
            if time.monotonic() - start > caps['wall_seconds'] - 2:
                reason = 'WALL_CAP'
            if directory_bytes(output) > caps['output_bytes'] - caps['reserve_bytes']:
                reason = 'OUTPUT_CAP'
            if reason:
                job.terminate(); break
            time.sleep(0.1)
        process.wait(timeout=10)
        peak = max(peak, job.peak())
    except Exception as exc:
        reason = str(exc) if isinstance(exc, s.Stop) else 'SUPERVISOR_' + type(exc).__name__
    finally:
        if process is not None and process.poll() is None:
            if job is not None: job.terminate()
            else: process.kill()
            process.wait(timeout=10)
        if job is not None: job.close()
    verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': reason or 'WORKER_TERMINAL_MISSING', **s.CLAIMS}
    if not reason and process is not None and process.returncode == 0:
        try:
            terminal = output / 'worker_terminal.json'
            s.require(terminal.stat().st_size <= 65536, 'WORKER_TERMINAL_SIZE')
            verdict = validate_worker(json.loads(terminal.read_text(encoding='utf-8')), output, config)
        except Exception as exc:
            verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': str(exc) if isinstance(exc, s.Stop)
                       else 'TERMINAL_' + type(exc).__name__, **s.CLAIMS}
    members = {p.name: s.sha_file(p) for p in sorted(output.iterdir()) if p.is_file()}
    if (time.monotonic() - start > caps['wall_seconds'] or peak > caps['memory_bytes']
            or directory_bytes(output) > caps['output_bytes'] - caps['reserve_bytes']):
        verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'FINAL_RESOURCE_CAP', **s.CLAIMS}
    s.atomic_json(output / 'supervisor_terminal.json', {'verdict': verdict, 'worker_count': int(process is not None),
        'worker_exit_code': None if process is None else process.returncode, 'restarts': 0, 'synthetic': synthetic,
        'elapsed_seconds': time.monotonic() - start, 'job_peak_committed_bytes': peak,
        'enforcement': 'Windows job: worker plus one decoder, aggregate memory, kill-on-close; external wall/output monitor'})
    members['supervisor_terminal.json'] = s.sha_file(output / 'supervisor_terminal.json')
    with (output / 'SHA256SUMS').open('xb') as stream:
        stream.write(''.join(h + '  ' + n + '\n' for n, h in sorted(members.items())).encode('ascii'))
    return verdict


def pid_alive(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle: return False
    code = ctypes.c_ulong()
    try: return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally: kernel.CloseHandle(handle)


def status(output):
    if not output.exists(): return {'status': 'NOT_STARTED', 'final': False}
    try:
        terminal = output / 'supervisor_terminal.json'
        if terminal.exists() and (output / 'SHA256SUMS').exists():
            s.verify_seal(output)
            receipt = json.loads(terminal.read_text(encoding='utf-8'))
            return {'status': 'COMPLETED' if receipt['verdict']['status'] == 'OUTER_COMPARISON_COMPLETE' else 'STOPPED',
                    'final': True, **receipt}
        attempt = json.loads((output / 'attempt.json').read_text(encoding='utf-8'))
        if not pid_alive(attempt['controller_pid']):
            return {'status': 'INTERRUPTED_DO_NOT_RESTART', 'final': False}
        if (output / 'worker_terminal.json').exists(): return {'status': 'SEALING', 'final': False}
        if (output / 'progress.json').exists():
            return {**json.loads((output / 'progress.json').read_text(encoding='utf-8')), 'final': False}
        return {'status': 'STARTING', 'final': False}
    except (OSError, ValueError, s.Stop, KeyError):
        return {'status': 'RECEIPT_OR_SEAL_INVALID_DO_NOT_RESTART', 'final': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('status', 'check-readiness', 'run-real', 'worker'))
    parser.add_argument('--authorization')
    args = parser.parse_args()
    output = s.ROOT / s.REAL
    if args.mode == 'status': print(json.dumps(status(output)), flush=True); return
    if args.mode == 'check-readiness':
        readiness(); s.require(not output.exists(), 'ATTEMPT_ALREADY_EXISTS')
        print(json.dumps({'status': 'READY_FOR_SEPARATELY_AUTHORIZED_OUTER_COMPARISON', 'real_started': False})); return
    s.require(args.authorization == s.AUTH, 'EXPLICIT_REAL_AUTHORIZATION_REQUIRED')
    if args.mode == 'worker':
        deadline = time.monotonic() + 30
        while not (output / 'worker_gate.json').exists():
            s.require(time.monotonic() < deadline, 'WORKER_GATE_TIMEOUT'); time.sleep(0.05)
        gate = json.loads((output / 'worker_gate.json').read_text(encoding='utf-8'))
        s.require(gate['worker_pid'] == os.getpid() and gate['parent_pid'] == os.getppid(), 'WORKER_GATE_IDENTITY')
        config = readiness()
        from issue27frontend_inheritance_outer_runner_v1 import worker
        worker(output, config, gate['started']); return
    config = readiness()
    command = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--authorization', s.AUTH]
    print(json.dumps(supervise(command, output, config)), flush=True)


if __name__ == '__main__': main()
