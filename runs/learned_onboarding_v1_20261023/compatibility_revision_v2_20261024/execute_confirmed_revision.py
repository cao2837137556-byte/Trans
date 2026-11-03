"""Execute the user's confirmed independent V2 attempt once; preserve V1."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path('runs/learned_onboarding_v1_20261023')
REVISION = Path(__file__).resolve().parent
OPERATIONS = REVISION / 'operations'
REMOTE = '/srv/paper04/learned_onboarding_20261024_v2'
UNIT = 'paper04-learned-onboarding-20261024-v2'
HOST = 'paper04-coupon-20261020'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_helper():
    path = ROOT / PACKAGE / 'deployment_20261024/local_ops/deploy.py'
    spec = importlib.util.spec_from_file_location('confirmed_revision_deploy_helper', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OPS = OPERATIONS
    module.REMOTE = REMOTE
    return module


def get_launch_code():
    path = ROOT / PACKAGE / 'deployment_20261024/local_ops/launch.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id == 'code']
    assert len(values) == 1
    code = values[0]
    previous_root = "'/srv/paper04/learned_onboarding_20261024'"
    previous_unit = "unit='paper04-learned-onboarding-20261024-v1'"
    assert code.count(previous_root) == code.count(previous_unit) == 1
    code = code.replace(previous_root, repr(REMOTE)).replace(previous_unit, 'unit=' + repr(UNIT))
    ast.parse(code, feature_version=(3, 9))
    return code


def main():
    assert sys.argv[1:] == ['--execute-user-confirmed-v2'], 'EXPLICIT_CONFIRMED_MODE_REQUIRED'
    assert not OPERATIONS.exists(), 'ATTEMPT_ALREADY_EXISTS_NO_AUTOMATIC_RETRY'
    receipt = json.loads((REVISION / 'REVISION_RECEIPT.json').read_text(encoding='utf-8'))
    archive = REVISION / 'learned_onboarding_20261024_v2.zip'
    assert receipt['archive_sha256'] == '6e3e13f04e7b6bcac69e2fbf278c287f000a93e773f57ef7e27348cf452c0e61'
    assert sha(archive) == receipt['archive_sha256'] and archive.stat().st_size == receipt['archive_bytes']
    manifest_path = REVISION / 'staging/DEPLOYMENT_MANIFEST.json'
    assert sha(manifest_path) == receipt['deployment_manifest_sha256']
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == set(manifest['files']) | {'DEPLOYMENT_MANIFEST.json'}
        assert bundle.read('DEPLOYMENT_MANIFEST.json') == manifest_path.read_bytes()
        for name, item in manifest['files'].items():
            content = bundle.read(name)
            assert len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'], name
    original_path = ROOT / PACKAGE / 'implementation_manifest.json'
    assert sha(original_path) == 'f304679eed5214e6f670d7a4a77037c8b00329aa2ce82abc42c6f9ac484f81c8'
    original = json.loads(original_path.read_text(encoding='utf-8'))
    for name, item in original['artifacts'].items():
        assert sha(ROOT / PACKAGE / name) == item['sha256'], 'ORIGINAL_CHANGED:' + name
    launch_code = get_launch_code()
    OPERATIONS.mkdir()
    helper = load_helper()
    helper.write(OPERATIONS / 'USER_CONFIRMATION.json', dict(
        authorized_by='Current user message', instruction='确认重新启动',
        at=datetime.now(timezone.utc).isoformat(), scope='One independent V2 deployment and full frozen chain',
        root=REMOTE, unit=UNIT, archive_sha256=receipt['archive_sha256'],
        automatic_retry=False, prior_attempt_preserved=True))
    helper.remote("from pathlib import Path\nimport shutil,json\np=Path(" + repr(REMOTE) +
        ")\nassert not p.exists(),'NEW_REMOTE_ROOT_EXISTS'\n" +
        "assert not Path(str(p)+'.zip').exists(),'NEW_REMOTE_ZIP_EXISTS'\n" +
        "assert shutil.disk_usage(p.parent).free > 12*1024**3,'DISK_HEADROOM'\n" +
        "print(json.dumps({'status':'FRESH_V2_DESTINATION','free_bytes':shutil.disk_usage(p.parent).free}))\n",
        'REMOTE_DESTINATION_CHECK.json')
    upload = subprocess.run(['scp', '-oBatchMode=yes', '-oConnectTimeout=8', str(archive),
                              HOST + ':' + REMOTE + '.zip'], text=True, encoding='utf-8',
                             capture_output=True, timeout=180)
    helper.write(OPERATIONS / 'UPLOAD_RECEIPT.json', dict(returncode=upload.returncode,
                 stdout=upload.stdout, stderr=upload.stderr, archive_sha256=receipt['archive_sha256']))
    assert upload.returncode == 0, 'V2_UPLOAD_FAILED_NO_AUTOMATIC_RETRY'
    helper.finish_deploy(dict(archive_sha256=receipt['archive_sha256'],
                             manifest_sha256=receipt['deployment_manifest_sha256']),
                         'REMOTE_DEPLOYMENT_VERIFIED.json')
    (OPERATIONS / 'exact_remote_launch.py').write_text(launch_code, encoding='utf-8', newline='\n')
    helper.remote(launch_code, 'REMOTE_LAUNCH_RECEIPT.json', timeout=60)


if __name__ == '__main__':
    main()
