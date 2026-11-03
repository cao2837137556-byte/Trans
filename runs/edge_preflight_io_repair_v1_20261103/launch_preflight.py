"""Package-external I/O supervisor; frozen computation, one bounded attempt."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
MANIFEST_SHA256 = 'f61af6ca64c629565e6914ef520c85352b65a5987e7af6d9515d1848cc4ccbd6'
MANIFEST_FILE_COUNT = 863
PACKAGE_RELATIVE = Path('runs/edge_linux_preflight_package_v1_20261103')


def write(path, body):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(body, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('DELIVERY_DEADLINE_FINAL_RECEIPT_RESERVED')


def sha(path, deadline=None):
    digest = hashlib.sha256()
    check_deadline(deadline)
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 ** 2), b''):
            check_deadline(deadline)
            digest.update(block)
    check_deadline(deadline)
    return digest.hexdigest()


def verify_sealed_checkout(root, deadline=None):
    package = root / PACKAGE_RELATIVE
    manifest_path = package / 'PACKAGE_MANIFEST.json'
    if sha(manifest_path, deadline) != MANIFEST_SHA256:
        raise ValueError('SEALED_MANIFEST_SHA256')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if len(manifest['files']) != MANIFEST_FILE_COUNT:
        raise ValueError('SEALED_MANIFEST_FILE_COUNT')
    # Verify bytes before executing anything from that checkout, including its verifier.
    for name, item in manifest['files'].items():
        check_deadline(deadline)
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('PACKAGE_PATH_OR_MISSING:' + name)
        if path.stat().st_size != item['bytes'] or sha(path, deadline) != item['sha256']:
            raise ValueError('PACKAGE_BYTE_PIN:' + name)
    return dict(status='PACKAGE_BYTES_PASS_NOT_RUNTIME_PASS', files=len(manifest['files']),
                bytes=sum(x['bytes'] for x in manifest['files'].values()),
                manifest_sha256=sha(manifest_path, deadline)), manifest


def pinned_execution(root, manifest, slice_path, deadline=None):
    contract = json.loads((root / PACKAGE_RELATIVE / 'PACKAGE_CONTRACT.json').read_text(encoding='utf-8'))
    if sha(slice_path, deadline) != contract['active_slice_sha256']:
        raise ValueError('ACTIVE_SLICE_SHA256')
    # Relocation changes the supplied path, never the selected bytes.
    active = contract['active_slice']
    if active not in manifest['files'] or manifest['files'][active]['sha256'] != sha(slice_path, deadline):
        raise ValueError('ACTIVE_SLICE_NOT_PINNED')
    entry = (root / contract['preflight_entry']).resolve()
    if not entry.is_relative_to(root) or entry.relative_to(root).as_posix() not in manifest['files']:
        raise ValueError('PREFLIGHT_WRAPPER_NOT_PINNED')
    if contract.get('total_preflight_logical_with_probes') != 91:
        raise ValueError('FROZEN_LOGICAL_ENDPOINT_CONTRACT')
    return entry, contract


def acceptance(exit_code, actual):
    return (exit_code == 0
            and actual.get('status') == 'SAME_RUNTIME_REAL_SLICE_E2E_PASS'
            and actual.get('final_linux_runtime_gate_pass') is True
            and actual.get('strict_shape_probes', {}).get('status') == 'PASS')


def stop_group(child):
    if child is None or child.poll() is not None:
        return
    if os.name == 'posix':
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            os.killpg(child.pid, signal.SIGKILL)
        else:
            child.kill()
        child.wait(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-directory', required=True)
    parser.add_argument('--tshark', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--slice', required=True)
    parser.add_argument('--frozen-root', default=os.environ.get('EDGE_FROZEN_CHECKOUT'))
    args = parser.parse_args(argv)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = dict(scope='ENGINEERING_ONLY_NOT_FULL_EVALUATION', automatic_retry=False,
                  cloud_jobs_submitted=0, training=False, formal_external_evaluation=False,
                  created_utc=datetime.now(timezone.utc).isoformat())
    child = None
    delivery_deadline = started + 560.
    previous_alarm = None
    if hasattr(signal, 'setitimer'):
        previous_alarm = signal.getsignal(signal.SIGALRM)
        def alarm_expired(signum, frame):
            raise TimeoutError('DELIVERY_DEADLINE_FINAL_RECEIPT_RESERVED')
        signal.signal(signal.SIGALRM, alarm_expired)
        signal.setitimer(signal.ITIMER_REAL, max(.001, delivery_deadline-time.monotonic()))
    try:
        if not args.frozen_root:
            raise ValueError('EXPLICIT_FROZEN_CHECKOUT_REQUIRED')
        root = Path(args.frozen_root).resolve(strict=True)
        result['frozen_root'] = str(root)
        write(out / 'DELIVERY_STATUS.json', dict(result, status='RUNNING', stage='PACKAGE_BYTE_VERIFY'))
        result['package'], manifest = verify_sealed_checkout(root, delivery_deadline)
        entry, contract = pinned_execution(root, manifest, Path(args.slice).resolve(strict=True), delivery_deadline)
        result['original_probe_entry'] = str(entry)
        result['frozen_contract_sha256'] = sha(root / PACKAGE_RELATIVE / 'PACKAGE_CONTRACT.json', delivery_deadline)
        write(out / 'DELIVERY_STATUS.json', dict(result, status='RUNNING', stage='RUNTIME_IDENTITY'))
        identity = [sys.executable, '-X', 'utf8', '-B', str(root / PACKAGE_RELATIVE / 'runtime_identity.py'),
                    '--tshark', args.tshark, '--output', str(out / 'RUNTIME_IDENTITY.json')]
        check_deadline(delivery_deadline)
        subprocess.run(identity, check=True, timeout=min(45., delivery_deadline-time.monotonic()))
        setup_seconds = time.monotonic() - started
        allowance = min(520., 560. - setup_seconds)
        if allowance <= 15:
            raise TimeoutError('PACKAGE_SETUP_EXHAUSTED_PREFLIGHT_BUDGET')
        hard_deadline = time.monotonic() + allowance
        deadline = hard_deadline - 15.
        cache = Path(os.environ.get('EDGE_REPLAY_CACHE', str(out.parent / 'replay_cache'))).resolve()
        command = [sys.executable, '-X', 'utf8', '-B', str(HERE / 'worker.py'),
                   '--slice', str(Path(args.slice).resolve()), '--output', str(out / 'real_slice'),
                   '--strict-runtime', '--tshark', args.tshark,
                   '--raw-directory', str(Path(args.raw_directory).resolve()),
                   '--frozen-root', str(root), '--cache-root', str(cache),
                   '--deadline-monotonic', str(deadline),
                   '--hard-deadline-monotonic', str(hard_deadline)]
        result['deadline_contract'] = dict(setup_seconds=setup_seconds, child_hard_seconds=allowance,
                                          receipt_reserve_seconds=15., overall_reserve_at_least_seconds=40.)
        write(out / 'DELIVERY_STATUS.json', dict(result, status='RUNNING', stage='STRICT_REAL_SLICE',
              child_wall_seconds=allowance, real_slice_status_path=str(out / 'real_slice/STATUS.json')))
        with (out / 'preflight_supervisor.log').open('x', encoding='utf-8') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                result['child_exit_code'] = child.wait(timeout=max(.01, hard_deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                stop_group(child)
                raise TimeoutError('OUTER_ENGINEERING_WALL_LIMIT_NO_RETRY')
        receipt = out / 'real_slice/RESULT.json'
        if not receipt.is_file():
            raise ValueError('NO_REAL_SLICE_RESULT')
        actual = json.loads(receipt.read_text(encoding='utf-8'))
        result['package_after'], _ = verify_sealed_checkout(root, delivery_deadline)
        passed = acceptance(result['child_exit_code'], actual)
        result.update(status='LINUX_PREFLIGHT_PASS' if passed else 'STOPPED_NO_RETRY',
                      real_slice_status=actual.get('status'),
                      strict_shape_probe_status=actual.get('strict_shape_probes', {}).get('status'),
                      final_runtime_gate_pass=bool(actual.get('final_linux_runtime_gate_pass', False)) and passed,
                      full_execution_ready=False)
    except BaseException as exc:
        stop_group(child)
        result.update(status='STOPPED_NO_RETRY', error=repr(exc), final_runtime_gate_pass=False,
                      full_execution_ready=False)
    finally:
        if previous_alarm is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_alarm)
    result['elapsed_seconds'] = time.monotonic() - started
    write(out / 'DELIVERY_RESULT.json', result)
    write(out / 'DELIVERY_STATUS.json', result)
    return 0 if result['status'] == 'LINUX_PREFLIGHT_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
