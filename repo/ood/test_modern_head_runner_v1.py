"""Generated orchestration/identity failures; never run production stages."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import modern_head_runner_v1 as r
import modern_head_resources_v1 as resources

ROOT=Path(os.environ.get('MODERN_TEST_ROOT',Path(__file__).resolve().parents[2]/'runs/modern_head_comparison_v1_20261018/bundle'))


class DeliveryTests(unittest.TestCase):
    def test_fixed_stage_matrix(self):
        self.assertEqual(len(r.STAGES),13)
        self.assertEqual(r.STAGES[:2],('P','T_MLP_QUERY_BCE_27'))
        self.assertEqual(r.STAGES[-3:],('K','M_TabM','M_LightGBM'))

    def test_frozen_bundle_resources(self):
        config,runtime,plan=r.contract(ROOT)
        self.assertEqual(config['seeds'],[27,127,227])
        self.assertEqual(plan['memory_gib'],16)

    def test_bad_allocation_cannot_start(self):
        with patch.dict(os.environ,{'SLURM_JOB_ID':'fake','MODERN_HEAD_AUTHORIZED':'0'*64},clear=True):
            with self.assertRaisesRegex(RuntimeError,'MODERN_SUBMITTED_IDENTITY'): r.contract(ROOT,True)

    def test_output_cannot_overlap_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(RuntimeError,'INPUT_OUTPUT_OVERLAP'):
                r.scope(root,{'paths':{'parent':str(root/'runs/modern_heads/source')}})

    def test_seal_detects_script_modification(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)/'bundle'; shutil.copytree(ROOT,dst,ignore=shutil.ignore_patterns('wheelhouse'))
            # Verify a small private sealed fixture, without duplicating dependency wheels.
            (dst/'SHA256SUMS').unlink(); r.c.seal(dst)
            (dst/'scripts/run.slurm').write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'): r.contract(dst)

    def test_wrong_stage_receipt_rejected_before_training(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); run=root/'runs/modern_heads'; run.mkdir(parents=True)
            r.c.write(run/'stage_launch.json',dict(stage='K'))
            (root/'resource_plan.json').write_text('{}'); (root/'experiment_contract.json').write_text('{}')
            with patch.object(r,'contract',return_value=({}, {'paths':{}}, {})),patch.object(r,'dependency_check'):
                with self.assertRaisesRegex(RuntimeError,'MODERN_STAGE_LAUNCH'): r.stage(root,'T_TabM_27')

    def run_fixture(self,fail=None):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root=Path(tmp.name)
        (root/'resource_plan.json').write_text('{}'); (root/'experiment_contract.json').write_text('{}')
        banks=root/'generated_banks'; banks.mkdir(); r.c.write(banks/'banks_manifest.json',dict(synthetic=True))
        config={'synthetic_only':True}
        calls=[]
        def stage(root,run,name,plan,started):
            calls.append(name)
            if name==fail: raise RuntimeError('generated-stage-failure')
            if name=='P': r.c.write(run/'heads/P_COMPLETE.json',dict(status='COMPLETE',config_digest=r.c.digest(config)))
            if name.startswith('T_'):
                out=run/'heads/endpoints'/name[2:]; out.mkdir(); r.c.write(out/'endpoint.json',dict(status='COMPLETE',id=name))
            if name=='K':
                r.c.write(run/'heads/decision.json',dict(synthetic=True))
                r.c.write(run/'heads/K_COMPLETE.json',dict(status='COMPLETE',config_digest=r.c.digest(config),decision_sha256=r.c.sha(run/'heads/decision.json')))
                r.c.seal(run/'heads')
        with patch.object(r,'contract',return_value=(config,{'paths':{}},{})),patch.object(r,'preflight'),patch.object(r,'inputs_module',return_value=banks),patch.object(r,'launch',side_effect=stage):
            if fail:
                with self.assertRaisesRegex(RuntimeError,'generated-stage-failure'): r.run(root,True)
            else: r.run(root,True)
        return root/'runs/modern_heads',calls

    def test_complete_chain_and_frozen_endpoint_count(self):
        run,calls=self.run_fixture()
        self.assertEqual(calls,list(r.STAGES))
        self.assertEqual(len(r.c.read(run/'heads/T_COMPLETE.json')['endpoints']),9)
        self.assertFalse(r.c.read(run/'COMPLETE.json')['automatic_selection'])

    def test_failed_training_stops_remaining_heads_and_module(self):
        run,calls=self.run_fixture('T_TabM_27')
        self.assertEqual(calls[-1],'T_TabM_27')
        self.assertNotIn('K',calls)
        self.assertFalse((run/'COMPLETE.json').exists())
        self.assertEqual(r.c.read(run/'status.json')['status'],'STOPPED_NO_RETRY')

    def test_no_authorization_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'EXPLICIT_CHAIN_REQUIRED'): r.run(d,False)
            self.assertEqual(list(Path(d).iterdir()),[])


if __name__=='__main__': unittest.main()
