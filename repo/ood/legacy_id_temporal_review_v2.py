"""Review saved qualification metadata; never decode captures or load models."""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'runs/legacy_id_temporal_qualification_v1_20260916'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 ** 2), b''):
            h.update(block)
    return h.hexdigest()


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(path, values):
    path.write_text(''.join(json.dumps(v, ensure_ascii=False, allow_nan=False) + '\n' for v in values), encoding='utf-8')


def separate(candidates, packets, exposures):
    """Exclude old context anywhere in scope; retain one capture per session.

    The old context union is conservative: all packets in an exposed canonical
    session up to its final old actual/semantic target, not just last L events.
    Candidate context includes every packet up to that session's final target.
    """
    old_sessions, old_ends, direct_old = set(), {}, set()
    for e in exposures:
        member = e['member']
        for frame_key, session_key in (
            ('actual_cached_frame_1based', 'actual_session_key_sha256'),
            ('semantic_timestamp_frame_1based', 'semantic_session_key_sha256'),
        ):
            frame, sk = e[frame_key], e[session_key]
            direct_old.add(packets[member][frame - 1]['packet_sha256'])
            if sk is not None:
                old_sessions.add(sk)
                old_ends[member, sk] = max(old_ends.get((member, sk), 0), frame)
    old_context = [p for member, ps in packets.items() for p in ps
                   if p['session_key_sha256'] is not None
                   and p['frame_number_1based'] <= old_ends.get((member, p['session_key_sha256']), 0)]
    old_digests = direct_old | {p['packet_sha256'] for p in old_context}
    candidate_groups = collections.defaultdict(list)
    for c in candidates:
        candidate_groups[c['raw_member'], c['session_key_sha256']].append(c)
    excluded, admissible, context_by_group = [], [], {}
    for key, values in sorted(candidate_groups.items()):
        member, sk = key
        last_frame = max(v['frame_number_1based'] for v in values)
        context = [p for p in packets[member] if p['session_key_sha256'] == sk and p['frame_number_1based'] <= last_frame]
        context_by_group[key] = context
        overlap = sorted({p['packet_sha256'] for p in context} & old_digests)
        reason = 'CANONICAL_SESSION_EXPOSED_IN_OLD_FIT_SELECT_WITHIN_FIVE_CAPTURE_SCOPE' if sk in old_sessions else (
            'CAUSAL_PREFIX_PACKET_BYTES_DUPLICATE_OLD_EXPOSURE_WITHIN_FIVE_CAPTURE_SCOPE' if overlap else None)
        if reason:
            excluded.extend(dict(c, exclusion_reason=reason, old_prefix_duplicate_packet_sha256=overlap) for c in values)
        else:
            admissible.extend(values)
    representative = {}
    for c in admissible:
        sk = c['session_key_sha256']
        representative[sk] = min(representative.get(sk, c['raw_member']), c['raw_member'])
    kept = []
    for c in sorted(admissible, key=lambda x: (x['raw_member'], x['frame_number_1based'])):
        if c['raw_member'] == representative[c['session_key_sha256']]:
            kept.append(c)
        else:
            excluded.append(dict(c, exclusion_reason='DUPLICATE_CANONICAL_SESSION_CAPTURE_REPRESENTATIVE',
                                 retained_member=representative[c['session_key_sha256']]))
    retained_context = [p for (member, sk), ps in context_by_group.items()
                        if member == representative.get(sk) for p in ps]
    require(not ({p['packet_sha256'] for p in retained_context} & old_digests), 'RETAINED_CONTEXT_OLD_PACKET_OVERLAP')
    require(not ({c['session_key_sha256'] for c in kept} & old_sessions), 'RETAINED_OLD_SESSION_OVERLAP')
    require(len(kept) + len(excluded) == len(candidates), 'REVIEW_TARGET_CONSERVATION')
    after_old = collections.defaultdict(list)
    for c in admissible:
        after_old[packets[c['raw_member']][c['frame_number_1based'] - 1]['packet_sha256']].append(c)
    duplicate_groups = [values for values in after_old.values() if len({c['raw_member'] for c in values}) > 1]
    stats = {
        'old_causal_prefix_packet_observations': len(old_context),
        'old_direct_or_prefix_unique_packet_digests': len(old_digests),
        'after_old_exposure_exclusion_targets': len(admissible),
        'after_old_exposure_exclusion_source_sessions': len({(c['raw_member'], c['session_key_sha256']) for c in admissible}),
        'after_old_exposure_exclusion_cross_capture_duplicate_digest_groups': len(duplicate_groups),
        'after_old_exposure_exclusion_cross_capture_duplicate_packet_observations': sum(map(len, duplicate_groups)),
        'retained_context_packet_observations': len(retained_context),
        'retained_old_session_intersection': 0,
        'retained_old_direct_or_context_packet_digest_intersection': 0,
        'excluded_by_reason': dict(collections.Counter(c['exclusion_reason'] for c in excluded)),
    }
    return kept, excluded, stats


