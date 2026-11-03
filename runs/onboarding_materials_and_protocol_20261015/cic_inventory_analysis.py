"""CIC metadata-only material inventory. No PCAP decode, scores, model or training.

Reads the already consumed two-device DEV roster only. Historical HOLDOUT is
summarized from reference costs; no holdout query manifest is opened.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREP = ROOT / 'runs/legacy_reference_sample_preparation_v1_20260917'
PULL = ROOT / 'runs/legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891'
DEVICES = ['Eufy Home Base', 'HeimVision Camera']
pins = {}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def pin(path, expected=None):
    size = path.stat().st_size
    record = {'absolute_path': path.as_posix(), 'bytes': size}
    if size <= 16 * 1024**2:
        record.update(sha256=digest(path), sha256_status='RECOMPUTED_SMALL_METADATA')
        if expected:
            assert record['sha256'] == expected
    else:
        record.update(sha256=expected, sha256_status='EXISTING_FROZEN_PIN_NOT_REHASHED_THIS_INVENTORY')
    pins[path.relative_to(ROOT).as_posix()] = record
    return path


def read(path):
    return json.loads(pin(path).read_text(encoding='utf-8'))


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def uid_hash(rows):
    return hashlib.sha256(('\n'.join(sorted(r['uid'] for r in rows)) + '\n').encode()).hexdigest()


def counts(rows):
    return {name: sum(r['label'] == label for r in rows) for label, name in [(0, 'normal'), (1, 'attack')]}


def load_gzip(path, expected=None):
    pin(path, expected)
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def raw_record(c):
    p = Path(c['path'])
    return {'capture_id': c['capture_id'], 'original_member': c['member_path'],
            'absolute_path': p.as_posix(), 'publisher_provenance': c['provenance'],
            'catalog_activity': c['mode'], 'catalog_use': c['use'],
            'first_timestamp': c['first'], 'last_timestamp': c['last'],
            'first_utc': iso(c['first']), 'last_utc': iso(c['last']),
            'catalog_bytes': c['bytes'], 'local_exists': p.exists(),
            'local_bytes': p.stat().st_size if p.exists() else None,
            'size_matches_catalog': p.exists() and p.stat().st_size == c['bytes'],
            'historical_source_sha256': c['sha256'], 'raw_sha_recomputed_this_inventory': False}


def main():
    index = read(PREP / 'finalized/manifest_index.json')
    catalog = read(PREP / 'capture_catalog.json')
    by_capture = {c['capture_id']: c for c in catalog}
    costs = read(PREP / 'finalized/reference_costs.json')
    refs_all = load_gzip(PREP / 'finalized/references.jsonl.gz', index['REFERENCE']['sha256'])
    dev = load_gzip(PREP / 'finalized/dev.jsonl.gz', index['DEV']['sha256'])
    assert len(dev) == 179886 and {r['device'] for r in dev} == set(DEVICES)
    assert uid_hash(dev) == index['DEV']['sorted_uid_lines_sha256']
    assert len({r['uid'] for r in dev}) == len(dev)
    sessions = read(PREP / 'captures/active-00_sessions.json')
    prior = read(ROOT / 'runs/legacy_commissioning_policy_v1_20260924/metadata_feasibility.json')
    policy = read(ROOT / 'runs/legacy_commissioning_policy_v1_20260924/commissioning_policy.json')
    parent = read(PULL / 'design_contract.json')
    assert parent['data']['source_manifests']['DEV'] == index['DEV']
    assert parent['data']['reference_counts']['CIC_DEV'] == 75
    active = sorted((c for c in catalog if c['provenance'] == 'normal' and c['mode'] == 'ACTIVE_UNANNOTATED'), key=lambda c: (c['first'], c['capture_id']))
    chosen = active[0]
    assert chosen['capture_id'] == 'active-00'
    t0 = chosen['first']
    assert chosen['last'] >= t0 + 7200
    summaries = []
    for name in DEVICES:
        rows = [r for r in dev if r['device'] == name]
        refs = [r for r in refs_all if r['device'] == name]
        cost = next(c for c in costs if c['device'] == name)
        old_protocols = {str(p): len({r['component_id'] for r in refs if r['protocol'] == p}) for p in [6, 17]}
        windows = {}
        for seconds in [3600, 7200]:
            cutoff = t0 + seconds
            inside = [r for r in rows if r['capture_id'] == chosen['capture_id'] and t0 <= r['timestamp'] <= cutoff]
            future = [r for r in rows if r['timestamp'] > cutoff]
            past = [r for r in rows if r['timestamp'] <= cutoff]
            assert all(r['label'] == 0 for r in inside)
            component_sets = {p: {r['component_id'] for r in inside if r['protocol'] == p} for p in [6, 17]}
            started = {p: {s['component_id'] for s in sessions if s['device'] == name and s['protocol'] == p and s['first'] <= cutoff} for p in [6, 17]}
            # This quota is only illustrative on saved endpoints. It is not a bank.
            quotas = {6: 0, 17: 0}
            while sum(quotas.values()) < 64:
                changed = False
                for p in [6, 17]:
                    if sum(quotas.values()) < 64 and quotas[p] < len(component_sets[p]):
                        quotas[p] += 1
                        changed = True
                if not changed:
                    break
            windows[str(seconds)] = {
                'cutoff_timestamp': cutoff, 'cutoff_utc': iso(cutoff),
                'raw_capture_spans_entire_window': True,
                'capture_continuity_health': 'UNKNOWN_NOT_CERTIFIED_BY_TIMESTAMPS',
                'saved_endpoint_count': len(inside),
                'distinct_components_with_saved_endpoint_lower_bound': {str(p): len(v) for p, v in component_sets.items()},
                'components_with_session_start_by_cutoff_not_legal_endpoint_proof': {str(p): len(v) for p, v in started.items()},
                'quota_if_only_saved_endpoint_components_existed_not_a_selected_bank': quotas,
                'saved_endpoint_time_range': [min(r['timestamp'] for r in inside), max(r['timestamp'] for r in inside)] if inside else None,
                'saved_endpoint_activity_counts': dict(Counter(r['activity'] for r in inside)),
                'saved_endpoint_quarter_counts': {str(q): sum(min(3, int((r['timestamp']-t0)/(seconds/4))) == q for r in inside) for q in range(4)},
                'future_fixed_uid_counts': counts(future),
                'at_or_before_cutoff_fixed_uid_counts': counts(past),
                'same_capture_future_fixed_uid_counts': counts([r for r in future if r['capture_id'] == chosen['capture_id']]),
                'future_uid_set_sha256': uid_hash(future),
                'new_recent_frontend_reference_targets': 'NOT_MATERIALIZED',
                'reference_features_and_q14': 'NOT_PREPARED',
                'activity_stratification': 'UNKNOWN_PASSIVE_ONLY; ACTIVE_UNANNOTATED is not a verified functional activity',
                'readiness': 'NORMAL_RAW_PRESENT_AND_LATER_NORMAL_ATTACK_PAIRING_AVAILABLE; CAUSAL_BANK_MATERIALIZATION_PENDING'
            }
        one = windows['3600']
        prior_d = next(r for r in prior['devices'] if r['device'] == name)
        assert one['saved_endpoint_count'] == prior_d['saved_normal_query_endpoints_inside_window']
        assert one['distinct_components_with_saved_endpoint_lower_bound'] == prior_d['distinct_components_with_saved_legal_endpoint']
        assert one['future_fixed_uid_counts'] == prior_d['future_rows_in_existing_manifest']
        time_ranges = {label: {'first': min(r['timestamp'] for r in rows if r['label']==y), 'last': max(r['timestamp'] for r in rows if r['label']==y)} for y,label in [(0,'normal'),(1,'attack')]}
        summaries.append({
            'device': name, 'role': 'CIC_DEV_ALREADY_CONSUMED_DEVELOPMENT',
            'fixed_query_counts': counts(rows), 'fixed_query_uid_sha256': uid_hash(rows),
            'fixed_query_protocol_counts': {str(p): counts([r for r in rows if r['protocol']==p]) for p in [6,17]},
            'query_time_ranges': {k: dict(v,first_utc=iso(v['first']),last_utc=iso(v['last'])) for k,v in time_ranges.items()},
            'old_bank': {'rows': len(refs), 'distinct_components_by_protocol': old_protocols,
                         'first_selected_timestamp': min(r['timestamp'] for r in refs),
                         'last_selected_timestamp': max(r['timestamp'] for r in refs),
                         'reference_cutoff': cost['reference_end'], 'reference_cutoff_utc': iso(cost['reference_end']),
                         'observation_start': cost['observation_interval_start'],
                         'captured_seconds_sum': cost['observed_seconds_sum'],
                         'wall_span_seconds': cost['reference_end']-cost['observation_interval_start'],
                         'activities': cost['selected_activities'],
                         'reference_uids': sorted(r['uid'] for r in refs),
                         'sources': [raw_record(by_capture[c]) for c in cost['observed_capture_ids']],
                         'every_fixed_query_is_after_old_cutoff': all(r['timestamp'] > cost['reference_end'] for r in rows)},
            'new_policy_windows': windows,
        })
    result = {
        'status': 'METADATA_MATERIAL_INVENTORY_COMPLETE_NOT_BANK_OR_EXPERIMENT_IMPLEMENTATION',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': DEVICES, 'parent_job': 177891,
        'fixed_query_rows': len(dev), 'fixed_query_uid_sha256': uid_hash(dev),
        'fixed_query_source_matches_job177891_contract': True,
        'new_policy_t0': t0, 'new_policy_t0_utc': iso(t0),
        'source_selection': policy['observation']['archive_projection'],
        'active_source': raw_record(chosen),
        'other_active_sources_existing_inventory_only': [raw_record(c) for c in active[1:]],
        'devices': summaries,
        'historical_three_device_reference_status_only': [
            {'device': c['device'], 'old_reference_rows': c['selected'], 'old_reference_end': c['reference_end'],
             'query_access_this_inventory': False, 'independent_confirmation_status': 'ALREADY_CONSUMED; NOT_REOPENED'}
            for c in costs if c['partition'] == 'DEVICE_HOLDOUT'],
        'field_availability': {
            'uid_owner_device_capture_timestamp_frame_component_protocol': 'PRESENT_IN_QUERY_REFERENCE_METADATA',
            'normal_provenance': 'PUBLISHER_DECLARED_NORMAL_CAPTURE; CHECKED_OLD_RECEIPTS',
            'current_target_direction': 'NOT_IN_ROW_MANIFEST',
            'whole_capture_direction_counts': 'PRESENT_IN_SESSION_METADATA_BUT_NOT_SAFE_AS_CUTOFF_LOCAL_SELECTION_FIELD',
            'active_operation_labels': 'ABSENT; ALL_WINDOW_ROWS_ACTIVE_UNANNOTATED',
            'operation_log_capture_health': 'ABSENT',
            'current_recent_reference_endpoints': 'NOT_MATERIALIZED_FOR_NEW_BANKS'},
        'interpretation': [
            'B0/B1/B2 have existing normal raw files spanning 1h and 2h plus later fixed normal and attack queries; readiness is conditional on causal bank materialization, not NOT_AVAILABLE.',
            'Saved endpoints are full-capture-sampled historical rows. Counts are availability lower bounds, not all packets or a valid online bank selector.',
            'Session start can precede the first legal target. A session-start count alone is not legal reference evidence.',
            'B1 can compare fixed time strata at equal protocol quotas; verified functional-activity diversity is unavailable here.',
            'At both windows Eufy has no proved TCP components and Heim has only one. 2h does not establish repair of the TCP coverage gap.',
            'OLD_BANK remains the main integration anchor; chronological Active acquisition is not presumed superior to the older interaction bank.',
            'All fixed original query UIDs remain in the full report; before-cutoff queries fall back to the same head. Common-later comparison uses the 2h cutoff and unchanged original weights with explicit subset normalization.',
            'Same-component later continuation is allowed but reported separately; no self-reference or future target may enter a bank.',
            'New references need their own causal recent E3/q14 materialization; preserve source FIT/CAL roles and never turn source CAL query rows into a reference bank.',
            'No rates, scores, new experiment outcomes or threshold choices were computed.'
        ],
        'sources': pins,
        'execution_boundary': {'pcap_decode':0,'model_forward':0,'optimizer_updates':0,'score_reads':0,'holdout_query_reads':0,'remote_actions':0,'sealed_file_changes':0}
    }
    (HERE/'cic_inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'devices': [{'device':s['device'],'old_protocol_components':s['old_bank']['distinct_components_by_protocol'],'windows':s['new_policy_windows']} for s in summaries]},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
