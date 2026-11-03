"""Generated caches only: identity, layer separation, failure behavior and packaging."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import legacy_unsw_saved_cache_audit_v1 as a


def save_rows(path, rows):
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row)+'\n')


def fixture(source):
    source.mkdir()
    run = source/a.RUN
    for folder in ('manifests', 'flows', 'features', 'evaluation'):
        (run/folder).mkdir(parents=True)
    query, refs = [], []
    for device in ('generated-a', 'generated-b'):
        for k in range(1, 13):
            use = 'REFERENCE' if k > 10 else 'QUERY'
            query_row = dict(uid=a.digest([device, k]), device=device, display_name=device,
                label=int(k <= 8), use=use, protocol=6, component_id=device+'-component',
                session_id=device+'-session', annotation_id='interval-'+str(1 if k <= 4 else 2) if k <= 8 else None,
                attack_rate=(1 if k <= 4 else 10) if k <= 8 else None,
                timestamp=float(k) if use == 'QUERY' else float(k-15), frame=k)
            (query if use == 'QUERY' else refs).append(query_row)
    query.sort(key=lambda r:r['uid']); refs.sort(key=lambda r:r['uid'])
    rows = query+refs
    save_rows(run/'manifests/queries.jsonl.gz', query)
    save_rows(run/'manifests/references.jsonl.gz', refs)
    a.seal(run/'manifests')
    flow_rows, features = [], []
    for row in rows:
        phase = min(row['frame'], 7)
        flow = dict(flow_duration=row['frame']*1000, burst_tokens=[[1, phase]],
                    directions=[True], bytes=[40], iats=[phase], counts=[1], protocol=6)
        flow_rows.append(dict(uid=row['uid'], flow=flow))
        features.append(np.full(768, phase, dtype=np.float32))
    shards = []
    for k in range(4):
        name = 'shard_%02d.jsonl.gz' % k
        chunk = flow_rows[k::4]
        save_rows(run/'flows'/name, chunk)
        shards.append(dict(file=name, count=len(chunk)))
    a.write(run/'flows/index.json', dict(shards=shards, total=len(rows),
            manifest_seal_sha256=a.sha(run/'manifests/SHA256SUMS'), immutable_causal_snapshots=True))
    a.seal(run/'flows')
    np.save(run/'features/features.npy', np.stack(features), allow_pickle=False)
    a.write(run/'features/uids.json', [r['uid'] for r in rows])
    a.write(run/'features/receipt.json', dict(rows=len(rows), recipe_sha256='ab'*32,
            manifest_seal_sha256=a.sha(run/'manifests/SHA256SUMS'), flows_seal_sha256=a.sha(run/'flows/SHA256SUMS')))
    a.seal(run/'features')
    np.savez(run/'evaluation/decisions.npz', uid=np.array([r['uid'] for r in query]))
    values = {key:np.array([min(r['frame'],7) for r in query], dtype=np.float32) for key in a.SCORES}
    values['valid'] = np.ones(len(query), dtype=bool)
    np.savez(run/'evaluation/evidence.npz', **values)
    a.write(run/'status.json', dict(status='COMPLETE'))
    (source/'job.id').write_bytes(b'176975\n'); (source/'exit_code.txt').write_bytes(b'0\n')
    contract = dict(source_job=176975, source_root=str(source), recipe_sha256='ab'*32,
            actual_tensor_hashing='NOT_ENABLED', wall_seconds=1200,
            counts=dict(queries=len(query), references=len(refs), attacks=16),
            devices=['generated-a', 'generated-b'], shards=shards,
            input_files={p.relative_to(source).as_posix():dict(sha256=a.sha(p), bytes=p.stat().st_size)
                         for p in source.rglob('*') if p.is_file()})
    return contract


class CacheAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source, self.out = self.base/'source', self.base/'out'
        self.contract = fixture(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def repin(self, path):
        self.contract['input_files'][path.relative_to(self.source).as_posix()] = dict(sha256=a.sha(path), bytes=path.stat().st_size)

    def run_audit(self):
        return a.audit(self.source, self.out, self.contract, authorized=True)

    def expect_failure(self, reason):
        with self.assertRaisesRegex((RuntimeError, FileExistsError), reason):
            self.run_audit()
        self.assertEqual(a.read(self.out/'status.json')['status'], 'STOPPED_NO_RETRY')
        self.assertFalse((self.out/'summary.json').exists())
        self.assertTrue((self.out/'first_failure.json').is_file())

    def test_full_generated_audit_separates_duration_and_content(self):
        before = {p:a.sha(self.source/p) for p in self.contract['input_files']}
        result = self.run_audit()
        self.assertEqual(len(result['attack_devices']), 2)
        for item in result['attack_devices']:
            self.assertEqual(item['semantic_source_sha256']['unique'], 7)
            self.assertEqual(item['feature_sha256']['constant_tail_start_1based'], 7)
            self.assertEqual(item['rows'], 8)
        groups = a.read(self.out/'grouped_summary.json')
        self.assertEqual(sum(g['rows'] for g in groups['device/use/label']), 24)
        self.assertEqual(before, {p:a.sha(self.source/p) for p in before})
        state = a.read(self.out/'status.json')
        self.assertEqual((state['status'],state['percent']), ('COMPLETE',100))
        self.assertFalse(result['performance_improvement_measured'])
        self.assertEqual(result['target_frame_to_token_provenance'], 'UNAVAILABLE')

    def test_no_authority_before_file_reads(self):
        with patch.object(a, 'verify_inputs', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(RuntimeError, 'NOT_AUTHORIZED'):
                a.audit(self.source, self.out, self.contract)
        self.assertFalse(self.out.exists())

    def test_output_cannot_overlap_source(self):
        with self.assertRaisesRegex(RuntimeError, 'OUTPUT_OVERLAPS_SOURCE'):
            a.audit(self.source, self.source/'child', self.contract, True)

    def test_existing_output_cannot_restart(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_audit()

    def test_source_pin_detects_content_change(self):
        path=self.source/'job.id'
        path.write_bytes(b'176974\n')
        self.expect_failure('SHA_MISMATCH')

    def test_source_job_identity_even_with_valid_hash(self):
        path=self.source/'job.id'
        path.write_bytes(b'176974\n'); self.repin(path)
        self.expect_failure('WRONG_SOURCE_JOB')

    def test_missing_cache_not_recomputed(self):
        path=self.source/(a.RUN+'features/features.npy')
        path.unlink()
        self.expect_failure('MISSING_CACHE')

    def test_unsafe_path(self):
        self.contract['input_files']['../escape'] = dict(bytes=0,sha256='0'*64)
        self.expect_failure('UNSAFE_INPUT_PATH')

    def test_feature_uid_order(self):
        path=self.source/(a.RUN+'features/uids.json')
        a.write(path, a.read(path)[::-1]); self.repin(path)
        self.expect_failure('FEATURE_UID_ORDER')

    def test_nonfinite_features(self):
        path=self.source/(a.RUN+'features/features.npy')
        data=np.load(path); data[0,0]=np.nan; np.save(path,data); self.repin(path)
        self.expect_failure('FEATURE_NONFINITE')

    def test_feature_dtype(self):
        path=self.source/(a.RUN+'features/features.npy')
        data=np.load(path).astype(np.float64); np.save(path,data); self.repin(path)
        self.expect_failure('FEATURE_SHAPE_DTYPE')

    def test_duplicate_snapshot(self):
        path=self.source/(a.RUN+'flows/shard_00.jsonl.gz')
        with gzip.open(path,'rt') as f: records=[json.loads(line) for line in f]
        records[1]=copy.deepcopy(records[0]); save_rows(path,records); self.repin(path)
        self.expect_failure('SNAPSHOT_UID_COVERAGE')

    def test_snapshot_protocol(self):
        path=self.source/(a.RUN+'flows/shard_00.jsonl.gz')
        with gzip.open(path,'rt') as f: records=[json.loads(line) for line in f]
        records[0]['flow']['protocol']=17; save_rows(path,records); self.repin(path)
        self.expect_failure('FLOW_PROTOCOL')

    def test_changed_feature_is_not_claimed_identical_to_source(self):
        path=self.source/(a.RUN+'features/features.npy')
        data=np.load(path)
        with gzip.open(self.source/(a.RUN+'manifests/queries.jsonl.gz'),'rt') as f:
            records=[json.loads(line) for line in f]
        ix=next(i for i,r in enumerate(records) if r['device']=='generated-a' and r['frame']==8)
        data[ix]=99; np.save(path,data); self.repin(path)
        result=self.run_audit()
        item=next(x for x in result['attack_devices'] if x['group']['device']=='generated-a')
        self.assertEqual(item['semantic_source_sha256']['unique'],7)
        self.assertEqual(item['feature_sha256']['unique'],8)
        self.assertEqual(item['source_hashes_with_multiple_features'],1)

    def test_input_mutation_during_audit_stops(self):
        original=a.summarize
        def mutate(rows, progress):
            result=original(rows,progress)
            (self.source/'job.id').write_bytes(b'176974\n')
            return result
        with patch.object(a, 'summarize', mutate):
            self.expect_failure('SHA_MISMATCH')

    def test_tensor_stage_cannot_enable_itself(self):
        self.contract['actual_tensor_hashing']='ENABLED'
        self.expect_failure('UNFROZEN_TENSOR_SCOPE')

    def test_wall_limit(self):
        self.contract['wall_seconds']=-1
        self.expect_failure('WALL_TIME_LIMIT')

    def test_stop_request(self):
        original=a.verify_inputs
        def stop(source,contract,progress,stage):
            (self.out/'STOP_REQUESTED').write_bytes(b'1')
            return original(source,contract,progress,stage)
        with patch.object(a, 'verify_inputs', stop):
            self.expect_failure('USER_STOP_REQUESTED')

    def test_export_omits_original_caches(self):
        self.run_audit()
        root=self.base/'delivery'; root.mkdir()
        (root/'runs').mkdir(); self.out.rename(root/'runs/cache_audit')
        a.export_output(root)
        manifest=a.read(root/'export_manifest.json')
        self.assertTrue(all('features.npy' not in name and 'shard_' not in name for name in manifest))
        with self.assertRaisesRegex(RuntimeError, 'EXPORT_EXISTS'):
            a.export_output(root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
