"""Generated delivery checks; never decode PCAP, load E3 or score real inputs."""
import copy
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import continuous_common_v3 as c
import onboarding_delivery_v1 as delivery
import onboarding_resources_v1 as resources
import constrained_onboarding_reference_v2 as reference
import constrained_onboarding_query_tail_adapter_v2 as adapter
import constrained_onboarding_runner_v2 as runner
from test_constrained_onboarding_integration_v1 import fixture as scientific_fixture


SOURCE = Path(__file__).resolve().parents[2]
PROTOCOL_FILE = SOURCE/'protocol.json' if (SOURCE/'protocol.json').is_file() else SOURCE/'runs/onboarding_materials_and_protocol_20261015/protocol.json'
DESIGN_FILE = SOURCE/'query_tail_design.json' if (SOURCE/'query_tail_design.json').is_file() else SOURCE/'runs/legacy_query_tail_learning_design_v2_20261010/design_contract.json'


def fixture(tmp):
    """A sealed generated package; external files are inert test bytes only."""
    tmp = Path(tmp); root = tmp/'package'; root.mkdir()
    (root/'repo/ood').mkdir(parents=True)
    (root/'repo/ood/scientific_fixture.py').write_bytes(b'# generated test only\n')
    (root/'protocol.json').write_bytes(PROTOCOL_FILE.read_bytes())
    (root/'query_tail_design.json').write_bytes(DESIGN_FILE.read_bytes())
    (root/'evidence.json').write_bytes(b'{"scope":"SYNTHETIC_TEST_ONLY"}\n')
    evidence = [dict(path='evidence.json', sha256=c.sha(root/'evidence.json'))]
    def phase(value):
        return dict(basis='ESTIMATED', explanation='Synthetic arithmetic, not a production estimate',
            includes_mappings_and_temporary_buffers=True, evidence=copy.deepcopy(evidence),
            components=[dict(name='generated', gib_per_instance=value, instances=1, explanation='Generated')],
            simultaneous_peak_gib=value)
    plan = dict(schema=resources.SCHEMA, status='REVIEWABLE', processes=1, threads=4, cpus=8,
        concurrency_basis='Synthetic fixture', workload_identity=dict(protocol_sha256=delivery.PROTOCOL_SHA,
            query_tail_design_sha256=delivery.DESIGN_SHA, head_package_seal_sha256='1'*64,
            target_pools=list(delivery.POOLS), target_policies=['OLD_BANK']+list(delivery.POLICIES)),
        phases=dict(RAW_REFERENCE=phase(4.), E3_REFERENCE=phase(7.), HEAD_AND_MODULE=phase(12.)),
        margin_fraction=.25, memory_gib=16, guard_gib=14, disk_gib=4, minimum_free_gib=6,
        export_included_limit_gib=1, wall_seconds=82800, slurm_time='1-00:00:00',
        disk_basis='Synthetic fixture', time_basis='Synthetic fixture',
        state_storage=dict(resident_contexts=2, resident_legacy_prefixes=3, resident_candidate_snapshots=4))
    head_root = tmp/'head'; parent = tmp/'parent'; checkpoint = tmp/'checkpoint.bin'
    checkpoint.write_bytes(b'generated checkpoint placeholder')
    paths = dict(parent=str(parent), head_root=str(head_root), head_run=str(head_root/'runs/query_tail'),
                 checkpoint=str(checkpoint))
    runtime = dict(protocol_sha256=delivery.PROTOCOL_SHA, query_tail_design_sha256=delivery.DESIGN_SHA,
        arm='QUERY_TAIL', retries=0, optimizer_updates=0, head_package_seal_sha256='1'*64,
        paths=paths, versions={}, additional_required_packages=[], tshark='tshark', tshark_version='4.4.0',
        checkpoint_sha256=c.sha(checkpoint), normalizer_sha256='2'*64,
        scientific_code_sha256={'scientific_fixture.py':c.sha(root/'repo/ood/scientific_fixture.py')}, captures={})
    for field in ('cpus','memory_gib','guard_gib','disk_gib','minimum_free_gib','wall_seconds',
                  'export_included_limit_gib','state_storage','slurm_time'):
        runtime[field] = copy.deepcopy(plan[field])
    for pool in delivery.POOLS:
        raw = tmp/(pool+'.pcap'); raw.write_bytes(b'not a pcap: generated test bytes')
        runtime['captures'][pool] = dict(capture=dict(path=str(raw),sha256=c.sha(raw),bytes=raw.stat().st_size,
            expected_packets=1,capture_id=pool,t0=1.,provenance='normal',normality_evidence='SYNTHETIC_TEST_ONLY',
            known_macs=['owner']),device_registry=[dict(owner='owner',device='device',partition='DEV')])
    c.write(root/'resource_plan.json',plan)
    runtime['resource_plan_sha256'] = c.sha(root/'resource_plan.json')
    c.write(root/'runtime_contract.json',runtime); c.seal(root)
    env = dict(SLURM_JOB_ID='SYNTHETIC', SLURM_CPUS_PER_TASK='8', SLURM_MEM_PER_NODE='16384',
        SLURM_JOB_NUM_NODES='1', ONBOARDING_RESOURCE_SHA=c.sha(root/'resource_plan.json'),
        OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
    return root,runtime,plan,env


def rewrite(root, runtime=None, plan=None):
    """Reseal only this test's temporary fixture after an intentional change."""
    (root/'SHA256SUMS').unlink()
    if plan is not None:
        c.write(root/'resource_plan.json',plan,replace=True)
        if runtime is not None: runtime['resource_plan_sha256']=c.sha(root/'resource_plan.json')
    if runtime is not None: c.write(root/'runtime_contract.json',runtime,replace=True)
    c.seal(root)


def launch_fixture(root, runtime, name):
    run = root/'runs/onboarding'; run.mkdir(parents=True)
    c.write(run/'launch.json',dict(stages=list(delivery.STAGES),arm=runtime['arm'],
        package_seal_sha256=c.sha(root/'SHA256SUMS'),resource_plan_sha256=c.sha(root/'resource_plan.json'),
        head_run=runtime['paths']['head_run'],optimizer_updates=0,retries=0))
    c.write(run/'stage_launch.json',dict(stage=name,resource_plan_sha256=c.sha(root/'resource_plan.json'),remaining_disk_gib=3.))
    c.write(run/'preflight.json',dict(tshark='synthetic-tshark'))
    return run


class ResourceContractTests(unittest.TestCase):
    def test_sequential_peak_allocation_and_allocation_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,plan,env=fixture(tmp)
            with mock.patch.dict(os.environ,env,clear=True):
                got,actual=delivery.load_contract(root,True)
            self.assertEqual(got,runtime);self.assertEqual(actual,plan)
            wrong=copy.deepcopy(plan);wrong['memory_gib']=30
            with self.assertRaisesRegex(RuntimeError,'ALLOCATION'):resources.validate(wrong)

    def test_evidence_is_pinned_and_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,plan,_=fixture(tmp)
            (root/'evidence.json').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'):resources.load(root/'resource_plan.json')
            plan['phases']['RAW_REFERENCE']['evidence'][0]['path']='../outside.json'
            c.write(root/'resource_plan.json',plan,replace=True)
            with self.assertRaisesRegex(RuntimeError,'ESCAPE'):resources.load(root/'resource_plan.json')

    def test_pending_component_guard_and_disk_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,plan,_=fixture(tmp)
            changes=[('status','PENDING'),('guard_gib',12),('guard_gib',16),('minimum_free_gib',5),
                     ('margin_fraction',float('nan')),('wall_seconds',86400),('processes',2)]
            for field,value in changes:
                wrong=copy.deepcopy(plan);wrong[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(RuntimeError):resources.validate(wrong)
            wrong=copy.deepcopy(plan);wrong['phases']['RAW_REFERENCE']['simultaneous_peak_gib']=5
            with self.assertRaisesRegex(RuntimeError,'COMPONENT_SUM'):resources.validate(wrong)

    def test_runtime_and_workload_cannot_drift_after_resealing(self):
        cases=[('guard_gib',13),('arm','QUERY_BCE'),('optimizer_updates',1),('retries',1),('resource_plan_sha256','0'*64)]
        for field,value in cases:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root,runtime,_,_=fixture(tmp);runtime[field]=value;rewrite(root,runtime)
                with self.assertRaises(RuntimeError):delivery.load_contract(root)
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,plan,_=fixture(tmp)
            plan['workload_identity']['target_policies']=['OLD_BANK'];rewrite(root,runtime,plan)
            with self.assertRaisesRegex(RuntimeError,'WORKLOAD_IDENTITY'):delivery.load_contract(root)

    def test_scientific_file_pin_survives_outer_reseal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,_=fixture(tmp)
            (root/'repo/ood/scientific_fixture.py').write_bytes(b'changed')
            rewrite(root,runtime)
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'):delivery.load_contract(root)

    def test_slurm_plan_cpu_memory_and_node_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_,_,env=fixture(tmp)
            for key,value in [('SLURM_JOB_ID',''),('ONBOARDING_RESOURCE_SHA','bad'),
                ('SLURM_CPUS_PER_TASK','16'),('SLURM_MEM_PER_NODE','32768'),('SLURM_JOB_NUM_NODES','2')]:
                with self.subTest(key=key),mock.patch.dict(os.environ,dict(env,**{key:value}),clear=True),self.assertRaises(RuntimeError):
                    delivery.load_contract(root,True)

    def test_input_root_containment_and_fixed_head_directory(self):
        for mode in ('parent_inside','parent_ancestor','raw_inside','head_outside_expected'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root,runtime,_,_=fixture(tmp)
                if mode=='parent_inside':runtime['paths']['parent']=str(root/'parent')
                elif mode=='parent_ancestor':runtime['paths']['parent']=str(root.parent)
                elif mode=='raw_inside':runtime['captures']['CIC_DEV']['capture']['path']=str(root/'raw.pcap')
                else:runtime['paths']['head_run']=str(root.parent/'other')
                rewrite(root,runtime)
                with self.assertRaises(RuntimeError):delivery.load_contract(root)


class StageTests(unittest.TestCase):
    def test_no_authorization_touches_no_assets(self):
        with mock.patch.object(delivery,'load_contract') as loaded,self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'):
            delivery.run('/does/not/exist',False)
        loaded.assert_not_called()
        with mock.patch.object(delivery.sys,'argv',['onboarding','stage','--root','/missing','--name','evaluate']),\
             mock.patch.object(delivery,'stage') as stage,self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'):
            delivery.main()
        stage.assert_not_called()

    def test_bad_stage_launch_and_plan_rejected_before_producer(self):
        for field,value in [('stage','evaluate'),('resource_plan_sha256','0'*64),
                            ('remaining_disk_gib',0.),('remaining_disk_gib',5.)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root,runtime,_,env=fixture(tmp);run=launch_fixture(root,runtime,'raw-CIC_DEV')
                launch=c.read(run/'stage_launch.json');launch[field]=value;c.write(run/'stage_launch.json',launch,replace=True)
                with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(reference,'prepare_raw_capture') as raw,\
                     self.assertRaisesRegex(RuntimeError,'STAGE_'):
                    delivery.stage(root,'raw-CIC_DEV')
                raw.assert_not_called()

    def test_stale_parent_launch_cannot_start_producer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);run=launch_fixture(root,runtime,'raw-CIC_DEV')
            launch=c.read(run/'launch.json');launch['package_seal_sha256']='0'*64
            c.write(run/'launch.json',launch,replace=True)
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(reference,'prepare_raw_capture') as raw,\
                 self.assertRaisesRegex(RuntimeError,'STAGE_IDENTITY'):
                delivery.stage(root,'raw-CIC_DEV')
            raw.assert_not_called()

    def test_raw_gets_fixed_capture_state_and_remaining_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,plan,env=fixture(tmp);run=launch_fixture(root,runtime,'raw-UNSW_DEV')
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(reference,'prepare_raw_capture') as raw:
                delivery.stage(root,'raw-UNSW_DEV')
            config,out=raw.call_args.args
            self.assertEqual(config['capture'],runtime['captures']['UNSW_DEV']['capture'])
            self.assertEqual(config['state_storage'],plan['state_storage'])
            self.assertEqual(config['limits']['disk_gib'],3.)
            self.assertEqual(config['limits']['memory_gib'],plan['guard_gib'])
            self.assertEqual(out,run/'raw/UNSW_DEV')

    def test_encode_pins_selected_receipt_and_frozen_normalizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);run=launch_fixture(root,runtime,'encode-CIC_DEV-B2')
            prepared=run/'raw/CIC_DEV/prepared/B2';prepared.mkdir(parents=True)
            c.write(prepared/'receipt.json',{'fixture':True})
            c.write(run/'encoder_runtime_identity.json',{'manifest_sha256':'3'*64})
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(reference,'encode_selected') as encode:
                delivery.stage(root,'encode-CIC_DEV-B2')
            got,out,config=encode.call_args.args
            self.assertEqual(got,prepared);self.assertEqual(out,run/'encoded/CIC_DEV/B2')
            self.assertEqual(config['prepared_receipt_sha256'],c.sha(prepared/'receipt.json'))
            self.assertEqual(config['runtime_manifest_sha256'],'3'*64)
            self.assertEqual(config['normalizer_sha256'],runtime['normalizer_sha256'])

    def test_evaluation_uses_one_head_one_fit_all_policies_and_pending_third_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);run=launch_fixture(root,runtime,'evaluate')
            c.write(run/'banks_manifest.json',{'pools':{}})
            bundle=scientific_fixture()
            def attach(got,path):
                self.assertIs(got,bundle);self.assertEqual(path,run/'banks_manifest.json')
                for target in got['targets'].values():
                    bank=copy.deepcopy(target['banks']['B1']);bank['preparation_receipt']['policy']='B2'
                    target['banks']['B2']=bank
                return got
            original_support=runner.support_for;observed=[]
            def support(bank,data,geometry,override=None):
                if data['rows'][0]['partition'] != 'LEARN':
                    c.verify(run/'evaluation/calibration')
                    observed.append(data['rows'][0]['partition'])
                return original_support(bank,data,geometry,override)
            with mock.patch.dict(os.environ,env,clear=True),\
                 mock.patch.object(adapter,'prepare_query_tail',return_value=bundle) as prepare,\
                 mock.patch.object(runner,'attach_reference_banks',side_effect=attach) as attach_call,\
                 mock.patch.object(runner.core,'fit_geometry',wraps=runner.core.fit_geometry) as geometry,\
                 mock.patch.object(runner.core,'fit_scales',wraps=runner.core.fit_scales) as scales,\
                 mock.patch.object(runner.core,'choose_lambda',wraps=runner.core.choose_lambda) as protect,\
                 mock.patch.object(runner,'support_for',side_effect=support):
                delivery.stage(root,'evaluate')
            prepare.assert_called_once_with(runtime['paths']['parent'],runtime['paths']['head_run'],
                root/'query_tail_design.json',arm='QUERY_TAIL')
            attach_call.assert_called_once();geometry.assert_called_once();scales.assert_called_once();protect.assert_called_once()
            self.assertTrue(observed)
            result=c.read(run/'evaluation/result.json')
            self.assertEqual(set(result['scientific_decisions']),{'OLD_BANK',*delivery.POLICIES})
            self.assertEqual(result['optimizer_updates'],0)
            for decision in result['scientific_decisions'].values():
                self.assertEqual(decision['status'],'PENDING')
                self.assertIn('CIC_THREE_DEVICE_REGRESSION_CONSUMED',decision['missing_evidence'])
            for pool in delivery.POOLS:
                self.assertTrue((run/'evaluation'/pool/'B1/equivalence.json').is_file())
            c.verify(run/'evaluation')

    def test_evaluation_refuses_incomplete_banks_before_source_fitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);launch_fixture(root,runtime,'evaluate');bundle=scientific_fixture()
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(adapter,'prepare_query_tail',return_value=bundle),\
                 mock.patch.object(runner,'attach_reference_banks'),mock.patch.object(runner,'run_development') as evaluate,\
                 self.assertRaisesRegex(RuntimeError,'INCOMPLETE_BANK_MATRIX'):
                delivery.stage(root,'evaluate')
            evaluate.assert_not_called()

    def test_wrapper_cannot_promote_missing_third_pool_to_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);launch_fixture(root,runtime,'evaluate');bundle=scientific_fixture()
            for target in bundle['targets'].values():target['banks']['B2']=copy.deepcopy(target['banks']['B1'])
            result=dict(status='COMPLETE',optimizer_updates=0,automatic_model_selection=False,
                        scientific_decisions={'OLD_BANK':dict(status='PASS')})
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(adapter,'prepare_query_tail',return_value=bundle),\
                 mock.patch.object(runner,'attach_reference_banks'),mock.patch.object(runner,'run_development',return_value=result),\
                 self.assertRaisesRegex(RuntimeError,'MISSING_REGRESSION_CANNOT_PASS'):
                delivery.stage(root,'evaluate')

    def test_encoder_runtime_copies_only_into_private_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,_=fixture(tmp);run=root/'runs/onboarding';run.mkdir(parents=True)
            for name in ('netFound','netFound-base'):
                folder=root/'vendor'/name;folder.mkdir(parents=True);(folder/'config.json').write_bytes(b'{}')
            before=Path(runtime['paths']['checkpoint']).read_bytes()
            delivery.make_encoder_runtime(root,run,runtime)
            model=run/'encoder_runtime/vendor/netFound-base/model.safetensors'
            self.assertEqual(model.read_bytes(),before);self.assertFalse(model.is_symlink())
            self.assertFalse((root/'vendor/netFound-base/model.safetensors').exists())
            self.assertEqual(Path(runtime['paths']['checkpoint']).read_bytes(),before)
            c.verify(run/'encoder_runtime')

    def test_bank_manifest_requires_all_real_policy_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)
            for pool in delivery.POOLS:
                for policy in delivery.POLICIES:
                    folder=run/'encoded'/pool/policy;folder.mkdir(parents=True)
                    c.write(folder/'receipt.json',dict(status='COMPLETE',synthetic_only=False,policy=policy))
            delivery.make_banks_manifest(run)
            manifest=c.read(run/'banks_manifest.json')
            self.assertEqual(set(manifest['pools']),set(delivery.POOLS))
            for pool,policies in manifest['pools'].items():
                self.assertEqual(set(policies),set(delivery.POLICIES))
                for policy,spec in policies.items():
                    self.assertEqual(spec['wrong_reference_controls'],[])
                    self.assertEqual(spec['receipt_sha256'],c.sha(run/spec['path']/'receipt.json'))
            self.assertIn('NOT_AVAILABLE',c.read(run/'bank_controls_status.json')['controls_status'])


