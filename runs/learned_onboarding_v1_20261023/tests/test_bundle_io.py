import gzip
import gc
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import bundle_io as b
import common as c


def rows(partition='DEV'):
    return [dict(uid='ref-'+str(i), partition=partition, device='camera',
        protocol=6, use='REFERENCE', label=0, component_id='component-'+str(i),
        capture_id='capture-'+str(i), frame=1, timestamp=1., reference_end=10.)
        for i in range(2)]


def arrays(count=2):
    z = np.zeros((count, 768), np.float32)
    z[:, 0] = 1.
    q = np.zeros((count, 14), np.float32)
    if count > 1:
        q[1, 0] = .2
    return z, q


def write_rows(path, values):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'wt', encoding='utf-8') as stream:
        for value in values:
            stream.write(json.dumps(value, sort_keys=True)+'\n')


def entry(path):
    return dict(path=str(path), sha256=c.sha(path))


def producer_payload(folder, items, q14=None):
    folder.mkdir(parents=True)
    z, q = arrays(len(items))
    if q14 is not None:
        q = q14
    write_rows(folder/'references.jsonl.gz', items)
    np.savez(folder/'bank.npz', uid=np.array([r['uid'] for r in items], dtype='<U64'),
             e3=z, q14=q)
    return dict(rows=items, e3=z.copy(), q14=q.copy(),
                feature_uids=[r['uid'] for r in items],
                q_uids=[r['uid'] for r in items])


