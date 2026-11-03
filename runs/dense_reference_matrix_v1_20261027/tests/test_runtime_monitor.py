"""Synthetic failure/transport tests; no service, remote access or model use."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'hpc'))
sys.path.insert(0, str(HERE / 'src'))
from common import read, write
import progress_server
import status_bridge
import status_sync
import supervisor
import prepare_runtime


class OuterStateTests(unittest.TestCase):
    def test_scheduler_queue_without_child_is_explicit_and_connection_loss_stays_unknown(self):
        for state in ('PENDING', 'CONFIGURING'):
            value = status_bridge.reconcile({'status': 'UNKNOWN', 'stage': 'launch'}, {'state': state})
            self.assertEqual(value['status'], 'QUEUED')
            self.assertFalse(value['worker_alive'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'bundle.json', {'job_id': '123',
                'observed_utc': datetime.now(timezone.utc).isoformat(),
                'progress': {'status': 'UNKNOWN', 'stage': 'launch'},
                'scheduler': {'state': 'PENDING'}})
            write(root / 'sync.json', {'status': 'OK'})
            self.assertEqual(progress_server.view(root)['status'], 'QUEUED')
            write(root / 'sync.json', {'status': 'UNKNOWN'})
            self.assertEqual(progress_server.view(root)['status'], 'UNKNOWN')

    def test_scheduler_running_without_child_waits_for_receipt_and_then_actual_progress(self):
        value = status_bridge.reconcile({'status': 'UNKNOWN', 'stage': 'launch'}, {'state': 'RUNNING'})
        self.assertEqual(value['status'], 'STARTING')
        self.assertFalse(value['worker_alive'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'bundle.json', {'job_id': '123',
                'observed_utc': datetime.now(timezone.utc).isoformat(),
                'progress': value, 'scheduler': {'state': 'RUNNING'}})
            write(root / 'sync.json', {'status': 'OK'})
            view = progress_server.view(root)
            self.assertEqual(view['status'], 'STARTING')
            self.assertIn('等待实验启动回执', view['label'])
        value = status_bridge.reconcile({'status': 'RUNNING', 'stage': 'encode'}, {'state': 'RUNNING'})
        self.assertEqual(value['status'], 'RUNNING')

    def test_prefix_completion_explicitly_excludes_target_matrix(self):
        with tempfile.TemporaryDirectory() as temp:
            write(Path(temp) / 'bundle.json', {'job_id': '123',
                'observed_utc': datetime.now(timezone.utc).isoformat(),
                'progress': {'status': 'COMPLETE', 'evaluation_scope': 'AUTHORIZED_STAGE_PREFIX_ONLY',
                             'stages': [{'name': name, 'state': 'COMPLETE'}
                                        for name in ('runtime', 'encode', 'source_cal')]},
                'scheduler': {'state': 'COMPLETED', 'exit_code': '0:0'}})
            value = progress_server.view(temp)
            self.assertFalse(value['matrix_included'])
            self.assertIn('未运行目标矩阵', value['label'])
            self.assertIn('第三池冻结证据', value['scope_message'])

    def test_full_scope_and_legacy_stage_fallback_are_distinguished(self):
        for data in ({'evaluation_scope': 'FULL_MATRIX'},
                     {'stages': [{'name': 'runtime'}, {'name': 'matrix'}]},
                     {'stages': ['runtime', 'matrix']}):
            self.assertTrue(progress_server.execution_scope(data)['matrix_included'])
        value = progress_server.execution_scope({'evaluation_scope': 'AUTHORIZED_STAGE_PREFIX_ONLY',
                                                'stages': ['matrix']})
        self.assertFalse(value['matrix_included'])

    def test_science_complete_waits_for_scheduler_before_freezing_cache(self):
        value = status_bridge.reconcile({'status': 'COMPLETE'}, {'state': 'RUNNING'})
        self.assertEqual(value['status'], 'FINALIZING')
        value = status_bridge.reconcile(value, {'state': 'COMPLETED', 'exit_code': '0:0'})
        self.assertEqual(value['status'], 'COMPLETE')

    def test_outer_failure_after_child_complete_is_still_observed(self):
        value = status_bridge.reconcile({'status': 'COMPLETE'}, {'state': 'RUNNING'})
        value = status_bridge.reconcile(value, {'state': 'FAILED', 'exit_code': '143:0'})
        self.assertEqual(value['status'], 'EXCEPTION_STOP')
        self.assertEqual(value['scientific_child_status'], 'COMPLETE')

    def test_scheduler_failure_overrides_completed_child(self):
        value = status_bridge.reconcile({'status': 'COMPLETE', 'scientific_status': 'FAIL'},
                                         {'state': 'OUT_OF_MEMORY'})
        self.assertEqual(value['status'], 'EXCEPTION_STOP')
        self.assertEqual(value['scientific_child_status'], 'COMPLETE')
        self.assertEqual(value['scientific_status'], 'FAIL')
        value = status_bridge.reconcile(value, {'state': 'OUT_OF_MEMORY'})
        self.assertEqual(value['scientific_child_status'], 'COMPLETE')

    def test_launch_failure_overrides_completed_child(self):
        value = status_bridge.reconcile({'status': 'COMPLETE'}, {'state': 'COMPLETED'},
            {'status': 'EXCEPTION_STOP', 'reason': 'POST_CHAIN_EXIT:143'})
        self.assertEqual(value['status'], 'EXCEPTION_STOP')
        self.assertEqual(value['reason'], 'POST_CHAIN_EXIT:143')

    def test_scheduler_complete_requires_science_receipt(self):
        value = status_bridge.reconcile({'status': 'RUNNING'}, {'state': 'COMPLETED', 'exit_code': '0:0'})
        self.assertEqual(value['status'], 'EXCEPTION_STOP')
        self.assertIn('WITHOUT_CHAIN_COMPLETE_RECEIPT', value['reason'])

    def test_completed_job_nonzero_exit_is_failure(self):
        value = status_bridge.reconcile({'status': 'COMPLETE'}, {'state': 'COMPLETED', 'exit_code': '1:0'})
        self.assertEqual(value['status'], 'EXCEPTION_STOP')

    def test_collector_keeps_root_job_and_actual_encoder_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'job_123/science/status.json', {'status': 'RUNNING', 'stage': 'encode'})
            write(root / 'job_123/science/encode/status.json',
                  {'status': 'RUNNING', 'stage': 'E3_ORIGINAL104', 'completed': 16, 'total': 104})
            result = subprocess.CompletedProcess([], 0,
                '123.batch|FAILED|1:0|00:01|node1\n123|RUNNING|0:0|00:02|node1\n', '')
            with patch.object(status_bridge.subprocess, 'run', return_value=result):
                value = status_bridge.collect(root, '123')
            self.assertEqual(value['scheduler']['state'], 'RUNNING')
            self.assertEqual(value['progress']['stage_progress']['completed'], 16)
            self.assertEqual(value['progress']['stage_progress']['total'], 104)

    def test_collector_launch_failure_is_not_hidden_by_child_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'job_123/science/status.json', {'status': 'COMPLETE'})
            write(root / 'job_123/launch.json', {'status': 'EXCEPTION_STOP', 'reason': 'OUTER_EXIT:143'})
            with patch.object(status_bridge.subprocess, 'run', side_effect=OSError('fixture')):
                value = status_bridge.collect(root, '123')
            self.assertEqual(value['progress']['status'], 'EXCEPTION_STOP')

    def test_unknown_first_sync_does_not_claim_unsubmitted(self):
        with tempfile.TemporaryDirectory() as temp:
            write(Path(temp) / 'sync.json', {'status': 'UNKNOWN', 'job_id': '123', 'reason': 'ConnectionError'})
            value = progress_server.view(temp)
            self.assertEqual(value['status'], 'UNKNOWN')
            self.assertEqual(value['job_id'], '123')
            self.assertFalse(value['terminal'])

    def test_cached_scheduler_terminal_does_not_require_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp:
            write(Path(temp) / 'bundle.json', {'job_id': '123',
                'observed_utc': datetime.now(timezone.utc).isoformat(),
                'progress': {'status': 'RUNNING'}, 'scheduler': {'state': 'COMPLETED'}})
            value = progress_server.view(temp)
            self.assertEqual(value['status'], 'EXCEPTION_STOP')
            self.assertFalse(value['heartbeat_required'])


class ValidationTests(unittest.TestCase):
    def fixture(self):
        return dict(schema='paper04-dense-progress-bundle-v1', job_id='123',
            observed_utc=datetime.now(timezone.utc).isoformat(), progress={'status': 'RUNNING'},
            scheduler={'job_id': '123', 'state': 'RUNNING'}, read_only=True, automatic_retry=False)

    def test_retry_policy_and_timestamp_must_be_explicit(self):
        for field, wrong in (('automatic_retry', True), ('observed_utc', '2026-10-27T00:00:00'),
                             ('observed_utc', None), ('observed_utc', 'not-a-time')):
            value = self.fixture()
            value[field] = wrong
            with self.assertRaises(ValueError):
                status_sync.validate_bundle(value, '123')

    def test_sync_normalizes_terminal_scheduler_before_deciding_to_exit(self):
        value = self.fixture()
        value['scheduler']['state'] = 'TIMEOUT'
        self.assertEqual(status_sync.validate_bundle(value, '123')['progress']['status'], 'EXCEPTION_STOP')

    def test_port_recovery_uses_unique_ssh_pid_listener_pair(self):
        def process(pid, port):
            return SimpleNamespace(pid=pid, info={'name': 'ssh.exe', 'pid': pid,
                'cmdline': ['ssh.exe', '-T', '-D', str(port), 'school-hpc', 'bash']})
        def listener(pid, port):
            return SimpleNamespace(pid=pid, status=status_sync.psutil.CONN_LISTEN,
                laddr=SimpleNamespace(ip='127.0.0.1', port=port))
        with patch.object(status_sync.psutil, 'process_iter', return_value=[process(10, 60001)]), \
             patch.object(status_sync.psutil, 'net_connections', return_value=[listener(10, 60001)]):
            self.assertEqual(status_sync.existing_port(), 60001)
        with patch.object(status_sync.psutil, 'process_iter', return_value=[process(10, 60001)]), \
             patch.object(status_sync.psutil, 'net_connections', return_value=[listener(11, 60001)]):
            self.assertIsNone(status_sync.existing_port())
        with patch.object(status_sync.psutil, 'process_iter',
                          return_value=[process(10, 60001), process(11, 60002)]), \
             patch.object(status_sync.psutil, 'net_connections',
                          return_value=[listener(10, 60001), listener(11, 60002)]):
            self.assertIsNone(status_sync.existing_port())


class PrivateRuntimeTests(unittest.TestCase):
    def fixture(self, root):
        package = root / 'package'
        wheel = package / 'wheels/numpy-fixture.whl'
        wheel.parent.mkdir(parents=True)
        wheel.write_bytes(b'not installed: mocked subprocess only')
        from common import sha
        write(package / 'config/runtime.json', {'numpy_wheel': 'wheels/numpy-fixture.whl',
                                              'numpy_wheel_sha256': sha(wheel)})
        return package, wheel

    def test_offline_install_and_fresh_child_overlay_are_wired(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package, _ = self.fixture(root)
            output = root / 'private'
            with patch.object(prepare_runtime.sys, 'platform', 'linux'), \
                 patch.object(prepare_runtime.sys, 'version_info', (3, 11)), \
                 patch.object(prepare_runtime.subprocess, 'run') as run:
                result = prepare_runtime.prepare(package, output, python='/fixture/python311')
            self.assertEqual(result['numerical_parity'], 'NOT_ASSESSED')
            install, probe = run.call_args_list
            self.assertIn('--no-index', install.args[0])
            self.assertIn('--no-deps', install.args[0])
            target = install.args[0].index('--target') + 1
            self.assertEqual(install.args[0][target], str(output / 'numpy201'))
            self.assertEqual(probe.kwargs['env']['PYTHONPATH'].split(__import__('os').pathsep)[0],
                             str(output / 'numpy201'))
            self.assertTrue(install.kwargs['stdout'].closed)

    def test_wheel_tamper_stops_before_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package, wheel = self.fixture(root)
            wheel.write_bytes(b'changed')
            with patch.object(prepare_runtime.sys, 'platform', 'linux'), \
                 patch.object(prepare_runtime.sys, 'version_info', (3, 11)), \
                 patch.object(prepare_runtime.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'NUMPY_WHEEL_SHA'):
                    prepare_runtime.prepare(package, root / 'private')
                run.assert_not_called()
            self.assertFalse((root / 'private').exists())


class BeforeLaunchTests(unittest.TestCase):
    def call(self, root, **kwargs):
        return supervisor.run_stage([sys.executable, '-c', 'raise RuntimeError("must not launch")'],
            output=root / 'out', control=root / 'control',
            limits=dict(wall_seconds=5, rss_bytes=256*1024**2, output_bytes=1024**2,
                        min_free_bytes=kwargs.pop('min_free_bytes', 0), poll_seconds=.03), **kwargs)

    def test_existing_stop_is_honored_before_child_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stop = root / 'STOP_REQUESTED'
            stop.touch()
            with patch.object(supervisor.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(RuntimeError, 'USER_STOP_REQUESTED'):
                    self.call(root, stop_file=stop)
                launch.assert_not_called()
            self.assertTrue(read(root / 'control/status.json')['cleanup_confirmed'])

    def test_free_space_failure_is_honored_before_child_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(supervisor.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(RuntimeError, 'FREE_SPACE_LIMIT'):
                    self.call(root, min_free_bytes=2**63)
                launch.assert_not_called()
            self.assertFalse(read(root / 'control/status.json')['worker_alive'])

    def test_cleanup_failure_keeps_durable_error_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            child = unittest.mock.Mock(pid=123, returncode=7)
            child.poll.return_value = 7
            with patch.object(supervisor.subprocess, 'Popen', return_value=child), \
                 patch.object(supervisor, 'tree', return_value=[]), \
                 patch.object(supervisor, 'read', side_effect=RuntimeError('fixture')), \
                 patch.object(child, 'poll', side_effect=[None, 7, 7, 7]), \
                 patch.object(supervisor, 'kill_tree', side_effect=TimeoutError('cleanup fixture')):
                # Force the final cleanup path to discover an unconfirmed worker.
                with patch.object(supervisor, 'tree', side_effect=[[], [child]]):
                    with self.assertRaises(RuntimeError):
                        self.call(root)
            record = read(root / 'control/status.json')
            self.assertEqual(record['status'], 'EXCEPTION_STOP')
            self.assertFalse(record['cleanup_confirmed'])
            self.assertIn('cleanup fixture', record['cleanup_error'])


if __name__ == '__main__':
    unittest.main()
