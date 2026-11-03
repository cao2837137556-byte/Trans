import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
import common
import service


class ServiceOutputIsolationTests(unittest.TestCase):
    def setUp(self):
        validation = Path(__file__).resolve().parents[1] / 'validation'
        self.temp = tempfile.TemporaryDirectory(dir=str(validation))
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = self.base / 'config.json'
        common.write(self.config, dict(schema='learned-onboarding-local-config-v1',
                                       spec_sha256=common.SPEC_SHA256,
                                       source={}))
        self.assets = self.base / 'source_assets'

    def call(self, stage, output, *extra):
        args = [stage, '--config', str(self.config), '--output', str(output),
                '--source-assets', str(self.assets), *extra]
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = service.main(args)
        return result, errors.getvalue()

    def test_existing_output_is_unchanged(self):
        output = self.base / 'existing'
        output.mkdir()
        marker = output / 'user.txt'
        marker.write_bytes(b'preserve this exact content')
        with mock.patch('source_inputs.prepare_source') as prepare:
            code, error = self.call('prepare', output)
        self.assertEqual(code, 1)
        self.assertIn('OUTPUT_ALREADY_EXISTS', error)
        prepare.assert_not_called()
        self.assertEqual(marker.read_bytes(), b'preserve this exact content')
        self.assertEqual(sorted(p.name for p in output.iterdir()), ['user.txt'])

    def test_aliases_are_rejected_before_source_loading(self):
        self.assets.mkdir()
        cases = [
            ('prepare', self.assets, ()),
            ('fit', self.base / 'fit_input',
             ('--fit-dir', str(self.base / 'fit_input'),
              '--execution-slot', 'exclusive-local')),
            ('prepare', SRC / 'unsafe-output-test', ()),
            ('prepare', common.ROOT /
             'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022', ()),
        ]
        with mock.patch('source_inputs.prepare_source') as prepare:
            for stage, output, extra in cases:
                with self.subTest(stage=stage, output=str(output)):
                    existed = output.exists()
                    code, error = self.call(stage, output, *extra)
                    self.assertEqual(code, 1)
                    self.assertTrue('OUTPUT_INPUT_PATH_OVERLAP' in error or
                                    'OUTPUT_OUTSIDE_STAGE_ROOTS' in error)
                    self.assertEqual(output.exists(), existed)
                    self.assertFalse((output / 'EXCEPTION_STOP.json').exists())
        prepare.assert_not_called()

    def test_new_output_missing_execution_slot_keeps_own_exception(self):
        output = self.base / 'missing_slot'
        with mock.patch('source_inputs.prepare_source') as prepare:
            code, error = self.call('fit', output)
        self.assertEqual(code, 1)
        self.assertIn('EXCLUSIVE_EXECUTION_SLOT_REQUIRED', error)
        prepare.assert_not_called()
        receipt = common.read(output / 'EXCEPTION_STOP.json')
        self.assertEqual(receipt['stage'], 'fit')
        self.assertIn('EXCLUSIVE_EXECUTION_SLOT_REQUIRED',
                      str(receipt))
        self.assertFalse((self.assets / 'EXCEPTION_STOP.json').exists())

    def test_prepare_writes_only_source_receipt_and_seal(self):
        output = self.base / 'prepared'
        source = dict(rows=[{}, {}], references=dict(rows=[{}]),
                      binding=dict(source='fixture'))
        with mock.patch('source_inputs.prepare_source', return_value=source) as prepare, \
             mock.patch.object(service.pipeline, 'fit_source') as fit:
            code, error = self.call('prepare', output)
        self.assertEqual((code, error), (0, ''))
        prepare.assert_called_once_with(config={}, output_dir=self.assets,
                                        validate_only=True)
        fit.assert_not_called()
        self.assertEqual(sorted(p.name for p in output.iterdir()),
                         ['SEAL.json', 'source_prepare.json'])
        common.verify_seal(output)
        receipt = common.read(output / 'source_prepare.json')
        self.assertEqual(receipt['status'], 'SOURCE_IDENTITIES_VERIFIED')
        self.assertEqual(receipt['source_rows'], 2)
        self.assertEqual(receipt['reference_rows'], 1)
        self.assertFalse(receipt['training_started'])
        self.assertEqual(receipt['target_queries_read'], 0)


if __name__ == '__main__':
    unittest.main()
