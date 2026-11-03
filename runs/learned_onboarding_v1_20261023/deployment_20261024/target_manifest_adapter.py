"""Assemble sealed production target inputs after source FIT and CAL.

The accepted cache, head run, and onboarding bank producers are read-only.  All
new interchange artifacts live below a fresh output directory.  No target
query is opened until both source stage seals and their binding are checked.
"""

import argparse
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import traceback

import numpy as np


DEPLOYMENT_ROOT = Path(__file__).resolve().parents[3]
SRC = DEPLOYMENT_ROOT / 'runs/learned_onboarding_v1_20261023/src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import common as c
import bundle_io


DEFAULT_CACHE = Path('/srv/paper04/cache/coupon_resume_20261020_v2')
DEFAULT_HEAD_RUN = Path('/srv/paper04/runs/query_twelve_heads_20261022_v1')
DEFAULT_OLD_RUN = Path('/srv/paper04/runs/onboarding_new_lineage_20261022_v3')
BANKS_MANIFEST_SHA256 = '8149a87ec7814e988bb86c0bb11b918b40d9bde88524ceb7b4057e0ebed7adb0'
QUERY_COMPLETE_SHA256 = 'fd9b46e510c0937d8c151aa80dd3940a636e8a68e618ec3ef9267a846705fd83'
POOLS = {'CIC_DEV': ('DEV', 179886),
         'UNSW_DEV': ('EXTERNAL_ARCHIVAL_EVALUATION', 148316)}
POLICIES = ('B0', 'B1', 'B2')
PARENT_ROLES = {'CIC_DEV': 'SOURCE_REFS', 'UNSW_DEV': 'UNSW_REFS'}


def _manifest(path, expected_sha256):
    path = c.pin(path, expected_sha256)
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        c.require(name not in result and len(digest) == 64 and
                  all(ch in '0123456789abcdef' for ch in digest.lower()),
                  'PARENT_MANIFEST_SCHEMA:' + str(path))
        result[name] = digest.lower()
    return result


def _entry(path, expected_sha256=None):
    path = Path(path).resolve()
    actual = c.sha(c.pin(path, expected_sha256)) if expected_sha256 else c.sha(path)
    return dict(path=str(path), sha256=actual)


