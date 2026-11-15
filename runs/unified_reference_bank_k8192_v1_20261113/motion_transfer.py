"""Stage Motion on HPC and persist a resumable upload status locally."""
import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shlex
import time

from motion_ingress import (ARCHIVE_BYTES, ARCHIVE_SHA, FAILED_PREP_JOB, LIMIT, RAW_SHA, REPAIR_RUN,
                            RESUME_RUN, TIMEOUT_PREP_JOB, digest)

HERE = Path(__file__).resolve().parent
PRIVATE = HERE / '.private'
CFG = PRIVATE / 'MOTION_CONNECTION.json'
PROJECT = '/public/home/jiangxinwei.zr/work/paper04'
STAGE = PROJECT + '/runs/.' + HERE.name + '_motion_ingress'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'


def write(path, value):
    tmp = path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def config_path(repair, resume=False):
    if resume:
        return PRIVATE/'RESUME_183987_CONNECTION.json'
    return PRIVATE / ('REPAIR_CONNECTION.json' if repair else 'MOTION_CONNECTION.json')


def prepare(repair=False, resume=False):
    PRIVATE.mkdir(exist_ok=True)
    config = config_path(repair,resume)
    if not config.exists():
        write(config, dict(port=18891 if resume else 18889 if repair else 18888,
                           token=secrets.token_hex(32)))
    cfg = json.loads(config.read_text())
    job = TIMEOUT_PREP_JOB if resume else FAILED_PREP_JOB if repair else None
    stage = STAGE + ('_resume_' if resume else '_repair_')+job if job else STAGE
    suffix = f' --retry-prepare-job {job}' if job else ''
    source = (HERE/'motion_ingress.py').read_bytes().replace(b'\r\n',b'\n')
    script = base64.b64encode(gzip.compress(source,mtime=0)).decode()
    # Dedicated private staging dir; a second invocation keeps the same token and partial upload.
    command = (
        f'umask 077 && s={shlex.quote(stage)} && mkdir -p -- "$s" && '
        f'( set -C; printf "%s\\n" {shlex.quote(cfg["token"])} > "$s/token" ) 2>/dev/null; '
        f's={shlex.quote(stage)} && test "$(cat "$s/token")" = {shlex.quote(cfg["token"])} && '
        f'printf %s {shlex.quote(script)} | base64 -d | gzip -d > "$s/motion_ingress.py.tmp" && '
        'mv -- "$s/motion_ingress.py.tmp" "$s/motion_ingress.py" && '
        f'( nohup flock -n "$s/receiver.lock" {PYTHON} -B "$s/motion_ingress.py" '
        f'--stage "$s" --port {cfg["port"]}{suffix} </dev/null >>"$s/relay.log" 2>&1 & ) # end'
    )
    name = 'START_RESUME_183987.txt' if resume else 'START_REPAIR_INGRESS.txt' if repair else 'START_MOTION_INGRESS.txt'
    (PRIVATE/name).write_text(command,encoding='ascii')


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


def experiment(*, send, repair=False, resume=False):
    cfg = json.loads(config_path(repair,resume).read_text())
    expected_run = RESUME_RUN if resume else REPAIR_RUN if repair else None
    client = get_client()
    relay = None
    for port in client.ssh_socks_ports():
        channel = client.Relay(cfg, port, client.transport())
        try:
            remote = channel.request('state', timeout=5)
            if remote['scope']=='P04_K8192_MOTION_V1' and (expected_run is None or remote.get('run') == expected_run):
                relay = channel
                break
        except (OSError, ValueError, client.http.client.HTTPException):
            continue
    if relay is None:
        raise ConnectionError('EXISTING_RELAY_UNAVAILABLE')
    if send:
        path = PRIVATE/('package_resume_183987.tar.gz' if resume else 'package.tar.gz')
        manifest = HERE/('PACKAGE_MANIFEST_RESUME_183987.json' if resume else 'PACKAGE_MANIFEST.json')
        if not remote['complete']:
            raise ValueError('MOTION_UPLOAD_INCOMPLETE')
        data = path.read_bytes()
        if not 0 < len(data) <= LIMIT:
            raise ValueError('PACKAGE_SIZE')
        receipt = relay.request('install', 'POST', data,
                                {'X-SHA256': hashlib.sha256(data).hexdigest()}, timeout=60)
        if receipt['archive_sha256'] != digest(path) or receipt['package_manifest_sha256'] != digest(manifest):
            raise ValueError('INSTALL_RECEIPT_PACKAGE_PIN')
        name = 'INSTALL_RECEIPT_RESUME_183987.json' if resume else 'INSTALL_RECEIPT_REPAIR.json' if repair else 'INSTALL_RECEIPT.json'
        write(HERE/name, receipt)
    return relay


def publish(status,resume):
    if status['install'] is None:
        return
    if resume:
        write(HERE/'LOCAL_PROGRESS_RESUME_183987.json',status)
        stage = (status['chain'] or {}).get('stage')
        if stage in (None,'WAITING_FOR_VERIFIED_MOTION','WAITING_FOR_183987_TIMEOUT','PREDECESSOR_COMPLETED'):
            return
    write(HERE/'LOCAL_PROGRESS.json',status)


def pull(relay, repair=False,resume=False):
    status = relay.request('experiment')
    publish(status,resume)
    manifest = relay.request('results')
    if not manifest:
        return False
    folder = HERE/('received_resume_183987' if resume else 'received_repair_183971' if repair else 'received')
    folder.mkdir(exist_ok=True)
    for name, pin in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('RESULT_OUTSIDE_SCOPE')
        path = folder/name
        if not path.is_file() or digest(path) != pin['sha256']:
            relay.request('result-'+name, destination=(path,pin), timeout=60)
    write(folder/'RETURN.json', manifest)
    if resume:
        publish(dict(status,local_return_verified=True),resume=True)
    return True


def watch(repair=False, install=False,resume=False):
    # Ordinary file transfer/status process. It never submits a job or starts SSH.
    end = time.monotonic()+72*3600
    state_path = HERE/('LOCAL_RELAY_STATE_RESUME_183987.json' if resume else 'LOCAL_RELAY_STATE.json')
    while time.monotonic() < end:
        try:
            relay = experiment(send=install, repair=repair, resume=resume)
            install = False
            if pull(relay, repair=repair, resume=resume):
                return
        except (OSError, ConnectionError, ValueError) as error:
            if install and isinstance(error, ValueError):
                write(state_path, dict(status='STOP', error=str(error)))
                raise
            write(state_path, dict(status='RECONNECTING', error=str(error)))
        time.sleep(20)
    write(state_path, dict(status='STOP', error='RETRIEVAL_DEADLINE'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'upload', 'install', 'status', 'watch', 'install-watch'))
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--repair-183971', action='store_true')
    modes.add_argument('--resume-183987', action='store_true')
    args = parser.parse_args()
    repair,resume = args.repair_183971,args.resume_183987
    if args.action == 'prepare':
        prepare(repair,resume)
    elif args.action == 'upload':
        upload()
    elif args.action in ('watch', 'install-watch'):
        watch(repair=repair, install=args.action=='install-watch', resume=resume)
    else:
        relay = experiment(send=args.action=='install', repair=repair, resume=resume)
        pull(relay, repair=repair, resume=resume)
        name = 'LOCAL_PROGRESS_RESUME_183987.json' if resume else 'LOCAL_PROGRESS.json'
        status = json.loads((HERE/name).read_text(encoding='utf-8'))
        print(json.dumps({k:status[k] for k in ('install','chain','progress')}, ensure_ascii=True))
