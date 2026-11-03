"""Synthetic/mocked tests only: no PCAP, E3 model, training, scheduler, or network."""
import copy
from contextlib import closing
import os
import shutil
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np
import continuous_common_v3 as c
import frontend_resources_v1 as r
import continuous_rebuild_engineering_v1 as runner


def fixture(tmp):
    root = Path(tmp)/'source'; root.mkdir()
    # Use the actual frozen scientific contract but generated resource-only runtime.
    source = Path(__file__).resolve().parents[2]/'runs/legacy_continuous_input_repair_delivery_v3_20260929/bundle/design_contract.json'
    (root/'design_contract.json').write_bytes(source.read_bytes())
    shutil.copytree(source.parent/'repo/ood',root/'repo/ood',ignore=shutil.ignore_patterns('__pycache__'))
    base = dict(design_sha256=c.DESIGN_SHA,retries=0,threads_per_worker=4,versions={},cpus=64,feature_workers=16,
                limits=dict(wall_seconds=252000,memory_gib=176,disk_gib=160),
                worker_limits=dict(wall_seconds=252000,memory_gib=32,disk_gib=30),
                slurm=dict(time='3-00:00:00',cpus=64,memory='192G'),checkpoint_sha256='0'*64,tshark='tshark')
    for field in ('source_cache','source_inputs','external_run','external_raw','checkpoint'):
        base[field] = str(Path(tmp)/('original_'+field))
    c.write(root/'runtime_contract.json',base); c.seal(root)
    evidence = Path(tmp)/'evidence.txt'; evidence.write_text('SYNTHETIC_TEST_ONLY',encoding='utf-8')
    phase = lambda components: dict(basis='ESTIMATED',explanation='Generated test arithmetic; never a production estimate',
        includes_mappings_and_temporary_buffers=True,evidence=[dict(path=evidence.name,sha256=c.sha(evidence))],
        components=[dict(name=name,gib_per_instance=gib,instances=count,explanation='Generated') for name,gib,count in components],
        simultaneous_peak_gib=sum(gib*count for _,gib,count in components))
    plan = dict(schema=r.SCHEMA,status='REVIEWABLE',feature_workers=2,threads_per_worker=4,cpus=8,
        concurrency_basis='SYNTHETIC fixture',workload_identity=dict(design_sha256=c.DESIGN_SHA,
            runtime_sha256=c.sha(root/'runtime_contract.json'),package_seal_sha256=c.sha(root/'SHA256SUMS')),
        phases={'P_DECODE_AND_PROBE':phase([('metadata_and_probe',4,1)]),
                'E3_WORKERS':phase([('parent_and_shared',1,1),('worker_private',3,2)]),
                'MERGE_NORMALIZE':phase([('parent_and_maps',3,1)])},margin_fraction=.2,memory_gib=10,
        guard_gib=9,worker_guard_gib=3.5,minimum_free_gib=55,disk_gib=50,worker_disk_gib=10,
        disk_basis='SYNTHETIC fixture',post_features_reserve_seconds=100,post_features_reserve_basis='SYNTHETIC fixture',
        state_storage=dict(resident_contexts=2,resident_legacy_prefixes=3,resident_candidate_snapshots=4))
    plan_path = Path(tmp)/'resource_plan.json'; c.write(plan_path,plan)
    env = dict(SLURM_JOB_ID='SYNTHETIC',SLURM_CPUS_PER_TASK='8',SLURM_MEM_PER_NODE='10240',SLURM_JOB_NUM_NODES='1',
               FRONTEND_RESOURCE_SHA=c.sha(plan_path),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
    return root,base,plan_path,plan,env


class ResourceTests(unittest.TestCase):
    def test_sequential_max_not_sum_and_preserve_runtime_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,path,plan,_ = fixture(tmp)
            result=r.runtime(base,r.load(path))
            self.assertEqual(result['slurm']['memory'],'10G')
            for key in ('source_cache','source_inputs','external_run','external_raw','checkpoint','versions'):
                self.assertEqual(result[key],base[key])
            wrong=copy.deepcopy(plan);wrong['memory_gib']=18
            with self.assertRaisesRegex(RuntimeError,'FRONTEND_ALLOCATION'):r.validate(wrong)

    def test_pending_missing_evidence_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,path,plan,_=fixture(tmp)
            wrong=copy.deepcopy(plan);wrong['status']='PENDING_PHASE_EVIDENCE'
            with self.assertRaisesRegex(RuntimeError,'PENDING'):r.validate(wrong)
            wrong=copy.deepcopy(plan);wrong['phases']['E3_WORKERS']['evidence']=[]
            with self.assertRaisesRegex(RuntimeError,'EVIDENCE'):r.validate(wrong)
            (Path(tmp)/'evidence.txt').write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'):r.load(path)

    def test_evidence_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,path,plan,_=fixture(tmp)
            plan['phases']['E3_WORKERS']['evidence'][0]['path']='../outside'
            c.write(path,plan,replace=True)
            with self.assertRaisesRegex(RuntimeError,'ESCAPE'):r.load(path)

    def test_worker_components_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,_,plan,_=fixture(tmp)
            for field,value in [('feature_workers',3),('cpus',4),('worker_guard_gib',8),('guard_gib',11),('margin_fraction',float('nan'))]:
                wrong=copy.deepcopy(plan);wrong[field]=value
                with self.subTest(field=field),self.assertRaises(RuntimeError):r.validate(wrong)
            wrong=copy.deepcopy(plan);wrong['phases']['E3_WORKERS']['components'][1]['instances']=1
            wrong['phases']['E3_WORKERS']['simultaneous_peak_gib']=4
            with self.assertRaisesRegex(RuntimeError,'CONCURRENCY'):r.validate(wrong)

    def test_component_sum_and_disk_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,_,plan,_=fixture(tmp)
            wrong=copy.deepcopy(plan);wrong['phases']['MERGE_NORMALIZE']['simultaneous_peak_gib']=4
            with self.assertRaisesRegex(RuntimeError,'SUM'):r.validate(wrong)
            wrong=copy.deepcopy(plan);wrong['disk_gib']=100
            with self.assertRaisesRegex(RuntimeError,'DISK_BASIS'):r.validate(wrong)


class EntrypointTests(unittest.TestCase):
    def test_explicit_required_before_source_access(self):
        with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'):
            runner.authorize('/does/not/exist','/missing',False)

    def test_slurm_identity_and_actual_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_,path,_,env=fixture(tmp)
            with mock.patch.dict(os.environ,env,clear=True):
                _,runtime=runner.authorize(root,path,True)
                self.assertEqual(runtime['feature_workers'],2)
                for key,value in [('SLURM_CPUS_PER_TASK','64'),('SLURM_MEM_PER_NODE','196608'),
                                  ('FRONTEND_RESOURCE_SHA','wrong'),('SLURM_JOB_NUM_NODES','2'),('OMP_NUM_THREADS','1')]:
                    with self.subTest(key=key),mock.patch.dict(os.environ,{key:value}),self.assertRaises(RuntimeError):
                        runner.authorize(root,path,True)

    def test_missing_plan_and_no_local_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_,path,_,_=fixture(tmp)
            with self.assertRaises(FileNotFoundError):runner.authorize(root,Path(tmp)/'absent',True)
            with mock.patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(RuntimeError,'SLURM_ALLOCATION'):
                runner.authorize(root,path,True)

    def test_output_scope_existing_or_source_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,_,_,_=fixture(tmp)
            self.assertEqual(runner.output_scope(root,Path(tmp)/'result',base),Path(tmp)/'result')
            for path in (root/'runs/new',Path(tmp),Path(base['external_run'])/'new',root):
                with self.subTest(path=path),self.assertRaisesRegex(RuntimeError,'OVERLAP'):
                    runner.output_scope(root,path,base)
            existing=Path(tmp)/'used';existing.mkdir()
            with self.assertRaisesRegex(RuntimeError,'ALREADY_EXISTS'):runner.output_scope(root,existing,base)

    def test_fixed_checkpoint_missing_fails_without_source_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,_,_,_=fixture(tmp)
            checkpoint=Path(base['checkpoint']);checkpoint.write_bytes(b'synthetic checkpoint placeholder')
            base.update(checkpoint_sha256=c.sha(checkpoint),minimum_free_gib=.00001)
            before=sorted(str(x.relative_to(root)) for x in root.rglob('*'))
            with self.assertRaisesRegex(RuntimeError,'FIXED_VENDOR_CHECKPOINT_MISSING'):
                runner.environment(root,Path(tmp)/'result',base)
            self.assertEqual(before,sorted(str(x.relative_to(root)) for x in root.rglob('*')))

    def test_worker_rechecks_plan_and_code_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,path,_,env=fixture(tmp)
            run=Path(tmp)/'result';run.mkdir()
            launch=dict(scope='CACHE_ONLY_P_E3_NORMALIZERS',root=str(root.resolve()),run=str(run.resolve()),
                resource_plan_path=str(path),resource_plan_sha256=c.sha(path),engineering_code=runner.code_identity(),
                package_seal_sha256=c.sha(root/'SHA256SUMS'))
            c.write(run/'launch.json',launch)
            with mock.patch.dict(os.environ,env,clear=True):
                runner.authorize_worker(root,run,True)
                with mock.patch.object(runner,'code_identity',return_value={'changed':'file'}),self.assertRaisesRegex(RuntimeError,'CODE_IDENTITY'):
                    runner.authorize_worker(root,run,True)
                path.write_text('{}')
                with self.assertRaisesRegex(RuntimeError,'IDENTITY'):runner.authorize_worker(root,run,True)

    def test_launcher_commands_success_and_fail_closed(self):
        class Child:
            pid=99999
            def __init__(self,code):self.returncode=code
            def poll(self):return self.returncode
            def wait(self,timeout=None):return self.returncode
        class Progress:
            def __init__(self):self.children=[];self.killed=False
            def guard(self):pass
            def kill_children(self):self.killed=True
        with tempfile.TemporaryDirectory() as tmp:
            root,_,_,_,_=fixture(tmp)
            for code in (0,1):
                run=Path(tmp)/('result'+str(code));run.mkdir();(run/'logs').mkdir()
                for shard in range(2):
                    out=run/('features_worker_%02d'%shard);out.mkdir();c.write(out/'status.json',{'status':'COMPLETE'})
                progress=Progress()
                with mock.patch.object(runner.subprocess,'Popen',side_effect=lambda *args,**kwargs:Child(code)) as popen:
                    if code:
                        with self.assertRaisesRegex(RuntimeError,'WORKER_FAILED'):
                            runner.launch_features(root,run,{'feature_workers':2},progress)
                    else:runner.launch_features(root,run,{'feature_workers':2},progress)
                    self.assertEqual(popen.call_count,2)
                    command=popen.call_args_list[0].args[0]
                    self.assertIn('feature-worker',command);self.assertIn('--authorize-cache-rebuild',command)
                    self.assertNotIn('continuous_runner_v3.py',command)
                    self.assertTrue(all(x.kwargs['stdout'].closed for x in popen.call_args_list))
                self.assertTrue(progress.killed)
                self.assertEqual(c.read(run/'feature_worker_exit_codes.json'),{'0':code,'1':code})

    def test_main_passes_worker_authorizer_and_rejects_shard(self):
        command=['runner','feature-worker','--root','source','--run','output','--shard','1','--authorize-cache-rebuild']
        with mock.patch.object(runner.sys,'argv',command),\
             mock.patch.object(runner,'authorize_worker',return_value=({},{'feature_workers':2})) as auth,\
             mock.patch.object(runner.features,'feature_worker') as worker:
            runner.main()
            self.assertIs(worker.call_args.kwargs['authorization'],auth)
        command[command.index('1')]='2'
        with mock.patch.object(runner.sys,'argv',command),\
             mock.patch.object(runner,'authorize_worker',return_value=({},{'feature_workers':2})),\
             mock.patch.object(runner.features,'feature_worker') as worker,self.assertRaisesRegex(RuntimeError,'SHARD'):
            runner.main()
        worker.assert_not_called()

    def test_real_worker_progress_authorization_and_empty_shard_receipt(self):
        # An empty modulo shard is valid. Exercise the real worker/Progress API,
        # replacing only checkpoint/model construction (no model is used).
        with tempfile.TemporaryDirectory() as tmp:
            root,_,path,_,env=fixture(tmp);run=Path(tmp)/'result';run.mkdir()
            (run/'spool').mkdir()
            with closing(sqlite3.connect(str(run/'spool/snapshots.sqlite'))) as db:
                db.execute('CREATE TABLE snapshots(uid TEXT,role TEXT,slot INTEGER,body TEXT,batch_id INTEGER)')
                db.commit()
            c.write(run/'spool_pin.json',dict(sha256=c.sha(run/'spool/snapshots.sqlite')))
            c.write(run/'launch.json',dict(scope='CACHE_ONLY_P_E3_NORMALIZERS',root=str(root.resolve()),run=str(run.resolve()),
                design_sha256=c.DESIGN_SHA,resource_plan_path=str(path),resource_plan_sha256=c.sha(path),
                engineering_code=runner.code_identity(),package_seal_sha256=c.sha(root/'SHA256SUMS')))
            def synthetic_authorizer(root,run,explicit):
                design,runtime=runner.authorize_worker(root,run,explicit)
                return design,dict(runtime,synthetic_only=True)
            with mock.patch.dict(os.environ,env,clear=True),\
                 mock.patch.object(runner.features,'e3_runtime',return_value=(None,None,None,None,None)):
                runner.features.feature_worker(root,run,0,True,authorization=synthetic_authorizer)
            output=run/'features_worker_00';c.verify(output)
            self.assertEqual(c.read(output/'receipt.json')['rows'],0)
            self.assertEqual(c.read(output/'status.json')['status'],'COMPLETE')
            self.assertTrue((output/'resource_samples.jsonl').is_file())

    def test_real_merge_normalizer_and_progress_on_generated_arrays(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'result';run.mkdir();(run/'inputs').mkdir()
            def row(uid,fit_role,use='QUERY'):
                return dict(uid=uid,partition='LEARN',fit_role=fit_role,device='d0',protocol=6,
                    use=use,label=0,component_id=uid,timestamp=0. if use=='REFERENCE' else 2.,reference_end=1.)
            rows=[row('q0','FIT'),row('q1','FIT'),row('q2','CAL'),row('q3','CAL')]
            refs=[row('r0','FIT','REFERENCE'),row('r1','FIT','REFERENCE')]
            metadata=dict(LEARN=rows,SOURCE_REFS=refs)
            values=np.arange(6*794,dtype=np.float32).reshape(6,794)
            values[2:]*=100 # CAL/reference outliers must not enter the fit moments.
            old=values[:4,:768]+.25;np.save(run/'old.npy',old,allow_pickle=False)
            c.write(run/'inputs/old_features.json',dict(LEARN=str(run/'old.npy')))
            for role,indices in [('FIT',[0,1]),('CAL',[2,3])]:
                c.save_arrays(run/'inputs'/(role+'.npz'),indices=np.asarray(indices,dtype=np.int64))
            worker=run/'features_worker_00';block=worker/'block_000000';block.mkdir(parents=True)
            c.save_arrays(block/'values.npz',values=values,slots=np.asarray([0,1,2,3,0,1]),
                          roles=np.asarray(['LEARN']*4+['SOURCE_REFS']*2),uids=np.asarray([x['uid'] for x in rows+refs]))
            c.write(worker/'receipt.json',dict(status='COMPLETE',blocks=1));c.seal(worker)
            design=dict(data=dict(fit_cal_identity={role:dict(eligible_rows=2,
                eligible_uid_sha256=c.uid_sha(x['uid'] for x in rows if x['fit_role']==role)) for role in ('FIT','CAL')}))
            progress=runner.Progress(run/'monitor',dict(wall_seconds=120,memory_gib=4,disk_gib=1),storage_scope=run)
            try:
                runner.features.merge_features(run,metadata,dict(feature_workers=1))
                runner.original.prepare_normalizers(run,metadata,design,progress)
                progress.stop('COMPLETE')
            finally:
                if not progress.closed.is_set():progress.stop('STOPPED_NO_RETRY')
            c.verify(run/'features');c.verify(run/'normalizers')
            self.assertEqual(c.read(run/'monitor/status.json')['status'],'COMPLETE')
            for arm,x in [('OLD_MATCHED',old),('RECENT',values[:4,:768]),('RECENT_STATE',values[:4])]:
                with np.load(run/'normalizers'/(arm+'.npz'),allow_pickle=False) as saved:
                    np.testing.assert_array_equal(saved['mean'],x[:2].astype(np.float64).mean(0))
                    np.testing.assert_array_equal(saved['scale'],x[:2].astype(np.float64).std(0))
            with np.load(run/'normalizers/CAL_eligible.npz',allow_pickle=False) as saved:
                np.testing.assert_array_equal(saved['indices'],[2,3])

    def test_mocked_chain_has_only_cache_stages(self):
        class Progress:
            def __init__(self,*args,**kwargs):self.stage='';self.events=[]
            def tick(self):self.events.append(self.stage)
            def stop(self,status,**kwargs):self.final=status
            def record_failure(self,*args):pass
        with tempfile.TemporaryDirectory() as tmp:
            root,_,path,_,env=fixture(tmp);run=Path(tmp)/'result'
            before={str(x.relative_to(root)):c.sha(x) for x in root.rglob('*') if x.is_file()}
            def load(root,runtime,design,out):
                out.mkdir();c.write(out/'old_features.json',{});c.seal(out);return {},[]
            def spool(root,out,*args):
                out.mkdir();(out/'snapshots.sqlite').write_bytes(b'synthetic placeholder');c.seal(out)
            def seal_subfolder(run,name):
                out=run/name;out.mkdir();c.write(out/'receipt.json',dict(synthetic=True));c.seal(out)
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(runner,'environment',return_value={'synthetic':True}),\
                 mock.patch.object(runner,'Progress',Progress),mock.patch.object(runner.data,'load_inputs',side_effect=load),\
                 mock.patch.object(runner.audit,'preflight') as audit, mock.patch.object(runner.data,'old_tail_audit'),\
                 mock.patch.object(runner.features,'spool',side_effect=spool),mock.patch.object(runner.original,'numeric_probe') as probe,\
                 mock.patch.object(runner,'launch_features') as launch,\
                 mock.patch.object(runner.features,'merge_features',side_effect=lambda run,*args:seal_subfolder(run,'features')),\
                 mock.patch.object(runner.original,'prepare_normalizers',side_effect=lambda run,*args:seal_subfolder(run,'normalizers')),\
                 mock.patch.object(runner.original,'run_chain') as forbidden:
                runner.rebuild(root,run,path,True)
                audit.assert_called_once();probe.assert_called_once();launch.assert_called_once();forbidden.assert_not_called()
            receipt=c.read(run/'P_COMPLETE.json')
            self.assertEqual(receipt['real_optimizer_updates'],0);self.assertFalse(receipt['target_scoring'])
            self.assertFalse((run/'T_COMPLETE.json').exists());self.assertFalse((run/'launch_T.json').exists())
            self.assertEqual(before,{str(x.relative_to(root)):c.sha(x) for x in root.rglob('*') if x.is_file()})


if __name__=='__main__':unittest.main()
