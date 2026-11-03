"""Generated acceptance: exact old objectives, sealed reuse and supervised T/E."""
import copy
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import issue27frontend_abstart_fixture_v1 as fixture
import numpy as np
import torch
import issue27frontend_abstart_support_v1 as s
import issue27frontend_abstart_model_v1 as m
import issue27frontend_abstart_reuse_v1 as reuse
import issue27frontend_abstart_train_v1 as train
import issue27frontend_abstart_evaluate_v1 as e
import issue27frontend_abstart_control_v1 as control
import issue27frontend_transfer_model_v1 as old
import issue27frontend_aligned_model_v1 as aligned
from issue27frontend_abstart_build_v1 import code_pins

fixture.TEST_ROOT.mkdir(parents=True, exist_ok=True)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): m.configure()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=fixture.TEST_ROOT)
        self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)

    def assets(self): return fixture.generated_assets(self.base/'assets')

    def budget(self): return control.Budget(self.base,time.monotonic(),dict(seconds=120))

    def batch(self):
        cs=[fixture.context('normal',0,events=(0,1,2)),fixture.context('attack',1),fixture.context('B',0,'B')]
        r=copy.deepcopy(s.recipe());r['schedule']['steps_per_epoch']=1
        r['data']['A']['contexts']=2;r['data']['B']['contexts']=1
        r['teacher_cache'].update(expected_N_T0=1,expected_N_T1=1)
        cache={t['uid']:dict(margin=torch.tensor(3. if t['label'] else -3.),scale=torch.tensor(2.),target=torch.linspace(-1,1,128)) for t in s.targets(cs[:2])}
        guard=({c['key']:[dict(t,logit=2. if t['label'] else -2.) for t in c['targets']] for c in cs[:2]},2.)
        return cs,r,cache,guard

    def test_frozen_scope_counts_and_no_P(self):
        r=s.recipe();self.assertEqual(set(s.OUTPUTS),{'T','E'})
        self.assertEqual(r['schedule']['updates_all_arms'],7880)
        self.assertEqual(r['evaluation']['targets_all_arms'],560632)
        self.assertFalse(any(p.exists() for p in s.OUTPUTS.values()))

    def test_no_real_json_or_model_access(self):
        for name in ['runs/frontend_task_aligned_transfer_p_v1_20260912/teacher_index.json',
                     'runs/frontend_paired_train_v3_20260910/candidate_AB.pt']:
            with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_BLOCKED_REAL_RUN_ACCESS'):(s.ROOT/name).read_bytes()

    def exact_objective(self, arm):
        cs,r,cache,guard=self.batch();a=m.Student()
        with torch.no_grad(): a.head_output.bias.fill_(.37)
        b=copy.deepcopy(a);da=m.Projection() if arm=='R_AB' else None
        db=copy.deepcopy(da);oa=m.optimizer(a,da,r);ob=m.optimizer(b,db,r)
        self.assertFalse(oa.state);self.assertFalse(ob.state)
        for epoch in (1,2,3):
            sa=m.update(a,da,oa,cs[:2],cs[2:],arm,epoch,guard,cache,r)
            if arm=='C0_AB': sb=old.update(b,db,ob,cs[:2],cs[2:],'C0',epoch,guard,cache,r)
            else: sb=aligned.update(b,db,ob,cs[:2],cs[2:],'R',epoch,guard,cache,r)
            self.assertEqual(m.state_hash(a),m.state_hash(b))
            if da is not None:self.assertEqual(m.state_hash(da),m.state_hash(db))
            for k in ('label','guard','student_gradient_L2','D_gradient_L2','clip_factor'):
                self.assertEqual(sa[k],sb[k])
            for av,bv in zip(oa.state.values(),ob.state.values()):
                for key in av:torch.testing.assert_close(av[key],bv[key],rtol=0,atol=0)

    def test_C0_three_steps_match_original(self): self.exact_objective('C0_AB')
    def test_R_three_steps_match_original(self): self.exact_objective('R_AB')

    def test_C0_never_calls_guard_teacher_or_projection(self):
        cs,r,cache,guard=self.batch();model=m.Student();opt=m.optimizer(model,None,r)
        with patch.object(old,'guard_loss',side_effect=AssertionError('guard called')),patch.object(old,'teacher_loss',side_effect=AssertionError('teacher called')),patch.object(aligned,'teacher_terms',side_effect=AssertionError('teacher called')):
            stats=m.update(model,None,opt,cs[:2],cs[2:],'C0_AB',1,object(),object(),r)
        self.assertEqual(stats['pairs'],0);self.assertEqual(stats['teacher_targets'],0)

    def test_nonzero_initial_guard_is_valid(self):
        cs,r,cache,guard=self.batch();model=m.Student();d=m.Projection()
        with torch.no_grad():model.head_output.weight.zero_();model.head_output.bias.zero_()
        stats=m.update(model,d,m.optimizer(model,d,r),cs[:2],cs[2:],'R_AB',1,guard,cache,r)
        self.assertGreater(stats['guard'],0);self.assertGreater(stats['pairs'],0)

    def test_zero_D_no_rng_and_original_deployment(self):
        state=torch.get_rng_state().clone();d=m.Projection();self.assertTrue(torch.equal(state,torch.get_rng_state()))
        a=old.OriginalStudent();b=m.Student();b.load_state_dict(a.state_dict())
        xs=[torch.randn(n,131) for n in (2,7,1)];keys=['b','a','c']
        for x,y in zip(a(xs,keys),b(xs,keys)):torch.testing.assert_close(x,y,rtol=0,atol=0)
        self.assertEqual(sum(v.numel() for v in b.parameters()),91265)
        self.assertEqual(sum(v.numel() for v in d.parameters()),16512)

    def test_early_target_causality(self):
        model=m.Student();x=torch.randn(8,131);z=x.clone();z[3:]+=100
        torch.testing.assert_close(model([x],['a'])[0][:3],model([z],['a'])[0][:3],rtol=0,atol=0)

    def test_reuse_no_derive_forward_or_optimizer(self):
        r,plan=self.assets();cs=s.train_metadata(plan,r);b=self.budget()
        with patch('issue27frontend_aligned_prepare_v1.derive',side_effect=AssertionError('derive')), \
             patch.object(torch.nn.Module,'__call__',side_effect=AssertionError('forward')), \
             patch.object(torch.optim,'AdamW',side_effect=AssertionError('optimizer')):
            guard,cache=reuse.preflight(r,cs,self.base,b)
        self.assertEqual(len(cache),r['teacher_cache']['expected_targets'])
        self.assertEqual(b.access['derived_teacher_rows'],0);self.assertEqual(b.access['student_forwards'],0)
        self.assertFalse((self.base/'P').exists())

    def test_reuse_wrong_producer_sha_rejected(self):
        r,plan=self.assets();r['prepared_teacher_reuse']['producer_recipe_sha256']='0'*64
        with self.assertRaisesRegex(s.Stop,'REUSE_PRODUCER'):reuse.load_prepared(s.train_metadata(plan,r),r,self.budget())

    def test_reuse_scale_bits_rejected(self):
        r,plan=self.assets();r['prepared_teacher_reuse']['s_q32_hex']='00000000'
        with self.assertRaisesRegex(s.Stop,'REUSE_FIXED_VALUE'):reuse.load_prepared(s.train_metadata(plan,r),r,self.budget())

    def test_reuse_receipt_keeps_old_producer_new_consumer(self):
        r,plan=self.assets();self.assertNotEqual(s.RECIPE_SHA,r['prepared_teacher_reuse']['producer_recipe_sha256'])
        reuse.preflight(r,s.train_metadata(plan,r),self.base,self.budget())
        result=s.read_json(self.base/'reuse_receipt.json')
        self.assertEqual(result['recipe_sha256'],s.RECIPE_SHA)
        self.assertEqual(result['producer_recipe_sha256'],r['prepared_teacher_reuse']['producer_recipe_sha256'])

    def test_teacher_label_identity_rejected(self):
        r,plan=self.assets();cs=s.train_metadata(plan,r)
        # Keep count/eligibility unchanged but make the UID refer to a different context.
        for c in cs:
            if c['key']=='a0':
                for target in c['targets']:target['context_key']='other'
        with self.assertRaisesRegex(s.Stop,'REUSE_ROW_JOIN'):reuse.load_prepared(cs,r,self.budget())

    def test_saved_margin_sign_rejected_even_with_consistent_fixture_hashes(self):
        r,plan=self.assets();spec=r['prepared_teacher_reuse']
        # Model a malformed newly supplied producer, not a re-run or edit of a real seal.
        src=Path(spec['index']['path']);rows=s.read_json(src)
        values=np.fromfile(spec['margins']['path'],dtype='<f4');values[0]=-values[0]
        rows[0].update(margin32=float(values[0]),margin64=float(values[0]),margin32_hex=values[0].tobytes().hex())
        new=self.base/'bad_producer';new.mkdir()
        s.atomic_json(new/'teacher_index.json',rows);(new/'margins.f32le').write_bytes(values.tobytes())
        receipt=s.read_json(Path(spec['receipt']['path']))
        receipt.update(index_sha256=s.sha(new/'teacher_index.json'),margins_sha256=s.sha(new/'margins.f32le'))
        s.atomic_json(new/'preparation_receipt.json',receipt);s.atomic_json(new/'supervisor_terminal.json',dict(status='COMPLETE'));s.seal(new)
        for key,name in [('manifest','SHA256SUMS'),('index','teacher_index.json'),('margins','margins.f32le'),('receipt','preparation_receipt.json'),('terminal','supervisor_terminal.json')]:spec[key]=fixture.pin(new/name)
        with self.assertRaisesRegex(s.Stop,'REUSE_MARGIN_SIGN'):reuse.load_prepared(s.train_metadata(plan,r),r,self.budget())

    def test_AB_native_terminal_schema_required(self):
        r,plan=self.assets();r['inputs']['initial_AB_receipt']['epoch']=39
        with self.assertRaisesRegex(s.Stop,'AB_RECEIPT'):reuse.preflight(r,s.train_metadata(plan,r),self.base,self.budget())

    def test_reuse_margin_file_corruption_rejected(self):
        r,plan=self.assets();path=Path(r['prepared_teacher_reuse']['margins']['path'])
        with path.open('r+b') as f:f.write(b'xxxx')
        with self.assertRaisesRegex(s.Stop,'SEALED_FILE_DRIFT'):reuse.load_prepared(s.train_metadata(plan,r),r,self.budget())

    def test_guard_scale_not_reestimated(self):
        r,plan=self.assets()
        with patch('statistics.median',side_effect=AssertionError('reestimate')):
            _,scale=reuse.load_guard(s.train_metadata(plan,r),r,self.budget())
        self.assertEqual(scale,r['losses']['A_guard']['s_A'])

    def test_guard_wrong_scale_rejected(self):
        r,plan=self.assets();r['losses']['A_guard']['s_A']=99.
        with self.assertRaisesRegex(s.Stop,'GUARD_SCALE'):reuse.load_guard(s.train_metadata(plan,r),r,self.budget())

    def test_training_reads_only_train_bytes(self):
        r,plan=self.assets();b=self.budget();cs=s.train_metadata(plan,r)
        loaded=train.load_contexts(cs,Path(r['inputs']['train_check_features']['path']),b)
        self.assertTrue(all(c['role']=='train' for c in loaded))
        self.assertEqual(b.access['feature_bytes_decoded'],r['stages']['T']['expected_feature_bytes_decoded'])

    def test_full_generated_T_E_and_independent_states(self):
        with patch('issue27frontend_abstart_train_v1.m.update',wraps=m.update) as update:
            r,outs,result=fixture.generated_pipeline(self.base)
        for stage in 'TE':s.manifest(outs[stage]);self.assertEqual(s.read_json(outs[stage]/'verification.json')['status'],'PASS')
        barrier=s.read_json(outs['T']/'candidates_sealed.json');a,b=[barrier['candidates'][k] for k in ('C0_AB','R_AB')]
        self.assertEqual(a['initial_state_sha256'],b['initial_state_sha256'])
        self.assertEqual(a['initial_state_sha256'],r['inputs']['initial_AB']['state_sha256'])
        self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['guard_pair_occurrences'],0)
        self.assertEqual(a['teacher_target_presentations'],0)
        self.assertEqual(b['teacher_target_presentations'],r['schedule']['epochs']*r['teacher_cache']['expected_targets'])
        log=[json.loads(x) for x in (outs['T']/'epoch_log.jsonl').read_text().splitlines()]
        self.assertTrue(all(v['raw_logit_MAE'] is None for v in log if v['arm']=='C0_AB'))
        comparison=s.read_json(outs['E']/'comparison.json')
        self.assertEqual(set(comparison['models']),{'A','AB','C0','C1','C2','Q','R','C0_AB','R_AB','old_P2'})
        self.assertEqual(set(comparison['contrasts']),set(r['evaluation']['contrasts']))
        self.assertEqual(result['E']['targets'],r['evaluation']['targets_all_arms'])
        self.assertEqual(update.call_count,r['schedule']['updates_all_arms'])

    def test_E_before_both_candidates_rejected(self):
        r,plan=self.assets();out=self.base/'T';out.mkdir();s.atomic_json(out/'supervisor_terminal.json',dict(status='COMPLETE'))
        s.atomic_json(out/'candidates_sealed.json',dict(status='BOTH_FINAL_CANDIDATES_SEALED',recipe_sha256=s.RECIPE_SHA,candidates={'C0_AB':{}}));s.seal(out)
        with patch.dict(s.OUTPUTS,{'T':out}),patch.object(torch,'load',side_effect=AssertionError('model loaded early')):
            with self.assertRaisesRegex(s.Stop,'FINAL_ARM_SET'):e.evaluate(r,self.base,self.budget())

    def test_tie_budget_no_split_or_fill(self):
        rows=[dict(uid='a',label=1,attack_family='f')]+[dict(uid=str(i),label=0,attack_family='n') for i in range(100)]
        q={t['uid']:-float(i) for i,t in enumerate(rows)};q['a']=q['0']=q['1']=2.
        points=e.ranking(rows,q)['points']
        self.assertIsNone(points['0.01']['threshold']);self.assertEqual(points['0.01']['false_alarms'],0)

    def test_auc_pairwise_reference(self):
        rows=[dict(uid=k,label=y,attack_family='f') for k,y in [('a',1),('b',1),('n',0)]]
        self.assertEqual(e.ranking(rows,{'a':2.,'b':0.,'n':1.})['auroc'],.5)

    def test_exact_fraction_comparison_ignores_rounded_display(self):
        r,plan=self.assets();baseline=e.read_baseline(Path(r['inputs']['expanded_A_predictions']['path']))
        q={t['uid']:t['a_logit'] for t in baseline}
        a=dict(fixed=e.fixed(baseline,{k:int(v>=0) for k,v in q.items()}),ranking=e.ranking(baseline,q))
        b=copy.deepcopy(a);b['fixed']['overall']['recall']=.123 # display not evidence
        self.assertEqual(e.contrast(a,b)['status'],'NO_CHANGE')
        self.assertTrue(all(v=='0' for v in e.contrast(a,b)['exact_desired_deltas']))
        self.assertEqual(len(e.contrast(a,b)['exact_desired_deltas']),6)

    def test_tail_counts_and_comparison_separate(self):
        r,plan=self.assets();rows=e.read_baseline(Path(r['inputs']['expanded_A_predictions']['path']))
        q={t['uid']:t['a_logit'] for t in rows};rank=e.ranking(rows,q)
        for cap,v in e.tail_composition(rows,q,rank).items():self.assertEqual(v['false_alarms'],rank['points'][cap]['false_alarms'])
        value=e.compare_ab_tail({'ranking':rank},{'ranking':rank})
        self.assertTrue(all(v['relation']=='EQUAL' and v['diagnostic_only'] for v in value.values()))

    def test_authorization_and_old_tokens_block_launch(self):
        for token in [None,'I_AUTHORIZE_ONE_TASK_ALIGNED_TRANSFER_V1_TE']:
            args=['abstart','run','--stage','TE']+([] if token is None else ['--authorization',token])
            with patch.object(sys,'argv',args),patch.object(control,'supervise') as run:
                with self.assertRaises(s.Stop):control.main()
                run.assert_not_called()

    def test_duplicate_attempt_blocked(self):
        with patch.dict(s.OUTPUTS,{'T':self.base}),patch.object(sys,'argv',['abstart','run','--stage','T','--authorization',s.TOKENS['T']]):
            with self.assertRaises(s.Stop):control.main()

    def test_chain_stops_on_exception(self):
        with patch.dict(s.OUTPUTS,{k:self.base/k for k in 'TE'}),patch.object(sys,'argv',['abstart','run','--stage','TE','--authorization',s.TOKENS['TE']]),patch.object(control,'supervise',return_value={'status':'STOP'}) as run,patch('sys.stdout',io.StringIO()):
            with self.assertRaises(SystemExit):control.main()
            self.assertEqual(run.call_count,1)

    def test_chain_continues_without_second_permission(self):
        with patch.dict(s.OUTPUTS,{k:self.base/k for k in 'TE'}),patch.object(sys,'argv',['abstart','run','--stage','TE','--authorization',s.TOKENS['TE']]),patch.object(control,'supervise',return_value={'status':'COMPLETE'}) as run,patch('sys.stdout',io.StringIO()):
            control.main();self.assertEqual(run.call_count,2)

    def test_status_no_model_import_needed(self):
        with patch.dict(s.OUTPUTS,{'T':self.base/'absent'}),patch.object(torch,'load',side_effect=AssertionError('model loaded')):
            self.assertEqual(control.status('T')['status'],'NOT_STARTED')

    def test_terminal_progress_and_open_readers(self):
        control.present(self.base,dict(status='STARTING'))
        with (self.base/'status.md').open('rb'),(self.base/'status.html').open('rb'):
            s.atomic_json(self.base/'progress.json',dict(targets_complete=560632,targets_total=560632))
            control.present(self.base,dict(status='COMPLETE',stage='E'))
        self.assertIn('560632/560632',(self.base/'status.md').read_text(encoding='utf-8'))

    def supervise(self,mode):
        out=self.base/mode
        result=subprocess.run([str(s.PYTHON),'-B',str(Path(fixture.__file__)),mode,str(out)],cwd=s.ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);s.manifest(out);return value

    def test_windows_supervisor_generated_success(self):self.assertEqual(self.supervise('supervise')['status'],'COMPLETE')
    def test_windows_supervisor_generated_failure(self):
        v=self.supervise('supervise-fail');self.assertEqual(v['status'],'STOP');self.assertEqual(v['retries'],0)

    def test_windows_supervisor_enforces_wall_budget(self):
        v=self.supervise('supervise-wall');self.assertEqual(v['status'],'STOP')
        self.assertIn('WALL_CAP',v['reason']);self.assertEqual(v['retries'],0)

    def test_worker_budget_stops_before_work(self):
        b=control.Budget(self.base,time.monotonic()-30,dict(seconds=10))
        with self.assertRaisesRegex(s.Stop,'WORKER_WALL_CAP'):b.check()


if __name__=='__main__':
    pins=code_pins();start=time.monotonic();stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(stream.getvalue());s.require(pins==code_pins(),'CODE_CHANGED_DURING_TESTS')
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
        tests_passed=result.testsRun-len(result.failures)-len(result.errors),seconds=time.monotonic()-start,
        real_model_forwards=0,real_teacher_rows=0,real_optimizer_steps=0,numeric_access_guard=True,tested_code_pins=pins)
    s.atomic_json(Path(sys.argv[1]),report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
