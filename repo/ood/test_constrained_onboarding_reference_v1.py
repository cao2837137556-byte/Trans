"""Generated-only selection/causality/descriptor tests; never real assets."""
import copy
import contextlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import constrained_onboarding_reference_v1 as r
import continuous_input_v3 as inp
import query_tail_core_v2 as legacy_query
from test_continuous_repair_v3 import packet

SOURCE = 'a'*64
REGISTRY = [dict(owner='aa', device='Device A', partition='DEV')]
SPEC = dict(capture_id='normal', sha256=SOURCE, t0=0., provenance='normal',
            normality_evidence='generated independent normal capture', known_macs=['aa', 'cc'])
DECODER = dict(name='generated decoder', version='1', unfiltered=True, occurrence='f')


def make_row(index, timestamp, proto=6, *, owner='aa', device='Device A', capture='normal'):
    key = (proto, ('1.1.1.1', 1000+index), ('2.2.2.2', 80))
    row = dict(uid=r.digest([SOURCE, index, owner]), frame=index, timestamp=float(timestamp),
               source_sha256=SOURCE, owner=owner, device=device, capture_id=capture,
               protocol=proto, partition='DEV', use='REFERENCE', label=0,
               canonical_key=key, component_id=r.digest([owner, key]),
               session_id=r.digest([owner, capture, key]), reference_end=3600.,
               bank_end_frame=1000, activity='UNKNOWN', activity_verified=False)
    return row


def census(rows, duration=3600, registry=None):
    rr = copy.deepcopy(rows)
    for row in rr:
        row['reference_end'] = float(duration)
    receipt = dict(generator_version=r.VERSION, status='COMPLETE',
                   enumeration='ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT', window_closed=True,
                   duration_seconds=duration, t0=0., cutoff=float(duration), cutoff_frame=1000,
                   candidate_rows=len(rr), candidates_sha256=r.digest(rr), decoder_identity=DECODER,
                   source_sha256=SOURCE, normality_evidence='generated normal', capture_id='normal',
                   device_registry=REGISTRY if registry is None else registry)
    return rr, receipt


def body_row(proto=6, flags=2):
    p = packet(1, inp.NS, proto=proto, flags=flags)
    key = (proto, ('1.1.1.1', 1234), ('2.2.2.2', 80))
    ns = ('aa', 'normal', key)
    state = inp.RecentState('aa', ns, proto); state.append(p)
    flow, values, provenance = state.snapshot()
    body = dict(flow=flow, state=values, provenance=provenance, source_sha256=SOURCE)
    row = make_row(1, 1, proto)
    row.update(canonical_key=key, component_id=r.digest(['aa', key]), session_id=r.digest(ns))
    return body, row


def stream_packet(frame, seconds, port=1234, proto=6):
    p = packet(frame, int(seconds*inp.NS), proto=proto)
    p['tcp.srcport'] = str(port); p['udp.srcport'] = str(port)
    return p


