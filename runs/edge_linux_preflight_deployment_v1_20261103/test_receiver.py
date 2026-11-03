"""Metadata/transfer and Slurm uncertainty contracts; no live scheduler/network."""
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('edge_receiver_tested', HERE / 'remote_receiver.py')
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def config():
    return dict(token='a' * 48, archive_manifest_sha256=receiver.MANIFEST_SHA,
                files={key: dict(filename='bundle.tar' if key == 'archive' else key + '.pcap',
                                bytes=4, sha256=receiver.ARCHIVE_SHA if key == 'archive' else digest(b'abcd'))
                       for key in ('archive', 'NORMAL', 'HTTP', 'UDP')})


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as temporary:
        runner = Mock()
        item = receiver.Receiver(config(), root=Path(temporary), runner=runner)
        yield item, runner


def make_tar(names, link=False):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as stream:
        for name in names:
            info = tarfile.TarInfo(name)
            if link:
                info.type = tarfile.SYMTYPE
                info.linkname = '/etc/passwd'
                stream.addfile(info)
            else:
                info.size = 1
                stream.addfile(info, io.BytesIO(b'x'))
    data.seek(0)
    return tarfile.open(fileobj=data, mode='r:')


def prepare_submit(item):
    script = item.here / 'SUBMIT_PREFLIGHT_ONCE.sh'
    script.write_bytes(b'#!/bin/bash\nexit 0\n')
    receiver.write(item.here / 'PREPARE_RECEIPT.json',
                   dict(status='PREPARED_NOT_SUBMITTED', submit_wrapper_sha256=receiver.sha(script)))


