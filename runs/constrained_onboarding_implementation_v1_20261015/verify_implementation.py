"""Verify only new code and generated fixtures; no real model/data execution."""
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODE = ROOT/'repo/ood'
SUITES = [
    'test_constrained_onboarding_core_v1',
    'test_constrained_onboarding_reference_v1',
    'test_constrained_onboarding_query_tail_adapter_v1',
    'test_constrained_onboarding_integration_v1',
]
FROZEN = {
    'runs/onboarding_materials_and_protocol_20261015/protocol.json':
        '2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5',
    'runs/legacy_query_tail_learning_design_v2_20261010/design_contract.json':
        'c6027a90f1f997b1bb1e8dd44409237531d7dc97cc13813e9bec364dc40b21af',
    'runs/legacy_query_tail_learning_delivery_v2r1_20261010/legacy_query_tail_learning_v2r1_20261010.tar.gz':
        'af61a1b187acaf8c379f1c8b01de0b18001aaa194333cfb7cf3bf95f6adddc4c',
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def write(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    frozen = {rel: dict(expected=expected, actual=sha(ROOT/rel)) for rel, expected in FROZEN.items()}
    assert all(v['expected'] == v['actual'] for v in frozen.values()), 'FROZEN_IDENTITY_CHANGED'
    files = sorted(set(CODE.glob('constrained_onboarding_*_v1.py')) |
                   set(CODE.glob('test_constrained_onboarding_*_v1.py')))
    for path in files:
        compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    command = [sys.executable, '-m', 'unittest', '-v']+SUITES
    begin = time.perf_counter()
    result = subprocess.run(command, cwd=str(CODE), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
    (HERE/'synthetic_tests.log').write_text(result.stdout, encoding='utf-8')
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    assert before == after, 'SOURCES_CHANGED_DURING_VERIFICATION'
    matches = re.findall(r'Ran (\d+) tests in ([\d.]+)s', result.stdout)
    passed = result.returncode == 0 and bool(matches) and result.stdout.rstrip().endswith('OK')
    write('source_manifest.json', dict(files=after, scope='New implementation and tests only'))
    write('implementation_receipt.json', dict(
        status='IMPLEMENTED_SYNTHETIC_VERIFIED_REAL_NOT_STARTED' if passed else 'VALIDATION_FAILED',
        date='2026-10-15', python=sys.version, executable=sys.executable, platform=platform.platform(),
        test_command=command, test_cwd=str(CODE), tests=int(matches[-1][0]) if matches else None,
        exit_code=result.returncode, wall_seconds=time.perf_counter()-begin,
        test_log_sha256=sha(HERE/'synthetic_tests.log'), frozen_inputs=frozen,
        source_manifest_sha256=sha(HERE/'source_manifest.json'),
        real_experiment='NOT_STARTED', real_training=False, real_pcap_decode=False,
        real_E3_forward=False, real_target_scoring=False, remote_access=False,
        standalone_HPC_package=False, modern_heads_implemented=False,
        required_before_real_pairing=['Complete verified parent current-input caches and snapshots',
            'Completed QUERY_TAIL v2r1 endpoints and score receipts',
            'For B0/B1/B2, complete normal capture preparation and frozen E3 encoding'],
        remaining_complete_system_evidence=['Consumed three-device current-input regression',
            'All real development results and frozen scientific gates',
            'Independent confirmation after model/rule selection']
    ))
    print(json.dumps(dict(passed=passed, tests=int(matches[-1][0]) if matches else None,
                          receipt=str(HERE/'implementation_receipt.json')), ensure_ascii=False))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
