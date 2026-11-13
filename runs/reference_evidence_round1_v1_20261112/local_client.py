"""Resume through a user's existing tunnel and verify returned small artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time

from common_round1 import HERE, RUN, dump, load, require, sha, temp_path

PRIVATE = HERE / '.private'
LOCAL_STATE = HERE / 'LOCAL_PROGRESS.json'
MAX_FILE = 32 * 1024 ** 2


def state(stage, **data):
    dump(LOCAL_STATE, dict(stage=stage, updated_utc=datetime.now(timezone.utc).isoformat(), **data))


def ssh_socks_ports():
    # Only inspect user-started Windows SSH processes. Never launch ssh.exe.
    script = r"""
$items = @(Get-CimInstance Win32_Process -Filter "Name='ssh.exe'")
foreach ($item in $items) {
  foreach ($match in [regex]::Matches($item.CommandLine, '(?:^|\s)-D\s*"?((?:127\.0\.0\.1:|localhost:)?[0-9]+)"?(?:\s|$)')) {
    $port = [int](($match.Groups[1].Value -split ':')[-1])
    if (Get-NetTCPConnection -State Listen -LocalPort $port -OwningProcess $item.ProcessId -ErrorAction SilentlyContinue) {
      Write-Output $port
    }
  }
}
"""
    p = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                       capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    return list(dict.fromkeys(int(s) for s in p.stdout.splitlines() if s.strip().isdigit()))


def transport():
    path = HERE.parent / 'edge_linux_preflight_deployment_v1_20261103/client.py'
    spec = importlib.util.spec_from_file_location('paper04_existing_socks', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.connect


class Relay:
    def __init__(self, cfg, port, connect):
        self.cfg = cfg
        self.port = port
        self.connect = connect

    def request(self, action, method='GET', data=None, headers=None, destination=None, timeout=15):
        conn = http.client.HTTPConnection('127.0.0.1', self.cfg['port'], timeout=timeout)
        conn.sock = self.connect(dict(socks_port=self.port, remote_port=self.cfg['port']), timeout)
        try:
            conn.request(method, '/' + self.cfg['token'] + '/' + action, body=data, headers=headers or {})
            with conn.getresponse() as response:
                if response.status != 200:
                    operation = action.split('/')[0]
                    reason = response.reason or str(response.status)
                    if operation == 'upload' and reason == 'UPLOAD_OFFSET':
                        raise ConnectionError('RESYNCHRONIZE_UPLOAD_OFFSET')
                    raise ValueError('RELAY_ACTION_REJECTED:' + operation + ':' + reason)
                if destination is None:
                    payload = response.read(4 * 1024 ** 2 + 1)
                    require(len(payload) <= 4 * 1024 ** 2, 'RELAY_JSON_TOO_LARGE')
                    return json.loads(payload)
                path, pin = destination
                length = int(response.headers['Content-Length'])
                require(length == pin['bytes'] and length <= MAX_FILE, 'PULLBACK_LENGTH')
                tmp = temp_path(path)
                h = hashlib.sha256()
                n = 0
                with tmp.open('wb') as out:
                    while True:
                        block = response.read(256 * 1024)
                        if not block:
                            break
                        h.update(block)
                        n += len(block)
                        out.write(block)
                require(n == length and h.hexdigest() == pin['sha256'], 'PULLBACK_SHA:' + path.name)
                tmp.replace(path)
        finally:
            conn.close()


def discover(cfg, connect):
    ports = ssh_socks_ports()
    for port in ports:
        r = Relay(cfg, port, connect)
        try:
            remote = r.request('state', timeout=5)
            require(remote['remote_root'].endswith('/' + RUN) and remote['total_bytes'] == cfg['bytes'],
                    'RELAY_RUN_SCOPE')
            return r, remote, None
        except (OSError, ValueError, http.client.HTTPException):
            continue
    return None, None, 'WAITING_FOR_HPC_RELAY' if ports else 'WAITING_FOR_USER_SSH'


def transfer(relay, cfg, archive, remote):
    pos = remote['uploaded_bytes']
    require(type(pos) is int and 0 <= pos <= cfg['bytes'], 'RESUME_OFFSET')
    with archive.open('rb') as stream:
        stream.seek(pos)
        for chunk in iter(lambda: stream.read(512 * 1024), b''):
            state('UPLOADING', uploaded_bytes=pos, total_bytes=cfg['bytes'])
            r = relay.request('upload', method='POST', data=chunk,
                              headers={'X-Offset': str(pos), 'X-SHA256': hashlib.sha256(chunk).hexdigest()})
            require(r['bytes'] == pos + len(chunk), 'UPLOAD_RECEIPT')
            pos = r['bytes']
    require(pos == cfg['bytes'], 'UPLOAD_LENGTH')
    relay.request('install', method='POST', data=b'', timeout=90)


def receive(relay, remote):
    manifest = relay.request('manifest')
    dest = HERE / 'received'
    for name, spec in manifest['files'].items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and len(path.parts) <= 3 and
                all(re.fullmatch(r'[A-Za-z0-9_.-]+', part) for part in path.parts) and
                0 <= spec['bytes'] <= MAX_FILE, 'PULLBACK_PATH_OR_LIMIT')
        local = dest.joinpath(*path.parts)
        if not local.is_file() or local.stat().st_size != spec['bytes'] or sha(local) != spec['sha256']:
            relay.request('result/' + name, destination=(local, spec), timeout=90)
    dump(dest / 'PULLBACK_MANIFEST.json', manifest)
    r = manifest['files']
    accepted = 'FINAL_ACCEPTANCE.json' in r
    if accepted:
        verdict = load(dest / 'FINAL_ACCEPTANCE.json')
        require('RESULTS_FOR_PAPER.md' in r and verdict == remote['acceptance'], 'PULLBACK_ACCEPTANCE_IDENTITY')
    dump(dest / 'LOCAL_PULLBACK_VERIFICATION.json', dict(status='PASS', files=len(r),
         acceptance_present=accepted, manifest_sha256=sha(dest / 'PULLBACK_MANIFEST.json'),
         small_artifacts_only=True))


def run(max_wait):
    cfg = load(PRIVATE / 'connection.json')
    archive = PRIVATE / (RUN + '.tar.gz')
    require(archive.stat().st_size == cfg['bytes'] and sha(archive) == cfg['sha256'], 'LOCAL_ARCHIVE_SHA')
    connect = transport()
    until = time.monotonic() + max_wait
    relay = None
    previous = load(LOCAL_STATE) if LOCAL_STATE.is_file() else {}
    last = previous.get('remote') or previous.get('previous')
    installed = False
    stop_without_manifest_since = None
    while time.monotonic() < until:
        try:
            if relay is None:
                relay, remote, waiting = discover(cfg, connect)
                if relay is None:
                    state('CONNECTION_PAUSED' if installed else waiting, previous=last)
                    time.sleep(15)
                    continue
            else:
                remote = relay.request('state')
            last = remote
            if remote['stage'] == 'WAITING_UPLOAD' and not installed:
                transfer(relay, cfg, archive, remote)
                installed = True
                state('INSTALLING', remote=remote)
            else:
                installed = installed or bool(remote.get('dispatch'))
                stage = remote['stage']
                state(stage, remote=remote)
                if stage in ('ACCEPTED', 'PARTIAL_C0_FAILED', 'STOP'):
                    if remote['has_pullback']:
                        receive(relay, remote)
                        state(stage, remote=remote, local_pullback=True)
                        return
                    stop_without_manifest_since = stop_without_manifest_since or time.monotonic()
                    if (remote.get('error') == 'DISPATCH_PROCESS_EXITED_WITHOUT_COMPLETION' or
                            time.monotonic() - stop_without_manifest_since > 120):
                        state('LOCAL_CLIENT_STOP', previous=remote, error='REMOTE_TERMINAL_STATE_WITHOUT_PULLBACK')
                        return
            time.sleep(8)
        except (OSError, http.client.HTTPException, subprocess.TimeoutExpired):
            relay = None
            state('CONNECTION_PAUSED', previous=last)
            time.sleep(15)
        except ValueError as exc:
            state('LOCAL_CLIENT_STOP', error=str(exc), previous=last)
            raise
    state('LOCAL_CLIENT_WAIT_EXPIRED', previous=last)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-wait-seconds', type=int, default=172800)
    options = parser.parse_args()
    try:
        run(options.max_wait_seconds)
    except Exception as exc:
        previous = load(LOCAL_STATE) if LOCAL_STATE.is_file() else {}
        if previous.get('stage') != 'LOCAL_CLIENT_STOP':
            state('LOCAL_CLIENT_STOP', error=str(exc), previous=previous.get('remote'))
        raise
