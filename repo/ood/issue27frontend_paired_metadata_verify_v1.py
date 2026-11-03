"""Seal implementation acceptance from generated-test evidence; no experiment launch."""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import issue27frontend_paired_metadata_v1 as s

DOC = 'runs/mainline_docs/frontend_paired_metadata_implementation_and_synthetic_verification_20260909.md'


def main():
    folder = s.ROOT / s.PACKAGE
    s.require(not (folder / 'SHA256SUMS').exists(), 'IMPLEMENTATION_ALREADY_SEALED')
    s.require(not (s.ROOT / s.REAL).exists(), 'REAL_ATTEMPT_MUST_NOT_EXIST')
    targets, members = s.load_inputs()
    tests_path = s.ROOT / 'repo/ood/issue27frontend_paired_metadata_tests_v1.py'
    tree = ast.parse(tests_path.read_text(encoding='utf-8'))
    expected = {(cls.name, n.name) for cls in tree.body if isinstance(cls, ast.ClassDef)
                for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')}
    observed = set()
    for name in ('synthetic_tests.log', 'child_cleanup_test.log'):
        log = (folder / name).read_text(encoding='utf-8-sig')
        s.require('\nOK\n' in log and 'FAILED (' not in log, 'TEST_LOG_FAILED')
        for method, classname in re.findall(r'^(test_\w+) \((?:\w+\.)*(\w+)\) \.\.\. ok$', log, flags=re.M):
            key = (classname, method)
            s.require(key not in observed, 'DUPLICATE_COUNTED_TEST')
            observed.add(key)
    s.require(observed == expected and len(expected) == 45, 'COMPLETE_GENERATED_TEST_SET')
    parse_checks = json.loads((folder / 'powershell_parser_checks.json').read_text(encoding='utf-8-sig'))
    s.require(len(parse_checks) == 2 and all(c['status'] == 'PASS' and c['errors'] == 0 for c in parse_checks), 'POWERSHELL_PARSE_CHECK')
    baseline = s.read_json(folder / 'workspace_start_hashes.json')
    old_baseline = s.read_json(s.ROOT / s.FREEZE / 'workspace_preservation_baseline.json')['unrelated_hashes']
    for rel, h in old_baseline.items():
        s.require(s.sha_file(s.ROOT / rel) == h, 'PREVIOUS_UNRELATED_FILE_DRIFT')
    for rel, h in baseline.items():
        s.require(s.sha_file(s.ROOT / rel) == h, 'UNRELATED_FILE_DRIFT')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=str(s.ROOT), text=True).strip()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=str(s.ROOT), text=True).strip()
    s.require(head == '4b28747b09480471e2bac1beb3a9badf27280efb' and branch == 'codex/exp-mainline', 'WORKSPACE_IDENTITY')
    doc = s.ROOT / DOC
    sidecar = doc.with_suffix('.sha256')
    sidecar.write_bytes((s.sha_file(doc) + '  ' + doc.name + '\n').encode('utf-8'))
    sources = [
        'repo/ood/issue27frontend_paired_metadata' + suffix + '_v1.py'
        for suffix in ('', '_runner', '_control', '_tests', '_verify')]
    sources += ['scripts/start_frontend_paired_metadata_local.ps1', 'scripts/show_frontend_paired_metadata_status.ps1']
    frozen = s.read_json(s.ROOT / s.FREEZE / 'frozen_dependency_pins.json')
    sources += list(frozen['verified_source_pins'])
    sources += ['repo/ood/' + name for name in s.LEGACY]
    sources += ['repo/ood/issue27frontend_inheritance_outer_control_v1.py',
                'repo/ood/issue27frontend_inheritance_outer_support_v1.py',
                'repo/ood/issue27frontend_inheritance_n1_support_v1.py', DOC, sidecar.relative_to(s.ROOT).as_posix()]
    code_pins = {rel: s.sha_file(s.ROOT / rel) for rel in sorted(set(sources))}
    for rel in sources:
        if rel.endswith('.py'):
            ast.parse((s.ROOT / rel).read_text(encoding='utf-8-sig'), filename=rel)
    python_root = Path(sys.executable).parent
    runtime = [python_root / name for name in ('python.exe', 'python39.dll', 'DLLs/_ctypes.pyd',
               'Lib/ast.py', 'Lib/csv.py', 'Lib/gzip.py', 'Lib/zipfile.py', 'Lib/dataclasses.py',
               'Lib/json/decoder.py', 'Lib/json/encoder.py', 'Lib/subprocess.py', 'Lib/threading.py')]
    tshark = Path('C:/Program Files/Wireshark/tshark.exe')
    runtime += [tshark.parent / name for name in ('tshark.exe', 'libwireshark.dll', 'libwiretap.dll',
                'libwsutil.dll', 'glib-2.0-0.dll')]
    s.require(s.sha_file(tshark) == '908a3b04da69ee45be9bd54627a722741d895262b4ce0b39f6d79a03daa24087', 'TSHARK_BINARY')
    runtime_pins = {str(p.resolve()): s.sha_file(p) for p in runtime}
    containers = {m['container_path']: m['container_bytes'] for m in members}
    config = {'status': 'IMPLEMENTATION_FROZEN_REAL_READ_REQUIRES_EXPLICIT_AUTHORIZATION',
              'caps': dict(s.CAPS, controller_reserve_bytes=256 * 1024**2),
              'metadata_manifest_sha256': s.FREEZE_SHA,
              'code_and_document_pins': code_pins, 'runtime_pins': runtime_pins,
              'python_path': str(Path(sys.executable).resolve()), 'python_version': sys.version,
              'tshark_path': str(tshark.resolve()), 'raw_identity_bytes': sum(containers.values()),
              'raw_identity_files': len(containers), 'legal_targets': len(targets),
              'A_targets_H1_verified_from_saved_metadata': 11529,
              'raw_containers_opened_this_stage': 0, 'real_namespace': s.REAL,
              'training_authorized': False, 'scientific_capability': 'NOT_TESTED'}
    s.atomic_json(folder / 'execution_config.json', config)
    accept = {'status': 'PAIRED_METADATA_IMPLEMENTATION_ACCEPTANCE_PASS',
              'tests_run': len(expected), 'tests_passed': len(observed), 'powershell_parsers_passed': 2,
              'real_packets_decoded': 0, 'model_calls': 0,
              'config_sha256': s.sha_file(folder / 'execution_config.json'),
              'test_names': [cls + '.' + name for cls, name in sorted(expected)],
              'test_file_sha256': s.sha_file(tests_path),
              'test_logs': {n: s.sha_file(folder / n) for n in ('synthetic_tests.log', 'child_cleanup_test.log')},
              'qualification': 'generated correctness only; no real dependency/coverage/capability result',
              'real_namespace_exists': False}
    s.atomic_json(folder / 'synthetic_acceptance.json', accept)
    diff = subprocess.run(['git', 'diff', '--check', '--', 'runs/mainline_docs/mainline_handoff.md',
                           'runs/mainline_docs/mainline_experiment_map.md'], cwd=str(s.ROOT), capture_output=True, text=True)
    s.require(diff.returncode == 0, 'GIT_DIFF_CHECK')
    verification = {'status': 'IMPLEMENTATION_INTEGRITY_PASS', 'branch': branch, 'head': head,
                    'unrelated_hashes_verified': len(baseline), 'previous_freeze_verified_unchanged': s.FREEZE_SHA,
                    'code_and_document_pins': len(code_pins), 'runtime_pins': len(runtime_pins),
                    'generated_tests': len(observed), 'powershell_checks': 2, 'git_diff_check': 'PASS',
                    'real_raw_access': 0, 'real_model_calls': 0, 'real_attempt': 'NOT_STARTED'}
    s.atomic_json(folder / 'final_verification.json', verification)
    s.seal(folder)
    print(json.dumps(dict(verification, package_manifest_sha256=s.sha_file(folder / 'SHA256SUMS'),
                         raw_identity_bytes=config['raw_identity_bytes'], raw_identity_files=len(containers)), indent=2))


if __name__ == '__main__':
    main()
