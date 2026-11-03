"""Local WSL installer, fake scheduling and generated export evidence only."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.platform != 'linux':
        raise RuntimeError('LOCAL_LINUX_VALIDATION_REQUIRED')
    destination=HERE/'linux_clean_install'
    output=HERE/'linux_validation'
    output.mkdir(parents=True,exist_ok=True)
    if destination.exists() or (output/'result.json').exists():
        raise RuntimeError('VALIDATION_EXISTS_NO_OVERWRITE')
    archive=HERE/(HERE.name+'.tar.gz')
    commands={
        'install':[sys.executable,'-B',str(HERE/'modern_head_install_v1.py'),'install','--archive',str(archive),'--destination',str(destination)],
        'scheduler':[sys.executable,'-B',str(HERE/'test_delivery_linux.py'),'-v'],
        'export_phases':[sys.executable,'-B',str(HERE/'test_export_phases.py'),'-v']}
    env=dict(os.environ,MODERN_HEAD_TEST_BUNDLE=str(destination),PYTHONDONTWRITEBYTECODE='1')
    checks={}
    for name,command in commands.items():
        log=output/(name+'.log')
        with log.open('xb') as stream:
            completed=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,check=False)
        text=log.read_text()
        match=re.search(r'Ran (\d+) tests? in ',text)
        checks[name]={'exit_code':completed.returncode,'log':log.relative_to(HERE).as_posix(),'log_sha256':sha(log)}
        if match:
            checks[name]['tests_run']=int(match.group(1))
            checks[name]['skipped']=bool(re.search(r'OK \(skipped=',text))
        if completed.returncode:
            break
    counts_match=checks.get('scheduler',{}).get('tests_run')==37 and checks.get('export_phases',{}).get('tests_run')==3
    status='PASS' if len(checks)==3 and counts_match and all(v['exit_code']==0 and not v.get('skipped') for v in checks.values()) else 'FAIL'
    record={'status':status,'archive':archive.name,'archive_sha256':sha(archive),
            'python':sys.version,'platform':sys.platform,'checks':checks,'commands':commands,
            'real_experiment':False,'remote_access':False,'dependency_installation':False,
            'models_imported':False,'scheduler':'fake sbatch and Python only',
            'phase_export':'real stdlib exporter on generated tiny fixtures'}
    if (destination/'SHA256SUMS').is_file():
        record['package_seal_sha256']=sha(destination/'SHA256SUMS')
        record['installation_receipt_sha256']=sha(destination.with_name(destination.name+'.install_receipt.json'))
    with (output/'result.json').open('x') as stream:
        json.dump(record,stream,indent=2); stream.write('\n')
    print(json.dumps(record,indent=2))
    if status!='PASS':
        raise SystemExit(1)


if __name__=='__main__': main()
