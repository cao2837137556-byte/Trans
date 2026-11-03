"""Independent synthetic contract checks; no raw, feature, model or result data.

Temporary 'real' metadata inputs below are generated fixtures exercising only
the I/O authorization branch. They are not experimental data or authorizations.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

import legacy_commissioning_common_v1 as c
import legacy_commissioning_policy_v1 as p
import legacy_commissioning_runner_v1 as runner
from legacy_commissioning_fixture_v1 import fixture, event, query, ready


ROOT = Path(__file__).resolve().parents[2]


def add_event(episode, sources, events, protocol=6, port=1000, timestamp=200.):
    source = sources[0]
    frame = source['cutoff_frame'] + 1
    source['cutoff_frame'] = frame
    source['processed_through_frame'] = frame
    source['owner_event_count'] += 1
    source['last_frame_timestamp'] = timestamp
    row = event(episode, source, frame, protocol, port, timestamp)
    events.append(row)
    return row


def add_capture(episode, sources, events, timestamp=3500.):
    source = copy.deepcopy(sources[0])
    source.update(capture_id='synthetic-capture-1', sha256=c.digest('second synthetic capture'),
                  cutoff_frame=1, processed_through_frame=1, owner_event_count=1,
                  last_frame_timestamp=timestamp)
    episode['source_normality']['source_sha256s'].append(source['sha256'])
    sources.append(source)
    events.append(event(episode, source, 1, timestamp=timestamp))
    return source


class PolicyContracts(unittest.TestCase):
    def test_fixed_budget_balances_both_plentiful_protocols(self):
        plan = p.plan_bank(*fixture(80, 80))
        self.assertEqual(len(plan['references']), 64)
        self.assertEqual(plan['selected_coverage']['protocol'], {'6': 32, '17': 32})
        self.assertEqual(len({r['component_id'] for r in plan['references']}), 64)
        self.assertEqual(plan['unselected_components'], 96)
        self.assertFalse(plan['registration_activated'])
        self.assertFalse(plan['encoded_bank_created'])

    def test_scarce_protocols_remain_and_other_protocol_uses_spare_capacity(self):
        for tcp, udp, expected in ((1, 80, {'6': 1, '17': 63}),
                                    (80, 2, {'6': 62, '17': 2}),
                                    (0, 80, {'17': 64}), (80, 0, {'6': 64})):
            with self.subTest(tcp=tcp, udp=udp):
                plan = p.plan_bank(*fixture(tcp, udp))
                self.assertEqual(plan['selected_coverage']['protocol'], expected)
                self.assertEqual(len(plan['references']), 64)

    def test_duplicate_component_and_different_stream_never_inflate_references(self):
        e, sources, events = fixture(1, 0)
        add_event(e, sources, events, timestamp=150.)
        latest = add_event(e, sources, events, timestamp=200.)
        plan = p.plan_bank(e, sources, events)
        self.assertEqual([r['uid'] for r in plan['references']], [latest['uid']])
        self.assertEqual(plan['candidate_components'], 1)
        self.assertEqual(plan['discarded_duplicate_component_endpoints'], 2)
        self.assertEqual(plan['candidate_coverage']['known_transport_streams'], 3)
        self.assertEqual(plan['protocol_status']['6']['status'], 'SINGLE_COMPONENT')

    def test_cross_capture_component_uses_last_endpoint_without_joining_prefix(self):
        e, sources, events = fixture(1, 0)
        add_capture(e, sources, events)
        self.assertEqual(events[0]['component_id'], events[1]['component_id'])
        self.assertNotEqual(events[0]['session_id'], events[1]['session_id'])
        plan = p.plan_bank(e, sources, events)
        self.assertEqual(len(plan['references']), 1)
        self.assertEqual(plan['references'][0]['capture_id'], 'synthetic-capture-1')
        self.assertEqual(plan['references'][0]['prefix_max_frame'], 1)

    def test_equal_time_uses_capture_frame_uid_order(self):
        e, sources, events = fixture(1, 0)
        add_capture(e, sources, events, timestamp=101.)
        plan = p.plan_bank(e, sources, events)
        self.assertEqual(plan['references'][0]['capture_id'], 'synthetic-capture-1')
        self.assertEqual(plan, p.plan_bank(e, sources[::-1], events[::-1]))

    def test_input_shuffle_cannot_change_membership_or_uid_serialization(self):
        e, sources, events = fixture(70, 70)
        expected = p.plan_bank(e, sources, events)
        random.Random(27).shuffle(events)
        actual = p.plan_bank(e, sources, events)
        self.assertEqual(actual, expected)
        self.assertEqual([r['uid'] for r in actual['references']],
                         sorted(r['uid'] for r in actual['references']))

    def test_planning_copies_inputs_and_route_never_absorbs_query(self):
        e, sources, events = fixture()
        original = copy.deepcopy((e, sources, events))
        plan = p.plan_bank(e, sources, events)
        self.assertEqual((e, sources, events), original)
        snapshot = copy.deepcopy(plan)
        p.route_query(plan, query(plan), ready(plan))
        self.assertEqual(plan, snapshot)
        e['device']['owners'].append('02:00:00:00:00:02')
        events[0]['timestamp'] = -123.
        sources[0]['bytes'] = 1
        self.assertEqual(plan, snapshot)

    def test_cutoff_endpoint_allowed_but_future_time_and_frame_rejected(self):
        for field, value, error in (('timestamp', 3700.01, 'FUTURE_OR_EARLY_TIME'),
                                     ('timestamp', 99., 'FUTURE_OR_EARLY_TIME'),
                                     ('frame', 2, 'FUTURE_FRAME')):
            with self.subTest(field=field, value=value):
                e, sources, events = fixture(1, 0)
                events[0][field] = value
                with self.assertRaisesRegex(c.Stop, error):
                    p.plan_bank(e, sources, events)
        e, sources, events = fixture(1, 0)
        events[0]['timestamp'] = events[0]['prefix_max_timestamp'] = e['cutoff']
        sources[0]['last_frame_timestamp'] = e['cutoff']
        plan = p.plan_bank(e, sources, events)
        self.assertEqual(plan['selected_coverage']['phase'], {'settled_operation': 1})

    def test_future_prefix_forbidden_even_when_endpoint_itself_legal(self):
        for key, value in (('prefix_max_frame', 2), ('prefix_max_timestamp', 102.)):
            with self.subTest(key=key):
                e, sources, events = fixture(1, 0)
                events[0][key] = value
                with self.assertRaisesRegex(c.Stop, 'FUTURE_PREFIX'):
                    p.plan_bank(e, sources, events)

    def test_cutoff_frame_and_source_last_time_must_agree(self):
        e, sources, events = fixture(1, 0)
        sources[0]['last_frame_timestamp'] += 1
        with self.assertRaisesRegex(c.Stop, 'CUTOFF_FRAME_TIME_CONFLICT'):
            p.plan_bank(e, sources, events)

    def test_timestamp_regression_poison_does_not_erase_already_legal_prefix(self):
        e, sources, events = fixture(1, 0)
        last_good = add_event(e, sources, events, timestamp=200.)
        regressed = add_event(e, sources, events, timestamp=150.)
        after = add_event(e, sources, events, timestamp=300.)
        with self.assertRaisesRegex(c.Stop, 'LEGAL_TARGET_AFTER_TIMESTAMP_REGRESSION'):
            p.plan_bank(e, sources, events)
        regressed.update(legal_target=False, rejection_reason='NEW_TIMESTAMP_REGRESSION',
                         prefix_max_frame=None, prefix_max_timestamp=None)
        with self.assertRaisesRegex(c.Stop, 'LEGAL_TARGET_AFTER_TIMESTAMP_REGRESSION'):
            p.plan_bank(e, sources, events)
        after.update(legal_target=False, rejection_reason='POISONED_PREFIX',
                     prefix_max_frame=None, prefix_max_timestamp=None)
        plan = p.plan_bank(e, sources, events)
        self.assertEqual([r['uid'] for r in plan['references']], [last_good['uid']])
        self.assertEqual(plan['rejection_reasons'], {'NEW_TIMESTAMP_REGRESSION': 1, 'POISONED_PREFIX': 1})

    def test_source_must_be_complete_cutoff_enumeration(self):
        for key, value, error in (('processed_through_frame', 7, 'SOURCE_NOT_CUTOFF_BOUNDED'),
                                  ('last_frame_timestamp', 3701., 'SOURCE_WINDOW'),
                                  ('capture_start', 99., 'SOURCE_WINDOW'),
                                  ('enumeration', 'WHOLE_CAPTURE_SPARSE', 'SPARSE_OR_FUTURE'),
                                  ('adapter_contract', 'NEW_STREAM_FRONTEND', 'FRONTEND_CONTRACT')):
            with self.subTest(key=key):
                e, sources, events = fixture()
                sources[0][key] = value
                with self.assertRaisesRegex(c.Stop, error):
                    p.plan_bank(e, sources, events)

    def test_missing_or_duplicate_event_is_an_error_not_silent_filter(self):
        e, sources, events = fixture()
        with self.assertRaisesRegex(c.Stop, 'INCOMPLETE_EVENT_ENUMERATION'):
            p.plan_bank(e, sources, events[:-1])
        with self.assertRaisesRegex(c.Stop, 'DUPLICATE_EVENT'):
            p.plan_bank(e, sources, events + [copy.deepcopy(events[0])])

    def test_capture_alias_does_not_create_independent_component(self):
        e, sources, events = fixture()
        alias = copy.deepcopy(sources[0])
        alias['capture_id'] = 'renamed-same-bytes'
        with self.assertRaisesRegex(c.Stop, 'CAPTURE_ALIAS_DUPLICATE'):
            p.plan_bank(e, sources + [alias], events)

    def test_forbidden_roles_and_consumed_devices(self):
        for role in ('CAL', 'HOLDOUT', 'FINAL', 'select', 'viewed', 'report'):
            with self.subTest(role=role):
                e, sources, events = fixture()
                e['role'] = role
                with self.assertRaisesRegex(c.Stop, 'ROLE_FORBIDDEN'):
                    p.plan_bank(e, sources, events)
        for device in ('Borun Camera', ' netatmo CAMERA ', 'Ring Basestation'):
            with self.subTest(device=device):
                e, sources, events = fixture()
                e['device']['name'] = device
                with self.assertRaisesRegex(c.Stop, 'CONSUMED_DEVICE_FORBIDDEN'):
                    p.plan_bank(e, sources, events)

    def test_event_role_owner_source_and_uid_are_bound(self):
        for key, value, error in (('role', 'LEARN', 'EVENT_DEVICE_ROLE'),
                                  ('device', 'OTHER', 'EVENT_DEVICE_ROLE'),
                                  ('owner', '02:00:00:00:00:02', 'EVENT_OWNER'),
                                  ('source_sha256', '0' * 64, 'EVENT_SOURCE'),
                                  ('capture_id', 'missing', 'EVENT_SOURCE'),
                                  ('uid', '0' * 64, 'EVENT_UID')):
            with self.subTest(key=key):
                e, sources, events = fixture()
                events[0][key] = value
                with self.assertRaisesRegex(c.Stop, error):
                    p.plan_bank(e, sources, events)

    def test_canonical_key_and_component_session_identity_are_validated(self):
        for key, value, error in (('canonical_key', [17, ['10.0.0.1', 1], ['10.0.0.2', 443]], 'CANONICAL_KEY'),
                                  ('canonical_key', [6, ['10.0.0.2', 1], ['10.0.0.1', 443]], 'CANONICAL_ORDER'),
                                  ('canonical_key', [6, ['not-an-ip', 1], ['10.0.0.2', 443]], 'CANONICAL_IP'),
                                  ('canonical_key', [6, [123, 1], ['10.0.0.2', 443]], 'CANONICAL_IP'),
                                  ('canonical_key', [6, ['10.0.0.1', 65536], ['10.0.0.2', 443]], 'CANONICAL_PORT'),
                                  ('component_id', '0' * 64, 'COMPONENT_ID'),
                                  ('session_id', '0' * 64, 'SESSION_ID')):
            with self.subTest(key=key, error=error):
                e, sources, events = fixture()
                events[0][key] = value
                with self.assertRaisesRegex(c.Stop, error):
                    p.plan_bank(e, sources, events)

    def test_labels_scores_and_embeddings_cannot_enter_selector(self):
        for key in ('label', 'attack_label', 'score', 'embedding', 'future_query_fp'):
            with self.subTest(key=key):
                e, sources, events = fixture()
                events[0][key] = 0
                with self.assertRaisesRegex(c.Stop, 'SCHEMA_FIELDS'):
                    p.plan_bank(e, sources, events)

    def test_bool_and_nonfinite_numbers_cannot_sneak_through(self):
        for key, value in (('frame', True), ('protocol', True), ('timestamp', float('nan')),
                            ('timestamp', float('inf')), ('legal_target', 1)):
            with self.subTest(key=key, value=value):
                e, sources, events = fixture()
                events[0][key] = value
                with self.assertRaises(c.Stop):
                    p.plan_bank(e, sources, events)

    def test_normality_failure_invalidates_whole_bank(self):
        for key, value in (('status', 'CONTAMINATED'), ('status', 'UNVERIFIED'),
                            ('basis', 'UNKNOWN'), ('evidence_sha256', None),
                            ('inferred_from_scores_or_query_labels', True), ('source_sha256s', [])):
            with self.subTest(key=key, value=value):
                e, sources, events = fixture(40, 40)
                e['source_normality'][key] = value
                plan = p.plan_bank(e, sources, events)
                self.assertTrue(plan['bank_invalidated'])
                self.assertFalse(plan['normal_source_trusted'])
                self.assertEqual(plan['references'], [])
                self.assertEqual(plan['eligible_endpoints'], 80)
                self.assertEqual(p.route_query(plan, query(plan)), 'R')

    def test_certificate_must_cover_all_sources_exactly(self):
        e, sources, events = fixture(1, 0)
        add_capture(e, sources, events)
        e['source_normality']['source_sha256s'].pop()
        plan = p.plan_bank(e, sources, events)
        self.assertTrue(plan['bank_invalidated'])
        self.assertEqual(plan['references'], [])

    def test_unsupported_and_ambiguous_targets_do_not_register(self):
        e, sources, events = fixture(1, 0)
        events[0].update(protocol=1, canonical_key=None, component_id=None, session_id=None,
                         legal_target=False, rejection_reason='UNSUPPORTED_PROTOCOL',
                         prefix_max_frame=None, prefix_max_timestamp=None)
        plan = p.plan_bank(e, sources, events)
        self.assertEqual(plan['rejection_reasons'], {'UNSUPPORTED_PROTOCOL': 1})
        self.assertEqual(plan['references'], [])
        self.assertEqual(p.route_query(plan, query(plan)), 'R')
        e, sources, events = fixture(1, 0)
        events[0].update(legal_target=False, rejection_reason='OWNER_AMBIGUOUS_OR_OUTSIDE',
                         direction='ambiguous', prefix_max_frame=None, prefix_max_timestamp=None)
        plan = p.plan_bank(e, sources, events)
        self.assertEqual(plan['protocol_status']['6']['status'], 'OBSERVED_NO_LEGAL_REFERENCE')

    def test_shared_dhcp_cannot_be_counted_as_own_reference(self):
        e, sources, events = fixture(0, 1)
        row = events[0]
        row['canonical_key'] = [17, ['0.0.0.0', 68], ['255.255.255.255', 67]]
        row['component_id'] = c.legacy_digest([row['owner'], row['canonical_key']])
        row['session_id'] = c.legacy_digest([row['owner'], row['capture_id'], row['canonical_key']])
        with self.assertRaisesRegex(c.Stop, 'SHARED_DHCP'):
            p.plan_bank(e, sources, events)
        row.update(legal_target=False, rejection_reason='SHARED_DHCP_CONTEXT',
                   prefix_max_frame=None, prefix_max_timestamp=None)
        self.assertEqual(p.plan_bank(e, sources, events)['references'], [])

    def test_legal_endpoint_cannot_follow_ambiguous_or_invalid_receipt(self):
        e, sources, events = fixture(1, 0)
        events[0]['direction'] = 'ambiguous'
        with self.assertRaisesRegex(c.Stop, 'LEGAL_TARGET_REASON'):
            p.plan_bank(e, sources, events)
        events[0].update(legal_target=False, rejection_reason='INCOMPLETE_TARGET')
        with self.assertRaisesRegex(c.Stop, 'INVALID_PREFIX_RECEIPT'):
            p.plan_bank(e, sources, events)

    def test_fixed_window_cannot_extend_early_stop_or_retroactively_declare(self):
        for key, value in (('cutoff', 3701.), ('cutoff', 3600.), ('wall_seconds', 3600.),
                            ('declared_at', 100.), ('roster_frozen_before_outcomes', False)):
            with self.subTest(key=key):
                e, sources, events = fixture()
                e[key] = value
                with self.assertRaises(c.Stop):
                    p.plan_bank(e, sources, events)

    def test_phase_boundaries_have_one_slot_and_cutoff_in_last_slot(self):
        e, _, _ = fixture()
        for name, start, _ in c.PHASES:
            self.assertEqual(p.phase_at(e, e['t0'] + start), name)
        self.assertEqual(p.phase_at(e, e['cutoff']), 'settled_operation')
        with self.assertRaisesRegex(c.Stop, 'PHASE_TIME'):
            p.phase_at(e, e['cutoff'] + .1)

    def test_active_passive_and_unavailable_are_distinct(self):
        e, sources, events = fixture()
        self.assertEqual(p.plan_bank(e, sources, events)['functional_coverage'],
                         'VERIFIED_APPLICABLE_OPERATIONS')
        e['operations_log'][2]['outcome'] = 'UNAVAILABLE'
        self.assertEqual(p.plan_bank(e, sources, events)['functional_coverage'], 'PARTIAL')
        e['operations_log'] = []
        self.assertEqual(p.plan_bank(e, sources, events)['functional_coverage'], 'UNKNOWN_PASSIVE')

    def test_not_applicable_stays_idle_for_entire_slot(self):
        e, sources, events = fixture()
        e['function_declarations'][2]['applicability'] = 'NOT_APPLICABLE'
        e['function_declarations'][2]['planned_actions'] = []
        e['operations_log'][2]['outcome'] = 'NOT_APPLICABLE_IDLE'
        e['operations_log'][2]['completed_action_ids'] = []
        self.assertEqual(p.plan_bank(e, sources, events)['functional_coverage'],
                         'VERIFIED_APPLICABLE_OPERATIONS')
        e['operations_log'][2]['end'] -= 1
        with self.assertRaisesRegex(c.Stop, 'NA_MUST_REMAIN_IDLE'):
            p.plan_bank(e, sources, events)

    def test_unavailable_cannot_be_relabelled_na_and_time_cannot_be_reallocated(self):
        e, sources, events = fixture()
        e['operations_log'][2]['outcome'] = 'NOT_APPLICABLE_IDLE'
        with self.assertRaisesRegex(c.Stop, 'UNAVAILABLE_IS_NOT_NA'):
            p.plan_bank(e, sources, events)
        e['operations_log'][2]['outcome'] = 'COMPLETED'
        e['operations_log'][2]['end'] += 1
        with self.assertRaisesRegex(c.Stop, 'OPERATION_OUTSIDE_SLOT'):
            p.plan_bank(e, sources, events)

    def test_unknown_health_is_not_full_functional_coverage(self):
        e, sources, events = fixture()
        e['capture_health'] = sources[0]['capture_health'] = 'UNKNOWN'
        self.assertEqual(p.plan_bank(e, sources, events)['functional_coverage'], 'PARTIAL')
        e['capture_health'] = 'HEALTHY'
        with self.assertRaisesRegex(c.Stop, 'HEALTH_NOT_VERIFIED'):
            p.plan_bank(e, sources, events)

    def test_operations_need_declared_actions_and_nonzero_duration(self):
        for field, value, error in (('completed_action_ids', ['unplanned-test-action'], 'UNPLANNED_OPERATION'),
                                    ('completed_action_ids', [], 'INCOMPLETE_OR_UNKNOWN_FUNCTION'),
                                    ('end', 1000., 'INCOMPLETE_OR_UNKNOWN_FUNCTION')):
            with self.subTest(field=field, value=value):
                e, sources, events = fixture()
                e['operations_log'][2][field] = value
                with self.assertRaisesRegex(c.Stop, error):
                    p.plan_bank(e, sources, events)
        e, sources, events = fixture()
        e['operations_log'][1]['start'] += 1
        with self.assertRaisesRegex(c.Stop, 'IDLE_SLOT_INCOMPLETE'):
            p.plan_bank(e, sources, events)
        e, sources, events = fixture()
        e['function_declarations'][2]['planned_actions'] = []
        with self.assertRaisesRegex(c.Stop, 'APPLICABLE_ACTIONS_MISSING'):
            p.plan_bank(e, sources, events)

    def test_protocol_declaration_is_union_not_promise_of_future_coverage(self):
        e, sources, events = fixture(0, 2)
        e['declared_protocols'] = [6, 1]
        e['protocol_declaration_complete'] = False
        plan = p.plan_bank(e, sources, events)
        self.assertEqual(plan['required_protocols'], [6, 17])
        self.assertFalse(plan['protocol_declaration_complete'])
        self.assertEqual(plan['protocol_status']['6']['status'], 'NOT_OBSERVED')

    def test_routes_preserve_registration_and_per_protocol_qualification(self):
        for tcp, udp, tcp_route, udp_route in ((2, 2, 'Q_PLUS_VERIFIER', 'Q_PLUS_VERIFIER'),
                                                (1, 2, 'Q', 'Q_PLUS_VERIFIER'),
                                                (0, 2, 'Q', 'Q_PLUS_VERIFIER'),
                                                (1, 0, 'Q', 'Q'), (0, 0, 'R', 'R')):
            with self.subTest(tcp=tcp, udp=udp):
                plan = p.plan_bank(*fixture(tcp, udp))
                self.assertEqual(p.route_query(plan, query(plan, 6)), 'R')
                self.assertEqual(p.route_query(plan, query(plan, 6), ready(plan)), tcp_route)
                self.assertEqual(p.route_query(plan, query(plan, 17), ready(plan)), udp_route)

    def test_encoding_delay_and_cutoff_queries_retain_r(self):
        plan = p.plan_bank(*fixture())
        for timestamp in (100., 3700., 3749.):
            self.assertEqual(p.route_query(plan, query(plan, timestamp=timestamp), ready(plan)), 'R')
        self.assertEqual(p.route_query(plan, query(plan, timestamp=3750.), ready(plan)), 'Q_PLUS_VERIFIER')

    def test_readiness_is_exact_bank_and_artifact_receipt(self):
        plan = p.plan_bank(*fixture())
        for key, value, error in (('plan_sha256', '0' * 64, 'READY_BANK_IDENTITY'),
                                  ('detector_contract_sha256', '0' * 64, 'READY_BANK_IDENTITY'),
                                  ('reference_uids', [], 'READY_BANK_IDENTITY'),
                                  ('causal_snapshots_verified', False, 'READY_VERIFICATION'),
                                  ('frozen_artifacts_verified', False, 'READY_VERIFICATION'),
                                  ('synthetic', False, 'READY_VERIFICATION'),
                                  ('ready_at', 3699., 'READY_BEFORE_CUTOFF')):
            with self.subTest(key=key):
                receipt = ready(plan)
                receipt[key] = value
                with self.assertRaisesRegex(c.Stop, error):
                    p.route_query(plan, query(plan), receipt)

    def test_mutating_plan_is_detected_before_routing(self):
        plan = p.plan_bank(*fixture())
        receipt = ready(plan)
        plan['references'].pop()
        with self.assertRaisesRegex(c.Stop, 'PLAN_MUTATED'):
            p.route_query(plan, query(plan), receipt)

    def test_rehash_cannot_promote_singleton_or_inject_duplicates(self):
        plan = p.plan_bank(*fixture(1, 0))
        plan['protocol_status']['6']['status'] = 'REFERENCE_AVAILABLE'
        plan['plan_sha256'] = c.digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
        with self.assertRaisesRegex(c.Stop, 'PLAN_PROTOCOL_QUALIFICATION'):
            p.route_query(plan, query(plan), ready(plan))
        plan = p.plan_bank(*fixture(1, 0))
        plan['references'].append(copy.deepcopy(plan['references'][0]))
        plan['plan_sha256'] = c.digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
        with self.assertRaisesRegex(c.Stop, 'PLAN_UNIQUE_CAPACITY'):
            p.route_query(plan, query(plan), ready(plan))

    def test_query_device_role_and_owner_cannot_cross_bank(self):
        plan = p.plan_bank(*fixture())
        for key, value in (('device', 'OTHER'), ('role', 'CAL'), ('owner', '02:00:00:00:00:02')):
            q = query(plan)
            q[key] = value
            with self.assertRaisesRegex(c.Stop, 'QUERY_IDENTITY_ROLE'):
                p.route_query(plan, q, ready(plan))

    def test_future_pool_is_strict_and_never_filters_illegal_rows(self):
        plan = p.plan_bank(*fixture())
        good = query(plan)
        self.assertEqual(p.validate_future_queries(plan, [good]), {'queries_checked': 1, 'queries_removed': 0})
        for timestamp in (plan['cutoff'], plan['cutoff'] - 1):
            with self.assertRaisesRegex(c.Stop, 'QUERY_NOT_STRICTLY_FUTURE'):
                p.validate_future_queries(plan, [good, query(plan, timestamp=timestamp)])
        q = query(plan)
        q.update(capture_id='synthetic-capture-0', frame=6)
        with self.assertRaisesRegex(c.Stop, 'QUERY_FRAME_NOT_AFTER_CUTOFF'):
            p.validate_future_queries(plan, [q])
        q['frame'] = 7
        self.assertEqual(p.validate_future_queries(plan, [q])['queries_removed'], 0)

    def test_unsupported_protocol_and_original_unsupported_target_keep_legacy_route(self):
        plan = p.plan_bank(*fixture())
        q = query(plan, protocol=1)
        self.assertEqual(p.route_query(plan, q, ready(plan)), 'LEGACY_UNSUPPORTED_CONTRACT')
        q = query(plan)
        q['legacy_supported'] = False
        self.assertEqual(p.route_query(plan, q, ready(plan)), 'LEGACY_UNSUPPORTED_CONTRACT')

    def test_unsupported_or_untrusted_future_query_cannot_bypass_frame_order(self):
        e, sources, events = fixture()
        for untrusted in (False, True):
            e['source_normality']['status'] = 'CONTAMINATED' if untrusted else 'VERIFIED'
            plan = p.plan_bank(e, sources, events)
            for protocol in (1, 6):
                q = query(plan, protocol=protocol)
                q.update(capture_id=sources[0]['capture_id'], frame=sources[0]['cutoff_frame'])
                with self.subTest(protocol=protocol, untrusted=untrusted), \
                     self.assertRaisesRegex(c.Stop, 'QUERY_FRAME_NOT_AFTER_CUTOFF'):
                    p.validate_future_queries(plan, [q])

    def test_synthetic_fixture_cannot_certify_real_plan(self):
        plan = p.plan_bank(*fixture())
        plan['synthetic'] = False
        with self.assertRaisesRegex(c.Stop, 'FIXTURE_CANNOT_CERTIFY_REAL_BANK'):
            ready(plan)


class FileAndAuthorityContracts(unittest.TestCase):
    def test_confined_rejects_traversal_and_absolute_paths_on_every_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../secret', 'foo/../../secret', r'foo\..\secret',
                         '/etc/passwd', r'C:\secret', 'C:secret', r'\\server\share\x',
                         r'\rooted', 'safe:stream', '.', ''):
                with self.subTest(name=name), self.assertRaises(c.Stop):
                    c.confined(tmp, name)
            self.assertEqual(c.confined(tmp, r'runs\safe.json'), Path(tmp).resolve() / 'runs' / 'safe.json')

    def test_json_duplicate_keys_and_nonfinite_constants_are_rejected(self):
        for raw in ('{"authorized":false,"authorized":true}', '{"x": NaN}', '{"x": Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(c.Stop):
                c.parse_json(raw)

    def test_pins_detect_single_byte_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.json'
            raw = b'{"synthetic":true}\n'
            path.write_bytes(raw)
            pin = hashlib.sha256(raw).hexdigest()
            self.assertEqual(c.pinned_json(path, pin), {'synthetic': True})
            path.write_bytes(raw + b' ')
            with self.assertRaisesRegex(c.Stop, 'FILE_IDENTITY'):
                c.pinned_json(path, pin)

    def test_cli_denies_before_any_input_read_or_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'runs' / 'denied'
            with mock.patch.object(Path, 'read_text', side_effect=AssertionError('read forbidden')), \
                 mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('read forbidden')), \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                status = runner.main(['--root', tmp, 'metadata-plan', '--scope', 'missing.json', '--output', str(out)])
            self.assertEqual(status, 1)
            self.assertIn('REAL_METADATA_NOT_AUTHORIZED', err.getvalue())
            self.assertFalse(out.exists())

    def _test_root(self, tmp):
        """Copy only two small frozen contract files; everything else is synthetic."""
        root = Path(tmp)
        for name in (c.POLICY_REL, c.CONTRACT_REL):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        episode, sources, events = fixture()
        episode['synthetic'] = False  # Tests I/O branch, never denotes real observations.
        episode['episode_id'] = 'TEST_ONLY_GENERATED_NOT_A_REAL_EPISODE'
        inputs = {}
        for key, value in (('episode', episode), ('sources', sources), ('events', events)):
            path = root / ('test-only-' + key + '.json')
            raw = json.dumps(value, sort_keys=True).encode()
            path.write_bytes(raw)
            inputs[key] = {'path': path.name, 'sha256': hashlib.sha256(raw).hexdigest()}
        out = root / 'runs' / 'test-only-output'
        scope = {'schema': 'commissioning-metadata-scope-v1', 'authorized': True,
                 'policy_sha256': c.POLICY_SHA, 'root': str(root), 'output': str(out),
                 'stage': 'LEARN_DEV_METADATA_PLAN', 'roles': ['LEARN', 'DEV'], 'retries': 0,
                 'inputs': inputs, 'forbidden': {k: False for k in runner.FORBIDDEN}}
        return root, out, scope

    def _scope_write(self, root, scope):
        name = 'test-only-scope.json'
        (root / name).write_text(json.dumps(scope), encoding='utf-8')
        return name

    def test_scope_rejects_real_actions_changed_roles_retry_and_duplicate_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, baseline = self._test_root(tmp)
            changes = [('authorized', False), ('roles', ['DEV']), ('retries', 1),
                       ('stage', 'TRAIN'), ('policy_sha256', '0' * 64)]
            for key, value in changes:
                scope = copy.deepcopy(baseline)
                scope[key] = value
                with self.subTest(key=key), self.assertRaises(c.Stop):
                    runner.authorize_metadata(scope, root, out, True)
            scope = copy.deepcopy(baseline)
            scope['forbidden']['model_forward'] = True
            with self.assertRaisesRegex(c.Stop, 'REAL_ACTION_FORBIDDEN'):
                runner.authorize_metadata(scope, root, out, True)
            scope = copy.deepcopy(baseline)
            scope['inputs']['events'] = copy.deepcopy(scope['inputs']['sources'])
            with self.assertRaisesRegex(c.Stop, 'DUPLICATE_INPUT_PATH'):
                runner.authorize_metadata(scope, root, out, True)

    def test_authorized_test_only_metadata_io_completes_without_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, scope = self._test_root(tmp)
            scope_name = self._scope_write(root, scope)
            plan = runner.execute_metadata(root, scope_name, out, explicit=True)
            status = json.loads((out / 'status.json').read_text())
            self.assertEqual(status['status'], 'METADATA_PLAN_COMPLETE_NOT_ENCODED')
            self.assertFalse(status['bank_registered'])
            self.assertEqual(status['real_decodes'], 0)
            self.assertEqual(status['real_forwards'], 0)
            self.assertEqual(status['optimizer_updates'], 0)
            self.assertFalse(status['new_confirmation_opened'])
            self.assertEqual(p.route_query(plan, query(plan)), 'R')
            for line in (out / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), sha)
            with self.assertRaisesRegex(c.Stop, 'OUTPUT_EXISTS_NO_RETRY'):
                runner.execute_metadata(root, scope_name, out, explicit=True)

    def test_corrupt_input_stops_once_and_cannot_retry_same_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, scope = self._test_root(tmp)
            scope_name = self._scope_write(root, scope)
            (root / scope['inputs']['events']['path']).write_bytes(b'[]')
            with self.assertRaisesRegex(c.Stop, 'FILE_IDENTITY'):
                runner.execute_metadata(root, scope_name, out, explicit=True)
            failure = json.loads((out / 'failure.json').read_text())
            self.assertEqual(failure['status'], 'STOPPED_NO_RETRY')
            self.assertEqual(failure['retries'], 0)
            self.assertFalse((out / 'bank_plan.json').exists())
            with self.assertRaisesRegex(c.Stop, 'OUTPUT_EXISTS_NO_RETRY'):
                runner.execute_metadata(root, scope_name, out, explicit=True)

    def test_scope_path_escape_denied_before_protected_input_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, scope = self._test_root(tmp)
            scope['inputs']['events']['path'] = '../protected.json'
            scope_name = self._scope_write(root, scope)
            with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('input read forbidden')):
                with self.assertRaisesRegex(c.Stop, 'PATH_ESCAPE'):
                    runner.execute_metadata(root, scope_name, out, explicit=True)
            self.assertFalse(out.exists())

    def test_generated_demo_has_no_real_actions_and_cannot_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = self._test_root(tmp)
            out = root / 'runs' / 'test-only-demo'
            cases = runner.synthetic_demo(root, out)
            self.assertEqual(len(cases), 5)
            status = json.loads((out / 'status.json').read_text())
            self.assertEqual(status['real_inputs_read'], 0)
            self.assertEqual(status['model_forwards'], 0)
            self.assertEqual(status['real_decodes'], 0)
            with self.assertRaisesRegex(c.Stop, 'SYNTHETIC_OUTPUT_EXISTS_OR_OUTSIDE_RUNS'):
                runner.synthetic_demo(root, out)


if __name__ == '__main__':
    unittest.main()
