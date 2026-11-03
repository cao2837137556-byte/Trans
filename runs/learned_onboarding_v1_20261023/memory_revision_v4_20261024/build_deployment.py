"""Build one independent V4 package from the already validated source closure."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
PACKAGE = Path('runs/learned_onboarding_v1_20261023')
OUT = HERE/'deployment_20261024'
STAGING = OUT/'staging'
REMOTE = '/srv/paper04/learned_onboarding_20261024_v4'
UNIT = 'paper04-learned-onboarding-20261024-v4'
AUTHORIZATION = '\u53ef\u4ee5\u52a8\u624b\u8fd0\u884c\u3002'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def main():
    assert not OUT.exists(), 'V4_DEPLOYMENT_ALREADY_PREPARED'
    candidate = HERE/'staging'
    repair = json.loads((HERE/'REPAIR_RECEIPT.json').read_text(encoding='utf-8'))
    assert repair['status'] == 'REPAIR_VALIDATED_SOURCE_ONLY_FORMAL_EXPERIMENT_STOPPED'
    for name, expected in repair['artifacts'].items():
        assert sha(HERE/name) == expected, 'REPAIR_EVIDENCE_CHANGED:'+name
    accepted = json.loads((HERE/'remote_validation/PREFLIGHT_ACCEPTANCE.json').read_text(encoding='utf-8'))
    assert accepted['status'] == 'PASS_ACTUAL_PREFLIGHT' and accepted['local_proof_installed']
    assert accepted['resource_plan']['status'] == 'READY'
    proof_path = candidate/'MEMORY_RESOURCE_VALIDATION.json'
    assert sha(proof_path) == accepted['source_proof_sha256']
    validated = candidate/'MEMORY_REVISION_MANIFEST.json'
    closure = json.loads(validated.read_text(encoding='utf-8'))
    assert sha(validated) == json.loads((HERE/'PACKAGE_RECEIPT.json').read_text(encoding='utf-8'))['revision_manifest_sha256']
    # The diagnostic closure pins Python files; production also needs the
    # delivery documents/configuration and source transport allowlist.
    candidate_impl = json.loads((candidate/PACKAGE/'implementation_manifest.json').read_text(encoding='utf-8'))
    pinned = dict(closure['files'])
    for name, item in candidate_impl['artifacts'].items():
        relative = (PACKAGE/name).as_posix()
        assert relative not in pinned or pinned[relative] == item, relative
        pinned[relative] = item
    parent = json.loads((candidate/'DEPLOYMENT_MANIFEST.json').read_text(encoding='utf-8'))
    for name in ('remote_config.json', 'source_members.json'):
        relative = (PACKAGE/'deployment_20261024'/name).as_posix()
        pinned[relative] = parent['files'][relative]
    names = set(pinned)
    assert not {'DEPLOYMENT_MANIFEST.json', 'MEMORY_REVISION_MANIFEST.json'} & names
    for name, expected in pinned.items():
        source = candidate/name
        assert sha(source) == expected['sha256'] and source.stat().st_size == expected['bytes'], name
        target = STAGING/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(proof_path, STAGING/'MEMORY_RESOURCE_VALIDATION.json')
    names.add('MEMORY_RESOURCE_VALIDATION.json')
    package = STAGING/PACKAGE
    expected_code = repair['source_code_sha256']
    assert {p.name: sha(p) for p in (package/'src').glob('*.py')} == expected_code
    for path in list((package/'src').glob('*.py')) + list((package/'tests').glob('*.py')):
        ast.parse(path.read_text(encoding='utf-8-sig'), feature_version=(3, 9))
    config_path = package/'deployment_20261024/remote_config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['source']['archive'] = REMOTE+'/inputs/source_head_archive'
    config_path.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    implementation_path = package/'implementation_manifest.json'
    implementation = json.loads(implementation_path.read_text(encoding='utf-8'))
    for name, expected in implementation['artifacts'].items():
        path = package/name
        assert sha(path) == expected['sha256'] and path.stat().st_size == expected['bytes'], name
    implementation.update(schema='learned-onboarding-memory-revision-v4',
        status='AUTHORIZED_INDEPENDENT_V4_EXECUTION_PACKAGE',
        production_restart_authorized_this_revision=True, user_authorization=AUTHORIZATION,
        validated_memory_manifest_sha256=sha(validated),
        source_repair_receipt_sha256=sha(HERE/'REPAIR_RECEIPT.json'),
        full_scale_memory_receipt_sha256=sha(proof_path),
        validated_memory_src_unchanged=True, scientific_recipe_changed=False)
    implementation_path.write_text(json.dumps(implementation, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    files = {name: dict(sha256=sha(STAGING/name), bytes=(STAGING/name).stat().st_size)
             for name in sorted(names)}
    manifest = dict(schema='learned-onboarding-deployment-manifest-v1',
        created_at=datetime.now(timezone.utc).isoformat(), spec_sha256=implementation['spec_sha256'],
        engineering_manifest_sha256=sha(implementation_path), files=files,
        validated_memory_src_unchanged=True, scientific_recipe_changed=False,
        validated_memory_manifest_sha256=sha(validated),
        full_scale_memory_receipt_sha256=sha(proof_path),
        source_repair_receipt_sha256=sha(HERE/'REPAIR_RECEIPT.json'),
        source_only_until_calibration_seal=True, automatic_retry=False,
        integrated_unittests=63, adapter_tests_separate=4,
        prior_attempts_preserved=True, user_authorized=True, remote_root=REMOTE, unit=UNIT)
    write(STAGING/'DEPLOYMENT_MANIFEST.json', manifest)
    archive = OUT/'learned_onboarding_20261024_v4.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in files:
            bundle.write(STAGING/name, name)
        bundle.write(STAGING/'DEPLOYMENT_MANIFEST.json', 'DEPLOYMENT_MANIFEST.json')
    with zipfile.ZipFile(archive) as bundle:
        assert len(bundle.namelist()) == len(set(bundle.namelist()))
        assert set(bundle.namelist()) == set(files)|{'DEPLOYMENT_MANIFEST.json'}
        for name, expected in files.items():
            data = bundle.read(name)
            assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
    receipt = dict(status='USER_AUTHORIZED_V4_PACKAGED_NOT_LAUNCHED', instruction=AUTHORIZATION,
        archive_path=str(archive), archive_bytes=archive.stat().st_size, archive_sha256=sha(archive),
        manifest_sha256=sha(STAGING/'DEPLOYMENT_MANIFEST.json'),
        engineering_manifest_sha256=sha(implementation_path), files=len(files),
        validated_source_file_count=len(expected_code), validated_memory_src_unchanged=True,
        full_scale_memory_receipt_sha256=sha(proof_path),
        previous_local_tests=63, startup_remote_tests_required=63,
        remote_root=REMOTE, unit=UNIT, automatic_retry=False, prior_attempts_preserved=True)
    write(OUT/'PACKAGE_RECEIPT.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
