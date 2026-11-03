"""Generated-only oracle checks for bounded storage; never decode or run E3."""
from collections import deque
from contextlib import ExitStack
import copy
import gzip
import pickle
from pathlib import Path
import random
import sqlite3
import struct
import tempfile
import unittest

import numpy as np
import continuous_audit_v3 as original_audit
import continuous_audit_engineering_v1 as revised_audit
import continuous_input_v3 as original_input
import continuous_input_engineering_v1 as revised_input
from feature_batches_engineering_v1 import assign_batches
import legacy_reference_sample_prepare_v1 as prep
from spill_mapping_v1 import SpillMap, object_codec
from test_continuous_repair_v3 import packet

NS = original_input.NS
POLICY = dict(resident_contexts=1, resident_legacy_prefixes=1,
              resident_candidate_snapshots=1)


def generated(frame, ns, flow=0, incoming=False, proto=6, owner='aa'):
    row = packet(frame, ns, incoming=incoming, proto=proto,
                 flags=16 if incoming else 2, seq=100+frame)
    row['eth.dst' if incoming else 'eth.src'] = owner
    prefix = 'tcp' if proto == 6 else 'udp'
    row[prefix+'.srcport'] = '80' if incoming else str(1234+flow)
    row[prefix+'.dstport'] = str(1234+flow) if incoming else '80'
    if proto == 17:
        row['tcp.srcport'] = row['tcp.dstport'] = ''
    return row


