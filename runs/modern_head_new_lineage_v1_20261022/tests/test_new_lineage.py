"""Regression checks for new boundaries, without training on development data."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'package'))
import package_io as p
import install_dependencies as installer
import modern_adapter as a
import modern_service as service


class WheelTests(unittest.TestCase):
    def wheel(self, root, name, data, wrong=False):
        dest = root / 'test.whl'; record = 'example.dist-info/RECORD'
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
        out = io.StringIO(); writer = csv.writer(out)
        writer.writerow([name, 'sha256=' + ('bad' if wrong else digest), len(data)])
        writer.writerow([record, '', ''])
        with zipfile.ZipFile(dest, 'w') as z:
            z.writestr(name, data); z.writestr(record, out.getvalue())
        return dest

    def test_real_frozen_wheels_all_records_validate(self):
        wheels = list((ROOT / 'package/wheelhouse').glob('*.whl'))
        self.assertEqual(len(wheels), 4)
        for wheel in wheels:
            self.assertGreater(len(installer.wheel_members(wheel)), 1)

    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            wheel = self.wheel(Path(tmp), '../outside.py', b'no')
            with self.assertRaisesRegex(RuntimeError, 'WHEEL_UNSUPPORTED_PATH'):
                installer.wheel_members(wheel)

    def test_tampered_record_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            wheel = self.wheel(Path(tmp), 'inside.py', b'no', wrong=True)
            with self.assertRaisesRegex(RuntimeError, 'WHEEL_RECORD_HASH'):
                installer.wheel_members(wheel)

    def test_extra_unrecorded_member_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            wheel = self.wheel(Path(tmp), 'inside.py', b'no')
            with zipfile.ZipFile(wheel, 'a') as z: z.writestr('surprise.py', b'no')
            with self.assertRaisesRegex(RuntimeError, 'WHEEL_RECORD_FILE_SET'):
                installer.wheel_members(wheel)


class ContractTests(unittest.TestCase):
    def test_stage_count_and_fixed_mlp_pairing(self):
        self.assertEqual(len(service.HEAD_STAGES), 11)
        self.assertEqual(len(service.MODULE_STAGES), 3)
        self.assertEqual(service.MODULE_STAGES, ('M_MLP_QUERY_BCE', 'M_TabM', 'M_LightGBM'))
        self.assertEqual(len([s for s in service.STAGES if s.startswith('T_')]), 9)

    def test_original_contract_byte_identity_and_registration(self):
        old = ROOT.parent / 'modern_head_comparison_v1r1_20261018/bundle/experiment_contract.json'
        self.assertEqual(p.sha(old), p.sha(ROOT / 'package/experiment_contract.json'))
        reg = p.read(ROOT / 'package/supplementary_registration.json')
        self.assertEqual(reg['paired_families'], list(a.FAMILIES))
        self.assertTrue(reg['head_scientific_FAIL_does_not_block_modules'])
        self.assertFalse(reg['target_calibration'])

    def test_scientific_fail_does_not_block_modules(self):
        # Scientific decisions may all be negative. Integrity, completion and
        # predeclared matrix remain the only head->module execution conditions.
        digest = p.sha(ROOT / 'package/supplementary_registration.json')
        states = {
            'HEADS_COMPLETE.json': dict(status='COMPLETE', config_digest='cfg', registration_sha256=digest,
                                       head_seal_sha256='seal', decision_sha256='decision'),
            'decision.json': dict(automatic_promotion=False, selected_family=None,
                                  onboarding_families=list(a.FAMILIES),
                                  families={f: {'core_capability_pass': False} for f in a.FAMILIES})}
        c = mock.Mock()
        c.read.side_effect = lambda path: states[Path(path).name]
        c.digest.return_value = 'cfg'; c.require.side_effect = p.require
        result = a.verified_heads({'run': str(ROOT / 'dummy')}, {'c': c, 'contract': {}})
        self.assertEqual(result.name, 'heads'); c.verify.assert_called_once()

    def test_incomplete_heads_block_modules(self):
        states = {'status': 'RUNNING', 'config_digest': 'cfg', 'registration_sha256': ''}
        c = mock.Mock(); c.read.return_value = states; c.digest.return_value = 'cfg'; c.require.side_effect = p.require
        with self.assertRaisesRegex(RuntimeError, 'HEADS_COMPLETE_REQUIRED'):
            a.verified_heads({'run': str(ROOT / 'dummy')}, {'c': c, 'contract': {}})

    def test_output_inside_current_cache_rejected(self):
        cfg = p.read(ROOT / 'package/config.json')
        cfg['run'] = cfg['source_config']['cache'] + '/bad-output'
        with self.assertRaisesRegex(RuntimeError, 'INPUT_OUTPUT_OVERLAP'):
            service.scope(cfg)


if __name__ == '__main__': unittest.main()
