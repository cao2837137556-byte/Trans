"""Explicit fixed-package deployment actions over the existing SSH tunnel."""
import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import time
import zlib

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
PRIVATE = HERE / '.private'
REMOTE = '/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_deployment_20261027'
ARCHIVE = PACKAGE / 'distribution/r2/dense_reference_matrix_v1_20261027.tar.gz'
ARCHIVE_SHA = '43c31bd5ba3dc169aa95fae0079f2b856801043c46fd7862736110cb603b0140'
SIZE = 115876260
sys.path.insert(0, str(PACKAGE / 'src'))
sys.path.insert(0, str(PACKAGE / 'hpc'))
from common import read, require, sha, write
from status_sync import Connection, existing_port


def prepare():
    require(not (PRIVATE / 'client.json').exists(), 'ALREADY_PREPARED_PRESERVE')
    port = existing_port()
    require(port is not None, 'EXISTING_SSH_TUNNEL_REQUIRED')
    require(ARCHIVE.stat().st_size == SIZE and sha(ARCHIVE) == ARCHIVE_SHA, 'LOCAL_ARCHIVE_IDENTITY')
    config = dict(schema='paper04-dense-deploy-bootstrap-v1', token=secrets.token_hex(32),
                  status_token=secrets.token_hex(32), approval=read(HERE / 'APPROVED.json'))
    PRIVATE.mkdir(exist_ok=True)
    write(PRIVATE / 'client.json', dict(config, remote_port=18781, socks_port=port))
    source = '\n'.join([
        'import os,subprocess', 'from pathlib import Path',
        'p=Path(' + repr(REMOTE) + ')', 'p.mkdir(mode=0o700,parents=True,exist_ok=False)',
        '(p/".bootstrap.json").write_text(' + repr(json.dumps(config)) + ',encoding="utf-8")',
        '(p/".bootstrap.json").chmod(0o600)',
        '(p/"deploy_bridge.py").write_text(' + repr((HERE / 'deploy_bridge.py').read_text(encoding='utf-8')) + ',encoding="utf-8")',
        'log=(p/"bridge.log").open("ab")',
        'q=subprocess.Popen(["/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python","-B",str(p/"deploy_bridge.py")],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)',
        'print("PAPER04_DENSE_DEPLOY_BRIDGE_STARTED pid="+str(q.pid))',
    ])
    ast.parse(source)
    payload = base64.b64encode(zlib.compress(source.encode(), 9)).decode()
    command = "/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B -c " + "'import base64,zlib;exec(zlib.decompress(base64.b64decode(\"" + payload + "\")))'"
    (PRIVATE / 'bootstrap.command.sh').write_text(command, encoding='utf-8')
    write(HERE / 'PREPARED.json', dict(status='PREPARED_NOT_STARTED',
        archive_sha256=ARCHIVE_SHA, existing_socks_port=port, secrets_output=False))
    print('BOOTSTRAP_PREPARED_NO_TOKEN_OUTPUT')


def request(method, path, data=None, *, headers=None, timeout=30):
    config = read(PRIVATE / 'client.json')
    connection = Connection(config['remote_port'], config['socks_port'])
    def abort():
        try:
            if connection.sock is not None:
                connection.sock.shutdown(2)
        except OSError:
            pass
        connection.close()
    timer = threading.Timer(timeout, abort)
    timer.daemon = True
    timer.start()
    try:
        connection.connect()
        connection.sock.settimeout(timeout)
        values = dict(headers or {}, Authorization='Bearer ' + config['token'])
        connection.request(method, path, body=data, headers=values)
        response = connection.getresponse()
        payload = response.read(2*1024**2)
        require(response.status == 200, 'HTTP_' + str(response.status) + ':' + payload[:2000].decode(errors='replace'))
        return json.loads(payload)
    finally:
        timer.cancel()
        connection.close()


def upload():
    require(ARCHIVE.stat().st_size == SIZE and sha(ARCHIVE) == ARCHIVE_SHA, 'LOCAL_ARCHIVE_IDENTITY')
    remote = request('GET', '/status')
    write(HERE / 'BEFORE_UPLOAD.json', remote)
    # A fresh explicit upload only. If interrupted, preserve its last receipt;
    # inspect the exact server offset before an explicit, separately chosen resume.
    offset = remote.get('upload', {}).get('received_bytes', 0)
    require(offset == 0, 'NONZERO_UPLOAD_OFFSET_REQUIRES_RECONCILIATION')
    started = time.monotonic()
    with ARCHIVE.open('rb') as handle:
        while offset < SIZE:
            block = handle.read(4*1024**2)
            end = offset + len(block)
            result = request('PUT', '/archive', block,
                headers={'Content-Range': f'bytes {offset}-{end-1}/{SIZE}',
                         'X-Chunk-SHA256': hashlib.sha256(block).hexdigest()}, timeout=60)
            require(result.get('received_bytes') == end, 'REMOTE_UPLOAD_OFFSET')
            offset = end
            write(HERE / 'UPLOAD_PROGRESS.json', dict(result,
                elapsed_seconds=time.monotonic()-started, automatic_retry=False))
            print(f'UPLOAD {offset}/{SIZE} ({100*offset/SIZE:.1f}%)', flush=True)
    require(result.get('status') == 'UPLOADED_VERIFIED', 'REMOTE_ARCHIVE_NOT_VERIFIED')
    write(HERE / 'UPLOAD.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'inspect', 'upload', 'deploy', 'submit', 'monitor'))
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
        return
    if args.action == 'upload':
        upload()
        return
    if args.action == 'inspect':
        result = request('GET', '/status')
    else:
        result = request('POST', '/' + args.action, b'', timeout=180 if args.action == 'deploy' else 50)
    write(HERE / (args.action.upper() + '.json'), result)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
