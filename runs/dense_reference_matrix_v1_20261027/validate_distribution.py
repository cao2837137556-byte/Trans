"""Independently extract and verify a sealed distribution on synthetic inputs."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024**2), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', required=True)
    args = parser.parse_args()
    distribution = Path(args.distribution).resolve()
    receipt = json.loads((distribution / 'PACKAGE_RECEIPT.json').read_text())
    archive = Path(receipt['archive'])
    assert digest(archive) == receipt['archive_sha256'], 'ARCHIVE_SHA'
    validation = distribution / 'validation'
    validation.mkdir()
    unpacked = validation / 'extracted'
    unpacked.mkdir()
    package_name = Path(__file__).resolve().parent.name
    with tarfile.open(archive, 'r:gz') as handle:
        for member in handle.getmembers():
            destination = (unpacked / member.name).resolve()
            assert destination.is_relative_to(unpacked) and not member.issym() and not member.islnk(), 'ARCHIVE_PATH'
            assert member.name.split('/')[0] == package_name, 'ARCHIVE_ROOT'
        handle.extractall(unpacked)
    package = unpacked / package_name
    # The local host provides psutil in its user site, while the registered HPC
    # environment provides it via its existing vendor. Keep user-site disabled
    # for isolated verification, but explicitly copy this already installed,
    # platform-specific local dependency into a validation-only private view.
    # This view is never shipped to Linux or written into shared site-packages.
    import psutil
    local_dependencies = validation / 'dependencies'
    local_dependencies.mkdir()
    shutil.copytree(Path(psutil.__file__).resolve().parent, local_dependencies / 'psutil',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    local_pins = {p.relative_to(local_dependencies).as_posix(): digest(p)
                  for p in local_dependencies.rglob('*') if p.is_file()}
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                       PYTHONPATH=os.pathsep.join([str(package / 'src'), str(local_dependencies)]))
    checks = []
    def run(name, argv, *, env=environment):
        result = subprocess.run(argv, cwd=package, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180, text=True,
                                encoding='utf-8', errors='replace')
        (validation / (name + '.log')).write_text(result.stdout, encoding='utf-8')
        checks.append(dict(name=name, exit_code=result.returncode,
                           log=name + '.log', status='PASS' if result.returncode == 0 else 'FAIL'))
        assert result.returncode == 0, name + ': see log'
        return result.stdout
    run('package_verify', [sys.executable, '-B', '-c',
        'from common import verify_package; from pathlib import Path; '
        'print(verify_package(Path.cwd()))'])
    assert digest(package / 'PACKAGE_SHA256SUMS') == receipt['package_sha256'], 'PACKAGE_IDENTITY'
    vendor = package / 'vendor/encoding_v2'
    assert digest(vendor / 'SHA256SUMS') == '50969f127dbb258b851f36ea03669456863a7d532b1c6f1b70a9c6a84088a910'
    vendor_members = set()
    for line in (vendor / 'SHA256SUMS').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        assert digest(vendor / relative) == expected, 'FROZEN_ENCODER_COPY'
        vendor_members.add(relative)
    assert vendor_members == {p.relative_to(vendor).as_posix() for p in vendor.rglob('*') if p.is_file()
                              and p != vendor / 'SHA256SUMS' and '__pycache__' not in p.parts}
    checks.append(dict(name='original_encoder_exact_copy', status='PASS', files=len(vendor_members)))
    reviewed = {}
    for name, field in (('CHAIN_INDEPENDENT_REVIEW.json', 'reviewed_files'),
                        ('FINAL_RUNTIME_REVIEW.json', 'reviewed_code_sha256')):
        report = json.loads((package / 'preparation' / name).read_text(encoding='utf-8'))
        for relative, expected in report[field].items():
            assert digest(package / relative) == expected, 'REVIEWED_CODE_CHANGED:' + relative
            reviewed[relative] = expected
    matrix_review = json.loads((package / 'preparation/MATRIX_INDEPENDENT_REVIEW.json').read_text(encoding='utf-8'))
    for item in matrix_review['files'].values():
        relative = item['path'].split('runs/' + package_name + '/', 1)[1]
        assert digest(package / relative) == item['sha256'], 'REVIEWED_MATRIX_CHANGED:' + relative
        reviewed[relative] = item['sha256']
    checks.append(dict(name='independent_review_exact_code_pins', status='PASS', files=len(reviewed)))
    source_manifest = json.loads((package / 'config/SOURCE_ASSET_MANIFEST.json').read_text())
    source_names = {item['path'] for item in source_manifest['files']}
    for name in ('CAL.npz', 'LEARN.jsonl.gz', 'LEARN_q.npy', 'normalizer.npz', 'SHA256SUMS'):
        assert 'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/' + name in source_names
    assert 'runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/INPUT_SEAL.json' in source_names
    assert 'runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/RESULT.json' in source_names
    assert all('/CIC_DEV.npy' not in name and '/UNSW_DEV.npy' not in name for name in source_names)
    for item in source_manifest['files']:
        if item['bundled']:
            assert digest(package / 'assets' / item['path']) == item['sha256'], 'SOURCE_SMALL_ASSET_CLOSURE'
    assert source_manifest['external_bytes'] == sum(i['bytes'] for i in source_manifest['files'] if not i['bundled'])
    checks.append(dict(name='source_prefix_static_closure', status='PASS', files=len(source_names),
                       real_arrays_loaded=False))
    parsed = 0
    for directory in ('src', 'hpc', 'tests'):
        for path in (package / directory).rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            parsed += 1
    checks.append(dict(name='new_python_syntax', status='PASS', files=parsed))
    output = run('synthetic_unittests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    match = re.search(r'Ran (\d+) tests?', output)
    assert match, 'TEST_COUNT_NOT_FOUND'
    unit_count = int(match[1])
    source_env = dict(environment, PYTHONPATH=os.pathsep.join([
        str(package / 'assets/repo/ood'), str(local_dependencies)]))
    run('source_cal_import_closure', [sys.executable, '-B', '-c',
        'import constrained_onboarding_core_v3, onboarding_budget_v1, indexed_features_v1; '
        'print("PASS: source CAL imports only; zero array reads or supports")'], env=source_env)
    bash = Path('C:/Program Files/Git/bin/bash.exe')
    if os.name == 'nt':
        assert bash.is_file(), 'BASH_SYNTAX_VERIFIER_MISSING'
        run('slurm_syntax', [str(bash), '--noprofile', '--norc', '-n', 'hpc/run_dense.slurm'])
    else:
        run('slurm_syntax', ['bash', '--noprofile', '--norc', '-n', 'hpc/run_dense.slurm'])
    run('package_reverify_after_tests', [sys.executable, '-B', '-c',
        'from common import verify_package; from pathlib import Path; print(verify_package(Path.cwd()))'])
    result = dict(schema='dense-reference-local-acceptance-v1', status='PASS',
        created_utc=datetime.now(timezone.utc).isoformat(), package_sha256=receipt['package_sha256'],
        archive_sha256=receipt['archive_sha256'], extracted_package=str(package),
        python=sys.version, synthetic_tests=unit_count, checks=checks,
        local_validation_only_dependency=dict(name='psutil', version=psutil.__version__,
            source_path=psutil.__file__, private_copy_sha256=local_pins,
            shipped_to_hpc=False, shared_environment_changed=False),
        real_model_forwards=0, real_encoding_rows=0, real_source_support_computations=0,
        real_target_evaluations=0, optimizer_updates=0, submitted_jobs=0, remote_operations=0,
        full_matrix_ready=False, blockers=receipt['blockers'])
    (distribution / 'VALIDATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status='PASS', synthetic_tests=unit_count, package_sha256=receipt['package_sha256'])))


if __name__ == '__main__':
    main()
