from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import tempfile,unittest,gzip,json,sys
import numpy as np
import torch
import legacy_qref_common_v1 as c
import legacy_qconfirm_common_v1 as d
import legacy_qconfirm_runner_v1 as runner
from legacy_qconfirm_fixture_v1 import fixture
from legacy_qconfirm_evaluate_v1 import predict,evaluate
from legacy_qconfirm_report_v1 import summarize,group_tables,gate
ROOT=Path(__file__).resolve().parents[2]

class Confirmation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(4);cls.plan=d.recipe(ROOT);cls.qrecipe=c.load_recipe(ROOT)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='qconfirm_');self.folder=Path(self.temp.name)
        self.plan,self.inputs=fixture(self.plan,self.qrecipe)
    def tearDown(self):self.temp.cleanup()
    def scope(self):
        return dict(execution_authorized=True,recipe_sha256=d.DESIGN_SHA,stages=d.STAGES,training=False,calibration=False,retries=0,
            holdout_owner='THIS_HPC_JOB_ONLY',root=str(self.folder),output=str(self.folder/'runs/result'),workers=8)
    def progress(self):return d.Progress(self.folder/'progress')
    def predictions(self):return predict(self.plan,self.qrecipe,**self.inputs,progress=self.progress())
    def test_unauthorized_before_asset_read(self):
        path=self.folder/'scope.json';s=self.scope();s['execution_authorized']=False;c.write(path,s)
        with patch.object(d,'implementation_check',side_effect=AssertionError('opened assets')):
            with self.assertRaisesRegex(c.Stop,'NOT_AUTHORIZED'):runner.execute(self.folder,path,Path(s['output']),True)
    def test_scope_boundary(self):
        for key,val in [('training',True),('calibration',True),('retries',1),('holdout_owner','OLD_LOCAL')]:
            with self.subTest(key=key):
                s=self.scope();s[key]=val
                with self.assertRaises(c.Stop):d.authorize(s,self.folder,Path(s['output']),True)
    def test_data_packaging_refuses_without_authority(self):
        from legacy_qconfirm_delivery_v1 import package_inputs
        path=self.folder/'scope.json';c.write(path,dict(execution_authorized=False))
        with patch.object(d,'recipe',side_effect=AssertionError('protected input read')):
            with self.assertRaisesRegex(c.Stop,'PACKAGING_NOT_AUTHORIZED'):package_inputs(self.folder,path,self.folder/'inputs.tar.gz',True)
    def test_failure_preserves_status_and_refuses_retry(self):
        scope=self.scope();path=self.folder/'scope.json';c.write(path,scope);plan=deepcopy(self.plan);plan['immutable']['artifact_pins']={}
        with patch.object(d,'implementation_check',return_value=plan),patch.object(sys,'platform','linux'),patch('legacy_qconfirm_runtime_v1.install',side_effect=c.Stop('INJECTED_MISSING_ENV')):
            with self.assertRaisesRegex(c.Stop,'INJECTED'):runner.execute(self.folder,path,Path(scope['output']),True)
        state=c.status(Path(scope['output']));self.assertEqual(state['status'],'STOPPED_NO_RETRY');self.assertFalse(state['heldout_opened'])
        with self.assertRaisesRegex(c.Stop,'OUTPUT_EXISTS'):d.authorize(scope,self.folder,Path(scope['output']),True)
    def test_missing_raw_before_query_read(self):
        from legacy_qconfirm_runtime_v1 import inventory
        scope=dict(raw_paths={'fixture':str(self.folder/'absent.pcap')})
        with patch.object(c,'read',return_value={'assets':[dict(capture_id='fixture',bytes=42)]}) as read:
            with self.assertRaisesRegex(c.Stop,'MISSING_RAW_INVENTORY'):inventory(self.folder,scope,self.plan,self.qrecipe)
            self.assertEqual(read.call_count,1)
            self.assertEqual(read.call_args[0][0].name,'asset_candidates.json')
    def test_no_retry_existing_output(self):
        s=self.scope();Path(s['output']).mkdir(parents=True)
        with self.assertRaisesRegex(c.Stop,'OUTPUT_EXISTS'):d.authorize(s,self.folder,Path(s['output']),True)
    def test_scope_stages_and_paths(self):
        s=self.scope();s['stages']=['DEV']
        with self.assertRaises(c.Stop):d.authorize(s,self.folder,Path(s['output']),True)
        s=self.scope();s['output']=str(self.folder/'outside')
        with self.assertRaises(c.Stop):d.authorize(s,self.folder,Path(s['output']),True)
    def test_worker_budget(self):
        s=self.scope();s['workers']=9
        with self.assertRaisesRegex(c.Stop,'WORKERS'):d.authorize(s,self.folder,Path(s['output']),True)
    def test_metadata_contract(self):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_partition_leak_refused(self):
        self.inputs['rows'][0]['partition']='LEARN'
        with self.assertRaises(c.Stop):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_future_and_equal_time_refused(self):
        self.inputs['rows'][0]['timestamp']=10.
        with self.assertRaises(c.Stop):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_reference_packet_overlap_refused(self):
        # Packet identity equal at the same timestamp is invalid even if UID differs.
        self.inputs['refs'][0]['packet_sha256']=self.inputs['rows'][0]['packet_sha256']
        self.inputs['refs'][0]['timestamp']=self.inputs['rows'][0]['timestamp']
        with self.assertRaises(c.Stop):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_normal_reference_provenance(self):
        self.inputs['refs'][0]['label']=1
        with self.assertRaises(c.Stop):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_weight_drift(self):
        self.inputs['rows'][0]['label_metric_weight_denominator']*=2
        with self.assertRaisesRegex(c.Stop,'WEIGHT'):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_duplicate_component(self):
        self.inputs['refs'][1]['component_id']=self.inputs['refs'][0]['component_id']
        with self.assertRaisesRegex(c.Stop,'COMPONENT'):d.validate_metadata(self.plan,self.inputs['rows'],self.inputs['refs'])
    def test_wrong_control_protocol(self):
        self.plan['arms']['controls'][0]['protocol']=17
        with self.assertRaisesRegex(c.Stop,'PROTOCOL'):d.validate_controls(self.plan,self.inputs['refs']+self.inputs['donors'])
    def test_wrong_control_future(self):
        self.inputs['donors'][0]['reference_end']=30.
        with self.assertRaisesRegex(c.Stop,'TIME_ROLE'):d.validate_controls(self.plan,self.inputs['refs']+self.inputs['donors'])
    def test_no_optimizer_or_calibration(self):
        with patch('torch.optim.AdamW',side_effect=AssertionError('optimizer')),patch('legacy_qref_evaluate_v1.calibrate',side_effect=AssertionError('CAL')):
            p,_,_,_=self.predictions();self.assertEqual(p['FULL'].shape,(48,))
    def test_fallback_and_preservation(self):
        p,_,valid,_=self.predictions();rr=self.inputs['rows'];y=np.array([r['label'] for r in rr])
        self.assertTrue(np.array_equal(p['Q'][y==1],p['FULL'][y==1]));self.assertTrue((p['Q']&~p['FULL']).any())
        self.assertTrue(np.array_equal(p['Q'][~valid],p['FULL'][~valid]));self.assertTrue(np.array_equal(p['FULL_empty_inner'],p['Q']))
        for i,r in enumerate(rr):
            if r['device']=='Ring Basestation' or (r['device']=='Netatmo Camera' and r['protocol']==6):self.assertFalse(valid[i])
    def test_query_order_invariant(self):
        p,_,_,_=self.predictions();order=np.arange(len(self.inputs['rows']))[::-1];self.inputs['rows']=[self.inputs['rows'][i] for i in order];self.inputs['features']=self.inputs['features'][order]
        q,_,_,_=predict(self.plan,self.qrecipe,**self.inputs,progress=d.Progress(self.folder/'p2'))
        for name in p:self.assertTrue(np.array_equal(p[name][order],q[name]),name)
    def test_labels_not_model_inputs(self):
        p,_,_,_=self.predictions()
        for r in self.inputs['rows']:r['label']=1-r['label']
        q,_,_,_=predict(self.plan,self.qrecipe,**self.inputs,progress=d.Progress(self.folder/'p2'))
        for name in p:self.assertTrue(np.array_equal(p[name],q[name]),name)
    def test_zero_vector_stops(self):
        self.inputs['features'][0]=0
        with self.assertRaisesRegex(c.Stop,'NORM'):self.predictions()
    def test_update_guard(self):
        with self.assertRaisesRegex(c.Stop,'OPTIMIZER'):self.progress().tick(1)
    def test_monitor_rename_race_and_disk_guard(self):
        p=self.progress();pending=p.out/'gone.pending'
        with patch.object(Path,'rglob',return_value=iter([pending])),patch.object(Path,'is_file',return_value=True),patch.object(Path,'stat',side_effect=FileNotFoundError(2,'renamed')):
            p.guard()
        p.last_disk=-1e9;p.disk=0
        with self.assertRaisesRegex(c.Stop,'OUTPUT_DISK_LIMIT'):p.guard()
    def test_status_open_boundary(self):
        p=self.progress();self.assertFalse(c.status(p.out)['heldout_opened']);p.heldout_opened=True;p.emit();self.assertTrue(c.status(p.out)['heldout_opened'])
    def test_full_synthetic_report(self):
        progress=self.progress();result=evaluate(self.plan,self.qrecipe,self.inputs,self.folder/'evaluation',progress,synthetic=True)
        c.verify(self.folder/'evaluation');self.assertEqual(result['gate']['status'],'PASS');self.assertFalse(result['heldout_opened'])
        # Independently reconstruct every compressed group count from saved decisions.
        out=self.folder/'evaluation';rows=self.inputs['rows']
        with np.load(out/'decisions.npz') as saved:
            for file in (out/'groups').glob('*.keys.json.gz'):
                with gzip.open(file,'rt') as f:keys=json.load(f)
                arr=np.load(file.with_name(file.name.replace('.keys.json.gz','.npz')))
                for g,key in enumerate(keys['keys']):
                    ix=[i for i,r in enumerate(rows) if all((str(bool(saved['eligible'][i])) if field=='eligible' else str(r.get(field,'NA')))==value for field,value in zip(keys['fields'],key))]
                    for arm in result['reports']:
                        for label,cl in [(0,'normal'),(1,'attack')]:
                            jj=[i for i in ix if rows[i]['label']==label];self.assertEqual(int(arr[arm+'__'+cl+'_positive'][g]),int(saved[arm][jj].sum()))
                arr.close()
    def test_inconclusive_no_errors(self):
        p,b,v,_=self.predictions()
        for name in p:p[name][:]=False;b[name][:]=False
        reports=group_tables(self.inputs['rows'],p,b,v,self.folder/'g',d.Progress(self.folder/'pr2'))
        self.assertEqual(gate(reports,self.inputs['rows'],v)['status'],'INCONCLUSIVE')
    def test_attack_loss_gate(self):
        p,b,v,_=self.predictions();i=next(i for i,r in enumerate(self.inputs['rows']) if r['label']==1);p['FULL'][i]=False
        reports=group_tables(self.inputs['rows'],p,b,v,self.folder/'g',d.Progress(self.folder/'pr2'))
        self.assertIn('NEW_ATTACK_MISSES',gate(reports,self.inputs['rows'],v)['reasons'])
        self.assertFalse(gate(reports,self.inputs['rows'],v)['two_device_replication'])
    def test_outer_no_reference_exact_R(self):
        for r in self.inputs['rows']:r['device']='Unregistered device'
        p,_,valid,detail=self.predictions()
        self.assertFalse(valid.any());self.assertFalse(detail['registered'].any())
        self.assertTrue(np.array_equal(p['R'],p['Q']));self.assertTrue(np.array_equal(p['FULL'],p['R']))
    def test_inconclusive_when_errors_only_in_fallback(self):
        p,b,v,_=self.predictions()
        for name in p:p[name][v]=False;b[name][v]=False
        reports=group_tables(self.inputs['rows'],p,b,v,self.folder/'g',d.Progress(self.folder/'pr2'))
        self.assertEqual(gate(reports,self.inputs['rows'],v)['status'],'INCONCLUSIVE')
    def test_capture_shards_and_feature_merge(self):
        import legacy_reference_executor_common_v1 as oldc
        import legacy_reference_executor_fixture_v1 as fx
        import legacy_reference_sample_prepare_v1 as prep
        import issue27ckda_d0_resource_pilot_v1 as translator
        from legacy_qconfirm_features_v1 import materialize,partition,merge
        with patch.object(oldc,'PACKAGE',self.folder):info=c.read(fx.create(self.folder/'synthetic/input'))
        rows=c.rows(info['recipe']['data']['manifests']['DEVICE_HOLDOUT']['path'])
        refs=[r for r in c.rows(info['recipe']['data']['manifests']['REFERENCE']['path']) if r['partition']=='DEVICE_HOLDOUT']
        catalog={r['capture_id']:r for r in info['catalog']}
        tasks=partition(rows,refs,catalog,2);self.assertEqual(sum(len(x['targets']) for x in tasks),len(rows)+len(refs))
        self.assertEqual(len(set(cid for x in tasks for cid in x['captures'])),sum(len(x['captures']) for x in tasks))
        api,prefix,_=prep.old.legacy_runtime()
        class Embed:
            @staticmethod
            def embed_flows(trans,model,tok,col,flows,device,batch):
                self.assertTrue(all(set(f)=={'flow_duration','burst_tokens','directions','bytes','iats','counts','protocol'} for f in flows))
                return np.ones((len(flows),768),np.float32)
        runtime=dict(event=api,prefix=prefix,translator=translator,embed=Embed,model=None,tokenizer=None,collator=None)
        outputs=[]
        for i,task in enumerate(tasks):
            p=d.Progress(self.folder/('shard'+str(i)));outputs.append(p.out)
            materialize(task,catalog,[r['mac'] for r in info['devices']],runtime,p.out,p,decoder=lambda spec:info['rows'][spec['capture_id']])
        p=d.Progress(self.folder/'merge_progress');arr=merge(outputs,rows,refs,self.folder/'merged',p)
        self.assertEqual(arr.shape,(len(rows)+len(refs),768));self.assertTrue((arr==1).all());del arr
        c.verify(self.folder/'merged')
        with self.assertRaises(c.Stop):merge(outputs+outputs[:1],rows,refs,self.folder/'badmerge',d.Progress(self.folder/'badpr'))

if __name__=='__main__':unittest.main(verbosity=2)
