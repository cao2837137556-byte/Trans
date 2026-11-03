"""Explicit repair of a failed, never-submitted preparation; no SSH login."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shlex
import zlib

import client
import pipeline

HERE = Path(__file__).resolve().parent
REMOTE = '/public/home/jiangxinwei.zr/work/paper04/runs/edge_linux_preflight_deployment_v1_20261103'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'


def build():
    delivery = client.read(HERE / 'DELIVERY.json')
    source = (HERE / 'remote_receiver.py').read_bytes()
    compile(source, 'remote_receiver.py', 'exec')
    old_sha = delivery['receiver_source_sha256']
    new_sha = hashlib.sha256(source).hexdigest()
    client.need(old_sha != new_sha, 'REPAIR_MUST_CHANGE_RECEIVER')
    public_binding = dict(files={k: {n: v[n] for n in ('filename', 'bytes', 'sha256')}
                                 for k, v in delivery['files'].items()},
                          archive_manifest_sha256=delivery['archive_manifest_sha256'])
    # The command contains source and public pins only. It reads the already
    # installed private configuration on the remote host without printing it.
    bootstrap = '''import base64,hashlib,http.client,json,os,pathlib,shutil,signal,subprocess,sys,time,zlib
os.umask(0o077)
here=pathlib.Path(REMOTE_PATH)
source=zlib.decompress(base64.b64decode(SOURCE_B64))
old_sha=OLD_SHA
new_sha=NEW_SHA
binding=PUBLIC_BINDING
def need(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
need(hashlib.sha256(source).hexdigest()==new_sha,'REPAIR_SOURCE_PIN')
compile(source,'remote_receiver.py','exec')
need(here.is_dir(),'EXISTING_DEPLOYMENT_REQUIRED')
config=load(here/'.receiver_private.json')
need({k:config[k] for k in binding}==binding,'EXISTING_CONFIG_PIN')
need(load(here/'DELIVERY_BINDING.json')==binding,'EXISTING_BINDING_PIN')
for name in ('SUBMIT_ATTEMPT.json','SUBMIT_RECEIPT.json','SUBMIT_UNCERTAIN.json'):
    need(not (here/name).exists(),'NEVER_SUBMITTED_REQUIRED:'+name)
source_path=here/'remote_receiver.py'
need(sha(source_path)==old_sha,'OLD_RECEIVER_SOURCE_PIN')
pid=int((here/'RECEIVER_PID.txt').read_text().strip())
cmdline=pathlib.Path('/proc')/str(pid)/'cmdline'
need(cmdline.is_file(),'OLD_RECEIVER_PROCESS_REQUIRED')
args=cmdline.read_bytes()
need(str(source_path).encode() in args and str(here/'.receiver_private.json').encode() in args,'OLD_PROCESS_IDENTITY')
backup=here/'repair_history'/'prepare_tshark_environment_v1'
backup.mkdir(parents=True,exist_ok=False)
for name in ('remote_receiver.py','LAST_ERROR.json','PREPARE_STATUS.json','RECEIVER_PID.txt'):
    if (here/name).is_file():shutil.copy2(here/name,backup/name)
os.kill(pid,signal.SIGTERM)
for unused in range(100):
    stat=pathlib.Path('/proc')/str(pid)/'stat'
    if not stat.exists() or stat.read_text().split()[2]=='Z':break
    time.sleep(.1)
else:raise RuntimeError('OLD_RECEIVER_DID_NOT_EXIT')
temporary=here/'.repaired_receiver.tmp'
temporary.write_bytes(source)
temporary.replace(source_path)
need(sha(source_path)==new_sha,'INSTALLED_SOURCE_PIN')
entry='import json,runpy;ns=runpy.run_path('+repr(str(source_path))+');ns["main"](json.load(open('+repr(str(here/'.receiver_private.json'))+')))'
with (here/'receiver.log').open('ab',buffering=0) as log:
    process=subprocess.Popen([sys.executable,'-u','-B','-c',entry],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
(here/'RECEIVER_PID.txt').write_text(str(process.pid)+'\\n')
state=None
for unused in range(100):
    try:
        connection=http.client.HTTPConnection('127.0.0.1',18817,timeout=1)
        connection.request('GET','/'+config['token']+'/state')
        response=connection.getresponse()
        need(response.status==200,'REPAIR_HTTP_STATE')
        state=json.loads(response.read())
        connection.close()
        need(state.get('receiver_source_sha256')==new_sha,'LOADED_RECEIVER_SOURCE_PIN')
        break
    except Exception:
        if process.poll() is not None:raise RuntimeError('REPAIRED_RECEIVER_EXITED') from None
        time.sleep(.1)
else:raise RuntimeError('REPAIRED_RECEIVER_NOT_READY')
need(state.get('job') is None and all(v['complete'] for v in state['files'].values()),'REPAIR_INPUTS_AND_NO_JOB')
receipt=dict(status='RECEIVER_REPAIRED_NOT_SUBMITTED',old_receiver_sha256=old_sha,new_receiver_sha256=new_sha,previous_pid=pid,new_pid=process.pid,all_inputs_preserved=True,job=None,formal_external_evaluation=False)
(here/'REPAIR_INSTALL_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\\n')
print('EDGE_PREFLIGHT_RECEIVER_REPAIR_READY '+new_sha,flush=True)
'''
    values = dict(REMOTE_PATH=repr(REMOTE), SOURCE_B64=repr(base64.b64encode(zlib.compress(source, 9)).decode()),
                  OLD_SHA=repr(old_sha), NEW_SHA=repr(new_sha), PUBLIC_BINDING=repr(public_binding))
    for key, value in values.items():
        bootstrap = bootstrap.replace(key, value)
    compile(bootstrap, 'repair_bootstrap', 'exec')
    packed = base64.b64encode(zlib.compress(bootstrap.encode(), 9)).decode()
    code = "import base64,zlib;exec(zlib.decompress(base64.b64decode('" + packed + "')))"
    command = PYTHON + ' -B -c ' + shlex.quote(code)
    (HERE / 'RUN_REPAIR_IN_HPC_TERMINAL.txt').write_text(command+'\n', encoding='utf-8')
    plan = dict(status='PREPARE_REPAIR_READY_NOT_SUBMITTED',
                old_receiver_sha256=old_sha, new_receiver_sha256=new_sha,
                remote_directory=REMOTE, existing_inputs_preserved=True,
                frozen_package_changed=False, authorized_jobs_max=1,
                wall_seconds=600, formal_external_evaluation=False,
                bootstrap_sha256=hashlib.sha256(command.encode()+b'\n').hexdigest())
    client.write(HERE / 'PREPARE_REPAIR_PLAN.json', plan)
    print(json.dumps(plan))


def allow_local_resume(*, folder=HERE, action=client.request):
    folder = Path(folder)
    plan = client.read(folder / 'PREPARE_REPAIR_PLAN.json')
    client.need(client.sha(folder / 'remote_receiver.py') == plan['new_receiver_sha256'],
                'LOCAL_REPAIR_SOURCE_CHANGED')
    state = action('state')
    client.need(state.get('receiver_source_sha256') == plan['new_receiver_sha256'],
                'REPAIR_NOT_LOADED_REMOTELY')
    client.need(not state.get('job') and state.get('status') == 'READY_TO_UPLOAD'
                and not state.get('last_error'), 'REMOTE_UNSUBMITTED_CLEAN_STATE_REQUIRED')
    for key, spec in client.read(folder / 'DELIVERY.json')['files'].items():
        client.need(client.remote_file(state, key, spec)['complete'], 'EXISTING_COMPLETE_INPUT:' + key)
    for name in ('SUBMIT_ATTEMPT.json', 'SUBMIT_RECEIPT.json', 'SUBMIT_UNCERTAIN.json'):
        client.need(not (folder / name).exists(), 'NO_LOCAL_SUBMISSION_ALLOWED_FOR_PREPARE_REPAIR:' + name)
    backup = folder / 'repair_history' / 'prepare_tshark_environment_v1'
    backup.mkdir(parents=True, exist_ok=False)
    # Move, rather than discard, the old intent. The repair is a new explicit
    # user-requested attempt after confirmed failure, never an automatic retry.
    for name in ('PREPARE_ATTEMPT.json', 'PIPELINE_FAILURE.json', 'PROGRESS.json'):
        path = folder / name
        if path.exists():
            path.replace(backup / name)
    receipt = dict(status='EXPLICIT_PREPARE_RESUME_AUTHORIZED',
                   observed_utc=client.utc(), receiver_source_sha256=plan['new_receiver_sha256'],
                   previous_intent_preserved=True, input_upload_repeated=False,
                   known_job_before_resume=None, formal_external_evaluation=False)
    client.write(folder / 'REPAIR_RESUME_RECEIPT.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('build', 'resume'))
    args = parser.parse_args()
    if args.mode == 'build':
        build()
    else:
        allow_local_resume()
        raise SystemExit(pipeline.run(0, 1800, 20))