def main():
    extension = OUT / 'id_test_extension_v2.json'
    require(not extension.exists(), 'ADDITIVE_REVIEW_ALREADY_COMPLETE')
    pins = {}
    for line in (OUT / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = OUT / relative
        require(path.resolve().is_relative_to(OUT.resolve()), 'HASH_PATH_ESCAPES_RUN')
        require(sha(path) == expected, 'ORIGINAL_OUTPUT_HASH_MISMATCH:' + relative)
        pins[relative] = expected
    q = json.loads((OUT / 'qualification.json').read_text(encoding='utf-8'))
    manifest = json.loads((OUT / 'execution_manifest.json').read_text(encoding='utf-8'))
    candidates = rows(OUT / 'id_candidate_target_plan.jsonl')
    exposures = rows(OUT / 'original_fit_select_exposure.jsonl')
    packets = {m['raw_member']: rows(OUT / ('%02d_packet_metadata.jsonl.gz' % m['file_id'])) for m in q['members']}
    require(len(candidates) == q['candidate_targets'] == 2583, 'INITIAL_CANDIDATE_COUNT')
    require(len(exposures) == q['original_exposure_targets'] == 2009, 'ORIGINAL_EXPOSURE_COUNT')
    require(len({c['uid'] for c in candidates}) == len(candidates), 'INITIAL_UID_DUPLICATE')
    require(all(e['same_actual_and_semantic_frame'] for e in exposures), 'ACTUAL_SEMANTIC_MAPPING_DIFFERENCE')
    for member in q['members']:
        name = member['raw_member']
        require(len(packets[name]) == member['packets'], 'PACKET_DENOMINATOR')
        require(member['candidate_targets'] + sum(member['exclusion_counts'].values()) == member['packets'], 'SOURCE_CONSERVATION')
        require(len([c for c in candidates if c['raw_member'] == name]) == member['candidate_targets'], 'SOURCE_CANDIDATE_COUNT')
        session_rows = rows(OUT / ('%02d_session_ledger.jsonl' % member['file_id']))
        require(sum(s['candidate_targets'] for s in session_rows) == member['candidate_targets'], 'SESSION_CONSERVATION')
        for frame, packet in enumerate(packets[name], 1):
            require(packet['frame_number_1based'] == frame and packet['position_zero_based'] == frame - 1, 'PACKET_FRAME_MAPPING')
    for c in candidates:
        p = packets[c['raw_member']][c['frame_number_1based'] - 1]
        require(p['timestamp'] == c['timestamp'] and p['session_key_sha256'] == c['session_key_sha256'], 'CANDIDATE_IDENTITY')
        require(p['legacy_input_eligible'] and p['session_first_frame'] > c['source_cutoff_frame_1based'], 'CANDIDATE_INPUT_QUALIFICATION')
        require(c['timestamp'] > c['source_cutoff_time'] and c['frame_number_1based'] > c['source_cutoff_frame_1based'], 'SOURCE_LOCAL_CHRONOLOGY')
    kept, excluded, stats = separate(candidates, packets, exposures)
    boundary = {
        'domain': 'Original ID iotsim-combined-cycle-tls',
        'source_local_later_than_old_fit_select': True,
        'global_later_than_all_old_fit_select': False,
        'five_id_capture_old_target_session_prefix_overlap': False,
        'other_old_p2_capture_raw_mirror_deduplication': 'NOT_ESTABLISHED_IN_FIVE_CAPTURE_SCOPE',
        'predecessor_development_untouched': False,
        'external_e3_pretraining_full_deduplication': 'UNKNOWN',
        'independent_capture_device_campaign': False,
        'packet_observations_statistically_independent': False,
        'used_by_this_enhancement_training_normalizer_or_threshold': False,
    }
    final = []
    for c in kept:
        r = dict(c)
        r.update(planned_role='ID_TEST', role='ID_TEST', member_path=c['raw_member'],
                 device_family='iotsim-combined-cycle-tls', source_group=Path(c['raw_member']).stem,
                 session_id='canonical-sha256:' + c['session_key_sha256'],
                 session_id_semantics='scope-independent canonical bidirectional five-tuple SHA256, not old source-encoded cache session_id',
                 packet_sha256=packets[c['raw_member']][c['frame_number_1based'] - 1]['packet_sha256'],
                 independence_boundary=boundary,
                 feature_semantics='literal original E3 prefix, current packet included; no future event')
        final.append(r)
    plan = OUT / 'id_test_target_plan_v2.jsonl'
    exclusion_path = OUT / 'cross_capture_exclusions_v2.jsonl'
    write_rows(plan, final)
    write_rows(exclusion_path, excluded)
    report = {
        'schema': 'legacy-id-temporal-postqualification-review-v2', 'status': 'PASS_WITH_DECLARED_LIMITS',
        'original_outputs_sha256_verified': len(pins), 'original_output_pins': pins,
        'actual_semantic_identity_mismatches': 0, 'original_exposure_targets': 2009,
        'initial_candidates': len(candidates), 'qualified_targets': len(final),
        'qualified_canonical_sessions': len({c['session_key_sha256'] for c in final}),
        'qualified_sources': dict(collections.Counter(c['raw_member'] for c in final)),
        'qualified_protocol_targets': dict(collections.Counter(str(packets[c['raw_member']][c['frame_number_1based'] - 1]['ip_proto']) for c in final)),
        'cross_capture_review': stats, 'independence_boundary': boundary,
        'deduplication_rule': 'Reject whole source-session if any canonical session or causal-prefix packet overlaps old exposure within five-capture scope; among remaining canonical sessions retain complete target set of lexicographically first member_path',
        'candidate_ordering_rule': 'member_path then raw frame number',
        'global_latest_old_target_time': q['global_ID_latest_old_target_time'],
        'qualified_targets_later_than_global_old_cutoff': sum(c['timestamp'] > q['global_ID_latest_old_target_time'] for c in final),
        'target_plan_sha256': sha(plan), 'exclusion_ledger_sha256': sha(exclusion_path),
        'script_sha256': sha(Path(__file__)), 'raw_decodes_in_review': 0,
        'model_loads': 0, 'feature_arrays_opened': 0, 'optimizer_steps': 0, 'score_based_selection': False,
    }
    report_path = OUT / 'cross_capture_review_v2.json'
    dump(report_path, report)
    member_pins = {m['raw_member']: {'sha256': m['member_sha256'], 'bytes': m['member_bytes'],
                    'local_path': str(OUT / 'raw_selected' / ('%02d.pcap' % m['file_id'])),
                    'packets': m['packets']} for m in q['members']}
    dump(extension, {
        'schema': 'legacy-id-test-extension-v2', 'status': 'QUALIFIED_WITH_DECLARED_LIMITS', 'qualified': bool(final),
        'archive_path': manifest['archive_path'],
        'metadata_identity': {'method': manifest['archive_identity_method'],
                              'archive_bytes_stat': manifest['archive_bytes_stat'], 'archive_full_rehash': False,
                              'qualification_manifest_path': str(OUT / 'execution_manifest.json'),
                              'qualification_manifest_sha256': sha(OUT / 'execution_manifest.json')},
        'target_plan_path': str(plan), 'target_plan_sha256': sha(plan), 'rows': len(final),
        'planned_role': 'ID_TEST', 'label': 0, 'device_family': 'iotsim-combined-cycle-tls',
        'member_pins': member_pins, 'canonical_sessions': report['qualified_canonical_sessions'],
        'qualification': {'path': str(report_path), 'sha256': sha(report_path), 'independence_boundary': boundary},
        'model_features_materialized': False, 'scored': False,
        'later_materialization_requirements': [
            'Use member SHA + raw frame as exact packet identity; recorded_index is never raw index.',
            'Decode each chosen member in capture order and preserve the literal old canonical session prefix; current event included, future excluded.',
            'Verify raw timestamp, protocol/header eligibility, session hash and metadata qualification; retain any numerical model-input failures in denominator.',
            'Do not fit normalizer, threshold, selection, optimizer or stopping rule on these targets.',
            'Compare fixed R/B/C at original probability threshold; report source/session dependence and development status.',
        ],
    })
    new_files = [plan, exclusion_path, report_path, extension]
    (OUT / 'review_v2.SHA256SUMS').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in new_files), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'rows': len(final), 'sessions': report['qualified_canonical_sessions'],
                      'exclusions': stats['excluded_by_reason'], 'extension_sha256': sha(extension)}))


if __name__ == '__main__':
    main()
