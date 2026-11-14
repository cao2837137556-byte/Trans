"""Stage Motion on HPC and persist a resumable upload status locally."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import shlex
import time

from motion_ingress import ARCHIVE_BYTES, ARCHIVE_SHA, FAILED_PREP_JOB, LIMIT, RAW_SHA, REPAIR_RUN, digest

HERE = Path(__file__).resolve().parent
PRIVATE = HERE / '.private'
CFG = PRIVATE / 'MOTION_CONNECTION.json'
PROJECT = '/public/home/jiangxinwei.zr/work/paper04'
STAGE = PROJECT + '/runs/.' + HERE.name + '_motion_ingress'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'


def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def config_path(repair):
    return PRIVATE / ('REPAIR_CONNECTION.json' if repair else 'MOTION_CONNECTION.json')


def prepare(repair=False):
    PRIVATE.mkdir(exist_ok=True)
    config = config_path(repair)
    if not config.exists():
        write(config, dict(port=18889 if repair else 18888, token=secrets.token_hex(32)))
    cfg = json.loads(config.read_text())
    stage = STAGE + '_repair_' + FAILED_PREP_JOB if repair else STAGE
    suffix = f' --retry-prepare-job {FAILED_PREP_JOB}' if repair else ''
    script = base64.b64encode((HERE / 'motion_ingress.py').read_bytes().replace(b'\r\n', b'\n')).decode()
    # Dedicated private staging dir; a second invocation keeps the same token and partial upload.
    command = (
        f'umask 077 && s={shlex.quote(stage)} && mkdir -p -- "$s" && '
        f'( set -C; printf "%s\\n" {shlex.quote(cfg["token"])} > "$s/token" ) 2>/dev/null; '
        f's={shlex.quote(stage)} && test "$(cat "$s/token")" = {shlex.quote(cfg["token"])} && '
        f'printf %s {shlex.quote(script)} | base64 -d > "$s/motion_ingress.py.tmp" && '
        'mv -- "$s/motion_ingress.py.tmp" "$s/motion_ingress.py" && '
        f'( nohup flock -n "$s/receiver.lock" {PYTHON} -B "$s/motion_ingress.py" '
        f'--stage "$s" --port {cfg["port"]}{suffix} </dev/null >>"$s/relay.log" 2>&1 & )'
    )
    (PRIVATE / ('START_REPAIR_INGRESS.txt' if repair else 'START_MOTION_INGRESS.txt')).write_text(
        command, encoding='ascii')


def get_client():
    client_path = HERE.parent / 'reference_evidence_round1_v1_20261112' / 'local_client.py'
    import sys
    sys.path.insert(0, str(client_path.parent))
    spec = importlib.util.spec_from_file_location('r1_motion_transfer', client_path)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    return client


def upload():
    cfg = json.loads(CFG.read_text())
    local = PRIVATE / 'motion.pcap.gz'
    status_path = HERE / 'MOTION_UPLOAD_PROGRESS.json'
    if local.stat().st_size != ARCHIVE_BYTES or digest(local) != ARCHIVE_SHA:
        raise ValueError('MOTION_LOCAL_ARCHIVE_SHA')
    client = get_client()
    connect = client.transport()
    last_error = 'WAITING_FOR_EXISTING_VSCODE_TUNNEL'
    deadline = time.monotonic() + 3 * 3600
    while time.monotonic() < deadline:
        for port in client.ssh_socks_ports():
            relay = client.Relay(cfg, port, connect)
            try:
                status = relay.request('state', timeout=5)
                if (status['scope'], status['total_bytes'], status['raw_sha256']) != (
                        'P04_K8192_MOTION_V1', ARCHIVE_BYTES, RAW_SHA):
                    raise ValueError('MOTION_REMOTE_SCOPE')
                offset = status['bytes']
                if type(offset) is not int or not 0 <= offset <= ARCHIVE_BYTES:
                    raise ValueError('MOTION_REMOTE_OFFSET')
                with local.open('rb') as stream:
                    stream.seek(offset)
                    for data in iter(lambda: stream.read(LIMIT), b''):
                        write(status_path, dict(status='UPLOADING_MOTION', bytes=offset,
                                                total_bytes=ARCHIVE_BYTES))
                        receipt = relay.request('upload', 'POST', data,
                            {'X-Offset': str(offset), 'X-SHA256': hashlib.sha256(data).hexdigest()},
                            timeout=50)
                        if receipt['bytes'] != offset + len(data):
                            raise ValueError('MOTION_CHUNK_RECEIPT')
                        offset = receipt['bytes']
                result = relay.request('finish', 'POST', b'', timeout=90)
                if not result['complete'] or result['archive_sha256'] != ARCHIVE_SHA:
                    raise ValueError('MOTION_REMOTE_FINAL_PIN')
                write(status_path, result)
                return
            except (OSError, client.http.client.HTTPException) as error:
                last_error = type(error).__name__
            except ValueError as error:
                last_error = str(error)
                if 'MOTION_UPLOAD_OFFSET' not in last_error:
                    write(status_path, dict(status='STOP_MOTION_UPLOAD', error=last_error))
                    raise
        write(status_path, dict(status='WAITING_FOR_RELAY', reason=last_error))
        time.sleep(8)
    write(status_path, dict(status='STOP_MOTION_UPLOAD', error='TRANSFER_TIMEOUT'))
    raise TimeoutError('MOTION_UPLOAD_TIMEOUT')


def experiment(*, send, repair=False):
    cfg = json.loads(config_path(repair).read_text())
    client = get_client()
    relay = None
    for port in client.ssh_socks_ports():
        channel = client.Relay(cfg, port, client.transport())
        try:
            remote = channel.request('state', timeout=5)
            if remote['scope']=='P04_K8192_MOTION_V1' and (not repair or remote.get('run') == REPAIR_RUN):
                relay = channel
                break
        except (OSError, ValueError, client.http.client.HTTPException):
            continue
    if relay is None:
        raise ConnectionError('EXISTING_RELAY_UNAVAILABLE')
    if send:
        path = PRIVATE/'package.tar.gz'
        if not remote['complete']:
            raise ValueError('MOTION_UPLOAD_INCOMPLETE')
        data = path.read_bytes()
        if not 0 < len(data) <= LIMIT:
            raise ValueError('PACKAGE_SIZE')
        receipt = relay.request('install', 'POST', data,
                                {'X-SHA256': hashlib.sha256(data).hexdigest()}, timeout=60)
        if receipt['archive_sha256'] != digest(path) or receipt['package_manifest_sha256'] != digest(
                HERE/'PACKAGE_MANIFEST.json'):
            raise ValueError('INSTALL_RECEIPT_PACKAGE_PIN')
        write(HERE/('INSTALL_RECEIPT_REPAIR.json' if repair else 'INSTALL_RECEIPT.json'), receipt)
    return relay


def pull(relay, repair=False):
    status = relay.request('experiment')
    if status['install'] is not None:
        write(HERE/'LOCAL_PROGRESS.json', status)
    manifest = relay.request('results')
    if not manifest:
        return False
    folder = HERE/('received_repair_183971' if repair else 'received')
    folder.mkdir(exist_ok=True)
    for name, pin in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('RESULT_OUTSIDE_SCOPE')
        path = folder/name
        if not path.is_file() or digest(path) != pin['sha256']:
            relay.request('result-'+name, destination=(path,pin), timeout=60)
    write(folder/'RETURN.json', manifest)
    return True


def watch(repair=False, install=False):
    # Ordinary file transfer/status process. It never submits a job or starts SSH.
    end = time.monotonic()+72*3600
    while time.monotonic() < end:
        try:
            relay = experiment(send=install, repair=repair)
            install = False
            if pull(relay, repair=repair):
                return
        except (OSError, ConnectionError, ValueError) as error:
            if install and isinstance(error, ValueError):
                write(HERE/'LOCAL_RELAY_STATE.json', dict(status='STOP', error=str(error)))
                raise
            write(HERE/'LOCAL_RELAY_STATE.json', dict(status='RECONNECTING', error=str(error)))
        time.sleep(20)
    write(HERE/'LOCAL_RELAY_STATE.json', dict(status='STOP', error='RETRIEVAL_DEADLINE'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'upload', 'install', 'status', 'watch', 'install-watch'))
    parser.add_argument('--repair-183971', action='store_true')
    args = parser.parse_args()
    repair = args.repair_183971
    if args.action == 'prepare':
        prepare(repair)
    elif args.action == 'upload':
        upload()
    elif args.action in ('watch', 'install-watch'):
        watch(repair=repair, install=args.action=='install-watch')
    else:
        relay = experiment(send=args.action=='install', repair=repair)
        pull(relay, repair=repair)
        status = json.loads((HERE/'LOCAL_PROGRESS.json').read_text(encoding='utf-8'))
        print(json.dumps({k:status[k] for k in ('install','chain','progress')}, ensure_ascii=True))
