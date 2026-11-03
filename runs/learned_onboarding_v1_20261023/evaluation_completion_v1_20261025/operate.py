"""Explicit local transport/launch actions. SSH is hidden and never retries jobs."""
import argparse
import base64
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
HOST = 'paper04-coupon-20261020'
NEW = '/srv/paper04/learned_onboarding_eval_20261025_v1'
PARENT = '/srv/paper04/learned_onboarding_20261024_v4'
PYTHON = '/opt/paper04-venv/bin/python'
UNIT = 'paper04-learned-onboarding-eval-20261025-v1'
OPS = HERE/'operations'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


def run(command, label, timeout=180):
    OPS.mkdir(exist_ok=True)
    at = datetime.now().astimezone()
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
        encoding='utf-8', timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    receipt = dict(at=at.isoformat(), ended_at=datetime.now().astimezone().isoformat(),
                   returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                   hidden_windows=True, automatic_retry=False)
    save(OPS/(label+'_'+at.strftime('%Y%m%d_%H%M%S_%f')+'.json'), receipt)
    if result.returncode:
        raise RuntimeError(label+' failed; no automatic retry: '+result.stderr[-1200:]+result.stdout[-1200:])
    return result.stdout


def ssh_code(code, label, timeout=180):
    encoded = base64.b64encode(code.encode()).decode()
    command = PYTHON+' -B -c '+shlex.quote("import base64;exec(base64.b64decode('"+encoded+"'))")
    return run(['ssh','-nT','-oBatchMode=yes','-oConnectTimeout=12',
                '-oServerAliveInterval=10','-oServerAliveCountMax=2',HOST,command], label, timeout)


def scp(paths, destination, label, timeout=300):
    return run(['scp','-q','-oBatchMode=yes','-oConnectTimeout=12',
                *[str(p) for p in paths],destination],label,timeout)


PREPARE = '''
import json,pathlib,psutil,subprocess,os,datetime
root=pathlib.Path('/srv/paper04/learned_onboarding_eval_20261025_v1')
parent=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
assert not root.exists(),'FRESH_EVALUATION_ROOT_REQUIRED'
active=subprocess.run(['systemctl','list-units','--all','--no-legend','--plain','--state=running,activating,deactivating','paper04-*'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
assert not active,'PAPER04_SLOT_BUSY:'+active
workers=[]
for p in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=p.info['cmdline'] or [];cmd=' '.join(args)
  reader='-c' in args and 'reference_forward' in cmd and 'modern_heads' in cmd
  if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower() and '/srv/paper04/' in cmd and not reader:workers.append(dict(pid=p.pid,command=cmd))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not workers,'PAPER04_WORKER_BUSY:'+repr(workers)
assert (parent/'state/EXCEPTION_STOP.json').is_file(),'PARENT_FAILURE_EVIDENCE_MISSING'
assert psutil.virtual_memory().available>=16*1024**3,'MEMORY_SLOT_NOT_READY'
assert psutil.disk_usage(parent).free>=12*1024**3,'DISK_SLOT_NOT_READY'
root.mkdir()
print(json.dumps(dict(status='FRESH_EVALUATION_ROOT_CREATED',root=str(root),at=datetime.datetime.now(datetime.timezone.utc).isoformat(),workers=workers,memory_available=psutil.virtual_memory().available,disk_free=psutil.disk_usage(root).free)))
'''


def prepare():
    print(ssh_code(PREPARE, 'PREPARE_REMOTE_ROOT'))
    scp([HERE/'run_evaluation.py'], HOST+':'+NEW+'/', 'UPLOAD_INSPECTOR')


def inspect():
    command = PYTHON+' -B '+NEW+'/run_evaluation.py --inspect-parent'
    raw = run(['ssh','-nT','-oBatchMode=yes','-oConnectTimeout=12',HOST,command], 'PARENT_INVENTORY', 240)
    inventory = json.loads(raw)
    save(HERE/'parent_inventory.json', inventory)
    print(json.dumps(dict(status='PARENT_INVENTORY_PINNED',files=len(inventory['files']),
                         parent_results_bytes=inventory['parent_results_bytes'])))


