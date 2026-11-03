"""Fault and contract checks using a tiny stand-in for the frozen adapter."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

import replay_io


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='edge-replay-test-',
                                                    dir=str(Path(__file__).resolve().parent))
        self.root = Path(self.temporary.name)
        (self.root/'raw').write_bytes(b'raw-pinned')
        self.value = dict(raw_inputs={'HTTP': dict(path=str(self.root/'raw'),
            bytes=10, sha256=hashlib.sha256(b'raw-pinned').hexdigest(), records=3)})
        self.edge = SimpleNamespace(TSHARK='fake-decoder', OWNER='owner', calls=0,
                                    finished=0, value=self.value, fail_final=False,
                                    context_paths=[])
        self.edge.card = lambda: self.value
        self.edge.segments = lambda role, value: [dict(first_frame=1, last_frame=3,
                                                     capture_id='HTTP')]
        def decode_rows(*args, **kwargs):
            for frame in (1, 2, 3):
                yield {'frame.number': str(frame)}
        self.edge.decode_rows = decode_rows
        class Context:
            def __init__(ctx, capture, path):
                ctx.capture = capture
                ctx.states = SimpleNamespace(path=Path(path), stats={'spills': 0})
                Path(path).touch(exist_ok=False)
            def append(ctx, packet):
                return None
            def close(ctx):
                pass
        def numerical_context(capture, api, working, first_frame=1, max_states=4_000_000):
            self.edge.context_paths.append(Path(working))
            return Context(capture, working)
        self.edge.numerical_context = numerical_context
        def selected_snapshots(role, frames, working_directory, **kwargs):
            self.edge.calls += 1
            ctx = self.edge.numerical_context('HTTP', None, self.root/'wrong.sqlite')
            try:
                for packet in self.edge.decode_rows(None):
                    ctx.append(packet)
                    frame = int(packet['frame.number'])
                    if frame in frames:
                        yield dict(uid=str(frame), row={'frame': frame},
                                   body={'tuple': (1, [2, 3.0]), 'bool': True},
                                   q14=[0.0], info={'key': ('x', 1)})
                if self.edge.fail_final:
                    raise RuntimeError('FINAL_RAW_CHECK_FAILED')
                self.edge.finished += 1
            finally:
                ctx.close()
        self.edge.selected_snapshots = selected_snapshots
        self.original = {n: getattr(self.edge, n) for n in
                         ('numerical_context', 'decode_rows', 'selected_snapshots')}

    def tearDown(self):
        self.temporary.cleanup()

    def install(self, **kwargs):
        return replay_io.install(self.edge, output=self.root/'output',
            cache_root=self.root/'cache', scratch_root=self.root,
            deadline=kwargs.pop('deadline', time.monotonic()+30),
            guard=kwargs.pop('guard', lambda: None), **kwargs)

    def run_role(self, frames=(1, 3)):
        return list(self.edge.selected_snapshots('HTTP', frames, self.root/'work'))

    def test_completed_cache_and_exact_types(self):
        with self.install() as repair:
            first = self.run_role()
            self.assertEqual(self.edge.finished, 1)
            second = self.run_role()
            self.assertEqual(first, second)
            self.assertIs(type(second[0]['body']['tuple']), tuple)
            self.assertIs(type(second[0]['info']['key']), tuple)
            self.assertEqual(self.edge.calls, 1)
            self.assertTrue(self.edge.context_paths)
            self.assertTrue(all(repair.scratch in path.parents for path in self.edge.context_paths))
        self.assertFalse((self.root/'wrong.sqlite').exists())
        self.assertFalse(repair.scratch.exists())

    def test_timeout_persists_stop_before_raise(self):
        checks = [0]
        def guard():
            checks[0] += 1
            if checks[0] == 7:
                raise TimeoutError('INJECTED_PACKET_TIMEOUT')
        with self.install(guard=guard):
            with self.assertRaises(TimeoutError):
                self.run_role()
            stop = json.loads((self.root/'output/REPLAY_STOP.json').read_text())
            self.assertEqual(stop['stage'], 'STOP')
            self.assertFalse(stop['partial_role_reusable'])
            self.assertTrue(list((self.root/'cache').rglob('STOP.json')))
        self.assertFalse(list((self.root/'cache').rglob('COMPLETE.json')))

    def test_actual_deadline_writes_stop(self):
        with self.install(deadline=time.monotonic()-1):
            with self.assertRaises(TimeoutError):
                self.run_role()
        self.assertTrue((self.root/'output/REPLAY_STOP.json').exists())

    def test_deadline_expiring_after_first_snapshot_stops_prefix(self):
        control = [None]
        def guard():
            repair = control[0]
            if repair is not None and repair.active and repair.active['selected_persisted']:
                repair.deadline = time.monotonic()-1
        with self.install(guard=guard) as repair:
            control[0] = repair
            with self.assertRaisesRegex(TimeoutError, 'EDGE_REPLAY_DEADLINE'):
                self.run_role()
            stop = json.loads((self.root/'output/REPLAY_STOP.json').read_text())
            self.assertEqual(stop['selected_persisted'], 1)
        self.assertFalse(list((self.root/'cache').rglob('COMPLETE.json')))

    def test_partial_cache_never_reused(self):
        with self.install():
            generator = self.edge.selected_snapshots('HTTP', [1, 3], self.root/'work')
            next(generator)
            generator.close()
            self.assertFalse(list((self.root/'cache').rglob('COMPLETE.json')))
            self.assertEqual(len(self.run_role()), 2)
            self.assertEqual(self.edge.calls, 2)
        self.assertTrue(list((self.root/'cache').rglob('INCOMPLETE.json')))

    def test_failed_final_check_never_marks_complete(self):
        self.edge.fail_final = True
        with self.install():
            with self.assertRaisesRegex(RuntimeError, 'FINAL_RAW_CHECK_FAILED'):
                self.run_role()
        self.assertFalse(list((self.root/'cache').rglob('COMPLETE.json')))
        self.assertTrue(list((self.root/'cache').rglob('PARTIAL.json')))

    def test_tampered_snapshot_rejected(self):
        with self.install():
            self.run_role()
            path = next((self.root/'cache').rglob('1.pickle'))
            path.write_bytes(path.read_bytes()+b'TAMPER')
            with self.assertRaisesRegex(RuntimeError, 'SIZE_OR_SHA_GATE'):
                self.run_role()
        self.assertEqual(self.edge.calls, 1)

    def test_different_frames_and_card_do_not_reuse(self):
        with self.install():
            self.run_role()
            self.run_role((1, 2))
            self.value['new_contract'] = 'different'
            self.run_role((1, 2))
        self.assertEqual(self.edge.calls, 3)
        self.assertEqual(len(list((self.root/'cache').rglob('COMPLETE.json'))), 3)

    def test_scope_restored_on_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'failure'):
            with self.install():
                raise RuntimeError('failure')
        for name, original in self.original.items():
            self.assertIs(getattr(self.edge, name), original)

    def test_unpickler_blocks_globals_even_with_valid_sha(self):
        import pickle
        path = self.root/'untrusted.pickle'
        blob = pickle.dumps(Path('not-a-primitive'), protocol=5)
        path.write_bytes(blob)
        entry = dict(bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(), frame=1)
        with self.assertRaisesRegex(RuntimeError, 'GLOBAL_FORBIDDEN'):
            replay_io._load_snapshot(path, entry)


if __name__ == '__main__':
    unittest.main(verbosity=2)
