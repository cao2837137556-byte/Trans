"""Cutoff-bounded metadata planning and route validation; never decodes or scores.

Source/candidate receipts describe an upstream causal adapter. Checking their
metadata is not verification of PCAP bytes or construction of encoded references.
Real input I/O belongs to a separately authorized and pinned caller.
"""
import copy
import hashlib
import ipaddress
import re
from collections import Counter

import legacy_commissioning_common_v1 as c


def owner(value):
    c.require(isinstance(value, str) and re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', value), 'OWNER_MAC')
    return value


def canonical_key(key, protocol):
    c.require(isinstance(key, list) and len(key) == 3 and key[0] == protocol, 'CANONICAL_KEY')
    ends = []
    for endpoint in key[1:]:
        c.require(isinstance(endpoint, list) and len(endpoint) == 2, 'CANONICAL_ENDPOINT')
        c.require(isinstance(endpoint[0], str), 'CANONICAL_IP')
        try:
            ipaddress.ip_address(endpoint[0])
        except (ValueError, TypeError):
            raise c.Stop('CANONICAL_IP')
        c.integer(endpoint[1], 'CANONICAL_PORT')
        c.require(endpoint[1] <= 65535, 'CANONICAL_PORT')
        ends.append(endpoint)
    c.require(ends == sorted(ends), 'CANONICAL_ORDER')
    return key


def phase_at(episode, timestamp):
    offset = timestamp - episode['t0']
    c.require(0 <= offset <= 3600, 'PHASE_TIME')
    for name, start, end in c.PHASES:
        if start <= offset < end or (end == 3600 and offset == end):
            return name


def validate_episode(e):
    c.fields(e, ('schema', 'synthetic', 'policy_sha256', 'episode_id', 'device', 'role',
                 'declared_at', 't0', 'cutoff', 'wall_seconds', 'roster_frozen_before_outcomes',
                 'source_normality', 'capture_health', 'function_declarations', 'operations_log',
                 'declared_protocols', 'protocol_declaration_complete'))
    c.require(e['schema'] == 'commissioning-episode-v1' and e['policy_sha256'] == c.POLICY_SHA, 'EPISODE_POLICY')
    c.boolean(e['synthetic'], 'SYNTHETIC_BOOL')
    c.text(e['episode_id'], 'EPISODE_ID')
    c.fields(e['device'], ('name', 'owners', 'lineage_sha256'))
    c.text(e['device']['name'], 'DEVICE_NAME')
    c.require(e['device']['name'].strip().lower() not in c.CONSUMED, 'CONSUMED_DEVICE_FORBIDDEN')
    c.sha_text(e['device']['lineage_sha256'])
    owners = e['device']['owners']
    c.require(isinstance(owners, list) and len(owners) > 0 and len(set(owners)) == len(owners), 'DEVICE_OWNERS')
    for value in owners:
        owner(value)
    c.require(e['role'] in ('LEARN', 'DEV'), 'ROLE_FORBIDDEN')
    for field in ('declared_at', 't0', 'cutoff'):
        c.number(e[field], field)
    c.require(e['declared_at'] < e['t0'] and e['cutoff'] == e['t0'] + 3600 and
              type(e['wall_seconds']) is int and e['wall_seconds'] == 3600, 'FIXED_WINDOW')
    c.require(e['roster_frozen_before_outcomes'] is True, 'ROSTER_NOT_FROZEN')
    c.require(e['capture_health'] in ('HEALTHY', 'KNOWN_GAPS', 'UNKNOWN'), 'CAPTURE_HEALTH')
    declared = e['declared_protocols']
    c.require(isinstance(declared, list) and all(type(p) is int and 0 <= p <= 255 for p in declared)
              and len(declared) == len(set(declared)), 'DECLARED_PROTOCOLS')
    c.boolean(e['protocol_declaration_complete'], 'PROTOCOL_DECLARATION_BOOL')
    cert = e['source_normality']
    c.fields(cert, ('status', 'basis', 'evidence_sha256', 'source_sha256s', 'inferred_from_scores_or_query_labels'))
    c.require(cert['status'] in ('VERIFIED', 'UNVERIFIED', 'CONTAMINATED'), 'NORMALITY_STATUS')
    c.require(cert['basis'] in ('PUBLISHER_NORMAL_CAPTURE', 'CONTROLLED_NORMAL_ENVIRONMENT', 'UNKNOWN'), 'NORMALITY_BASIS')
    c.boolean(cert['inferred_from_scores_or_query_labels'], 'NORMALITY_INFERENCE_BOOL')
    c.require(isinstance(cert['source_sha256s'], list) and len(set(cert['source_sha256s'])) == len(cert['source_sha256s']), 'NORMALITY_SOURCES')
    for sha in cert['source_sha256s']:
        c.sha_text(sha)
    if cert['evidence_sha256'] is not None:
        c.sha_text(cert['evidence_sha256'])
    declarations = e['function_declarations']
    c.require(isinstance(declarations, list) and len(declarations) == len(c.PHASES), 'FUNCTION_DECLARATIONS')
    for d, (name, _, _) in zip(declarations, c.PHASES):
        c.fields(d, ('phase', 'applicability', 'basis', 'planned_actions'))
        c.require(d['phase'] == name and d['applicability'] in ('APPLICABLE', 'NOT_APPLICABLE', 'UNKNOWN'), 'FUNCTION_PHASE')
        c.text(d['basis'], 'FUNCTION_BASIS')
        c.require(isinstance(d['planned_actions'], list), 'PLANNED_ACTIONS')
        action_ids = set()
        for action in d['planned_actions']:
            c.fields(action, ('id', 'description'))
            c.text(action['id'], 'ACTION_ID'); c.text(action['description'], 'ACTION_DESCRIPTION')
            c.require(action['id'] not in action_ids, 'DUPLICATE_ACTION_ID')
            action_ids.add(action['id'])
        if d['applicability'] == 'APPLICABLE':
            c.require(bool(action_ids), 'APPLICABLE_ACTIONS_MISSING')
        elif d['applicability'] == 'NOT_APPLICABLE':
            c.require(not action_ids, 'NA_HAS_ACTIONS')
        if name in ('idle', 'settled_operation'):
            c.require(d['applicability'] == 'APPLICABLE', 'IDLE_MUST_APPLY')
    logs = e['operations_log']
    c.require(isinstance(logs, list), 'OPERATIONS_LOG')
    by_phase = {name: (a, b, d) for (name, a, b), d in zip(c.PHASES, declarations)}
    seen = set()
    for log in logs:
        c.fields(log, ('phase', 'start', 'end', 'outcome', 'reason', 'completed_action_ids'))
        name = log['phase']
        c.require(name in by_phase and name not in seen, 'LOG_PHASE')
        seen.add(name)
        a, b, declaration = by_phase[name]
        c.number(log['start'], 'OPERATION_START'); c.number(log['end'], 'OPERATION_END')
        c.require(e['t0'] + a <= log['start'] <= log['end'] <= e['t0'] + b, 'OPERATION_OUTSIDE_SLOT')
        c.require(log['outcome'] in ('COMPLETED', 'NOT_APPLICABLE_IDLE', 'UNAVAILABLE', 'UNKNOWN'), 'OPERATION_OUTCOME')
        c.text(log['reason'], 'OPERATION_REASON')
        completed = log['completed_action_ids']
        c.require(isinstance(completed, list) and all(isinstance(x, str) for x in completed) and
                  len(completed) == len(set(completed)), 'COMPLETED_ACTION_IDS')
        planned = {x['id'] for x in declaration['planned_actions']}
        c.require(set(completed) <= planned, 'UNPLANNED_OPERATION')
        app = declaration['applicability']
        if app == 'NOT_APPLICABLE':
            c.require(log['outcome'] == 'NOT_APPLICABLE_IDLE' and log['start'] == e['t0'] + a and
                      log['end'] == e['t0'] + b and not completed, 'NA_MUST_REMAIN_IDLE')
        else:
            c.require(log['outcome'] != 'NOT_APPLICABLE_IDLE', 'UNAVAILABLE_IS_NOT_NA')
            if log['outcome'] == 'COMPLETED':
                c.require(app == 'APPLICABLE' and set(completed) == planned and log['end'] > log['start'],
                          'INCOMPLETE_OR_UNKNOWN_FUNCTION')
                if name in ('idle', 'settled_operation'):
                    c.require(log['start'] == e['t0'] + a and log['end'] == e['t0'] + b, 'IDLE_SLOT_INCOMPLETE')
    if not logs:
        return 'UNKNOWN_PASSIVE'
    complete = len(logs) == 6 and all(x['outcome'] in ('COMPLETED', 'NOT_APPLICABLE_IDLE') for x in logs)
    return 'VERIFIED_APPLICABLE_OPERATIONS' if complete and e['capture_health'] == 'HEALTHY' else 'PARTIAL'


def validate_sources(e, sources):
    c.require(isinstance(sources, list) and bool(sources), 'SOURCE_LIST')
    result = {}
    hashes = set()
    for source in sources:
        c.fields(source, ('capture_id', 'sha256', 'bytes', 'capture_start', 'cutoff_timestamp',
                          'cutoff_frame', 'processed_through_frame', 'last_frame_timestamp',
                          'owner_event_count', 'enumeration', 'adapter_contract', 'capture_health'))
        cid = c.text(source['capture_id'], 'CAPTURE_ID')
        c.require(cid not in result, 'DUPLICATE_CAPTURE')
        c.sha_text(source['sha256'])
        c.require(source['sha256'] not in hashes, 'CAPTURE_ALIAS_DUPLICATE')
        hashes.add(source['sha256'])
        c.integer(source['bytes'], 'SOURCE_BYTES', 1)
        c.integer(source['cutoff_frame'], 'CUTOFF_FRAME')
        c.integer(source['processed_through_frame'], 'PROCESSED_FRAME')
        c.integer(source['owner_event_count'], 'OWNER_EVENT_COUNT')
        c.require(source['owner_event_count'] <= source['cutoff_frame'], 'EVENT_COUNT_OVERFLOW')
        for name in ('capture_start', 'cutoff_timestamp', 'last_frame_timestamp'):
            c.number(source[name], name)
        c.require(e['t0'] <= source['capture_start'] <= source['last_frame_timestamp'] <= e['cutoff'] and
                  source['cutoff_timestamp'] == e['cutoff'], 'SOURCE_WINDOW')
        c.require(source['processed_through_frame'] == source['cutoff_frame'], 'SOURCE_NOT_CUTOFF_BOUNDED')
        c.require(source['enumeration'] == 'ALL_OWNER_EVENTS_AT_CUTOFF', 'SPARSE_OR_FUTURE_BASED_ENUMERATION')
        c.require(source['adapter_contract'] == 'UNCHANGED_LEGACY_OWNER_CAPTURE_PREFIX', 'FRONTEND_CONTRACT')
        c.require(source['capture_health'] in ('HEALTHY', 'KNOWN_GAPS', 'UNKNOWN'), 'SOURCE_HEALTH')
        if e['capture_health'] == 'HEALTHY':
            c.require(source['capture_health'] == 'HEALTHY', 'HEALTH_NOT_VERIFIED')
        result[cid] = source
    cert = e['source_normality']
    trusted = (cert['status'] == 'VERIFIED' and cert['basis'] != 'UNKNOWN' and
               cert['evidence_sha256'] is not None and not cert['inferred_from_scores_or_query_labels'] and
               set(cert['source_sha256s']) == hashes)
    return result, trusted


EVENT_FIELDS = ('uid', 'device', 'role', 'owner', 'capture_id', 'source_sha256', 'frame',
                'timestamp', 'protocol', 'canonical_key', 'component_id', 'session_id',
                'legal_target', 'rejection_reason', 'prefix_max_frame', 'prefix_max_timestamp',
                'direction', 'transport_stream_id')
REJECTION_REASONS = {'UNSUPPORTED_PROTOCOL', 'SHARED_DHCP_CONTEXT', 'INCOMPLETE_TARGET',
                     'OWNER_AMBIGUOUS_OR_OUTSIDE', 'POISONED_PREFIX', 'NEW_TIMESTAMP_REGRESSION'}


def validate_event(e, sources, event):
    c.fields(event, EVENT_FIELDS)  # labels, model scores and embeddings are forbidden here.
    c.require(event['device'] == e['device']['name'] and event['role'] == e['role'], 'EVENT_DEVICE_ROLE')
    c.require(owner(event['owner']) in e['device']['owners'], 'EVENT_OWNER')
    cid = event['capture_id']
    c.require(cid in sources and event['source_sha256'] == sources[cid]['sha256'], 'EVENT_SOURCE')
    source = sources[cid]
    c.integer(event['frame'], 'EVENT_FRAME', 1)
    c.require(event['frame'] <= source['cutoff_frame'], 'FUTURE_FRAME')
    c.number(event['timestamp'], 'EVENT_TIME')
    c.require(source['capture_start'] <= event['timestamp'] <= e['cutoff'], 'FUTURE_OR_EARLY_TIME')
    if event['frame'] == source['cutoff_frame']:
        c.require(event['timestamp'] == source['last_frame_timestamp'], 'CUTOFF_FRAME_TIME_CONFLICT')
    c.require(event['uid'] == c.legacy_digest([source['sha256'], event['frame'], event['owner']]), 'EVENT_UID')
    c.integer(event['protocol'], 'PROTOCOL')
    c.require(event['protocol'] <= 255, 'PROTOCOL')
    c.boolean(event['legal_target'], 'LEGAL_TARGET_BOOL')
    c.require(event['direction'] in ('inbound', 'outbound', 'ambiguous'), 'DIRECTION')
    if event['transport_stream_id'] is not None:
        c.integer(event['transport_stream_id'], 'STREAM_ID')
    if event['protocol'] in (6, 17):
        key = canonical_key(event['canonical_key'], event['protocol'])
        c.require(event['component_id'] == c.legacy_digest([event['owner'], key]), 'COMPONENT_ID')
        c.require(event['session_id'] == c.legacy_digest([event['owner'], cid, key]), 'SESSION_ID')
        dhcp = key == [17, ['0.0.0.0', 68], ['255.255.255.255', 67]]
        if dhcp:
            c.require(not event['legal_target'] and event['rejection_reason'] == 'SHARED_DHCP_CONTEXT', 'SHARED_DHCP')
    else:
        c.require(not event['legal_target'] and event['rejection_reason'] == 'UNSUPPORTED_PROTOCOL' and
                  all(event[k] is None for k in ('canonical_key', 'component_id', 'session_id')), 'UNSUPPORTED_TARGET')
    if event['legal_target']:
        c.require(event['rejection_reason'] is None and event['direction'] != 'ambiguous', 'LEGAL_TARGET_REASON')
        c.integer(event['prefix_max_frame'], 'PREFIX_FRAME', 1)
        c.number(event['prefix_max_timestamp'], 'PREFIX_TIME')
        c.require(event['prefix_max_frame'] <= event['frame'] and
                  source['capture_start'] <= event['prefix_max_timestamp'] <= event['timestamp'], 'FUTURE_PREFIX')
    else:
        c.require(event['rejection_reason'] in REJECTION_REASONS, 'REJECTION_REASON')
        c.require(event['prefix_max_frame'] is None and event['prefix_max_timestamp'] is None, 'INVALID_PREFIX_RECEIPT')


def _histogram(events, e):
    return {'protocol': dict(sorted(Counter(str(r['protocol']) for r in events).items())),
            'direction': dict(sorted(Counter(r['direction'] for r in events).items())),
            'phase': dict(sorted(Counter(phase_at(e, r['timestamp']) for r in events).items())),
            'known_transport_streams': len({(r['capture_id'], r['protocol'], r['transport_stream_id'])
                                            for r in events if r['transport_stream_id'] is not None}),
            'stream_metadata_unknown_rows': sum(r['transport_stream_id'] is None for r in events)}


def plan_bank(episode, sources, events):
    """Accept a complete cutoff snapshot; reject later/filtered/sparse inputs.

    Membership is score/label independent. Serialized references use UID order
    because the existing verifier uses that order to resolve similarity ties.
    No encoded bank is created and registration is not activated by this call.
    """
    e = copy.deepcopy(episode)
    functional = validate_episode(e)
    by_capture, trusted = validate_sources(e, sources)
    c.require(isinstance(events, list), 'EVENT_LIST')
    uids, frames, counts, latest = set(), set(), Counter(), {}
    eligible, observed, reasons = [], set(), Counter()
    for event in events:
        validate_event(e, by_capture, event)
        ident = (event['capture_id'], event['frame'])
        c.require(event['uid'] not in uids and ident not in frames, 'DUPLICATE_EVENT')
        uids.add(event['uid']); frames.add(ident); counts[event['capture_id']] += 1
        observed.add(event['protocol'])
        if not event['legal_target']:
            reasons[event['rejection_reason']] += 1
            continue
        eligible.append(event)
        component = event['component_id']
        order = lambda r: (r['timestamp'], r['capture_id'], r['frame'], r['uid'])
        if component not in latest or order(event) > order(latest[component]):
            latest[component] = event
    for cid, source in by_capture.items():
        c.require(counts[cid] == source['owner_event_count'], 'INCOMPLETE_EVENT_ENUMERATION')
    # A late timestamp regression poisons subsequent targets in that namespace,
    # never the already-issued legal snapshots. Order here is capture frame order.
    last_time, poisoned = {}, set()
    for event in sorted(events, key=lambda r: (r['capture_id'], r['frame'])):
        if event['protocol'] not in (6, 17) or event['rejection_reason'] in (
                'SHARED_DHCP_CONTEXT', 'OWNER_AMBIGUOUS_OR_OUTSIDE'):
            continue
        namespace = event['session_id']
        if namespace in last_time and event['timestamp'] < last_time[namespace]:
            poisoned.add(namespace)
        if event['rejection_reason'] in ('NEW_TIMESTAMP_REGRESSION', 'POISONED_PREFIX'):
            poisoned.add(namespace)
        c.require(not (event['legal_target'] and namespace in poisoned), 'LEGAL_TARGET_AFTER_TIMESTAMP_REGRESSION')
        last_time[namespace] = max(last_time.get(namespace, event['timestamp']), event['timestamp'])
    sort_key = lambda r: (hashlib.sha256((c.SALT + '|' + r['component_id']).encode()).hexdigest(), r['component_id'])
    lists = {p: sorted([r for r in latest.values() if r['protocol'] == p], key=sort_key) for p in (6, 17)}
    membership = []
    if trusted:
        index = {6: 0, 17: 0}
        while len(membership) < 64:
            changed = False
            for p in (6, 17):
                if index[p] < len(lists[p]) and len(membership) < 64:
                    membership.append(lists[p][index[p]])
                    index[p] += 1; changed = True
            if not changed:
                break
    selected = sorted(membership, key=lambda r: r['uid'])
    qualifications = {}
    for p in (6, 17):
        count = sum(r['protocol'] == p for r in selected)
        status = ('NOT_OBSERVED' if p not in observed else 'OBSERVED_NO_LEGAL_REFERENCE' if not count
                  else 'SINGLE_COMPONENT' if count == 1 else 'REFERENCE_AVAILABLE')
        qualifications[str(p)] = {'status': status, 'selected_components': count,
                                   'candidate_components': len(lists[p])}
    result = {'schema': 'commissioning-bank-plan-v1', 'policy_sha256': c.POLICY_SHA,
              'detector_contract_sha256': c.CONTRACT_SHA, 'episode_sha256': c.digest(e),
              'sources_sha256': c.digest(sorted(sources, key=lambda r: r['capture_id'])),
              'events_sha256': c.digest(sorted(events, key=lambda r: r['uid'])),
              'synthetic': e['synthetic'], 'episode_id': e['episode_id'], 'device': copy.deepcopy(e['device']),
              'role': e['role'], 't0': e['t0'], 'cutoff': e['cutoff'],
              'cutoff_frames': {cid: s['cutoff_frame'] for cid, s in sorted(by_capture.items())},
              'normal_source_trusted': trusted, 'bank_invalidated': not trusted,
              'functional_coverage': functional, 'capture_health': e['capture_health'],
              'required_protocols': sorted(({6, 17} & set(e['declared_protocols'])) | ({6, 17} & observed)),
              'protocol_declaration_complete': e['protocol_declaration_complete'],
              'protocol_status': qualifications, 'selection_order_uids': [r['uid'] for r in membership],
              'references': copy.deepcopy(selected), 'raw_owner_events': len(events),
              'eligible_endpoints': len(eligible), 'candidate_components': len(latest),
              'discarded_duplicate_component_endpoints': len(eligible) - len(latest),
              'unselected_components': len(latest) - len(selected),
              'rejection_reasons': dict(sorted(reasons.items())),
              'candidate_coverage': _histogram(eligible, e), 'selected_coverage': _histogram(selected, e),
              'source_coverage': copy.deepcopy(sorted(sources, key=lambda r: r['capture_id'])),
              'registration_activated': False, 'encoded_bank_created': False,
              'validation_level': 'METADATA_ASSERTIONS_ONLY_NOT_PCAP_OR_FEATURE_VERIFICATION'}
    result['plan_sha256'] = c.digest(result)
    return result


def validate_plan(plan):
    c.require(isinstance(plan, dict) and 'plan_sha256' in plan, 'PLAN_SCHEMA')
    body = {k: v for k, v in plan.items() if k != 'plan_sha256'}
    c.require(c.digest(body) == plan['plan_sha256'], 'PLAN_MUTATED')
    c.require(plan['schema'] == 'commissioning-bank-plan-v1' and plan['policy_sha256'] == c.POLICY_SHA and
              plan['detector_contract_sha256'] == c.CONTRACT_SHA, 'PLAN_IDENTITY')
    c.boolean(plan['synthetic'], 'PLAN_SYNTHETIC')
    c.require(plan['role'] in ('LEARN', 'DEV') and plan['device']['name'].strip().lower() not in c.CONSUMED,
              'PLAN_DEVICE_ROLE')
    c.number(plan['t0'], 'PLAN_T0'); c.number(plan['cutoff'], 'PLAN_CUTOFF')
    c.require(plan['cutoff'] == plan['t0'] + 3600, 'PLAN_WINDOW')
    c.require(plan['registration_activated'] is False and plan['encoded_bank_created'] is False, 'PLAN_NOT_ENCODING')
    c.boolean(plan['normal_source_trusted'], 'PLAN_TRUST')
    c.require(plan['bank_invalidated'] is (not plan['normal_source_trusted']), 'PLAN_TRUST_CONFLICT')
    sources = plan['source_coverage']
    c.require(isinstance(sources, list) and len({r['capture_id'] for r in sources}) == len(sources), 'PLAN_SOURCES')
    c.require(c.digest(sorted(sources, key=lambda r: r['capture_id'])) == plan['sources_sha256'], 'PLAN_SOURCE_DIGEST')
    by_capture = {r['capture_id']: r for r in sources}
    c.require(plan['cutoff_frames'] == {cid: s['cutoff_frame'] for cid, s in by_capture.items()}, 'PLAN_CUTOFF_FRAMES')
    for source in sources:
        c.require(source['cutoff_timestamp'] == plan['cutoff'] and
                  source['processed_through_frame'] == source['cutoff_frame'] and
                  plan['t0'] <= source['capture_start'] <= source['last_frame_timestamp'] <= plan['cutoff'],
                  'PLAN_SOURCE_CUTOFF')
    refs = plan['references']
    c.require(isinstance(refs, list) and len(refs) <= 64 and
              len({r['uid'] for r in refs}) == len(refs) == len({r['component_id'] for r in refs}), 'PLAN_UNIQUE_CAPACITY')
    c.require(refs == sorted(refs, key=lambda r: r['uid']), 'PLAN_METRIC_UID_ORDER')
    c.require(len(plan['selection_order_uids']) == len(refs) and
              set(plan['selection_order_uids']) == {r['uid'] for r in refs}, 'PLAN_SELECTION_UIDS')
    c.require(plan['normal_source_trusted'] or not refs, 'UNTRUSTED_PLAN_HAS_REFERENCES')
    for ref in refs:
        validate_event(plan, by_capture, ref)
        c.require(ref['legal_target'] is True, 'PLAN_ILLEGAL_REFERENCE')
    for protocol in (6, 17):
        count = sum(r['protocol'] == protocol for r in refs)
        status = plan['protocol_status'][str(protocol)]
        c.integer(status['candidate_components'], 'PLAN_CANDIDATE_COMPONENTS')
        c.require(status['selected_components'] == count and status['candidate_components'] >= count,
                  'PLAN_PROTOCOL_COUNTS')
        expected = 'REFERENCE_AVAILABLE' if count >= 2 else 'SINGLE_COMPONENT' if count else None
        c.require(status['status'] == expected if expected else
                  status['status'] in ('NOT_OBSERVED', 'OBSERVED_NO_LEGAL_REFERENCE'), 'PLAN_PROTOCOL_QUALIFICATION')


def route_query(plan, query, readiness=None):
    """Return a routing instruction, never an alarm or a score.

    A readiness receipt must be emitted by a future authorized encoder, after
    verifying cutoff snapshots and the frozen detector. A metadata plan alone
    leaves registration inactive. No receipt is manufactured by this module.
    """
    validate_plan(plan)
    c.fields(query, ('device', 'role', 'owner', 'capture_id', 'frame', 'timestamp', 'protocol', 'legacy_supported'))
    c.require(query['device'] == plan['device']['name'] and query['role'] == plan['role'] and
              query['owner'] in plan['device']['owners'], 'QUERY_IDENTITY_ROLE')
    c.text(query['capture_id'], 'QUERY_CAPTURE')
    c.integer(query['frame'], 'QUERY_FRAME', 1); c.number(query['timestamp'], 'QUERY_TIME')
    c.integer(query['protocol'], 'QUERY_PROTOCOL'); c.require(query['protocol'] <= 255, 'QUERY_PROTOCOL')
    c.boolean(query['legacy_supported'], 'QUERY_SUPPORTED_BOOL')
    if query['timestamp'] > plan['cutoff'] and query['capture_id'] in plan['cutoff_frames']:
        c.require(query['frame'] > plan['cutoff_frames'][query['capture_id']], 'QUERY_FRAME_NOT_AFTER_CUTOFF')
    if not query['legacy_supported'] or query['protocol'] not in (6, 17):
        return 'LEGACY_UNSUPPORTED_CONTRACT'
    if query['timestamp'] <= plan['cutoff'] or not plan['references'] or not plan['normal_source_trusted']:
        return 'R'
    if readiness is None:
        return 'R'
    c.fields(readiness, ('plan_sha256', 'detector_contract_sha256', 'reference_uids', 'ready_at',
                         'causal_snapshots_verified', 'frozen_artifacts_verified', 'synthetic'))
    c.require(readiness['plan_sha256'] == plan['plan_sha256'] and
              readiness['detector_contract_sha256'] == c.CONTRACT_SHA and
              readiness['reference_uids'] == [r['uid'] for r in plan['references']], 'READY_BANK_IDENTITY')
    c.require(readiness['causal_snapshots_verified'] is True and readiness['frozen_artifacts_verified'] is True and
              type(readiness['synthetic']) is bool and readiness['synthetic'] == plan['synthetic'], 'READY_VERIFICATION')
    c.number(readiness['ready_at'], 'READY_TIME')
    c.require(readiness['ready_at'] >= plan['cutoff'], 'READY_BEFORE_CUTOFF')
    if query['timestamp'] < readiness['ready_at']:
        return 'R'
    return ('Q_PLUS_VERIFIER' if plan['protocol_status'][str(query['protocol'])]['status'] == 'REFERENCE_AVAILABLE'
            else 'Q')


def validate_future_queries(plan, queries):
    """Evaluate no values; guard a declared future pool without removing rows."""
    validate_plan(plan)
    for query in queries:
        c.require(c.number(query['timestamp'], 'QUERY_TIME') > plan['cutoff'], 'QUERY_NOT_STRICTLY_FUTURE')
        route_query(plan, query)
    return {'queries_checked': len(queries), 'queries_removed': 0}
