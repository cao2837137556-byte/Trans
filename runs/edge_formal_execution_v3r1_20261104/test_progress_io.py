import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import progress_io as candidate

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('frozen_replay',
    ROOT/'runs/edge_preflight_io_repair_v1_20261103/replay_io.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class ProgressIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'replay_status').mkdir()
        self.calls = []
        def durable(path, value):
            self.calls.append(Path(path))
            replay._write_json(path, value)
        self.worker = types.SimpleNamespace(atomic_json=durable)

    def tearDown(self):
        self.temp.cleanup()

    def test_bytes_equal_frozen_writer(self):
        value = {'stage': 'RAW_PREFIX_REPLAY', 'frame': 770000,
                 'role': 'UDP', 'detail': ['中文', None, False, 1.25]}
        replay._write_json(self.root/'old.json', value)
        candidate.live_json(self.root/'new.json', value)
        self.assertEqual((self.root/'old.json').read_bytes(),
                         (self.root/'new.json').read_bytes())

    def test_both_live_paths_skip_fsync(self):
        with candidate.install(replay, self.worker, self.root):
            with patch('os.fsync', side_effect=AssertionError('live fsync')):
                replay._write_json(self.root/'replay_status'/'REPLAY_HEARTBEAT.json', {'n': 1})
                self.worker.atomic_json(self.root/'PROGRESS.json', {'n': 2})
        self.assertEqual(self.calls, [])

    def test_authoritative_paths_keep_fsync(self):
        original = replay._write_json
        count = []
        # Separate spy modules avoid recursion in the durable test writer.
        def durable(path, value):
            count.append(Path(path).name)
            original(path, value)
        r = types.SimpleNamespace(_write_json=durable)
        w = types.SimpleNamespace(atomic_json=durable)
        names = ['REPLAY_STOP.json', 'STOP.json', 'COMPLETE.json',
                 'CURRENT_ENGINEERING_ATTEMPT.json', 'CANDIDATE.json',
                 'MANIFEST.json', 'AUTHORIZATION.json', 'REPLAY_COVERAGE.json']
        with candidate.install(r, w, self.root), patch('os.fsync') as sync:
            for name in names:
                r._write_json(self.root/name, {'status': 'evidence'})
                w.atomic_json(self.root/name, {'status': 'evidence'})
        self.assertEqual(sync.call_count, 2*len(names))
        self.assertEqual(len(count), 2*len(names))

    def test_same_basename_other_directory_stays_durable(self):
        other = self.root/'another'; other.mkdir()
        original = replay._write_json
        r = types.SimpleNamespace(_write_json=original)
        w = types.SimpleNamespace(atomic_json=original)
        with candidate.install(r, w, self.root), patch('os.fsync') as sync:
            r._write_json(other/'REPLAY_HEARTBEAT.json', {})
            w.atomic_json(other/'PROGRESS.json', {})
        self.assertEqual(sync.call_count, 2)

    def test_restore_after_exception(self):
        old_r, old_w = replay._write_json, self.worker.atomic_json
        with self.assertRaisesRegex(RuntimeError, 'test'):
            with candidate.install(replay, self.worker, self.root):
                raise RuntimeError('test')
        self.assertIs(replay._write_json, old_r)
        self.assertIs(self.worker.atomic_json, old_w)

    def test_invalid_json_preserves_previous(self):
        path = self.root/'PROGRESS.json'
        candidate.live_json(path, {'frame': 1})
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            candidate.live_json(path, {'bad': float('nan')})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_replace_failure_preserves_previous_and_cleans_owned_temp(self):
        path = self.root/'PROGRESS.json'
        candidate.live_json(path, {'frame': 1})
        with patch.object(candidate.os, 'replace', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                candidate.live_json(path, {'frame': 2})
        self.assertEqual(json.loads(path.read_bytes()), {'frame': 1})
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_replay_status_callback_and_counters_unchanged(self):
        # Exercise the actual frozen status implementation with identical clocks.
        def run(output, optimized):
            output.mkdir(); captured = []
            repair = object.__new__(replay._Repair)
            repair.output = output
            repair.active = dict(role='UDP', frame=123, start=5.,
                append_seconds=2., decoder_next_seconds=.1, selected_persisted=3)
            repair.contexts, repair.closed_contexts = [], []
            repair.start, repair.scratch = 1., Path('/node/local')
            repair.callback = lambda stage, **kw: captured.append((stage, kw))
            if optimized:
                with candidate.install(replay, self.worker, output.parent):
                    with patch.object(replay.time, 'monotonic', return_value=10.):
                        result = repair.status('RAW_PREFIX_REPLAY')
            else:
                with patch.object(replay.time, 'monotonic', return_value=10.):
                    result = repair.status('RAW_PREFIX_REPLAY')
            return result, captured, (output/'REPLAY_HEARTBEAT.json').read_bytes()
        (self.root/'baseline').mkdir(); (self.root/'candidate').mkdir()
        old = run(self.root/'baseline'/'replay_status', False)
        new = run(self.root/'candidate'/'replay_status', True)
        self.assertEqual(old, new)


if __name__ == '__main__':
    unittest.main(verbosity=2)
