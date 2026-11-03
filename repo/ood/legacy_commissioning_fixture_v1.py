"""Generated, obviously synthetic metadata. No file, packet or model access."""
import copy
import legacy_commissioning_common_v1 as c


def fixture(tcp=3, udp=3):
    source_sha = c.digest('synthetic-capture')
    e = {'schema': 'commissioning-episode-v1', 'synthetic': True, 'policy_sha256': c.POLICY_SHA,
         'episode_id': 'synthetic-commissioning', 'device': {'name': 'SYNTHETIC_DEVICE',
         'owners': ['02:00:00:00:00:01'], 'lineage_sha256': c.digest('synthetic-lineage')},
         'role': 'DEV', 'declared_at': 99., 't0': 100., 'cutoff': 3700., 'wall_seconds': 3600,
         'roster_frozen_before_outcomes': True,
         'source_normality': {'status': 'VERIFIED', 'basis': 'CONTROLLED_NORMAL_ENVIRONMENT',
                             'evidence_sha256': c.digest('synthetic-certificate'), 'source_sha256s': [source_sha],
                             'inferred_from_scores_or_query_labels': False},
         'capture_health': 'HEALTHY', 'function_declarations': [], 'operations_log': [],
         'declared_protocols': [6, 17], 'protocol_declaration_complete': True}
    for name, a, b in c.PHASES:
        e['function_declarations'].append({'phase': name, 'applicability': 'APPLICABLE', 'basis': 'SYNTHETIC manual',
                                          'planned_actions': [{'id': name, 'description': 'SYNTHETIC phase operation'}]})
        e['operations_log'].append({'phase': name, 'start': e['t0'] + a, 'end': e['t0'] + b,
                                  'outcome': 'COMPLETED', 'reason': 'SYNTHETIC operation', 'completed_action_ids': [name]})
    s = {'capture_id': 'synthetic-capture-0', 'sha256': source_sha, 'bytes': 100000,
         'capture_start': 100., 'cutoff_timestamp': 3700., 'cutoff_frame': tcp + udp,
         'processed_through_frame': tcp + udp, 'last_frame_timestamp': 100. + tcp + udp,
         'owner_event_count': tcp + udp, 'enumeration': 'ALL_OWNER_EVENTS_AT_CUTOFF',
         'adapter_contract': 'UNCHANGED_LEGACY_OWNER_CAPTURE_PREFIX', 'capture_health': 'HEALTHY'}
    events = []
    for protocol, count in ((6, tcp), (17, udp)):
        for i in range(count):
            frame = len(events) + 1
            events.append(event(e, s, frame, protocol=protocol, port=1000 + i, timestamp=100. + frame))
    return e, [s], events


def event(e, source, frame, protocol=6, port=1000, timestamp=101.):
    own = e['device']['owners'][0]
    key = [protocol, ['10.0.0.1', port], ['10.0.0.2', 443]]
    return {'uid': c.legacy_digest([source['sha256'], frame, own]), 'device': e['device']['name'],
            'role': e['role'], 'owner': own, 'capture_id': source['capture_id'], 'source_sha256': source['sha256'],
            'frame': frame, 'timestamp': timestamp, 'protocol': protocol, 'canonical_key': key,
            'component_id': c.legacy_digest([own, key]), 'session_id': c.legacy_digest([own, source['capture_id'], key]),
            'legal_target': True, 'rejection_reason': None, 'prefix_max_frame': frame,
            'prefix_max_timestamp': timestamp, 'direction': 'outbound', 'transport_stream_id': frame}


def query(plan, protocol=6, timestamp=3800.):
    return {'device': plan['device']['name'], 'role': plan['role'], 'owner': plan['device']['owners'][0],
            'capture_id': 'synthetic-future-capture', 'frame': 1, 'timestamp': timestamp,
            'protocol': protocol, 'legacy_supported': True}


def ready(plan, ready_at=3750.):
    c.require(plan['synthetic'] is True, 'FIXTURE_CANNOT_CERTIFY_REAL_BANK')
    return {'plan_sha256': plan['plan_sha256'], 'detector_contract_sha256': c.CONTRACT_SHA,
            'reference_uids': [r['uid'] for r in plan['references']], 'ready_at': ready_at,
            'causal_snapshots_verified': True, 'frozen_artifacts_verified': True, 'synthetic': True}
