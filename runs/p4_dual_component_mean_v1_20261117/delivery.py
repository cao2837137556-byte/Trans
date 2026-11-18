"""Use the established Windows SSH SOCKS listener and the dedicated experiment receiver."""
from hashlib import sha256
import hmac
import http.client
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from reports import headline, paper_text, require

HERE = Path(__file__).resolve().parent
RUN = HERE.name
OLD = HERE.parent/'unified_reference_bank_k8192_v1_20261113'
PRIVATE = HERE/'.private'
sys.path.append(str(OLD))
from motion_transfer import get_client, PROJECT, PYTHON

PORT = 18896
TAG = '.p04_dual17'
OLD_STAGE = '.p04_q12_20261115_relay'


def read(path):
    return json.loads(path.read_bytes())


def save(path, data):
    tmp = path.with_suffix('.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    os.replace(tmp,path)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def config():
    previous_key = read(OLD/'.private/Q12_CONNECTION.json')['token'].encode()
    return dict(port=PORT, token=hmac.digest(previous_key,RUN.encode(),'sha256').hex())


def start_command():
    # Launch a fresh instance of the installed transport in its own stage, with a distinct run token.
    # The old service remains bound to its two original runs.
    pin = sha256((OLD/'q12_recovery_relay.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    code = ('from pathlib import Path as P; import sys,hmac,relay as r; '
            f'n="{RUN}"; d=P(sys.argv[1]); '
            f'(d/"token").write_text(hmac.digest((P("{OLD_STAGE}")/"token").read_bytes().strip(),n.encode(),"sha256").hex()); '
            'r.RUNS={"dual":n}; r.main()')
    return (f'cd {PROJECT}/runs && umask 077 && mkdir -p {TAG} && '
            f'echo "{pin}  {OLD_STAGE}/relay.py" | sha256sum -c --status && '
            f'PYTHONPATH={OLD_STAGE} nohup flock -n {TAG}/lock {PYTHON} -B -c {shlex.quote(code)} '
            f'{TAG} {PORT} </dev/null >>{TAG}/relay.log 2>&1 &')


def state(stage, **info):
    save(HERE/'LOCAL_PROGRESS.json', dict(stage=stage,updated_unix=time.time(),**info))


def receive(channel, remote, manifest):
    dest = HERE/'received'
    dest.mkdir(exist_ok=True)
    allowed = {'INSTALL.json','PREFLIGHT.json','SCIENCE.json','ACCEPTANCE.json','ARTIFACTS.json',
               'METRICS.csv','METRICS.json','PAIRED.csv','PAIRED.json','HEADLINE.csv','HEADLINE.json',
               'RESULTS_FOR_PAPER.md','CONTROLLER_FAILURE.json'}
    for p in ('preflight','formal'):
        for prefix in ('INPUTS','RUNTIME','RESOURCES','SUBMIT_INTENT','SBATCH','TEST_ONLY','JOB','SCHEDULER','FAILURE','SLURM_STOP'):
            allowed.add(prefix+'_'+p+'.json')
    files = manifest['files']
    require(bool(files) and set(files) <= allowed, 'SMALL_RESULT_ALLOWLIST')
    for n,spec in files.items():
        require(spec['file'] == n and 0 <= spec['bytes'] <= 32*1024**2, 'PULLBACK_ENTRY')
        path = dest/n
        if not path.exists() or path.stat().st_size != spec['bytes'] or digest(path) != spec['sha256']:
            channel.request('file-dual-'+n, destination=(path,spec),timeout=90)
        require(digest(path) == spec['sha256'], 'LOCAL_RETURN_SHA:' + n)
    save(dest/'RETURN.json',manifest)
    if remote['chain']['stage'] == 'STOP':
        state('STOP',remote=remote,local_files=len(files))
        return
    accepted = read(dest/'ACCEPTANCE.json')
    require(accepted == remote['acceptance'] and accepted['status'] == 'PASS'
            and accepted['queries'] == 388202 and accepted['subset_violations'] == 0
            and accepted['original_weak_metric_rows'] == 736 and
            accepted['package_sha256'] == digest(HERE/'PACKAGE_MANIFEST.json'), 'LOCAL_ACCEPTANCE_IDENTITY')
    science = read(dest/'SCIENCE.json')
    require(accepted['science'] == files['SCIENCE.json'] and
            all(files.get(n) == v for n,v in science['outputs'].items()), 'SCIENCE_AND_RETURN_SHA')
    for phase, job in accepted['jobs'].items():
        sched = read(dest/f'SCHEDULER_{phase}.json')
        require(sched['state'] == 'COMPLETED' and sched['job_id'] == job and
                any(line.split('|')[:3] == [job,'COMPLETED','0:0'] for line in sched['account']['stdout'].splitlines()),
                'LOCAL_SLURM_RECEIPT')
    pairs = read(dest/'PAIRED.json')
    heads = headline(read(dest/'METRICS.json'),pairs)
    jobs = accepted['jobs']
    require(heads == read(dest/'HEADLINE.json') and paper_text(heads,jobs['preflight'],jobs['formal'],pairs) ==
            (dest/'RESULTS_FOR_PAPER.md').read_text(encoding='utf-8'), 'LOCAL_PAIRED_AND_TEXT_RECOUNT')
    save(dest/'LOCAL_ACCEPTANCE.json',dict(status='PASS',jobs=jobs,files=len(files),return_sha256=digest(dest/'RETURN.json'),
         package_sha256=accepted['package_sha256'], queries=accepted['queries'], independent_paired_recount=True))
    try:
        from archive_run import publish
        backup=dict(status='PUSHED',commit=publish('results'))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        backup=dict(status='PENDING',error=str(error))
    save(dest/'BACKUP_STATUS.json',backup)
    state('ACCEPTED',remote=remote,local_files=len(files),headline=heads,backup=backup)


def watch():
    api = get_client()
    configuration = config()
    connect = api.transport()
    package = PRIVATE/'package.tar.gz'
    pin = digest(package)
    package_manifest = digest(HERE/'PACKAGE_MANIFEST.json')
    cached_port = None
    last = None
    installed = False
    state('STARTING_CLIENT')
    while True:
        try:
            ports = [cached_port] if cached_port is not None else api.ssh_socks_ports()
            channel = None
            for port in ports:
                candidate = api.Relay(configuration,port,connect)
                try:
                    remote = candidate.request('state-dual',timeout=8)
                except (OSError,http.client.HTTPException):
                    continue
                channel, cached_port = candidate, port
                break
            if channel is None:
                if not installed:
                    state('WAITING_TERMINAL' if ports else 'WAITING_SSH',ssh_ports=ports)
                else:
                    state('CONNECTION_PAUSED',remote=last)
                cached_port = None
                time.sleep(10)
                continue
            if not remote.get('install'):
                state('UPLOADING',bytes=package.stat().st_size)
                reply = channel.request('install-dual','POST',package.read_bytes(),{'X-SHA256':pin},timeout=90)
                require(reply['run'] == RUN and reply['archive_sha256'] == pin and
                        reply['manifest_sha256'] == package_manifest, 'INSTALL_RECEIPT')
                save(HERE/'INSTALL_READBACK.json',reply)
                remote = channel.request('state-dual')
            install = remote['install']
            require(install['run'] == RUN and install['manifest_sha256'] == package_manifest and
                    install['archive_sha256'] == pin,'REMOTE_EXPERIMENT_IDENTITY')
            installed, last = True, remote
            if not (HERE/'INSTALL_READBACK.json').is_file():
                save(HERE/'INSTALL_READBACK.json',install)
            chain = remote.get('chain') or {}
            stage = chain.get('stage','INSTALLED')
            state(stage, remote=remote)
            if stage in ('COMPLETE','STOP'):
                manifest = channel.request('manifest-dual')
                if manifest is not None:
                    state('VERIFYING_RETURN', remote=remote)
                    receive(channel,remote,manifest)
                    return
            time.sleep(10)
        except (OSError,http.client.HTTPException,subprocess.TimeoutExpired):
            cached_port = None
            state('CONNECTION_PAUSED' if installed else 'WAITING_TERMINAL',remote=last)
            time.sleep(10)


if __name__ == '__main__':
    if sys.argv[1:] == ['command']:
        PRIVATE.mkdir(exist_ok=True)
        (PRIVATE/'START.txt').write_text(start_command()+'\n',encoding='ascii')
    else:
        try:
            watch()
        except Exception as e:
            state('LOCAL_STOP', error=str(e))
            raise
