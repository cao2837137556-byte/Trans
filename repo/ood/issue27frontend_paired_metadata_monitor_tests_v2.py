"""Generated-only monitor regression. Never invokes the real worker."""
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import issue27frontend_paired_metadata_control_v1 as old
import issue27frontend_paired_metadata_control_v2 as c
import issue27frontend_paired_metadata_monitor_fix_v2 as fix
import issue27frontend_paired_metadata_tests_v1 as prior


class Entry:
    def __init__(self, name, size=0, missing=False, directory=False):
        self.name, self.size, self.missing, self.directory = name, size, missing, directory
        self.calls = 0

    def is_file(self):
        return True

    def stat(self):
        self.calls += 1
        if self.missing:
            raise FileNotFoundError(self.name)
        return SimpleNamespace(st_size=self.size, st_mode=stat.S_IFDIR if self.directory else stat.S_IFREG)


class Folder:
    def __init__(self, *scans):
        self.scans, self.calls = scans, 0

    def iterdir(self):
        index = min(self.calls, len(self.scans) - 1)
        self.calls += 1
        return iter(self.scans[index])


class MonitorTests(unittest.TestCase):
    def test_old_race_reproduced(self):
        with self.assertRaises(FileNotFoundError):
            old.directory_bytes(Folder([Entry('progress.json.tmp', missing=True)]))

    def test_replacement_rescans_complete_directory(self):
        folder = Folder([Entry('a', 8), Entry('progress.json.tmp', missing=True)],
                        [Entry('a', 8), Entry('progress.json', 200)])
        self.assertEqual(fix.directory_bytes(folder), 208)
        self.assertEqual(folder.calls, 2)

    def test_third_snapshot_can_succeed(self):
        missing = [Entry('progress.json.tmp', missing=True)]
        self.assertEqual(fix.directory_bytes(Folder(missing, missing, [Entry('a', 50)])), 50)

    def test_three_unstable_scans_fail_closed(self):
        folder = Folder([Entry('progress.json.tmp', missing=True)])
        with self.assertRaisesRegex(RuntimeError, 'AFTER_3_SCANS'):
            fix.directory_bytes(folder)
        self.assertEqual(folder.calls, 3)

    def test_persistent_disappearance_is_not_ignored(self):
        folder = Folder([Entry('progress.json', missing=True)])
        with self.assertRaises(FileNotFoundError): fix.directory_bytes(folder)
        self.assertEqual(folder.calls, 1)

    def test_one_stat_and_regular_files_only(self):
        entries = [Entry('a', 6), Entry('b.tmp', 10), Entry('dir', 100, directory=True)]
        self.assertEqual(fix.directory_bytes(Folder(entries)), 16)
        self.assertEqual([x.calls for x in entries], [1, 1, 1])

    def test_empty_directory(self):
        self.assertEqual(fix.directory_bytes(Folder([])), 0)

    def test_large_replacement_is_not_undercounted(self):
        self.assertGreater(fix.directory_bytes(Folder([Entry('p.tmp', missing=True)],
                           [Entry('p', 67108865)])), 67108864)

    def test_namespaces_do_not_mutate_v1(self):
        self.assertTrue(old.s.REAL.endswith('_v1_20260909'))
        self.assertTrue(old.s.PACKAGE.endswith('_v1_20260909'))
        self.assertTrue(c.s.REAL.endswith('_v2_20260909'))
        self.assertEqual(c.s.CAPS, old.s.CAPS)
        self.assertIs(c.s.load_inputs, old.s.load_inputs)


class ControllerV2Tests(prior.ControllerTests):
    @classmethod
    def setUpClass(cls):
        cls.saved = prior.c, prior.s
        prior.c, prior.s = c, c.s

    @classmethod
    def tearDownClass(cls):
        prior.c, prior.s = cls.saved

    def test_atomic_writer_under_supervisor(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / 'attempt'
            code = ('import pathlib,time,os; p=pathlib.Path(' + repr(str(folder)) + ');\n'
                    'while not (p/"worker_gate.json").exists(): time.sleep(.01)\n'
                    'for i in range(500):\n'
                    ' (p/"progress.json.tmp").write_text(str(i)); os.replace(p/"progress.json.tmp",p/"progress.json"); time.sleep(.001)\n'
                    '(p/"worker_terminal.json").write_text("{}")')
            out = c.supervise([sys.executable, '-B', '-c', code], folder, self.config(), True,
                              lambda *args: {'status': 'GENERATED_MONITOR_PASS'})
            self.assertEqual(out['status'], 'GENERATED_MONITOR_PASS')
            self.assertTrue(c.status(folder)['seal_verified'])

    def test_snapshot_failure_still_seals_stop(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / 'attempt'
            with patch.object(c, 'directory_bytes', side_effect=RuntimeError('GENERATED_UNSTABLE')):
                out = c.supervise([sys.executable, '-B', '-c', 'import time; time.sleep(20)'],
                                  folder, self.config(), True)
            self.assertEqual(out['status'], 'INPUT_OR_EXECUTION_STOP')
            self.assertIn('FINAL_OUTPUT_SNAPSHOT', out['reason'])
            self.assertTrue(c.status(folder)['seal_verified'])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'tests_run': result.testsRun,
              'tests_passed': result.testsRun - len(result.errors) - len(result.failures) - len(result.skipped),
              'errors': len(result.errors), 'failures': len(result.failures), 'skipped': len(result.skipped),
              'real_packets_decoded': 0, 'model_calls': 0,
              'scope': 'V2 monitor regressions and inherited controller tests rebound to V2; generated only'}
    print('SYNTHETIC_RESULT ' + json.dumps(report), flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
