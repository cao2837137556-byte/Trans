"""Write preparation-only manifests from existing metadata and freeze receipts."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
FREEZE = ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = BASE / name
    assert not path.exists(), str(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')


facts = read(BASE / 'acquisition/FACTS_AND_MINIMUM_ROLES.json')
freeze = read(FREEZE)
assert freeze['p'] == 3 and freeze['method_frozen'] and freeze['AB_development_line_closed']
roles = facts['minimum_acquisition_roles']
for role in roles:
    role.update({'official_download_url': None, 'sha256': None,
                 'selected': False, 'qualification_pass': False})
manifest = {
    'schema': 'CICIoMT2024_ACQUISITION_MANIFEST_DRAFT_V1',
    'status': 'LEAF_MANIFEST_AND_RAW_QUALIFICATION_PENDING',
    'date': '2026-11-02',
    'registration_entry': facts['registration_url'],
    'official_description': facts['official_url'],
    'author_preprint': facts['author_preprint_url'],
    'existing_user_registration_session_state': 'NOT_INSPECTED',
    'raw_found_in_scanned_project_directories': False,
    'personal_downloads_checked': False,
    'registered_directory_snapshot': None,
    'device_table_with_verified_MAC_IP': None,
    'attack_schedule_and_direction_specification': None,
    'candidate_real_wifi_targets_from_author_preprint': facts['primary_author_preprint_facts']['target_names'],
    'minimum_roles': roles,
    'file_count_not_equal_to_role_count': True,
    'qualification_subset_not_final_evaluation_population': True,
    'selection_rule': 'Cover all required qualification roles with minimum verified total bytes; metadata only; deterministic normalized relative-path tie break; retain exclusion ledger.',
    'model_score_based_selection': False,
    'final_population_rule': 'All metadata-qualified physical Wi-Fi devices by default; resource-limited subset and count/coverage criteria must be locked before model scores.',
    'required_ACK': 'Direct labeled attack TCP ACK=1,SYN=0 against admitted physical targets; reverse responses/SYN+ACK/simulated-only traffic do not substitute.',
    'required_UDP': 'Direct labeled UDP attack traffic with official event/direction mapping.',
    'observation_seconds': 7200,
    'total_download_bytes': None,
    'destination': {'path': None, 'verified_free_bytes': None, 'verified_quota_bytes': None,
                    'prefer_personal_HPC_storage_for_large_data': True},
    'large_download_started': False,
    'external_evaluation_started': False,
}
write('ACQUISITION_MANIFEST_DRAFT.json', manifest)
card = {
    'schema': 'C5_EXTERNAL_CONFIRMATION_DRAFT_V1',
    'status': 'DRAFT_NOT_EXECUTION_READY',
    'date': '2026-11-02',
    'method_freeze': {'path': FREEZE.relative_to(ROOT).as_posix(), 'sha256': sha(FREEZE), 'p': 3},
    'dataset_candidate': 'CICIoMT2024 physical Wi-Fi/IP subset',
    'execution_authorized': False,
    'raw_acquisition_complete': False,
    'raw_qualification_pass': False,
    'external_evaluations': 0,
    'comparison_methods': ['RAW', 'SAME_BANK_C2_P1', 'C5_P3'],
    'strong_baseline_status': 'Not selected/implemented/calibrated; do not claim readiness; freeze any included baseline before first external scores.',
    'head_order': [27, 127, 227, 'ensemble'],
    'views': ['full', 'post_window_primary'],
    'observation_seconds': 7200,
    'p_selection_reapplied_on_external': False,
    'AB_development_line_closed': True,
    'reference_material_modes': ['FULL_LEGAL_HISTORY_PLUS_COMMISSIONING', 'COMMISSIONING_ONLY_NO_HISTORY'],
    'reference_roles_and_boundaries': None,
    'device_roster_and_MAC_IP': None,
    'qualified_raw_manifest_sha256': None,
    'query_population_and_UID_manifest_sha256': None,
    'labels_events_directions_schema_sha256': None,
    'ACK_UDP_qualification_receipt': None,
    'sample_adequacy_preregistration': {
        'min_post_window_normal_queries_per_device': None,
        'min_direct_ACK_attack_queries': None,
        'min_direct_UDP_attack_queries': None,
        'independent_capture_day_event_requirements': None,
        'uncertainty_estimation_and_precision_targets': None,
        'must_be_fixed_before_scores': True,
    },
    'primary_endpoint': 'post_window_primary ensemble unweighted FPR and recall, FP/FN/counts',
    'targets_under_test': {'pool_unweighted_FPR_max': 0.02, 'pool_unweighted_recall_min': 0.99,
                          'all_devices_under_2pct_not_assumed': True},
    'weighted_schema': {
        'status': 'PROPOSED_REQUIRES_METADATA_VALIDATION_AND_PRE_SCORE_SEAL',
        'normal': ['device', 'logical_capture', 'component'],
        'attack': ['device', 'official_event', 'component'],
        'allocation': 'equal mass per child at each level; normalize normal and attack separately',
        'missing_event_policy': 'NOT_EVALUABLE; never fabricate UNKNOWN to pass a safety gate',
        'final_schema_sha256': None,
    },
    'safety': {'baseline': 'RAW cumulative withdrawals', 'device_weighted_loss_max_pp': 1.0,
               'activity_or_available_event_weighted_loss_max_pp': 5.0,
               'low_RAW_recall_group_requires_zero_TP_withdrawal': True,
               'direct_ACK_and_UDP_separate_counts_and_recall_required': True,
               'empty_or_unknown_truth_gate': 'NOT_EVALUABLE',
               'one_pool_top_level_report_count': 8},
    'external_adapter': {'status': 'NOT_IMPLEMENTED', 'changes_limited_to': ['dataset identity/time/label wiring', 'registered external metric schema'],
                         'numeric_core_changes_allowed': False, 'source_and_synthetic_parity_checks_required': True},
    'budget': {'CPU': None, 'RAM_bytes': None, 'wall_seconds': None, 'distance_pairs': None,
               'unique_encoding_rows': None, 'raw_and_intermediate_bytes': None, 'location': None,
               'automatic_budget_extension': False},
    'runtime': {'required_identity_check': True, 'HPC_python_if_used': '3.11, exact environment to verify',
                'checkpointed_encoding_batches': True, 'reuse_verified_completed_arrays': True,
                'automatic_resubmit': False},
    'progress': {'Codex_right_panel': True, 'continuous_AI_monitoring': False},
    'activation_conditions': ['raw files obtained and SHA/bytes verified', 'all raw qualification requirements satisfied',
                              'population/roles/labels/metrics/adequacy/baselines fixed before scores',
                              'external adapter engineering checks passed', 'budget/runtime paths verified',
                              'actual evaluation authorized'],
    'failure_policy': 'Preserve and report failed external confirmation; no p/lambda/cut/geometry/bank retuning on external outcomes.',
}
write('EXECUTION_CARD_DRAFT.json', card)
files = [
    ROOT / 'runs/mainline_docs/collab/20261102_c5_p3_method_freeze_receipt_codex.md',
    ROOT / 'runs/mainline_docs/collab/20261102_ciciomt2024_acquisition_checklist_codex.md',
    ROOT / 'runs/mainline_docs/collab/20261102_c5_external_test_execution_card_draft_codex.md',
    BASE / 'ACQUISITION_MANIFEST_DRAFT.json', BASE / 'EXECUTION_CARD_DRAFT.json',
    BASE / 'acquisition/ACQUISITION_RESEARCH.md', BASE / 'acquisition/FACTS_AND_MINIMUM_ROLES.json',
    BASE / 'contract/CONTRACT_REVIEW.md', FREEZE,
]
artifacts = {}
for path in files:
    artifacts[path.relative_to(ROOT).as_posix()] = sha(path)
    path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')
write('PREPARATION_RECEIPT.json', {
    'status': 'PASS_PREPARATION_COMPLETE_NOT_EXECUTION', 'date': '2026-11-02',
    'method_frozen_p': 3, 'AB_development_frozen': True,
    'public_HTML_bytes_saved': 100126, 'registration_submissions': 0, 'raw_PCAP_downloads': 0,
    'external_model_forwards': 0, 'external_distance_pairs': 0, 'external_evaluations': 0,
    'training_runs': 0, 'cloud_runs': 0,
    'raw_leaf_names_verified': False, 'ACK_attack_qualification_verified': False,
    'artifacts': artifacts,
})
print(json.dumps({'status': 'PASS_PREPARATION_COMPLETE_NOT_EXECUTION', 'artifacts': len(artifacts),
                  'execution_ready': False, 'method_p': 3}, ensure_ascii=False))
