"""Metadata/transfer and Slurm uncertainty contracts; no live scheduler/network."""
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('edge_receiver_tested', HERE / 'remote_receiver.py')
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)
SEALED_SLURM = (HERE.parent / 'edge_linux_preflight_package_v1_20261103/preflight.slurm').read_bytes()


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
    original = item.checkout / receiver.PACKAGE / 'preflight.slurm'
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(SEALED_SLURM)
    receiver.write(original.parent / 'PACKAGE_MANIFEST.json', dict(files={
        receiver.PACKAGE + '/preflight.slurm': dict(bytes=len(SEALED_SLURM), sha256=digest(SEALED_SLURM))}))
    with patch.object(item, 'runner', return_value=syntax_result()):
        adapter = item.create_path_adapter()
    script = item.here / 'SUBMIT_PREFLIGHT_ONCE.sh'
    script.write_bytes(b'#!/bin/bash\nexit 0\n')
    receiver.write(item.here / 'PREPARE_RECEIPT.json',
                   dict(status='PREPARED_NOT_SUBMITTED', submit_wrapper_sha256=receiver.sha(script),
                        slurm_path_adapter=adapter))


@contextmanager
def package_fixture():
    """Actual small archive/manifest/raw bytes exercise prepare, not just mocks."""
    cfg = config()
    expected = dict(Python='3.11.11', numpy='2.0.1', torch='2.5.1',
                    transformers='4.57.3', TShark='4.6.6')
    payload = b'pinned payload\n'
    payloads = {'repo/payload.bin': payload, receiver.PACKAGE + '/preflight.slurm': SEALED_SLURM}
    manifest_data = json.dumps(dict(files={name: dict(bytes=len(data), sha256=digest(data))
        for name, data in payloads.items()})).encode('utf-8')
    contract_data = json.dumps(dict(total_preflight_logical_with_probes=91,
        full_quality_evaluation_authorized=False, expected_runtime=expected,
        raw_inputs_separate_not_archived={key: cfg['files'][key]
                                         for key in ('NORMAL', 'HTTP', 'UDP')})).encode('utf-8')
    members = dict(payloads, **{
               receiver.PACKAGE + '/PACKAGE_MANIFEST.json': manifest_data,
               receiver.PACKAGE + '/PACKAGE_CONTRACT.json': contract_data})
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode='w') as archive:
        for name, data in members.items():
            info = tarfile.TarInfo('edge_preflight_checkout/' + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    archive_data = content.getvalue()
    cfg['archive_manifest_sha256'] = digest(manifest_data)
    cfg['files']['archive'].update(bytes=len(archive_data), sha256=digest(archive_data))
    with tempfile.TemporaryDirectory() as temporary, \
            patch.object(receiver, 'ARCHIVE_SHA', digest(archive_data)), \
            patch.object(receiver, 'MANIFEST_SHA', digest(manifest_data)), \
            patch.object(receiver.Receiver, 'storage', return_value={'free_bytes': 10**12}):
        runner = Mock()
        item = receiver.Receiver(cfg, root=Path(temporary), runner=runner)
        for key in cfg['files']:
            item.path(key).write_bytes(archive_data if key == 'archive' else b'abcd')
        yield item, runner


def metadata_result():
    return subprocess.CompletedProcess(['bash'], 0, json.dumps(dict(
        python='3.11.11', numpy='2.0.1', torch='2.5.1', transformers='4.57.3')) + '\n', '')


def decoder_result(code=0, stdout='TShark (Wireshark) 4.6.6 (Git commit test)\n', stderr=''):
    return subprocess.CompletedProcess(['bash'], code, stdout, stderr)


def syntax_result():
    return subprocess.CompletedProcess(['bash', '-n'], 0, '', '')


class ReceiverContracts(unittest.TestCase):
    def test_path_adapter_preserves_resources_and_all_but_two_source_lines(self):
        with package_fixture() as (item, runner):
            runner.side_effect = [metadata_result(), decoder_result(), syntax_result(), syntax_result()]
            prepared = item.prepare()
            adapter = prepared['slurm_path_adapter']
            original = (item.checkout / receiver.PACKAGE / 'preflight.slurm').read_bytes()
            adapted = (item.here / 'PREFLIGHT_PATH_ADAPTER.slurm').read_bytes()
            self.assertEqual(original, SEALED_SLURM)
            original_lines, adapted_lines = original.splitlines(keepends=True), adapted.splitlines(keepends=True)
            self.assertEqual(len(original_lines), len(adapted_lines))
            changed = [(a, b) for a, b in zip(original_lines, adapted_lines) if a != b]
            self.assertEqual(len(changed), 2)
            self.assertEqual([x for x in original_lines if x.startswith(b'#SBATCH')],
                             [x for x in adapted_lines if x.startswith(b'#SBATCH')])
            self.assertIn(b'#SBATCH --time=00:10:00', adapted)
            self.assertIn(b'#SBATCH --cpus-per-task=1', adapted)
            self.assertIn(b'#SBATCH --mem=6G', adapted)
            self.assertIn(b'#SBATCH --no-requeue', adapted)
            self.assertEqual(adapter['original_slurm_sha256'], digest(SEALED_SLURM))
            self.assertEqual(adapter['adapter_sha256'], digest(adapted))
            self.assertEqual({x['variable'] for x in adapter['replacements']}, {'EDGE_PACKAGE_DIR', 'EDGE_ROOT'})
            wrapper = (item.here / 'SUBMIT_PREFLIGHT_ONCE.sh').read_text(encoding='utf-8')
            self.assertIn(adapter['adapter_path'], wrapper)
            self.assertNotIn(' --partition=amd ' + receiver.PACKAGE + '/preflight.slurm', wrapper)

    def test_path_adapter_resolves_checkout_even_when_assignments_run_from_slurm_spool(self):
        git_bash = Path('C:/Program Files/Git/bin/bash.exe')
        bash = str(git_bash) if git_bash.is_file() else shutil.which('bash')
        if not bash:
            self.skipTest('A local Bash is needed for the relocated-spool assignment regression')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = (root / 'checkout with spaces').as_posix()
            package = checkout + '/' + receiver.PACKAGE
            adapted, _ = receiver.adapt_slurm_paths(SEALED_SLURM, checkout, package)
            assignments = [line for line in adapted.decode('utf-8').splitlines()
                           if line.startswith(('EDGE_PACKAGE_DIR=', 'EDGE_ROOT='))]
            spool = root / 'different-spool/job123/slurm_script'
            spool.parent.mkdir(parents=True)
            spool.write_text('\n'.join(assignments) + '\nprintf "%s\\n%s\\n" "$EDGE_PACKAGE_DIR" "$EDGE_ROOT"\n',
                             encoding='utf-8', newline='\n')
            result = subprocess.run([bash, spool.as_posix()], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [package, checkout])

    def test_adapter_tamper_fails_before_submission_intent(self):
        with fixture() as (item, runner):
            prepare_submit(item)
            (item.here / 'PREFLIGHT_PATH_ADAPTER.slurm').write_bytes(b'changed adapter')
            with patch.object(item, 'validate_extracted', return_value={}):
                with self.assertRaisesRegex(ValueError, 'SLURM_PATH_ADAPTER_CHANGED'):
                    item.submit()
            self.assertFalse((item.here / 'SUBMIT_ATTEMPT.json').exists())
            runner.assert_not_called()

    def test_path_adapter_refuses_unexpected_or_duplicate_assignments(self):
        for source in (SEALED_SLURM.replace(b'EDGE_ROOT="$(cd --', b'EDGE_ROOT="$(pwd); #'),
                       SEALED_SLURM + b'\nEDGE_ROOT=/unexpected\n'):
            with self.subTest(source_sha=digest(source)):
                with self.assertRaisesRegex(ValueError, 'SLURM_PATH_ASSIGNMENT_IDENTITY:EDGE_ROOT'):
                    receiver.adapt_slurm_paths(source, '/checkout', '/checkout/' + receiver.PACKAGE)

    def test_state_source_identity_is_captured_at_load_not_rehashed_after_file_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source_path = folder / 'snapshot_receiver.py'
            original = (HERE / 'remote_receiver.py').read_bytes()
            source_path.write_bytes(original)
            loaded_spec = importlib.util.spec_from_file_location('snapshot_receiver_tested', source_path)
            loaded = importlib.util.module_from_spec(loaded_spec)
            loaded_spec.loader.exec_module(loaded)
            # Replace on-disk code before creating the instance as well as
            # before reading state. This must not pretend the old import is new.
            source_path.write_bytes(b'# later deployed replacement\n')
            item = loaded.Receiver(config(), root=folder / 'work', runner=Mock())
            self.assertEqual(item.state()['receiver_source_sha256'], digest(original))
            self.assertNotEqual(item.state()['receiver_source_sha256'], digest(source_path.read_bytes()))

    def test_prepare_decoder_uses_worker_environment_and_saves_success_diagnostics(self):
        with package_fixture() as (item, runner):
            runner.side_effect = [metadata_result(), decoder_result(), syntax_result(), syntax_result()]
            prepared = item.prepare()
            self.assertEqual(prepared['status'], 'PREPARED_NOT_SUBMITTED')
            self.assertFalse(prepared['reused_verified_extraction'])
            command = runner.call_args_list[1].args[0]
            self.assertEqual(command[:2], ['bash', '-c'])
            self.assertTrue(command[2].startswith(item.shell_environment()))
            self.assertIn(receiver.TSHARK + ' --version', command[2])
            diagnostic = receiver.read(item.here / 'DECODER_IDENTITY.json')
            self.assertEqual(diagnostic['status'], 'PASS')
            self.assertEqual(diagnostic['returncode'], 0)
            self.assertIn('4.6.6', diagnostic['stdout'])
            self.assertEqual(diagnostic['stderr'], '')
            self.assertFalse((item.here / 'SUBMIT_ATTEMPT.json').exists())

    def test_decoder_library_failure_preserves_diagnostics_and_complete_extraction_can_resume(self):
        with package_fixture() as (item, runner):
            message = 'error while loading shared libraries: libimf.so: cannot open shared object file\n'
            runner.side_effect = [metadata_result(), decoder_result(127, '', message)]
            with self.assertRaisesRegex(ValueError, 'TSHARK_IDENTITY'):
                item.prepare()
            diagnostic = receiver.read(item.here / 'DECODER_IDENTITY.json')
            self.assertEqual(diagnostic['returncode'], 127)
            self.assertEqual(diagnostic['stdout'], '')
            self.assertEqual(diagnostic['stderr'], message)
            self.assertFalse((item.here / 'PREPARE_RECEIPT.json').exists())
            payload = item.checkout / 'repo/payload.bin'
            original_mtime = payload.stat().st_mtime_ns
            restarted = receiver.Receiver(item.config, root=item.root, runner=runner)
            runner.side_effect = [metadata_result(), decoder_result(), syntax_result(), syntax_result()]
            prepared = restarted.prepare()
            self.assertTrue(prepared['reused_verified_extraction'])
            self.assertEqual(payload.stat().st_mtime_ns, original_mtime)
            self.assertFalse((item.here / 'SUBMIT_ATTEMPT.json').exists())

    def test_partial_extraction_is_not_overwritten_or_silently_reused(self):
        with package_fixture() as (item, runner):
            item.checkout.mkdir(parents=True)
            partial = item.checkout / 'partial.bin'
            partial.write_bytes(b'partial')
            with self.assertRaisesRegex(ValueError, 'PARTIAL_EXTRACTION_REQUIRES_MANUAL_REVIEW'):
                item.prepare()
            self.assertEqual(partial.read_bytes(), b'partial')
            runner.assert_not_called()
            self.assertFalse((item.here / 'PREPARE_RECEIPT.json').exists())

    def test_complete_extraction_tamper_is_not_reused_after_decoder_failure(self):
        with package_fixture() as (item, runner):
            runner.side_effect = [metadata_result(), decoder_result(127, '', 'missing libimf.so')]
            with self.assertRaisesRegex(ValueError, 'TSHARK_IDENTITY'):
                item.prepare()
            (item.checkout / 'repo/payload.bin').write_bytes(b'changed payload')
            runner.reset_mock()
            with self.assertRaisesRegex(ValueError, 'PARTIAL_EXTRACTION_REQUIRES_MANUAL_REVIEW.*MANIFEST_FILE_PIN'):
                item.prepare()
            runner.assert_not_called()
            self.assertFalse((item.here / 'PREPARE_RECEIPT.json').exists())

    def test_decoder_identity_gate_rejects_empty_output_and_lookalike_versions(self):
        for output in ('', 'TShark (Wireshark) 4.6.60\n', 'TShark (Wireshark) 4.6.6.1\n'):
            with self.subTest(output=output), package_fixture() as (item, runner):
                runner.side_effect = [metadata_result(), decoder_result(stdout=output)]
                with self.assertRaisesRegex(ValueError, 'TSHARK_IDENTITY'):
                    item.prepare()
                diagnostic = receiver.read(item.here / 'DECODER_IDENTITY.json')
                self.assertEqual(diagnostic['status'], 'FAILED')
                self.assertEqual(diagnostic['stdout'], output)
                self.assertFalse((item.here / 'PREPARE_RECEIPT.json').exists())

    def test_decoder_timeout_preserves_captured_bytes_as_text(self):
        with package_fixture() as (item, runner):
            runner.side_effect = [metadata_result(), subprocess.TimeoutExpired(
                ['bash'], 15, output=b'partial stdout', stderr=b'partial stderr')]
            with self.assertRaises(subprocess.TimeoutExpired):
                item.prepare()
            diagnostic = receiver.read(item.here / 'DECODER_IDENTITY.json')
            self.assertEqual(diagnostic['status'], 'FAILED')
            self.assertIsNone(diagnostic['returncode'])
            self.assertEqual(diagnostic['stdout'], 'partial stdout')
            self.assertEqual(diagnostic['stderr'], 'partial stderr')
            self.assertFalse((item.here / 'PREPARE_RECEIPT.json').exists())

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
