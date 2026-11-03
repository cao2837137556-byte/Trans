"""Synthetic byte engines only. No torch import, checkpoint, or neural forward."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('source8_diagnostic', HERE/'diagnostic.py')
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


class FakeEngine:
    def __init__(self, anchors, old, observed, *, bad_tensor=False, bad_b1=False, disagree=False):
        self.anchors, self.old, self.observed = anchors, old, observed
        self.calls=[]
        self.bad_tensor, self.bad_b1, self.disagree = bad_tensor, bad_b1, disagree

    def prepare(self, anchor, snapshot, count):
        self.calls.append(('prepare', anchor['uid'], count))
        hashes=[anchor['observed_hpc_b1_tensor_sha256']]*count
        if self.bad_tensor: hashes[0]='0'*64
        return (anchor['uid'],count),hashes

    def forward(self, batch):
        uid,count=batch
        self.calls.append(('forward',uid,count))
        value=(self.observed if count==1 else self.old)[uid]
        if self.bad_b1 and count==1:value=b'X'*diag.ROW_BYTES
        rows=[value]*count
        if self.disagree and count==16:rows[-1]=b'Y'*diag.ROW_BYTES
        return rows


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.out=self.root/'observations';self.out.mkdir()
        self.anchors=[];self.rows=[];self.old={};self.observed={}
        for i in range(8):
            uid=f'{i+1:064x}'
            self.old[uid]=bytes([i])*diag.ROW_BYTES
            self.observed[uid]=bytes([i+10])*diag.ROW_BYTES
            self.rows.append(dict(uid=uid,flow={'protocol':6},provenance={'query_frame':i+1}))
            self.anchors.append(dict(uid=uid,role='SOURCE_REFS',original_batch_size=16,
                source_identity=dict(use='REFERENCE',partition='LEARN'),
                flow_sha256=diag.digest(diag.canonical(self.rows[-1]['flow'])),
                provenance_sha256=diag.digest(diag.canonical(self.rows[-1]['provenance'])),
                expected_old_feature_sha256=diag.digest(self.old[uid]),
                observed_hpc_b1_tensor_sha256=f'{i+20:064x}',
                observed_hpc_b1_feature_sha256=diag.digest(self.observed[uid])))
        self.manifest=dict(schema='paper04-source8-batch-size-diagnostic-v1',scope='SOURCE_REFERENCE8_B1_B16_CLONE_ONLY',
            previous_job_id='179536',anchor_count=8,clone_count=16,maximum_forward_positions=136,limits=diag.LIMITS,
            real_execution_authorized=False,anchors=self.anchors,no_training=True,no_production_bank=True,
            no_source_cal=True,no_target_evaluation=True,no_automatic_variant=True)
        self.expected=[self.old[a['uid']] for a in self.anchors]

    def engine(self, **kwargs):
        return FakeEngine(self.anchors,self.old,self.observed,**kwargs)

    def run_fake(self, engine=None):
        return diag.observe_fixed(self.manifest,self.rows,self.expected,self.out,engine or self.engine())

    def fixture_package(self):
        package=self.root/'package';(package/'data').mkdir(parents=True)
        (package/'data/ANCHOR8.jsonl').write_bytes(b''.join(diag.canonical(r)+b'\n' for r in self.rows))
        (package/'data/EXPECTED8.f32').write_bytes(b''.join(self.expected))
        self.manifest['data_files']={str(p.relative_to(package)).replace('\\','/'):diag.sha(p) for p in (package/'data').iterdir()}
        (package/'manifest.json').write_bytes(diag.canonical(self.manifest))
        self.seal(package)
        return package

    def seal(self, package):
        paths=sorted(p for p in package.rglob('*') if p.is_file() and p.name!='PACKAGE_SHA256SUMS')
        raw=''.join(diag.sha(p)+'  '+p.relative_to(package).as_posix()+'\n' for p in paths).encode()
        (package/'PACKAGE_SHA256SUMS').write_bytes(raw)

    def test_exact_136_synthetic_positions_b1_before_b16_and_observations_durable(self):
        engine=self.engine();result=self.run_fake(engine)
        forwards=[call for call in engine.calls if call[0]=='forward']
        self.assertEqual([v[2] for v in forwards],[1]*8+[16]*8)
        self.assertEqual(result['forward_positions'],136)
        self.assertEqual(result['b16_clone_old_matches'],8)
        self.assertTrue(result['b16_clone_all_old_bytes_equal'])
        self.assertFalse(result['original_cohort_restored'])
        self.assertEqual(len(list(self.out.glob('*.diagnostic.f32'))),16)
        self.assertEqual(diag.read(self.out/'OBSERVATIONS.json')['total_forward_positions'],136)

    def test_tensor_mismatch_stops_before_any_forward(self):
        engine=self.engine(bad_tensor=True)
        with self.assertRaisesRegex(RuntimeError,'FAILED_HPC_TENSOR_IDENTITY'):self.run_fake(engine)
        self.assertFalse(any(c[0]=='forward' for c in engine.calls))

    def test_b1_control_mismatch_saves_observation_and_never_runs_b16(self):
        engine=self.engine(bad_b1=True)
        with self.assertRaisesRegex(RuntimeError,'FAILED_HPC_B1_FEATURE_NOT_REPRODUCED'):self.run_fake(engine)
        self.assertEqual([c[2] for c in engine.calls if c[0]=='forward'],[1])
        self.assertEqual(len(diag.read(self.out/'OBSERVATIONS.json')['observations']),1)

    def test_clone_disagreement_stops_with_all_raw_observations(self):
        with self.assertRaisesRegex(RuntimeError,'B16_CLONES_NOT_BYTE_IDENTICAL'):self.run_fake(self.engine(disagree=True))
        self.assertEqual(len(list(self.out.glob('*.diagnostic.f32'))),9)

    def test_negative_b16_is_reported_without_variant_or_tolerance(self):
        uid=self.anchors[0]['uid'];self.old[uid]=b'Z'*diag.ROW_BYTES
        result=self.run_fake()
        self.assertEqual(result['b16_clone_old_matches'],7)
        self.assertFalse(result['b16_clone_all_old_bytes_equal'])
        self.assertFalse(result['automatic_variant'])

    def test_load_input_no_runtime_import_and_order_verified(self):
        package=self.fixture_package()
        with patch.object(diag,'RealEngine',side_effect=AssertionError('Real runtime must not load')):
            manifest,rows,expected,seal=diag.load_inputs(package)
        self.assertEqual([r['uid'] for r in rows],[r['uid'] for r in self.anchors])
        self.assertEqual(expected,self.expected)
        self.assertEqual(manifest['anchor_count'],8)

    def test_target_role_and_labels_rejected_after_reseal(self):
        for mode in ('target','label'):
            with self.subTest(mode=mode):
                package=self.root/mode;(package/'data').mkdir(parents=True)
                source=self.fixture_package() if not (self.root/'package').exists() else self.root/'package'
                for p in source.rglob('*'):
                    if p.is_file():
                        q=package/p.relative_to(source);q.parent.mkdir(exist_ok=True);q.write_bytes(p.read_bytes())
                value=diag.read(package/'manifest.json')
                if mode=='target':value['anchors'][0]['role']='CIC_DEV'
                else:value['anchors'][0]['source_identity']['label']=0
                (package/'manifest.json').write_bytes(diag.canonical(value));self.seal(package)
                with self.assertRaisesRegex(RuntimeError,'SOURCE_REFERENCE_ONLY|NO_LABELS_OR_SCORES'):diag.load_inputs(package)

    def test_source_snapshot_reordering_rejected_even_after_data_reseal(self):
        package=self.fixture_package()
        path=package/'data/ANCHOR8.jsonl';path.write_bytes(b''.join(diag.canonical(r)+b'\n' for r in reversed(self.rows)))
        self.manifest['data_files']['data/ANCHOR8.jsonl']=diag.sha(path)
        (package/'manifest.json').write_bytes(diag.canonical(self.manifest));self.seal(package)
        with self.assertRaisesRegex(RuntimeError,'FIXED_SOURCE_SNAPSHOT_ORDER'):diag.load_inputs(package)

    def test_tampered_expected_bytes_rejected_by_seal(self):
        package=self.fixture_package();(package/'data/EXPECTED8.f32').write_bytes(b'bad')
        with self.assertRaisesRegex(RuntimeError,'SEALED_MEMBER_SHA'):diag.load_inputs(package)

    def test_missing_extra_or_unsafe_member_rejected(self):
        package=self.fixture_package();(package/'extra').write_bytes(b'extra')
        with self.assertRaisesRegex(RuntimeError,'SEALED_MEMBER_SET'):diag.load_inputs(package)
        (package/'extra').unlink()
        (package/'PACKAGE_SHA256SUMS').write_bytes(b'0'*64+b'  ../escape\n')
        with self.assertRaisesRegex(RuntimeError,'SEALED_PATH_OR_DIGEST'):diag.load_inputs(package)

    def test_expected_per_uid_feature_bytes_not_only_whole_file_hash(self):
        package=self.fixture_package();value=diag.read(package/'manifest.json')
        value['anchors'][0]['expected_old_feature_sha256']='0'*64
        (package/'manifest.json').write_bytes(diag.canonical(value));self.seal(package)
        with self.assertRaisesRegex(RuntimeError,'EXPECTED_UID_FEATURE_BYTES'):diag.load_inputs(package)

    def test_no_implicit_authorization_or_scope_expansion(self):
        value=dict(user_authorized=True,scope='SOURCE_REFERENCE8_B1_B16_CLONE_DIAGNOSTIC_ONLY',
            package_sha256='a'*64,manifest_sha256='b'*64,previous_numerical_stop_job='179536',
            maximum_forward_positions=136,limits=diag.LIMITS,production_encode=False,source_cal=False,
            target_evaluation=False,automatic_retry=False,retries=0,evidence='Synthetic fixture only')
        diag.authorize(value,'a'*64,'b'*64)
        for changes in ({'user_authorized':False},{'maximum_forward_positions':137},{'production_encode':True},
                        {'source_cal':True},{'target_evaluation':True},{'retries':1},{'package_sha256':'c'*64}):
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError,'NEW_EXPLICIT'):
                diag.authorize(dict(value,**changes),'a'*64,'b'*64)

    def test_guard_failure_prevents_forward(self):
        engine=self.engine()
        def guard():raise RuntimeError('synthetic resource guard')
        with self.assertRaisesRegex(RuntimeError,'synthetic resource guard'):
            diag.observe_fixed(self.manifest,self.rows,self.expected,self.out,engine,guard)
        self.assertEqual(engine.calls,[])

    def test_fixed_fresh_output_rejects_any_cache_or_reused_directory(self):
        runtime=self.root/'fixed_runtime'
        with patch.object(diag,'OUTPUT_ROOT',runtime):
            allowed=runtime/'job_123/science'
            self.assertEqual(diag.fresh_output(allowed),allowed.resolve())
            for path in (self.root/'cache/new_output',runtime/'job_0/science',runtime/'job_123/reused'):
                with self.assertRaisesRegex(RuntimeError,'FIXED_FRESH_DIAGNOSTIC_OUTPUT'):diag.fresh_output(path)
            allowed.mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError,'FIXED_FRESH_DIAGNOSTIC_OUTPUT'):diag.fresh_output(allowed)

    def test_resource_guard_counts_child_rss_toward_eight_gib_limit(self):
        class Process:
            def memory_info(self):return SimpleNamespace(rss=5*1024**3)
            def children(self,recursive):return [SimpleNamespace(memory_info=lambda:SimpleNamespace(rss=4*1024**3))]
        guard=diag.Guard.__new__(diag.Guard)
        guard.process=Process();guard.output=self.out;guard.start=diag.time.monotonic()
        guard.psutil=SimpleNamespace(NoSuchProcess=ProcessLookupError)
        with self.assertRaisesRegex(RuntimeError,'DIAGNOSTIC_8GIB_TREE_RSS_LIMIT'):guard()

    def test_private_approval_remains_outside_immutable_seal(self):
        package=self.fixture_package()
        (package/'.private').mkdir()
        (package/'.private/APPROVED.json').write_text('{"user_authorized":false}')
        diag.load_inputs(package)

    def test_prepared_slurm_is_lf_bash_valid_and_fixed_ten_minutes(self):
        path=HERE/'run_diagnostic.slurm'
        raw=path.read_bytes();self.assertNotIn(b'\r',raw)
        bash=Path('C:/Program Files/Git/bin/bash.exe')
        binary=str(bash) if bash.is_file() else shutil.which('bash')
        self.assertTrue(binary,'Bash required for prepared Slurm syntax check')
        subprocess.run([binary,'-n',str(path)],check=True,capture_output=True,text=True)
        self.assertIn(b'#SBATCH --time=00:10:00',raw)
        self.assertIn(b'#SBATCH --no-requeue',raw)


if __name__=='__main__':unittest.main()
