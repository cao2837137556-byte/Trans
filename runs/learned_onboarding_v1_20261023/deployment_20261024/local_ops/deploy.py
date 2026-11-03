"""One-shot packaging and deployment; never launch, resume, or retry training."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path('runs/learned_onboarding_v1_20261023')
OPS = ROOT / PACKAGE / 'deployment_20261024/local_ops'
REMOTE = '/srv/paper04/learned_onboarding_20261024'
HOST = 'paper04-coupon-20261020'
PYTHON = '/opt/paper04-venv/bin/python'
SPEC = Path('runs/learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md')
SPEC_SHA = 'a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8'
ENGINEERING_SHA = 'f304679eed5214e6f670d7a4a77037c8b00329aa2ce82abc42c6f9ac484f81c8'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def remote(code, receipt, timeout=180):
    result = subprocess.run(['ssh', '-T', '-oBatchMode=yes', '-oConnectTimeout=8', HOST,
                             PYTHON + ' -'], input=code, text=True, encoding='utf-8',
                            capture_output=True, timeout=timeout)
    write(OPS / receipt, dict(returncode=result.returncode, stdout=result.stdout,
                             stderr=result.stderr, at=datetime.now(timezone.utc).isoformat()))
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    if result.returncode:
        raise SystemExit(result.returncode)
    return result.stdout


def main():
    assert not (OPS / 'PACKAGE_RECEIPT.json').exists(), 'PACKAGING_ALREADY_ATTEMPTED'
    assert sha(ROOT / SPEC) == SPEC_SHA
    implementation_path = ROOT / PACKAGE / 'implementation_manifest.json'
    assert sha(implementation_path) == ENGINEERING_SHA
    implementation = json.loads(implementation_path.read_text(encoding='utf-8'))
    selected = {PACKAGE / 'implementation_manifest.json', SPEC}
    for name, item in implementation['artifacts'].items():
        relative = PACKAGE / name
        path = ROOT / relative
        assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], name
        selected.add(relative)
    selected.update(p.relative_to(ROOT) for p in (ROOT / 'repo/ood').rglob('*.py'))
    for name in ('run_chain.py', 'run_stage.py', 'target_manifest_adapter.py',
                 'prepare_source_archive.py', 'source_members.json', 'remote_config.json'):
        selected.add(PACKAGE / 'deployment_20261024' / name)
    files = {p.as_posix(): dict(sha256=sha(ROOT / p), bytes=(ROOT / p).stat().st_size)
             for p in sorted(selected)}
    manifest = dict(schema='learned-onboarding-deployment-manifest-v1',
                    created_at=datetime.now(timezone.utc).isoformat(),
                    spec_sha256=SPEC_SHA, engineering_manifest_sha256=ENGINEERING_SHA,
                    original_artifacts_verified=len(implementation['artifacts']),
                    files=files, source_only_until_calibration_seal=True,
                    scientific_recipe_changed=False, automatic_retry=False)
    manifest_path = OPS / 'DEPLOYMENT_MANIFEST.json'
    write(manifest_path, manifest)
    archive_path = OPS / 'learned_onboarding_20261024.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT / name, name)
        archive.write(manifest_path, 'DEPLOYMENT_MANIFEST.json')
    receipt = dict(status='PACKAGED_NOT_LAUNCHED', files=len(files),
                   original_artifacts_verified=len(implementation['artifacts']),
                   uncompressed_bytes=sum(item['bytes'] for item in files.values()),
                   archive_path=str(archive_path), archive_bytes=archive_path.stat().st_size,
                   archive_sha256=sha(archive_path), manifest_sha256=sha(manifest_path),
                   remote_root=REMOTE, host=HOST)
    write(OPS / 'PACKAGE_RECEIPT.json', receipt)
    print(json.dumps(receipt))
    remote("from pathlib import Path\nimport shutil,json\np=Path(" + repr(REMOTE) +
           ")\nassert not p.exists(),'REMOTE_ROOT_EXISTS'\n" +
           "assert not Path(str(p)+'.zip').exists(),'REMOTE_ZIP_EXISTS'\n" +
           "assert shutil.disk_usage(p.parent).free > 12*1024**3,'DISK_HEADROOM'\n" +
           "print(json.dumps({'status':'FRESH_DESTINATION','free_bytes':shutil.disk_usage(p.parent).free}))\n",
           'REMOTE_DESTINATION_CHECK.json')
    upload = subprocess.run(['scp', '-oBatchMode=yes', '-oConnectTimeout=8', str(archive_path),
                             HOST + ':' + REMOTE + '.zip'], capture_output=True, text=True,
                            encoding='utf-8', timeout=180)
    write(OPS / 'UPLOAD_RECEIPT.json', dict(returncode=upload.returncode,
                                           stdout=upload.stdout, stderr=upload.stderr))
    assert upload.returncode == 0, 'UPLOAD_FAILED_NO_AUTOMATIC_RETRY'
    finish_deploy(receipt, 'REMOTE_DEPLOYMENT_VERIFIED.json')


def finish_deploy(receipt, verification_name):
    remote("""from pathlib import Path
import hashlib,json,zipfile,datetime
root=Path(__REMOTE_ROOT__)
archive=Path(str(root)+'.zip')
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert sha(archive)==__ARCHIVE_SHA__,'UPLOAD_SHA'
assert not root.exists(),'REMOTE_ROOT_EXISTS'
with zipfile.ZipFile(archive) as z:
 for member in z.infolist():
  target=(root/member.filename).resolve()
  assert root in target.parents,'ZIP_ESCAPE'
 root.mkdir()
 z.extractall(root)
manifest_path=root/'DEPLOYMENT_MANIFEST.json'
assert sha(manifest_path)==__MANIFEST_SHA__,'MANIFEST_SHA'
manifest=json.loads(manifest_path.read_text())
for name,item in manifest['files'].items():
 p=root/name
 assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],name
receipt=dict(status='DEPLOYED_VERIFIED_NOT_LAUNCHED',files=len(manifest['files']),
 manifest_sha256=__MANIFEST_SHA__,archive_sha256=__ARCHIVE_SHA__,
 at=datetime.datetime.now(datetime.timezone.utc).isoformat(),automatic_retry=False)
with (root/'DEPLOYMENT_VERIFIED.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
""".replace('__REMOTE_ROOT__', repr(REMOTE)).replace('__ARCHIVE_SHA__', repr(receipt['archive_sha256']))
           .replace('__MANIFEST_SHA__', repr(receipt['manifest_sha256'])), verification_name)
    builder = REMOTE + '/' + (PACKAGE / 'deployment_20261024/prepare_source_archive.py').as_posix()
    code = "import subprocess\nsubprocess.run(" + repr([PYTHON, '-B', builder, '--deployment-root', REMOTE]) + ",check=True)\n"
    remote(code, 'REMOTE_SOURCE_ARCHIVE_RECEIPT.json')


if __name__ == '__main__':
    if sys.argv[1:] == ['--finish-uploaded-after-installer-fix']:
        receipt = json.loads((OPS / 'PACKAGE_RECEIPT.json').read_text(encoding='utf-8'))
        assert sha(receipt['archive_path']) == receipt['archive_sha256'], 'LOCAL_PACKAGE_CHANGED'
        finish_deploy(receipt, 'REMOTE_DEPLOYMENT_VERIFIED_AFTER_INSTALLER_FIX.json')
    else:
        assert not sys.argv[1:], 'UNKNOWN_MODE'
        main()
