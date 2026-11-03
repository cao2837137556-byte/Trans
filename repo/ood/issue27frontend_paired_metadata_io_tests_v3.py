"""Generated files/processes only: Windows rename sharing regression."""
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import issue27frontend_paired_metadata_io_fix_v3 as io
import issue27frontend_paired_metadata_control_v3 as c
import issue27frontend_paired_metadata_runner_v3 as r
import issue27frontend_paired_metadata_runner_v1 as original_runner
import issue27frontend_paired_metadata_monitor_tests_v2 as prior


class ControllerV3Tests(prior.ControllerV2Tests):
    @classmethod
    def setUpClass(cls):
        cls.old_controller = prior.c
        prior.c = c
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        prior.c = cls.old_controller


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'progress.json'
        self.path.write_text('{"old":true}', encoding='utf-8')

    def error(self, code):
        exc = PermissionError('generated sharing denial')
        exc.winerror = code
        return exc

    def test_old_writer_reproduces_windows_sharing_failure(self):
        with self.path.open('rb'):
            with self.assertRaises(PermissionError): io.original.atomic_json(self.path, {'new': True})
        self.assertEqual(json.loads(self.path.read_text()), {'old': True})

    def test_actual_transient_reader_lock_recovers(self):
        handle = self.path.open('rb')
        timer = threading.Timer(.1, handle.close)
        timer.start()
        try:
            io.atomic_json(self.path, {'new': True})
        finally:
            timer.join(); handle.close()
        self.assertEqual(json.loads(self.path.read_text()), {'new': True})
        self.assertFalse(self.path.with_suffix('.json.tmp').exists())

    def test_persistent_lock_fails_and_preserves_old_receipt(self):
        with self.path.open('rb'), patch.object(io.time, 'sleep') as sleep:
            with self.assertRaises(PermissionError): io.atomic_json(self.path, {'new': True})
        self.assertEqual(sleep.call_count, 20)
        self.assertEqual(json.loads(self.path.read_text()), {'old': True})

    def test_permission_error_codes_bounded(self):
        for code in (5, 32, 33):
            with self.subTest(code=code), patch.object(io.os, 'replace', side_effect=self.error(code)) as replace, patch.object(io.time, 'sleep') as sleep:
                with self.assertRaises(PermissionError): io.atomic_json(self.path, {})
                self.assertEqual(replace.call_count, 21)
                self.assertEqual(sleep.call_count, 20)
                self.assertAlmostEqual(sum(call.args[0] for call in sleep.call_args_list), .5)

    def test_unrelated_permission_not_retried(self):
        with patch.object(io.os, 'replace', side_effect=self.error(999)) as replace, patch.object(io.time, 'sleep') as sleep:
            with self.assertRaises(PermissionError): io.atomic_json(self.path, {})
            self.assertEqual(replace.call_count, 1); sleep.assert_not_called()

    def test_missing_source_not_retried(self):
        with patch.object(io.os, 'replace', side_effect=FileNotFoundError('generated')) as replace, patch.object(io.time, 'sleep') as sleep:
            with self.assertRaises(FileNotFoundError): io.atomic_json(self.path, {})
            self.assertEqual(replace.call_count, 1); sleep.assert_not_called()

    def test_write_error_not_retried(self):
        with patch.object(io.os, 'fsync', side_effect=OSError('generated disk failure')), patch.object(io.os, 'replace') as replace:
            with self.assertRaises(OSError): io.atomic_json(self.path, {})
            replace.assert_not_called()

    def test_multiple_denials_then_success_writes_once(self):
        real_replace = os.replace
        count = []
        def replace(*args):
            count.append(1)
            if len(count) < 3: raise self.error(32)
            return real_replace(*args)
        with patch.object(io.os, 'replace', side_effect=replace), patch.object(io.os, 'fsync', wraps=io.os.fsync) as fsync:
            io.atomic_json(self.path, {'text': 'generated', 'n': 3})
            self.assertEqual(fsync.call_count, 1)
        self.assertEqual(len(count), 3)
        self.assertEqual(self.path.read_bytes(), io.original.canonical({'text': 'generated', 'n': 3}) + b'\n')

    def test_runner_and_controller_use_writer_without_mutating_v1(self):
        self.assertIs(c.s.atomic_json, io.atomic_json)
        self.assertIs(r.s.atomic_json, io.atomic_json)
        self.assertIsNot(original_runner.s.atomic_json, io.atomic_json)
        self.assertTrue(c.s.REAL.endswith('_v3_20260909'))
        self.assertTrue(original_runner.s.REAL.endswith('_v1_20260909'))
        self.assertEqual(c.s.CAPS, original_runner.s.CAPS)

    def test_runner_progress_uses_recovered_writer(self):
        import time
        handle = self.path.open('rb')
        timer = threading.Timer(.1, handle.close); timer.start()
        try:
            progress = r.Progress(self.path.parent, c.s.CAPS, time.monotonic())
            progress.check(True)
        finally:
            timer.join(); handle.close()
        self.assertEqual(json.loads(self.path.read_text())['status'], 'PREPARING')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'tests_run': result.testsRun, 'tests_passed': result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
              'errors': len(result.errors), 'failures': len(result.failures), 'skipped': len(result.skipped),
              'real_packets_decoded': 0, 'model_calls': 0,
              'scope': 'V3 Windows file sharing tests and V2 controller tests rebound to V3; generated only'}
    print('SYNTHETIC_RESULT ' + json.dumps(report), flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
