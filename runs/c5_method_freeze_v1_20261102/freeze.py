"""Record the authorized p=3 decision; read saved evidence only, no evaluation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
C4 = ROOT / 'runs/history_sample_coverage_c4_batch_resume_v1_20261102'
AUDIT = ROOT / 'runs/c5_kernel_independent_replay_codex_20261102'
DECISION = ROOT / 'runs/mainline_docs/collab/20261102_c5_kernel_decision_claude.md'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')


assert not (HERE / 'METHOD_FREEZE.json').exists(), 'Do not overwrite a freeze receipt'
decision_text = DECISION.read_text(encoding='utf-8-sig')
assert '## 4.' in decision_text and '**冻结 C5 = 支持凹核 p=3。**' in decision_text
audit_receipt = read(AUDIT / 'VERIFICATION.json')
ab = read(AUDIT / 'ab/RESULT.json')
source = read(AUDIT / 'source_cal/RESULT.json')
assets = read(C4 / 'config/ASSETS.json')
card = read(C4 / 'EXECUTION_CARD.json')
input_manifest = read(C4 / 'INPUT_MANIFEST.json')
pins = {}


def pin(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected is not None:
        assert actual == expected, (str(path), actual, expected)
    rel = path.relative_to(ROOT).as_posix()
    pins[rel] = {'sha256': actual, 'bytes': path.stat().st_size, 'verified_now': True}
    return rel


# The previous audit is immutable. Its discussion document was intentionally
# amended after the audit; the new authority is bound separately below.
for rel in [
    'ab/replay.py', 'ab/RESULT.json', 'ab/SUMMARY.json',
    'ab/CIC_DEV_REPLAY.npz', 'ab/UNSW_DEV_REPLAY.npz',
    'AB_SAVED_ARRAY_VERIFICATION.json', 'METRIC_TABLES.md',
    'source_cal/RESULT.json', 'source_cal/p3_DECISIONS.npz',
    'source_cal/P1_179602_IDENTITY.json', 'source_cal/SAVED_ARRAY_VERIFICATION.json',
    'source_cal/CAP_REACHABLE_ATTACK_CASES.json',
]:
    path = AUDIT / rel
    expected = audit_receipt['artifacts'][path.relative_to(ROOT).as_posix()]['sha256']
    pin(path, expected)
pin(AUDIT / 'VERIFICATION.json')
pin(ROOT / audit_receipt['collab_report']['path'], audit_receipt['collab_report']['sha256'])
for name in ['config/ASSETS.json', 'INPUT_MANIFEST.json', 'EXECUTION_CARD.json',
             'config/ENCODER_RUNTIME_FILES.json', 'FINAL_ACCEPTANCE.json']:
    pin(C4 / name)
pin(C4 / 'outputs/evaluation/RESULT.json', read(C4 / 'FINAL_ACCEPTANCE.json')['result_sha256'])
for name in ['topup_selector.py', 'hnr/selection.py', 'hnr/component_selection.py',
             'hnr/encoding.py', 'hnr/evaluation.py', 'hnr/common.py']:
    pin(C4 / name, card['code_sha256'][name])
for name in ['constrained_onboarding_core_v3.py', 'constrained_onboarding_reference_v2.py',
             'constrained_onboarding_query_tail_adapter_v2.py',
             'onboarding_dense_reference_v1.py', 'continuous_input_v3.py']:
    rel = 'repo/ood/' + name
    pin(ROOT / rel, input_manifest['local_inputs'][rel])
metric_rel = 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py'
pin(ROOT / metric_rel, ab['input_sha256'][metric_rel])
for item in assets['calibration'].values():
    pin(ROOT / item['path'], item['sha256'])
pin(ROOT / assets['heads']['design']['path'], assets['heads']['design']['sha256'])
for endpoint in assets['heads']['endpoints'].values():
    for item in endpoint.values():
        pin(ROOT / item['path'], item['sha256'])
pin(DECISION)
pin(Path(__file__))
snapshot = HERE / 'DECISION_AUTHORITY_SNAPSHOT.md'
snapshot.write_bytes(DECISION.read_bytes())
snapshot.with_name(snapshot.name + '.sha256').write_text(sha(snapshot) + '  ' + snapshot.name + '\n', encoding='utf-8')
assert ab['summary']['3']['all_16_gates_pass']
assert source['candidates']['p3']['protection']['strict_source_zero_withdrawal_pass']
assert all(p['p1_logits_decisions_and_reports_bit_exact'] for p in ab['pools'].values())
calibration = {name: read(ROOT / assets['calibration'][name]['path'])
               for name in ['cuts', 'scales', 'geometry']}
freeze = {
    'schema': 'C5_METHOD_FREEZE_V1',
    'status': 'FROZEN_C5_P3_DEVELOPMENT_COMPLETE',
    'date': '2026-11-02',
    'method': 'C5_SUPPORT_CONCAVE_KERNEL_P3',
    'method_frozen': True,
    'AB_development_line_closed': True,
    'further_AB_method_search': False,
    'evidence_role': 'CONSUMED_DEVELOPMENT_ONLY',
    'authority': {'user_instruction': 'C5 已冻结为 p=3；据 Claude 第4节更新入口和冻结回执；A/B开发线冻结',
                  'document': DECISION.relative_to(ROOT).as_posix(), 'sha256': sha(DECISION),
                  'section': 4, 'snapshot': snapshot.relative_to(ROOT).as_posix()},
    'p': 3, 'lambda': 0.25,
    'support': 's=clip(1-second_joint,0,1), from two distinct eligible components of the same legal bank; unavailable support=0',
    'kernel': 'g(0)=0; g(s)=1-(1-s)^3 for s>0',
    'correction': 'raw[j] - (0.25*scale[j])*g(s)',
    'guard': '(q14[0]==1) & (q14[2]==1) & (q14[5]==0); all devices; guarded query keeps RAW',
    'head_order': [27, 127, 227],
    'ensemble': 'seed-major float64 mean in order 27,127,227; strict score > ensemble_cut',
    'individual_decision': 'strict score > source cut[j]',
    'calibration': calibration,
    'observation_seconds': 7200,
    'reference_policy': {
        'preserve': 'frozen same-device/partition/protocol eligibility, two distinct components, causal availability and RAW fallback',
        'commissioning': 'frozen dense RECENT input/selection contracts',
        'history': 'only admitted trusted same-device normal history; preserve original C1 allocation/C3 small-bank completion/C4 top-up contracts',
        'C4_additional_cap_per_device_protocol': 4096,
        'C4_hash_salt': 'C4_HISTORY_SAMPLE_COVERAGE_V1_20261101',
        'C4_is_flat_total_bank_cap': False,
        'source_donor_banks_are_external_device_banks': False,
        'external_dataset_adapter_ready': False,
    },
    'selection_provenance': {
        'posthoc_after_AB_results_known': True,
        'safe_registered_grid': [1, 2, 3, 4],
        'objective': 'HIST_DEV ensemble unweighted false-positive count',
        'denominator': 'p1 FP minus positive-support-saturation FP',
        'denominator_rows': 347,
        'fp_counts': {'1': 2219, '2': 1953, '3': 1893, '4': 1885, 'positive_saturation': 1872},
        'first_transition_below_fraction': {'from': 3, 'to': 4, 'removed_fp': 8,
                                          'fraction': 8 / 347, 'threshold': 0.05},
        'stop_semantics': 'keep the smaller p of the first qualifying transition',
        'selected_p': 3,
        'full_registered_grid_reported': True,
        'reapply_selection_on_external_data': False,
    },
    'development_primary_ensemble': ab['summary']['3']['primary_ensemble'],
    'target_protection': {'passed': 16, 'total': 16, 'baseline': 'cumulative relative to RAW'},
    'source_CAL_p3_strict_zero_withdrawal': True,
    'source_saturation_strict_zero_withdrawal': False,
    'limitations': [
        'p2 B primary sample FPR=2.133147%; not all finite-grid candidates meet 2%',
        'p3 A adds 108 HeimVision ACK-only labeled-query misses vs C4; total FN=141 and sample recall=99.821645%',
        'p3 WEMO Power sample FPR=3.085662%, Netatmo=2.278787%',
        'p3 full B sample FPR=2.235920%',
        'All B attacks are SYN guarded; no direct B ACK/UDP risk evidence',
        'A ACK-labeled misses do not provide independent UDP attack protection evidence',
        'External data and adapter are not yet qualified or evaluated',
    ],
    'external_evaluation_started': False,
    'new_training_or_evaluation_in_this_freeze': False,
    'immutable_asset_pins': pins,
    'encoder_weights_identity': {
        'binding_manifest': 'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ENCODER_RUNTIME_FILES.json',
        'weights_sha256': read(C4 / 'config/ENCODER_RUNTIME_FILES.json')['files']['vendor/netFound-base/model.safetensors'],
        'weights_rehashed_in_this_document_update': False,
        'require_full_runtime_identity_check_before_external_inference': True,
    },
    'intentional_document_amendment': {
        'path': DECISION.relative_to(ROOT).as_posix(),
        'pre_decision_hash_in_original_audit': ab['input_sha256'][DECISION.relative_to(ROOT).as_posix()],
        'current_section4_authority_sha256': sha(DECISION),
        'original_audit_receipt_rewritten': False,
    },
}
save(HERE / 'METHOD_FREEZE.json', freeze)
verification = {
    'status': 'PASS_FREEZE_RECEIPT', 'method': freeze['method'], 'p': 3,
    'source_and_target_saved_evidence_verified': True, 'p1_identity_previously_verified': True,
    'scientific_artifacts_pinned_now': len(pins), 'original_scientific_assets_modified': False,
    'no_training_no_new_encoding_no_new_evaluation': True,
    'method_freeze_sha256': sha(HERE / 'METHOD_FREEZE.json'),
    'authority_sha256': sha(DECISION),
}
save(HERE / 'VERIFICATION.json', verification)
print(json.dumps(verification, ensure_ascii=False))
