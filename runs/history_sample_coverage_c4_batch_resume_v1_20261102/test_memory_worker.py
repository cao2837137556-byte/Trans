"""Worker budget and progress tests; no model, PCAP or external runtime."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import worker_runtime
from worker_runtime import WorkerRuntime


class WorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'workers' / 'member_stage.json'

    def read_status(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def test_only_status_parent_created_and_children_supported(self):
        runtime = WorkerRuntime(self.path, 60, 10)
        child = object()
        runtime.children.append(child)
        self.assertEqual(runtime.children, [child])
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        self.assertEqual(set(self.read_status()),
                         {'phase', 'elapsed_seconds', 'encoded_charged',
                          'work_heartbeat_utc'})

    def test_wall_boundary_and_guard_does_not_fake_heartbeat(self):
        with patch.object(worker_runtime.time, 'monotonic', return_value=100.), \
                patch.object(worker_runtime, 'utc', return_value='work-start'):
            runtime = WorkerRuntime(self.path, 10, 0)
        with patch.object(worker_runtime.time, 'monotonic', return_value=110.), \
                patch.object(worker_runtime, 'utc', return_value='not-work'):
            runtime.guard()
        self.assertEqual(self.read_status()['elapsed_seconds'], 10.)
        self.assertEqual(self.read_status()['work_heartbeat_utc'], 'work-start')
        with patch.object(worker_runtime.time, 'monotonic', return_value=110.001):
            with self.assertRaisesRegex(RuntimeError, 'WALL_SECONDS_LIMIT'):
                runtime.guard()

    def test_charge_boundary_before_forward_and_not_completed(self):
        runtime = WorkerRuntime(self.path, 60, 3)
        initial_heartbeat = self.read_status()['work_heartbeat_utc']
        runtime.encoded(3)
        self.assertEqual(self.read_status()['encoded_charged'], 3)
        self.assertNotIn('completed', self.read_status())
        self.assertEqual(self.read_status()['work_heartbeat_utc'], initial_heartbeat)
        forwarded = []
        with self.assertRaisesRegex(RuntimeError, 'ENCODED_LIMIT'):
            runtime.encoded(1)
            forwarded.append('must not forward')
        self.assertEqual(forwarded, [])
        self.assertEqual(self.read_status()['encoded_charged'], 3)

    def test_reject_invalid_charge_counts_without_corrupting_budget(self):
        runtime = WorkerRuntime(self.path, 60, 3)
        for value in (-1, True, 1.5, '1'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, 'NONNEGATIVE_INTEGER_COUNT'):
                    runtime.encoded(value)
        self.assertEqual(runtime._encoded, 0)

    def test_update_and_tick_report_real_progress_and_stage_reset(self):
        runtime = WorkerRuntime(self.path, 60, 3)
        with patch.object(worker_runtime, 'utc', return_value='actual-work'):
            runtime.update('HISTORY_E3', completed=2, total=3)
        status = self.read_status()
        self.assertEqual(status['completed'], 2)
        self.assertEqual(status['encoded_charged'], 0)
        self.assertEqual(status['work_heartbeat_utc'], 'actual-work')
        runtime.update('NEXT_STAGE')
        self.assertNotIn('completed', self.read_status())
        runtime.tick(done=4, total=5, device='test-device')
        status = self.read_status()
        self.assertEqual((status['done'], status['total'], status['device']),
                         (4, 5, 'test-device'))

    def test_reserved_fields_cannot_forge_budget_or_heartbeat(self):
        runtime = WorkerRuntime(self.path, 60, 3)
        for field in ('phase', 'elapsed_seconds', 'encoded_charged',
                      'work_heartbeat_utc'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError, 'RESERVED_PROGRESS_FIELD'):
                    runtime.update(**{field: 'forged'})
        self.assertEqual(self.read_status()['encoded_charged'], 0)

    def test_display_sharing_failure_nonfatal_but_budget_still_enforced(self):
        runtime = WorkerRuntime(self.path, 60, 1)
        original_status = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('display busy')):
            runtime.encoded(1)
            runtime.update('HISTORY_E3', completed=1, total=1)
            self.assertEqual(self.path.read_bytes(), original_status)
            with self.assertRaisesRegex(RuntimeError, 'ENCODED_LIMIT'):
                runtime.encoded(1)
        runtime.update('FINISHED', completed=1, total=1)
        self.assertEqual(self.read_status()['encoded_charged'], 1)
        self.assertIn('display busy', self.read_status()['display_write_warning'])
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_nonpermission_status_errors_are_not_swallowed(self):
        runtime = WorkerRuntime(self.path, 60, 0)
        with patch.object(Path, 'replace', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                runtime.update('WORK')

    def test_invalid_constructor_limits(self):
        for wall, cap in ((0, 1), (-1, 1), (True, 1), (float('inf'), 1),
                          (float('nan'), 1), (60, -1), (60, True), (60, 1.5)):
            with self.subTest(wall=wall, cap=cap):
                with self.assertRaises(RuntimeError):
                    WorkerRuntime(self.path, wall, cap)
        self.assertFalse(self.path.parent.exists())


if __name__ == '__main__':
    unittest.main()
