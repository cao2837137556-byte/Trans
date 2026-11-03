"""Generated-only resource and terminal-state tests. No real experiment assets."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from hnr.runtime import Runtime, LIMITS
from hnr import runtime as runtime_module

spec = importlib.util.spec_from_file_location('history_progress', PACKAGE / 'progress.py')
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'generated'
        # Resource tests must be isolated from parallel implementation edits.
        # The real source enumeration is tested independently below.
        identity = patch('hnr.runtime.code_identity', return_value={'generated.py': 'a'*64})
        identity.start()
        self.addCleanup(identity.stop)

    def runtime(self, **changes):
        limits = dict(LIMITS, **changes)
        return Runtime(self.output, synthetic=True, monitor=False, limits=limits)

    def test_terminal_receipt_and_no_reuse(self):
        with self.runtime() as rt:
            rt.update('CENSUS', device='generated', pass_number=1, processed_packets=5)
            rt.pairs(9)
            rt.encoded(3)
            rt.finish(dict(scientific_status='STOP_DEV_FAIL'))
        status = json.loads((self.output / 'STATUS.json').read_text())
        receipt = json.loads((self.output / 'STAGE_RECEIPT.json').read_text())
        self.assertEqual(status['technical_status'], 'COMPLETED')
        self.assertEqual(status['scientific_status'], 'STOP_DEV_FAIL')
        self.assertEqual(receipt['pairs'], 9)
        self.assertEqual(receipt['encoded_rows'], 3)
        self.assertFalse(receipt['automatic_retry'])
        self.assertIn('RESULT.json', receipt['outputs'])
        with self.assertRaises(FileExistsError):
            with self.runtime():
                pass
        self.assertEqual(json.loads((self.output / 'RESULT.json').read_text())['scientific_status'],
                         'STOP_DEV_FAIL')

    def test_precharged_pair_limit_prevents_work(self):
        reached_work = False
        with self.assertRaisesRegex(ValueError, 'PAIRS_LIMIT'):
            with self.runtime(pairs=10) as rt:
                rt.count_pairs(11)
                reached_work = True
        self.assertFalse(reached_work)
        status = json.loads((self.output / 'STATUS.json').read_text())
        self.assertEqual(status['technical_status'], 'EXCEPTION_STOPPED')
        self.assertEqual(status['error'], 'PAIRS_LIMIT')

    def test_encoded_limit_and_negative_counts(self):
        with self.runtime(encoded=3) as rt:
            rt.encoded(3)
            with self.assertRaisesRegex(ValueError, 'ENCODED_LIMIT'):
                rt.encoded(1)
            with self.assertRaisesRegex(ValueError, 'NONNEGATIVE'):
                rt.pairs(-1)
            rt.finish(dict(status='TEST_ONLY'))

    def test_wall_guard(self):
        with self.assertRaisesRegex(ValueError, 'WALL_SECONDS_LIMIT'):
            with self.runtime() as rt:
                rt.started -= LIMITS['wall_seconds'] + 1
                rt.guard()

    def test_disk_and_memory_limits(self):
        for key, message in [('rss_bytes', 'RSS_BYTES_LIMIT'),
                             ('output_bytes', 'OUTPUT_BYTES_LIMIT')]:
            self.output = Path(self.temp.name) / key
            with self.assertRaisesRegex(ValueError, message):
                with self.runtime() as rt:
                    rt.limits[key] = 1
                    rt.checkpoint(force=True)

    def test_check_disallows_science_and_no_missing_finish(self):
        with self.assertRaisesRegex(ValueError, 'PAIRS_LIMIT'):
            with Runtime(self.output, mode='check', synthetic=True, monitor=False) as rt:
                rt.pairs(1)
        self.output = Path(self.temp.name) / 'missing_finish'
        with self.assertRaisesRegex(RuntimeError, 'RUN_DID_NOT_FINALIZE'):
            with self.runtime():
                pass
        self.assertEqual(json.loads((self.output / 'STATUS.json').read_text())['technical_status'],
                         'EXCEPTION_STOPPED')

    def test_monitor_heartbeat_does_not_claim_work(self):
        with self.runtime() as rt:
            stale = (datetime.now(timezone.utc) - timedelta(seconds=150)).isoformat()
            rt.state['work_heartbeat_utc'] = stale
            rt.checkpoint(force=True)
            view = progress.snapshot(self.output / 'STATUS.json')
            self.assertEqual(view['freshness'], 'stale')
            self.assertEqual(view['display_status'], 'UNKNOWN_WORKER_PROGRESS')
            self.assertLess(view['service_heartbeat_age_seconds'], 5)
            self.assertGreater(view['work_heartbeat_age_seconds'], 90)
            rt.tick(1, 3)
            rt.checkpoint(force=True)
            self.assertEqual(progress.snapshot(self.output / 'STATUS.json')['freshness'], 'fresh')
            rt.finish(dict(status='TEST_ONLY'))
        self.assertEqual(progress.snapshot(self.output / 'STATUS.json')['freshness'], 'terminal')

    def test_code_change_stops_finish(self):
        with self.assertRaisesRegex(ValueError, 'CODE_CHANGED_DURING_RUN'):
            with self.runtime() as rt:
                with patch('hnr.runtime.code_identity', return_value={'changed': 'yes'}):
                    rt.finish(dict(status='TEST_ONLY'))

    def test_signal_failure_is_durable(self):
        before = signal.getsignal(signal.SIGTERM)
        with self.assertRaisesRegex(RuntimeError, 'SIGNAL_STOP:SIGTERM'):
            with self.runtime() as rt:
                rt._on_signal(signal.SIGTERM, None)
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)
        self.assertEqual(json.loads((self.output / 'STATUS.json').read_text())['technical_status'],
                         'EXCEPTION_STOPPED')


class CodeIdentityTests(unittest.TestCase):
    def test_external_helpers_and_runtime_python_are_sealed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / 'runs/history'
            files = [package / 'run.py', package / 'progress.py', package / 'progress.html',
                     package / 'hpc/run.slurm', root / 'repo/ood/core.py',
                     root / 'runs/dense_reference_matrix_v1_20261027/vendor/encoding_v2/repo/ood/core.py',
                     root / 'runs/dense_reference_ab_stage_candidate_v1_20261028/vendor/encoding_v2/repo/ood/core.py',
                     root / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/matrix.py',
                     root / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py',
                     root / 'encoder/vendor/netFound/model.py']
            for path in files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixed content', encoding='utf-8')
            (package / 'config').mkdir()
            (package / 'config/EXECUTION.json').write_text(json.dumps(
                {'encoder': {'runtime_root': str(root / 'encoder')}}), encoding='utf-8')
            with patch.object(runtime_module, 'ROOT', root), patch.object(runtime_module, 'PACKAGE', package):
                first = runtime_module.code_identity()
                self.assertIn('@root/repo/ood/core.py', first)
                self.assertIn('@root/encoder/vendor/netFound/model.py', first)
                self.assertIn('progress.html', first)
                self.assertIn('hpc/run.slurm', first)
                self.assertIn('@root/runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py', first)
                (root / 'repo/ood/core.py').write_text('changed helper', encoding='utf-8')
                second = runtime_module.code_identity()
                self.assertNotEqual(first['@root/repo/ood/core.py'], second['@root/repo/ood/core.py'])


if __name__ == '__main__':
    unittest.main()