def build():
    spec = importlib.util.spec_from_file_location('eval_runner_ops', HERE/'run_evaluation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventory = json.loads((HERE/'parent_inventory.json').read_text())
    plan = module.budget_plan(inventory)
    save(HERE/'RESOURCE_PLAN.json', plan)
    contract = dict(schema='learned-onboarding-evaluation-completion-contract-v1',
        version='V4-EVAL1', root=NEW, parent_root=PARENT, unit=UNIT,
        spec_sha256=module.SPEC_SHA, user_authorization='Complete this experiment on the current server; start.',
        authorization_date='2026-10-25', automatic_retry=False, new_training_updates=0,
        fit_and_calibration_reused=True, calibration_recomputed=False, scientific_recipe_changed=False,
        parent_original_chain_remains_exception_stop=True,
        output_budget_scope='new evaluation results only; retained original V4 recorded as read-only inputs',
        original_failed_chain_output_limit_bytes=module.OUTPUT_LIMIT,
        retained_parent_results_bytes=inventory['parent_results_bytes'],
        output_limit_bytes=module.OUTPUT_LIMIT, rss_guard_bytes=module.RSS_LIMIT,
        environment_memory_ceiling_bytes=module.HARD_LIMIT, cpu_threads=4, cpu_quota=8, heavy_workers=1,
        chain_administrative_limit_seconds=24*3600,
        backup_transport_limit_bytes=256*1024**2,
        parent_inventory_sha256=sha(HERE/'parent_inventory.json'),
        expected_output_upper_bytes=plan['estimated_output_upper_bytes'])
    save(HERE/'contract.json', contract)
    files = ['run_evaluation.py','test_run_evaluation.py','contract.json','parent_inventory.json','RESOURCE_PLAN.json']
    save(HERE/'DEPLOYMENT_MANIFEST.json', dict(schema='learned-onboarding-evaluation-payload-v1',
        spec_sha256=module.SPEC_SHA, files={p:dict(bytes=(HERE/p).stat().st_size,sha256=sha(HERE/p)) for p in files}))
    print(json.dumps(dict(status='PAYLOAD_BUILT',manifest_sha256=sha(HERE/'DEPLOYMENT_MANIFEST.json'),plan=plan),indent=2))


def upload_test():
    manifest = json.loads((HERE/'DEPLOYMENT_MANIFEST.json').read_text())
    files = [HERE/name for name in manifest['files']]+[HERE/'DEPLOYMENT_MANIFEST.json']
    scp(files, HOST+':'+NEW+'/', 'UPLOAD_FINAL_PAYLOAD')
    code = "expected="+repr(sha(HERE/'DEPLOYMENT_MANIFEST.json'))+'\n'+'''
import pathlib,json,hashlib,subprocess,os,datetime
root=pathlib.Path('/srv/paper04/learned_onboarding_eval_20261025_v1')
assert not (root/'state').exists() and not (root/'results').exists(),'EXECUTION_ALREADY_ATTEMPTED'
assert hashlib.sha256((root/'DEPLOYMENT_MANIFEST.json').read_bytes()).hexdigest()==expected,'PAYLOAD_MANIFEST_SHA'
m=json.loads((root/'DEPLOYMENT_MANIFEST.json').read_text())
for name,item in m['files'].items():
 p=(root/name).resolve();assert root in p.parents and p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],name
environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
result=subprocess.run(['/opt/paper04-venv/bin/python','-B','-m','unittest','-v','test_run_evaluation'],cwd=str(root),env=environment,capture_output=True,text=True,timeout=90)
receipt=dict(status='PASS' if result.returncode==0 else 'FAIL',python_executable='/opt/paper04-venv/bin/python',manifest_sha256=expected,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,real_model_training_updates=0,real_target_queries_read=0)
with (root/'DEPLOYMENT_VERIFIED.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
assert result.returncode==0,'ACTUAL_PYTHON_TESTS_FAILED_NO_RETRY'
'''
    result = json.loads(ssh_code(code, 'ACTUAL_PYTHON_TESTS', 120))
    save(HERE/'ACTUAL_PYTHON_TESTS.json', result)
    print(json.dumps(result, indent=2))


def backup():
    assert shutil.disk_usage(HERE).free >= 1024**3, 'LOCAL_BACKUP_DISK_HEADROOM'
    raw = ssh_code('''
import pathlib,json,tarfile,hashlib,datetime
root=pathlib.Path('/srv/paper04/learned_onboarding_eval_20261025_v1')
old=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
inv=json.loads((root/'parent_inventory.json').read_text())
prefix='runs/learned_onboarding_v1_20261023/results/'
chosen={}
for name,item in inv['files'].items():
 rel=name[len(prefix):] if name.startswith(prefix) else ''
 if (rel.startswith('fit/') and (rel.endswith('/final.pt') or rel.endswith('/init.pt') or
     (rel.endswith('.json') and item['bytes']<=128*1024))) or rel.startswith('calibration/') or rel.endswith('/head.npz') or name in ('state/EXCEPTION_STOP.json','state/status.json','DEPLOYMENT_MANIFEST.json'):
  chosen[name]=item
assert sum(x['bytes'] for x in chosen.values())<=128*1024**2,'CRITICAL_BACKUP_BUDGET'
folder=root/'retained_v4_backup';folder.mkdir()
archive=folder/'sealed_models_and_calibration.tar.gz'
with tarfile.open(str(archive),'x:gz') as target:
 for name,item in sorted(chosen.items()):
  p=old/name
  assert p.is_file() and p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],name
  target.add(str(p),arcname=name,recursive=False)
assert archive.stat().st_size<=256*1024**2,'BACKUP_TRANSPORT_BUDGET'
h=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(1024**2),b''):h.update(block)
receipt=dict(status='BACKUP_READY',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),archive=str(archive),bytes=archive.stat().st_size,sha256=h.hexdigest(),members=chosen,independent_local_backup_not_yet_verified=True)
with (folder/'BACKUP_MANIFEST.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
''','MAKE_CRITICAL_MODEL_BACKUP',180)
    receipt=json.loads(raw)
    destination=HERE/'parent_backup'
    destination.mkdir()
    local=destination/'sealed_models_and_calibration.tar.gz'
    scp([HOST+':'+receipt['archive']],str(local),'DOWNLOAD_CRITICAL_MODEL_BACKUP',300)
    assert local.stat().st_size==receipt['bytes'] and sha(local)==receipt['sha256'],'BACKUP_ARCHIVE_SHA'
    with tarfile.open(local,'r:gz') as archive:
        members=archive.getmembers()
        assert len(members)==len(receipt['members']) and {x.name for x in members}==set(receipt['members'])
        for item in members:
            assert item.isfile()
            stream=archive.extractfile(item)
            h=hashlib.sha256()
            for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
            assert item.size==receipt['members'][item.name]['bytes'] and h.hexdigest()==receipt['members'][item.name]['sha256']
    receipt.update(status='LOCAL_CRITICAL_BACKUP_VERIFIED',local_path=str(local),
                   independent_local_backup_not_yet_verified=False,all_member_sha256_verified=True)
    save(destination/'BACKUP_MANIFEST.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','bytes','sha256','local_path')},indent=2))


