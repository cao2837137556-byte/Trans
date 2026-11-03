"""Generated-only tests of the paired learning experiment and gates."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
import issue27frontend_paired_train_support_v1 as s
import issue27frontend_paired_train_model_v1 as m
import issue27frontend_paired_train_metrics_v1 as metrics
import issue27frontend_paired_train_runner_v1 as r
import issue27frontend_paired_train_control_v1 as c


def population():
    cs=[]
    for role in ('train','check'):
        for owner in ('A','B'):
            for label in (0,1):
                key=role+owner+str(label);length=label+2
                x=torch.full((length,131),.1+label)
                ts=[]
                for event in range(length):
                    ts.append(dict(uid=key+str(event),context_key=key,component_id=key,
                        owner=owner,label=label,source_group='generated',member='generated',
                        device_family='device',attack_family='attack' if label else 'benign',event=event,
                        old_hard=label if owner=='A' else None,
                        feature_prefix_sha256=s.digest(x[:event+1].numpy().astype('<f4').tobytes())))
                cs.append(dict(key=key,role=role,component=key,length=length,targets=ts,x=x,
                               source='fixture',source_offset=0,offset=0))
    return sorted(cs,key=lambda c:c['key'])


def predictions(cs):
    return {t['uid']:float(1 if t['label'] else -1) for c in cs if c['role']=='check' for t in c['targets']}


class ModelTests(unittest.TestCase):
    def test_exact_architecture_and_no_auxiliary_head(self):
        model=m.Student();self.assertEqual(sum(p.numel() for p in model.parameters()),91265)
        self.assertEqual(list(model._modules),['event_projection','event_activation','encoder','head_hidden','head_activation','head_output'])
        self.assertTrue(all(p.requires_grad for p in model.parameters()))

    def test_seed_reproduces_initialization(self):
        m.configure();a=m.Student();m.configure();b=m.Student()
        self.assertEqual(m.state_hash(a),m.state_hash(b))

    def test_causal_prefix(self):
        model=m.Student();x=torch.randn(5,131)
        a=model([x],['a'])[0];b=model([x[:3]],['a'])[0]
        torch.testing.assert_close(a[:3],b,atol=1e-6,rtol=1e-5)

    def test_batch_order_restored(self):
        model=m.Student();xs=[torch.randn(2,131),torch.randn(4,131),torch.randn(4,131)]
        out=model(xs,['b','z','a'])
        for i,x in enumerate(xs):torch.testing.assert_close(out[i],model([x],['one'])[0],atol=1e-6,rtol=1e-5)

    def test_hidden_state_reset(self):
        model=m.Student();x=torch.randn(2,131);a=model([x],['x'])[0]
        model([torch.ones(3,131)*99],['other'])
        torch.testing.assert_close(a,model([x],['x'])[0],rtol=0,atol=0)

    def test_bad_input_rejected(self):
        model=m.Student()
        for x in (torch.zeros(1,130),torch.zeros(0,131),torch.full((1,131),float('nan')),torch.zeros(1,131,dtype=torch.float64)):
            with self.subTest(shape=x.shape),self.assertRaises(s.Stop):model([x],['x'])

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(s.Stop):m.Student()([torch.zeros(1,131)]*2,['x','x'])

    def test_plain_context_mean_not_target_mean(self):
        cs=population()[:2];model=m.Student()
        qs=model([c['x'] for c in cs],[c['key'] for c in cs])
        expected=sum(torch.nn.functional.binary_cross_entropy_with_logits(q,torch.tensor([t['label'] for t in c['targets']],dtype=torch.float32)) for c,q in zip(cs,qs))
        torch.testing.assert_close(m.context_sum(model,cs),expected)

    def test_all_blocks_receive_gradients(self):
        model=m.Student();m.context_sum(model,population()[:2]).backward()
        for name in ('event_projection','encoder','head_hidden','head_output'):
            self.assertGreater(sum(float(p.grad.abs().sum()) for p in getattr(model,name).parameters()),0)

    def test_microbatch_accumulation_matches_full_loss_gradient(self):
        cs=population()[:2];a=m.Student();b=copy.deepcopy(a)
        (m.context_sum(a,cs)*.25).backward()
        for context in cs:(m.context_sum(b,[context])*.25).backward()
        for p,q in zip(a.parameters(),b.parameters()):torch.testing.assert_close(p.grad,q.grad,atol=2e-7,rtol=2e-5)

    def test_optimizer_fixed_and_single_step(self):
        model=m.Student();opt=m.optimizer(model);before=m.state_hash(model)
        m.update(model,opt,population()[:2],[],1,2,2)
        self.assertNotEqual(before,m.state_hash(model))
        self.assertEqual(opt.defaults['lr'],.001);self.assertEqual(opt.defaults['weight_decay'],.0001)
        self.assertTrue(all(int(st['step'])==1 for st in opt.state.values()))


class ScheduleTests(unittest.TestCase):
    def test_balanced_buckets_no_dropped_tail(self):
        for n,steps in ((65,3),(2,5),(129,2)):
            bs=list(s.buckets(list(range(n)),steps))
            self.assertEqual([x for b in bs for x in b],list(range(n)))
            self.assertLessEqual(max(map(len,bs))-min(map(len,bs)),1)

    def test_order_independent_of_input_order(self):
        self.assertEqual(s.order(['a','b','c'],1,'A'),s.order(['c','a','b'],1,'A'))

    def test_epoch_average_restores_global_objective(self):
        values=list(range(1,66));steps=3
        estimated=sum((steps/len(values))*sum(b) for b in s.buckets(values,steps))/steps
        self.assertAlmostEqual(estimated,sum(values)/len(values))

    def test_owner_masks_trim_prefix(self):
        cs=population();c0=cs[0];c0['role']='train';c0['targets'][0]['owner']='A';c0['targets'][1]['owner']='B'
        av=next(c for c in s.views(cs,'train','A') if c['key']==c0['key'])
        self.assertEqual(av['length'],1);self.assertEqual(len(av['targets']),1)

    def test_views_exclude_check_from_training(self):
        self.assertTrue(all(c['role']=='train' and all(t['owner']=='A' for t in c['targets']) for c in s.views(population(),'train','A')))

    def test_empty_training_owner_rejected(self):
        with self.assertRaises(s.Stop):s.exact_accounting(s.views(population(),'train','A'))

    def test_accounting_counts_target_exposure(self):
        cs=population();a=s.exact_accounting(cs)
        nt={g:sum(len(c['targets']) for c in s.views(cs,'train',g)) for g in ('A','B')}
        self.assertEqual(a['training']['targets'],40*(2*nt['A']+nt['B']))


class QualificationTests(unittest.TestCase):
    def fixture(self):
        membership=[];lawful=[];audits=[];index=[];offset=0
        for c0 in population():
            index.append(dict(context_key=c0['key'],event_offset=str(offset),event_count=str(c0['length'])))
            offset+=c0['length']
            for t in c0['targets']:
                row={k:str(t[k]) for k in ('uid','context_key','source_group','member','owner','label','attack_family','device_family')}
                row.update(event_index=str(t['event']),context_events=str(c0['length']),history='generated')
                kind='none' if t['owner']=='B' else 'attack_hard' if t['label'] else 'benign_normal'
                lawful.append(dict(row,teacher_kind=kind))
                membership.append(dict(row,new_role=c0['role'],component_id=c0['component']))
                audits.append(dict(row,teacher_kind=kind,roundtrip_exact='true',finite='true',feature_width='131',
                                   feature_prefix_sha256=t['feature_prefix_sha256']))
        return membership,lawful,index,audits,[],[]
    def test_metadata_join_and_offsets(self):
        plan=s.qualify_plan(*self.fixture());self.assertEqual(plan['targets'],20)
        self.assertEqual(plan['feature_bytes'],20*524)
    def test_teacher_lineage_drift_rejected(self):
        args=self.fixture();next(t for t in args[1] if t['owner']=='A' and t['label']=='1')['teacher_kind']='none'
        with self.assertRaises(s.Stop):s.qualify_plan(*args)
    def test_benign_uid_reference_drift_rejected(self):
        args=self.fixture();args[3][0]['teacher_kind']='benign_hard'
        with self.assertRaises(s.Stop):s.qualify_plan(*args)
    def test_shared_dependency_cannot_cross_roles(self):
        args=self.fixture()
        for t in args[0]:t['component_id']='same'
        with self.assertRaises(s.Stop):s.qualify_plan(*args)
    def test_context_role_cannot_split(self):
        args=self.fixture();args[0][0]['new_role']='train'
        with self.assertRaises(s.Stop):s.qualify_plan(*args)
    def test_missing_target_rejected(self):
        args=self.fixture();args[0].pop()
        with self.assertRaises(s.Stop):s.qualify_plan(*args)
    def test_source_length_drift_rejected(self):
        args=self.fixture();args[2][0]['event_count']='1'
        with self.assertRaises(s.Stop):s.qualify_plan(*args)


class MetricTests(unittest.TestCase):
    def setUp(self):self.cs=population();self.a=predictions(self.cs);self.b=dict(self.a)
    def run_result(self):return metrics.comparison(self.cs,self.a,self.b)[0]
    def test_identical_correct_no_false_increment(self):
        x=self.run_result();self.assertEqual(x['A_retention'],'PASS');self.assertEqual(x['B_normal_increment']['status'],'NOT_DEMONSTRATED')
    def test_zero_logit_is_attack(self):
        key='checkA00';self.a[key]=0.;self.assertEqual(self.run_result()['A_retention'],'FAIL')
    def test_old_correct_attack_regression_fails(self):
        self.b['checkA10']=-1.;self.assertEqual(self.run_result()['A_retention'],'FAIL')
    def test_A_to_AB_correct_flip_fails_even_old_wrong(self):
        for c0 in self.cs:
            for t in c0['targets']:
                if t['uid']=='checkA00':t['old_hard']=1
        self.b['checkA00']=1.;self.assertEqual(self.run_result()['A_to_AB_negative_flips'],1)
    def test_B_normal_gain(self):
        self.a['checkB00']=1.;self.assertEqual(self.run_result()['B_normal_increment']['status'],'PASS')
    def test_B_attack_regression_blocks_benign_gain(self):
        self.a['checkB00']=1.;self.b['checkB10']=-1.
        self.assertEqual(self.run_result()['B_normal_increment']['status'],'BLOCKED_BY_B_ATTACK_REGRESSION')
    def test_zero_B_attack_not_established(self):
        self.cs=[c0 for c0 in self.cs if c0['key']!='checkB1'];self.a=predictions(self.cs);self.b=dict(self.a)
        self.assertEqual(self.run_result()['B_attack_increment']['status'],'NOT_ESTABLISHED')
    def test_incomplete_or_nonfinite_rejected(self):
        for change in ('missing','nan'):
            a=dict(self.a)
            if change=='missing':a.pop('checkA00')
            else:a['checkA00']=float('nan')
            with self.assertRaises(s.Stop):metrics.comparison(self.cs,a,self.b)
    def test_context_errors_not_target_errors(self):
        self.a['checkB10']=-1.;self.a['checkB11']=-1.
        x=self.run_result()['B_attack_increment']['A'];self.assertEqual(x['errors'],2);self.assertEqual(x['error_contexts'],1)
    def test_uncovered_behavior_disclosed(self):
        self.cs=[c0 for c0 in self.cs if c0['key']!='trainB1']
        _,rows=metrics.comparison(self.cs,self.a,self.b)
        self.assertFalse(next(r0 for r0 in rows['A'] if r0['uid']=='checkB10')['training_covered'])
    def test_terminal_summary_is_bounded_and_excludes_detail(self):
        result=self.run_result();result['groups']=result['groups']*1000
        small=metrics.compact_result(result)
        self.assertLess(len(s.canonical(small)),1024)
        self.assertNotIn('groups',small);self.assertEqual(small['A_retention'],result['A_retention'])


class IOTests(unittest.TestCase):
    def fixture(self,folder):
        cs=population()[:2];cursor=0;raw=bytearray()
        for c0 in cs:c0.update(offset=cursor,source_offset=cursor);b=c0['x'].numpy().astype('<f4').tobytes();raw.extend(b);cursor+=len(b)
        path=folder/'source';path.write_bytes(raw)
        return {'contexts':cs,'feature_bytes':cursor},{'fixture':{'path':str(path),'bytes':cursor,'sha256':s.sha_file(path)}}
    def test_preparation_roundtrip_and_prefix_identity(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);plan,sources=self.fixture(folder);out=folder/'out';out.mkdir();budget=r.Budget(out,s.PREP_CAPS,time.monotonic())
            access=r.prepare_data(plan,sources,out,budget)
            loaded=r.load_prepared(plan,out/'features.f32le',budget)
            self.assertEqual(access['prefixes_verified'],5)
            for a,b in zip(plan['contexts'],loaded):torch.testing.assert_close(a['x'],b['x'])
    def test_wrong_source_hash_stops_before_decode(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);plan,sources=self.fixture(folder);sources['fixture']['sha256']='0'*64
            with self.assertRaises(s.Stop):r.prepare_data(plan,sources,folder,r.Budget(folder,s.PREP_CAPS,time.monotonic()))
            self.assertFalse((folder/'features.f32le').exists())
    def test_prefix_drift_stops(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);plan,sources=self.fixture(folder);plan['contexts'][0]['targets'][0]['feature_prefix_sha256']='0'*64
            with self.assertRaises(s.Stop):r.prepare_data(plan,sources,folder,r.Budget(folder,s.PREP_CAPS,time.monotonic()))
    def test_budget_fails_before_overrun_forward(self):
        with tempfile.TemporaryDirectory() as d:
            b=r.Budget(Path(d),s.CAPS,time.monotonic(),dict(events=0,padded_slots=0,targets=0,contexts=0))
            with self.assertRaises(s.Stop):b.charge(population()[:1])
    def test_no_evaluation_without_both_seals(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(s.Stop):r.terminal_checks(population(),{}, {},Path(d),None)
    def test_full_40_epoch_generated_pair_and_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);cs=population();expected=s.exact_accounting(cs)['total']
            budget=r.Budget(folder,s.CAPS,time.monotonic(),expected)
            models,barrier=r.paired_fit(cs,m.Student(),folder,budget)
            self.assertEqual(barrier['updates'],{'A':40,'AB':40})
            result=r.terminal_checks(cs,models,barrier,folder,budget)
            self.assertEqual(result['status'],'PAIRED_COMPARISON_COMPLETE');self.assertEqual(budget.counts,expected)
    def test_explicit_stage_gates(self):
        for stage in ('prepare','train'):
            p=subprocess.run([sys.executable,'-B',str(Path(c.__file__)),'run-real','--stage',stage],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertNotEqual(p.returncode,0);self.assertIn(b'EXPLICIT_STAGE_AUTHORIZATION_REQUIRED',p.stderr)
    def test_real_attempts_not_started(self):
        self.assertFalse((s.ROOT/s.PREP).exists());self.assertFalse((s.ROOT/s.REAL).exists())
    def test_barrier_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);s.atomic_json(folder/'candidates_sealed.json',{'tampered':True})
            with self.assertRaises(s.Stop):r.terminal_checks(population(),{}, {},folder,None)
    def test_bad_terminal_output_set_rejected(self):
        with tempfile.TemporaryDirectory() as d,patch.object(c.s,'read_json',return_value={}):
            receipt={'status':'WORK_COMPLETE','plan_sha256':'p','stage':'prepare','output_hashes':{}}
            with self.assertRaises(s.Stop):c.validate_worker(receipt,Path(d),{'plan_sha256':'p','stage':'prepare'})
    def test_B_large_bucket_clips_and_updates_once(self):
        a=s.views(population(),'train','A')
        b=[]
        for i in range(33):
            item=copy.deepcopy(s.views(population(),'train','B')[0]);item['key']='b'+str(i);b.append(item)
        model=m.Student();opt=m.optimizer(model);sizes=[]
        with patch.object(torch.nn.utils,'clip_grad_norm_',wraps=torch.nn.utils.clip_grad_norm_) as clip:
            m.update(model,opt,a,b,1,len(a),len(b),lambda batch:sizes.append(len(batch)))
            self.assertEqual(clip.call_count,1)
        self.assertEqual(sizes,[2,32,1]);self.assertTrue(all(int(v['step'])==1 for v in opt.state.values()))


if __name__=='__main__':
    m.configure()
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    # Supervisor fixtures run in a separate standard-library process, matching
    # the real controller's reserved memory (this process has imported torch).
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(tests_run=result.testsRun,tests_passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
                errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
                real_feature_bytes_decoded=0,real_optimizer_steps=0,raw_packets=0,
                scope='generated tensors/files/processes only; one full 40-epoch miniature pair, not a resource pilot')
    print('SYNTHETIC_RESULT '+json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
