"""Deploy and launch the authorized independent V4 once; never resume or retry."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
OUT = HERE/'deployment_20261024'
OPS = OUT/'operations'
PACKAGE = 'runs/learned_onboarding_v1_20261023'
REMOTE = '/srv/paper04/learned_onboarding_20261024_v4'
UNIT = 'paper04-learned-onboarding-20261024-v4'
HOST = 'paper04-coupon-20261020'
CREATE = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def remote(code, receipt_name, timeout=60):
    payload = base64.b64encode(code.encode()).decode()
    command = '/opt/paper04-venv/bin/python -B -c "import base64;exec(base64.b64decode(\''+payload+'\'))"'
    result = subprocess.run(['ssh', '-nT', '-oBatchMode=yes', '-oConnectTimeout=8', HOST, command],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout, creationflags=CREATE)
    write(OPS/receipt_name, dict(returncode=result.returncode, stdout=result.stdout,
        stderr=result.stderr, checked_at=datetime.now(timezone.utc).isoformat()))
    assert result.returncode == 0, result.stderr+'\n'+result.stdout
    return json.loads(result.stdout)


PREFLIGHT_CODE = r'''import datetime,json,pathlib,psutil,subprocess
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
unit='paper04-learned-onboarding-20261024-v4'
assert not root.exists() and not pathlib.Path(str(root)+'.zip').exists(),'FRESH_V4_DESTINATION_REQUIRED'
active=subprocess.run(['systemctl','list-units','--all','--no-legend','--plain','--state=running,activating,deactivating','paper04-*'],capture_output=True,text=True,check=True).stdout.strip()
assert not active,'PAPER04_SLOT_BUSY:'+active
state=subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True)
assert state.stdout.strip()=='not-found','V4_UNIT_ALREADY_EXISTS'
workers=[]
for process in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=process.info['cmdline'] or [];command=' '.join(args)
  if 'python' not in (process.info['name'] or '').lower():continue
  reader='-c' in args and 'reference_forward' in command and 'modern_heads' in command
  if '/srv/paper04/' in command and not reader:workers.append(dict(pid=process.pid,command=command))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not workers,'PAPER04_WORKER_SLOT_BUSY:'+repr(workers)
memory=psutil.virtual_memory().available;disk=psutil.disk_usage('/srv/paper04').free
assert memory>=16*1024**3 and disk>=12*1024**3,'RESOURCE_SLOT_NOT_READY'
print(json.dumps(dict(status='EXCLUSIVE_EXISTING_INSTANCE_READY',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),active_units=active,workers=workers,memory_available=memory,disk_free=disk)))
'''


DEPLOY_CODE = r'''import datetime,hashlib,json,pathlib,subprocess,zipfile
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
archive=pathlib.Path(str(root)+'.zip')
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()
assert sha(archive)==__ARCHIVE_SHA__,'UPLOADED_ARCHIVE_SHA'
assert not root.exists(),'FRESH_V4_DESTINATION_REQUIRED'
with zipfile.ZipFile(archive) as bundle:
 names=bundle.namelist()
 assert len(names)==len(set(names)),'DUPLICATE_ZIP_MEMBER'
 for name in names:assert root in (root/name).resolve().parents,'ZIP_PATH_ESCAPE'
 root.mkdir();bundle.extractall(root)
manifest_path=root/'DEPLOYMENT_MANIFEST.json'
assert sha(manifest_path)==__MANIFEST_SHA__,'DEPLOYMENT_MANIFEST_SHA'
manifest=json.loads(manifest_path.read_text())
assert set(names)==set(manifest['files'])|{'DEPLOYMENT_MANIFEST.json'},'ZIP_CLOSURE'
for name,item in manifest['files'].items():
 path=root/name
 assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],name
assert sha(root/'MEMORY_RESOURCE_VALIDATION.json')==manifest['full_scale_memory_receipt_sha256'],'MEMORY_PROOF_SHA'
receipt=dict(status='DEPLOYED_VERIFIED_NOT_LAUNCHED',files=len(manifest['files']),archive_sha256=sha(archive),manifest_sha256=sha(manifest_path),at=datetime.datetime.now(datetime.timezone.utc).isoformat(),automatic_retry=False)
with (root/'DEPLOYMENT_VERIFIED.json').open('x') as stream:json.dump(receipt,stream,indent=2)
builder=root/'runs/learned_onboarding_v1_20261023/deployment_20261024/prepare_source_archive.py'
assembled=subprocess.run(['/opt/paper04-venv/bin/python','-B',str(builder),'--deployment-root',str(root)],capture_output=True,text=True,timeout=120)
assert assembled.returncode==0,assembled.stdout+assembled.stderr
receipt['source_archive']=json.loads(assembled.stdout)
assert receipt['source_archive']['target_query_files_opened']==0
print(json.dumps(receipt))
'''


LAUNCH_CODE = r'''import datetime,hashlib,json,pathlib,psutil,subprocess
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
package=root/'runs/learned_onboarding_v1_20261023';unit='paper04-learned-onboarding-20261024-v4'
assert not (root/'state').exists() and not (package/'results').exists(),'FRESH_OUTPUTS_REQUIRED'
assert (root/'DEPLOYMENT_VERIFIED.json').is_file(),'DEPLOYMENT_NOT_VERIFIED'
assert (root/'inputs/source_head_archive/BACKUP_INDEX.json').is_file(),'SOURCE_ARCHIVE_NOT_READY'
manifest=json.loads((root/'DEPLOYMENT_MANIFEST.json').read_text())
for name,item in manifest['files'].items():
 path=root/name
 assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'] and path.stat().st_size==item['bytes'],name
active=subprocess.run(['systemctl','list-units','--all','--no-legend','--plain','--state=running,activating,deactivating','paper04-*'],capture_output=True,text=True,check=True).stdout.strip()
assert not active,'PAPER04_SLOT_BECAME_BUSY:'+active
state=subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True)
assert state.stdout.strip()=='not-found','V4_UNIT_ALREADY_EXISTS'
workers=[]
for process in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=process.info['cmdline'] or [];command=' '.join(args)
  reader='-c' in args and 'reference_forward' in command and 'modern_heads' in command
  if 'python' in (process.info['name'] or '').lower() and '/srv/paper04/' in command and not reader:workers.append(dict(pid=process.pid,command=command))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not workers,'PAPER04_WORKER_SLOT_BUSY:'+repr(workers)
slot=dict(status='EXCLUSIVE_EXISTING_INSTANCE_READY',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),active_units=active,workers=workers,memory_available=psutil.virtual_memory().available,disk_free=psutil.disk_usage(root).free)
assert slot['memory_available']>=16*1024**3 and slot['disk_free']>=12*1024**3,'RESOURCE_SLOT_NOT_READY'
with (root/'EXECUTION_SLOT_RECEIPT.json').open('x') as stream:json.dump(slot,stream,indent=2)
command=['systemd-run','--unit='+unit,'--description=Paper04 learned onboarding V4 memory repair','--property=Type=exec','--property=Restart=no','--property=KillMode=control-group','--property=MemoryAccounting=yes','--property=MemoryMax=16G','--property=MemorySwapMax=0','--property=CPUAccounting=yes','--property=CPUQuota=800%','--property=WorkingDirectory='+str(root),'--property=StandardOutput=append:'+str(root/'service.stdout.log'),'--property=StandardError=append:'+str(root/'service.stderr.log')]
command+=['--setenv='+key+'=4' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]
command+=['--setenv=PYTHONUNBUFFERED=1','--setenv=PYTHONDONTWRITEBYTECODE=1','/opt/paper04-venv/bin/python','-u',str(package/'deployment_20261024/run_chain.py'),'--root',str(root),'--config',str(package/'deployment_20261024/remote_config.json'),'--state',str(root/'state'),'--source-assets',str(package/'results/source_assets')]
completed=subprocess.run(command,capture_output=True,text=True,timeout=30)
receipt=dict(status='SERVICE_SUBMITTED' if completed.returncode==0 else 'LAUNCH_EXCEPTION_STOP',unit=unit,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command,returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr,slot=slot,automatic_retry=False)
with (root/'LAUNCH_RECEIPT.json').open('x') as stream:json.dump(receipt,stream,indent=2)
assert completed.returncode==0,'SYSTEMD_LAUNCH_FAILED_NO_RETRY:'+completed.stderr
query=subprocess.run(['systemctl','show',unit,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,Environment'],capture_output=True,text=True,check=True,timeout=10)
properties=dict(line.split('=',1) for line in query.stdout.splitlines() if '=' in line)
assert properties['MemoryMax']==str(16*1024**3) and properties['MemorySwapMax']=='0','SYSTEMD_MEMORY_LIMIT'
assert properties['CPUQuotaPerSecUSec']=='8s' and properties['Restart']=='no' and properties['KillMode']=='control-group','SYSTEMD_RESOURCE_POLICY'
limits=dict(status='PASS',properties=properties)
with (root/'SERVICE_HARD_LIMIT_RECEIPT.json').open('x') as stream:json.dump(limits,stream,indent=2)
print(json.dumps(dict(launch=receipt,hard_limits=limits)))
'''


def main():
    assert sys.argv[1:] == ['--execute-user-authorized-v4'], 'EXPLICIT_V4_MODE_REQUIRED'
    assert not OPS.exists(), 'V4_ATTEMPT_ALREADY_EXISTS_NO_AUTOMATIC_RETRY'
    receipt = json.loads((OUT/'PACKAGE_RECEIPT.json').read_text(encoding='utf-8'))
    archive = OUT/'learned_onboarding_20261024_v4.zip'
    assert sha(archive) == receipt['archive_sha256'] and archive.stat().st_size == receipt['archive_bytes']
    manifest_path = OUT/'staging/DEPLOYMENT_MANIFEST.json'
    assert sha(manifest_path) == receipt['manifest_sha256']
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == set(manifest['files'])|{'DEPLOYMENT_MANIFEST.json'}
        assert bundle.read('DEPLOYMENT_MANIFEST.json') == manifest_path.read_bytes()
        for name, expected in manifest['files'].items():
            data = bundle.read(name)
            assert hashlib.sha256(data).hexdigest() == expected['sha256'] and len(data) == expected['bytes']
    OPS.mkdir()
    write(OPS/'USER_AUTHORIZATION.json', dict(instruction='\u53ef\u4ee5\u52a8\u624b\u8fd0\u884c\u3002',
        authorized_by='Current user message', at=datetime.now(timezone.utc).isoformat(),
        scope='One independent V4 deployment and full frozen chain using the validated memory repair',
        root=REMOTE, unit=UNIT, automatic_retry=False, prior_attempts_preserved=True))
    remote(PREFLIGHT_CODE, 'REMOTE_SLOT_CHECK.json')
    uploaded = subprocess.run(['scp', '-q', '-oBatchMode=yes', '-oConnectTimeout=8',
        str(archive), HOST+':'+REMOTE+'.zip'], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180, creationflags=CREATE)
    write(OPS/'UPLOAD_RECEIPT.json', dict(returncode=uploaded.returncode, stdout=uploaded.stdout,
        stderr=uploaded.stderr, archive_sha256=receipt['archive_sha256']))
    assert uploaded.returncode == 0, 'V4_UPLOAD_FAILED_NO_AUTOMATIC_RETRY:'+uploaded.stderr
    deploy = DEPLOY_CODE.replace('__ARCHIVE_SHA__', repr(receipt['archive_sha256'])).replace('__MANIFEST_SHA__', repr(receipt['manifest_sha256']))
    remote(deploy, 'REMOTE_DEPLOYMENT_VERIFIED.json', timeout=180)
    (OPS/'exact_remote_launch.py').write_text(LAUNCH_CODE, encoding='utf-8')
    launched = remote(LAUNCH_CODE, 'REMOTE_LAUNCH_RECEIPT.json', timeout=60)
    print(json.dumps(dict(status=launched['launch']['status'], root=REMOTE, unit=UNIT,
        started_at=launched['launch']['at'], invocation_id=launched['hard_limits']['properties']['InvocationID'],
        automatic_retry=False)))


if __name__ == '__main__':
    main()
