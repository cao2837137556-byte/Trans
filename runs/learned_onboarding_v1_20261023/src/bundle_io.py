"""Pinned bundle interchange. Target manifests open only during evaluation."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

import common as c


def _file(base, entry):
    c.require(set(entry) >= {'path', 'sha256'}, 'UNPINNED_BUNDLE_FILE')
    path = Path(entry['path'])
    if not path.is_absolute():
        path = base/path
    return c.pin(path, entry['sha256'])


def write_bundle(folder, rows, e3, q14, *, scores=None):
    """Write pinned interchange files from an already verified ordered bundle."""
    folder = Path(folder).resolve()
    c.require(not folder.exists(), 'BUNDLE_OUTPUT_EXISTS')
    rows = list(rows)
    uids = [r['uid'] for r in rows]
    z, q = np.asarray(e3), np.asarray(q14)
    c.require(all(isinstance(uid, str) and uid and '\n' not in uid for uid in uids) and
              len(set(uids)) == len(rows) and
              z.shape == (len(rows), 768) and q.shape == (len(rows), 14) and
              z.dtype.kind == q.dtype.kind == 'f' and
              np.isfinite(z).all() and np.isfinite(q).all() and
              np.all((q >= 0) & (q <= 1)), 'BUNDLE_EXPORT_SCHEMA')
    x = None if scores is None else np.asarray(scores)
    if x is not None:
        c.require(x.shape == (len(rows),) and x.dtype.kind == 'f' and
                  np.isfinite(x).all(), 'BUNDLE_EXPORT_SCORE')
    folder.mkdir(parents=True)
    with gzip.open(folder/'rows.jsonl.gz', 'wt', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
    np.save(folder/'e3.npy', z)
    np.save(folder/'q14.npy', q)
    for name in ('feature_uids.txt', 'q_uids.txt'):
        (folder/name).write_text(''.join(uid+'\n' for uid in uids), encoding='utf-8')
    result = {name: dict(path=str(folder/file), sha256=c.sha(folder/file))
              for name, file in [('rows', 'rows.jsonl.gz'), ('e3', 'e3.npy'),
                                 ('q14', 'q14.npy'),
                                 ('feature_uids', 'feature_uids.txt'),
                                 ('q_uids', 'q_uids.txt')]}
    if x is not None:
        np.save(folder/'scores.npy', x)
        result['scores'] = dict(path=str(folder/'scores.npy'),
                                sha256=c.sha(folder/'scores.npy'))
        result['score_head'] = 'QUERY_TAIL_27'
        result['ordered_uid_sha256'] = c.uid_hash(uids, ordered=True)
    return result


def _rows_file(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream]


def _producer_uid_digest(uids):
    # continuous_input_v3.digest, used by encode_selected's selected_uid_sha256.
    body = json.dumps(list(uids), separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


def _sha_manifest(path):
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        c.require(name not in result and len(digest) == 64 and
                  all(char in '0123456789abcdef' for char in digest.lower()),
                  'HISTORICAL_PARENT_MANIFEST_SCHEMA')
        result[name] = digest.lower()
    return result


def _same_bundle(export_rows, export_e3, export_q14, export_uids, loaded):
    expected = [r['uid'] for r in export_rows]
    c.require(export_rows == loaded['rows'] and export_uids == expected ==
              loaded['feature_uids'] == loaded['q_uids'] and
              export_e3.shape == loaded['e3'].shape and
              export_q14.shape == loaded['q14'].shape and
              export_e3.tobytes(order='C') == loaded['e3'].tobytes(order='C') and
              export_q14.tobytes(order='C') == loaded['q14'].tobytes(order='C') and
              export_e3.dtype == loaded['e3'].dtype and
              export_q14.dtype == loaded['q14'].dtype,
              'BANK_BUNDLE_PRODUCER_MISMATCH')


def _exported_bank(folder, receipt, loaded, *, metadata_field, array_field):
    rows = _rows_file(c.pin(folder/'references.jsonl.gz', receipt[metadata_field]))
    with np.load(c.pin(folder/'bank.npz', receipt[array_field]),
                 allow_pickle=False) as saved:
        c.require(set(saved.files) >= {'uid', 'e3', 'q14'}, 'BANK_ARRAY_KEYS')
        uids = saved['uid'].tolist()
        e3, q14 = saved['e3'], saved['q14']
        c.require(e3.shape == (len(rows), 768) and
                  q14.shape == (len(rows), 14) and
                  e3.dtype == q14.dtype == np.float32 and
                  np.isfinite(e3).all() and np.isfinite(q14).all(),
                  'BANK_ARRAY_SCHEMA')
        _same_bundle(rows, e3, q14, uids, loaded)
        return rows, uids, e3.copy(), q14.copy()


def _modern_producer(base, policy, declaration, loaded, normalizer_sha256):
    receipt_path = _file(base, declaration['producer_receipt'])
    folder = receipt_path.parent
    record = c.read(receipt_path)
    c.require(receipt_path.name == 'receipt.json' and
              declaration['producer_receipt_sha256'] ==
              declaration['producer_receipt']['sha256'], 'BANK_PRODUCER_IDENTITY')
    c.require(record.get('status') == 'COMPLETE' and
              record.get('synthetic_only') is False and
              record.get('real_recent_features') is True and
              record.get('complete_candidate_census') is True and
              record.get('policy') == policy and
              record.get('input_version') ==
              'continuous-input-core-repair-design-v3-20260929' and
              record.get('input_readout') == 'RECENT_CURRENT_INCLUSIVE' and
              record.get('normalizer_sha256') == normalizer_sha256 and
              record.get('e3_dimensions') == 768 and
              record.get('q14_dimensions') == 14 and
              record.get('model_training') is False and
              record.get('classifier_scoring') is False,
              'BANK_PRODUCER_CONTRACT')
    c.pin(folder/'tensor_receipts.jsonl.gz', record['tensor_receipts_sha256'])
    c.pin(folder/'environment.json', record['environment_sha256'])
    rows, uids, _, _ = _exported_bank(folder, record, loaded,
        metadata_field='metadata_sha256', array_field='bank_npz_sha256')
    c.require(len(rows) == record['rows'] and len(set(uids)) == len(uids) and
              _producer_uid_digest(uids) == record['selected_uid_sha256'] and
              all(r['use'] == 'REFERENCE' and r['label'] == 0 for r in rows),
              'BANK_METADATA_IDENTITY')
    tensors = _rows_file(folder/'tensor_receipts.jsonl.gz')
    c.require(len(tensors) == len(rows) and
              {(r['uid'], r['slot']) for r in tensors} ==
              {(uid, i) for i, uid in enumerate(uids)}, 'BANK_TENSOR_RECEIPT_JOIN')
    return record


def _historical_producer(base, pool, partition, declaration, loaded,
                         normalizer_sha256, source_binding):
    receipt_path = _file(base, declaration['producer_receipt'])
    folder = receipt_path.parent
    record = c.read(receipt_path)
    c.require(record.get('schema') == 'learned-onboarding-historical-bank-export-v1' and
              record.get('status') == 'SEALED' and
              record.get('synthetic_only') is False and
              record.get('pool') == pool and
              record.get('partition') == partition and
              record.get('policy') == 'OLD_BANK' and
              record.get('source_method') == 'parent_cache_uid_slot_replay' and
              record.get('normalizer_sha256') == normalizer_sha256 and
              declaration['producer_receipt_sha256'] ==
              declaration['producer_receipt']['sha256'],
              'HISTORICAL_BANK_PRODUCER_CONTRACT')
    source = record.get('source_assets', {})
    required = ('parent_cache_binding', 'parent_input_manifest',
                'parent_feature_manifest', 'parent_normalizer_manifest',
                'parent_metadata', 'parent_e3', 'parent_q14',
                'parent_spool', 'normalizer', 'lineage_map')
    c.require(set(source) == set(required), 'HISTORICAL_SOURCE_ASSETS')
    paths = {name: _file(folder, source[name]) for name in required}
    c.require(source['normalizer']['sha256'] == normalizer_sha256,
              'HISTORICAL_NORMALIZER_BINDING')
    binding = c.read(paths['parent_cache_binding'])
    marker = binding.get('marker', {})
    c.require(marker.get('lineage') == c.LINEAGE and
              marker.get('original_input_manifest_sha256') ==
              source['parent_input_manifest']['sha256'] and
              marker.get('feature_manifest_sha256') ==
              source['parent_feature_manifest']['sha256'] and
              marker.get('normalizer_manifest_sha256') ==
              source['parent_normalizer_manifest']['sha256'] and
              marker.get('spool_sha256') == source['parent_spool']['sha256'] and
              source_binding.get('input_manifest_sha256') ==
              marker.get('original_input_manifest_sha256') and
              source_binding.get('feature_manifest_sha256') ==
              marker.get('feature_manifest_sha256') and
              source_binding.get('spool_sha256') == marker.get('spool_sha256') and
              source_binding.get('normalizer_sha256') == normalizer_sha256,
              'HISTORICAL_PARENT_CACHE_BINDING')
    role = 'SOURCE_REFS' if pool == 'CIC_DEV' else 'UNSW_REFS'
    c.require(_sha_manifest(paths['parent_input_manifest']).get(role+'.jsonl.gz') ==
              source['parent_metadata']['sha256'] and
              _sha_manifest(paths['parent_feature_manifest']).get(role+'.npy') ==
              source['parent_e3']['sha256'] and
              _sha_manifest(paths['parent_normalizer_manifest']).get('RECENT.npz') ==
              source['normalizer']['sha256'],
              'HISTORICAL_PARENT_MANIFEST_BINDING')
    rows, uids, e3, q14 = _exported_bank(folder, record, loaded,
        metadata_field='metadata_sha256', array_field='bank_npz_sha256')
    c.require(len(rows) == record.get('rows') and
              c.uid_hash(uids, ordered=True) == record.get('ordered_uid_sha256') and
              all(r['partition'] == partition and r['use'] == 'REFERENCE' and
                  r['label'] == 0 for r in rows), 'HISTORICAL_BANK_IDENTITY')
    lineage = _rows_file(paths['lineage_map'])
    c.require(len(lineage) == len(rows) and
              [r['uid'] for r in lineage] == uids, 'HISTORICAL_LINEAGE_UIDS')
    parent_z = np.load(paths['parent_e3'], mmap_mode='r', allow_pickle=False)
    parent_q = np.load(paths['parent_q14'], mmap_mode='r', allow_pickle=False)
    c.require(parent_z.ndim == 2 and parent_z.shape[1] >= 768 and
              parent_q.ndim == 2 and parent_q.shape[1] == 14,
              'HISTORICAL_PARENT_ARRAY_SCHEMA')
    needed = set()
    for i, item in enumerate(lineage):
        slot = item.get('parent_slot')
        c.require(type(slot) is int and slot >= 0 and
                  slot < len(parent_z) and slot < len(parent_q),
                  'HISTORICAL_LINEAGE_SLOT')
        needed.add(slot)
        c.require(np.asarray(parent_z[slot, :768]).tobytes(order='C') ==
                  e3[i].tobytes(order='C') and
                  np.asarray(parent_q[slot]).tobytes(order='C') ==
                  q14[i].tobytes(order='C'),
                  'HISTORICAL_PARENT_FEATURE_MISMATCH')
    metadata = {}
    opener = gzip.open if paths['parent_metadata'].suffix == '.gz' else open
    with opener(paths['parent_metadata'], 'rt', encoding='utf-8-sig') as stream:
        for slot, line in enumerate(stream):
            if slot in needed:
                metadata[slot] = json.loads(line)
    for row, item in zip(rows, lineage):
        parent = metadata.get(item['parent_slot'])
        c.require(parent is not None and all(parent.get(k) == row.get(k) for k in
            ('uid', 'device', 'partition', 'protocol', 'component_id',
             'capture_id', 'frame', 'timestamp', 'label')),
             'HISTORICAL_PARENT_METADATA_MISMATCH')
    old_module_dir = Path(__file__).resolve().parents[3] / 'repo' / 'ood'
    if str(old_module_dir) not in sys.path:
        sys.path.insert(0, str(old_module_dir))
    from constrained_onboarding_reference_v2 import extract_old_bank_q14
    replay_rows = [dict(row, parent_slot=item['parent_slot'])
                   for row, item in zip(rows, lineage)]
    extracted_q14 = extract_old_bank_q14(paths['parent_spool'], replay_rows,
                                         marker['spool_sha256'])
    c.require(extracted_q14.tobytes(order='C') == q14.tobytes(order='C') and
              extracted_q14.tobytes(order='C') == np.asarray(parent_q[
                  [item['parent_slot'] for item in lineage]]).tobytes(order='C'),
              'HISTORICAL_SPOOL_Q14_MISMATCH')
    return record


def load_bundle(base, declaration, *, query=False):
    """Every row/feature/UID artifact is independently hash-bound."""
    path = _file(base, declaration['rows'])
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as f:
        rows = [__import__('json').loads(line) for line in f]
    z = np.load(_file(base, declaration['e3']), mmap_mode='r', allow_pickle=False)
    q = np.load(_file(base, declaration['q14']), mmap_mode='r', allow_pickle=False)
    with _file(base, declaration['feature_uids']).open(encoding='utf-8') as f:
        feature_uids = [line.rstrip('\n') for line in f]
    with _file(base, declaration['q_uids']).open(encoding='utf-8') as f:
        q_uids = [line.rstrip('\n') for line in f]
    uids = [r['uid'] for r in rows]
    c.require(feature_uids == uids == q_uids and len(set(uids)) == len(uids), 'BUNDLE_UID_JOIN')
    c.require(z.shape == (len(rows), 768) and q.shape == (len(rows), 14), 'BUNDLE_DIMENSIONS')
    result = dict(rows=rows, e3=z, q14=q, feature_uids=feature_uids, q_uids=q_uids)
    if query:
        scores = np.load(_file(base, declaration['scores']), mmap_mode='r', allow_pickle=False)
        c.require(scores.shape == (len(rows),) and np.isfinite(scores).all(), 'BUNDLE_SCORE_SCHEMA')
        c.require(declaration['score_head'] == 'QUERY_TAIL_27', 'TARGET_WRONG_HEAD')
        c.require(declaration['ordered_uid_sha256'] == c.uid_hash(uids, ordered=True), 'TARGET_SCORE_UIDS')
        # The original pinned score file remains the input identity. Every
        # downstream comparator uses this one float64 transport baseline.
        result['scores'] = np.asarray(scores, dtype=np.float64)
        result['score_transport_dtype'] = 'float64'
    return result


def load_targets(manifest_path, *, expected_sha256, source_binding_digest, cut,
                 normalizer_sha256, source_binding):
    """Called by the sealed evaluation stage, never by source fitting."""
    path = c.pin(manifest_path, expected_sha256)
    manifest = c.read(path)
    c.require(manifest['schema'] == 'learned-onboarding-target-inputs-v1' and
              manifest['spec_sha256'] == c.SPEC_SHA256 and
              manifest['status'] == 'SEALED' and manifest['synthetic_only'] is False,
              'TARGET_MANIFEST_SCOPE')
    c.require(manifest['source_binding_digest'] == source_binding_digest and
              manifest['cut'] == cut and manifest['lineage'] == c.LINEAGE and
              manifest['parent_parity'] == c.PARENT_PARITY, 'TARGET_HEAD_BINDING')
    c.require(isinstance(normalizer_sha256, str) and len(normalizer_sha256) == 64 and
              manifest.get('normalizer_sha256') == normalizer_sha256 and
              c.digest(source_binding) == source_binding_digest,
              'TARGET_NORMALIZER_BINDING')
    c.require(set(manifest['pools']) == {'CIC_DEV', 'UNSW_DEV'}, 'TARGET_POOLS')
    targets = {}
    for pool, declaration in manifest['pools'].items():
        value = load_bundle(path.parent, declaration['query'], query=True)
        partition = 'DEV' if pool == 'CIC_DEV' else 'EXTERNAL_ARCHIVAL_EVALUATION'
        c.require(all(r['partition'] == partition and r['use'] != 'REFERENCE' for r in value['rows']),
                  'TARGET_QUERY_ROLE')
        c.require(set(declaration['banks']) == {'OLD_BANK', 'B0', 'B1', 'B2'}, 'TARGET_BANKS')
        banks = {}
        for policy, bank_decl in declaration['banks'].items():
            banks[policy] = load_bundle(path.parent, bank_decl)
            c.require(all(r['partition'] == partition and r['use'] == 'REFERENCE' and r['label'] == 0
                          for r in banks[policy]['rows']), 'TARGET_REFERENCE_ROLE')
            kind = bank_decl.get('producer_kind')
            if policy == 'OLD_BANK':
                c.require(kind == 'historical-old-bank-v1', 'HISTORICAL_PRODUCER_KIND')
                _historical_producer(path.parent, pool, partition, bank_decl,
                                     banks[policy], normalizer_sha256,
                                     source_binding)
            else:
                c.require(kind == 'encoded-selected-v2', 'MODERN_PRODUCER_KIND')
                _modern_producer(path.parent, policy, bank_decl,
                                 banks[policy], normalizer_sha256)
        value['banks'] = banks
        targets[pool] = value
    return targets
