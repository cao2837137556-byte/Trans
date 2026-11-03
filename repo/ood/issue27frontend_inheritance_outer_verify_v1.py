"""Accept generated checks and seal the outer implementation, never launch real work."""
from __future__ import annotations

import importlib.metadata
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

import issue27frontend_inheritance_outer_support_v1 as s
import issue27frontend_inheritance_outer_tests_v1 as tests
import issue27frontend_inheritance_n3_support_v1 as n3s
import issue27frontend_inheritance_n3_runner_v1 as n3

CONTRACT = s.DOCS + 'frontend_inheritance_outer_execution_contract_20260909.md'
NEW = tuple('repo/ood/issue27frontend_inheritance_outer_' + k + '_v1.py'
            for k in ('support', 'metadata', 'runner', 'control', 'tests', 'verify')) + (
    'scripts/start_frontend_inheritance_outer_local.ps1', 'scripts/show_frontend_inheritance_outer_status.ps1')


def main():
    folder = s.ROOT / s.PACKAGE
    s.require(not folder.exists() and not (s.ROOT / s.REAL).exists(), 'PACKAGE_OR_REAL_ALREADY_EXISTS')
    historical = n3s.frozen_design()
    accepted = json.loads((s.ROOT / n3s.IMPLEMENTATION / 'synthetic_acceptance.json').read_text(encoding='utf-8'))
    for path, sha in accepted['code_pins'].items():
        s.require(s.sha_file(s.ROOT / path) == sha, 'HISTORICAL_CODE_DRIFT')
    # Known frozen mapping/replay identities, not a new method selection.
    extra = {
        'repo/ood/issue27frontend_f0_zero_training_semantics_v1.py': '00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa',
        'repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py': 'ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60',
        'repo/ood/issue27frontend_f1_d1_train_v1.py': '6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634',
        'repo/ood/issue27frontend_f3_conflict_field_sufficiency_v1.py': '80b4de6c931b77f528bafaf64a4a0e449295c8a78fb1d9776a8fed1d35eb9791',
        'repo/ood/issue27frontend_f3_full_fit_l1_identifiability_v1.py': '69fc92fb417fe8dbca646c30aaaf7f7ea40edf81ecae3c4fe36d831434e35a67',
        'repo/ood/issue27frontend_f4_fieldwise_input_v1.py': '9c729a3165d19042549723f029235734595131d5e7ba344a3f605cca89677200',
    }
    for path, sha in extra.items():
        s.require(s.sha_file(s.ROOT / path) == sha, 'FROZEN_MAPPING_DRIFT')
    code_pins = {**accepted['code_pins'], **extra,
        **{p: s.sha_file(s.ROOT / p) for p in NEW + ('repo/ood/issue27frontend_inheritance_n0_inventory_v1.py',)}}
    s.verify_seal(s.ROOT / s.METADATA)
    metadata = json.loads((s.ROOT / s.METADATA / 'qualified_metadata.json').read_text(encoding='utf-8'))
    s.validate_population(metadata['contexts'])
    s.require(metadata['raw_packets'] == 628903 and metadata['events'] == 5164
              and metadata['batches'] == 112 and metadata['padded_slots'] == 18808, 'QUALIFIED_COUNT_DRIFT')
    unique_raw = {m['identity']['container_path']: int(m['identity']['container_bytes']) for m in metadata['members']}
    actions = {'raw_identity_files': 2, 'raw_identity_bytes': sum(unique_raw.values()), 'decoder_version_calls': 1,
        'decoder_calls': 5, 'raw_packets': 628903, 'members': 5, 'prepared_events': 5164,
        'loads': 1, 'head_decodes': 1, 'assemblies': 1, 'passes': 1, 'batches': 112,
        'contexts': 3582, 'targets': 4400, 'events': 5164, 'padded_slots': 18808}
    s.require(actions['raw_identity_bytes'] == 24442596676, 'OPAQUE_RAW_HASH_BUDGET')
    runtime_pins = dict(historical['runtime_file_sha256'])
    dist = importlib.metadata.distribution('pandas')
    pandas_metadata = next(p for p in dist.files if str(p).endswith('.dist-info/METADATA'))
    pandas_path = Path(dist.locate_file(pandas_metadata)).resolve()
    pandas_rel = pandas_path.relative_to(Path(historical['runtime_root']).resolve()).as_posix()
    runtime_pins[pandas_rel] = s.sha_file(pandas_path)
    for path, sha in runtime_pins.items():
        s.require(s.sha_file(Path(historical['runtime_root']) / path) == sha, 'RUNTIME_DRIFT')
    docs = (s.DESIGN, CONTRACT, n3s.DESIGN, n3s.EVIDENCE, n3s.PINS_FILE,
            'runs/mainline_docs/frontend_inheritance_n3_real_result_20260908.md',
            'runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908/SHA256SUMS')
    config = {'status': 'IMPLEMENTATION_ONLY_REAL_NOT_AUTHORIZED', 'metadata_sha256': s.sha_file(s.ROOT / s.METADATA / 'qualified_metadata.json'),
        'metadata_manifest_sha256': s.sha_file(s.ROOT / s.METADATA / 'SHA256SUMS'),
        'code_pins': code_pins, 'document_pins': {p: s.sha_file(s.ROOT / p) for p in docs},
        'runtime_root': historical['runtime_root'], 'runtime_pins': runtime_pins, 'tshark': metadata['tshark_identity'],
        'expected_actions': actions, 'caps': {'wall_seconds': 1800, 'memory_bytes': 8*1024**3,
            'output_bytes': 100*1024**2, 'reserve_bytes': 1024**2, **actions},
        'model_inputs': {k: v for k, v in historical['repository_inputs'].items()
            if k.endswith(('training/resume.pt', 'training/resume.pt.receipt.json', 'preflight/identities.json', 'training/terminal.json'))},
        'head_path': 'runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908/candidate_head.f32le',
        'candidate_state_sha256': 'ff41638339604d4270ff5eef616885ef4b25bb075e8d1cd89dcb565ed10df3f9',
        'assembly': {'terminal_state_tensor_sha256': '131d15e7a586a6fb105995ecb25d56f8217351c03b60495c56d6e1b723db1bcc',
            'non_head_state_tensor_sha256': '29328fc616ef5b0197d1dcc8c564d89865201eb08b540d826847e233932dbe67',
            'head_float32_le_sha256': 'e26bf80e8a45f605b806ed559afef0f3029f949a4c3cff00cf4aa6b7ef8d8d5a'}, **s.CLAIMS}
    runtime = n3.configure_runtime()
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    parser_checks = []
    for script in NEW[-2:]:
        ps = "$taskTokens=$null; $taskErrors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('" + str(s.ROOT / script).replace("'", "''") + "',[ref]$taskTokens,[ref]$taskErrors); if($taskErrors.Count){$taskErrors | ForEach-Object { $_.ToString() }; exit 1}"
        check = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        parser_checks.append({'path': script, 'exit_code': check.returncode})
    if not result.wasSuccessful() or result.skipped or any(p['exit_code'] for p in parser_checks):
        print(buffer.getvalue(), flush=True)
        raise s.Stop('GENERATED_ACCEPTANCE_FAILED')
    s.require(all(s.sha_file(s.ROOT / p) == h for p, h in code_pins.items()), 'CODE_CHANGED_DURING_TESTS')
    s.require(not (s.ROOT / s.REAL).exists(), 'UNEXPECTED_REAL_NAMESPACE')
    acceptance = {'status': 'OUTER_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS', 'tests_run': result.testsRun,
        'tests_passed': result.testsRun, 'tests_skipped': 0, 'powershell_parser_checks': parser_checks,
        'config_sha256': s.digest(s.json_bytes(config)), 'code_pin_count': len(code_pins),
        'runtime_pin_count': len(runtime_pins), 'runtime': runtime, 'pandas': dist.version,
        'real_model_forwards': 0, 'raw_replays': 0, 'real_checkpoint_tensor_loads': 0,
        'generated_decoder_fixtures_only': True, 'synthetic_process_enforcement_checks_only': True,
        'resource_pilots': 0, 'real_started': False, **s.CLAIMS}
    folder.mkdir(parents=True, exist_ok=False)
    for name, value in (('execution_config.json', config), ('synthetic_acceptance.json', acceptance)):
        with (folder / name).open('xb') as stream: stream.write(s.json_bytes(value))
    (folder / 'synthetic_tests.txt').write_text(buffer.getvalue(), encoding='utf-8')
    s.seal(folder)
    print(json.dumps(acceptance), flush=True)


if __name__ == '__main__': main()
