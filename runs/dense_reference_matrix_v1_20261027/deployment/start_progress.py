"""Bind one verified submitted job to ordinary hidden progress programs."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path.insert(0, str(PACKAGE / 'src'))
sys.path.insert(0, str(PACKAGE / 'hpc'))
from common import read, require, write
from status_sync import fetch


def main():
    submitted = read(HERE / 'SUBMIT.json')
    monitor = read(HERE / 'MONITOR.json')
    require(submitted.get('status') == 'SUBMITTED' and
            monitor.get('status') == 'STATUS_BRIDGE_STARTED' and
            submitted['job_id'] == monitor['job_id'], 'VERIFIED_FIXED_JOB_REQUIRED')
    job = submitted['job_id']
    transport = read(HERE / '.private/client.json')
    config = dict(job_id=job, token=transport['status_token'], remote_port=monitor['port'],
                  socks_port=transport['socks_port'])
    private = PACKAGE / '.private'
    private.mkdir(exist_ok=True)
    config_path = private / ('status_job_' + job + '.json')
    require(not config_path.exists(), 'FRESH_STATUS_BINDING_REQUIRED')
    cache = PACKAGE / 'remote_progress' / ('job_' + job)
    require(not cache.exists(), 'FRESH_STATUS_CACHE_REQUIRED')
    # Process creation is not proof that a bridge is healthy. Verify its
    # authenticated exact-job endpoint before claiming a usable transport.
    bundle = fetch(config)
    write(config_path, config)
    write(cache / 'bundle.json', bundle)
    write(cache / 'sync.json', dict(status='OK', updated_epoch=time.time(),
        job_id=job, ai_polling=False, experiment_retry=False))
    probe = socket.socket()
    try:
        probe.bind(('127.0.0.1', 18770))
    finally:
        probe.close()
    pythonw = Path(sys.executable).with_name('pythonw.exe') if os.name == 'nt' else Path(sys.executable)
    require(pythonw.is_file(), 'HIDDEN_PYTHON_RUNTIME_REQUIRED')
    processes = {}
    for name, script, args in (
        ('sync', 'status_sync.py', ['--private-config', str(config_path), '--cache', str(cache)]),
        ('dashboard', 'progress_server.py', ['--cache', str(cache), '--port', '18770'])):
        with (cache / (name + '.stdout.log')).open('xb') as stdout, (cache / (name + '.stderr.log')).open('xb') as stderr:
            child = subprocess.Popen([str(pythonw), '-B', str(PACKAGE / 'hpc' / script)] + args,
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt')
            processes[name] = dict(pid=child.pid, command_script=script, hidden=True)
    write(HERE / 'LOCAL_PROCESSES.json', dict(job_id=job, processes=processes,
        created_utc=datetime.now(timezone.utc).isoformat(), cache=str(cache),
        url='http://127.0.0.1:18770/', ai_polling=False, secrets_output=False))
    view = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen('http://127.0.0.1:18770/status', timeout=3) as response:
                view = json.load(response)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1)
    require(view is not None and view.get('job_id') == job, 'LOCAL_PAGE_FIXED_JOB_MISMATCH')
    write(HERE / 'INITIAL_STATUS_VIEW.json', view)
    print(json.dumps(dict(status='PROGRESS_READY', job_id=job, url='http://127.0.0.1:18770/',
        remote_status=view['status'], label=view.get('label'), stage=view.get('stage'),
        scheduler=view.get('scheduler'), reason=view.get('reason')), ensure_ascii=True))


if __name__ == '__main__':
    main()
