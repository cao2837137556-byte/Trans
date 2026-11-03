"""Generated acceptance of the same P/T/E functions used by the real entrypoint."""
import copy
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import issue27dualview_fixture_v1 as fixture
import numpy as np
import torch
import issue27dualview_support_v1 as s
import issue27dualview_model_v1 as m
import issue27dualview_pipeline_v1 as p
import issue27dualview_metrics_v1 as metrics
import issue27dualview_control_v1 as control
from issue27dualview_build_v1 import code_pins


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):m.configure();fixture.TEST_ROOT.mkdir(parents=True,exist_ok=True)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=fixture.TEST_ROOT);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
    def assets(self):return fixture.assets(self.base/'assets')
    def budget(self,stage='P'):
        b=control.Budget(self.base,time.monotonic(),dict(seconds=120));b.stage=stage;return b

    def test_frozen_recipe_and_real_not_started(self):
        r=s.recipe();self.assertEqual(r['training']['updates_total'],5900);self.assertEqual(r['stages']['E']['head_scores_total'],560632)
        self.assertEqual(r['stages']['P']['E3_numeric_rows'],9402);self.assertEqual(r['training']['epochs'],50)
        self.assertEqual(set(s.OUTPUTS),set('PTE'));self.assertFalse(any(d.exists() for d in s.OUTPUTS.values()))
    def test_real_model_guard(self):
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_BLOCKED'):(s.ROOT/s.recipe()['inputs']['initial_AB']['path']).read_bytes()
    def test_real_npz_guard(self):
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_BLOCKED'):np.load(s.ROOT/s.recipe()['inputs']['e3_caches']['fit_select']['path'])
    def test_recipe_tamper(self):
        path=self.base/'bad.json';path.write_text('{}')
        with patch.object(s,'RECIPE',path),self.assertRaisesRegex(s.Stop,'RECIPE_IDENTITY'):s.recipe()
    def test_exact_head_and_encoder_sizes(self):
        self.assertEqual(sum(x.numel() for x in m.Encoder().parameters()),82944)
        self.assertEqual(sum(x.numel() for x in m.head().parameters()),115073)
    def test_new_heads_same_initialization(self):self.assertEqual(m.state_hash(m.head()),m.state_hash(m.head()))
    def test_zero_content_control_preserves_AB_and_mask(self):
        x=torch.randn(4,897);y=m.arm_input(x,'U0')
        self.assertTrue(torch.equal(x[:,:128],y[:,:128]));self.assertTrue(torch.equal(x[:,896],y[:,896]));self.assertEqual(int(torch.count_nonzero(y[:,128:896])),0)
        self.assertGreater(int(torch.count_nonzero(x[:,128:896])),0)
    def test_encoder_no_old_head_and_causal(self):
        model=m.Encoder();x=torch.randn(8,131);z=x.clone();z[3:]+=100
        with torch.inference_mode():a=model([x],['x'])[0];b=model([z],['x'])[0]
        torch.testing.assert_close(a[:3],b[:3],rtol=0,atol=0)
        self.assertFalse(any('head' in n for n,_ in model.named_parameters()))
    def test_encoder_generated_original_equivalence(self):
        from issue27frontend_paired_train_model_v1 import Student
        original=Student().eval();new=m.Encoder();new.load_state_dict({k:v for k,v in original.state_dict().items() if k.startswith(('encoder.','event_projection.'))})
        xs=[torch.randn(n,131) for n in (2,7,1)];keys=['b','a','c']
        with torch.inference_mode():
            h=new(xs,keys);q=original(xs,keys)
            for a,b in zip(h,q):torch.testing.assert_close(original.head_output(original.head_activation(original.head_hidden(a))).squeeze(-1),b,rtol=0,atol=0)
    def test_encoder_requires_no_grad(self):
        with self.assertRaisesRegex(s.Stop,'ENCODER_MODE'):m.Encoder()([torch.randn(2,131)],['x'])
    def test_encoder_mutation_detected(self):
        a=m.Encoder();identity=m.state_hash(a)
        with torch.no_grad():a.event_projection.weight[0,0]+=1
        with self.assertRaisesRegex(s.Stop,'ENCODER_MUTATED'):m.verify_encoder(a,identity)
    def test_independent_weighted_loss_and_update(self):
        r=s.recipe();a=m.head().eval();b=copy.deepcopy(a);oa=m.optimizer(a,r);ob=m.optimizer(b,r)
        x=torch.randn(5,897);y=torch.tensor([0.,0.,0.,0.,1.]);w=torch.tensor([5/8]*4+[5/2])
        for _ in range(3):
            loss,_=m.update(a,oa,x,y,w);ob.zero_grad(set_to_none=True)
            q=b(x).reshape(-1);ref=(w*(torch.nn.functional.softplus(q)-y*q)).sum()/len(y)
            self.assertAlmostEqual(loss,float(ref.detach()),places=6);ref.backward();torch.nn.utils.clip_grad_norm_(b.parameters(),1.,error_if_nonfinite=True,foreach=False);ob.step()
            for av,bv in zip(a.parameters(),b.parameters()):torch.testing.assert_close(av,bv,rtol=1e-5,atol=2e-7)
    def test_normalizers_valid_train_only_zero_variance(self):
        ab=np.arange(3*128,dtype=np.float32).reshape(3,128);e=np.ones((3,768),dtype=np.float32)*7;e[2]=np.nan;mask=np.array([True,True,False])
        mean,scale=m.normalizers(ab,e,mask);self.assertTrue((mean[128:]==7).all());self.assertTrue((scale[128:]==1).all())
        z=m.normalize(ab,e,mask,mean,scale);self.assertTrue(np.isfinite(z).all());self.assertTrue((z[2,128:896]==0).all());self.assertEqual(z[2,896],0)
    def test_nonfinite_available_E3_rejected(self):
        with self.assertRaisesRegex(s.Stop,'NORMALIZER_NONFINITE'):m.normalizers(np.zeros((2,128)),np.full((2,768),np.nan),np.ones(2,dtype=np.bool_))
    def test_selective_reader_skips_forbidden_nan(self):
        r,plan=self.assets();ts=sorted(s.targets([c for c in plan['contexts'] if c['role']=='train']),key=lambda t:t['uid']);budget=self.budget()
        values,mask,_=p.e3_rows(r,'fit_select',ts,budget)
        self.assertEqual(budget.access['E3_numeric_rows'],4);self.assertEqual(int(mask.sum()),4);self.assertTrue(np.isfinite(values).all())
        self.assertEqual(budget.access['opaque_E3_bytes_streamed'],r['inputs']['e3_caches']['fit_select']['shape'][0]*768*4)
    def test_teacher_wrong_normal_still_available(self):
        r,plan=self.assets();ts=sorted(s.targets([c for c in plan['contexts'] if c['role']=='train']),key=lambda t:t['uid'])
        values,mask,_=p.e3_rows(r,'fit_select',ts,self.budget());i=next(i for i,t in enumerate(ts) if t['owner']=='A' and t['label']==0 and t['old_hard']==1)
        self.assertTrue(mask[i]);self.assertTrue(np.any(values[i]!=0))
    def test_mask_independent_of_labels_and_scores(self):
        r,plan=self.assets();ts=s.targets([c for c in plan['contexts'] if c['role']=='train']);a=p.e3_rows(r,'fit_select',ts,self.budget())
        for t in ts:t['label']=1-t['label'];t['old_hard']=1-t['old_hard']
        b=p.e3_rows(r,'fit_select',ts,self.budget());np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[1],b[1])
    def test_P_rejects_CHECK_before_file_access(self):
        r,plan=self.assets();ts=s.targets([c for c in plan['contexts'] if c['role']=='check'])
        with patch.object(s,'pin',side_effect=AssertionError('opened')),self.assertRaisesRegex(s.Stop,'E3_ROLE_BOUNDARY'):p.e3_rows(r,'fit_select',ts,self.budget())
    def test_P_and_T_reject_expanded_before_file_access(self):
        for stage in ('P','T'):
            with patch.object(s,'pin',side_effect=AssertionError('opened')),self.assertRaisesRegex(s.Stop,'E3_ROLE_BOUNDARY'):p.e3_rows({},'expanded',[],self.budget(stage))
    def test_row_index_duplicates_rejected(self):
        with self.assertRaisesRegex(s.Stop,'ROW_INDICES'):p.selective_rows(self.base/'absent',[1,1],[2,768],self.budget())
    def test_cache_hash_drift_rejected(self):
        r,plan=self.assets();r['inputs']['e3_caches']['fit_select']['sha256']='0'*64
        with self.assertRaisesRegex(s.Stop,'INPUT_DRIFT'):p.e3_rows(r,'fit_select',s.targets([c for c in plan['contexts'] if c['role']=='train']),self.budget())
    def test_input_availability_disagreement_stops(self):
        r,plan=self.assets();ts=s.targets([c for c in plan['contexts'] if c['role']=='train']);ts[0]['owner']='B'
        with self.assertRaisesRegex(s.Stop,'AVAILABILITY_MISMATCH'):p.e3_rows(r,'fit_select',ts,self.budget())
    def test_prefix_position_mismatch_stops(self):
        r,plan=self.assets();ts=s.targets([c for c in plan['contexts'] if c['role']=='train']);ts[0]['position']+=1
        with self.assertRaisesRegex(s.Stop,'OLD_PREFIX_JOIN'):p.e3_rows(r,'fit_select',ts,self.budget())
    def test_metadata_component_tamper_rejected(self):
        r,_=self.assets();a=s.read_json(Path(r['inputs']['plan']['path']));a['contexts'][0]['component']='wrong'
        s.atomic_json(Path(r['inputs']['plan']['path']),a);r['inputs']['plan']=fixture.pin(Path(r['inputs']['plan']['path']))
        with self.assertRaisesRegex(s.Stop,'COMPONENT_ASSIGNMENTS'):p.metadata(r,self.budget())
    def test_T_requires_P_seal(self):
        with patch.dict(s.OUTPUTS,{'P':self.base/'missing'}),self.assertRaises((s.Stop,FileNotFoundError)):p.prepared(s.recipe(),self.budget('T'))
    def test_full_generated_PTE_50_epochs_and_exact_counters(self):
        r,outs,result=fixture.run_direct(self.base)
        self.assertEqual(set(result),set('PTE'))
        a=s.read_json(outs['T']/'access.json');self.assertEqual(a['optimizer_steps'],100);self.assertEqual(a['historical_student_loads'],0)
        self.assertEqual(a['E3_numeric_rows'],0);self.assertEqual(a['encoder_forwards'],0)
        a=s.read_json(outs['E']/'access.json');self.assertEqual(a['E3_numeric_rows'],5);self.assertEqual(a['evaluated_targets'],34)
        rec=s.read_json(outs['T']/'candidates_sealed.json');self.assertEqual(rec['order_hashes']['U0'],rec['order_hashes']['U1'])
        self.assertEqual(rec['candidates']['U0']['initial_state_sha256'],rec['candidates']['U1']['initial_state_sha256'])
        comparison=s.read_json(outs['E']/'comparison.json');self.assertFalse(comparison['scientific_success']);self.assertEqual(comparison['commissioning'],'NOT_EVALUATED')
    def test_ranking_ties_do_not_split_normal_group(self):
        rows=[dict(uid=str(i),label=int(i==0),attack_family='f') for i in range(201)];q={str(i):1. for i in range(201)}
        result=metrics.ranking(rows,q);self.assertEqual(result['points']['0.01']['detected'],0);self.assertIsNone(result['points']['0.01']['threshold'])
    def test_ranking_tail_exact_integer_cap(self):
        rows=[dict(uid=str(i),label=int(i<2),attack_family='f',pool='p',source_group='g',event_index=0) for i in range(202)]
        q={str(i):float(202-i) for i in range(202)};rank=metrics.ranking(rows,q)
        self.assertEqual(rank['points']['0.01']['false_alarms'],2);self.assertEqual(rank['points']['0.001']['false_alarms'],0)
        self.assertEqual(metrics.tail_composition(rows,q,rank)['0.01']['false_alarms'],2)
    def test_unauthorized_entry_no_output(self):
        proc=subprocess.run([str(s.PYTHON),'-B',str(Path(control.__file__)),'run'],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(proc.returncode,0);self.assertIn('EXPLICIT_STAGE_AUTHORIZATION_REQUIRED',proc.stderr)
        self.assertFalse(any(p.exists() for p in s.OUTPUTS.values()))
    def test_windows_supervised_full_chain(self):
        result=subprocess.run([str(s.PYTHON),'-B',str(Path(fixture.__file__)),'chain',str(self.base/'chain')],capture_output=True,text=True,encoding='utf-8',timeout=90)
        self.assertEqual(result.returncode,0,result.stderr);states=json.loads(result.stdout.strip().splitlines()[-1]);self.assertEqual([x['status'] for x in states],['COMPLETE']*3,str(states))
        self.assertTrue(all(x['verified'] and x['retries']==0 for x in states))
        for stage in 'PTE':s.manifest(self.base/'chain'/stage)
    def fault(self,mode):
        proc=subprocess.run([str(s.PYTHON),'-B',str(Path(fixture.__file__)),mode,str(self.base/'failure')],capture_output=True,text=True,encoding='utf-8',timeout=45)
        self.assertEqual(proc.returncode,0,proc.stderr);state=json.loads(proc.stdout.strip().splitlines()[-1]);self.assertEqual(state['status'],'STOP');self.assertFalse(state['verified']);self.assertEqual(state['retries'],0)
        s.manifest(self.base/'failure');self.assertFalse((self.base/'T').exists());return state
    def test_worker_failure_stops_and_seals(self):self.assertIn('GENERATED_FAILURE',self.fault('failure')['reason'])
    def test_wall_limit_stops_and_seals(self):self.assertIn('WALL_CAP',self.fault('wall')['reason'])
    def test_powerShell_scripts_parse(self):
        for path in sorted((s.ROOT/'scripts').glob('*unified_dual_view_v1.ps1')):
            command="$e=$null; $t=$null; [System.Management.Automation.Language.Parser]::ParseFile('"+str(path).replace("'","''")+"',[ref]$t,[ref]$e) > $null; if($e.Count){$e | Out-String; exit 1}"
            proc=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,timeout=20)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)


def main():
    started=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,tests_passed=result.testsRun-len(result.failures)-len(result.errors),
                elapsed_seconds=time.monotonic()-started,numeric_access_guard=True,real_model_forwards=0,real_teacher_rows=0,real_optimizer_steps=0,
                generated_PTE_real_entry_functions=True,generated_50epoch_two_heads=True,tested_code_pins=code_pins())
    dest=fixture.TEST_ROOT/'acceptance.json';s.atomic_json(dest,output);print(s.canonical({k:v for k,v in output.items() if k!='tested_code_pins'}).decode())
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
