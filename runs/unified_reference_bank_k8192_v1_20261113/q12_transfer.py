"""Deliver the two independent run packages through the existing SSH tunnel."""
import argparse
import base64
import gzip
import json
from pathlib import Path
import secrets
import shlex
import time

from motion_transfer import HERE, PRIVATE, PROJECT, PYTHON, get_client, write
from q12_recovery_relay import RUNS, digest

CONNECTION = PRIVATE/'Q12_CONNECTION.json'


def prepare():
    if not CONNECTION.exists():
        write(CONNECTION,dict(port=18894,token=secrets.token_hex(32)))
    cfg = json.loads(CONNECTION.read_text())
    stage = shlex.quote(PROJECT+'/runs/.p04_q12_20261115_relay')
    token = shlex.quote(cfg['token'])
    source = (HERE/'q12_recovery_relay.py').read_bytes().replace(b'\r\n',b'\n')
    encoded = base64.b64encode(gzip.compress(source,mtime=0)).decode()
    cmd = (
        f'umask 077 && s={stage} && mkdir -p -- "$s" && '
        f'( set -C; printf "%s\\n" {token} > "$s/token" ) 2>/dev/null; '
        f's={stage} && test "$(cat "$s/token")" = {token} && '
        f'printf %s {encoded} | base64 -d | gzip -d > "$s/relay.py.tmp" && '
        'mv -- "$s/relay.py.tmp" "$s/relay.py" && '
        f'( nohup flock -n "$s/receiver.lock" {PYTHON} -B "$s/relay.py" "$s" {cfg["port"]} '
        '</dev/null >>"$s/relay.log" 2>&1 & ) # end')
    (PRIVATE/'Q12_START.txt').write_text(cmd,encoding='ascii')


def connection():
    cfg = json.loads(CONNECTION.read_text())
    c = get_client()
    for port in c.ssh_socks_ports():
        relay = c.Relay(cfg,port,c.transport())
        try:
            relay.request('state-uid',timeout=5)
            return relay
        except (OSError,ValueError,c.http.client.HTTPException):
            continue
    raise ConnectionError('EXISTING_Q12_RELAY_UNAVAILABLE')


def pull(relay, mode):
    target = HERE.parent/RUNS[mode]
    target.mkdir(exist_ok=True)
    status = relay.request('state-'+mode)
    manifest = relay.request('manifest-'+mode)
    if manifest:
        folder = target/'received'
        folder.mkdir(exist_ok=True)
        for name,pin in manifest['files'].items():
            if Path(name).name != name:
                raise ValueError('RESULT_FILE_SCOPE')
            path = folder/name
            if not path.is_file() or digest(path) != pin['sha256']:
                relay.request('file-'+mode+'-'+name,destination=(path,pin),timeout=60)
        write(folder/'RETURN.json',manifest)
        chain = status.get('chain') or {}
        if mode == 'heads' and chain.get('stage') == 'COMPLETE' and 'ACCEPTANCE.json' in manifest['files']:
            accepted = json.loads((folder/'ACCEPTANCE.json').read_text(encoding='utf-8'))
            count = accepted.get('method_configurations')
            if (accepted == status.get('acceptance') and accepted['status'] == 'PASS' and
                    accepted['job_id'] == chain.get('job_id') and type(count) is int and count > 1):
                progress = status.get('progress') or {}
                status['worker_progress'] = progress
                status['progress'] = dict(progress,stage='配置已验收',done=count,total=count,
                                          unit='configurations')
    write(target/'LOCAL_PROGRESS.json',status)
    return status, manifest is not None


def install(relay, mode):
    pkg = PRIVATE/(mode+'_package.tar.gz')
    receipt = relay.request('install-'+mode,'POST',pkg.read_bytes(),
        {'X-SHA256':digest(pkg)},timeout=80)
    if receipt['run'] != RUNS[mode] or receipt['archive_sha256'] != digest(pkg):
        raise ValueError('INSTALL_RECEIPT_MISMATCH')
    write(HERE.parent/RUNS[mode]/'INSTALL_READBACK.json',receipt)
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('prepare','probe','install','status','watch'))
    p.add_argument('mode', nargs='?',choices=tuple(RUNS))
    a = p.parse_args()
    if a.action == 'prepare':
        return prepare()
    if a.action == 'watch':
        end = time.monotonic()+72*3600
        while time.monotonic() < end:
            try:
                _,complete = pull(connection(),a.mode)
                if complete:
                    return
            except (OSError,ValueError) as e:
                write(HERE.parent/RUNS[a.mode]/'LOCAL_RELAY_STATE.json',dict(error=str(e)))
            time.sleep(20)
        return
    relay = connection()
    if a.action == 'probe':
        data = relay.request('probe',timeout=45)
        write(PRIVATE/'Q12_PROBE.json',data)
        print(json.dumps(data,ensure_ascii=True))
        return
    if a.action == 'install':
        print(json.dumps(install(relay,a.mode),ensure_ascii=True))
    status,_ = pull(relay,a.mode)
    print(json.dumps({k:status[k] for k in ('chain','progress','prep','replay')},ensure_ascii=True))


if __name__ == '__main__':
    main()
