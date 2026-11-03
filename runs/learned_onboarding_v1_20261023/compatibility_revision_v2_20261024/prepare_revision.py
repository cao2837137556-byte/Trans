"""Prepare a local, reviewable compatibility revision; never deploy or launch it."""
import ast
import copy
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path('runs/learned_onboarding_v1_20261023')
REVISION = ROOT / PACKAGE / 'compatibility_revision_v2_20261024'
STAGING = REVISION / 'staging'
SPEC = Path('runs/learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def main():
    assert not STAGING.exists(), 'REVISION_ALREADY_PREPARED'
    old_deployment = json.loads((ROOT / PACKAGE / 'deployment_20261024/local_ops/DEPLOYMENT_MANIFEST.json').read_text())
    for name, item in old_deployment['files'].items():
        source = ROOT / name
        assert sha(source) == item['sha256'] and source.stat().st_size == item['bytes'], name
        destination = STAGING / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    original_manifest_path = STAGING / PACKAGE / 'implementation_manifest.json'
    original_manifest = json.loads(original_manifest_path.read_text(encoding='utf-8'))
    shutil.copyfile(original_manifest_path, original_manifest_path.with_name('implementation_manifest.original.json'))
    target = STAGING / PACKAGE / 'tests/test_learning.py'
    original_bytes = target.read_bytes()
    before = b'        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:'
    line_end = b'\r\n' if b'\r\n' in original_bytes else b'\n'
    after = (b"        cleanup_options = {'ignore_cleanup_errors': True} if sys.version_info >= (3, 10) else {}" +
             line_end + b'        with tempfile.TemporaryDirectory(**cleanup_options) as temp:')
    assert original_bytes.count(before) == 1
    revised_bytes = original_bytes.replace(before, after)
    target.write_bytes(revised_bytes)
    ast.parse(revised_bytes.decode('utf-8'), feature_version=(3, 9))
    patch = ''.join(difflib.unified_diff(original_bytes.decode().splitlines(keepends=True),
                                        revised_bytes.decode().splitlines(keepends=True),
                                        fromfile='original/tests/test_learning.py',
                                        tofile='compatibility-v2/tests/test_learning.py'))
    (REVISION / 'test_learning_python39.patch').write_text(patch, encoding='utf-8', newline='\n')
    config_path = STAGING / PACKAGE / 'deployment_20261024/remote_config.json'
    config = json.loads(config_path.read_text())
    config['source']['archive'] = '/srv/paper04/learned_onboarding_20261024_v2/inputs/source_head_archive'
    config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8', newline='\n')
    artifacts = copy.deepcopy(original_manifest['artifacts'])
    artifacts['tests/test_learning.py'] = dict(sha256=sha(target), bytes=target.stat().st_size)
    revised_manifest = dict(schema='learned-onboarding-compatibility-revision-manifest-v1',
        status='PREPARED_NOT_REMOTE_VALIDATED_NOT_AUTHORIZED_FOR_RELAUNCH',
        spec_sha256=original_manifest['spec_sha256'], lineage=original_manifest['lineage'],
        parent_parity=original_manifest['parent_parity'],
        derived_from=dict(file='implementation_manifest.original.json',
                          sha256=sha(original_manifest_path.with_name('implementation_manifest.original.json'))),
        scientific_src_unchanged=True, assertions_removed=0, tests_skipped=0,
        change='Version-gate a test-only Python3.10 temporary-directory keyword; preserve original assertions',
        artifacts=artifacts)
    original_manifest_path.write_text(json.dumps(revised_manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    # Evaluate the exact keyword expression under both API generations.
    import tempfile
    class Version:
        def __init__(self, value): self.version_info = value
    expression = "{'ignore_cleanup_errors': True} if sys.version_info >= (3, 10) else {}"
    options39 = eval(expression, {'sys': Version((3, 9))})
    options310 = eval(expression, {'sys': Version((3, 10))})
    assert options39 == {} and options310 == {'ignore_cleanup_errors': True}
    def legacy_temporary_directory(suffix=None, prefix=None, dir=None):
        return tempfile.TemporaryDirectory(suffix=suffix, prefix=prefix, dir=dir)
    with legacy_temporary_directory(**options39): pass
    # Full original assertions plus the revised cleanup branch, synthetic data only.
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='4',
                       MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4')
    tests = STAGING / PACKAGE / 'tests'
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(tests), '-v']
    with (REVISION / 'local_tests.log').open('x', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=STAGING, env=environment,
                                stdout=stream, stderr=subprocess.STDOUT)
    write(REVISION / 'LOCAL_VALIDATION.json', dict(
        status='PASS' if result.returncode == 0 else 'FAIL', returncode=result.returncode,
        runtime=sys.version, command=command, synthetic_only=True,
        legacy_keyword_dispatch='PASS', real_python39_runtime='NOT_RUN',
        remote_execution='NOT_RUN', production_training='NOT_RUN',
        log_sha256=sha(REVISION / 'local_tests.log')))
    assert result.returncode == 0, 'LOCAL_COMPATIBILITY_VALIDATION_FAILED'
    names = set(old_deployment['files'])
    names.add((PACKAGE / 'implementation_manifest.original.json').as_posix())
    files = {name: dict(sha256=sha(STAGING / name), bytes=(STAGING / name).stat().st_size)
             for name in sorted(names)}
    manifest = dict(schema='learned-onboarding-deployment-manifest-v1',
        created_at=datetime.now(timezone.utc).isoformat(),
        spec_sha256=old_deployment['spec_sha256'],
        engineering_manifest_sha256=sha(original_manifest_path), files=files,
        parent_deployment_manifest_sha256=sha(ROOT / PACKAGE / 'deployment_20261024/local_ops/DEPLOYMENT_MANIFEST.json'),
        scientific_recipe_changed=False, automatic_retry=False,
        execution_status='LOCAL_PROPOSAL_NOT_DEPLOYED_NOT_LAUNCHED')
    write(STAGING / 'DEPLOYMENT_MANIFEST.json', manifest)
    archive = REVISION / 'learned_onboarding_20261024_v2.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in files:
            bundle.write(STAGING / name, name)
        bundle.write(STAGING / 'DEPLOYMENT_MANIFEST.json', 'DEPLOYMENT_MANIFEST.json')
    for name, item in original_manifest['artifacts'].items():
        assert sha(ROOT / PACKAGE / name) == item['sha256'], 'ORIGINAL_CHANGED:' + name
    changed = [name for name, item in old_deployment['files'].items()
               if files[name]['sha256'] != item['sha256']]
    assert changed == sorted([(PACKAGE / 'deployment_20261024/remote_config.json').as_posix(),
                             (PACKAGE / 'implementation_manifest.json').as_posix(),
                             (PACKAGE / 'tests/test_learning.py').as_posix()])
    receipt = dict(status='REVIEWABLE_LOCAL_REVISION_NO_RELAUNCH',
        archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
        deployment_manifest_sha256=sha(STAGING / 'DEPLOYMENT_MANIFEST.json'),
        engineering_manifest_sha256=sha(original_manifest_path),
        files=len(files), changed_files=changed, original_30_artifacts_unchanged=True,
        all_scientific_src_unchanged=True, test_assertions_unchanged=True,
        local_validation='PASS', remote_python39_validation='NOT_RUN',
        proposed_root='/srv/paper04/learned_onboarding_20261024_v2',
        proposed_unit='paper04-learned-onboarding-20261024-v2',
        prior_attempt_preserved=True, automatic_relaunch=False)
    write(REVISION / 'REVISION_RECEIPT.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
