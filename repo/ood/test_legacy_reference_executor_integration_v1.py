"""Synthetic process-level acceptance; no real checkpoint or PCAP is opened."""
import copy,json,tempfile,time,unittest
from pathlib import Path
import legacy_reference_executor_common_v1 as c
import legacy_reference_executor_control_v1 as control
from legacy_reference_executor_fixture_v1 import create
class SupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (c.PACKAGE/'synthetic').mkdir(parents=True,exist_ok=True)
        cls.root=Path(tempfile.mkdtemp(prefix='supervisor_',dir=c.PACKAGE/'synthetic'))
        cls.fixture=create(cls.root/'inputs');cls.value=c.load(cls.fixture);cls.recipe=cls.value['recipe']
    def context(self,name):
        chain=Path(tempfile.mkdtemp(prefix=name+'_',dir=self.root));(chain/'requests').mkdir()
        c.atomic_json(chain/'recipe.json',self.recipe);c.atomic_json(chain/'execution_scope.json',dict(synthetic_only=True))
        out=chain/'worker'
        q=dict(operation=name,out=str(out),chain=str(chain),recipe_sha256=c.sha(chain/'recipe.json'),fixture=str(self.fixture))
        return chain,out,q,chain/'requests'/(name+'.json')
    def test_deadline_kills_entire_child_tree(self):
        chain,out,q,path=self.context('SYNTHETIC_CHILD')
        with self.assertRaisesRegex(c.Stop,'WALL_TIME_LIMIT'):
            control.launch(q,path,self.recipe['runtime']['training_python'],chain,time.monotonic()+3,dict(self.recipe['runtime']))
        from issue27frontend_inheritance_outer_control_v1 import pid_alive
        self.assertTrue((out/'child.json').exists(),'child probe must actually start before timeout')
        self.assertFalse(pid_alive(c.load(out/'child.json')['pid']))
        self.assertEqual(c.load(path.with_suffix('.supervisor.json'))['attempts'],1)
    def test_disk_limit_stops_and_keeps_partial_evidence(self):
        chain,out,q,path=self.context('SYNTHETIC_DISK');limits=dict(self.recipe['runtime'])
        limits['disk_new_output_limit_GiB']=(control.directory_bytes(chain)+65536)/2**30
        with self.assertRaisesRegex(c.Stop,'DISK_LIMIT'):
            control.launch(q,path,self.recipe['runtime']['training_python'],chain,time.monotonic()+20,limits)
        self.assertEqual((out/'payload.bin').stat().st_size,1024*1024)
    def test_memory_cap_is_enforced_by_windows_job(self):
        chain,out,q,path=self.context('SYNTHETIC_MEMORY');limits=dict(self.recipe['runtime']);limits['ram_process_tree_limit_GiB']=64/1024
        with self.assertRaisesRegex(c.Stop,'WORKER_EXIT'):
            control.launch(q,path,self.recipe['runtime']['training_python'],chain,time.monotonic()+20,limits)
        self.assertIn('MemoryError',path.with_suffix('.log').read_text(encoding='utf8'))
    def test_explicit_stop_request_does_not_retry(self):
        chain,out,q,path=self.context('SYNTHETIC_CHILD');(chain/'STOP_REQUESTED').touch()
        with self.assertRaisesRegex(c.Stop,'USER_STOP'):
            control.launch(q,path,self.recipe['runtime']['training_python'],chain,time.monotonic()+20,dict(self.recipe['runtime']))
        self.assertEqual(c.load(path.with_suffix('.supervisor.json'))['retries'],0)
    def test_failure_chain_is_sealed_and_cannot_restart(self):
        fixture=create(self.root/'failed_inputs',inject_failure='before_features');out=self.root/'failed_run'
        with self.assertRaisesRegex(c.Stop,'WORKER_EXIT'):control.run_chain(fixture_path=fixture,out=out)
        self.assertEqual(c.load(out/'status.json')['status'],'STOPPED_NO_RETRY');c.verify_seal(out)
        self.assertFalse((out/'features_LEARN_DEV').exists())
        with self.assertRaisesRegex(c.Stop,'OUTPUT_EXISTS_NO_RETRY'):control.run_chain(fixture_path=fixture,out=out)
class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(tempfile.mkdtemp(prefix='e2e_final_',dir=c.PACKAGE/'synthetic'))
    def run_case(self,name,force):
        fixture=create(self.root/(name+'_inputs'),force_gate=force);out=self.root/(name+'_run')
        value=control.run_chain(fixture_path=fixture,out=out);c.verify_seal(out)
        self.assertEqual(value['status'],'COMPLETE')
        endpoints=list(out.glob('train_*/endpoint.json'));self.assertEqual(len(endpoints),9)
        self.assertEqual(sum(c.load(p)['updates'] for p in endpoints),54)
        access=list((out/'requests').glob('*.access.json'));self.assertEqual(len(access),len(value['stages']))
        self.assertTrue(all(c.load(p)['blocked_asset_attempts']==0 and c.load(p)['real_checkpoint_reads']==c.load(p)['real_raw_reads']==0 for p in access))
        dev=c.load(out/'evaluation_DEV/report.json')
        self.assertEqual(len(dev['reports']),13);self.assertEqual(len(dev['interventions']),2)
        self.assertTrue(all(len(x['comparisons']['correct'])==len(x['comparisons']['wrong'])==13 for x in dev['interventions']))
        from legacy_reference_executor_features_v1 import load_cache
        features,rows=load_cache(out/'features_LEARN_DEV','LEARN',value['recipe_digest'])
        self.assertEqual(features.shape,(12,768));self.assertEqual(len(rows),12)
        self.assertTrue(all(r['report_direction']=='inbound' and r['report_local_port']==80 for r in rows))
        return out,value
    def test_closed_actual_gate_never_materializes_holdout(self):
        out,value=self.run_case('closed',None)
        self.assertFalse(value['heldout_opened'])
        self.assertFalse((out/'features_HOLDOUT').exists());self.assertFalse((out/'holdout_open_claim.json').exists())
    def test_fixture_open_branch_runs_once_without_real_assets(self):
        out,value=self.run_case('open',True)
        self.assertTrue(value['heldout_opened']);self.assertTrue(value['gate']['synthetic_gate_override'])
        self.assertEqual(sum(x=='PREPARE_HOLDOUT' for x in value['stages']),1)
        self.assertEqual(c.load(out/'features_HOLDOUT/cache.json')['rows'],8)
        self.assertTrue((out/'evaluation_DEVICE_HOLDOUT/report.json').exists())
if __name__=='__main__':unittest.main(verbosity=2)

