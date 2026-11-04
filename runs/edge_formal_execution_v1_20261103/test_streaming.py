"""No-model integration tests, including real process termination/restart."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from checkpoint import canonical, sha
from evaluate import ResultStore
from streaming import make_plan, run_encoding
from worker import Guard, merge_selected, run, selection_inputs

HERE = Path(__file__).resolve().parent


def fixture():
    headers, snapshots = [], {}
    for group, count in enumerate((33, 3, 1)):
        shape = ((6, 13, 1), (6, 25, 2), (17, 7, 1))[group]
        for i in range(count):
            uid = 'g%d-%04d' % (group, i)
            row = dict(uid=uid, protocol=shape[0], use='QUERY')
            snapshots[uid] = dict(uid=uid, row=row, q14=[0.]*14, body={})
            headers.append(dict(uid=uid, row=row, shape=list(shape)))
    return headers, snapshots


class FakeBackend:
    """The fixture proves orchestration/recovery, not frozen model parity."""
    def encode(self, snapshots, shape):
        n = len(snapshots)
        values = []
        for snapshot in snapshots:
            value = int(hashlib.sha256(snapshot['uid'].encode()).hexdigest()[:6], 16)
            values.append(np.full(768, value, dtype=np.float32))
        return np.asarray(values), np.zeros((n, 14), dtype=np.float32), dict(
            physical_rows=16 if n == 1 else n,
            inputs=[dict(uid=s['uid'], input_tensor_sha256=hashlib.sha256(s['uid'].encode()).hexdigest())
                    for s in snapshots])


def child(root, fail):
    headers, snapshots = fixture()
    marker = Path(root)/'fail-already-used'
    def hook(name):
        if name == fail and not marker.exists():
            marker.write_text('test-only', encoding='utf-8')
            os._exit(73)
    run_encoding(make_plan(headers), snapshots.__getitem__, FakeBackend,
                 Path(root)/'encoded', dict(test='fixture-v1'), failpoint=hook)


class Integration(unittest.TestCase):
    def test_shape_uid_plan_order_and_singleton(self):
        headers, _ = fixture()
        forward = make_plan(headers)
        self.assertEqual(forward, make_plan(list(reversed(headers))))
        self.assertEqual(sum(len(x['uids']) for x in forward), 37)
        self.assertEqual(sum(x['physical_rows'] for x in forward), 67)
        self.assertTrue(all(x['uids'] == sorted(x['uids']) for x in forward))

    def test_duplicate_and_invalid_shapes_rejected(self):
        headers, _ = fixture()
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            make_plan(headers+[headers[0]])
        headers[0] = dict(headers[0], shape=[6, 99, 1])
        with self.assertRaisesRegex(ValueError, 'SHAPE'):
            make_plan(headers)

    def test_every_commit_crash_stage_recovers_identical_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)/'base'
            subprocess.run([sys.executable, '-B', __file__, '--child', str(base), 'none'], check=True)
            expected = {str(p.relative_to(base/'encoded')): p.read_bytes()
                        for p in (base/'encoded').rglob('*') if p.is_file() and 'pending' not in p.parts}
            for stage in ('after_payload', 'after_manifest', 'after_commit', 'after_ledger'):
                dest = Path(temp)/stage
                result = subprocess.run([sys.executable, '-B', __file__, '--child', str(dest), stage])
                self.assertEqual(result.returncode, 73)
                subprocess.run([sys.executable, '-B', __file__, '--child', str(dest), stage], check=True)
                actual = {str(p.relative_to(dest/'encoded')): p.read_bytes()
                          for p in (dest/'encoded').rglob('*') if p.is_file() and 'pending' not in p.parts}
                self.assertEqual(actual, expected)

    def test_complete_store_never_reloads_encoder_or_snapshots(self):
        headers, snapshots = fixture()
        plan = make_plan(headers)
        with tempfile.TemporaryDirectory() as temp:
            run_encoding(plan, snapshots.__getitem__, FakeBackend, temp, dict(test='reuse'))
            def forbidden(*args):
                self.fail('committed output incorrectly recomputed')
            _, receipt = run_encoding(plan, forbidden, forbidden, temp, dict(test='reuse'))
            self.assertEqual(receipt['reused_rows'], 37)
            self.assertEqual(receipt['new_rows'], 0)

    def test_real_sealed_inputs_metadata_only(self):
        seal, refs, selected = selection_inputs()
        self.assertEqual(len(refs), 4124)
        self.assertEqual({k: len(v) for k, v in selected.items()}, dict(NORMAL=20000, HTTP=20000, UDP=20000))
        self.assertEqual(seal['total_logical_encoding_rows'], 64124)

    def test_metadata_merge_checks_identity_and_protocol_flags(self):
        row = dict(uid='one', frame=3, timestamp_ns=10, protocol=6, capture_id='c',
                   component_id='component', source_role='HTTP', use='QUERY',
                   owner='owner', source_sha256='raw')
        q = [1., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 1.]
        expected = dict(row, tcp_flags=2, weights={'sealed': True})
        actual = merge_selected(dict(uid='one', row=row, q14=q), expected)
        self.assertEqual(actual['row']['weights'], {'sealed': True})
        with self.assertRaisesRegex(ValueError, 'IDENTITY'):
            merge_selected(dict(uid='one', row=row, q14=q), dict(expected, frame=4))
        with self.assertRaisesRegex(ValueError, 'TCP_FLAGS'):
            merge_selected(dict(uid='one', row=row, q14=q), dict(expected, tcp_flags=16))

    def test_result_chunk_resume_and_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ResultStore(temp, dict(identity='test'))
            data = dict(raw_scores=np.zeros((2, 3), dtype=np.float64),
                        support=np.zeros(2, dtype=np.float64),
                        knn_distance=np.asarray([np.nan, .1], dtype=np.float64))
            data.update({name: np.zeros((2, 4), dtype=bool)
                         for name in ('RAW', 'C5_P3', 'C5_P1', 'STANDARD_KNN5')})
            store.commit('q000000', ['a', 'b'], data)
            restored = ResultStore(temp, dict(identity='test')).load('q000000', ['a', 'b'])
            self.assertTrue(np.array_equal(restored['C5_P3'], data['C5_P3']))
            with self.assertRaisesRegex(ValueError, 'ORDER'):
                store.load('q000000', ['b', 'a'])
            payload = Path(temp)/'q000000/RESULT.npz'
            payload.write_bytes(payload.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError, 'SHA_SIZE'):
                store.load('q000000', ['a', 'b'])

    def test_replay_heartbeat_elapsed_does_not_collide(self):
        import time
        class DummyGuard(Guard):
            def __call__(self):
                pass
        with tempfile.TemporaryDirectory() as temp:
            guard = DummyGuard.__new__(DummyGuard)
            guard.out, guard.started = Path(temp), time.monotonic()
            guard.max_rss, guard.formal = 100, False
            guard.progress('RAW_PREFIX_REPLAY', elapsed_seconds=5., frame=4096)
            saved = json.loads((Path(temp)/'PROGRESS.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['replay_elapsed_seconds'], 5.)
            self.assertEqual(saved['frame'], 4096)
            self.assertFalse(saved['formal_evaluation'])

    def test_draft_card_cannot_start_formal_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            card = temp/'DRAFT.json'
            card.write_text(json.dumps(dict(status='DRAFT')), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'ENGINEERING_GATE'):
                run(card, temp/'missing_auth.json', temp/'missing_runtime.json', temp/'outputs')
            self.assertFalse((temp/'outputs').exists())


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--child':
        Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)
        child(sys.argv[2], sys.argv[3])
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Integration)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        receipt = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
            failures=len(result.failures), errors=len(result.errors),
            scope='LOCAL_NO_MODEL_ORCHESTRATION_AND_CHECKPOINT_NOT_LINUX_FROZEN_ENCODER_RECOVERY',
            actual_process_exit_code=73, frozen_model_calls=0, external_quality_computed=False,
            source_sha256={name: sha(HERE/name) for name in
                           ('streaming.py', 'evaluate.py', 'worker.py', 'test_streaming.py')})
        (HERE/'STREAMING_TEST_RECEIPT.json').write_bytes(canonical(receipt))
        raise SystemExit(0 if result.wasSuccessful() else 1)