class ProducerTests(unittest.TestCase):
    def test_modern_producer_exact_payload_and_negative_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'encoded'
            values = producer_payload(folder, rows())
            write_rows(folder/'tensor_receipts.jsonl.gz',
                       [dict(uid=r['uid'], slot=i) for i, r in enumerate(values['rows'])])
            c.write(folder/'environment.json', dict(runtime='synthetic-fixture'))
            normalizer_sha = 'a'*64
            receipt = dict(status='COMPLETE', synthetic_only=False,
                real_recent_features=True, complete_candidate_census=True,
                policy='B2', input_version='continuous-input-core-repair-design-v3-20260929',
                input_readout='RECENT_CURRENT_INCLUSIVE',
                normalizer_sha256=normalizer_sha, e3_dimensions=768,
                q14_dimensions=14, model_training=False, classifier_scoring=False,
                rows=2, selected_uid_sha256=b._producer_uid_digest(values['feature_uids']),
                bank_npz_sha256=c.sha(folder/'bank.npz'),
                metadata_sha256=c.sha(folder/'references.jsonl.gz'),
                tensor_receipts_sha256=c.sha(folder/'tensor_receipts.jsonl.gz'),
                environment_sha256=c.sha(folder/'environment.json'))
            c.write(folder/'receipt.json', receipt)
            declaration = dict(producer_receipt=entry(folder/'receipt.json'),
                               producer_receipt_sha256=c.sha(folder/'receipt.json'))
            b._modern_producer(folder, 'B2', declaration, values, normalizer_sha)
            exported = b.write_bundle(Path(tmp)/'bundle', values['rows'],
                                      values['e3'], values['q14'])
            loaded = b.load_bundle(Path(tmp), exported)
            b._modern_producer(folder, 'B2', declaration, loaded, normalizer_sha)
            del loaded
            gc.collect()
            changed = dict(values, q14=values['q14'].copy())
            changed['q14'][0, 0] = .3
            with self.assertRaisesRegex(ValueError, 'BANK_BUNDLE_PRODUCER_MISMATCH'):
                b._modern_producer(folder, 'B2', declaration, changed, normalizer_sha)
            signed_zero = dict(values, e3=values['e3'].copy())
            signed_zero['e3'][0, 2] = np.float32(-0.)
            self.assertTrue(np.array_equal(signed_zero['e3'], values['e3']))
            with self.assertRaisesRegex(ValueError, 'BANK_BUNDLE_PRODUCER_MISMATCH'):
                b._modern_producer(folder, 'B2', declaration, signed_zero, normalizer_sha)
            with self.assertRaisesRegex(ValueError, 'BANK_PRODUCER_CONTRACT'):
                b._modern_producer(folder, 'B1', declaration, values, normalizer_sha)
            with self.assertRaisesRegex(ValueError, 'BANK_PRODUCER_CONTRACT'):
                b._modern_producer(folder, 'B2', declaration, values, 'b'*64)
            receipt['synthetic_only'] = True
            c.write(folder/'receipt.json', receipt)
            declaration['producer_receipt'] = entry(folder/'receipt.json')
            declaration['producer_receipt_sha256'] = c.sha(folder/'receipt.json')
            with self.assertRaisesRegex(ValueError, 'BANK_PRODUCER_CONTRACT'):
                b._modern_producer(folder, 'B2', declaration, values, normalizer_sha)

    def test_historical_parent_slot_replay_and_missing_lineage(self):
        old_dir = Path(__file__).resolve().parents[3]/'repo'/'ood'
        sys.path.insert(0, str(old_dir))
        from test_constrained_onboarding_reference_v1 import body_row
        from constrained_onboarding_reference_v2 import reference_descriptor
        body, old_row = body_row()
        old_row = dict(old_row, parent_slot=0)
        q14 = reference_descriptor(body, old_row)[0][None, :]
        old_row = json.loads(json.dumps(old_row))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'historical'
            values = producer_payload(folder, [old_row], q14=q14)
            norm = folder/'normalizer.npz'
            np.savez(norm, mean=np.zeros(768), scale=np.ones(768))
            parent_z = folder/'parent_e3.npy'
            parent_q = folder/'parent_q14.npy'
            np.save(parent_z, values['e3'])
            np.save(parent_q, values['q14'])
            metadata = folder/'parent_metadata.jsonl.gz'
            spool = folder/'snapshots.sqlite'
            lineage = folder/'lineage_map.jsonl.gz'
            write_rows(metadata, values['rows'])
            db = sqlite3.connect(str(spool))
            db.execute('CREATE TABLE snapshots(uid TEXT PRIMARY KEY,role TEXT,slot INTEGER,protocol INTEGER,body TEXT)')
            db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)',
                       (old_row['uid'], 'SOURCE_REFS', 0, 6, json.dumps(body)))
            db.commit(); db.close()
            write_rows(lineage, [dict(uid=old_row['uid'], parent_slot=0)])
            manifests = {}
            for name, member, target in (
                    ('input', 'SOURCE_REFS.jsonl.gz', metadata),
                    ('feature', 'SOURCE_REFS.npy', parent_z),
                    ('normalizer', 'RECENT.npz', norm)):
                path = folder/(name+'-SHA256SUMS')
                path.write_text(c.sha(target)+'  '+member+'\n', encoding='utf-8')
                manifests[name] = path
            c.write(folder/'parent_cache_binding.json', dict(marker=dict(
                lineage=c.LINEAGE,
                original_input_manifest_sha256=c.sha(manifests['input']),
                feature_manifest_sha256=c.sha(manifests['feature']),
                normalizer_manifest_sha256=c.sha(manifests['normalizer']),
                spool_sha256=c.sha(spool))))
            assets = dict(parent_cache_binding=entry(folder/'parent_cache_binding.json'),
                parent_input_manifest=entry(manifests['input']),
                parent_feature_manifest=entry(manifests['feature']),
                parent_normalizer_manifest=entry(manifests['normalizer']),
                parent_metadata=entry(metadata), parent_e3=entry(parent_z),
                parent_q14=entry(parent_q), parent_spool=entry(spool),
                normalizer=entry(norm), lineage_map=entry(lineage))
            source_binding = dict(input_manifest_sha256=c.sha(manifests['input']),
                feature_manifest_sha256=c.sha(manifests['feature']),
                spool_sha256=c.sha(spool), normalizer_sha256=c.sha(norm))
            receipt = dict(schema='learned-onboarding-historical-bank-export-v1',
                status='SEALED', synthetic_only=False, policy='OLD_BANK',
                pool='CIC_DEV', partition='DEV',
                source_method='parent_cache_uid_slot_replay',
                normalizer_sha256=c.sha(norm), source_assets=assets,
                rows=1, ordered_uid_sha256=c.uid_hash(values['feature_uids'], ordered=True),
                bank_npz_sha256=c.sha(folder/'bank.npz'),
                metadata_sha256=c.sha(folder/'references.jsonl.gz'))
            c.write(folder/'receipt.json', receipt)
            declaration = dict(producer_receipt=entry(folder/'receipt.json'),
                               producer_receipt_sha256=c.sha(folder/'receipt.json'))
            b._historical_producer(folder, 'CIC_DEV', 'DEV', declaration,
                                   values, c.sha(norm), source_binding)
            with self.assertRaisesRegex(ValueError, 'HISTORICAL_PARENT_CACHE_BINDING'):
                b._historical_producer(folder, 'CIC_DEV', 'DEV', declaration,
                                       values, c.sha(norm),
                                       dict(source_binding, spool_sha256='f'*64))
            altered = q14.copy()
            altered[0, 0] = 0.123
            np.save(parent_q, altered)
            np.savez(folder/'bank.npz', uid=np.array(values['feature_uids'], dtype='<U64'),
                     e3=values['e3'], q14=altered)
            values['q14'] = altered
            assets['parent_q14'] = entry(parent_q)
            receipt['source_assets'] = assets
            receipt['bank_npz_sha256'] = c.sha(folder/'bank.npz')
            c.write(folder/'receipt.json', receipt)
            declaration['producer_receipt'] = entry(folder/'receipt.json')
            declaration['producer_receipt_sha256'] = c.sha(folder/'receipt.json')
            with self.assertRaisesRegex(ValueError, 'HISTORICAL_SPOOL_Q14_MISMATCH'):
                b._historical_producer(folder, 'CIC_DEV', 'DEV', declaration,
                                       values, c.sha(norm), source_binding)
            removed = dict(receipt, source_assets={k: v for k, v in assets.items()
                                                   if k != 'parent_spool'})
            c.write(folder/'receipt.json', removed)
            declaration['producer_receipt'] = entry(folder/'receipt.json')
            declaration['producer_receipt_sha256'] = c.sha(folder/'receipt.json')
            with self.assertRaisesRegex(ValueError, 'HISTORICAL_SOURCE_ASSETS'):
                b._historical_producer(folder, 'CIC_DEV', 'DEV', declaration,
                                       values, c.sha(norm), source_binding)

    def test_manifest_normalizer_rejected_before_any_target_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'manifest.json'
            c.write(path, dict(schema='learned-onboarding-target-inputs-v1',
                spec_sha256=c.SPEC_SHA256, status='SEALED', synthetic_only=False,
                source_binding_digest=c.digest({}), cut=1., lineage=c.LINEAGE,
                parent_parity=c.PARENT_PARITY, normalizer_sha256='a'*64,
                pools={'CIC_DEV': {}, 'UNSW_DEV': {}}))
            with self.assertRaisesRegex(ValueError, 'TARGET_NORMALIZER_BINDING'):
                b.load_targets(path, expected_sha256=c.sha(path),
                    source_binding_digest=c.digest({}), cut=1.,
                    normalizer_sha256='b'*64, source_binding={})


if __name__ == '__main__':
    unittest.main()