class ChainTests(unittest.TestCase):
    def test_full_chain_order_one_evaluation_and_no_real_producers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);names=[]
            def child(root,run,name,runtime,plan,started):
                names.append(name)
                if name=='evaluate':
                    (run/'evaluation').mkdir()
                    c.write(run/'evaluation/result.json',dict(scientific_decisions={p:dict(status='PENDING')
                        for p in ('OLD_BANK',*delivery.POLICIES)}))
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(delivery,'preflight',return_value={'test':True}),\
                 mock.patch.object(reference,'_environment',return_value={'test':True}),\
                 mock.patch.object(delivery,'make_encoder_runtime'),mock.patch.object(delivery,'make_banks_manifest') as manifest,\
                 mock.patch.object(delivery,'launch_stage',side_effect=child):
                delivery.run(root,True)
            self.assertEqual(names,list(delivery.STAGES));self.assertEqual(len(names),9)
            self.assertEqual(names[-1],'evaluate');self.assertEqual(names.count('evaluate'),1);manifest.assert_called_once()
            run=root/'runs/onboarding';complete=c.read(run/'COMPLETE.json')
            self.assertEqual(complete['required_three_device_regression'],'NOT_RUN')
            self.assertEqual(complete['optimizer_updates'],0);self.assertEqual(complete['independent_confirmation'],'NOT_RUN')
            with mock.patch.dict(os.environ,env,clear=True),self.assertRaisesRegex(RuntimeError,'RUN_EXISTS_NO_RETRY'):
                delivery.run(root,True)

    def test_preflight_failure_starts_no_chain_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_,_,env=fixture(tmp)
            with mock.patch.dict(os.environ,env,clear=True),\
                 mock.patch.object(delivery,'preflight',side_effect=RuntimeError('MISSING_PARENT')),\
                 mock.patch.object(delivery,'launch_stage') as launch,self.assertRaisesRegex(RuntimeError,'MISSING_PARENT'):
                delivery.run(root,True)
            self.assertFalse((root/'runs/onboarding').exists());launch.assert_not_called()

    def test_child_failure_stops_and_preserves_no_retry_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_,_,env=fixture(tmp)
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(delivery,'preflight',return_value={}),\
                 mock.patch.object(reference,'_environment',return_value={}),mock.patch.object(delivery,'make_encoder_runtime'),\
                 mock.patch.object(delivery,'launch_stage',side_effect=RuntimeError('SYNTHETIC_CHILD_FAILURE')) as launch,\
                 self.assertRaisesRegex(RuntimeError,'SYNTHETIC_CHILD_FAILURE'):
                delivery.run(root,True)
            self.assertEqual(launch.call_count,1)
            status=c.read(root/'runs/onboarding/status.json')
            self.assertEqual(status['status'],'STOPPED_NO_RETRY');self.assertEqual(status['retries'],0)
            self.assertFalse((root/'runs/onboarding/COMPLETE.json').exists())

    def test_symlinked_runs_cannot_redirect_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,_,env=fixture(tmp);parent=Path(runtime['paths']['parent']);parent.mkdir()
            link=root/'runs'
            if os.name=='nt':
                import _winapi
                _winapi.CreateJunction(str(parent),str(link))
            else:link.symlink_to(parent,target_is_directory=True)
            try:
                with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(delivery,'preflight',return_value={}),\
                     mock.patch.object(delivery,'make_encoder_runtime') as encoder,self.assertRaisesRegex(RuntimeError,'OVERLAP|ESCAPE|SYMLINK|REDIRECTED'):
                    delivery.run(root,True)
                encoder.assert_not_called();self.assertFalse((parent/'onboarding').exists())
            finally:
                # Remove only the exact test-created link, never its destination.
                if os.name=='nt':os.rmdir(link)
                else:link.unlink()