def exact_values(value):
    # Pickle memo IDs can differ after a round trip due to string interning.
    # Compare every stored value, including float bits, rather than pickle bytes.
    if isinstance(value, float): return ('float64', struct.pack('!d', value))
    if isinstance(value, dict): return {key: exact_values(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return tuple(exact_values(item) for item in value)
    return value


def anomaly_rows():
    rows = [generated(1, 0), generated(2, 100*NS, 1),
            generated(3, NS), generated(4, 2*NS, 2),
            generated(5, 2*NS, incoming=True), generated(6, NS, 2),
            generated(7, 101*NS, 1), generated(8, 1000*NS, 2),
            generated(9, 3*NS, 3), generated(10, 4*NS, 4, proto=17),
            generated(11, 63*NS, 3), generated(12, 5*NS, 4, True, 17),
            generated(13, 123*NS+1, 3), generated(14, 120*NS, owner='cc'),
            generated(15, 62*NS), generated(16, 122*NS+1),
            generated(17, 6*NS, 4, proto=17), generated(18, 6*NS+1, 4, True, 17)]
    rows[8]['tcp.flags'] = ''
    rows[13]['tcp.flags'] = ''
    rows[16]['frame.cap_len'] = '54'
    return rows


def target(row, api):
    ct = original_input.Contexts('generated', {'aa'}, api[0])
    ct.frame = int(row['frame.number'])-1
    owner, namespace, event = ct.append(row)
    return dict(uid=prep.digest(['fixture', ct.frame, owner]),
                source_sha256='fixture', capture_id='generated', owner=owner,
                session_id=prep.digest(namespace), timestamp=event.timestamp,
                protocol=event.ip_proto, frame=ct.frame, reference_end=-1., use='QUERY')


class SpillStorage(unittest.TestCase):
    def test_mutable_state_survives_repeated_eviction_and_restore(self):
        with tempfile.TemporaryDirectory() as td, ExitStack() as stack:
            store = SpillMap(Path(td)/'states.sqlite', 1)
            stack.callback(store.close)
            expected = {}
            for cycle in range(20):
                for key in ('x', ('aa', 17), 41):
                    value = store.setdefault(key, dict(queue=deque(maxlen=7), weights=[0., -0.]))
                    oracle = expected.setdefault(key, dict(queue=deque(maxlen=7), weights=[0., -0.]))
                    for item in (value, oracle):
                        item['queue'].append(cycle)
                        item['weights'][0] += 0.1
                    self.assertEqual(pickle.dumps(value, 5), pickle.dumps(oracle, 5))
            self.assertEqual(list(store), list(expected))
            for key, value in expected.items():
                self.assertEqual(pickle.dumps(store[key], 5), pickle.dumps(value, 5))
            self.assertEqual(store.stats['peak_resident'], 1)
            self.assertGreater(store.stats['spills'], 40)
            self.assertGreater(store.stats['loads'], 40)
            del store['x']
            store['x'] = {'replacement': True}
            self.assertEqual(list(store), [('aa', 17), 41, 'x'])
            store[41] = {'replaced_while_spilled': True}
            self.assertEqual(store[41], {'replaced_while_spilled': True})

    def test_dynamic_legacy_slots_preserve_float_and_prefix_bytes(self):
        api = prep.old.legacy_runtime()
        factory = api[1].BoundedNetfoundPrefix
        encode, decode = object_codec(factory)
        self.assertTrue(hasattr(factory, '__slots__'))
        with tempfile.TemporaryDirectory() as td, ExitStack() as stack:
            store = SpillMap(Path(td)/'prefixes.sqlite', 1, encode=encode, decode=decode)
            stack.callback(store.close)
            expected = {key: factory() for key in range(3)}
            for frame in range(1, 101):
                key = frame % 3
                row = generated(frame, frame*11_000_001, key, bool(frame % 2))
                timestamp = float(row['frame.time_epoch'])
                expected[key].append(row, timestamp)
                store.setdefault(key, factory()).append(row, timestamp)
                self.assertEqual(exact_values(pickle.loads(encode(store[key]))),
                                 exact_values(pickle.loads(encode(expected[key]))))
            for key in expected:
                self.assertEqual(exact_values(pickle.loads(encode(store[key]))),
                                 exact_values(pickle.loads(encode(expected[key]))))
            self.assertGreater(store.stats['loads'], 90)

    def test_close_is_idempotent_releases_database_and_rejects_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'states.sqlite'
            store = SpillMap(path, 1)
            store['a'] = [1]
            store['b'] = [2]
            store.close(); store.close()
            self.assertTrue(store.closed)
            self.assertFalse(store.cache)
            with self.assertRaisesRegex(RuntimeError, 'CLOSED'):
                store.get('a')
            with self.assertRaises(sqlite3.ProgrammingError):
                store.db.execute('SELECT 1')
            with self.assertRaises(FileExistsError):
                SpillMap(path, 1)
            path.unlink()  # Also catches a live SQLite handle on Windows.

    def test_serialization_failure_can_be_closed_without_lock_leak(self):
        def fail(value):
            raise ValueError('GENERATED_SERIALIZATION_FAILURE')
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'states.sqlite'
            store = SpillMap(path, 1, encode=fail)
            try:
                store['a'] = [1]
                with self.assertRaisesRegex(ValueError, 'GENERATED_SERIALIZATION_FAILURE'):
                    store['b'] = [2]
            finally:
                store.close()
            path.unlink()


class ContextOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = prep.old.legacy_runtime()

    def assert_context_equal(self, old, new):
        for name in ('reasons', 'retired', 'last_seen', 'poisoned', 'tainted',
                     'events', 'query_allowed', 'query_reason', 'frame_required_owner',
                     'frame', 'previous_ns'):
            self.assertEqual(getattr(old, name), getattr(new, name), name)
        self.assertEqual(list(old.states), list(new.states))
        for namespace, old_state in old.states.items():
            new_state = new.states[namespace]
            a, b = old_state.snapshot(), new_state.snapshot()
            self.assertEqual(a, b)
            for dtype in (np.float64, np.float32):
                self.assertEqual(np.asarray(a[1], dtype=dtype).tobytes(),
                                 np.asarray(b[1], dtype=dtype).tobytes())
            self.assertEqual(np.asarray(old_state.values).tobytes(),
                             np.asarray(new_state.values).tobytes())

    def run_oracle(self, rows):
        with tempfile.TemporaryDirectory() as td:
            old = original_input.Contexts('generated', {'aa', 'cc'}, self.api[0], required_owners={'aa'})
            new = revised_input.Contexts('generated', {'aa', 'cc'}, self.api[0], required_owners={'aa'},
                                         storage_path=Path(td)/'states.sqlite', resident_contexts=1)
            try:
                for row in rows:
                    self.assertEqual(old.append(copy.deepcopy(row)), new.append(copy.deepcopy(row)))
                    self.assert_context_equal(old, new)
                return old, dict(new.states.stats)
            finally:
                new.close()

    def test_cross_connection_time_regression_never_globally_expires_state(self):
        rows = [generated(1, 0), generated(2, 10000*NS, 1),
                generated(3, 10*NS, incoming=True)]
        old, stats = self.run_oracle(rows)
        first = next(iter(old.states.values()))
        self.assertEqual(first.episode_first_frame, 1)
        self.assertEqual(first.snapshot()[2]['bursts'][0]['frames'], [1])
        self.assertEqual(old.reasons['CAPTURE_REGRESSION_CROSS_KEY'], 1)
        self.assertGreater(stats['spills'], 2)

    def test_poison_taint_true_idle_reset_and_owner_isolation_match_per_frame(self):
        old, stats = self.run_oracle(anomaly_rows())
        self.assertEqual(old.reasons['NEW_TIMESTAMP_REGRESSION'], 1)
        self.assertEqual(old.reasons['POISONED_PREFIX'], 1)
        self.assertEqual(old.reasons['MISSING_REQUIRED_HEADERS'], 1)
        self.assertEqual(old.reasons['MISSING_HEADER_TAINT_RESET'], 1)
        self.assertEqual(old.reasons['OUTSIDE_REQUIRED_OWNER'], 1)
        self.assertEqual(old.reasons['PAYLOAD_TRUNCATED_HEADERS_COMPLETE'], 1)
        self.assertFalse(old.tainted)
        self.assertTrue(all(namespace[0] == 'aa' for namespace in old.last_seen))
        udp_state = next(state for state in old.states.values() if state.protocol == 17)
        self.assertIn(17, [frame for burst in udp_state.snapshot()[2]['bursts'] for frame in burst['frames']])
        self.assertGreater(stats['loads'], 10)

    def test_long_bidirectional_tcp_udp_stream_float_bytes_and_bursts(self):
        rows = [generated(i, i*11_000_001, i % 5, bool((i//5) % 2),
                          6 if i % 2 else 17) for i in range(1, 301)]
        old, stats = self.run_oracle(rows)
        self.assertEqual(len(old.states), 10)
        self.assertEqual(stats['peak_resident'], 1)
        self.assertGreater(stats['spills'], 100)

    def test_namespace_failure_stops_before_new_state_and_closes(self):
        row = generated(1, 0); row['tcp.srcport'] = ''
        with tempfile.TemporaryDirectory() as td:
            old = original_input.Contexts('generated', {'aa'}, self.api[0])
            new = revised_input.Contexts('generated', {'aa'}, self.api[0],
                storage_path=Path(td)/'states.sqlite', resident_contexts=1)
            try:
                for context in (old, new):
                    with self.assertRaisesRegex(RuntimeError, 'MISSING_NAMESPACE_HEADERS'):
                        context.append(row)
                self.assert_context_equal(old, new)
                self.assertFalse(new.last_seen)
            finally:
                new.close()
            self.assertTrue(new.states.closed)


class AuditOracle(unittest.TestCase):
    def test_receipt_anomaly_stream_target_identity_and_cleanup_match(self):
        api = prep.old.legacy_runtime(); rows = anomaly_rows()
        targets = {i: ('LEARN', j, target(rows[i-1], api))
                   for j, i in enumerate((1, 5, 13, 16))}
        spec = dict(capture_id='generated', sha256='fixture', expected_packets=len(rows))
        with tempfile.TemporaryDirectory() as td:
            dirs = [Path(td)/name for name in ('old', 'new')]
            for path in dirs: path.mkdir()
            old = original_audit.CaptureAudit(spec, {'aa', 'cc'}, api, targets, dirs[0])
            new = revised_audit.CaptureAudit(spec, {'aa', 'cc'}, api, targets, dirs[1], storage_policy=POLICY)
            stores = (new.contexts.states, new.legacy.states)
            try:
                for row in rows:
                    self.assertEqual(old.append(copy.deepcopy(row)), new.append(copy.deepcopy(row)))
                    self.assertEqual(old.contexts.events, new.contexts.events)
                    self.assertEqual(old.legacy.reasons, new.legacy.reasons)
                self.assertEqual(old.finish(), new.finish())
                self.assertGreater(stores[0].stats['spills'], 1)
                self.assertGreater(stores[1].stats['spills'], 1)
            finally:
                old.close(); new.close()
            new.close()
            with gzip.open(dirs[0]/'generated.anomalies.jsonl.gz', 'rb') as a:
                with gzip.open(dirs[1]/'generated.anomalies.jsonl.gz', 'rb') as b:
                    self.assertEqual(a.read(), b.read())
            self.assertTrue(all(store.closed for store in stores))
            self.assertFalse(new.cache_directory.exists())
            self.assertTrue((dirs[1]/'generated.storage.json').is_file())

    def test_failed_target_keeps_same_failure_evidence_and_releases_stores(self):
        api = prep.old.legacy_runtime(); row = generated(1, 0)
        targets = {1: ('LEARN', 0, target(row, api))}
        row['tcp.srcport'] = ''
        spec = dict(capture_id='generated', sha256='fixture', expected_packets=1)
        with tempfile.TemporaryDirectory() as td:
            receipts = []
            for name, cls in [('old', original_audit.CaptureAudit), ('new', revised_audit.CaptureAudit)]:
                directory = Path(td)/name; directory.mkdir()
                kwargs = dict(storage_policy=POLICY) if name == 'new' else {}
                audit = cls(spec, {'aa'}, api, targets, directory, **kwargs)
                try:
                    with self.assertRaisesRegex(RuntimeError, 'MISSING_NAMESPACE_HEADERS'):
                        audit.append(row)
                finally:
                    audit.close()
                with gzip.open(directory/'generated.anomalies.jsonl.gz', 'rb') as stream:
                    receipts.append(stream.read())
                if name == 'new':
                    self.assertTrue(audit.contexts.states.closed)
                    self.assertTrue(audit.legacy.states.closed)
                    self.assertFalse(audit.cache_directory.exists())
            self.assertEqual(*receipts)


class BatchAssignmentOracle(unittest.TestCase):
    @staticmethod
    def original_assign(db):
        # Literal assignment loop from continuous_features_v3.spool (oracle).
        db.execute('CREATE INDEX shape_uid ON snapshots(protocol,width,bursts,uid)')
        batch_id = 0; previous = None; offset = 0; updates = []
        for uid, proto, width, bursts in db.execute('SELECT uid,protocol,width,bursts FROM snapshots ORDER BY protocol,width,bursts,uid').fetchall():
            key = (proto, width, bursts)
            if key != previous or offset == 16:
                batch_id += 1; offset = 0; previous = key
            updates.append((batch_id-1, uid)); offset += 1
            if len(updates) == 4096:
                db.executemany('UPDATE snapshots SET batch_id=? WHERE uid=?', updates); updates = []
        if updates: db.executemany('UPDATE snapshots SET batch_id=? WHERE uid=?', updates)
        db.execute('CREATE INDEX batch_uid ON snapshots(batch_id,uid)'); db.commit()
        return batch_id

    def check_rows(self, count, chunk):
        rows = [('uid-%08d' % i, 6 if i % 2 else 17, 13+6*(i % 5), 1+i % 7)
                for i in range(count)]
        random.Random(817).shuffle(rows)
        databases = [sqlite3.connect(':memory:') for _ in range(2)]
        try:
            for db in databases:
                db.execute('CREATE TABLE snapshots(uid TEXT PRIMARY KEY, protocol INTEGER, width INTEGER, bursts INTEGER, batch_id INTEGER)')
                db.executemany('INSERT INTO snapshots VALUES(?,?,?,?,NULL)', rows)
            expected_batches = self.original_assign(databases[0])
            report = assign_batches(databases[1], update_chunk=chunk)
            self.assertEqual(report['rows'], count)
            self.assertEqual(report['batches'], expected_batches)
            self.assertEqual(report['model_batch_size'], 16)
            self.assertLessEqual(report['peak_update_rows'], chunk)
            mapping = 'SELECT uid,protocol,width,bursts,batch_id FROM snapshots ORDER BY uid'
            self.assertEqual(databases[0].execute(mapping).fetchall(), databases[1].execute(mapping).fetchall())
            for (size,) in databases[1].execute('SELECT COUNT(*) FROM snapshots GROUP BY batch_id'):
                self.assertLessEqual(size, 16)
        finally:
            for db in databases: db.close()

    def test_multiple_shapes_shuffled_uids_across_4096_row_updates(self):
        self.check_rows(10003, 4096)

    def test_empty_and_small_update_chunks_do_not_change_model_batch(self):
        for count, chunk in ((0, 4096), (1, 1), (35, 3), (1001, 7)):
            with self.subTest(count=count, chunk=chunk): self.check_rows(count, chunk)

    def test_rejects_batch_changes_and_invalid_chunk_before_mutation(self):
        db = sqlite3.connect(':memory:')
        try:
            for kwargs in (dict(batch_size=8), dict(batch_size=32), dict(update_chunk=0), dict(update_chunk=True)):
                with self.assertRaisesRegex(ValueError, 'FIXED_MODEL_BATCH_REQUIRED'):
                    assign_batches(db, **kwargs)
            self.assertFalse(db.execute('SELECT name FROM sqlite_master').fetchall())
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
