"""Post-check immutable inputs and seal the completed local C5 audit."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
REPORT = ROOT / 'runs/mainline_docs/collab/20261102_c5_kernel_independent_replay_reply_codex.md'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


ab = read(BASE / 'ab/RESULT.json')
ab_second = read(BASE / 'AB_SAVED_ARRAY_VERIFICATION.json')
source = read(BASE / 'source_cal/RESULT.json')
source_second = read(BASE / 'source_cal/SAVED_ARRAY_VERIFICATION.json')
assert ab_second['status'] == source_second['status'] == 'PASS'
assert ab_second['all_80_AB_protection_reports_independently_verified'] is True
assert source_second['joint_support_exact'] is True
assert source_second['inputs_post_verified'] == 21
assert source_second['outputs_verified'] == 19
assert digest(BASE / 'source_cal/RESULT.json') == source_second['source_support_rebuild_result_sha256']
assert digest(BASE / 'source_cal/RESULT.json') == '760b137a987b23442c47bc7c27d8f679867e1a4fd66dcc88048bcf3275d9ebcd'
assert digest(BASE / 'AB_SAVED_ARRAY_VERIFICATION.json') == '86c46aa14a1051e138df0b14f98cd8206e0f8b7011dd00574ffb3c4b8c05ffee'

input_checks = {}
for receipt in [ab, ab_second]:
    for path, expected in receipt['input_sha256'].items():
        resolved = ROOT / path
        got = digest(resolved)
        assert got == expected, (path, got, expected)
        input_checks[path] = {'sha256': got, 'unchanged': True}
source_output_checks = {}
for path, expected in source['output_sha256'].items():
    got = digest(BASE / 'source_cal' / path)
    assert got == expected, (path, got, expected)
    source_output_checks[path] = got

for pd in ab['pools'].values():
    assert pd['p1_logits_decisions_and_reports_bit_exact'] is True
for key, summary in ab['summary'].items():
    assert summary['gate_count'] == summary['gate_passes'] == 16
    assert summary['all_16_gates_pass'] is True
for p in ['p1', 'p2', 'p3', 'p4']:
    assert source['candidates'][p]['protection']['strict_source_zero_withdrawal_pass'] is True
assert source['candidates']['positive_saturation']['protection']['strict_source_zero_withdrawal_pass'] is False

manifest = {}
for path in sorted(BASE.rglob('*')):
    if not path.is_file() or path.name.endswith('.sha256') or path.name == 'VERIFICATION.json':
        continue
    sha = digest(path)
    manifest[path.relative_to(ROOT).as_posix()] = {'bytes': path.stat().st_size, 'sha256': sha}
    path.with_name(path.name + '.sha256').write_text(sha + '  ' + path.name + '\n', encoding='utf-8')
report_sha = digest(REPORT)
REPORT.with_name(REPORT.name + '.sha256').write_text(report_sha + '  ' + REPORT.name + '\n', encoding='utf-8')
result = {
    'schema': 'C5_INDEPENDENT_AUDIT_FINAL_VERIFICATION_V1',
    'status': 'PASS_AUDIT_COMPLETED',
    'date': '2026-11-02',
    'evidence_role': 'CONSUMED_DEVELOPMENT_ONLY',
    'training_runs': 0, 'new_model_forwards': 0, 'cloud_or_ssh_calls': 0,
    'AB_new_distance_pairs': 0,
    'source_local_support_distance_rebuild': True,
    'p1_AB_bit_exact': True,
    'target_gate_reports_passed': 80,
    'source_finite_grid_zero_withdrawal_pass': True,
    'source_positive_saturation_zero_withdrawal_pass': False,
    'p_selected': False,
    'reason_no_p_selected': 'Original 5% rule does not specify keeping the starting or ending exponent of the first sub-threshold transition.',
    'production_assets_changed': False,
    'AB_and_second_verifier_inputs_post_checked': input_checks,
    'source_inputs_post_checked_by_independent_verifier': 21,
    'source_outputs_rehashed': source_output_checks,
    'artifacts': manifest,
    'collab_report': {'path': REPORT.relative_to(ROOT).as_posix(), 'sha256': report_sha},
}
out = BASE / 'VERIFICATION.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
out.with_name(out.name + '.sha256').write_text(digest(out) + '  ' + out.name + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'AB_inputs_rechecked': len(input_checks),
                  'source_outputs_rechecked': len(source_output_checks), 'audit_artifacts': len(manifest),
                  'report_sha256': report_sha, 'verification_sha256': digest(out)}, ensure_ascii=False))
