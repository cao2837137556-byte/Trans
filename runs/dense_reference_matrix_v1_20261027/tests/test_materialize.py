import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE/'src'))
import matrix
import binding
import materialize
from test_matrix import synthetic_manifest


def fixture(root):
    synthetic_manifest(root)
    template = matrix.read(root/'manifest.json')
    template['root'] = 'READONLY_VIEW'
    template['source_cal_result'] = None
    template['source_preparations'] = None
    template['synthetic_only'] = False
    enc, cal = root/'encoding', root/'source_cal'
    enc.mkdir()
    cal.mkdir()
    def save(path, value):
        matrix.write(path, value)
    save(enc/'RESULT.json', dict(status='COMPLETE', mode='encode', package_sha256='package',
        benchmark_features_must_not_be_used_for_production=False, no_training=True, target_evaluation=False))
    save(enc/'ORIGINAL104_PARITY.json', dict(original104_exact_bytes=True, mismatch_count=0))
    save(cal/'RESULT.json', matrix.read(root/'SOURCE_RESULT.json'))
    source_seal = {str((enc/'RESULT.json').resolve()): matrix.sha(enc/'RESULT.json')}
    source_seal.update({str((root/pin['path']).resolve()): pin['sha256'] for pin in template['calibration'].values()})
    for arm in ('R-B2', 'R-DENSE'):
        (cal/arm).mkdir()
        shutil.copyfile(root/(arm+'_PREPARATION.json'), cal/arm/'PREPARATION.json')
        save(cal/arm/'EPS0_PARITY.json', dict(epsilon_zero_full_CAL_same_environment_legacy_bytes_equal=True))
    for pool in template['pools']:
        if pool['mode'] != 'DENSE_MATRIX':
            continue
        bank = pool['dense_bank']
        rr = matrix.Inputs(root).rows(bank['rows'])
        # Supply complete metadata-only frozen-window identities.
        for r in rr:
            r['source_sha256'] = 's'*64
        name = bank['rows']['path']
        import gzip
        with gzip.open(root/name, 'wt', encoding='utf-8') as stream:
            for r in rr:
                stream.write(json.dumps(r)+'\n')
        bank['rows']['sha256'] = matrix.sha(root/name)
        windows = [dict(device=d, partition=rr[0]['partition'], source_sha256='s'*64,
                        capture_id='capture', start=0., end=2., reference_end=2., frame_end=2)
                   for d in ('D1','D2')]
        wrong = binding.freeze_wrong_reference_plan(pool['pool_id'], rr, windows)
        wrong_path = root/(pool['pool_id']+'_wrong.json')
        save(wrong_path, wrong)
        pool['wrong_plan'] = dict(path=wrong_path.name, sha256=matrix.sha(wrong_path))
        pool['wrong_groups'] = wrong['groups']
        pool['windows'] = windows
        selected_uids = [r['uid'] for r in rr]
        bank.update(status='BLOCKED_SUPPLEMENT_ENCODING_REQUIRED', e3=None,
                    expected_rows=len(rr), expected_ordered_uid_sha256=matrix.core._uid_hash(selected_uids))
        target = enc/'banks'/pool['pool_id']
        target.mkdir(parents=True)
        shutil.copyfile(root/name, target/'references.jsonl.gz')
        shutil.copyfile(root/bank['q14']['path'], target/'bank.npz')
        save(target/'receipt.json', dict(status='COMPLETE', rows=len(rr), frozen_selection=True,
            existing_vectors_unchanged=True, reselection=False, bank_sha256=matrix.sha(target/'bank.npz'),
            metadata_sha256=matrix.sha(target/'references.jsonl.gz')))
    source_bank_dir = enc/'banks/SOURCE_REFS'
    source_bank_dir.mkdir(parents=True)
    np.savez(source_bank_dir/'bank.npz', uid=['source1','source2'], e3=np.ones((2,768),dtype=np.float32),
             q14=np.zeros((2,14),dtype=np.float32))
    (source_bank_dir/'references.jsonl.gz').write_bytes(b'SYNTHETIC source metadata hash binding fixture')
    source_bank_sha = matrix.sha(source_bank_dir/'bank.npz')
    source_metadata_sha = matrix.sha(source_bank_dir/'references.jsonl.gz')
    save(source_bank_dir/'receipt.json', dict(status='COMPLETE', frozen_selection=True,reselection=False,
         bank_sha256=source_bank_sha,metadata_sha256=source_metadata_sha))
    source_seal.update({str(source_bank_dir/'bank.npz'):source_bank_sha,
                        str(source_bank_dir/'references.jsonl.gz'):source_metadata_sha})
    save(cal/'INPUT_SEAL.json', source_seal)
    save(root/'template.json', template)
    return root/'template.json', enc, cal, root/'runtime_manifest.json'


class MaterializeTests(unittest.TestCase):
    def test_source_calibration_from_different_frozen_geometry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = fixture(root)
            seal = matrix.read(paths[2]/'INPUT_SEAL.json')
            seal[str(root/'geometry.json')] = '0'*64
            matrix.write(paths[2]/'INPUT_SEAL.json', seal)
            with self.assertRaisesRegex(ValueError, 'SOURCE_CAL_FIXED_PARAMETER_IDENTITY:geometry'):
                materialize.materialize_runtime(*paths, asset_root=root)
            self.assertFalse(paths[3].exists())

    def test_only_derived_pins_filled_original_scientific_metadata_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = fixture(root)
            original = matrix.read(paths[0])
            result = materialize.materialize_runtime(*paths, asset_root=root)
            self.assertFalse(result['full_matrix_ready'])
            self.assertEqual(result['calibration'], original['calibration'])
            self.assertEqual(result['derived_runtime_roots'], [paths[1].as_posix(), paths[2].as_posix()])
            for a, b in zip(original['pools'], result['pools']):
                for name in ('query','b2_bank','windows','wrong_groups','mode'):
                    self.assertEqual(a.get(name), b.get(name))
            self.assertTrue(result['materialization']['frozen_scientific_fields_changed'] is False)
            self.assertEqual(result['source_cal_result']['sha256'], matrix.sha(paths[2]/'RESULT.json'))

    def test_original104_failure_blocks_manifest_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = fixture(root)
            matrix.write(paths[1]/'ORIGINAL104_PARITY.json', dict(original104_exact_bytes=False, mismatch_count=1))
            with self.assertRaisesRegex(ValueError, 'ORIGINAL104_BYTE_GATE'):
                materialize.materialize_runtime(*paths, asset_root=root)
            self.assertFalse(paths[3].exists())

    def test_source_cal_must_bind_exact_encoding_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = fixture(root)
            matrix.write(paths[2]/'INPUT_SEAL.json', {str(paths[1]/'RESULT.json'): '0'*64})
            with self.assertRaisesRegex(ValueError, 'SOURCE_CAL_NOT_BOUND'):
                materialize.materialize_runtime(*paths, asset_root=root)

    def test_derived_roots_are_explicit_and_do_not_allow_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'enc').mkdir()
            (root/'outside.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'OUTSIDE_RUNTIME_ROOTS'):
                materialize._derived(root/'outside.json', (root/'enc',))
            pin = dict(path=str(root/'outside.json'), sha256=matrix.sha(root/'outside.json'), derived_runtime=True)
            with self.assertRaisesRegex(ValueError, 'INPUT_OUTSIDE_ROOT'):
                matrix.Inputs(root/'enc', [root/'enc']).pin(pin)


if __name__ == '__main__':
    unittest.main()
