"""Actual encoded-bank contract: receipt pins payloads, no folder seal emitted."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'package_v2'))
import modern_adapter as a
import package_io as p


def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class BankTests(unittest.TestCase):
    def fixture(self, folder):
        row = dict(uid='physical-1', label=0, use='REFERENCE')
        with gzip.open(folder / 'references.jsonl.gz', 'wt', encoding='utf-8') as stream:
            stream.write(json.dumps(row)+'\n')
        with gzip.open(folder / 'tensor_receipts.jsonl.gz', 'wt', encoding='utf-8') as stream:
            stream.write('{}\n')
        (folder / 'environment.json').write_text('{}')
        np.savez(folder / 'bank.npz', uid=np.asarray(['physical-1']),
                 e3=np.zeros((1,768),np.float32), q14=np.zeros((1,14),np.float32))
        record = dict(input_version='input-version', normalizer_sha256='source-normalizer',
            e3_dimensions=768, q14_dimensions=14, model_training=False, classifier_scoring=False,
            rows=1, selected_uid_sha256=digest(['physical-1']))
        for name, field in (('bank.npz','bank_npz_sha256'),('references.jsonl.gz','metadata_sha256'),
                            ('tensor_receipts.jsonl.gz','tensor_receipts_sha256'),('environment.json','environment_sha256')):
            record[field] = p.sha(folder / name)
        def rows(path):
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                yield from (json.loads(line) for line in stream)
        ctx = dict(c=SimpleNamespace(rows=rows), modules={
            'constrained_onboarding_reference_v2': SimpleNamespace(digest=digest),
            'constrained_onboarding_query_tail_adapter_v2': SimpleNamespace(INPUT_VERSION='input-version')})
        return record, ctx

    def test_valid_bank_needs_no_sha256sums(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder=Path(tmp); record,ctx=self.fixture(folder)
            self.assertFalse((folder/'SHA256SUMS').exists())
            a.verify_encoded_bank(folder,record,'source-normalizer',ctx)

    def test_payload_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder=Path(tmp); record,ctx=self.fixture(folder)
            (folder/'environment.json').write_text('{"changed": true}')
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'):
                a.verify_encoded_bank(folder,record,'source-normalizer',ctx)

    def test_uid_order_mismatch_rejected_even_with_valid_payload_hash(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder=Path(tmp); record,ctx=self.fixture(folder)
            np.savez(folder/'bank.npz',uid=np.asarray(['other']),
                     e3=np.zeros((1,768),np.float32),q14=np.zeros((1,14),np.float32))
            record['bank_npz_sha256']=p.sha(folder/'bank.npz')
            with self.assertRaisesRegex(RuntimeError,'BANK_ARRAY_UID_JOIN'):
                a.verify_encoded_bank(folder,record,'source-normalizer',ctx)

    def test_normalizer_drift_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder=Path(tmp); record,ctx=self.fixture(folder)
            with self.assertRaisesRegex(RuntimeError,'BANK_PRODUCER_CONTRACT'):
                a.verify_encoded_bank(folder,record,'different-normalizer',ctx)


if __name__ == '__main__': unittest.main()
