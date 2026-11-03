"""Generated numerical, pipeline and Windows supervision acceptance for Q/R."""
import copy
import io
import json
import math
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import issue27frontend_aligned_fixture_v1 as fixture
import numpy as np
import torch
from torch.nn import functional as F
import issue27frontend_transfer_model_v1 as old
import issue27frontend_aligned_support_v1 as s
import issue27frontend_aligned_model_v1 as m
import issue27frontend_aligned_prepare_v1 as p
import issue27frontend_aligned_train_v1 as train
import issue27frontend_aligned_evaluate_v1 as e
import issue27frontend_aligned_control_v1 as control
from issue27frontend_aligned_build_v1 import code_pins
from issue27frontend_transfer_io_v2 import read_progress

fixture.TEST_ROOT.mkdir(parents=True,exist_ok=True)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):m.configure()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=fixture.TEST_ROOT);self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)

    def assets(self):return fixture.generated_assets(self.base/'assets')

    def batch(self):
        cs=[fixture.context('n',0,events=(0,1,2)),fixture.context('a',1),fixture.context('b',0,'B')]
        r=copy.deepcopy(s.recipe());r['schedule']['steps_per_epoch']=1
        r['data']['A']['contexts']=2;r['data']['B']['contexts']=1
        r['teacher_cache'].update(expected_N_T0=1,expected_N_T1=1)
        cache={t['uid']:dict(margin=torch.tensor(3. if t['label'] else -3.),scale=torch.tensor(2.),target=torch.linspace(-1,1,128)) for t in s.targets(cs[:2])}
        guard=({c['key']:[dict(t,logit=2. if t['label'] else -2.) for t in c['targets']] for c in cs[:2]},2.)
        return cs,r,cache,guard

    def test_frozen_document_hashes_and_unstarted_scope(self):
        r=s.recipe();self.assertEqual(r['schedule']['updates_all_arms'],7880)
        self.assertEqual(r['evaluation']['targets_all_arms'],560632)
        self.assertFalse(any(s.OUTPUTS[k].exists() for k in 'PTE'))

    def test_audit_blocks_even_real_json(self):
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_BLOCKED_REAL_RUN_ACCESS'):
            (s.ROOT/'runs/frontend_task_knowledge_transfer_p_v1_20260911/teacher_index.json').read_bytes()

    def test_original_forward_bitwise_and_deployment(self):
        a=old.OriginalStudent();b=m.Student();b.load_state_dict(a.state_dict())
        xs=[torch.randn(n,131) for n in (2,7,1,7)];keys=['b','a','d','c']
        qs,hs=b(xs,keys,with_hidden=True)
        for left,right in zip(a(xs,keys),qs):torch.testing.assert_close(left,right,rtol=0,atol=0)
        self.assertEqual(sum(p0.numel() for p0 in b.parameters()),91265)
        self.assertEqual([h.shape for h in hs],[(2,128),(7,128),(1,128),(7,128)])

    def test_early_target_causality(self):
        model=m.Student();x=torch.randn(8,131);z=x.clone();z[3:]+=100
        torch.testing.assert_close(model([x],['a'])[0][:3],model([z],['a'])[0][:3],rtol=0,atol=0)

    def test_zero_projection_does_not_consume_rng(self):
        state=torch.get_rng_state().clone();d=m.Projection()
        self.assertTrue(torch.equal(state,torch.get_rng_state()))
        self.assertEqual(sum(v.numel() for v in d.parameters()),16512)

    def test_Q_zero_teacher_matches_original_C1_update_exactly(self):
        cs,r,cache,guard=self.batch();a=m.Student();b=copy.deepcopy(a)
        oa=m.optimizer(a,None,r);ob=m.optimizer(b,None,r)
        for epoch in (1,2):
            m.update(a,None,oa,cs[:2],cs[2:],'Q',epoch,guard,{},r)
            old.update(b,None,ob,cs[:2],cs[2:],'C1',epoch,guard,{},r)
            self.assertEqual(m.state_hash(a),m.state_hash(b))
        self.assertEqual(len(oa.state),len(ob.state))

    def test_task_gradient_reaches_real_head_and_encoder(self):
        cs,r,cache,_=self.batch();model=m.Student()
        qs,hs=model([c['x'] for c in cs[:2]],[c['key'] for c in cs[:2]],with_hidden=True)
        q,_,_=m.teacher_terms(cs[:2],qs,hs,None,cache,{0:1,1:1},1);q.backward()
        self.assertGreater(m.gradient_norm(model.head_output.parameters()),0)
        self.assertGreater(m.gradient_norm(model.encoder.parameters()),0)

    def test_overshoot_opposes_BCE_as_intended(self):
        q=torch.tensor(8.,requires_grad=True);loss=m.huber((q-3)/2);loss.backward()
        self.assertGreater(float(q.grad),0);q.grad=None
        F.binary_cross_entropy_with_logits(q,torch.ones_like(q)).backward()
        self.assertLess(float(q.grad),0)

    def test_R_first_zero_then_encoder_gradient_no_direct_head_path(self):
        cs,r,cache,_=self.batch();model=m.Student();d=m.Projection();opt=torch.optim.SGD(d.parameters(),lr=.2)
        def loss():
            qs,hs=model([c['x'] for c in cs[:2]],[c['key'] for c in cs[:2]],with_hidden=True)
            return m.teacher_terms(cs[:2],qs,hs,d,cache,{0:1,1:1},1)[1]
        loss().backward();self.assertEqual(m.gradient_norm(model.encoder.parameters()),0)
        self.assertGreater(m.gradient_norm(d.parameters()),0);self.assertIsNone(model.head_output.weight.grad)
        opt.step();model.zero_grad(set_to_none=True);d.zero_grad(set_to_none=True)
        loss().backward();self.assertGreater(m.gradient_norm(model.encoder.parameters()),0)
        self.assertIsNone(model.head_output.weight.grad)

    def test_coordinate_projection_before_huber_and_divisor127(self):
        cs,r,cache,_=self.batch();qs=[torch.zeros(3) for _ in cs[:2]];hs=[torch.zeros(3,128) for _ in cs[:2]];d=m.Projection()
        with torch.no_grad():d.bias.copy_(torch.arange(128,dtype=torch.float32)/32)
        _,loss,_=m.teacher_terms(cs[:2],qs,hs,d,cache,{0:1,1:1},1)
        vector=d.bias.detach()-torch.linspace(-1,1,128);v=vector-vector.mean()
        expected=sum(.5*float(x)**2 if abs(float(x))<=1 else abs(float(x))-.5 for x in v)/127
        self.assertAlmostEqual(float(loss.detach()),expected,places=6)
        with torch.no_grad():d.bias.add_(7.)
        other=m.teacher_terms(cs[:2],qs,hs,d,cache,{0:1,1:1},1)[1]
        torch.testing.assert_close(loss,other,rtol=1e-5,atol=1e-6)

    def test_nonuniform_class_context_measure(self):
        rows=[dict(uid=str(i),label=y,context_key=c) for i,(y,c) in enumerate([(0,'a'),(0,'a'),(0,'a'),(0,'b'),(1,'c')])]
        self.assertAlmostEqual(p.balanced_mean([1,4,7,10,2],rows),4.5)

    def test_bucket_measure_recovers_full_teacher_objective(self):
        cs,r,cache,_=self.batch();cs.insert(1,fixture.context('n2',0,events=(1,)))
        for t in cs[1]['targets']:cache[t['uid']]=dict(margin=torch.tensor(-1.),scale=torch.tensor(2.),target=torch.zeros(128))
        a=cs[:3];qs=[torch.arange(3,dtype=torch.float32) for c in a];hs=[torch.zeros(3,128) for c in a]
        whole=m.teacher_terms(a,qs,hs,None,cache,{0:2,1:1},1)[0]
        summed=sum(m.teacher_terms([c],[q],[h],None,cache,{0:2,1:1},197)[0] for c,q,h in zip(a,qs,hs))/197
        torch.testing.assert_close(whole,summed)

    def test_B_and_wrong_A_not_in_teacher(self):
        r,plan=self.assets();cs=s.train_metadata(plan,r);ts=s.teacher_targets(cs,r)
        self.assertTrue(all(t['owner']=='A' and t['old_hard']==t['label'] for t in ts))
        self.assertTrue(any(t['owner']=='B' for t in s.targets(cs)))
        self.assertTrue(any(t['old_hard']!=t['label'] for t in s.targets(cs)))

    def derived(self):
        r,plan=self.assets();cs=s.train_metadata(plan,r)
        rows=s.read_json(Path(r['teacher_cache']['index']['path']))
        vals=np.fromfile(r['teacher_cache']['values']['path'],dtype='<f4').reshape(-1,128)
        return r,rows,vals,s.teacher_targets(cs,r)

    def test_margin_scale_and_float_bits(self):
        r,rows,values,ts=self.derived();derived,m32,meta=p.derive(rows,values,ts,r)
        tau=math.log(r['losses']['task_score']['p_T'])-math.log1p(-r['losses']['task_score']['p_T'])
        expected=np.array([t['canonical_logit']-tau for t in rows])
        self.assertEqual(meta['s_q64'],max(1.,math.sqrt(p.balanced_mean(expected**2,rows))))
        self.assertEqual(m32.tobytes(),expected.astype('<f4').tobytes())
        self.assertEqual(derived[0]['margin32_hex'],m32[0].tobytes().hex())

    def test_canonical_hard_boundary_stops_without_filter(self):
        r,rows,values,ts=self.derived();i=next(i for i,t in enumerate(rows) if t['label']==1)
        rows[i]['canonical_logit']=-100.
        with self.assertRaisesRegex(s.Stop,'MARGIN_HARD_BOUNDARY_MISMATCH'):p.derive(rows,values,ts,r)
        self.assertEqual(len(rows),r['teacher_cache']['expected_targets'])

    def test_teacher_row_join_catches_swapped_rows(self):
        r,rows,values,ts=self.derived();rows[0],rows[1]=rows[1],rows[0]
        with self.assertRaisesRegex(s.Stop,'TEACHER_CACHE_JOIN'):p.derive(rows,values,ts,r)

    def test_nonfinite_teacher_rejected(self):
        r,rows,values,ts=self.derived();values[0,0]=np.nan
        with self.assertRaisesRegex(s.Stop,'TEACHER_VALUES'):p.derive(rows,values,ts,r)

    def test_no_residual_energy_renormalization(self):
        r,rows,values,ts=self.derived();values.fill(1.)
        _,_,meta=p.derive(rows,values,ts,r);self.assertEqual(meta['residual_energy'],0.)

    def test_real_style_P_calls_no_module_or_optimizer(self):
        r,plan=self.assets();out=self.base/'P';out.mkdir();budget=control.Budget(out,time.monotonic(),dict(seconds=30))
        with patch.object(torch.nn.Module,'__call__',side_effect=AssertionError('P module forward')),patch.object(torch.optim,'AdamW',side_effect=AssertionError('P optimizer')):
            result=p.prepare(r,out,budget)
        self.assertEqual(result['targets'],r['teacher_cache']['expected_targets'])
        self.assertEqual(budget.access['feature_bytes_decoded'],0)

    def test_derived_margin_corruption_is_rejected(self):
        r,plan=self.assets();out=self.base/'P';out.mkdir();budget=control.Budget(out,time.monotonic(),dict(seconds=30))
        p.prepare(r,out,budget)
        with (out/'margins.f32le').open('r+b') as f:f.write(b'xxxx')
        with self.assertRaisesRegex(s.Stop,'DERIVED_FILE_HASH'):
            p.load_prepared(s.train_metadata(plan,r),r,out,budget)

    def test_check_rows_cannot_be_teacher_targets(self):
        cs,r,cache,_=self.batch();cs[0]['role']='check'
        with self.assertRaisesRegex(s.Stop,'TEACHER_NONTRAIN'):
            m.teacher_terms(cs[:2],[torch.zeros(3)]*2,[torch.zeros(3,128)]*2,None,cache,{0:1,1:1},1)

    def test_T_accesses_only_train_prefix_bytes(self):
        r,plan=self.assets();budget=control.Budget(self.base,time.monotonic(),dict(seconds=30))
        cs=s.train_metadata(plan,r)
        loaded=train.load_contexts(cs,Path(r['inputs']['train_check_features']['path']),budget)
        self.assertEqual(budget.access['feature_bytes_decoded'],sum(c['length']*524 for c in cs))
        self.assertTrue(all(c['role']=='train' for c in loaded))

    def test_P_guard_identity_mismatch_rejected(self):
        r,plan=self.assets();guard=s.read_json(Path(r['teacher_cache']['guard']['path']));guard['groups']['a0'][0]['event']=99
        path=self.base/'bad_guard.json';s.atomic_json(path,guard);r['teacher_cache']['guard']=fixture.pin(path)
        with self.assertRaisesRegex(s.Stop,'GUARD_JOIN'):p.load_guard(s.train_metadata(plan,r),r,control.Budget(self.base,time.monotonic(),dict(seconds=30)))

    def test_generated_P_T_E_pipeline_and_roundtrip(self):
        r,outputs,results=fixture.generated_pipeline(self.base)
        for stage in 'PTE':s.manifest(outputs[stage]);self.assertEqual(s.read_json(outputs[stage]/'verification.json')['status'],'PASS')
        barrier=s.read_json(outputs['T']/'candidates_sealed.json')
        self.assertEqual(set(barrier['candidates']),{'Q','R'})
        self.assertEqual(barrier['candidates']['Q']['counts'],barrier['candidates']['R']['counts'])
        self.assertEqual(s.read_json(outputs['T']/'access.json')['optimizer_steps'],4)
        self.assertEqual(results['E']['targets'],r['evaluation']['targets_all_arms'])
        self.assertEqual(set(s.read_json(outputs['E']/'comparison.json')['models']),{'old_P2','A','AB','C0','C1','C2','Q','R'})
        self.assertFalse(s.read_json(outputs['E']/'Q_train_transfer_fit.json')['scientific_success'])

    def test_original_guard_and_label_functions_reused(self):
        self.assertIs(m.guard_loss,old.guard_loss);self.assertIs(m.label_loss,old.label_loss)
        self.assertIs(m.optimizer,old.optimizer)

    def test_low_FPR_ties_and_integer_boundaries(self):
        rows=[dict(uid='a',label=1,attack_family='f')]+[dict(uid=str(i),label=0,attack_family='n') for i in range(100)]
        q={t['uid']:-float(i) for i,t in enumerate(rows)};q['0']=1.
        points=e.ranking(rows,q)['points'];self.assertEqual(points['0.01']['false_alarms'],1);self.assertEqual(points['0.001']['detected'],0)
        q['a']=q['0'];self.assertEqual(e.ranking(rows,q)['points']['0.001']['detected'],0)

    def test_AUC_bruteforce_and_family_global_threshold(self):
        rows=[dict(uid=k,label=y,attack_family=k) for k,y in [('a',1),('b',1),('n',0)]]
        result=e.ranking(rows,{'a':2.,'b':0.,'n':1.})
        self.assertEqual(result['auroc'],.5);self.assertEqual(result['points']['0.01']['family_recall']['b']['recall'],0)

    def test_flips_do_not_cancel(self):
        rows=[dict(uid='a',label=1),dict(uid='b',label=0)]
        value=e.flips(rows,{'a':1,'b':1},{'a':0,'b':0})
        self.assertEqual((value['negative'],value['positive']),(1,1));self.assertFalse(value['is_zero_regression'])

    def test_missing_authorization_prevents_launch(self):
        with patch.object(sys,'argv',['aligned','run','--stage','P']),patch.object(control,'supervise') as launch:
            with self.assertRaises(s.Stop):control.main()
            launch.assert_not_called()

    def test_old_authorization_prevents_new_launch(self):
        with patch.object(sys,'argv',['aligned','run','--stage','T','--authorization','I_AUTHORIZE_ONE_NEW_TASK_KNOWLEDGE_TRANSFER_V2_T']),patch.object(control,'supervise') as launch:
            with self.assertRaises(s.Stop):control.main()
            launch.assert_not_called()

    def test_existing_attempt_not_restarted(self):
        with patch.dict(s.OUTPUTS,{'P':self.base}),patch.object(sys,'argv',['aligned','run','--stage','P','--authorization',s.TOKENS['P']]):
            with self.assertRaises(s.Stop):control.main()

    def test_chain_stops_on_first_failure(self):
        with patch.dict(s.OUTPUTS,{k:self.base/k for k in 'PTE'}),patch.object(sys,'argv',['aligned','run','--stage','PTE','--authorization',s.TOKENS['PTE']]),patch.object(control,'supervise',return_value={'status':'STOP'}) as run,patch('sys.stdout',io.StringIO()):
            with self.assertRaises(SystemExit):control.main()
            self.assertEqual(run.call_count,1)

    def test_frozen_stage_caps(self):
        r=s.recipe();self.assertEqual(control.caps(r,'P'),dict(seconds=600,memory=8589934592,output=67108864))
        self.assertEqual(control.caps(r,'T')['seconds'],14400)

    def test_progress_holds_readers_and_ignores_partial_record(self):
        path=self.base/'progress.json';s.atomic_json(path,{'n':1})
        with path.open('rb'),path.with_suffix('.jsonl').open('rb'):
            s.atomic_json(path,{'n':2})
        with path.with_suffix('.jsonl').open('ab') as f:f.write(b'{"partial":')
        self.assertEqual(s.read_json(path),{'n':2})

    def test_concurrent_readers_and_writer(self):
        path=self.base/'progress.json';s.atomic_json(path,dict(n=0,payload='x'*2048));done=threading.Event();errors=[]
        def reader():
            while not done.is_set():
                try:
                    if s.read_json(path)['payload']!='x'*2048:raise AssertionError('torn record')
                except Exception as exc:errors.append(str(exc));return
        readers=[threading.Thread(target=reader) for _ in range(2)]
        for t in readers:t.start()
        try:
            for i in range(100):s.atomic_json(path,dict(n=i,payload='x'*2048))
        finally:
            done.set()
            for t in readers:t.join(5)
        self.assertFalse(errors,errors);self.assertEqual(s.read_json(path)['n'],99)

    def test_human_status_read_handles_stay_open(self):
        control.present(self.base,dict(status='STARTING'))
        with (self.base/'status.md').open('rb'),(self.base/'status.html').open('rb'):
            control.present(self.base,dict(phase='TRAINING',arm='R',updates=7))
        self.assertIn('7/3940',(self.base/'status.md').read_text(encoding='utf-8'))

    def test_terminal_status_retains_actual_completed_work(self):
        s.atomic_json(self.base/'progress.json',dict(phase='VERIFIED',targets_complete=560632,targets_total=560632))
        control.present(self.base,dict(status='COMPLETE',stage='E'))
        text=(self.base/'status.md').read_text(encoding='utf-8')
        self.assertIn('560632/560632',text)

    def test_terminal_reason_visible_with_broken_progress(self):
        (self.base/'progress.json').write_text('{bad')
        control.present(self.base,dict(status='STOP',stage='T',reason='fixture failure'))
        self.assertIn('fixture failure',(self.base/'status.md').read_text(encoding='utf-8'))

    def test_manifest_tamper_rejected(self):
        path=self.base/'x';path.write_text('one');s.seal(self.base);path.write_text('two')
        with self.assertRaises(s.Stop):s.manifest(self.base)

    def test_missing_status_is_not_started(self):
        with patch.dict(s.OUTPUTS,{'P':self.base/'not-created'}):self.assertEqual(control.status('P')['status'],'NOT_STARTED')

    def test_real_windows_job_supervisor_with_generated_IO(self):
        out=self.base/'supervised'
        result=subprocess.run([str(s.PYTHON),'-B',str(Path(fixture.__file__)),'supervise',str(out)],cwd=s.ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['status'],'COMPLETE',value)
        s.manifest(out);self.assertEqual(read_progress(out/'progress.jsonl')['updates'],199)

    def test_supervisor_seals_failure_without_retry(self):
        out=self.base/'failed-stage'
        result=subprocess.run([str(s.PYTHON),'-B',str(Path(fixture.__file__)),'supervise-fail',str(out)],cwd=s.ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['status'],'STOP');self.assertEqual(value['retries'],0)
        self.assertIn('GENERATED_FAILURE',value['reason']);s.manifest(out)


if __name__=='__main__':
    pins=code_pins();start=time.monotonic();stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(stream.getvalue());s.require(pins==code_pins(),'CODE_CHANGED_DURING_TESTS')
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
        tests_passed=result.testsRun-len(result.failures)-len(result.errors),seconds=time.monotonic()-start,
        real_model_forwards=0,real_teacher_rows=0,real_optimizer_steps=0,numeric_access_guard=True,tested_code_pins=pins)
    s.atomic_json(Path(sys.argv[1]),report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
