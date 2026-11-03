"""Incremental P2/P3/P5/P6 checks with generated paths and mocked heavy work."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import modern_head_runner_v1 as r
import modern_head_train_v1 as trainer
import modern_head_evaluate_v1 as evaluation
from test_modern_head_evaluate_v1 import config as evaluation_config, DESIGN


class RevisionRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.old=self.root/'old'; self.old.mkdir()
        (self.old/'prepared').mkdir(); (self.old/'prepared/SHA256SUMS').write_text('generated')
        self.config={'synthetic_only':True}; self.runtime={'paths':{}}
        self.plan={'minimum_free_gib':0}
        for file in ('experiment_contract.json','resource_plan.json','query_tail_design.json'):
            r.c.write(self.root/file,{})
        self.banks=self.root/'generated_banks'; self.banks.mkdir()
        r.c.write(self.banks/'banks_manifest.json',dict(synthetic=True))
        self.calls=[]

    def fake_stage(self,root,run,name,plan,started):
        self.calls.append(name)
        if name=='P':
            r.c.write(run/'heads/P_COMPLETE.json',dict(status='COMPLETE',config_digest=r.c.digest(self.config)))
        elif name.startswith('T_'):
            folder=run/'heads/endpoints'/name[2:]; folder.mkdir()
            r.c.write(folder/'endpoint.json',dict(status='COMPLETE',id=name))
        elif name=='K':
            r.c.write(run/'heads/decision.json',{'generated':True})
            r.c.write(run/'heads/K_COMPLETE.json',dict(status='COMPLETE',config_digest=r.c.digest(self.config),decision_sha256=r.c.sha(run/'heads/decision.json')))
            r.c.seal(run/'heads')

    def run_mode(self,heads=False,modules=False):
        with patch.object(r,'contract',return_value=(self.config,self.runtime,self.plan)),patch.object(r,'preflight'),patch.object(r,'inputs_module',return_value=self.banks),patch.object(r,'launch',side_effect=self.fake_stage):
            r.run(self.root,True,heads,modules)
        return self.root/'runs/modern_heads'

    def test_heads_preflight_does_not_touch_missing_onboarding(self):
        with patch.object(r,'contract',return_value=(self.config,self.runtime,self.plan)),patch.object(r,'dependency_check'),patch.object(r,'inputs_head',return_value=(self.root,self.old)),patch.object(r,'inputs_module',side_effect=AssertionError('bank access')):
            result=r.preflight(self.root,heads_only=True)
        self.assertEqual(result['execution_mode'],'heads')
        self.assertNotIn('banks_manifest_sha256',result)

    def test_module_and_full_preflight_require_banks(self):
        for modules in (False,True):
            with patch.object(r,'contract',return_value=(self.config,self.runtime,self.plan)),patch.object(r,'dependency_check'),patch.object(r,'inputs_head',return_value=(self.root,self.old)),patch.object(r,'inputs_module',side_effect=RuntimeError('MISSING_BANKS')):
                with self.assertRaisesRegex(RuntimeError,'MISSING_BANKS'):
                    r.preflight(self.root,modules_only=modules)

    def test_heads_then_modules_never_retrain_or_mutate_sealed_heads(self):
        run=self.run_mode(heads=True)
        self.assertEqual(self.calls,list(r.HEAD_STAGES)); self.assertFalse((run/'COMPLETE.json').exists())
        self.assertEqual(r.c.read(run/'status.json')['status'],'HEADS_COMPLETE_MODULES_PENDING')
        before=r.c.sha(run/'heads/SHA256SUMS'); self.calls=[]
        self.run_mode(modules=True)
        self.assertEqual(self.calls,list(r.MODULE_STAGES)); self.assertEqual(before,r.c.sha(run/'heads/SHA256SUMS'))
        r.c.verify(run/'heads'); self.assertTrue((run/'COMPLETE.json').exists())
        self.assertEqual(r.c.read(run/'head_status.json')['status'],'COMPLETE')

    def test_modules_refuse_missing_heads(self):
        with self.assertRaises(FileNotFoundError): self.run_mode(modules=True)
        self.assertEqual(self.calls,[])

    def test_modules_refuse_tampered_heads(self):
        run=self.run_mode(heads=True); self.calls=[]
        (run/'heads/decision.json').write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'IDENTITY'): self.run_mode(modules=True)
        self.assertEqual(self.calls,[])

    def test_modules_cannot_be_repeated(self):
        self.run_mode(heads=True); self.run_mode(modules=True); self.calls=[]
        with self.assertRaisesRegex(RuntimeError,'MODULES_NO_RETRY'): self.run_mode(modules=True)
        self.assertEqual(self.calls,[])

    def test_module_failure_preserves_heads_and_prevents_restart(self):
        run=self.run_mode(heads=True); before=r.c.sha(run/'heads/SHA256SUMS')
        with patch.object(r,'contract',return_value=(self.config,self.runtime,self.plan)),patch.object(r,'preflight'),patch.object(r,'inputs_module',return_value=self.banks),patch.object(r,'launch',side_effect=RuntimeError('M_FAIL')):
            with self.assertRaisesRegex(RuntimeError,'M_FAIL'): r.run(self.root,True,modules_only=True)
        self.assertEqual(r.c.sha(run/'heads/SHA256SUMS'),before)
        self.assertEqual(r.c.read(run/'module_status.json')['status'],'STOPPED_NO_RETRY')
        self.assertTrue((run/'MODULES_STARTED.json').exists())

    def test_modes_cannot_be_combined(self):
        with self.assertRaisesRegex(RuntimeError,'MODE_CONFLICT'): r.execution_mode(True,True)

    def prepare_fixture(self,precondition='PASS',recorded_equal=True):
        run=self.root/'generated_run'; (run/'heads').mkdir(parents=True)
        r.c.write(self.old/'numeric_runtime.json',{'fixture':True})
        (self.old/'SHA256SUMS').write_text('0'*64+'  numeric_runtime.json\n')
        for seed in r.c.SEEDS:
            path=self.old/'endpoints'/('QUERY_BCE_'+str(seed)); path.mkdir(parents=True)
            r.c.write(path/'endpoint.json',{'head_sha256':'a'*64})
        pools={pool:{'heads':{str(seed):{'score':{'bitwise_equal':recorded_equal},'decision':{'bitwise_equal':True}} for seed in r.c.SEEDS}} for pool in ('CAL','CIC_DEV','UNSW_DEV')}
        replay={'schema':'generated-proof','pools':pools}
        bundle={'replay_evidence':replay,'source_fit':{'rows':[{'uid':'fit1'}],'e3':np.zeros((1,768),dtype=np.float32),'q14':np.zeros((1,14),dtype=np.float32)},'normalizer':(np.zeros(768),np.ones(768))}
        verdict={'status':precondition,'reason':'FIXTURE_INCOMPATIBLE'}
        with patch.object(r,'inputs_head',return_value=(self.root,self.old)),patch.object(r.prepare,'load_metadata',return_value=({},{})),patch.object(r.prepare,'arrays',return_value=({},None)),patch.object(r.prior,'_prepared_inputs'),patch.object(r,'environment',return_value={'fixture':True}),patch.object(r.prior,'prepare_query_tail',return_value=bundle),patch.object(trainer,'reuse_mlp_preconditions',return_value=verdict) as check:
            r.prepare_phase(self.root,run,self.config,self.runtime,None)
            self.assertEqual(check.call_count,3)
        return run,replay

    def test_reuse_plan_carries_adapter_output_and_computed_comparisons(self):
        run,replay=self.prepare_fixture()
        stored=r.c.read(run/'heads/reuse_adapter_replay.json'); self.assertEqual(stored,replay)
        proof=r.c.read(run/'heads/reuse_plan.json')['proofs']['27']
        self.assertEqual(proof['score_and_decision_bitwise']['CAL'],stored['pools']['CAL']['heads']['27']['score']['bitwise_equal'])
        self.assertEqual(proof['adapter_replay_evidence'],stored)
        self.assertEqual(proof['adapter_replay_sha256'],r.c.sha(run/'heads/reuse_adapter_replay.json'))

    def test_false_adapter_comparison_cannot_be_recorded_as_reuse_success(self):
        run,_=self.prepare_fixture(recorded_equal=False)
        plan=r.c.read(run/'heads/reuse_plan.json')
        self.assertEqual(plan['status'],'TRAIN_REQUIRED')
        self.assertFalse(plan['replay_checks']['27']['CAL'])

    def test_reuse_precondition_failure_records_train_required(self):
        run,_=self.prepare_fixture(precondition='TRAIN_REQUIRED')
        reuse=r.c.read(run/'heads/reuse_plan.json')
        self.assertEqual(reuse['status'],'TRAIN_REQUIRED'); self.assertNotIn('proofs',reuse)
        self.assertTrue((run/'heads/P_COMPLETE.json').exists())

    def test_module_optimizer_update_guard(self):
        import modern_head_onboarding_v1 as adapter
        import constrained_onboarding_runner_v2 as module
        run=self.run_mode(heads=True)
        heads=r.verified_heads(run,self.config)
        r.c.write(run/'MODULES_STARTED.json',dict(config_digest=r.c.digest(self.config),head_seal_sha256=heads['head_seal_sha256'],banks_manifest_sha256=r.c.sha(self.banks/'banks_manifest.json')))
        runtime={'paths':{'parent':str(self.root.parent/'generated_parent'),'prepared_run':str(self.root.parent/'generated_old'),'onboarding_root':str(self.root.parent/'generated_bank')}}
        real_pin=r.c.pin
        def pinned(path,digest):
            return path if str(path).endswith('banks_manifest.json') else real_pin(path,digest)
        bundle={'targets':{pool:{'banks':{k:{} for k in ('OLD_BANK','B0','B1','B2')}} for pool in ('CIC_DEV','UNSW_DEV')}}
        r.c.write(run/'stage_launch.json',dict(stage='M_TabM',resource_plan_sha256=r.c.sha(self.root/'resource_plan.json'),contract_sha256=r.c.sha(self.root/'experiment_contract.json')))
        for updates in (1,None):
            result=dict(status='COMPLETE',optimizer_updates=updates,automatic_model_selection=False,scientific_decisions={'x':{'status':'PENDING'}})
            with patch.object(r,'contract',return_value=(self.config,runtime,self.plan)),patch.object(r,'dependency_check'),patch.object(r.c,'pin',side_effect=pinned),patch.object(adapter,'prepare_modern',return_value=bundle),patch.object(module,'attach_reference_banks'),patch.object(module,'run_development',return_value=result):
                with self.assertRaisesRegex(RuntimeError,'NO_OPTIMIZER_UPDATES'): r.stage(self.root,'M_TabM')


class ScopeTextTests(unittest.TestCase):
    def test_only_description_changes_and_all_numeric_gates_remain_pinned(self):
        inherited=r.c.read(DESIGN); fixed=evaluation.modern_gates(inherited)
        reverted=copy.deepcopy(fixed); reverted['additional_regression']['applies_to']=inherited['gates']['additional_regression']['applies_to']
        self.assertEqual(reverted,inherited['gates'])
        config=evaluation_config(); evaluation.validate_config(config,inherited)
        config['gates']['common_inherited']['normal_weighted_FPR_each_pool_max']=.02
        with self.assertRaisesRegex(RuntimeError,'INHERITED_GATES'): evaluation.validate_config(config,inherited)

    def test_legacy_narrow_scope_text_rejected(self):
        inherited=r.c.read(DESIGN); config=evaluation_config(); config['gates']=inherited['gates']
        with self.assertRaisesRegex(RuntimeError,'INHERITED_GATES'): evaluation.validate_config(config,inherited)


if __name__=='__main__': unittest.main()
