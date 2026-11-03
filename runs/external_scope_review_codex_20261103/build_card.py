"""Materialize pre-score scope and an explicitly non-executable Edge card."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, data):
    p = OUT / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (p.parent / (p.name + '.sha256')).write_text(sha(p) + '  ' + p.name + '\n', encoding='utf-8')
    return sha(p)


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


def main():
    criteria = {
        'schema': 'EXTERNAL_DATA_SCOPE_S1_S6_V1', 'status': 'REGISTERED_BEFORE_EXTERNAL_MODEL_OUTPUTS',
        'date': '2026-11-03 America/Los_Angeles',
        'authority': {'path': 'runs/mainline_docs/collab/20261102_external_scope_criteria_and_edge_review_claude.md',
                      'sha256': sha(ROOT / 'runs/mainline_docs/collab/20261102_external_scope_criteria_and_edge_review_claude.md')},
        'rules': {
            'S1': 'IoT or edge-network target with identifiable L2/L3 identity; document Pi/server role.',
            'S2': 'Original PCAP/PCAPNG with actual packet clocks; feature CSV alone is insufficient.',
            'S3': 'Same target has trusted normal observation >=7200 real seconds before evaluation, plus later normal queries; no clock shifting or joining short windows.',
            'S4': 'Attack against the target with reproducible legal packet labels supported by direction, time interval or official filters; whole-file attack labeling is insufficient.',
            'S5': 'Network-visible attacks in the threat model; payload-only/physical attacks are out of scope.',
            'S6': 'No overlap with CICIoT2022 A, UNSW2018 B or admitted history; compare MAC and provenance.'},
        'normal_gap_rule_seconds': 3600, 'gap_comparison': 'strictly greater than',
        'direction_label_evidence': 'Researcher-reconstructed attack-associated packets are allowed when provenance and direction are established; distinguish these from publisher per-packet payload truth.',
        'descriptive_only_not_selection': ['Normal protocol mix', 'Same-protocol and target-local port overlap',
                                           'Direct ACK share', 'Reference coverage', 'Target/day/event counts'],
        'prohibited_selection_inputs': ['model scores', 'FPR', 'recall', 'support', 'embedding distances'],
        'inclusion': 'Evaluate every dataset that passes the registered scope and execution prerequisites; report all outcomes.',
        'external_candidate_model_evaluations': 0}
    criteria_sha = save('SCOPE_CRITERIA.json', criteria)
    prior = read('runs/edge_iiotset_raw_qualification_v1_20261102/RESULT.json')
    ports = read('runs/external_scope_review_codex_20261103/edge_audit/RAW_PORT_SEGMENT_RESULT.json')
    attacks = read('runs/external_scope_review_codex_20261103/edge_audit/ATTACK_PORT_RESULT.json')
    prefix = read('runs/external_scope_review_codex_20261103/FIRST_WINDOW.json')
    freeze = ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'
    assert sha(freeze) == 'ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7'
    groups = ports['global_groups']
    populations = {name: sum(int(value['protocols'].get(str(p), 0)) for p in (6, 17))
                   for name, value in groups.items()}
    assert populations['ALL'] == populations['GLOBAL_FIRST_7200'] + populations['AFTER_GLOBAL_7200']
    h = attacks['HTTP']['counts']['direct_rule_HTTP_source_target_dport80']
    u = attacks['UDP']['counts']['direct_rule_UDP_dst_target_dport0']
    card = {
        'schema': 'EDGE_EXTERNAL_TEST_1_EXECUTION_CARD_DRAFT_V1',
        'status': 'SCOPE_ELIGIBLE_CONTEXT_ADAPTER_BASELINES_AND_BUDGET_PENDING',
        'date': '2026-11-03 America/Los_Angeles',
        'execution_ready': False, 'model_evaluation_authorized': False,
        'training_authorized': False, 'cloud_run_authorized': False,
        'criteria_sha256': criteria_sha,
        'scope_assessment': {'S1': 'PASS_OBSERVED_EDGE_IDENTITY_AND_DOCUMENTED_ROLE',
                             'S2': 'PASS_ORIGINAL_INTEGER_CLOCK_PCAP',
                             'S3': 'PASS_OBSERVED_UNFILTERED_FIRST_WINDOW_UNDER_REGISTERED_GAP_RULE',
                             'S4': 'PASS_RECONSTRUCTED_DIRECTION_LABEL_CONTRACT_NOT_PUBLISHER_PACKET_TRUTH',
                             'S5': 'PASS_NETWORK_VISIBLE_FLOOD',
                             'S6': 'PASS_NAMED_USED_METADATA_AND_DECLARED_RELEASE_PROVENANCE_SCOPE'},
        'method': {'freeze_path': freeze.relative_to(ROOT).as_posix(), 'sha256': sha(freeze),
                   'p': 3, 'lambda': 0.25, 'head_order': [27, 127, 227, 'ensemble'],
                   'cuts_scales_geometry_encoder': 'Unchanged; exact pins are in METHOD_FREEZE.json.',
                   'guard': 'TCP SYN=1 and ACK=0 keeps RAW for every target.',
                   'selection_reapplied': False, 'AB_development_closed': True},
        'target': {'dataset': 'Edge-IIoTset', 'IP': '192.168.0.128', 'MAC': 'dc:a6:32:fb:69:b5',
                   'role': 'Raspberry Pi 4 Model B edge/Mosquitto server', 'physical_targets': 1,
                   'not_claimed': ['Attacks on 10 sensor nodes', 'Independent multi-device confirmation',
                                   'Hardware serial identity', 'Complete encoder pretraining non-overlap']},
        'raw_inputs': prior['inputs'],
        'reference': {'mode': 'COMMISSIONING_ONLY_NO_ADMITTED_SEPARATE_HISTORY',
                      'description': 'Early trusted normal within the same capture; not cross-year historical validation.',
                      'raw_role': 'NORMAL', 't0_ns': prior['normal_t0_ns'],
                      'cutoff_ns': prior['normal_cutoff_ns'], 'observation_seconds': 7200,
                      'original_prefix_frames': [1, prefix['last_prefix_frame']],
                      'first_after_cutoff': prefix['first_strictly_after_cutoff'],
                      'selection': 'Frozen dense commissioning rule on all legal target endpoints in the complete unfiltered prefix; preserve distinct-component eligibility and RAW fallback.',
                      'new_history_or_topup_from_query_rows': False, 'external_HIST_DEV_selection': False,
                      'reference_query_roles_must_be_materialized_and_sealed_before_scores': True},
        'capture_boundaries': {'rule': 'Split original NORMAL record ranges at positive capture-order gaps >3600s; do not shift clocks, sort regressions or join segments.',
                               'normal_segments': [{k: s[k] for k in ('first_frame', 'last_frame', 'min_ns', 'max_ns', 'span_seconds')} for s in ports['segments']],
                               'context': 'Reset RECENT context at each logical-capture boundary; preserve original raw SHA/frame lineage and pin any logical-frame mapping.',
                               'bank': 'One earliest completed static bank remains causally available for later captures; never rebuild it using their normal queries.',
                               'gap_independence_scope': 'Independent context/reporting segments, not independent devices or newly onboarded reference budgets.',
                               'December_segment': 'Later normal queries only, not pre-attack reference. It need not independently supply a fresh 7200s bank.',
                               'capture_duration_caution': 'First two >1h-gap segments exceed the paper stated 3h capture maximum; these are observed time segments, not verified independent recording sessions.'},
        'context_and_population_gate': {'unfiltered_context_required': True,
                                        'same_namespace_regression': 'Keep frozen permanent poison semantics; do not repair the clock or reorder.',
                                        'cross_key_capture_regression': 'Record under frozen Contexts; not automatically equivalent to a poisoned namespace.',
                                        'invalid_or_unsupported_rows': 'Count by reason before scores and seal population/UIDs; do not turn unscored rows into correct negatives or silently drop required truth.',
                                        'complete': False},
        'labels': {
            'evidence_level': 'Researcher-reconstructed attack-associated direct direction, supported by official scenario/tool descriptions and observed traffic; not official packet payload ground truth.',
            'normal': 'Official Normal traffic/Temperature_and_Humidity file, target-owned legal TCP/UDP; other-protocol context is outside evaluated protocol scope.',
            'HTTP': {'predicate': 'origin=HTTP AND IPv4.src=192.168.0.170 AND IPv4.dst=192.168.0.128 AND eth.dst=dc:a6:32:fb:69:b5 AND IP.proto=6 AND TCP.dport=80 AND original timestamp in the pinned capture interval',
                     'flags_for_all_direct': 'All observed TCP flags remain in direct session population; do not infer maliciousness from flags alone.',
                     'ACK_no_SYN_stratum': '(flags & 0x10)!=0 AND (flags & 0x02)==0',
                     'guard_stratum': '(flags & 0x02)!=0 AND (flags & 0x10)==0',
                     'ACK_only': 'flags==0x10', 'PSH_ACK': 'flags==0x18',
                     'reported_flags': attacks['HTTP']['HTTP_direct_flags'],
                     'captured_interval_ns': [prior['inputs']['HTTP']['UTC_range'][0], prior['inputs']['HTTP']['UTC_range'][1]],
                     'ACK_control_semantics': 'ACK/FIN/handshake are attack-session control traffic, not independent ACK floods; GET starts (19076 observed) and payload-containing packets are reported separately.'},
            'UDP': {'predicate': 'origin=UDP AND IPv4.dst=192.168.0.128 AND eth.dst=dc:a6:32:fb:69:b5 AND IP.proto=17 AND UDP.dport=0 AND original timestamp in the pinned capture interval',
                    'source_policy': 'No four-IP whitelist: the authors describe source spoofing; do not pretend random source IPs are independent attackers.',
                    'port_zero': 'Observed header value; preserve frozen legal endpoint range 0..65535.'},
            'outside_attack_direction': 'Retain for full unfiltered context and separate audit; exclude from normal/attack scored truth and every reference bank.',
            'public_HTTP_counterpart': '216.58.198.74:80 exchanges with target local port42162 are background-role traffic, not attacker->target:80.',
            'publication_claim': 'Direct attack-associated packet recall, with control/GET/payload strata; not detection probability of independent attacks.'},
        'header_populations_before_context_eligibility': {'normal_full_TCP_UDP': populations['ALL'],
                                                        'normal_first_7200_TCP_UDP': populations['GLOBAL_FIRST_7200'],
                                                        'normal_primary_TCP_UDP': populations['AFTER_GLOBAL_7200'],
                                                        'HTTP_direct': h, 'HTTP_ACK_no_SYN': 88262,
                                                        'HTTP_ACK_only': 7817, 'HTTP_PSH_ACK': 77043,
                                                        'HTTP_SYN_guarded': 61641, 'UDP_direct': u,
                                                        'all_direct': h+u,
                                                        'not_yet_final_encoded_query_counts': True},
        'difficulty_descriptive_only': {'normal_TCP': 1332428, 'normal_UDP': 2430,
                                       'normal_target_local_TCP80_full_first_post': [0, 0, 0],
                                       'normal_target_local_UDP0_full_first_post': [0, 0, 0],
                                       'same_protocol_present': {'TCP': True, 'UDP': True},
                                       'interpretation': 'Service/traffic-distribution shift, not absent UDP protocol; ports are component metadata rather than direct numeric RECENT header-token features. Do not predict detector success from this.'},
        'metrics_draft': {'views': ['full', 'post_window_primary'],
                          'primary': 'Same-population per-packet ensemble FPR, recall, FP/FN and counts; all four heads and each segment/scenario/flags stratum also reported.',
                          'full_causal_rule': 'Before bank closure keep RAW; after closure use only the fixed completed bank.',
                          'normal_weight_proposal': ['device', 'logical_capture_segment', 'canonical_component'],
                          'attack_weight_proposal': ['device', 'scenario_capture', 'canonical_component'],
                          'weight_allocation': 'Equal child mass at each level; normalize normal and attack separately. These are external weights, not A/B-identical metrics.',
                          'event_report': 'Two scenario capture groups; exact number of repeated official events unknown. No invented UNKNOWN event pass or claim millions of independent attacks.',
                          'safety': 'Cumulative TP withdrawals relative to RAW, device<=1pp and available scenario<=5pp, low-RAW-recall group zero TP withdrawal; retain frozen four-head safety logic, mark missing truth NOT_EVALUABLE.',
                          'uncertainty': 'No naive binomial/Wilson CI on weighted or correlated packets. Show counts and per-day/scenario limits; cluster scheme must be sealed before scores.',
                          'schema_frozen': False},
        'methods': {'required_comparisons': ['RAW', 'same-bank C2/p1', 'C5/p3'],
                    'same_bank_p1_is_strong_baseline': False,
                    'strong_baseline': 'Must be selected, implemented and source-calibrated under the same normal-information/time budget before external scores; not ready.'},
        'resources': {'CPU': None, 'RAM_bytes': None, 'wall_seconds': None,
                       'distance_pairs': None, 'unique_encoding_rows': None,
                       'location': None, 'raw_bytes_already_present': 621736430,
                       'population_sampling': 'No subsampling authorized/fixed here; any feasibility sampling must be specified before scores and the card resealed.',
                       'automatic_resubmit_or_budget_extension': False},
        'required_before_execution': ['Close real decoder/context/physical-lineage/UID population gates',
                                       'Implement isolated external adapter without changing numeric core and verify source parity',
                                       'Seal external metrics, uncertainty scheme, query population and baselines',
                                       'Fill resource/runtime bounds and pass same-delivery real-slice E2E',
                                       'Obtain actual external-evaluation authorization'],
        'progress': {'Codex_right_panel': True, 'continuous_AI_monitoring': False},
        'outcome_policy': 'Report failures; no external-output-driven p/lambda/cut/radius/bank/salt adjustment or dataset selection.'}
    # Intervals are exact original epoch nanoseconds; UTC strings remain in raw_inputs.
    card['labels']['HTTP']['captured_interval_ns'] = [1637836529350784000, 1637836801284354000]
    card['labels']['UDP']['captured_interval_ns'] = [1637792830139612000, 1637793231047885000]
    card_sha = save('EDGE_EXECUTION_CARD_DRAFT.json', card)
    print(json.dumps({'criteria_sha256': criteria_sha, 'card_sha256': card_sha,
                      'header_normal_full': populations['ALL'], 'header_normal_primary': populations['AFTER_GLOBAL_7200'],
                      'header_direct_attacks': h+u, 'execution_ready': False}))


if __name__ == '__main__':
    main()
