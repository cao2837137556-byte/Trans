"""Deploy one bounded source-only diagnostic; never restart an experiment."""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ALIAS = 'paper04-coupon-20261020'
REMOTE = '/srv/paper04/learned_onboarding_memory_validation_20261024_v4'
UNIT = 'paper04-onboarding-memory-validation-20261024-v4'
CREATE = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def ssh(code, timeout=45):
    payload = base64.b64encode(code.encode()).decode()
    command = '/opt/paper04-venv/bin/python -c "import base64;exec(base64.b64decode(\''+payload+'\'))"'
    result = subprocess.run(['ssh', '-nT', '-oBatchMode=yes', '-oConnectTimeout=8', ALIAS, command],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout, creationflags=CREATE)
    assert result.returncode == 0, result.stderr+'\n'+result.stdout
    return json.loads(result.stdout)


def main():
    receipt_path = HERE/'REMOTE_VALIDATION_LAUNCH.json'
    assert not receipt_path.exists(), 'DIAGNOSTIC_ALREADY_SUBMITTED_NO_AUTOMATIC_RETRY'
    package = json.loads((HERE/'PACKAGE_RECEIPT.json').read_text())
    remote_zip = '/srv/paper04/memory_validation_v4_'+package['archive_sha256'][:12]+'.zip'
    precheck = ssh("""import pathlib,psutil,subprocess,json,shutil
root=pathlib.Path('"""+REMOTE+"""')
assert not root.exists(),'DIAGNOSTIC_ROOT_ALREADY_EXISTS'
assert not pathlib.Path('"""+remote_zip+"""').exists(),'DIAGNOSTIC_UPLOAD_ALREADY_EXISTS'
q=subprocess.run(['systemctl','list-units','--state=running','--type=service','--no-legend','--no-pager','paper04-*'],capture_output=True,text=True,check=True)
assert not q.stdout.strip(),'EXPERIMENT_OR_DIAGNOSTIC_SLOT_BUSY'
assert psutil.virtual_memory().available>16*1024**3,'MEMORY_SLOT_NOT_READY'
assert shutil.disk_usage('/srv/paper04').free>6*1024**3,'DISK_SLOT_NOT_READY'
print(json.dumps({'status':'SOURCE_DIAGNOSTIC_SLOT_READY','memory_available':psutil.virtual_memory().available,'active_units':q.stdout,'original_experiment_restarted':False}))
""")
    upload = subprocess.run(['scp', '-q', '-oBatchMode=yes', '-oConnectTimeout=8',
        str(HERE/'memory_validation_v4.zip'), ALIAS+':'+remote_zip],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=90, creationflags=CREATE)
    assert upload.returncode == 0, upload.stderr
    launcher = '''import json,os,pathlib,subprocess,sys
here=pathlib.Path(__file__).resolve().parent
root=here/'staging'
package=root/'runs/learned_onboarding_v1_20261023'
command=[sys.executable,'-B',str(package/'deployment_20261024/run_stage.py'),'--root',str(root),'--config',str(package/'deployment_20261024/remote_config.json'),'--state',str(here/'test_state'),'--source-assets',str(here/'source_assets_not_used'),'--stage','tests']
with (here/'tests.log').open('xb') as stream:
 result=subprocess.run(command,cwd=root,stdout=stream,stderr=subprocess.STDOUT)
if result.returncode:raise SystemExit(result.returncode)
result=subprocess.run([sys.executable,'-B',str(here/'validate_memory_source.py')],cwd=here)
raise SystemExit(result.returncode)
'''
    code = """import pathlib,zipfile,hashlib,json,subprocess,datetime
root=pathlib.Path('"""+REMOTE+"""'); archive=pathlib.Path('"""+remote_zip+"""')
assert not root.exists(),'DIAGNOSTIC_ROOT_ALREADY_EXISTS'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='"""+package['archive_sha256']+"""','UPLOAD_SHA256'
q=subprocess.run(['systemctl','list-units','--state=running','--type=service','--no-legend','--no-pager','paper04-*'],capture_output=True,text=True,check=True)
assert not q.stdout.strip(),'SLOT_BECAME_BUSY'
root.mkdir()
with zipfile.ZipFile(archive) as bundle:
 for name in bundle.namelist():
  target=(root/name).resolve()
  assert root in target.parents,'ARCHIVE_PATH_ESCAPE'
 bundle.extractall(root)
(root/'run_validation.py').write_text("""+repr(launcher)+""",encoding='utf-8')
unit='"""+UNIT+"""'
command=['systemd-run','--unit='+unit,'--description=Paper04 source-only memory repair validation V4','--property=Type=exec','--property=Restart=no','--property=KillMode=control-group','--property=MemoryAccounting=yes','--property=MemoryMax=16G','--property=MemorySwapMax=0','--property=CPUQuota=800%','--property=RuntimeMaxSec=3900','--property=WorkingDirectory='+str(root),'--property=StandardOutput=append:'+str(root/'service.stdout.log'),'--property=StandardError=append:'+str(root/'service.stderr.log')]
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):command+=['--setenv='+key+'=4']
command+=['--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=PYTHONUNBUFFERED=1','/opt/paper04-venv/bin/python','-B',str(root/'run_validation.py')]
p=subprocess.run(command,capture_output=True,text=True)
assert p.returncode==0,p.stderr
print(json.dumps({'status':'SOURCE_VALIDATION_SUBMITTED','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root':str(root),'unit':unit,'command':command,'stdout':p.stdout,'stderr':p.stderr,'original_experiment_restarted':False,'production_optimizer_updates':0,'automatic_retry':False}))
"""
    submitted = ssh(code)
    receipt = dict(schema='paper04-memory-repair-diagnostic-launch-v4',
        recorded_at=datetime.now(timezone.utc).isoformat(), precheck=precheck,
        package=package, submitted=submitted, original_experiment_restarted=False)
    with receipt_path.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
