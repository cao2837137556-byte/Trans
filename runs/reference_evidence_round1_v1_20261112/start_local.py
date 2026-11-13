"""Start only this run's ordinary progress server and transfer client on Windows."""
from datetime import datetime, timezone
import http.client
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

from common_round1 import HERE, dump, load, require

PRIVATE = HERE / '.private'
URL = 'http://127.0.0.1:18807/'


def active(record, name):
    if not record:
        return False
    try:
        process = psutil.Process(record['pid'])
        args = process.cmdline()
        return (process.create_time() == record['create_time'] and
                any(Path(a).resolve() == HERE / name for a in args[1:] if a.endswith('.py')))
    except (OSError, psutil.Error):
        return False


def launch(name, previous):
    if active(previous, name):
        return previous
    with (PRIVATE / (name + '.log')).open('ab') as log:
        process = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(HERE / name)],
                                   cwd=HERE, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    return dict(pid=process.pid, create_time=psutil.Process(process.pid).create_time())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dashboard-only', action='store_true')
    args = parser.parse_args()
    require(os.name == 'nt' and (HERE / 'PACKAGE_RECEIPT.json').is_file(), 'LOCAL_PACKAGE_REQUIRED')
    processes = PRIVATE / 'LOCAL_PROCESSES.json'
    prev = load(processes) if processes.exists() else {}
    dashboard = launch('dashboard.py', prev.get('dashboard'))
    client = prev.get('client') if args.dashboard_only else launch('local_client.py', prev.get('client'))
    dump(processes, dict(dashboard=dashboard, client=client, started=datetime.now(timezone.utc).isoformat()))
    for _ in range(30):
        conn = http.client.HTTPConnection('127.0.0.1', 18807, timeout=2)
        try:
            conn.request('GET', '/')
            with conn.getresponse() as response:
                title = '正常参考补证首轮'
                require(response.status == 200 and title in response.read().decode('utf-8'), 'DASHBOARD_IDENTITY')
            conn.request('GET', '/state')
            with conn.getresponse() as response:
                state = json.loads(response.read())
                require(response.status == 200 and 'stage' in state, 'DASHBOARD_STATE')
            print('DASHBOARD_READY', URL, state['stage'])
            return
        except (OSError, http.client.HTTPException):
            time.sleep(.15)
        finally:
            conn.close()
    raise RuntimeError('ROUND1_DASHBOARD_NOT_REACHABLE')


if __name__ == '__main__':
    main()
