"""Execute the user's explicitly authorized independent V3 attempt exactly once."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

REV=Path(__file__).resolve().parent
ROOT=REV.parents[2]
PACKAGE=Path('runs/learned_onboarding_v1_20261023')
DEPLOYMENT=REV/'deployment_20261024'
OPS=DEPLOYMENT/'operations'
REMOTE='/srv/paper04/learned_onboarding_20261024_v3'
UNIT='paper04-learned-onboarding-20261024-v3'
HOST='paper04-coupon-20261020'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert sys.argv[1:]==['--execute-user-authorized-v3'],'EXPLICIT_MODE_REQUIRED'
    assert not OPS.exists(),'ATTEMPT_ALREADY_EXISTS_NO_AUTOMATIC_RETRY'
    receipt=json.loads((DEPLOYMENT/'PACKAGE_RECEIPT.json').read_text(encoding='utf-8'))
    archive=DEPLOYMENT/'learned_onboarding_20261024_v3.zip'
    assert sha(archive)==receipt['archive_sha256'] and archive.stat().st_size==receipt['archive_bytes']
    manifest_path=DEPLOYMENT/'staging/DEPLOYMENT_MANIFEST.json'
    assert sha(manifest_path)==receipt['manifest_sha256']
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist())==set(manifest['files'])|{'DEPLOYMENT_MANIFEST.json'}
        assert bundle.read('DEPLOYMENT_MANIFEST.json')==manifest_path.read_bytes()
        for name,item in manifest['files'].items():
            data=bundle.read(name)
            assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],name
    original_path=ROOT/PACKAGE/'implementation_manifest.json'
    assert sha(original_path)=='f304679eed5214e6f670d7a4a77037c8b00329aa2ce82abc42c6f9ac484f81c8'
    original=json.loads(original_path.read_text(encoding='utf-8'))
    for name,item in original['artifacts'].items():
        assert sha(ROOT/PACKAGE/name)==item['sha256'],'ORIGINAL_CHANGED:'+name
    helper_path=ROOT/PACKAGE/'deployment_20261024/local_ops/deploy.py'
    spec=importlib.util.spec_from_file_location('authorized_v3_deploy_helper',helper_path)
    helper=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.OPS,helper.REMOTE=OPS,REMOTE
    launch_path=ROOT/PACKAGE/'deployment_20261024/local_ops/launch.py'
    tree=ast.parse(launch_path.read_text(encoding='utf-8'))
    codes=[ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
           and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='code']
    assert len(codes)==1
    code=codes[0]
    old_root="'/srv/paper04/learned_onboarding_20261024'"
    old_unit="unit='paper04-learned-onboarding-20261024-v1'"
    assert code.count(old_root)==code.count(old_unit)==1
    code=code.replace(old_root,repr(REMOTE)).replace(old_unit,'unit='+repr(UNIT))
    code=code.replace('Paper04 learned onboarding frozen V1','Paper04 learned onboarding V3 numeric fix')
    ast.parse(code,feature_version=(3,9))
    OPS.mkdir()
    helper.write(OPS/'USER_AUTHORIZATION.json',dict(instruction='修复好了，就可以启动实验了。',
        authorized_by='Current user message',at=datetime.now(timezone.utc).isoformat(),
        scope='One independent V3 deployment and full frozen chain, using validated numeric revision',
        root=REMOTE,unit=UNIT,archive_sha256=receipt['archive_sha256'],
        automatic_retry=False,prior_attempts_preserved=True))
    helper.remote("from pathlib import Path\nimport shutil,json\np=Path("+repr(REMOTE)+")\n"
        "assert not p.exists(),'NEW_REMOTE_ROOT_EXISTS'\n"
        "assert not Path(str(p)+'.zip').exists(),'NEW_REMOTE_ZIP_EXISTS'\n"
        "assert shutil.disk_usage(p.parent).free>12*1024**3,'DISK_HEADROOM'\n"
        "print(json.dumps({'status':'FRESH_V3_DESTINATION','free_bytes':shutil.disk_usage(p.parent).free}))\n",
        'REMOTE_DESTINATION_CHECK.json')
    uploaded=subprocess.run(['scp','-oBatchMode=yes','-oConnectTimeout=8',str(archive),
        HOST+':'+REMOTE+'.zip'],capture_output=True,text=True,encoding='utf-8',timeout=180)
    helper.write(OPS/'UPLOAD_RECEIPT.json',dict(returncode=uploaded.returncode,stdout=uploaded.stdout,
        stderr=uploaded.stderr,archive_sha256=receipt['archive_sha256']))
    assert uploaded.returncode==0,'V3_UPLOAD_FAILED_NO_AUTOMATIC_RETRY'
    helper.finish_deploy(receipt,'REMOTE_DEPLOYMENT_VERIFIED.json')
    (OPS/'exact_remote_launch.py').write_text(code,encoding='utf-8',newline='\n')
    helper.remote(code,'REMOTE_LAUNCH_RECEIPT.json',timeout=60)


if __name__=='__main__':
    main()
