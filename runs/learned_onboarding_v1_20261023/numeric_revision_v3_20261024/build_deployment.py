"""Package the user-authorized V3 execution without altering validated sources."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

REV=Path(__file__).resolve().parent
ROOT=REV.parents[2]
PACKAGE=Path('runs/learned_onboarding_v1_20261023')
OUT=REV/'deployment_20261024'
STAGING=OUT/'staging'
REMOTE='/srv/paper04/learned_onboarding_20261024_v3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write('\n')


def main():
    assert not OUT.exists(),'DEPLOYMENT_PACKAGE_ALREADY_PREPARED'
    repair=json.loads((REV/'REPAIR_RECEIPT.json').read_text(encoding='utf-8'))
    assert repair['status']=='NUMERIC_FIX_VERIFIED_SOURCE_ONLY_EXPERIMENT_STILL_STOPPED'
    validated=REV/'staging/NUMERIC_REVISION_MANIFEST.json'
    assert sha(validated)==repair['candidate_manifest_sha256']
    original_manifest=json.loads(validated.read_text(encoding='utf-8'))
    for name,item in original_manifest['files'].items():
        source=REV/'staging'/name
        assert sha(source)==item['sha256'] and source.stat().st_size==item['bytes'],name
        target=STAGING/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    package=STAGING/PACKAGE
    # Integrate the already validated five regressions into ordinary discovery.
    test=(REV/'test_numeric_revision.py').read_text(encoding='utf-8')
    old="REV = Path(__file__).resolve().parent\nsys.path.insert(0,str(REV/'staging/runs/learned_onboarding_v1_20261023/src'))"
    new="sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))"
    assert test.count(old)==1
    test=test.replace(old,new)
    ast.parse(test,feature_version=(3,9))
    (package/'tests/test_numeric_revision.py').write_text(test,encoding='utf-8',newline='\n')
    config_path=package/'deployment_20261024/remote_config.json'
    config=json.loads(config_path.read_text(encoding='utf-8'))
    config['source']['archive']=REMOTE+'/inputs/source_head_archive'
    config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8',newline='\n')
    implementation_path=package/'implementation_manifest.json'
    implementation=json.loads(implementation_path.read_text(encoding='utf-8'))
    implementation['artifacts']['tests/test_numeric_revision.py']=dict(
        sha256=sha(package/'tests/test_numeric_revision.py'),
        bytes=(package/'tests/test_numeric_revision.py').stat().st_size)
    implementation.update(status='AUTHORIZED_INDEPENDENT_V3_EXECUTION_PACKAGE',
        validated_numeric_manifest_sha256=sha(validated),
        source_repair_receipt_sha256=sha(REV/'REPAIR_RECEIPT.json'),
        inference_backend='learned-onboarding-rowwise-float32-v3-20261024',
        user_authorization='修复好了，就可以启动实验了。')
    implementation_path.write_text(json.dumps(implementation,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    for path in (package/'src').glob('*.py'):
        assert sha(path)==sha(REV/'staging'/PACKAGE/'src'/path.name),'VALIDATED_SOURCE_CHANGED'
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',
                     MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
    with (OUT/'local_tests.log').open('x',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',
            str(package/'tests'),'-v'],cwd=STAGING,env=environment,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0,'INTEGRATED_TESTS_FAILED'
    log=(OUT/'local_tests.log').read_text(encoding='utf-8')
    assert 'Ran 54 tests' in log and log.rstrip().endswith('OK'),'INTEGRATED_TEST_COUNT'
    names=set(original_manifest['files'])|{(PACKAGE/'tests/test_numeric_revision.py').as_posix()}
    files={name:dict(sha256=sha(STAGING/name),bytes=(STAGING/name).stat().st_size) for name in sorted(names)}
    manifest=dict(schema='learned-onboarding-deployment-manifest-v1',
        created_at=datetime.now(timezone.utc).isoformat(),spec_sha256=implementation['spec_sha256'],
        engineering_manifest_sha256=sha(implementation_path),files=files,
        validated_numeric_manifest_sha256=sha(validated),numeric_execution_changed=True,
        validated_numeric_src_unchanged=True,scientific_recipe_changed=False,
        source_only_until_calibration_seal=True,automatic_retry=False,
        integrated_unittests=54,adapter_tests_separate=4,
        prior_attempts_preserved=True,user_authorized=True)
    write(STAGING/'DEPLOYMENT_MANIFEST.json',manifest)
    archive=OUT/'learned_onboarding_20261024_v3.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in files:
            bundle.write(STAGING/name,name)
        bundle.write(STAGING/'DEPLOYMENT_MANIFEST.json','DEPLOYMENT_MANIFEST.json')
    receipt=dict(status='USER_AUTHORIZED_V3_PACKAGED_NOT_LAUNCHED',
        instruction='修复好了，就可以启动实验了。',
        archive_path=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
        manifest_sha256=sha(STAGING/'DEPLOYMENT_MANIFEST.json'),
        engineering_manifest_sha256=sha(implementation_path),files=len(files),
        validated_numeric_src_unchanged=True,integrated_local_tests=54,
        remote_root=REMOTE,unit='paper04-learned-onboarding-20261024-v3',
        automatic_retry=False,prior_attempts_preserved=True)
    write(OUT/'PACKAGE_RECEIPT.json',receipt)
    print(json.dumps(receipt))


if __name__=='__main__':
    main()