class MonitorTests(unittest.TestCase):
    class Child:
        pid=987654
        def __init__(self,code):self.returncode=code
        def poll(self):return self.returncode
        def wait(self,timeout=None):return self.returncode

    def test_child_command_success_and_nonzero_failure(self):
        for code in (0,7):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as tmp:
                root,runtime,plan,_=fixture(tmp);run=root/'runs/onboarding';(run/'logs').mkdir(parents=True)
                with mock.patch.object(delivery.subprocess,'Popen',return_value=self.Child(code)) as popen,\
                     mock.patch.object(delivery,'tree_rss',return_value=1024),mock.patch.object(delivery,'terminate_group') as terminate:
                    if code:
                        with self.assertRaisesRegex(RuntimeError,'STAGE_FAILED'):
                            delivery.launch_stage(root,run,'evaluate',runtime,plan,time.monotonic())
                        terminate.assert_called_once()
                    else:delivery.launch_stage(root,run,'evaluate',runtime,plan,time.monotonic())
                command=popen.call_args.args[0]
                self.assertIn('--authorize-chain',command);self.assertIn('-B',command);self.assertIn('stage',command)
                self.assertTrue(popen.call_args.kwargs['stdout'].closed)
                status=c.read(run/'monitor/evaluate/status.json')
                self.assertEqual(status['status'],'STOPPED_NO_RETRY' if code else 'COMPLETE')

    def test_memory_breach_terminates_child_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,runtime,plan,_=fixture(tmp);run=root/'runs/onboarding';(run/'logs').mkdir(parents=True)
            with mock.patch.object(delivery.subprocess,'Popen',return_value=self.Child(None)) as popen,\
                 mock.patch.object(delivery,'tree_rss',return_value=15*1024**3),\
                 mock.patch.object(delivery,'terminate_group') as terminate,\
                 self.assertRaisesRegex(RuntimeError,'COMBINED_MEMORY_LIMIT'):
                delivery.launch_stage(root,run,'encode-CIC_DEV-B0',runtime,plan,time.monotonic())
            self.assertEqual(popen.call_count,1);terminate.assert_called_once()
            self.assertEqual(c.read(run/'monitor/encode-CIC_DEV-B0/status.json')['retries'],0)


if __name__=='__main__':
    unittest.main()
