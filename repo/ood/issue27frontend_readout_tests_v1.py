"""Generated acceptance for fixed-encoder/full-head training and one endpoint."""
import ast
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
import issue27frontend_readout_fixture_v1 as fixture
import torch
import issue27frontend_readout_support_v1 as s
import issue27frontend_readout_model_v1 as m
import issue27frontend_readout_entry_v1 as entry
import issue27frontend_readout_train_v1 as train
import issue27frontend_readout_evaluate_v1 as e
import issue27frontend_readout_control_v1 as control
import issue27frontend_transfer_model_v1 as original
from issue27frontend_readout_verify_v1 import verify_stage
from issue27frontend_readout_build_v1 import code_pins

fixture.TEST_ROOT.mkdir(parents=True,exist_ok=True)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):m.configure()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=fixture.TEST_ROOT)
        self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)

    def assets(self):return fixture.generated_assets(self.base/'assets')
    def budget(self,out=None):return control.Budget(out or self.base,time.monotonic(),dict(seconds=120))

    def batch(self):
        cs=[fixture.context('normal',0,events=(0,1,2)),fixture.context('attack',1),fixture.context('B',0,'B')]
        r=copy.deepcopy(s.recipe());r['schedule']['steps_per_epoch']=1
        r['data']['A']['contexts']=2;r['data']['B']['contexts']=1
        return cs,r

    def test_frozen_scope_counts_lr_and_no_P(self):
        r=s.recipe();self.assertEqual(set(s.OUTPUTS),{'T','E'})
        self.assertEqual(r['schedule']['updates_all_arms'],3940)
        self.assertEqual(r['evaluation']['targets_all_arms'],280316)
        self.assertEqual(r['optimizer']['lr'],.0001)
        self.assertEqual(r['arm']['trainable_parameters'],8321)
        self.assertFalse(any(p.exists() for p in s.OUTPUTS.values()))

    def test_access_guard_blocks_real_model_and_json(self):
        for name in ['runs/frontend_paired_train_v3_20260910/candidate_AB.pt',
                     'runs/frontend_task_aligned_transfer_p_v1_20260912/teacher_index.json']:
            with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_BLOCKED_REAL_RUN_ACCESS'):(s.ROOT/name).read_bytes()

    def exact_steps(self,frozen):
        cs,r=self.batch();a=m.Student()
        with torch.no_grad():a.head_output.bias.fill_(.37)
        b=copy.deepcopy(a)
        if frozen:
            m.freeze(a)
            for n,p in b.named_parameters():p.requires_grad_(n.startswith(('head_hidden.','head_output.')))
        oa=m.optimizer(a,r) if frozen else m.make_optimizer(a.parameters(),r)
        ob=m.make_optimizer([p for p in b.parameters() if p.requires_grad],r)
        self.assertFalse(oa.state);self.assertFalse(ob.state)
        for epoch in (1,2,3):
            sa=(m.update if frozen else m.numerical_update)(a,oa,cs[:2],cs[2:],epoch,r)
            sb=original.update(b,None,ob,cs[:2],cs[2:],'C0',epoch,None,None,r)
            self.assertEqual(m.state_hash(a),m.state_hash(b))
            for new,old in [('label','label'),('head_gradient_L2','student_gradient_L2'),('clip_factor','clip_factor')]:self.assertEqual(sa[new],sb[old])
            for av,bv in zip(oa.state.values(),ob.state.values()):
                for key in av:torch.testing.assert_close(av[key],bv[key],rtol=0,atol=0)

    def test_three_steps_exact_original_C0_with_frozen_encoder(self):self.exact_steps(True)
    def test_full_unfreeze_numerics_exact_original_C0(self):self.exact_steps(False)

    def test_full_head_updates_and_encoder_has_no_grad_or_optimizer_state(self):
        cs,r=self.batch();model=m.Student();before=m.tensor_hashes(model,m.HEAD+m.FROZEN)
        frozen=m.freeze(model);self.assertEqual(before,m.tensor_hashes(model,m.HEAD+m.FROZEN))
        opt=m.optimizer(model,r)
        m.update(model,opt,cs[:2],cs[2:],1,r);m.verify_frozen(model,frozen,opt)
        after=m.tensor_hashes(model,m.HEAD)
        self.assertTrue(all(after[k]!=before[k] for k in after))
        self.assertEqual(len(opt.state),4)
        self.assertTrue(all(p.grad is None and p not in opt.state for n,p in model.named_parameters() if n.startswith(m.FROZEN)))

    def test_label_context_weighting_independent_reference(self):
        cs,r=self.batch();model=m.Student();m.freeze(model)
        with torch.no_grad():
            qs=model([c['x'] for c in cs],[c['key'] for c in cs])
            means=[torch.stack([torch.nn.functional.binary_cross_entropy_with_logits(q[t['event']],torch.tensor(float(t['label']))) for t in c['targets']]).mean() for c,q in zip(cs,qs)]
            expected=float((means[0]+means[1])/2+means[2])
        stats=m.update(model,m.optimizer(model,r),cs[:2],cs[2:],1,r)
        self.assertAlmostEqual(stats['label'],expected,places=6)

    def test_microbatch_33_contexts_charged_once(self):
        _,r=self.batch();a=[fixture.context('a'+str(i),i%2,events=(0,)) for i in range(33)]
        b=[fixture.context('b',1,'B')];r['data']['A']['contexts']=33
        model=m.Student();m.freeze(model);charged=[]
        m.update(model,m.optimizer(model,r),a,b,1,r,lambda batch:charged.append([c['key'] for c in batch]))
        self.assertEqual([len(batch) for batch in charged],[32,1,1])
        self.assertEqual([k for batch in charged for k in batch],[c['key'] for c in a+b])

    def test_freeze_layout_mutation_rejected(self):
        model=m.Student();m.freeze(model);model.encoder.weight_ih_l0.requires_grad_(True)
        with self.assertRaisesRegex(s.Stop,'FREEZE_LAYOUT'):m.check_layout(model)

    def test_frozen_value_mutation_rejected(self):
        model=m.Student();h=m.freeze(model)
        with torch.no_grad():model.encoder.weight_ih_l0[0,0]+=1
        with self.assertRaisesRegex(s.Stop,'FROZEN_TENSOR_CHANGED'):m.verify_frozen(model,h)

    def test_optimizer_frozen_membership_rejected(self):
        model=m.Student();m.freeze(model);opt=m.make_optimizer(model.parameters(),s.recipe())
        with self.assertRaisesRegex(s.Stop,'OPTIMIZER_PARAMETER_SCOPE'):m.check_layout(model,opt)

    def test_frozen_gradient_and_optimizer_state_rejected(self):
        model=m.Student();m.freeze(model);opt=m.optimizer(model,s.recipe());p=model.encoder.weight_ih_l0
        p.grad=torch.zeros_like(p)
        with self.assertRaisesRegex(s.Stop,'FROZEN_GRADIENT'):m.check_layout(model,opt)
        p.grad=None;opt.state[p]={'step':torch.tensor(1.)}
        with self.assertRaisesRegex(s.Stop,'FROZEN_OPTIMIZER_STATE'):m.check_layout(model,opt)

    def test_original_deployment_and_parameter_count(self):
        a=original.OriginalStudent();b=m.Student();b.load_state_dict(a.state_dict());m.freeze(b)
        xs=[torch.randn(n,131) for n in (2,7,1)];keys=['b','a','c']
        for x,y in zip(a(xs,keys),b(xs,keys)):torch.testing.assert_close(x,y,rtol=0,atol=0)
        self.assertEqual(sum(p.numel() for p in b.parameters()),91265)

    def test_early_target_causality(self):
        model=m.Student();m.freeze(model);x=torch.randn(8,131);z=x.clone();z[3:]+=100
        torch.testing.assert_close(model([x],['a'])[0][:3],model([z],['a'])[0][:3],rtol=0,atol=0)

    def test_entry_no_model_load_forward_or_optimizer(self):
        r,plan=self.assets();budget=self.budget()
        with patch.object(torch,'load',side_effect=AssertionError('load')),patch.object(torch.nn.Module,'__call__',side_effect=AssertionError('forward')),patch.object(torch.optim,'AdamW',side_effect=AssertionError('optimizer')):
            orders=entry.preflight(r,plan,self.base,budget)
        self.assertEqual(len(orders),r['schedule']['epochs'])
        self.assertTrue(all(v==0 for v in budget.access.values()))
        self.assertFalse(s.read_json(self.base/'entry_receipt.json')['new_P_stage'])

    def test_entry_wrong_C0_producer_rejected(self):
        r,plan=self.assets();r['base_contract']['sha256']='0'*64
        with self.assertRaisesRegex(s.Stop,'C0_PRODUCER_RECEIPT'):entry.preflight(r,plan,self.base,self.budget())

    def test_entry_wrong_C0_counts_rejected(self):
        r,plan=self.assets();r['schedule']['expected_counts_per_arm']['updates']+=1
        with self.assertRaisesRegex(s.Stop,'C0_MATCHED_HISTORY'):entry.preflight(r,plan,self.base,self.budget())

    def test_entry_wrong_epoch_order_rejected(self):
        r,plan=self.assets();plan['accounting']['epoch_order_hashes'][0]['A_order_sha256']='0'*64
        with self.assertRaisesRegex(s.Stop,'C0_FROZEN_ORDERS'):entry.preflight(r,plan,self.base,self.budget())

    def test_AB_native_receipt_and_initial_state_required(self):
        r,plan=self.assets();r['inputs']['initial_AB_receipt']['epoch']=39
        with self.assertRaisesRegex(s.Stop,'AB_RECEIPT'):entry.preflight(r,plan,self.base,self.budget())
        r['inputs']['initial_AB_receipt']['epoch']=40;r['inputs']['initial_AB']['state_sha256']='0'*64
        with self.assertRaisesRegex(s.Stop,'AB_RECEIPT'):entry.preflight(r,plan,self.base,self.budget())

    def test_training_reads_only_TRAIN_bytes(self):
        r,plan=self.assets();b=self.budget();cs=s.train_metadata(plan,r)
        loaded=train.load_contexts(cs,Path(r['inputs']['train_check_features']['path']),b)
        self.assertTrue(all(c['role']=='train' for c in loaded))
        self.assertEqual(b.access['feature_bytes_decoded'],r['stages']['T']['expected_feature_bytes_decoded'])
        self.assertLess(b.access['feature_bytes_decoded'],Path(r['inputs']['train_check_features']['path']).stat().st_size)

    def test_feature_prefix_corruption_rejected(self):
        r,plan=self.assets();cs=s.train_metadata(plan,r);cs[0]['targets'][0]['feature_prefix_sha256']='0'*64
        with self.assertRaisesRegex(s.Stop,'PREFIX_IDENTITY'):train.load_contexts(cs,Path(r['inputs']['train_check_features']['path']),self.budget())

    def test_train_check_component_leak_rejected(self):
        r,plan=self.assets();plan['contexts'][-1]['component']=plan['contexts'][0]['component']
        with self.assertRaisesRegex(s.Stop,'COMPONENT_LEAK'):s.train_metadata(plan,r)

    def test_generated_actual_T_E_no_teacher_guard_or_projection(self):
        with patch.object(original,'guard_loss',side_effect=AssertionError('guard')),patch.object(original,'teacher_loss',side_effect=AssertionError('teacher')),patch.object(original,'Projection',side_effect=AssertionError('projection')),patch.object(torch,'load',wraps=torch.load) as loads,patch.object(m,'update',wraps=m.update) as updates:
            r,outs,result=fixture.generated_pipeline(self.base)
        self.assertEqual(loads.call_count,2)
        self.assertEqual([Path(c.args[0]).name for c in loads.call_args_list],['candidate_AB.pt','H_AB.pt'])
        self.assertEqual(updates.call_count,r['schedule']['updates_all_arms'])
        for stage in 'TE':
            s.manifest(outs[stage]);self.assertEqual(s.read_json(outs[stage]/'verification.json')['status'],'PASS')
            access=s.read_json(outs[stage]/'access.json')
            for k in ('teacher_passes','teacher_rows_read','guard_pairs_read','projection_loads','raw_decodes','retries','network_requests'):self.assertEqual(access[k],0)
        rec=s.read_json(outs['T']/'H_AB.receipt.json')
        self.assertEqual(rec['initial_frozen_tensor_hashes'],rec['final_frozen_tensor_hashes'])
        self.assertEqual(len(rec['initial_frozen_tensor_hashes']),6)
        comparison=s.read_json(outs['E']/'comparison.json')
        self.assertEqual(set(comparison['models']),{'A','AB','C0','C1','C2','Q','R','C0_AB','R_AB','old_P2','H_AB'})
        self.assertEqual(set(comparison['contrasts']),{'H_AB-AB','H_AB-C0_AB'})
        self.assertEqual(comparison['check_and_train']['H_AB']['ID_check']['overall']['targets'],1)
        self.assertTrue(comparison['verification']['H_AB']['state_unchanged'])
        self.assertEqual(result['E']['targets'],21)

    def test_E_wrong_candidate_barrier_stops_before_load(self):
        r,plan=self.assets();out=self.base/'T';out.mkdir();s.atomic_json(out/'supervisor_terminal.json',dict(status='COMPLETE'))
        s.atomic_json(out/'candidates_sealed.json',dict(status='FINAL_CANDIDATE_SEALED',recipe_sha256=s.RECIPE_SHA,candidates={'C0_AB':{}}));s.seal(out)
        with patch.dict(s.OUTPUTS,{'T':out}),patch.object(torch,'load',side_effect=AssertionError('early load')):
            with self.assertRaisesRegex(s.Stop,'FINAL_BARRIER'):e.evaluate(r,self.base,self.budget())

    def test_E_missing_T_barrier_stops_before_load(self):
        r,plan=self.assets()
        with patch.dict(s.OUTPUTS,{'T':self.base/'absent'}),patch.object(torch,'load',side_effect=AssertionError('early load')):
            with self.assertRaises(FileNotFoundError):e.evaluate(r,self.base,self.budget())

    def test_persisted_metric_tampering_rejected_without_forward(self):
        r,outs,_=fixture.generated_pipeline(self.base);bad=self.base/'badE';bad.mkdir()
        import shutil
        for p in outs['E'].iterdir():
            if p.is_file() and p.name!='SHA256SUMS':shutil.copyfile(p,bad/p.name)
        result=s.read_json(bad/'comparison.json');result['models']['H_AB']['fixed']['overall']['detected']+=1
        s.atomic_json(bad/'comparison.json',result);b=self.budget(bad);b.access=s.read_json(bad/'access.json')
        with patch.object(torch.nn.Module,'__call__',side_effect=AssertionError('forward')):
            with self.assertRaisesRegex(s.Stop,'E_METRIC_RECOMPUTATION'):verify_stage('E',bad,r,b)

    def test_persisted_frozen_receipt_tampering_rejected(self):
        r,outs,_=fixture.generated_pipeline(self.base);bad=self.base/'badT';bad.mkdir()
        import shutil
        for p in outs['T'].iterdir():
            if p.is_file() and p.name!='SHA256SUMS':shutil.copyfile(p,bad/p.name)
        barrier=s.read_json(bad/'candidates_sealed.json');rec=barrier['candidates']['H_AB'];rec['final_frozen_tensor_hashes']['encoder.bias_ih_l0']='0'*64
        s.atomic_json(bad/'candidates_sealed.json',barrier);s.atomic_json(bad/'H_AB.receipt.json',rec)
        b=self.budget(bad);b.access=s.read_json(bad/'access.json')
        with self.assertRaisesRegex(s.Stop,'T_FROZEN_IDENTITY'):verify_stage('T',bad,r,b)

    def test_metric_functions_unchanged_from_sealed_ABstart(self):
        def functions(path):return {n.name:ast.dump(n) for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef)}
        a=functions(Path(e.__file__));b=functions(s.ROOT/'repo/ood/issue27frontend_abstart_evaluate_v1.py')
        for name in ('ranking','fixed','flips','contrast','compare_ab_tail','tail_composition','read_baseline','save_predictions','read_predictions'):self.assertEqual(a[name],b[name],name)

    def test_tie_budget_no_split_or_fill(self):
        rows=[dict(uid='a',label=1,attack_family='f')]+[dict(uid=str(i),label=0,attack_family='n') for i in range(100)]
        q={t['uid']:-float(i) for i,t in enumerate(rows)};q['a']=q['0']=q['1']=2.
        points=e.ranking(rows,q)['points'];self.assertIsNone(points['0.01']['threshold']);self.assertEqual(points['0.01']['false_alarms'],0)

    def test_AUROC_pairwise_reference(self):
        rows=[dict(uid=k,label=y,attack_family='f') for k,y in [('a',1),('b',1),('n',0)]]
        self.assertEqual(e.ranking(rows,{'a':2.,'b':0.,'n':1.})['auroc'],.5)

    def test_exact_fraction_ignores_rounded_display(self):
        r,_=self.assets();rows=e.read_baseline(Path(r['inputs']['expanded_A_predictions']['path']));q={t['uid']:t['a_logit'] for t in rows}
        a=dict(fixed=e.fixed(rows,{k:int(v>=0) for k,v in q.items()}),ranking=e.ranking(rows,q));b=copy.deepcopy(a)
        b['fixed']['overall']['recall']=.123
        self.assertEqual(e.contrast(a,b)['status'],'NO_CHANGE')
        self.assertEqual(e.contrast(a,b)['exact_desired_deltas'],['0']*6)

    def test_tail_diagnostics_separate_from_six_metric_gate(self):
        r,_=self.assets();rows=e.read_baseline(Path(r['inputs']['expanded_A_predictions']['path']));q={t['uid']:t['a_logit'] for t in rows};rank=e.ranking(rows,q)
        for cap,v in e.tail_composition(rows,q,rank).items():self.assertEqual(v['false_alarms'],rank['points'][cap]['false_alarms'])
        a=dict(fixed=e.fixed(rows,{k:int(v>=0) for k,v in q.items()}),ranking=rank);b=copy.deepcopy(a)
        b['ranking']['points']['0.001']['detected']-=1
        self.assertEqual(e.contrast(a,b)['status'],'NO_CHANGE')
        self.assertEqual(e.compare_ab_tail(b,a)['0.001']['relation'],'LESS')
        self.assertTrue(e.compare_ab_tail(b,a)['0.001']['diagnostic_only'])

    def test_authorization_missing_and_old_tokens_block_launch(self):
        for token in [None,'I_AUTHORIZE_ONE_AB_START_CONTROL_V1_TE']:
            args=['readout','run','--stage','TE']+([] if token is None else ['--authorization',token])
            with patch.object(sys,'argv',args),patch.object(control,'supervise') as run:
                with self.assertRaises(s.Stop):control.main()
                run.assert_not_called()

    def test_duplicate_attempt_blocked(self):
        with patch.dict(s.OUTPUTS,{'T':self.base}),patch.object(sys,'argv',['readout','run','--stage','T','--authorization',s.TOKENS['T']]):
            with self.assertRaisesRegex(s.Stop,'ONE_ATTEMPT_ALREADY_EXISTS'):control.main()

    def test_chain_stops_on_exception_no_E_or_retry(self):
        with patch.dict(s.OUTPUTS,{k:self.base/k for k in 'TE'}),patch.object(sys,'argv',['readout','run','--stage','TE','--authorization',s.TOKENS['TE']]),patch.object(control,'supervise',return_value={'status':'STOP'}) as run,patch('sys.stdout',io.StringIO()):
            with self.assertRaises(SystemExit):control.main()
            self.assertEqual(run.call_count,1)

    def test_chain_continues_without_second_permission(self):
        with patch.dict(s.OUTPUTS,{k:self.base/k for k in 'TE'}),patch.object(sys,'argv',['readout','run','--stage','TE','--authorization',s.TOKENS['TE']]),patch.object(control,'supervise',return_value={'status':'COMPLETE'}) as run,patch('sys.stdout',io.StringIO()):
            control.main();self.assertEqual([c.args[0] for c in run.call_args_list],['T','E'])

    def test_readonly_status_no_model_load(self):
        with patch.dict(s.OUTPUTS,{'T':self.base/'absent'}),patch.object(torch,'load',side_effect=AssertionError('model loaded')):
            self.assertEqual(control.status('T')['status'],'NOT_STARTED')

    def test_terminal_progress_with_simultaneous_open_readers(self):
        control.present(self.base,dict(status='STARTING'))
        with (self.base/'status.md').open('rb'),(self.base/'status.html').open('rb'):
            s.atomic_json(self.base/'progress.json',dict(targets_complete=280316,targets_total=280316))
            control.present(self.base,dict(status='COMPLETE',stage='E'))
        self.assertIn('280316/280316',(self.base/'status.md').read_text(encoding='utf-8'))

    def supervise(self,mode):
        out=self.base/mode
        result=subprocess.run([str(s.PYTHON),'-B',str(Path(fixture.__file__)),mode,str(out)],cwd=s.ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout);s.manifest(out);return value

    def test_windows_supervisor_generated_success(self):self.assertEqual(self.supervise('supervise')['status'],'COMPLETE')
    def test_windows_supervisor_generated_failure(self):
        v=self.supervise('supervise-fail');self.assertEqual(v['status'],'STOP');self.assertEqual(v['retries'],0)
    def test_windows_supervisor_wall_cap(self):
        v=self.supervise('supervise-wall');self.assertEqual(v['status'],'STOP');self.assertIn('WALL_CAP',v['reason']);self.assertEqual(v['retries'],0)
    def test_worker_budget_stops_before_work(self):
        b=control.Budget(self.base,time.monotonic()-30,dict(seconds=10))
        with self.assertRaisesRegex(s.Stop,'WORKER_WALL_CAP'):b.check()


if __name__=='__main__':
    pins=code_pins();start=time.monotonic();stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(stream.getvalue());s.require(pins==code_pins(),'CODE_CHANGED_DURING_TESTS')
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
        tests_passed=result.testsRun-len(result.failures)-len(result.errors),seconds=time.monotonic()-start,
        real_model_forwards=0,real_teacher_rows=0,real_optimizer_steps=0,numeric_access_guard=True,
        tested_code_pins=pins,test_log=stream.getvalue())
    s.atomic_json(Path(sys.argv[1]),report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