def _rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_rows(path, rows):
    with gzip.open(path, 'xt', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def _source_gate(fit_dir, cal_dir):
    """This entire function runs before any target path is opened."""
    c.check_spec()
    c.verify_seal(fit_dir)
    c.verify_seal(cal_dir)
    binding = c.read(fit_dir / 'input_binding.json')
    c.require(c.read(cal_dir / 'input_binding.json') == binding,
              'CAL_SOURCE_BINDING_CHANGED')
    fit = c.read(fit_dir / 'FIT_COMPLETE.json')
    cal = c.read(cal_dir / 'calibration.json')
    c.require(fit['status'] in ('COMPLETE', 'NOOP') and
              fit['synthetic_only'] is False and
              fit['target_queries_read'] == 0 and
              cal['status'] == 'SEALED' and
              cal['synthetic_only'] is False and
              cal['target_queries_read'] == 0,
              'SOURCE_STAGES_NOT_PRODUCTION_SEALED')
    c.require(cal['fit_seal_sha256'] == c.sha(fit_dir / 'SEAL.json') and
              cal['input_binding_digest'] == c.digest(binding) and
              cal['cut'] == binding['cut'], 'SOURCE_CAL_BINDING_CHANGED')
    c.require(binding.get('normalizer_sha256') and
              len(binding['normalizer_sha256']) == 64 and
              binding.get('lineage', c.LINEAGE) == c.LINEAGE,
              'SOURCE_BINDING_INCOMPLETE')
    return binding


def _parent(cache, head_run, binding):
    c.require(str(cache.resolve()) == binding['cache'], 'SOURCE_CACHE_PATH_CHANGED')
    binding_path = c.pin(head_run/'cache_binding.json',
                         binding['extracted']['run/cache_binding.json']['sha256'])
    parent_binding = c.read(binding_path)
    marker = c.read(c.pin(cache/'CACHE_REBUILD_COMPLETE.json',
                          parent_binding['marker_sha256']))
    c.require(marker == parent_binding['marker'],
              'PARENT_CACHE_MARKER_CHANGED')
    c.require(parent_binding['marker'] == marker and
              parent_binding['marker']['lineage'] == c.LINEAGE and
              parent_binding['marker']['original_input_manifest_sha256'] ==
              binding['input_manifest_sha256'] and
              parent_binding['marker']['feature_manifest_sha256'] ==
              binding['feature_manifest_sha256'] and
              parent_binding['marker']['spool_sha256'] ==
              binding['spool_sha256'], 'PARENT_CACHE_BINDING_CHANGED')
    input_pins = _manifest(cache/'inputs/SHA256SUMS',
                           binding['input_manifest_sha256'])
    feature_pins = _manifest(cache/'features/SHA256SUMS',
                             binding['feature_manifest_sha256'])
    normalizer_pins = _manifest(cache/'normalizers/SHA256SUMS',
        marker['normalizer_manifest_sha256'])
    normalizer = c.pin(cache/'normalizers/RECENT.npz',
                       binding['normalizer_sha256'])
    c.require(normalizer_pins['RECENT.npz'] == binding['normalizer_sha256'],
              'PARENT_NORMALIZER_CHANGED')
    spool = c.pin(cache/'spool/snapshots.sqlite', binding['spool_sha256'])
    complete = c.read(c.pin(head_run/'QUERY_LINEAGE_COMPLETE.json',
                            QUERY_COMPLETE_SHA256))
    c.require(complete['status'] == 'COMPLETE' and
              complete['lineage'] == c.LINEAGE and
              complete['parent_parity'] == c.PARENT_PARITY,
              'QUERY_RUN_NOT_COMPLETE')
    p = c.read(c.pin(head_run/'LINEAGE_P_COMPLETE.json', complete['P_sha256']))
    c.pin(head_run/'LINEAGE_T_COMPLETE.json', complete['T_sha256'])
    c.pin(head_run/'LINEAGE_K_COMPLETE.json', complete['K_sha256'])
    c.require(p['status'] == 'COMPLETE' and
              p['cache_binding_digest'] == c.digest(parent_binding),
              'QUERY_PREPARED_BINDING_CHANGED')
    prepared_pins = _manifest(head_run/'prepared/SHA256SUMS',
                              p['prepared_seal_sha256'])
    # The completed run seal binds every pool's score seal.
    run_pins = _manifest(head_run/'SHA256SUMS',
                         complete['output_seal_sha256'])
    return dict(parent_binding=parent_binding,
                parent_binding_path=head_run/'cache_binding.json',
                input_pins=input_pins,
                feature_pins=feature_pins, prepared_pins=prepared_pins,
                run_pins=run_pins, normalizer=normalizer, spool=spool)


def _query(pool, partition, count, cache, head_run, parent, output):
    metadata = c.pin(cache/'inputs'/(pool+'.jsonl.gz'),
                     parent['input_pins'][pool+'.jsonl.gz'])
    c.require(parent['prepared_pins'][pool+'.jsonl.gz'] ==
              parent['input_pins'][pool+'.jsonl.gz'],
              'QUERY_PREPARED_METADATA_DRIFT:' + pool)
    rows = _rows(metadata)
    c.require(len(rows) == count and
              all(r.get('partition') == partition and
                  r.get('use') != 'REFERENCE' for r in rows),
              'TARGET_QUERY_ROLE:' + pool)
    uids = [r['uid'] for r in rows]
    c.require(len(set(uids)) == len(uids), 'TARGET_QUERY_UIDS:' + pool)
    feature = c.pin(cache/'features'/(pool+'.npy'),
                    parent['feature_pins'][pool+'.npy'])
    q_path = c.pin(head_run/'prepared'/(pool+'_q.npy'),
                   parent['prepared_pins'][pool+'_q.npy'])
    z = np.load(feature, mmap_mode='r', allow_pickle=False)
    q = np.load(q_path, mmap_mode='r', allow_pickle=False)
    c.require(z.shape == (count, 794) and z.dtype == np.float32 and
              q.shape == (count, 14) and q.dtype == np.float32 and
              np.isfinite(z[:, :768]).all() and np.isfinite(q).all() and
              np.all((q >= 0) & (q <= 1)), 'TARGET_QUERY_ARRAYS:' + pool)
    pool_pins = _manifest(head_run/pool/'SHA256SUMS',
                          parent['run_pins'][pool+'/SHA256SUMS'])
    score_path = c.pin(head_run/pool/'scores.npz', pool_pins['scores.npz'])
    with np.load(score_path, allow_pickle=False) as saved:
        c.require(set(saved.files) >= {'uid', 'QUERY_TAIL_27'} and
                  saved['uid'].tolist() == uids, 'TARGET_SCORE_UIDS:' + pool)
        scores = saved['QUERY_TAIL_27']
        c.require(scores.shape == (count,) and scores.dtype.kind == 'f' and
                  np.isfinite(scores).all(), 'TARGET_SCORE_SCHEMA:' + pool)
        folder = output/'query'/pool
        folder.mkdir(parents=True, exist_ok=False)
        e3_path, score_output, uid_path = (folder/name for name in
            ('e3.npy', 'scores.npy', 'uids.txt'))
        np.save(e3_path, z[:, :768])
        np.save(score_output, scores)
        uid_path.write_text(''.join(uid+'\n' for uid in uids),
                            encoding='utf-8')
        declaration = dict(rows=_entry(metadata), e3=_entry(e3_path),
                           q14=_entry(q_path), feature_uids=_entry(uid_path),
                           q_uids=_entry(uid_path), scores=_entry(score_output),
                           score_head='QUERY_TAIL_27',
                           ordered_uid_sha256=c.uid_hash(uids, ordered=True))
    z._mmap.close()
    q._mmap.close()
    return declaration


def _modern(pool, policy, old_run, location, normalizer_sha256, output):
    c.require(set(location) >= {'path', 'receipt_sha256'} and
              not Path(location['path']).is_absolute(),
              'BANK_LOCATION_SCHEMA:' + pool + ':' + policy)
    folder = (old_run/location['path']).resolve()
    c.require(old_run.resolve() in folder.parents,
              'BANK_LOCATION_ESCAPE:' + pool + ':' + policy)
    receipt_path = c.pin(folder/'receipt.json', location['receipt_sha256'])
    receipt = c.read(receipt_path)
    c.require(receipt.get('status') == 'COMPLETE' and
              receipt.get('synthetic_only') is False and
              receipt.get('policy') == policy and
              receipt.get('normalizer_sha256') == normalizer_sha256,
              'MODERN_PRODUCER_IDENTITY:' + pool + ':' + policy)
    metadata = c.pin(folder/'references.jsonl.gz', receipt['metadata_sha256'])
    rows = _rows(metadata)
    with np.load(c.pin(folder/'bank.npz', receipt['bank_npz_sha256']),
                 allow_pickle=False) as saved:
        c.require(set(saved.files) >= {'uid', 'e3', 'q14'} and
                  saved['uid'].tolist() == [r['uid'] for r in rows],
                  'MODERN_BANK_UIDS:' + pool + ':' + policy)
        declaration = bundle_io.write_bundle(output/'banks'/pool/policy,
                                              rows, saved['e3'], saved['q14'])
    declaration.update(producer_kind='encoded-selected-v2',
                       producer_receipt=_entry(receipt_path,
                                               location['receipt_sha256']),
                       producer_receipt_sha256=location['receipt_sha256'])
    return declaration


def _old(pool, partition, cache, parent, binding, output):
    role = PARENT_ROLES[pool]
    metadata_path = c.pin(cache/'inputs'/(role+'.jsonl.gz'),
                          parent['input_pins'][role+'.jsonl.gz'])
    parent_rows = _rows(metadata_path)
    feature_path = c.pin(cache/'features'/(role+'.npy'),
                         parent['feature_pins'][role+'.npy'])
    z = np.load(feature_path, mmap_mode='r', allow_pickle=False)
    c.require(z.shape == (len(parent_rows), 794) and z.dtype == np.float32,
              'OLD_PARENT_FEATURES:' + pool)
    c.require(len({r['uid'] for r in parent_rows}) == len(parent_rows) and
              all(r['use'] == 'REFERENCE' and r['label'] == 0 for r in parent_rows),
              'OLD_PARENT_ROWS:' + pool)
    old_module_dir = DEPLOYMENT_ROOT/'repo/ood'
    if str(old_module_dir) not in sys.path:
        sys.path.insert(0, str(old_module_dir))
    from constrained_onboarding_reference_v2 import extract_old_bank_q14
    indexed = [dict(row, parent_slot=i) for i, row in enumerate(parent_rows)]
    full_q = extract_old_bank_q14(parent['spool'], indexed,
                                 binding['spool_sha256'])
    c.require(full_q.shape == (len(parent_rows), 14) and
              full_q.dtype == np.float32 and np.isfinite(full_q).all() and
              np.all((full_q >= 0) & (full_q <= 1)),
              'OLD_PARENT_Q14:' + pool)
    source_dir = output/'historical'/pool
    source_dir.mkdir(parents=True, exist_ok=False)
    q_path = source_dir/'parent_q14.npy'
    np.save(q_path, full_q)
    slots = [i for i, row in enumerate(parent_rows)
             if row['partition'] == partition]
    c.require(bool(slots), 'OLD_BANK_EMPTY:' + pool)
    rows = [parent_rows[i] for i in slots]
    c.require(all(row['partition'] == partition for row in rows),
              'OLD_BANK_PARTITION:' + pool)
    lineage_path = source_dir/'lineage_map.jsonl.gz'
    _write_rows(lineage_path, [dict(uid=parent_rows[i]['uid'], parent_slot=i)
                               for i in slots])
    bank_dir = output/'banks'/pool/'OLD_BANK'
    declaration = bundle_io.write_bundle(bank_dir, rows,
                                          z[slots, :768], full_q[slots])
    np.savez(bank_dir/'bank.npz', uid=np.asarray([r['uid'] for r in rows]),
             e3=np.asarray(z[slots, :768]), q14=full_q[slots])
    z._mmap.close()
    _write_rows(bank_dir/'references.jsonl.gz', rows)
    marker = parent['parent_binding']['marker']
    assets = dict(
        parent_cache_binding=_entry(parent['parent_binding_path']),
        parent_input_manifest=_entry(cache/'inputs/SHA256SUMS',
                                     binding['input_manifest_sha256']),
        parent_feature_manifest=_entry(cache/'features/SHA256SUMS',
                                       binding['feature_manifest_sha256']),
        parent_normalizer_manifest=_entry(cache/'normalizers/SHA256SUMS',
                                          marker['normalizer_manifest_sha256']),
        parent_metadata=_entry(metadata_path), parent_e3=_entry(feature_path),
        parent_q14=_entry(q_path), parent_spool=_entry(parent['spool']),
        normalizer=_entry(parent['normalizer'], binding['normalizer_sha256']),
        lineage_map=_entry(lineage_path))
    receipt = dict(schema='learned-onboarding-historical-bank-export-v1',
                   status='SEALED', synthetic_only=False, pool=pool,
                   partition=partition, policy='OLD_BANK',
                   source_method='parent_cache_uid_slot_replay',
                   normalizer_sha256=binding['normalizer_sha256'],
                   rows=len(rows),
                   ordered_uid_sha256=c.uid_hash((r['uid'] for r in rows),
                                                  ordered=True),
                   bank_npz_sha256=c.sha(bank_dir/'bank.npz'),
                   metadata_sha256=c.sha(bank_dir/'references.jsonl.gz'),
                   source_assets=assets)
    c.write(bank_dir/'receipt.json', receipt)
    declaration.update(producer_kind='historical-old-bank-v1',
                       producer_receipt=_entry(bank_dir/'receipt.json'),
                       producer_receipt_sha256=c.sha(bank_dir/'receipt.json'))
    return declaration


def assemble(deployment_root, fit_dir, cal_dir, output, *, cache=DEFAULT_CACHE,
             head_run=DEFAULT_HEAD_RUN, old_run=DEFAULT_OLD_RUN):
    deployment_root = Path(deployment_root).resolve()
    fit_dir, cal_dir, output = (Path(path).resolve() for path in
                                (fit_dir, cal_dir, output))
    cache, head_run, old_run = (Path(path).resolve() for path in
                                (cache, head_run, old_run))
    c.require(deployment_root == DEPLOYMENT_ROOT and
              output == deployment_root/'inputs/target_bundle',
              'DEPLOYMENT_OUTPUT_PATH')
    c.require(not output.exists(), 'OUTPUT_ALREADY_EXISTS:' + str(output))
    c.require(all(output != p and output not in p.parents and
                  p not in output.parents for p in
                  (fit_dir, cal_dir, cache, head_run, old_run)),
              'TARGET_OUTPUT_INPUT_OVERLAP')
    output.mkdir(parents=True)
    try:
        c.write(output/'progress.json', dict(stage='SOURCE_SEAL_GATE',
                                             target_queries_read=0))
        binding = _source_gate(fit_dir, cal_dir)
        parent = _parent(cache, head_run, binding)
        bank_manifest_path = c.pin(old_run/'banks_manifest.json',
                                   BANKS_MANIFEST_SHA256)
        bank_manifest = c.read(bank_manifest_path)
        c.require(set(bank_manifest) == {'pools'} and
                  set(bank_manifest['pools']) == set(POOLS),
                  'BANKS_MANIFEST_SCHEMA')
        manifest = dict(schema='learned-onboarding-target-inputs-v1',
                        spec_sha256=c.SPEC_SHA256, status='SEALED',
                        synthetic_only=False,
                        source_binding_digest=c.digest(binding),
                        cut=binding['cut'],
                        normalizer_sha256=binding['normalizer_sha256'],
                        lineage=c.LINEAGE, parent_parity=c.PARENT_PARITY,
                        pools={})
        for pool, (partition, count) in POOLS.items():
            c.write(output/'progress.json', dict(stage='ASSEMBLE_'+pool,
                                                 target_queries_read=pool))
            query = _query(pool, partition, count, cache, head_run, parent,
                           output)
            banks = {'OLD_BANK': _old(pool, partition, cache, parent,
                                      binding, output)}
            locations = bank_manifest['pools'][pool]
            c.require(set(locations) == set(POLICIES),
                      'MODERN_BANK_MATRIX:' + pool)
            for policy in POLICIES:
                banks[policy] = _modern(pool, policy, old_run,
                                        locations[policy],
                                        binding['normalizer_sha256'], output)
            manifest['pools'][pool] = dict(query=query, banks=banks)
        path = output/'target_manifest.json'
        c.write(path, manifest)
        # The frozen loader performs every producer identity and bitwise join.
        bundle_io.load_targets(path, expected_sha256=c.sha(path),
            source_binding_digest=c.digest(binding), cut=binding['cut'],
            normalizer_sha256=binding['normalizer_sha256'],
            source_binding=binding)
        (output/'SHA256SUMS').write_text(c.sha(path)+'  target_manifest.json\n',
                                         encoding='utf-8')
        c.write(output/'progress.json', dict(stage='COMPLETE',
                                             manifest_sha256=c.sha(path)))
        c.seal(output)
        return path
    except Exception as error:
        c.write(output/'exception.json', dict(status='STOPPED_NO_RETRY',
            error_type=type(error).__name__, error=str(error),
            traceback=traceback.format_exc(), existing_artifacts_retained=True))
        raise


def self_test():
    """Small local fixture; it never opens the real target pools."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        fit, cal = root/'fit', root/'cal'
        fit.mkdir(); cal.mkdir()
        binding = dict(cut=-2.0, normalizer_sha256='a'*64,
                       lineage=c.LINEAGE)
        c.write(fit/'input_binding.json', binding)
        c.write(fit/'FIT_COMPLETE.json', dict(status='COMPLETE',
            synthetic_only=False, target_queries_read=0))
        c.seal(fit)
        c.write(cal/'input_binding.json', binding)
        c.write(cal/'calibration.json', dict(status='SEALED',
            synthetic_only=False, target_queries_read=0,
            fit_seal_sha256=c.sha(fit/'SEAL.json'),
            input_binding_digest=c.digest(binding), cut=-2.0))
        c.seal(cal)
        c.require(_source_gate(fit, cal) == binding,
                  'FIXTURE_SOURCE_GATE')
        c.write(cal/'input_binding.json', dict(binding, cut=-3.0))
        try:
            _source_gate(fit, cal)
        except c.ContractError:
            pass
        else:
            raise AssertionError('tampered CAL seal accepted')
        cache, run, output = root/'cache', root/'run', root/'out'
        for folder in (cache/'inputs', cache/'features', run/'prepared',
                       run/'CIC_DEV', output):
            folder.mkdir(parents=True, exist_ok=True)
        rows = [dict(uid='fixture-0', partition='DEV', use='QUERY', label=0),
                dict(uid='fixture-1', partition='DEV', use='QUERY', label=1)]
        metadata = cache/'inputs/CIC_DEV.jsonl.gz'
        _write_rows(metadata, rows)
        feature = cache/'features/CIC_DEV.npy'
        q_path = run/'prepared/CIC_DEV_q.npy'
        np.save(feature, np.arange(2*794, dtype=np.float32).reshape(2, 794))
        np.save(q_path, np.zeros((2, 14), dtype=np.float32))
        np.savez(run/'CIC_DEV/scores.npz',
                 uid=np.asarray([r['uid'] for r in rows]),
                 QUERY_TAIL_27=np.asarray([-1., 2.], dtype=np.float32))
        seal = run/'CIC_DEV/SHA256SUMS'
        seal.write_text(c.sha(run/'CIC_DEV/scores.npz')+
                        '  scores.npz\n', encoding='utf-8')
        pins = dict(input_pins={'CIC_DEV.jsonl.gz': c.sha(metadata)},
                    feature_pins={'CIC_DEV.npy': c.sha(feature)},
                    prepared_pins={'CIC_DEV.jsonl.gz': c.sha(metadata),
                                   'CIC_DEV_q.npy': c.sha(q_path)},
                    run_pins={'CIC_DEV/SHA256SUMS': c.sha(seal)})
        declaration = _query('CIC_DEV', 'DEV', 2, cache, run, pins, output)
        loaded = bundle_io.load_bundle(output, declaration, query=True)
        c.require(loaded['feature_uids'] == ['fixture-0', 'fixture-1'] and
                  loaded['e3'].shape == (2, 768) and
                  loaded['scores'].tolist() == [-1., 2.] and
                  declaration['rows']['path'] == str(metadata.resolve()) and
                  declaration['q14']['path'] == str(q_path.resolve()) and
                  declaration['feature_uids'] == declaration['q_uids'],
                  'FIXTURE_QUERY_INTERCHANGE')
        loaded['e3']._mmap.close()
        loaded['q14']._mmap.close()
        old_module_dir = DEPLOYMENT_ROOT/'repo/ood'
        if str(old_module_dir) not in sys.path:
            sys.path.insert(0, str(old_module_dir))
        from test_constrained_onboarding_reference_v1 import body_row
        body, old_row = body_row()
        source = cache/'inputs/SOURCE_REFS.jsonl.gz'
        old_feature = cache/'features/SOURCE_REFS.npy'
        _write_rows(source, [old_row])
        np.save(old_feature, np.zeros((1, 794), dtype=np.float32))
        spool = root/'snapshots.sqlite'
        database = sqlite3.connect(str(spool))
        try:
            database.execute('CREATE TABLE snapshots(uid TEXT PRIMARY KEY,role TEXT,slot INTEGER,protocol INTEGER,body TEXT)')
            database.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)',
                (old_row['uid'], 'SOURCE_REFS', 0, old_row['protocol'],
                 json.dumps(body)))
            database.commit()
        finally:
            database.close()
        (cache/'normalizers').mkdir()
        normalizer = cache/'normalizers/RECENT.npz'
        np.savez(normalizer, mean=np.zeros(768), scale=np.ones(768))
        manifests = {}
        for key, name, file, target in (
                ('input', 'SOURCE_REFS.jsonl.gz', source,
                 cache/'inputs/SHA256SUMS'),
                ('feature', 'SOURCE_REFS.npy', old_feature,
                 cache/'features/SHA256SUMS'),
                ('normalizer', 'RECENT.npz', normalizer,
                 cache/'normalizers/SHA256SUMS')):
            target.write_text(c.sha(file)+'  '+name+'\n', encoding='utf-8')
            manifests[key] = target
        marker = dict(lineage=c.LINEAGE,
            original_input_manifest_sha256=c.sha(manifests['input']),
            feature_manifest_sha256=c.sha(manifests['feature']),
            normalizer_manifest_sha256=c.sha(manifests['normalizer']),
            spool_sha256=c.sha(spool))
        parent_binding_path = root/'parent_cache_binding.json'
        c.write(parent_binding_path, dict(marker=marker))
        old_binding = dict(input_manifest_sha256=c.sha(manifests['input']),
            feature_manifest_sha256=c.sha(manifests['feature']),
            spool_sha256=c.sha(spool), normalizer_sha256=c.sha(normalizer))
        old_parent = dict(input_pins={'SOURCE_REFS.jsonl.gz': c.sha(source)},
            feature_pins={'SOURCE_REFS.npy': c.sha(old_feature)},
            parent_binding=dict(marker=marker),
            parent_binding_path=parent_binding_path,
            spool=spool, normalizer=normalizer)
        declaration = _old('CIC_DEV', 'DEV', cache, old_parent,
                           old_binding, output)
        loaded = bundle_io.load_bundle(output, declaration)
        bundle_io._historical_producer(output, 'CIC_DEV', 'DEV',
            declaration, loaded, c.sha(normalizer), old_binding)
        loaded['e3']._mmap.close()
        loaded['q14']._mmap.close()
        import gc
        gc.collect()
        print(json.dumps(dict(status='PASS', tests=['source-seal-gate',
            'tampered-cal-seal-rejected', 'pinned-query-interchange',
            'historical-parent-slot-replay'],
            real_target_queries_read=0)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--deployment-root', type=Path)
    parser.add_argument('--fit-dir', type=Path)
    parser.add_argument('--cal-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--head-run', type=Path, default=DEFAULT_HEAD_RUN)
    parser.add_argument('--old-run', type=Path, default=DEFAULT_OLD_RUN)
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if any(value is None for value in
           (args.deployment_root, args.fit_dir, args.cal_dir, args.output)):
        parser.error('--deployment-root, --fit-dir, --cal-dir and --output are required')
    path = assemble(args.deployment_root, args.fit_dir, args.cal_dir,
                    args.output, cache=args.cache, head_run=args.head_run,
                    old_run=args.old_run)
    print(json.dumps(dict(target_manifest=str(path), sha256=c.sha(path))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
