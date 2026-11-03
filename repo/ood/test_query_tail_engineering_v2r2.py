"""Storage, resource-boundary and unchanged-training generated checks."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import query_tail_core_v2 as k
import query_tail_train_v2 as training
import query_tail_runner_v2r2 as runner
import query_tail_resources_v1 as resources
import training_metadata_v1 as compact
from resource_observation_v1 import StageRecorder, cgroup_observation
from test_query_tail_diagnostics_v2 import generated_fixture, Quiet
c = k.c


def plan():
    return dict(schema=resources.SCHEMA, status='REVIEWABLE', train_workers=3, threads_per_worker=4,
        cpus=16, concurrency_basis='generated boundary fixture; not a production recommendation',
        workload_identity='SYNTHETIC_ONLY', margin_fraction=.25, memory_gib=14, guard_gib=12,
        worker_guard_gib=3,
        phases={name:dict(simultaneous_peak_gib=value, basis='ESTIMATED',
            explanation='generated arithmetic only', evidence=[dict(path='evidence.json', sha256='unset')],
            includes_mappings_and_temporary_buffers=True)
            for name, value in zip(resources.PHASES, (10, 9, 8))})


class MetadataTests(unittest.TestCase):
    def test_exact_values_order_types_and_identity(self):
        rows = generated_fixture()[1]; rows[0]['device'] = '设备\n零'; rows[1]['activity'] = ''
        rows.reverse()
        with tempfile.TemporaryDirectory() as tmp:
            folder = compact.build(iter(rows), Path(tmp)/'data', len(rows), 'source')
            stored = compact.Rows(folder, expected_source_sha256='source', expected_uid_sha256=c.uid_sha(r['uid'] for r in rows))
            try:
                self.assertEqual([dict(row) for row in stored], [{f:r[f] for f in compact.FIELDS} for r in rows])
                self.assertEqual(dict(stored[-1]), {f:rows[-1][f] for f in compact.FIELDS})
                compact.verify_projection(stored)
                np.testing.assert_array_equal(k.weights(rows), k.weights(stored))
                with self.assertRaises(TypeError): stored[0]['label'] = 1
                with self.assertRaises(ValueError): stored.codes[0,0] = 0
                with self.assertRaises(IndexError): _ = stored[len(rows)]
                with self.assertRaisesRegex(RuntimeError, 'METADATA_SOURCE_IDENTITY'):
                    compact.Rows(folder, expected_source_sha256='wrong')
            finally: stored.close()

    def test_large_vocabulary_remains_mapped(self):
        original = generated_fixture()[1][0]
        rows = [dict(original, uid='generated-'+str(i), component_id='c-'+str(i)) for i in range(4100)]
        with tempfile.TemporaryDirectory() as tmp:
            folder = compact.build(rows, Path(tmp)/'data', len(rows), 's')
            stored = compact.Rows(folder, expected_source_sha256='s')
            try:
                self.assertNotIn('uid', stored.small_vocab)
                self.assertIsInstance(stored.blobs['uid'], np.memmap)
                self.assertEqual(stored[4099]['uid'], rows[4099]['uid'])
                self.assertIn('device', stored.small_vocab)
            finally: stored.close()

    def test_wrong_counts_types_duplicate_and_tamper_rejected(self):
        rows = generated_fixture()[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i, values, count in [(0, rows, len(rows)+1), (1, rows, len(rows)-1),
                                     (2, [rows[0],rows[0]], 2), (3, [dict(rows[0],label=True)], 1)]:
                with self.subTest(i=i), self.assertRaises(RuntimeError): compact.build(values,root/str(i),count,'s')
            folder = compact.build(rows,root/'valid',len(rows),'s')
            with (folder/'uid.utf8').open('ab') as stream: stream.write(b'x')
            with self.assertRaisesRegex(RuntimeError, 'IDENTITY'):
                compact.Rows(folder,expected_source_sha256='s')

    def test_all_three_arm_training_trajectory_is_bitwise_identical(self):
        args = list(generated_fixture())
        # Include unequal positive/normal observations to avoid a vacuous tie-only fixture.
        rng = np.random.default_rng(73)
        args[2] = rng.standard_t(3, size=args[2].shape).astype(np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder=compact.build(args[1],root/'data',len(args[1]),'s')
            stored=compact.Rows(folder,expected_source_sha256='s')
            try:
                for arm in k.ARMS:
                    with self.subTest(arm=arm):
                        a=root/(arm+'-dict'); b=root/(arm+'-mapped')
                        training.train(*args,arm,27,a,Quiet(),synthetic=True)
                        changed=args[:]; changed[1]=stored
                        training.train(*changed,arm,27,b,Quiet(),synthetic=True)
                        for name in ('initial.npz','head.npz','endpoint.json','epoch_01.json','epoch_02.json'):
                            self.assertEqual((a/name).read_bytes(),(b/name).read_bytes(),name)
                        for name in ('batch_losses.npy','fixed_probes.jsonl'):
                            self.assertEqual((a/name).read_bytes(),(b/name).read_bytes(),name)
            finally: stored.close()


class ResourceTests(unittest.TestCase):
    def test_sequential_phases_use_max_once(self):
        p=plan(); self.assertIs(resources.validate(p),p)
        self.assertEqual(p['memory_gib'],14)
        for field,value in [('memory_gib',64),('margin_fraction',float('nan')),('cpus',4),
                            ('train_workers',16),('worker_guard_gib',5),('status','PENDING'),
                            ('worker_guard_gib',True),('memory_gib',14.),('threads_per_worker',4.)]:
            changed=copy.deepcopy(p); changed[field]=value
            with self.subTest(field=field), self.assertRaises(RuntimeError): resources.validate(changed)

    def test_missing_evidence_and_missing_phase_fail(self):
        for field in ('evidence','explanation'):
            p=plan(); p['phases']['P_PREPARATION'][field]=[] if field=='evidence' else ''
            with self.assertRaises(RuntimeError): resources.validate(p)
        p=plan(); del p['phases']['K_EVALUATION']
        with self.assertRaises(RuntimeError): resources.validate(p)

    def test_pinned_evidence_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c.write(root/'evidence.json',dict(synthetic_only=True))
            p=plan()
            for phase in p['phases'].values(): phase['evidence'][0]['sha256']=c.sha(root/'evidence.json')
            c.write(root/'plan.json',p); self.assertEqual(resources.load(root/'plan.json')['train_workers'],3)
            p['phases']['P_PREPARATION']['evidence'][0]['path']='../outside.json'
            c.write(root/'plan.json',p,replace=True)
            with self.assertRaisesRegex(RuntimeError,'RESOURCE_EVIDENCE_ESCAPE'): resources.load(root/'plan.json')

    def test_runtime_changes_only_engineering_fields(self):
        base=dict(version='old',cpus=16,train_workers=3, limits=dict(memory_gib=56,wall_seconds=252000),
            worker_limits=dict(memory_gib=14,wall_seconds=252000),slurm=dict(memory='64G',cpus=16,time='3-00:00:00'),
            design_sha256=k.DESIGN_SHA,retries=0)
        changed=resources.runtime(base,plan())
        self.assertEqual(changed['design_sha256'],base['design_sha256'])
        self.assertEqual(changed['limits']['wall_seconds'],252000)
        self.assertEqual(base['limits']['memory_gib'],56)
        self.assertEqual(changed['limits']['memory_gib'],12)

    def test_cgroup_mount_root_and_missing_peak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); proc=root/'proc'; (proc/'self').mkdir(parents=True)
            (proc/'self/cgroup').write_text('0::/jobs/job1/task\n')
            (proc/'self/mountinfo').write_text('1 0 0:1 /jobs /sys/fs/cgroup rw - cgroup2 cgroup rw\n')
            cg=root/'sys/fs/cgroup/job1/task';cg.mkdir(parents=True)
            (cg/'memory.current').write_text('1234\n');(cg/'memory.max').write_text('max\n')
            value=cgroup_observation(proc,root)
            self.assertEqual(value['counters'],{'memory.current':1234,'memory.max':None})
            self.assertNotIn('memory.peak',value['counters'])
            (cg/'memory.peak').write_text('4321\n')
            self.assertEqual(cgroup_observation(proc,root)['counters']['memory.peak'],4321)
            self.assertEqual(cgroup_observation(root/'missing',root)['status'],'UNAVAILABLE')

    def test_stage_samples_keep_peak_and_throttle(self):
        with tempfile.TemporaryDirectory() as tmp:
            now=[0.]; recorder=StageRecorder(tmp,clock=lambda:now[0],sample=lambda:dict(status='UNAVAILABLE'))
            recorder.observe('P',100);now[0]=1.;recorder.observe('P',999)
            now[0]=5.;recorder.observe('P',200);now[0]=6.;recorder.observe('T',50,force=True)
            report=c.read(Path(tmp)/'resource_summary.json')
            self.assertEqual(report['stages']['P']['samples'],2)
            self.assertEqual(report['stages']['P']['sampled_tree_rss_peak_bytes'],200)
            self.assertEqual(len((Path(tmp)/'resource_samples.jsonl').read_text().splitlines()),3)

    def test_progress_lifecycle_writes_separate_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress=runner.Progress(Path(tmp)/'monitor',dict(memory_gib=8,wall_seconds=60,disk_gib=1))
            progress.stage='GENERATED_CHECK';progress.stop('COMPLETE')
            report=c.read(Path(tmp)/'monitor/resource_summary.json')
            self.assertIn('GENERATED_CHECK',report['stages'])


class WorkerIntegrationTests(unittest.TestCase):
    def test_slurm_allocation_must_match_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=Path(os.environ.get('QUERY_TAIL_TEST_ROOT',Path(__file__).resolve().parents[2]))
            design=source/'design_contract.json'
            if not design.exists(): design=source/'runs/legacy_query_tail_learning_design_v2_20261010/design_contract.json'
            shutil.copyfile(design,root/'design_contract.json')
            c.write(root/'runtime_contract.json',dict(design_sha256=k.DESIGN_SHA,retries=0,versions={},
                limits=dict(wall_seconds=70*3600),worker_limits={},slurm=dict(time='3-00:00:00')))
            c.seal(root)
            c.write(root/'evidence.json',dict(generated_only=True))
            selected=plan()
            for phase in selected['phases'].values(): phase['evidence'][0]['sha256']=c.sha(root/'evidence.json')
            c.write(root/'resource_plan.json',selected)
            env=dict(SLURM_JOB_ID='FAKE_TEST',SLURM_CPUS_PER_TASK='16',SLURM_MEM_PER_NODE=str(14*1024),
                     QUERY_TAIL_RESOURCE_SHA=c.sha(root/'resource_plan.json'))
            with patch.dict(os.environ,env):
                self.assertEqual(runner.authorize(root,True)[1]['train_workers'],3)
                for field,value in [('SLURM_CPUS_PER_TASK','4'),('SLURM_MEM_PER_NODE','65536'),
                                    ('QUERY_TAIL_RESOURCE_SHA','changed')]:
                    with self.subTest(field=field),patch.dict(os.environ,{field:value}),self.assertRaises(RuntimeError):
                        runner.authorize(root,True)

    def test_production_worker_joins_compact_metadata_and_frozen_inputs(self):
        from test_query_tail_v2 import fixture
        import query_tail_prepare_v2 as prepare
        with tempfile.TemporaryDirectory() as tmp:
            root,base,design=fixture(tmp)
            run=root/'runs/query_tail';run.mkdir(parents=True);(run/'endpoints').mkdir()
            metadata,indices,arrays,norm=prepare.prepare(root,base,run,design,Quiet())
            source=c.sha(run/'prepared/LEARN.jsonl.gz')
            compact.build(metadata['LEARN'],run/'training_metadata',len(metadata['LEARN']),source)
            runner.close_maps(*arrays.values())
            c.write(run/'compact_metadata_receipt.json',dict(source_sha256=source,seal=c.sha(run/'training_metadata/SHA256SUMS')))
            c.write(root/'resource_plan.json',dict(synthetic_fixture=True))
            c.write(run/'launch_T.json',dict(P_sha256=c.sha(run/'P_COMPLETE.json'),resource_plan_sha256=c.sha(root/'resource_plan.json')))
            runtime=dict(base_run=str(base),worker_limits=dict(memory_gib=8,wall_seconds=60,disk_gib=1))
            original=training.train;seen=[]
            def generated_train(*args,**kwargs):
                self.assertIsInstance(args[1],compact.Rows);seen.append((args[1],args[2],args[3]))
                return original(*args,**kwargs,synthetic=True)
            with patch.object(runner,'authorize',return_value=(design,runtime)),patch.object(runner.signal,'signal'),patch.object(runner.t,'train',side_effect=generated_train):
                runner.worker(root,run,'QUERY_TAIL',27,True)
            self.assertEqual(len(seen),1)
            self.assertTrue(seen[0][0].codes._mmap.closed)
            self.assertTrue(seen[0][1]._mmap.closed)
            self.assertTrue(seen[0][2]._mmap.closed)
            self.assertTrue((run/'endpoints/QUERY_TAIL_27/head.npz').exists())
            self.assertEqual(c.read(run/'monitor_QUERY_TAIL_27/status.json')['status'],'COMPLETE')
            # Changing only resource evidence during a run must also be detected.
            c.write(root/'resource_plan.json',dict(synthetic_fixture='changed'),replace=True)
            with patch.object(runner,'authorize',return_value=(design,runtime)),self.assertRaisesRegex(RuntimeError,'IDENTITY'):
                runner.worker(root,run,'QUERY_TAIL',127,True)
            c.write(root/'resource_plan.json',dict(synthetic_fixture=True),replace=True)
            def fail_train(*args,**kwargs):
                seen.append((args[1],args[2],args[3]))
                raise RuntimeError('GENERATED_TRAINING_FAILURE')
            with patch.object(runner,'authorize',return_value=(design,runtime)),patch.object(runner.signal,'signal'),patch.object(runner.t,'train',side_effect=fail_train):
                with self.assertRaisesRegex(RuntimeError,'GENERATED_TRAINING_FAILURE'):
                    runner.worker(root,run,'QUERY_TAIL',127,True)
            self.assertTrue(all(value._mmap.closed for value in (seen[1][0].codes,seen[1][1],seen[1][2])))
            self.assertEqual(c.read(run/'monitor_QUERY_TAIL_127/status.json')['status'],'STOPPED_NO_RETRY')

    def test_authorize_requires_resource_plan_before_environment_or_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c.write(root/'runtime_contract.json',dict(design_sha256=k.DESIGN_SHA,retries=0))
            source=Path(os.environ.get('QUERY_TAIL_TEST_ROOT',Path(__file__).resolve().parents[2]))
            design=source/'design_contract.json'
            if not design.exists(): design=source/'runs/legacy_query_tail_learning_design_v2_20261010/design_contract.json'
            shutil.copyfile(design,root/'design_contract.json');c.seal(root)
            with self.assertRaises(FileNotFoundError):runner.authorize(root,True)


if __name__=='__main__': unittest.main()