def launch():
    code='expected='+repr(sha(HERE/'DEPLOYMENT_MANIFEST.json'))+'\n'+'''
import pathlib,json,hashlib,subprocess,datetime,psutil,os
root=pathlib.Path('/srv/paper04/learned_onboarding_eval_20261025_v1');unit='paper04-learned-onboarding-eval-20261025-v1'
assert not (root/'state').exists() and not (root/'results').exists(),'FRESH_EXECUTION_REQUIRED'
verified=json.loads((root/'DEPLOYMENT_VERIFIED.json').read_text())
assert verified['status']=='PASS' and verified['manifest_sha256']==expected,'ACTUAL_PYTHON_TESTS_NOT_VERIFIED'
assert hashlib.sha256((root/'DEPLOYMENT_MANIFEST.json').read_bytes()).hexdigest()==expected,'PAYLOAD_SHA_CHANGED'
for name,item in json.loads((root/'DEPLOYMENT_MANIFEST.json').read_text())['files'].items():
 p=root/name;assert p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],name
active=subprocess.run(['systemctl','list-units','--all','--no-legend','--plain','--state=running,activating,deactivating','paper04-*'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
assert not active,'PAPER04_SLOT_BUSY:'+active
assert subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()=='not-found','UNIT_ALREADY_EXISTS_NO_RETRY'
workers=[]
for p in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=p.info['cmdline'] or [];cmd=' '.join(args)
  reader='-c' in args and 'reference_forward' in cmd and 'modern_heads' in cmd
  if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower() and '/srv/paper04/' in cmd and not reader:workers.append(dict(pid=p.pid,command=cmd))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not workers,'PAPER04_WORKER_BUSY:'+repr(workers)
assert psutil.virtual_memory().available>=16*1024**3 and psutil.disk_usage(root).free>=12*1024**3,'RESOURCE_SLOT_NOT_READY'
command=['systemd-run','--unit='+unit,'--description=Paper04 V4 sealed-input evaluation completion',
 '--property=Type=exec','--property=Restart=no','--property=KillMode=control-group',
 '--property=MemoryAccounting=yes','--property=MemoryMax=16G','--property=MemorySwapMax=0',
 '--property=CPUAccounting=yes','--property=CPUQuota=800%',
 '--property=ReadOnlyPaths=/srv/paper04','--property=ReadWritePaths='+str(root),
 '--property=WorkingDirectory='+str(root),'--property=StandardOutput=append:'+str(root/'service.stdout.log'),
 '--property=StandardError=append:'+str(root/'service.stderr.log')]
command+=['--setenv='+key+'=4' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]
command+=['--setenv=PYTHONUNBUFFERED=1','--setenv=PYTHONDONTWRITEBYTECODE=1',
 '/opt/paper04-venv/bin/python','-B','-u',str(root/'run_evaluation.py'),'--root',str(root),'--manifest-sha256',expected]
result=subprocess.run(command,capture_output=True,text=True,timeout=30)
receipt=dict(status='SERVICE_SUBMITTED' if result.returncode==0 else 'LAUNCH_EXCEPTION_STOP',unit=unit,
 at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command,returncode=result.returncode,
 stdout=result.stdout,stderr=result.stderr,automatic_retry=False,parent_root='/srv/paper04/learned_onboarding_20261024_v4')
with (root/'LAUNCH_RECEIPT.json').open('x') as f:json.dump(receipt,f,indent=2)
assert result.returncode==0,'SYSTEMD_LAUNCH_FAILED_NO_RETRY:'+result.stderr
query=subprocess.run(['systemctl','show',unit,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,ReadOnlyPaths,ReadWritePaths,Environment'],capture_output=True,text=True,check=True,timeout=10)
props=dict(line.split('=',1) for line in query.stdout.splitlines() if '=' in line)
assert props['MemoryMax']==str(16*1024**3) and props['MemorySwapMax']=='0' and props['CPUQuotaPerSecUSec']=='8s' and props['Restart']=='no' and props['KillMode']=='control-group','SYSTEMD_RESOURCE_POLICY'
assert '/srv/paper04' in props['ReadOnlyPaths'] and str(root) in props['ReadWritePaths'],'INPUT_READONLY_SANDBOX_MISSING'
limits=dict(status='PASS',properties=props,original_inputs_readonly=True)
with (root/'SERVICE_HARD_LIMIT_RECEIPT.json').open('x') as f:json.dump(limits,f,indent=2)
print(json.dumps(dict(launch=receipt,hard_limits=limits)))
'''
    result=json.loads(ssh_code(code,'LAUNCH',90))
    save(HERE/'EXECUTION_RECEIPT.json',result)
    print(json.dumps(result,indent=2))


