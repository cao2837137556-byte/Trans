"""Prepared remote acceptance only: no real decoder, model forward or submission."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
PACKAGE = ROOT / 'runs/history_normal_reference_v1_20261031'
HERE = ROOT / 'runs/history_normal_reference_deployment_20261031'
PYTHON = Path('/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python')
ENVIRONMENT = ROOT / 'frontend_compat_v1/environment.sh'
ENVIRONMENT_SHA = '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf'
OVERLAY = ROOT / 'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201'
VENDOR = ROOT / 'environment/vendor_py311_v1'
RESULT = HERE / 'remote_preflight/PREFLIGHT_RESULT.json'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, body, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path if exclusive else path.with_suffix(path.suffix + '.tmp')
    with target.open('x' if exclusive else 'w', encoding='utf-8') as f:
        json.dump(body, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    if not exclusive:
        target.replace(path)


def authorization():
    value = read(HERE / 'AUTHORIZATION.json')
    require(value.get('status') == 'AUTHORIZED_SINGLE_EXECUTION' and
            value.get('user_message') == '允许下一步' and
            value.get('candidate') == 'C1' and value.get('path') == 'P-DEVONLY' and
            value.get('automatic_retry') is False and value.get('training_authorized') is False and
            value.get('limits') == dict(cpu=4, memory_gib=16, wall_hours=8, intermediate_gib=20),
            'AUTHORIZATION_NOT_FIXED_SINGLE_ATTEMPT')
    return value


def current_seals():
    """Verify the complete delivery inventory, including original input hashes."""
    authorization()
    require(sha(ENVIRONMENT) == ENVIRONMENT_SHA, 'FROZEN_ENVIRONMENT_SCRIPT_CHANGED')
    delivery = read(HERE / 'DELIVERY_INPUTS.json')
    require(delivery['remote_root'] == str(ROOT) and
            delivery['code_manifest_changed_keys'] == ['config/EXECUTION.json'], 'DELIVERY_BINDING')
    seen = set()
    for row in delivery['files']:
        relative = Path(row['remote_relative_path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'INPUT_PATH_ESCAPE')
        path = ROOT / relative
        require(path.resolve().is_relative_to(ROOT) and path.is_file() and not path.is_symlink(),
                'DELIVERY_INPUT_MISSING_OR_LINK:' + str(path))
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'DELIVERY_INPUT_CHANGED:' + str(path))
        require(str(relative) not in seen, 'DUPLICATE_DELIVERY_PATH')
        seen.add(str(relative))
    # Reject added files as well as modified listed files, including at submit time.
    source_paths = [PACKAGE/'run.py', PACKAGE/'progress.py', PACKAGE/'progress.html',
                    *PACKAGE.glob('hpc/*.slurm'), *PACKAGE.glob('hnr/*.py'), *PACKAGE.glob('config/*.json')]
    observed = {p.relative_to(PACKAGE).as_posix(): sha(p) for p in source_paths if p.is_file()}
    for directory in (ROOT/'repo/ood',
                      ROOT/'runs/dense_reference_matrix_v1_20261027/vendor/encoding_v2/repo/ood',
                      ROOT/'runs/dense_reference_ab_stage_candidate_v1_20261028/vendor/encoding_v2/repo/ood'):
        for p in directory.rglob('*.py'):
            if p.is_file():
                observed['@root/' + p.relative_to(ROOT).as_posix()] = sha(p)
    for name in ('matrix.py', 'metrics.py'):
        p = ROOT/'runs/dense_reference_ab_stage_candidate_v1_20261028/src'/name
        if p.is_file():
            observed['@root/' + p.relative_to(ROOT).as_posix()] = sha(p)
    runtime = Path(read(PACKAGE/'config/EXECUTION.json')['encoder']['runtime_root'])
    for p in runtime.rglob('*.py'):
        if p.is_file() and '__pycache__' not in p.parts:
            require(p.is_relative_to(ROOT), 'ENCODER_OUTSIDE_FIXED_ROOT')
            observed['@root/' + p.relative_to(ROOT).as_posix()] = sha(p)
    require(observed == read(PACKAGE/'CODE_MANIFEST.json')['code_sha256'], 'EXACT_CODE_INVENTORY_CHANGED')
    actual_vendor = {p.relative_to(runtime).as_posix()
                     for folder in ('vendor/netFound', 'vendor/netFound-base')
                     for p in (runtime/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    require(actual_vendor == set(read(PACKAGE/'config/ENCODER_RUNTIME_FILES.json')['files']),
            'EXACT_VENDOR_INVENTORY_CHANGED')
    paths = dict(delivery_inputs=HERE/'DELIVERY_INPUTS.json', authorization=HERE/'AUTHORIZATION.json',
                 code_manifest=PACKAGE/'CODE_MANIFEST.json', config=PACKAGE/'config/EXECUTION.json',
                 preflight_script=HERE/'remote_preflight.py', submit_script=HERE/'submit_once.py',
                 environment_script=ENVIRONMENT, slurm_script=PACKAGE/'hpc/run_history.slurm')
    return {key: dict(path=str(path), sha256=sha(path)) for key, path in paths.items()}


def shell_preamble():
    return '\n'.join([
        'set -euo pipefail',
        'export PATH=/usr/local/slurm-25.11.0-build/bin:/usr/bin:/bin',
        'export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=27',
        'export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4',
        'export CUDA_VISIBLE_DEVICES="" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1',
        'if ! type module >/dev/null 2>&1; then',
        '  for paper04_init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do',
        '    if [[ -r "$paper04_init" ]]; then source "$paper04_init"; if type module >/dev/null 2>&1; then break; fi; fi',
        '  done', 'fi', 'type module >/dev/null 2>&1',
        'source ' + shlex.quote(str(ENVIRONMENT)),
        'export PYTHONPATH=' + shlex.quote(str(OVERLAY) + ':' + str(VENDOR)),
        'cd ' + shlex.quote(str(PACKAGE)),
    ]) + '\n'


def checked_command(name, arguments, output):
    script = shell_preamble() + 'exec ' + ' '.join(shlex.quote(str(v)) for v in arguments) + '\n'
    (output / (name + '.command.sh')).write_text(script, encoding='utf-8')
    stdout_path, stderr_path = output/(name+'.stdout.log'), output/(name+'.stderr.log')
    with stdout_path.open('x', encoding='utf-8') as stdout, stderr_path.open('x', encoding='utf-8') as stderr:
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc'], input=script,
                                text=True, stdout=stdout, stderr=stderr, timeout=1800)
    record = dict(name=name, returncode=result.returncode,
                  stdout=dict(path=str(stdout_path), sha256=sha(stdout_path)),
                  stderr=dict(path=str(stderr_path), sha256=sha(stderr_path)))
    write(output/(name+'.json'), record, exclusive=True)
    require(result.returncode == 0, 'PREFLIGHT_COMMAND_FAILED:' + name)
    return record


def main():
    output = RESULT.parent
    output.mkdir(parents=True, exist_ok=False)
    result = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                  real_packet_decodes=0, real_model_forwards=0, scientific_execution=False,
                  automatic_retry=False, commands=[])
    write(RESULT, result)
    try:
        result['seals'] = current_seals()
        require(PYTHON.is_file() and os.access(PYTHON, os.X_OK), 'FROZEN_PYTHON_MISSING')
        code = ('import json,run; import numpy,torch,psutil,pandas,transformers,safetensors; '
                'import hnr.runtime,hnr.history,hnr.encoding,hnr.assets,hnr.evaluation; '
                'from issue27ckda_d0_resource_pilot_v1 import import_netfound; '
                'import_netfound(' + repr(str(ROOT/'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime/vendor/netFound')) + '); '
                'print(json.dumps(run.environment_check(),sort_keys=True))')
        result['commands'].append(checked_command('environment_and_imports', [PYTHON, '-B', '-c', code], output))
        result['commands'].append(checked_command('input_readiness', [PYTHON, '-B', 'run.py', 'check',
            '--runtime-config', PACKAGE/'config/EXECUTION.json'], output))
        text = (output/'input_readiness.stdout.log').read_text()
        readiness = [json.loads(line) for line in text.splitlines() if line.startswith('{')][-1]
        require(readiness.get('status') == 'READY' and readiness.get('blockers') == [], 'REMOTE_INPUTS_NOT_READY')
        result['commands'].append(checked_command('synthetic_tests', [PYTHON, '-B', '-m', 'unittest',
            'discover', '-s', 'tests', '-v'], output))
        log = (output/'synthetic_tests.stderr.log').read_text()
        require(re.search(r'Ran 56 tests?\b', log) and re.search(r'^OK\s*$', log, re.MULTILINE),
                'EXPECTED_SYNTHETIC_56_PASS')
        require(current_seals() == result['seals'], 'DELIVERY_CHANGED_DURING_PREFLIGHT')
        result.update(status='PASS', input_readiness='READY', synthetic_tests_passed=56,
                      environment=dict(python='3.11.11', numpy='2.0.1', torch='2.5.1'))
    except BaseException as exc:
        result.update(status='FAILED', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write(RESULT, result)


if __name__ == '__main__':
    main()
