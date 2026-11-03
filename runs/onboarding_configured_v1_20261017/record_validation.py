"""Record completed local checks and final archive identity; no experiment runs."""
import ast
import hashlib
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE / 'clean_install/repo/ood'))
import continuous_common_v3 as common


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def main():
    build = read(HERE / 'build_receipt.json')
    archive = HERE / build['archive']
    assert sha(archive) == build['archive_sha256']
    for path in (archive, HERE / 'onboarding_install_v1.py'):
        assert sha(path) == path.with_name(path.name + '.sha256').read_text().split()[0]
    bundle, installed = HERE / 'bundle', HERE / 'clean_install'
    for directory in (bundle, installed):
        common.verify(directory, exact=False)
        assert sha(directory / 'SHA256SUMS') == build['package_seal_sha256']
    package_files = {}
    for path in sorted(bundle.rglob('*')):
        if path.is_file():
            name = path.relative_to(bundle).as_posix()
            digest = sha(path)
            assert sha(installed / name) == digest, name
            package_files[name] = digest
    sources = sorted((installed / 'repo/ood').glob('*.py'))
    assert len(sources) == build['python_modules'] == 89
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path), feature_version=(3, 9))
    old = read(ROOT / 'runs/engineering_snapshot_journal_fix_20261017/source_manifest.json')
    inherited = {}
    for relative, expected in old['files'].items():
        if relative.startswith('repo/ood/') and (bundle / relative).is_file():
            assert sha(bundle / relative) == sha(ROOT / relative) == expected, relative
            inherited[relative] = expected
    for name, expected in build['original_scientific_code'].items():
        assert sha(ROOT / 'repo/ood' / name) == package_files['repo/ood/' + name] == expected
    protocol = ROOT / 'runs/onboarding_materials_and_protocol_20261015/protocol.json'
    assert sha(protocol) == package_files['protocol.json'] == build['protocol_sha256']
    query = ROOT / 'runs/query_tail_configured_v2r3_20261017'
    prior = read(query / 'validation.json')
    assert sha(query / prior['archive']) == build['query_tail_package_unchanged']
    assert package_files['query_tail_design.json'] == prior['unchanged_design_sha256']
    common.verify(query / 'bundle', exact=False)
    scientific = read(HERE / 'final_synthetic/result.json')
    assert scientific['status'] == 'PASS' and scientific['total_tests'] == 162
    assert scientific['package_seal_sha256'] == build['package_seal_sha256']
    for record in scientific['tests'].values():
        assert record['success'] and not any(record[k] for k in ('failures', 'errors', 'skipped'))
        assert sha(HERE / 'final_synthetic' / record['log']) == record['sha256']
    linux = read(HERE / 'linux_validation/result.json')
    assert linux['status'] == 'PASS'
    assert linux['archive_sha256'] == build['archive_sha256']
    assert linux['installed_seal']['sha256'] == build['package_seal_sha256']
    assert linux['test_count'] == 17 and not any(linux[k] for k in ('failures', 'errors', 'skipped'))
    for record in linux['logs'].values():
        assert sha(HERE / record['path']) == record['sha256']
    parser = read(HERE / 'powershell_parser.json')
    assert parser['status'] == 'PASS' and parser['error_count'] == 0
    assert sha(HERE / parser['script']) == parser['sha256']
    plan = read(installed / 'resource_plan.json')
    assert sha(installed / 'resource_plan.json') == build['resource_plan_sha256']
    new_names = ('onboarding_resources_v1.py', 'onboarding_delivery_v1.py',
                 'onboarding_delivery_io_v1.py', 'onboarding_synthetic_checks_v1.py',
                 'test_onboarding_delivery_v1.py', 'test_onboarding_delivery_io_v1.py')
    workspace_new = {}
    for name in new_names:
        relative = 'repo/ood/' + name
        assert sha(ROOT / relative) == package_files[relative]
        workspace_new[relative] = package_files[relative]
    supporting = ('build_delivery.py', 'record_validation.py', 'test_submit_linux.py',
                  'README.md', 'OPERATE_HPC.md', 'RESOURCE_BUDGET.md', 'transfer_v1.ps1',
                  'onboarding_install_v1.py', 'build_receipt.json', 'powershell_parser.json',
                  'clean_install.install_receipt.json', 'final_synthetic/result.json',
                  'linux_validation/result.json')
    manifest = dict(schema='onboarding-configured-delivery-manifest-v1', date='2026-10-17',
        archive_sha256=build['archive_sha256'], package_files=package_files,
        new_workspace_files=workspace_new, unchanged_inherited_engineering_files=inherited,
        original_scientific_code=build['original_scientific_code'],
        supporting_files={name: sha(HERE / name) for name in supporting})
    write(HERE / 'source_manifest.json', manifest)
    import numpy
    import torch
    receipt = dict(status='LOCAL_CONFIGURED_DELIVERY_PASS_TARGET_VERIFICATION_PENDING',
        date='2026-10-17', archive=archive.name, archive_sha256=sha(archive),
        archive_bytes=archive.stat().st_size, package_seal_sha256=build['package_seal_sha256'],
        source_manifest_sha256=sha(HERE / 'source_manifest.json'),
        resource_plan_sha256=build['resource_plan_sha256'],
        allocation={k: plan[k] for k in ('cpus', 'memory_gib', 'processes', 'threads', 'guard_gib')},
        phase_peak_estimates_gib={k: v['simultaneous_peak_gib'] for k, v in plan['phases'].items()},
        complete_phase_measurement=False,
        tests=dict(final_archive_clean_install_synthetic=scientific,
                   linux_standard_library_delivery=linux),
        total_checks=scientific['total_tests'] + linux['test_count'],
        powershell_transfer_parser=parser,
        local_environment=dict(python=sys.version, platform=platform.platform(),
                               numpy=numpy.__version__, torch=torch.__version__),
        target_environment='NOT_CHECKED', actual_tokenizer='NOT_RUN_LOCAL_TRANSFORMERS_UNAVAILABLE',
        tokenizer_required_in_target_job=True,
        syntax_python39_modules=len(sources), package_and_installed_byte_identity=True,
        installed_files=len(package_files),
        windows_final_archive_install=read(HERE / 'clean_install.install_receipt.json'),
        unchanged_query_tail_package_sha256=build['query_tail_package_unchanged'],
        unchanged_protocol_sha256=build['protocol_sha256'],
        original_scientific_code=build['original_scientific_code'],
        prior_engineering_manifest_sha256=sha(ROOT / 'runs/engineering_snapshot_journal_fix_20261017/source_manifest.json'),
        scope=dict(real_experiment='NOT_STARTED', remote_actions=False,
                   real_training=False, real_target_scoring=False, real_pcap_decode=False,
                   real_feature_extraction=False),
        draft_failure=dict(path='draft_validation',
            cause='One synthetic fixture retained its historical workspace protocol path.',
            fix='Installed check runner binds only fixture PROTOCOL to the identical sealed package protocol; original scientific source and protocol unchanged.',
            final_result='All 162 selected final archive checks passed; draft failure evidence retained.'),
        limitations=[
            'Whole-phase RAM/disk/time are estimates; the first real run must supply measured peaks.',
            'Preflight hashing occurs before the internal 22h chain timer; Slurm still caps the job at24h.',
            'Remote environment, full parent assets, checkpoint and completed QUERY_TAIL outputs remain required.',
            'Target numeric versions and actual tokenizer checks remain pending on the HPC environment.',
            'Zero added attack misses is an acceptance gate, not a guaranteed safety property.',
            'Missing three-device regression prevents complete-system PASS.',
            'CIC/UNSW remain development data; no new performance or independent confirmation results.',
            'The standalone frontend reconstruction package and modern replacement heads are still pending.'
        ])
    write(HERE / 'validation.json', receipt)
    print(json.dumps(dict(status=receipt['status'], archive_sha256=receipt['archive_sha256'],
                         synthetic_tests=162, package_files=len(package_files), python_modules=len(sources))))


if __name__ == '__main__':
    main()