class ReceiverContracts(unittest.TestCase):
    def test_wrong_archive_and_manifest_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            cfg = config()
            cfg['archive_manifest_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'PINNED_MANIFEST_IDENTITY'):
                receiver.Receiver(cfg, root=Path(temporary))
            cfg = config()
            cfg['files']['archive']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'PINNED_ARCHIVE_IDENTITY'):
                receiver.Receiver(cfg, root=Path(temporary))

    def test_upload_resumes_exact_offset_and_rejects_bad_chunk(self):
        with fixture() as (item, _):
            first = item.upload('NORMAL', b'ab', 0, digest(b'ab'))
            self.assertEqual(first['offset'], 2)
            self.assertFalse(first['complete'])
            with self.assertRaisesRegex(ValueError, 'UPLOAD_OFFSET'):
                item.upload('NORMAL', b'cd', 0, digest(b'cd'))
            with self.assertRaisesRegex(ValueError, 'UPLOAD_CHUNK_SHA'):
                item.upload('NORMAL', b'cd', 2, digest(b'xx'))
            done = item.upload('NORMAL', b'cd', 2, digest(b'cd'))
            self.assertTrue(done['complete'])
            self.assertEqual(item.path('NORMAL').read_bytes(), b'abcd')
            self.assertEqual(item.upload('NORMAL', b'cd', 2, digest(b'cd')), done)

    def test_existing_same_size_tamper_is_rehashed_and_rejected(self):
        with fixture() as (item, _):
            item.upload('HTTP', b'abcd', 0, digest(b'abcd'))
            item.path('HTTP').write_bytes(b'zzzz')
            with self.assertRaisesRegex(ValueError, 'EXISTING_INPUT_SHA'):
                item.file_state('HTTP')

    def test_complete_partial_after_crash_is_recovered_without_append(self):
        with fixture() as (item, _):
            target = item.path('UDP')
            target.with_name(target.name + '.part').write_bytes(b'abcd')
            self.assertTrue(item.file_state('UDP')['complete'])
            self.assertEqual(target.read_bytes(), b'abcd')

    def test_unsafe_duplicate_and_symlink_archive_entries_refused(self):
        for names, link, error in [(['edge_preflight_checkout/../oops'], False, 'ARCHIVE_PATH'),
                                   (['edge_preflight_checkout/a'] * 2, False, 'ARCHIVE_DUPLICATE'),
                                   (['edge_preflight_checkout/a'], True, 'ARCHIVE_REGULAR_ONLY'),
                                   (['other/a'], False, 'ARCHIVE_PREFIX')]:
            with self.subTest(error=error), make_tar(names, link=link) as archive:
                with self.assertRaisesRegex(ValueError, error):
                    receiver.regular_members(archive, 100)

    def test_submit_timeout_cannot_submit_again_even_after_restart(self):
        with fixture() as (item, runner):
            prepare_submit(item)
            runner.side_effect = subprocess.TimeoutExpired('sbatch', 20)
            with patch.object(item, 'validate_extracted', return_value={}):
                with self.assertRaises(subprocess.TimeoutExpired):
                    item.submit()
                with self.assertRaisesRegex(ValueError, 'STOP_UNCERTAIN'):
                    item.submit()
            restarted = receiver.Receiver(config(), root=item.root, runner=runner)
            with self.assertRaisesRegex(ValueError, 'STOP_UNCERTAIN'):
                restarted.submit()
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(receiver.read(item.here / 'SUBMIT_UNCERTAIN.json')['status'], 'STOP_UNCERTAIN_NO_RETRY')

    def test_confirmed_submission_is_idempotent(self):
        with fixture() as (item, runner):
            prepare_submit(item)
            runner.return_value = subprocess.CompletedProcess(['sbatch'], 0, 'environment message\n180999;cluster\n', '')
            with patch.object(item, 'validate_extracted', return_value={}):
                first = item.submit()
                second = item.submit()
            self.assertEqual(first['job_id'], '180999')
            self.assertEqual(first, second)
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(first['wall_seconds'], 600)
            self.assertFalse(first['formal_external_evaluation'])

    def test_wrapper_tamper_fails_before_attempt(self):
        with fixture() as (item, runner):
            prepare_submit(item)
            (item.here / 'SUBMIT_PREFLIGHT_ONCE.sh').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SUBMIT_WRAPPER_CHANGED'):
                item.submit()
            self.assertFalse((item.here / 'SUBMIT_ATTEMPT.json').exists())
            runner.assert_not_called()

    def test_result_manifest_pins_each_member_and_excludes_raw_arrays(self):
        with fixture() as (item, _):
            output = item.outputs / 'edge_preflight_180999'
            (output / 'real_slice').mkdir(parents=True)
            receiver.write(output / 'DELIVERY_RESULT.json', dict(status='STOPPED_NO_RETRY'))
            receiver.write(output / 'real_slice/RESULT.json', dict(status='STOPPED_NO_RETRY'))
            (output / 'raw.pcap').write_bytes(b'private raw')
            (output / 'encoding.npy').write_bytes(b'numerical array')
            state = dict(job=dict(job_id='180999', output_directory=str(output)), result_ready=True,
                         scheduler={'stdout': 'FAILED'})
            with patch.object(item, 'state', return_value=state):
                result = item.results()
            with tarfile.open(result) as archive:
                manifest = json.load(archive.extractfile('RESULT_MANIFEST.json'))
                self.assertFalse(any(x.endswith(('.pcap', '.npy')) for x in archive.getnames()))
                self.assertEqual(set(archive.getnames()) - {'RESULT_MANIFEST.json'}, set(manifest['files']))
                for name, pin in manifest['files'].items():
                    data = archive.extractfile(name).read()
                    self.assertEqual(len(data), pin['bytes'])
                    self.assertEqual(digest(data), pin['sha256'])

    def test_scheduler_terminal_without_receipt_exports_explicit_failure(self):
        with fixture() as (item, _):
            output = item.outputs / 'edge_preflight_180999'
            state = dict(job=dict(job_id='180999', output_directory=str(output)), result_ready=True,
                         scheduler={'stdout': 'TIMEOUT'})
            with patch.object(item, 'state', return_value=state):
                result = item.results()
            self.assertFalse((output / 'DELIVERY_RESULT.json').exists())
            with tarfile.open(result) as archive:
                manifest = json.load(archive.extractfile('RESULT_MANIFEST.json'))
                synthetic = manifest['synthesized_failure_receipts']
                self.assertEqual(len(synthetic), 1)
                failure = json.load(archive.extractfile(synthetic[0]))
                self.assertTrue(failure['generated_export_receipt'])
                self.assertFalse(failure['actual_delivery_result_emitted'])
                self.assertFalse(failure['final_runtime_gate_pass'])

    def test_existing_environment_is_reused_without_model_import(self):
        with fixture() as (item, _):
            environment = item.shell_environment()
            self.assertIn('frontend_compat_v1/environment.sh', environment)
            self.assertIn('numpy201:', environment)
            self.assertIn('vendor_py311_v1', environment)
            self.assertNotIn('pip install', environment)
            self.assertNotIn('import torch', environment)


if __name__ == '__main__':
    unittest.main()