def status():
    raw=ssh_code('''
import pathlib,json,subprocess,datetime
root=pathlib.Path('/srv/paper04/learned_onboarding_eval_20261025_v1')
def read(p):return json.loads(p.read_text()) if p.is_file() else None
names=['state/status.json','state/EXCEPTION_STOP.json','state/CHAIN_COMPLETE.json','state/resource_plan.json','state/stages/evaluation/worker.json','state/stages/evaluation/runtime.json','state/stages/evaluation/SOURCE_REUSE_VERIFIED.json','state/stages/evaluation/child_exception.json','state/stages/evaluation/process_exit.json']
q=subprocess.run(['systemctl','show','paper04-learned-onboarding-eval-20261025-v1','--property=LoadState,ActiveState,SubState,MainPID,Result,ExecMainStatus,InvocationID,NRestarts,MemoryCurrent,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,ReadOnlyPaths,ReadWritePaths'],capture_output=True,text=True,check=True,timeout=10)
out=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={n:read(root/n) for n in names},unit=dict(line.split('=',1) for line in q.stdout.splitlines() if '=' in line))
for name in ('service.stderr.log','state/stages/evaluation/output.log'):
 p=root/name
 out[name]=p.read_bytes()[-12000:].decode(errors='replace') if p.is_file() else None
print(json.dumps(out))
''','STARTUP_STATUS',45)
    value=json.loads(raw)
    save(OPS/('STARTUP_SNAPSHOT_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'),value)
    print(json.dumps(value,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','inspect','build','upload-test','backup','launch','status'))
    action=parser.parse_args().action
    globals()[action.replace('-','_')]()
