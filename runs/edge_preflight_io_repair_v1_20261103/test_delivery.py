import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('io_receiver_under_test', HERE / 'remote_receiver.py')
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


class DeliveryTests(unittest.TestCase):
    def make(self, root, runner=lambda *a, **k: subprocess.CompletedProcess(a[0], 0, '', '')):
        config = receiver.base.read(receiver.OLD / 'DELIVERY.json')
        return receiver.Receiver(config, root=root, runner=runner)

    def test_isolated_intents_reused_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / 'runs' / receiver.OLD.name
            old.mkdir(parents=True)
            prior = old / 'SUBMIT_ATTEMPT.json'
            prior.write_text('prior evidence')
            value = self.make(root)
            self.assertEqual(value.incoming, old / 'incoming')
            self.assertEqual(value.raw, old / 'raw')
            self.assertNotEqual(value.outputs.parent, old)
            receiver.base.write(value.here / 'SUBMIT_ATTEMPT.json', {'new': True})
            self.assertEqual(prior.read_text(), 'prior evidence')

    def test_live_prior_blocks_submit_before_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            value = self.make(folder, runner=lambda *a, **k:
                subprocess.CompletedProcess(a[0], 0, '181403|RUNNING|0:0\n', ''))
            receiver.base.write(value.old / 'SUBMIT_RECEIPT.json', {'job_id': '181403'})
            with self.assertRaisesRegex(ValueError, 'PRIOR_JOB_NOT_TERMINAL'):
                value.ensure_prior_terminal()
            self.assertFalse((value.here / 'SUBMIT_ATTEMPT.json').exists())

    def test_path_adapter_changes_only_two_assignments(self):
        source = (receiver.OLD.parent / 'edge_linux_preflight_package_v1_20261103/preflight.slurm').read_bytes()
        changed, replacements = receiver.base.adapt_slurm_paths(source, '/frozen', '/new')
        original_lines = source.decode().splitlines()
        modified_lines = changed.decode().splitlines()
        self.assertEqual(sum(a != b for a, b in zip(original_lines, modified_lines)), 2)
        self.assertEqual(len(replacements), 2)
        self.assertEqual([x for x in original_lines if x.startswith('#SBATCH')],
                         [x for x in modified_lines if x.startswith('#SBATCH')])
        self.assertEqual(original_lines[-3:], modified_lines[-3:])

    def test_export_no_outside_checkout_or_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            value = self.make(folder)
            output = value.outputs / 'edge_preflight_999999'
            output.mkdir(parents=True)
            receiver.base.write(output / 'DELIVERY_RESULT.json', {'status': 'STOPPED_NO_RETRY'})
            (output / 'state.pkl').write_bytes(b'never export')
            value.checkout.mkdir(parents=True)
            (value.checkout / 'edge-preflight-999999.err').write_text('this job log')
            value.state = lambda: dict(job=dict(job_id='999999', output_directory=str(output)),
                                        result_ready=True, scheduler={})
            archive = value.results()
            with tarfile.open(archive) as stream:
                names = stream.getnames()
                self.assertTrue(all('..' not in Path(name).parts for name in names))
                self.assertFalse(any(name.endswith('.pkl') for name in names))
                self.assertIn('edge-preflight-999999.err', names)
                self.assertIn('RESULT_MANIFEST.json', names)


if __name__ == '__main__':
    unittest.main()
