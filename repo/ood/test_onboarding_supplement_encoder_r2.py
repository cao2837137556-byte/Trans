"""Failure boundaries for a frozen-UID supplement merge, no mock E3 claims."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import nullcontext

import numpy as np
import onboarding_supplement_encoder_r2 as enc


def rows(path, value):
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        for r in value:
            f.write(json.dumps(r)+'\n')


class EncodingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'package'
        self.out = Path(self.temp.name)/'out'
        self.root.mkdir()
        self.out.mkdir()
        self.q = np.arange(42, dtype=np.float32).reshape(3, 14)
        self.e = np.arange(2304, dtype=np.float32).reshape(3, 768)
        rows(self.root/'rows.jsonl.gz', [dict(uid=x) for x in ('b', 'a', 'c')])
        np.savez(self.root/'q.npz', uid=['a', 'b', 'c'], q14=self.q)
        np.savez(self.root/'old.npz', uid=['c', 'a'], e3=self.e[[2, 0]], q14=self.q[[2, 0]])
        np.savez(self.out/'new.npz', uid=['b'], e3=self.e[[1]], q14=self.q[[1]])
        self.spec = dict(name='X', metadata='rows.jsonl.gz', q14='q.npz',
                         existing_bank='old.npz', supplement_dataset='new')

    def tearDown(self):
        self.temp.cleanup()

    def test_merge_joins_shuffled_uid_and_preserves_existing_bytes(self):
        enc.merge_bank(self.root, self.out, self.spec)
        with np.load(self.out/'banks/X/bank.npz') as result:
            self.assertEqual(result['uid'].tolist(), ['b', 'a', 'c'])
            self.assertEqual(result['e3'].tobytes(), self.e[[1, 0, 2]].tobytes())
            self.assertEqual(result['q14'].tobytes(), self.q[[1, 0, 2]].tobytes())

    def test_missing_frozen_uid_stops(self):
        np.savez(self.out/'new.npz', uid=np.array([], dtype='<U64'),
                 e3=np.empty((0, 768), dtype=np.float32), q14=np.empty((0, 14), dtype=np.float32))
        with self.assertRaisesRegex(RuntimeError, 'FROZEN_BANK_UID_COVERAGE'):
            enc.merge_bank(self.root, self.out, self.spec)

    def test_overlap_cannot_replace_existing(self):
        np.savez(self.out/'new.npz', uid=['a'], e3=self.e[[0]], q14=self.q[[0]])
        with self.assertRaisesRegex(RuntimeError, 'EXISTING_SUPPLEMENT_UID_OVERLAP'):
            enc.merge_bank(self.root, self.out, self.spec)

    def test_q14_mismatch_stops(self):
        np.savez(self.out/'new.npz', uid=['b'], e3=self.e[[1]], q14=self.q[[1]]+1)
        with self.assertRaisesRegex(RuntimeError, 'MERGE_Q14_IDENTITY'):
            enc.merge_bank(self.root, self.out, self.spec)

    def test_duplicate_metadata_stops(self):
        rows(self.root/'rows.jsonl.gz', [dict(uid='a'), dict(uid='a')])
        with self.assertRaisesRegex(RuntimeError, 'METADATA_DUPLICATE_UID'):
            enc.load_dataset(self.root, self.spec)

    def test_duplicate_q14_uid_stops(self):
        np.savez(self.root/'q.npz', uid=['a', 'a', 'c'], q14=self.q)
        with self.assertRaisesRegex(RuntimeError, 'Q14_SCHEMA'):
            enc.load_dataset(self.root, self.spec)

    def test_extra_uid_stops(self):
        np.savez(self.out/'new.npz', uid=['z'], e3=self.e[[1]], q14=self.q[[1]])
        with self.assertRaisesRegex(RuntimeError, 'MERGE_Q14_IDENTITY'):
            enc.merge_bank(self.root, self.out, self.spec)

    def test_nan_feature_stops(self):
        values = self.e[[1]].copy()
        values[0, 0] = np.nan
        np.savez(self.out/'new.npz', uid=['b'], e3=values, q14=self.q[[1]])
        with self.assertRaisesRegex(RuntimeError, 'MERGE_E3_SCHEMA'):
            enc.merge_bank(self.root, self.out, self.spec)

    def test_path_escape_stops(self):
        with self.assertRaisesRegex(RuntimeError, 'PACKAGE_PATH_ESCAPE'):
            enc.checked_file(self.root, '../out')

    def test_approval_must_bind_package_scope_and_explicit_user(self):
        valid = dict(package_sha256='abc', scope='SUPPLEMENT_E3_ONLY', user_authorized=True)
        enc.validate_approval(valid, 'abc')
        for key, value in (('package_sha256', 'wrong'), ('scope', 'TRAIN'), ('user_authorized', False)):
            with self.subTest(key=key):
                changed = dict(valid, **{key: value})
                with self.assertRaisesRegex(RuntimeError, 'APPROVAL_SCOPE_OR_IDENTITY'):
                    enc.validate_approval(changed, 'abc')

    def test_manifest_mutation_and_extra_file_stop(self):
        (self.root/'nested').mkdir()
        (self.root/'nested/SHA256SUMS').write_text('a sealed nested receipt\n')
        paths = sorted(p for p in self.root.rglob('*') if p.is_file())
        (self.root/'SHA256SUMS').write_text(''.join(enc.sha(p)+'  '+p.relative_to(self.root).as_posix()+'\n' for p in paths))
        enc.verify_package(self.root)
        (self.root/'surprise').write_text('x')
        with self.assertRaisesRegex(RuntimeError, 'PACKAGE_MEMBERS_CHANGED'):
            enc.verify_package(self.root)
        (self.root/'surprise').unlink()
        (self.root/'old.npz').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'PACKAGE_SHA'):
            enc.verify_package(self.root)

    def test_resource_stat_ignores_atomic_rename_race(self):
        def vanished(**kwargs):
            raise FileNotFoundError('atomic rename')
        entry = SimpleNamespace(is_dir=lambda **kw:False, is_file=lambda **kw:True,
                                stat=vanished, name='vanishing.tmp')
        with patch.object(enc.os, 'scandir', return_value=nullcontext(iter([entry]))):
            self.assertEqual(enc.output_bytes(self.out),0)

    def test_concurrent_atomic_status_writers_are_serialized(self):
        failures = []
        def writer(k):
            try:
                for i in range(25):
                    enc.write_json(self.out/'status.json', dict(worker=k, done=i))
            except BaseException as exc:
                failures.append(repr(exc))
        threads = [threading.Thread(target=writer, args=(k,)) for k in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(json.loads((self.out/'status.json').read_text())['done'], 24)

    def test_original104_one_bit_mismatch_prevents_all_supplement_forwards(self):
        # Exercise main's actual ordering/gate, not a copy of the gate formula.
        import legacy_unsw_archival_runtime_v1 as runtime
        import constrained_onboarding_reference_v2 as reference
        import continuous_features_v3 as features
        original_uids = [str(i) for i in range(104)]
        np.savez(self.root/'original.npz', uid=original_uids,
                 e3=np.zeros((104, 768), np.float32), q14=np.zeros((104, 14), np.float32))
        (self.root/'runtime/vendor/netFound-base').mkdir(parents=True)
        checkpoint = Path(self.temp.name)/'checkpoint'
        checkpoint.write_bytes(b'fixture')
        config = dict(datasets=[dict(name='ORIGINAL104', original104_check=True, expected_bank='original.npz'),
                                dict(name='SUPPLEMENT')], production_runtime_versions={},
                      benchmark_rows_per_dataset=16,
                      limits=dict(memory_gib=8, output_gib=1, min_free_gib=0, encoding_wall_seconds=120))
        (self.root/'config.json').write_text(json.dumps(config))
        approval = Path(self.temp.name)/'approval.json'
        approval.write_text(json.dumps(dict(package_sha256='fixture', scope='SUPPLEMENT_E3_ONLY', user_authorized=True)))
        forward_is_original = []
        def fake_forward(model, batches, device):
            examples = batches[0]['examples']
            forward_is_original.extend(e['original'] for e in examples)
            value = np.zeros((len(examples), 768), np.float32)
            if len(forward_is_original) == len(examples):
                value[0, 0] = np.nextafter(np.float32(0), np.float32(1))
            return value
        embed = SimpleNamespace(core=SimpleNamespace(e3_forward_batches=fake_forward))
        def spool(root, spec, db, tokenizer, progress):
            ids = original_uids if spec['name'] == 'ORIGINAL104' else ['new']
            data = [dict(uid=u) for u in ids]
            for uid in ids:
                db.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)', (spec['name'], uid, 6, 13, 1,
                    json.dumps(dict(original=spec['name'] == 'ORIGINAL104'))))
            db.commit()
            return data, {r['uid']:r for r in data}, {u:np.zeros(14,np.float32) for u in ids}
        output = Path(self.temp.name)/'control_flow_output'
        with patch.object(enc, 'verify_package', return_value='fixture'), \
             patch.object(enc, 'sha', return_value=enc.CHECKPOINT_SHA), \
             patch.object(enc, 'spool_dataset', side_effect=spool), \
             patch.object(runtime, 'e3_runtime', return_value=(embed,None,None,None,lambda e:dict(examples=e))), \
             patch.object(reference, '_environment', return_value=dict(synthetic_control_flow_test=True)), \
             patch.object(features, 'verify_batch'), patch.object(features, 'tensor_hash', return_value='fixture'):
            with self.assertRaisesRegex(RuntimeError, 'ORIGINAL104_NUMERICAL_IDENTITY_STOP'):
                enc.main(['--package',str(self.root),'--checkpoint',str(checkpoint),'--output',str(output),
                          '--mode','encode','--approval-file',str(approval)])
        self.assertEqual(len(forward_is_original), 104)
        self.assertTrue(all(forward_is_original))
        self.assertEqual(json.loads((output/'status.json').read_text())['status'], 'EXCEPTION_STOP')


if __name__ == '__main__':
    unittest.main()
