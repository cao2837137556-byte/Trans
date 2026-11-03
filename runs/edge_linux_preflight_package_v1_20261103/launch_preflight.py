"""Outer package supervisor: exact old preflight, no retry/full evaluation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def write(path, body):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(body, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-directory', required=True)
    parser.add_argument('--tshark', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--slice', required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = dict(scope='ENGINEERING_ONLY_NOT_FULL_EVALUATION', automatic_retry=False,
                  cloud_jobs_submitted=0, training=False, formal_external_evaluation=False,
                  created_utc=datetime.now(timezone.utc).isoformat())
    child = None
    try:
        write(out / 'DELIVERY_STATUS.json', dict(result, status='RUNNING', stage='PACKAGE_BYTE_VERIFY'))
        from verify_package import verify
        result['package'] = verify(ROOT, HERE / 'PACKAGE_MANIFEST.json')
        write(out / 'DELIVERY_STATUS.json', dict(result, status='RUNNING', stage='RUNTIME_IDENTITY'))
        identity = [sys.executable, '-X', 'utf8', '-B', str(HERE / 'runtime_identity.py'),
                    '--tshark', args.tshark, '--output', str(out / 'RUNTIME_IDENTITY.json')]
        subprocess.run(identity, check=True, timeout=45)
        slice_path = Path(args.slice).resolve()
        if not slice_path.is_relative_to(ROOT):
            raise ValueError('SLICE_NOT_IN_SEALED_PACKAGE')
        manifest = json.loads((HERE / 'PACKAGE_MANIFEST.json').read_text())
        if slice_path.relative_to(ROOT).as_posix() not in manifest['files']:
            raise ValueError('SLICE_NOT_PINNED')
        contract = json.loads((HERE / 'PACKAGE_CONTRACT.json').read_text())
        entry = (ROOT / contract['preflight_entry']).resolve()
        if not entry.is_relative_to(ROOT) or entry.relative_to(ROOT).as_posix() not in manifest['files']:
            raise ValueError('PREFLIGHT_WRAPPER_NOT_PINNED')
        command = [sys.executable, '-X', 'utf8', '-B',
            str(entry),
            '--slice', str(slice_path), '--output', str(out / 'real_slice'), '--strict-runtime',
            '--tshark', args.tshark, '--raw-directory', str(Path(args.raw_directory).resolve())]
        # Package setup and identity consume part of the enclosing ten minutes.
        # Leave at least 30 seconds for a durable STOP receipt.
        remaining = min(540., 565. - (time.monotonic() - started))
        if remaining <= 0:
            raise TimeoutError('PACKAGE_SETUP_EXHAUSTED_PREFLIGHT_BUDGET')
        write(out / 'DELIVERY_STATUS.json', dict(result, status='RUNNING', stage='STRICT_REAL_SLICE',
              child_wall_seconds=remaining, real_slice_status_path=str(out / 'real_slice/STATUS.json')))
        with (out / 'preflight_supervisor.log').open('x', encoding='utf-8') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                result['child_exit_code'] = child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
                raise TimeoutError('OUTER_ENGINEERING_WALL_LIMIT_NO_RETRY')
        receipt = out / 'real_slice/RESULT.json'
        if not receipt.is_file():
            raise ValueError('NO_REAL_SLICE_RESULT')
        actual = json.loads(receipt.read_text(encoding='utf-8'))
        result['package_after'] = verify(ROOT, HERE / 'PACKAGE_MANIFEST.json')
        passed = (result['child_exit_code'] == 0
                  and actual.get('status') == 'SAME_RUNTIME_REAL_SLICE_E2E_PASS'
                  and actual.get('final_linux_runtime_gate_pass') is True
                  and actual.get('strict_shape_probes', {}).get('status') == 'PASS')
        result.update(status='LINUX_PREFLIGHT_PASS' if passed else 'STOPPED_NO_RETRY',
                      real_slice_status=actual.get('status'),
                      strict_shape_probe_status=actual.get('strict_shape_probes', {}).get('status'),
                      final_runtime_gate_pass=bool(actual.get('final_linux_runtime_gate_pass', False)),
                      full_execution_ready=False)
    except BaseException as exc:
        result.update(status='STOPPED_NO_RETRY', error=repr(exc), final_runtime_gate_pass=False,
                      full_execution_ready=False)
    result['elapsed_seconds'] = time.monotonic() - started
    write(out / 'DELIVERY_RESULT.json', result)
    write(out / 'DELIVERY_STATUS.json', result)
    return 0 if result['status'] == 'LINUX_PREFLIGHT_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