class SelectionTests(unittest.TestCase):
    def test_b0_hash_protocol_round_robin_and_order_invariance(self):
        rows, receipt = census([make_row(i, i*10, 6 if i <= 50 else 17) for i in range(1, 101)])
        plan = r.plan_banks(rows, receipt, t0=0., policy='B0')
        self.assertEqual(len(plan['rows']), 64)
        self.assertEqual([b['count'] for b in plan['banks']], [32, 32])
        self.assertEqual({x['component_id'] for x in plan['rows'] if x['protocol']==6},
                         {x['component_id'] for x in sorted(rows[:50], key=r._hash_order)[:32]})
        rr = list(reversed(rows)); rec = dict(receipt, candidates_sha256=r.digest(rr))
        self.assertEqual(plan['rows'], r.plan_banks(rr, rec, t0=0., policy='B0')['rows'])

    def test_b1_same_actual_count_and_protocol_quotas_with_strata(self):
        rows = [make_row(i, (i % 4)*900+10, 6 if i <= 70 else 17) for i in range(1, 91)]
        rows, receipt = census(rows)
        a = r.plan_banks(rows, receipt, t0=0., policy='B0')
        b = r.plan_banks(rows, receipt, t0=0., policy='B1')
        self.assertEqual([x['count'] for x in a['banks']], [44, 20])
        self.assertEqual([x['count'] for x in a['banks']], [x['count'] for x in b['banks']])
        counts = [sum(x['protocol']==6 and int(x['timestamp']//900)==q for x in b['rows']) for q in range(4)]
        self.assertEqual(counts, [11, 11, 11, 11])

    def test_complete_small_bank_equivalence_and_singleton_not_duplicated(self):
        rows, receipt = census([make_row(1, 1), make_row(2, 2, 17)])
        a = r.plan_banks(rows, receipt, t0=0., policy='B0')
        b = r.plan_banks(rows, receipt, t0=0., policy='B1')
        self.assertEqual(a['rows'], b['rows'])
        self.assertEqual([x['count'] for x in a['banks']], [1, 1])
        self.assertTrue(all(x['status']=='INSUFFICIENT_DISTINCT_COMPONENTS' for x in a['banks']))

    def test_empty_bank_keeps_explicit_device_protocol_roster(self):
        rows, receipt = census([])
        plan = r.plan_banks(rows, receipt, t0=0., policy='B0')
        self.assertEqual(plan['rows'], [])
        self.assertEqual([x['count'] for x in plan['banks']], [0, 0])

    def test_whole_bank_cutoff_cannot_shrink_to_selected_representative(self):
        rows, receipt = census([make_row(1, 10), make_row(2, 20)])
        plan = r.plan_banks(rows, receipt, t0=0., policy='B0')
        self.assertTrue(all(x['reference_end']==3600 and x['bank_end_frame']==1000 for x in plan['rows']))
        rows[0]['reference_end'] = 20
        receipt['candidates_sha256'] = r.digest(rows)
        with self.assertRaisesRegex(RuntimeError, 'WHOLE_BANK_CUTOFF'):
            r.plan_banks(rows, receipt, t0=0., policy='B0')

    def test_reject_sparse_historical_selection_even_with_forged_receipt(self):
        rows, receipt = census([make_row(1, 1)])
        rows[0]['sample_count'] = 32; receipt['candidates_sha256'] = r.digest(rows)
        with self.assertRaisesRegex(RuntimeError, 'SPARSE_HISTORICAL'):
            r.plan_banks(rows, receipt, t0=0., policy='B0')
        rows[0].pop('sample_count'); receipt['candidates_sha256'] = r.digest(rows)
        receipt['enumeration'] = 'SAMPLED_ENDPOINTS'
        with self.assertRaisesRegex(RuntimeError, 'COMPLETE_CENSUS'):
            r.plan_banks(rows, receipt, t0=0., policy='B0')

    def test_activity_requires_verified_evidence_and_unknown_is_not_invented(self):
        self.assertEqual(r._activity(dict(activity='recording')), 'UNKNOWN')
        self.assertEqual(r._activity(dict(activity='ACTIVE_UNANNOTATED', activity_verified=True)), 'UNKNOWN')
        self.assertEqual(r._activity(dict(activity='recording', activity_verified=True, activity_evidence='operation log')), 'recording')
        with self.assertRaisesRegex(RuntimeError, 'ACTIVITY_EVIDENCE'):
            r._activity(dict(activity='recording', activity_verified=True))

    def test_b2_uses_own_universe_and_same_cap(self):
        rows, receipt = census([make_row(i, 3600+i, 17) for i in range(1, 100)], 7200)
        plan = r.plan_banks(rows, receipt, t0=0., policy='B2')
        self.assertEqual(len(plan['rows']), 64)
        self.assertEqual([b['count'] for b in plan['banks']], [0, 64])
        self.assertTrue(all(x['reference_end']==7200 for x in plan['rows']))
        with self.assertRaisesRegex(RuntimeError, 'CENSUS_WINDOW'):
            r.plan_banks(rows, receipt, t0=0., policy='B1')

    def test_reject_duplicate_components_and_mismatched_owner(self):
        rows, receipt = census([make_row(1, 1)])
        rows.append(dict(rows[0])); receipt.update(candidate_rows=2, candidates_sha256=r.digest(rows))
        with self.assertRaisesRegex(RuntimeError, 'CANDIDATE_COMPONENT_DUPLICATE'):
            r.plan_banks(rows, receipt, t0=0., policy='B0')
        rows, receipt = census([make_row(1, 1, owner='zz')])
        with self.assertRaisesRegex(RuntimeError, 'DEVICE_REGISTRY_JOIN'):
            r.plan_banks(rows, receipt, t0=0., policy='B0')


class DescriptorTests(unittest.TestCase):
    def test_reference_transform_exactly_matches_frozen_query_transform(self):
        for proto, flags in [(6, 2), (6, 18), (6, 4), (6, 511), (17, 0)]:
            with self.subTest(proto=proto, flags=flags):
                body, row = body_row(proto, flags)
                before = copy.deepcopy(row)
                q, info = r.reference_descriptor(body, row)
                query = dict(row, use='QUERY')
                old_q, old_info = legacy_query.descriptor(body, query)
                np.testing.assert_array_equal(q, old_q)
                self.assertEqual(info, old_info)
                np.testing.assert_array_equal(r.query_descriptor(body, query)[0], old_q)
                self.assertEqual(row, before)
                with self.assertRaisesRegex(RuntimeError, 'QUERY_ROLE'):
                    legacy_query.descriptor(body, row)

    def test_role_rejections_do_not_forge_reference_as_query(self):
        body, row = body_row()
        with self.assertRaisesRegex(RuntimeError, 'QUERY_ROLE'):
            r.query_descriptor(body, row)
        for changed in [dict(use='QUERY'), dict(label=1), dict(partition='HOLDOUT')]:
            bad = dict(row, **changed)
            with self.assertRaises(RuntimeError):
                r.reference_descriptor(body, bad)

    def test_source_frame_namespace_protocol_current_packet_guards(self):
        body, row = body_row()
        mutations = [dict(source_sha256='b'*64), dict(uid='b'*64), dict(frame=2),
                     dict(session_id='b'*64), dict(component_id='b'*64), dict(protocol=17),
                     dict(timestamp=1.01), dict(reference_end=.5), dict(bank_end_frame=0)]
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                r.reference_descriptor(body, dict(row, **change))
        with self.assertRaisesRegex(RuntimeError, 'BODY_SOURCE'):
            r.reference_descriptor(body, row, source_sha256='b'*64)

    def test_duplicate_current_future_packet_and_flow_header_join(self):
        body, row = body_row()
        bad = copy.deepcopy(body); bad['flow']['burst_tokens'][0][5] += 1
        with self.assertRaisesRegex(RuntimeError, 'FLOW_HEADER_JOIN'):
            r.reference_descriptor(bad, row)
        bad = copy.deepcopy(body); bad['provenance']['bursts'][0]['frames'][0] = 2
        with self.assertRaisesRegex(RuntimeError, 'FUTURE_OR_AGED_PACKET'):
            r.reference_descriptor(bad, row)
        bad = copy.deepcopy(body)
        for key in ('frames', 'times_ns', 'headers'):
            bad['provenance']['bursts'][0][key] *= 2
        bad['flow']['counts'][0] = 2; bad['flow']['burst_tokens'][0] *= 2
        with self.assertRaisesRegex(RuntimeError, 'BURST_ORDER'):
            r.reference_descriptor(bad, row)

    def test_pinned_old_bank_reads_subset_by_uid_and_real_parent_slots(self):
        body, row = body_row()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'snapshots.sqlite'
            db = sqlite3.connect(str(path))
            db.execute('CREATE TABLE snapshots(uid TEXT PRIMARY KEY,role TEXT,slot INTEGER,protocol INTEGER,body TEXT)')
            db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)', (row['uid'], 'SOURCE_REFS', 104, 6, json.dumps(body)))
            db.commit(); db.close()
            pin = r.sha(path)
            q = r.extract_old_bank_q14(path, [row], pin)
            np.testing.assert_array_equal(q[0], r.reference_descriptor(body, row)[0])
            with self.assertRaisesRegex(RuntimeError, 'PARENT_SLOT'):
                r.extract_old_bank_q14(path, [dict(row, parent_slot=0)], pin)
            with self.assertRaisesRegex(RuntimeError, 'IDENTITY'):
                r.extract_old_bank_q14(path, [row], 'b'*64)

    def test_parent_unsw_without_tuple_uses_pinned_source_and_namespace(self):
        body, row = body_row()
        row.pop('canonical_key')
        with self.assertRaisesRegex(RuntimeError, 'CANONICAL_KEY_REQUIRED'):
            r.reference_descriptor(body, row)
        np.testing.assert_array_equal(r.reference_descriptor(body, row, source_sha256=SOURCE)[0],
                                      legacy_query.descriptor(body, dict(row, use='QUERY'))[0])


class CompleteDecodeTests(unittest.TestCase):
    def prepare(self, packets, duration=7200):
        return r.prepare_decoded_capture(packets, SPEC, REGISTRY, t0=0.,
                    duration_seconds=duration, decoder_identity=DECODER)

    def test_own_window_last_representatives_and_current_q14(self):
        packets = [stream_packet(1, 0), stream_packet(2, 3599), stream_packet(3, 3600),
                   stream_packet(4, 3601), stream_packet(5, 7199), stream_packet(6, 7201)]
        result = self.prepare(packets)
        self.assertEqual(result[3600]['rows'][0]['frame'], 3)
        self.assertEqual(result[7200]['rows'][0]['frame'], 5)
        self.assertEqual(result[3600]['receipt']['legal_endpoint_count'], 3)
        self.assertEqual(result[7200]['receipt']['legal_endpoint_count'], 5)
        for duration in (3600, 7200):
            for row in result[duration]['rows']:
                r.reference_descriptor(result[duration]['snapshots'][row['uid']], row)

    def test_future_perturbation_cannot_change_closed_first_hour(self):
        baseline = [stream_packet(1, 0), stream_packet(2, 100), stream_packet(3, 3601)]
        before = self.prepare(baseline, 3600)
        future = stream_packet(3, 3601); future['tcp.flags'] = 'NOT_A_HEADER'
        after = self.prepare(baseline[:2]+[future, {'malformed': 'never consumed'}], 3600)
        self.assertEqual(before, after)

    def test_unselected_or_invalid_packets_still_determine_whole_bank_frame_cutoff(self):
        outside = stream_packet(3, 3599); outside['eth.src'] = 'cc'
        result = self.prepare([stream_packet(1, 0), stream_packet(2, 10), outside, stream_packet(4, 3601)], 3600)
        row = result[3600]['rows'][0]
        self.assertEqual(row['frame'], 2)
        self.assertEqual(row['bank_end_frame'], 3)
        self.assertEqual(row['reference_end'], 3600)

    def test_owner_ambiguity_does_not_create_normal_reference(self):
        mixed = stream_packet(2, 10); mixed['eth.dst'] = 'cc'
        result = self.prepare([stream_packet(1, 0), mixed, stream_packet(3, 3601)], 3600)
        self.assertEqual(result[3600]['rows'][0]['frame'], 1)

    def test_incomplete_window_and_skipped_capture_frames_fail(self):
        with self.assertRaisesRegex(RuntimeError, 'INCOMPLETE_WINDOW'):
            self.prepare([stream_packet(1, 0)], 3600)
        with self.assertRaisesRegex(RuntimeError, 'NONCONTIGUOUS_CAPTURE_FRAME'):
            self.prepare([stream_packet(1, 0), stream_packet(3, 100)], 3600)

    def test_missing_header_taint_does_not_silently_become_reference(self):
        damaged = stream_packet(2, 10); damaged['tcp.flags'] = ''
        result = self.prepare([stream_packet(1, 0), damaged, stream_packet(3, 11), stream_packet(4, 3601)], 3600)
        self.assertEqual(result[3600]['rows'][0]['frame'], 1)

    def test_saved_preparation_contains_real_q_snapshots_but_no_invented_e3(self):
        prepared = self.prepare([stream_packet(1, 0), stream_packet(2, 100, port=5678), stream_packet(3, 7201)])
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/'prepared'; r.save_prepared(out, prepared)
            receipt = json.loads((out/'receipt.json').read_text())
            self.assertEqual(receipt['status'], 'PREPARATION_REQUIRED')
            self.assertEqual(receipt['real_E3_forwards'], 0)
            self.assertFalse(list(out.rglob('*e3*.npy')))
            for policy in r.POLICIES:
                q = np.load(out/policy/'reference_q14.npy', allow_pickle=False)
                self.assertEqual(q.shape, (2, 14))
                rows = r._rows(out/policy/'references.jsonl.gz')
                snapshots = r._rows(out/policy/'selected_snapshots.jsonl.gz')
                for i, (row, entry) in enumerate(zip(rows, snapshots)):
                    self.assertEqual(row['uid'], entry['uid'])
                    np.testing.assert_array_equal(q[i], r.reference_descriptor(entry['body'], row)[0])


def fake_runtime(_root):
    """Tiny generated tokenizer/collator/encoder; no checkpoint or real data."""
    import torch
    def tokenizer(columns):
        flow = {k: v[0] for k, v in columns.items()}
        width = 12 if flow['protocol']==6 else 6
        tokens = []
        for flat in flow['burst_tokens']:
            vals = [v+1 for begin in range(0, len(flat), width+6) for v in flat[begin:begin+width]]
            tokens.append([65537]+vals)
        example = dict(input_ids=tokens, attention_mask=[[1]*len(t) for t in tokens],
                       dataset_burst_sizes=[len(t)-1 for t in tokens], protocol=flow['protocol'])
        return {k: [v] for k, v in example.items()}
    def collator(examples):
        width = max(examples[0]['dataset_burst_sizes'])+1
        ids, masks = [], []
        for e in examples:
            ids.append([v for t in e['input_ids'] for v in t+[0]*(width-len(t))])
            masks.append([v for t in e['attention_mask'] for v in t+[0]*(width-len(t))])
        out = dict(input_ids=torch.tensor(ids), attention_mask=torch.tensor(masks))
        for key in ('direction', 'iats', 'bytes', 'pkt_count', 'protocol', 'dataset_burst_sizes'):
            out[key] = torch.zeros((len(examples), 1), dtype=torch.int64)
        return out
    def forward(_model, batches, device):
        values = batches[0]['input_ids'].sum(1).numpy().astype(np.float32)
        return np.repeat(values[:, None], 768, axis=1)
    return SimpleNamespace(core=SimpleNamespace(e3_forward_batches=forward)), None, object(), tokenizer, collator


class PreparationEntrypointTests(unittest.TestCase):
    def test_encoder_rejects_output_inside_prepared_before_runtime_or_mkdir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); prepared = root/'prepared'; prepared.mkdir()
            target = prepared/'encoded'; factory = Mock(side_effect=AssertionError('model must not load'))
            config = dict(synthetic_only=True, runtime_root='not-a-real-model', normalizer=str(root/'norm.npz'))
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_PROTECTED_INPUT'):
                r.encode_selected(prepared, target, config, runtime_factory=factory)
            factory.assert_not_called(); self.assertFalse(target.exists())

    def test_encoder_rejects_output_inside_real_runtime_before_asset_reads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); runtime = root/'sealed_runtime'; runtime.mkdir()
            target = runtime/'new'; config = dict(runtime_root=str(runtime), normalizer=str(root/'norm.npz'))
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_PROTECTED_INPUT'):
                r.encode_selected(root/'prepared', target, config)
            self.assertFalse(target.exists())

    def test_explicit_protected_directories_guard_encode_raw_and_save(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); protected = root/'sealed'; protected.mkdir(); target = protected/'new'
            config = dict(synthetic_only=True, runtime_root='none', normalizer=str(root/'norm.npz'),
                          protected_paths=[str(protected)])
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_PROTECTED_INPUT'):
                r.encode_selected(root/'prepared', target, config, runtime_factory=fake_runtime)
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_PROTECTED_INPUT'):
                r.prepare_raw_capture(dict(config, capture=dict(path=str(root/'missing.pcap'))), target)
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_PROTECTED_INPUT'):
                r.save_prepared(target, {}, protected_paths=[protected])
            self.assertFalse(target.exists())

    def test_normalizer_protection_is_file_only_and_resolves_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); norm = root/'normalizer.npz'
            self.assertEqual(r._safe_output(root/'sibling', protected_files=[norm]), (root/'sibling').resolve())
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_OVERLAPS_PROTECTED_FILE'):
                r._safe_output(norm, protected_files=[norm])
            protected = root/'sealed'
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_PROTECTED_INPUT'):
                r._safe_output(root/'other'/'..'/'sealed'/'new', protected_paths=[protected])

    def test_raw_adapter_pins_and_drains_decoder_but_future_never_enters_bank(self):
        consumed = []
        packets = [stream_packet(1, 0), stream_packet(2, 100), stream_packet(3, 7201),
                   dict(frame='intentionally irrelevant future header')]
        @contextlib.contextmanager
        def decoder(path, spec, api, progress, log, tshark):
            def values():
                for i, packet_row in enumerate(packets):
                    consumed.append(i); yield packet_row
            yield values()
        class Progress:
            def __init__(self, path, limits): self.stage=''; self.events=[]
            def tick(self, *args): pass
            def stop(self, status, **kwargs): self.events.append(status)
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td)/'fake.pcap'; raw.write_bytes(b'generated test placeholder, never decoded')
            config = dict(synthetic_only=True, capture=dict(SPEC, path=str(raw), sha256=r.sha(raw), expected_packets=4),
                          device_registry=REGISTRY)
            result = r.prepare_raw_capture(config, Path(td)/'out', decoder_factory=decoder,
                         progress_factory=Progress, decoder_identity=DECODER)
            self.assertEqual(consumed, [0, 1, 2, 3])
            self.assertEqual(r._rows(result/'B0/references.jsonl.gz')[0]['frame'], 2)
            self.assertEqual(r._rows(result/'B2/references.jsonl.gz')[0]['frame'], 2)
            config['synthetic_only'] = False
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_ADAPTER'):
                r.prepare_raw_capture(config, Path(td)/'rejected', decoder_factory=decoder)

    def test_encoder_actual_q_snapshot_join_shape_batch_and_generated_receipt(self):
        packets = [stream_packet(1, 0), stream_packet(2, 100, port=5678),
                   stream_packet(3, 200, port=7890, proto=17), stream_packet(4, 7201)]
        prepared = r.prepare_decoded_capture(packets, SPEC, REGISTRY, t0=0., decoder_identity=DECODER)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); r.save_prepared(root/'prepared', prepared)
            norm = root/'RECENT.npz'; np.savez(norm, mean=np.zeros(768), scale=np.ones(768))
            config = dict(synthetic_only=True, runtime_root='not-a-real-model', normalizer=str(norm),
                          normalizer_sha256=r.sha(norm), prepared_receipt_sha256=r.sha(root/'prepared/B0/receipt.json'))
            r.encode_selected(root/'prepared/B0', root/'encoded', config, runtime_factory=fake_runtime)
            with np.load(root/'encoded/bank.npz', allow_pickle=False) as bank:
                self.assertEqual(bank['e3'].shape, (3, 768))
                self.assertEqual(bank['e3'].dtype, np.float32)
                self.assertEqual(bank['q14'].shape, (3, 14))
                self.assertEqual(bank['uid'].tolist(), [x['uid'] for x in r._rows(root/'encoded/references.jsonl.gz')])
            receipt = json.loads((root/'encoded/receipt.json').read_text())
            self.assertEqual(receipt['status'], 'SYNTHETIC_COMPLETE')
            self.assertEqual(receipt['batches'], 2)
            self.assertEqual(len(r._rows(root/'encoded/tensor_receipts.jsonl.gz')), 3)
            env = json.loads((root/'encoded/environment.json').read_text())
            self.assertIn('torch_cpu_capability', env)
            config['synthetic_only'] = False
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_ENCODER'):
                r.encode_selected(root/'prepared/B0', root/'rejected', config, runtime_factory=fake_runtime)


if __name__ == '__main__':
    unittest.main()
