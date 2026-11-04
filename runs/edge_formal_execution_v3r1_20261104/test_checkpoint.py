"""No-model crash/restart contracts for the formal Edge batch store."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from checkpoint import BatchStore, RoleSpool, PackedRoleSpool, canonical, sha

IDENTITY = {'selection_seal': 'fixed-seal', 'encoder_code': 'fixed-code',
            'runtime': 'test-no-model', 'role': 'NORMAL'}
PLAN = [('000000', ['u0', 'u1']), ('000001', ['u2', 'u3']), ('000002', ['u4'])]


def arrays(uids):
    seed = np.array([int(hashlib.sha256(uid.encode()).hexdigest()[:4], 16) % 97
                     for uid in uids], dtype=np.float32)
    e3 = np.arange(768, dtype=np.float32)[None, :] + seed[:, None]
    q14 = ((np.arange(14)[None, :] + seed[:, None]) % 2).astype(np.float32)
    return e3, q14


def rows(uids):
    return [{'uid': uid, 'frame': int(uid[1:]) + 1, 'component_id': 'c'+str(i),
             'canonical_key': [6, ['10.0.0.1', 80], ['10.0.0.2', 12345]]}
            for i, uid in enumerate(uids)]


def populate(root):
    store = BatchStore(root, IDENTITY)
    for name, uids in PLAN:
        if not store.has(name, uids):
            store.commit(name, uids, *arrays(uids), rows=rows(uids))
    store.finish(PLAN)
    return store


def crash_child(root, point):
    store = BatchStore(root, IDENTITY)
    name, uids = PLAN[1]

    def failure(current):
        if current == point:
            os._exit(73)

    store.commit(name, uids, *arrays(uids), rows=rows(uids), failpoint=failure)
    raise AssertionError('requested failure point did not execute')


def packed_snapshot(uid):
    index = int(uid[1:])
    return dict(uid=uid, row=dict(uid=uid, frame=index+1, protocol=6,
                                 canonical_key=(6, ('10.0.0.1', 80), ('10.0.0.2', 12345))),
        body=dict(flow=dict(protocol=6, counts=[index % 6+1, 1]),
                  nested=[(1., b'bytes')]), q14=[0.]*14, info={})


def packed_crash_child(root, point):
    def failure(current):
        if current == point:
            os._exit(74)
    spool = PackedRoleSpool(root, IDENTITY, 'NORMAL', ['u'+str(i) for i in range(5)],
                            chunk_rows=2, failpoint=failure)
    for i in range(5):
        spool.append(packed_snapshot('u'+str(i)))
    spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
    raise AssertionError('requested packed failure point did not execute')


class BatchTests(unittest.TestCase):
    def test_arrays_metadata_and_float_bytes_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BatchStore(tmp, IDENTITY)
            uids = ['u0', 'u1']
            e3, q14 = arrays(uids)
            store.commit('000000', uids, e3, q14, rows=rows(uids))
            loaded = store.load('000000', uids)
            self.assertEqual(loaded['e3'].tobytes(), e3.tobytes())
            self.assertEqual(loaded['q14'].tobytes(), q14.tobytes())
            self.assertEqual(loaded['rows'], rows(uids))
            self.assertEqual(loaded['uids'], uids)

    def test_binding_and_batch_bound_cannot_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            BatchStore(tmp, IDENTITY)
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED'):
                BatchStore(tmp, dict(IDENTITY, selection_seal='other'))
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED'):
                BatchStore(tmp, IDENTITY, max_rows=8)
            with self.assertRaisesRegex(ValueError, 'BATCH_ROW_BOUND'):
                BatchStore(Path(tmp)/'bad', IDENTITY, max_rows=17)

    def test_wrong_dtype_shape_nonfinite_or_too_large_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BatchStore(tmp, IDENTITY)
            e3, q14 = arrays(['u0'])
            bads = [(e3.astype(np.float64), q14), (e3[:, :767], q14),
                    (e3, q14[:, :13]), (np.full_like(e3, np.nan), q14)]
            for bad_e3, bad_q14 in bads:
                with self.assertRaisesRegex(ValueError, 'INPUT_ARRAY_SCHEMA'):
                    store.commit('bad', ['u0'], bad_e3, bad_q14)
            uids = ['u'+str(i) for i in range(17)]
            with self.assertRaisesRegex(ValueError, 'BATCH_ROW_BOUND'):
                store.commit('big', uids, *arrays(uids))

    def test_duplicate_uids_and_wrong_order_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BatchStore(tmp, IDENTITY)
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_UID'):
                store.commit('bad', ['u0', 'u0'], *arrays(['u0', 'u0']))
            store.commit('a', ['u0', 'u1'], *arrays(['u0', 'u1']))
            with self.assertRaisesRegex(ValueError, 'CROSS_BATCH_UID_OVERLAP'):
                store.commit('b', ['u1'], *arrays(['u1']))
            with self.assertRaisesRegex(ValueError, 'UID_ORDER_CHANGED'):
                store.has('a', ['u1', 'u0'])

    def test_changed_recomputed_bytes_cannot_overwrite_committed_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BatchStore(tmp, IDENTITY)
            e3, q14 = arrays(['u0'])
            q14[0, 0] = 0.
            store.commit('a', ['u0'], e3, q14)
            previous = sha(Path(tmp)/'batches/a/q14.npy')
            self.assertEqual(store.commit('a', ['u0'], e3, q14)['batch_id'], 'a')
            q14[0, 0] = -0.
            with self.assertRaisesRegex(ValueError, 'RECOMPUTED_BYTES_CHANGED'):
                store.commit('a', ['u0'], e3, q14)
            self.assertEqual(sha(Path(tmp)/'batches/a/q14.npy'), previous)

    def test_same_size_array_tamper_fails_on_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BatchStore(tmp, IDENTITY)
            store.commit('a', ['u0'], *arrays(['u0']))
            path = Path(tmp)/'batches/a/E3.npy'
            data = bytearray(path.read_bytes())
            data[-2] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'FILE_SHA_SIZE:E3.npy'):
                BatchStore(tmp, IDENTITY)

    def test_missing_manifest_not_treated_as_valid_empty_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BatchStore(tmp, IDENTITY)
            store.commit('a', ['u0'], *arrays(['u0']))
            (Path(tmp)/'batches/a/MANIFEST.json').unlink()
            with self.assertRaisesRegex(ValueError, 'JSON_SCOPE_SIZE'):
                BatchStore(tmp, IDENTITY)

    def test_finished_uid_order_is_immutable_and_no_extra_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = populate(tmp)
            with self.assertRaisesRegex(ValueError, 'FINAL_ORDER_CHANGED'):
                store.finish(list(reversed(PLAN)))
            with self.assertRaisesRegex(ValueError, 'ALREADY_FINISHED'):
                store.commit('extra', ['u5'], *arrays(['u5']))
            with self.assertRaisesRegex(ValueError, 'EXACT_COVERAGE'):
                store.finish(PLAN[:2])

    def test_real_process_death_four_commit_phases_matches_uninterrupted_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root/'baseline'
            populate(baseline)
            expected_files = {p.relative_to(baseline).as_posix(): p.read_bytes()
                              for p in baseline.rglob('*') if p.is_file()}
            for point in ('after_payload', 'after_manifest', 'after_commit', 'after_ledger'):
                destination = root/point
                store = BatchStore(destination, IDENTITY)
                name, uids = PLAN[0]
                store.commit(name, uids, *arrays(uids), rows=rows(uids))
                child = subprocess.run([sys.executable, '-X', 'utf8', '-B', __file__,
                                        '--crash-child', str(destination), point],
                                       capture_output=True, text=True, timeout=20)
                self.assertEqual(child.returncode, 73, child.stdout+child.stderr)
                resumed = BatchStore(destination, IDENTITY)
                self.assertTrue(resumed.has(*PLAN[0]))
                self.assertEqual(resumed.has(*PLAN[1]), point in ('after_commit', 'after_ledger'))
                populate(destination)
                for name, expected in expected_files.items():
                    self.assertEqual((destination/name).read_bytes(), expected, (point, name))
                self.assertEqual((destination/'COMPLETE.json').read_bytes(),
                                 (baseline/'COMPLETE.json').read_bytes())


class RoleTests(unittest.TestCase):
    def snapshot(self, uid):
        return dict(uid=uid, row=dict(uid=uid, frame=int(uid[1:])+1),
                    body={'bursts': [(1, [2., b'v'])]}, q14=[0.]*14, info={})

    def test_partial_role_never_exposes_encoding_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            partial = RoleSpool(tmp, IDENTITY, 'NORMAL', ['u0', 'u1'])
            partial.append(self.snapshot('u0'))
            self.assertFalse(partial.is_complete())
            with self.assertRaisesRegex(ValueError, 'INCOMPLETE_CANNOT_ENCODE'):
                list(partial.load_complete())
            restarted = RoleSpool(tmp, IDENTITY, 'NORMAL', ['u0', 'u1'])
            self.assertEqual(restarted.entries, [])
            self.assertFalse(restarted.is_complete())
            for uid in ('u0', 'u1'):
                restarted.append(self.snapshot(uid))
            with self.assertRaisesRegex(ValueError, 'GENERATOR_AND_FINAL_RAW_REQUIRED'):
                restarted.complete(generator_exhausted=True)
            restarted.complete(generator_exhausted=True, raw_final_identity_pass=True)
            saved = list(RoleSpool(tmp, IDENTITY, 'NORMAL', ['u0', 'u1']).load_complete())
            self.assertEqual(saved, [self.snapshot('u0'), self.snapshot('u1')])
            self.assertIs(type(saved[0]['body']['bursts'][0]), tuple)
            self.assertIs(type(saved[0]['body']['bursts'][0][1][1]), bytes)

    def test_completed_role_requires_exact_uid_set_and_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            role = RoleSpool(tmp, IDENTITY, 'HTTP', ['u0', 'u1'])
            role.append(self.snapshot('u0'))
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_UID'):
                role.append(self.snapshot('u0'))
            with self.assertRaisesRegex(ValueError, 'EXACT_UID_COVERAGE'):
                role.complete(generator_exhausted=True, raw_final_identity_pass=True)
            with self.assertRaisesRegex(ValueError, 'SNAPSHOT_UID'):
                role.append(self.snapshot('u2'))

    def test_completed_role_tamper_rejected_before_input_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            role = RoleSpool(tmp, IDENTITY, 'UDP', ['u0'])
            role.append(self.snapshot('u0'))
            record = role.complete(generator_exhausted=True, raw_final_identity_pass=True)
            path = Path(tmp)/record['attempt']/record['entries'][0]['file']
            value = bytearray(path.read_bytes())
            value[-1] ^= 1
            path.write_bytes(value)
            with self.assertRaisesRegex(ValueError, 'SNAPSHOT_SHA_SIZE'):
                list(RoleSpool(tmp, IDENTITY, 'UDP', ['u0']).load_complete())

    def test_role_binding_change_prevents_completed_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            RoleSpool(tmp, IDENTITY, 'HTTP', ['u0'])
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED'):
                RoleSpool(tmp, IDENTITY, 'HTTP', ['u1'])


class PackedRoleTests(unittest.TestCase):
    def test_chunked_headers_and_bodies_restore_without_loading_all_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = ['u'+str(i) for i in range(5)]
            spool = PackedRoleSpool(tmp, IDENTITY, 'NORMAL', expected, chunk_rows=2)
            for uid in expected:
                spool.append(packed_snapshot(uid))
                self.assertLessEqual(len(spool.buffer), 2)
            value = spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
            self.assertEqual([r['rows'] for r in value['chunks']], [2, 2, 1])
            self.assertEqual(len(list(Path(tmp).rglob('snapshots.bin'))), 3)
            reopened = PackedRoleSpool(tmp, IDENTITY, 'NORMAL', expected, chunk_rows=2)
            self.assertEqual([h['uid'] for h in reopened.headers()], expected)
            self.assertEqual([h['shape'] for h in reopened.headers()],
                             [[6, (i % 6+1)*12+1, 2] for i in range(5)])
            self.assertEqual(list(reopened.load_complete()), [packed_snapshot(uid) for uid in expected])
            self.assertEqual(reopened.buffer, [])
            self.assertFalse(any('body' in v for v in reopened._index.values()))

    def test_partial_headers_and_incomplete_coverage_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = PackedRoleSpool(tmp, IDENTITY, 'NORMAL', ['u0', 'u1'], chunk_rows=1)
            spool.append(packed_snapshot('u0'))
            self.assertFalse(spool.is_complete())
            with self.assertRaisesRegex(ValueError, 'INCOMPLETE_CANNOT_ENCODE'):
                list(spool.headers())
            with self.assertRaisesRegex(ValueError, 'EXACT_UID_COVERAGE'):
                spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
            with self.assertRaisesRegex(ValueError, 'COVERAGE_OR_DUPLICATE'):
                spool.append(packed_snapshot('u0'))
            spool.append(packed_snapshot('u1'))
            with self.assertRaisesRegex(ValueError, 'GENERATOR_AND_FINAL_RAW_REQUIRED'):
                spool.complete(generator_exhausted=True)

    def test_tampered_chunk_or_index_is_rejected_on_restart(self):
        for file in ('snapshots.bin', 'INDEX.json'):
            with tempfile.TemporaryDirectory() as tmp:
                spool = PackedRoleSpool(tmp, IDENTITY, 'NORMAL', ['u0'])
                spool.append(packed_snapshot('u0'))
                value = spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
                path = Path(tmp)/value['attempt']/value['chunks'][0]['name']/file
                blob = bytearray(path.read_bytes())
                blob[-2] ^= 1
                path.write_bytes(blob)
                with self.assertRaisesRegex(ValueError, 'CHUNK_SHA_SIZE'):
                    PackedRoleSpool(tmp, IDENTITY, 'NORMAL', ['u0']).is_complete()

    def test_same_instance_load_catches_changed_snapshot_without_rehashing_whole_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = PackedRoleSpool(tmp, IDENTITY, 'NORMAL', ['u0'])
            spool.append(packed_snapshot('u0'))
            value = spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
            path = Path(tmp)/value['attempt']/value['chunks'][0]['name']/'snapshots.bin'
            blob = bytearray(path.read_bytes())
            blob[-2] ^= 1
            path.write_bytes(blob)
            with self.assertRaisesRegex(ValueError, 'SNAPSHOT_SHA_SIZE'):
                spool.load('u0')

    def test_binding_change_and_invalid_shape_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = PackedRoleSpool(tmp, IDENTITY, 'NORMAL', ['u0'])
            bad = packed_snapshot('u0')
            bad['body']['flow']['counts'] = [7]
            with self.assertRaisesRegex(ValueError, 'FLOW_COUNTS'):
                spool.append(bad)
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED'):
                PackedRoleSpool(tmp, dict(IDENTITY, encoder_code='changed'), 'NORMAL', ['u0'])

    def test_actual_process_death_never_makes_partial_role_scientific_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = ['u'+str(i) for i in range(5)]
            for point in ('after_chunk_payload', 'after_chunk_commit', 'before_complete', 'after_complete'):
                root = Path(tmp)/point
                child = subprocess.run([sys.executable, '-X', 'utf8', '-B', __file__,
                                        '--packed-crash-child', str(root), point],
                                       capture_output=True, text=True, timeout=20)
                self.assertEqual(child.returncode, 74, child.stdout+child.stderr)
                spool = PackedRoleSpool(root, IDENTITY, 'NORMAL', expected, chunk_rows=2)
                self.assertEqual(spool.is_complete(), point == 'after_complete')
                if not spool.is_complete():
                    with self.assertRaisesRegex(ValueError, 'INCOMPLETE_CANNOT_ENCODE'):
                        list(spool.load_complete())
                    for uid in expected:
                        spool.append(packed_snapshot(uid))
                    spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
                self.assertEqual(list(spool.load_complete()), [packed_snapshot(uid) for uid in expected])
                for uid in expected:
                    self.assertEqual(spool.load(uid), packed_snapshot(uid))


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--crash-child':
        crash_child(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == '--packed-crash-child':
        packed_crash_child(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
