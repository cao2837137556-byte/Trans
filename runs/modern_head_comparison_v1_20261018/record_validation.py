"""Record completed local checks without repeating experiments or changing the seal."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def seal_entries(folder):
    entries = {}
    for line in (folder / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        require(sha(folder / name) == digest, 'SEALED_FILE_CHANGED: ' + str(folder / name))
        entries[name] = digest
    return entries


def write_new(name, value):
    path = HERE / name
    require(not path.exists(), 'RECEIPT_ALREADY_EXISTS: ' + name)
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def main():
    for name in ('validation.json', 'source_manifest.json'):
        require(not (HERE / name).exists(), 'RECEIPT_ALREADY_EXISTS: ' + name)
    build = read(HERE / 'build_receipt.json')
    bundle = HERE / 'bundle'
    require(sha(HERE / build['archive']) == build['archive_sha256'], 'ARCHIVE_CHANGED')
    require(sha(bundle / 'SHA256SUMS') == build['package_seal_sha256'], 'SEAL_CHANGED')
    package = seal_entries(bundle)
    package['SHA256SUMS'] = build['package_seal_sha256']
    installs = {}
    for name in ('clean_install', 'linux_clean_install'):
        require(seal_entries(HERE / name) == {k: v for k, v in package.items() if k != 'SHA256SUMS'},
                'INSTALL_CONTENT_CHANGED: ' + name)
        require(sha(HERE / name / 'SHA256SUMS') == build['package_seal_sha256'], 'INSTALL_SEAL_CHANGED')
        receipt = read(HERE / (name + '.install_receipt.json'))
        require(receipt['archive_sha256'] == build['archive_sha256'], 'INSTALL_ARCHIVE_MISMATCH')
        require(receipt['internal_seal_sha256'] == build['package_seal_sha256'], 'INSTALL_RECEIPT_SEAL_MISMATCH')
        require(receipt['status'] == 'INSTALLED_AND_VERIFIED_NO_EXPERIMENT_STARTED', 'INSTALL_FAILED')
        installs[name] = receipt

    inherited = {}
    for folder, key in (('query_tail_configured_v2r3_20261017', 'parent_query_tail_sha256'),
                        ('onboarding_configured_v1r1_20261017', 'parent_onboarding_sha256')):
        parent = ROOT / 'runs' / folder
        receipt = read(parent / 'validation.json')
        require(sha(parent / receipt['archive']) == build[key] == receipt['archive_sha256'], 'PARENT_ARCHIVE_CHANGED')
        require(sha(parent / 'bundle/SHA256SUMS') == receipt['package_seal_sha256'], 'PARENT_SEAL_CHANGED')
        inherited[folder] = dict(archive_sha256=receipt['archive_sha256'],
                                validation_sha256=sha(parent / 'validation.json'), rerun=False)
    old = ROOT / 'runs/onboarding_configured_v1r1_20261017/bundle'
    old_files = seal_entries(old)
    inherited_python = [name for name in old_files if name.startswith('repo/ood/') and name.endswith('.py')]
    inherited_vendor = [name for name in old_files if name.startswith('vendor/') and name.endswith('.py')]
    require(len(inherited_python) == 89, 'UNEXPECTED_INHERITED_MODULE_COUNT')
    require(len(inherited_vendor) == 17, 'UNEXPECTED_VENDOR_MODULE_COUNT')
    for name in inherited_python + inherited_vendor + ['protocol.json', 'query_tail_design.json', 'design_contract.json']:
        require(package[name] == old_files[name], 'INHERITED_SCIENTIFIC_FILE_CHANGED: ' + name)
    source = {}
    for path in sorted((ROOT / 'repo/ood').glob('*modern_head*_v1.py')):
        name = path.relative_to(ROOT).as_posix()
        require(sha(path) == package[name], 'SOURCE_PACKAGE_DRIFT: ' + name)
        source[name] = sha(path)
    for name in ('tabm.py', 'LICENSE'):
        path = ROOT / 'repo/ood/vendor/tabm_v0_0_3' / name
        rel = path.relative_to(ROOT).as_posix()
        require(sha(path) == package[rel], 'VENDOR_SOURCE_DRIFT')
        source[rel] = sha(path)

    synthetic = read(HERE / 'final_synthetic/result.json')
    require(synthetic['status'] == 'PASS' and synthetic['total_tests'] == 41, 'SYNTHETIC_FAILED')
    require(synthetic['package_seal_sha256'] == build['package_seal_sha256'], 'SYNTHETIC_WRONG_PACKAGE')
    for result in synthetic['tests'].values():
        require(result['success'] and not any(result[x] for x in ('failures', 'errors', 'skipped')), 'SYNTHETIC_FAILED')
        require(sha(HERE / 'final_synthetic' / result['log']) == result['sha256'], 'SYNTHETIC_LOG_CHANGED')
    linux = read(HERE / 'linux_validation/result.json')
    require(linux['status'] == 'PASS' and linux['tests_run'] == 24, 'LINUX_CHECKS_FAILED')
    require(not any(linux[x] for x in ('failures', 'errors', 'skips', 'install_returncode', 'seal_returncode')), 'LINUX_CHECKS_FAILED')
    for name in ('archive_sha256', 'package_seal_sha256', 'resource_plan_sha256', 'experiment_contract_sha256'):
        require(linux[name] == build[name], 'LINUX_IDENTITY_MISMATCH: ' + name)
    require(linux['test_code_sha256'] == sha(HERE / 'test_delivery_linux.py'), 'LINUX_TEST_SOURCE_CHANGED')
    seal_entries(HERE / 'linux_validation')
    export = read(HERE / 'linux_validation/export_fixture.json')
    require(export['status'] == 'PASS' and len(export['checks']) == 7, 'EXPORT_CHECK_FAILED')
    require(export['script_sha256'] == package['repo/ood/modern_head_delivery_io_v1.py'], 'EXPORT_SCRIPT_CHANGED')
    ps = read(HERE / 'powershell_parser.json')
    require(ps['status'] == 'PASS' and ps['sha256'] == sha(HERE / 'transfer_v1.ps1'), 'POWERSHELL_CHECK_FAILED')

    # Record this unchanged local interpreter/dependency environment; no model is loaded.
    sys.path.insert(0, str(HERE / 'local_deps'))
    versions = {name: importlib.metadata.version(name) for name in
                ('numpy', 'torch', 'lightgbm', 'rtdl-num-embeddings', 'scipy', 'typing_extensions')}
    support = {}
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.ps1', '.md', '.json', '.log', '.sha256'):
            support[path.name] = sha(path)
    for folder in ('final_synthetic', 'linux_validation', 'delivery_scripts'):
        for path in sorted((HERE / folder).iterdir()):
            if path.is_file():
                support[path.relative_to(HERE).as_posix()] = sha(path)
    changed = sorted(name for name in old_files if name in package and old_files[name] != package[name])
    added = sorted(set(package) - set(old_files) - {'SHA256SUMS'})
    write_new('source_manifest.json', dict(schema='modern-head-delivery-manifest-v1',
        archive_sha256=build['archive_sha256'], package_files=package, source_files=source,
        inherited_python_modules_unchanged=len(inherited_python), inherited_vendor_modules_unchanged=len(inherited_vendor),
        changed_inherited_payload_files=changed, added_payload_files=added, supporting_files=support))
    validation = dict(status='LOCAL_DELIVERY_PASS_TARGET_VERIFICATION_PENDING', date='2026-10-18',
        archive=build['archive'], archive_sha256=build['archive_sha256'], archive_bytes=build['archive_bytes'],
        package_seal_sha256=build['package_seal_sha256'], resource_plan_sha256=build['resource_plan_sha256'],
        experiment_contract_sha256=build['experiment_contract_sha256'],
        source_manifest_sha256=sha(HERE / 'source_manifest.json'),
        build_receipt_note='Build-time pending receipt retained unchanged; this validation is the final local status.',
        current_tests=65, synthetic_checks=synthetic, linux_delivery_checks=linux,
        export_fixture_checks=export, export_fixture_assertions=7,
        installation_checks=installs, powershell_syntax=ps,
        bash_syntax=dict(status='PASS', scripts=4, included_in_linux_tests=True),
        local_numeric_environment=dict(python=sys.version, platform=platform.platform(), versions=versions,
            production_environment_verified=False),
        unchanged_python_modules=89, unchanged_vendor_modules=17, inherited_validation=inherited,
        resource_budget=dict(cpus=8, memory_gib=16, numeric_threads=4, heavy_stage_processes=1,
            rss_guard_gib=14, whole_stage_peak='ESTIMATED_NOT_MEASURED',
            slurm_hours=72, runtime_guard_hours=70, time_limits_are_not_eta=True),
        real_experiment='NOT_STARTED', remote_actions=False,
        limitations=[
            'Only synthetic model/evaluation tests and mocked scheduler checks; no new scientific performance result.',
            'Local NumPy/Torch differ from target Python3.9/NumPy2.0.1/Torch2.5.1; target checks remain pending.',
            'LightGBM Linux x86_64 wheel needs glibc>=2.28; real cluster compatibility unverified.',
            'Original complete caches, completed QUERY_TAIL and onboarding v1r1 artifacts remain required.',
            'No full training/resource measurement; generated TabM timing cannot guarantee 72h completion.',
            'Missing sealed old numeric runtime requires common MLP retraining; plan for at most nine new endpoints.',
            'Zero additional attack misses is an acceptance gate, not a guarantee; missing three-device regression blocks full-system PASS.',
            'PowerShell transfer was syntax-checked only in this revision; no real upload/download or network check.',
            'Previous 179-test scientific suite was not rerun; inherited modules and scientific contracts remain byte-identical.',
        ])
    write_new('validation.json', validation)
    print(json.dumps(dict(status=validation['status'], tests=65, export_assertions=7,
        archive_sha256=build['archive_sha256'], manifest_sha256=validation['source_manifest_sha256'],
        sealed_files=len(package)-1, unchanged_python_modules=89, local_versions=versions)))


if __name__ == '__main__':
    main()
