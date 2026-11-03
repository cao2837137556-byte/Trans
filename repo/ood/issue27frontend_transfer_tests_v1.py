"""Generated-only acceptance tests; real numeric assets are never opened."""
import copy
import io
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch
import numpy as np
import torch
from torch.nn import functional as F
import issue27frontend_transfer_support_v1 as s
import issue27frontend_transfer_model_v1 as m
import issue27frontend_transfer_prepare_v1 as p
import issue27frontend_transfer_train_v1 as train
import issue27frontend_transfer_evaluate_v1 as e
import issue27frontend_transfer_control_v1 as control

TEST_ROOT = s.ROOT/'tmp/task_knowledge_transfer_synthetic_v1'
TEST_ROOT.mkdir(parents=True,exist_ok=True)


def no_real_numeric(event,args):
    if event != 'open' or not isinstance(args[0],(str,bytes,os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if s.ROOT/'runs' in path.parents and path.suffix.lower() in ('.pt','.npz','.npy','.f32le','.gz'):
        raise RuntimeError('SYNTHETIC_TEST_BLOCKED_REAL_NUMERIC_ACCESS:'+str(path))


def context(key,label,owner='A',length=3,events=(0,2),old=None,role='train'):
    ts = [dict(uid=key+':'+str(i),context_key=key,event=i,label=label,owner=owner,old_hard=label if old is None else old,
               component_id=key,new_role=role,attack_family='family'+str(label),device_family='device',source_group=key) for i in events]
    return dict(key=key,role=role,component=key,length=length,targets=ts,x=torch.randn(length,131))


def guard_for(cs):
    return {c['key']:[dict(t,logit=2. if t['label'] else -2.,hard=t['label']) for t in c['targets']] for c in cs if c['targets'][0]['owner']=='A'}


def small_recipe(cs,epochs=2):
    r = copy.deepcopy(s.recipe()); r['schedule'].update(epochs=epochs,steps_per_epoch=1,updates_per_arm=epochs,
        target_presentations_per_arm=sum(len(c['targets']) for c in cs)*epochs)
    r['data'].update(train_targets=sum(len(c['targets']) for c in cs),train_contexts=len(cs))
    for g in 'AB':
        ts = [t for c in cs for t in c['targets'] if t['owner']==g]
        r['data'][g] = dict(targets=len(ts),attack=sum(t['label'] for t in ts),benign=sum(1-t['label'] for t in ts),contexts=len({t['context_key'] for t in ts}))
    eligible = [t for c in cs for t in c['targets'] if t['owner']=='A' and t['old_hard']==t['label']]
    f = r['losses']['P2_feature']
    f.update(targets=len(eligible),attack_targets=sum(t['label'] for t in eligible),benign_targets=sum(1-t['label'] for t in eligible))
    f.update({('expected_N_T'+str(y)):len({t['context_key'] for t in eligible if t['label']==y}) for y in (0,1)})
    gs = guard_for(cs)
    r['losses']['A_guard'].update(s_A=2.,eligible_targets=sum(map(len,gs.values())),eligible_contexts=len(gs),pair_occurrences=epochs)
    r['schedule']['updates_all_arms']=3*epochs
    return r


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m.configure()

    def test_recipe_and_design_seals(self):
        self.assertEqual(s.recipe()['schedule']['updates_all_arms'],11820)

    def test_forward_original_equivalence(self):
        original=m.OriginalStudent(); new=m.Student(); new.load_state_dict(original.state_dict())
        xs=[torch.randn(n,131) for n in (7,1,4,4)]
        old=original(xs,['b','a','d','c']); qs,hs=new(xs,['b','a','d','c'],with_hidden=True)
        for a,b in zip(old,qs):
            torch.testing.assert_close(a,b,rtol=0,atol=0)
        self.assertEqual([h.shape for h in hs],[(7,128),(1,128),(4,128),(4,128)])

    def test_early_event_causality(self):
        model=m.Student(); x=torch.randn(6,131); modified=x.clone(); modified[3:]+=100
        a=model([x],['a'])[0]; b=model([modified],['a'])[0]
        torch.testing.assert_close(a[:3],b[:3],rtol=0,atol=0)

    def test_padding_does_not_change_short_sequence(self):
        model=m.Student(); x=torch.randn(2,131)
        solo=model([x],['a'])[0]; batched=model([x,torch.randn(10,131)],['a','b'])[0]
        torch.testing.assert_close(solo,batched,rtol=1e-5,atol=1e-7)

    def test_projection_zero_rng_parameters(self):
        rng=torch.get_rng_state().clone(); d=m.Projection()
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertEqual(sum(x.numel() for x in d.parameters()),16512)
        self.assertTrue(torch.count_nonzero(d(torch.randn(3,128))).item()==0)

    def test_projection_gradient_first_and_later_step(self):
        model=m.Student(); d=m.Projection(); opt=torch.optim.SGD(d.parameters(),lr=.2)
        x=torch.randn(4,131); _,hs=model([x],['a'],with_hidden=True)
        m.huber(d(hs[0])-torch.ones(4,128)).mean().backward()
        self.assertEqual(m.gradient_norm(model.encoder.parameters()),0.)
        self.assertGreater(m.gradient_norm(d.parameters()),0.)
        opt.step(); model.zero_grad(); d.zero_grad()
        _,hs=model([x],['a'],with_hidden=True)
        m.huber(d(hs[0])-torch.ones(4,128)).mean().backward()
        self.assertGreater(m.gradient_norm(model.encoder.parameters()),0.)

    def test_deployment_has_no_projection(self):
        model=m.Student(); state=copy.deepcopy(model.state_dict()); d=m.Projection()
        d.bias.data.fill_(9.)
        restored=m.OriginalStudent(); restored.load_state_dict(state,strict=True)
        self.assertEqual(m.state_hash(model),m.state_hash(restored))
        self.assertEqual(sum(v.numel() for v in state.values()),91265)

    def test_huber_values_and_gradient(self):
        x=torch.tensor([-2.,-.5,0.,.5,2.],requires_grad=True)
        torch.testing.assert_close(m.huber(x),torch.tensor([1.5,.125,0.,.125,1.5]))
        m.huber(x).sum().backward()
        torch.testing.assert_close(x.grad,torch.tensor([-1.,-.5,0.,.5,1.]))

    def test_guard_zero_and_violation_gradient(self):
        cs=[context('attack',1),context('normal',0)]; gs=guard_for(cs)
        qs=[torch.full((3,),2.,requires_grad=True),torch.full((3,),-2.,requires_grad=True)]
        loss,n=m.guard_loss(cs,qs,gs,1,2.); self.assertEqual(n,1); self.assertEqual(float(loss),0.)
        qs=[torch.full((3,),-1.,requires_grad=True),torch.full((3,),1.,requires_grad=True)]
        loss,_=m.guard_loss(cs,qs,gs,1,2.); loss.backward()
        self.assertLess(float(qs[0].grad.sum()),0.); self.assertGreater(float(qs[1].grad.sum()),0.)

    def test_guard_rotation_and_components(self):
        cs=[context('attack',1),context('normal',0)]; gs=guard_for(cs)
        pairs=[s.guard_pairs(cs,gs,k,2.)[0] for k in (1,2)]
        self.assertNotEqual(pairs[0][0]['uid'],pairs[1][0]['uid'])
        for t in gs['normal']: t['component_id']='attack'
        self.assertEqual(s.guard_pairs(cs,gs,1,2.),[])

    def test_guard_empty_bucket_zero(self):
        cs=[context('normal',0)]; q=[torch.randn(3,requires_grad=True)]
        loss,n=m.guard_loss(cs,q,guard_for(cs),1,2.); loss.backward()
        self.assertEqual(float(loss),0.); self.assertEqual(n,0)

    def test_label_context_means(self):
        cs=[context('a',1),context('b',0,events=(0,))]; qs=[torch.tensor([2.,0.,-1.]),torch.tensor([.5,2.,7.])]
        expected=(F.softplus(torch.tensor(-2.))+F.softplus(torch.tensor(1.)))/2+F.softplus(torch.tensor(.5))
        torch.testing.assert_close(m.label_loss(cs,qs),expected)

    def test_teacher_class_context_objective(self):
        cs=[context('a',1),context('b',0,events=(0,)),context('c',0)]
        hs=[torch.zeros(3,128) for _ in cs]; d=m.Projection()
        cache={t['uid']:torch.full((128,),float(i+1)) for i,c in enumerate(cs) for t in c['targets']}
        full=m.teacher_loss(cs,hs,d,cache,{0:2,1:1},3)
        split=sum(m.teacher_loss([c],[h],d,cache,{0:2,1:1},3) for c,h in zip(cs,hs))
        torch.testing.assert_close(full,split)
        self.assertAlmostEqual(float(full)/3,.5*(.5+(1.5+2.5)/2))

    def test_teacher_excludes_B_wrong_and_check(self):
        cs=[context('a',1),context('b',0,'B'),context('wrong',0,old=1),context('check',0,role='check')]
        r=small_recipe(cs[:3]); ts=s.teacher_targets(cs,r)
        self.assertEqual({t['context_key'] for t in ts},{'a'})
        with self.assertRaises(s.Stop):
            m.teacher_loss([cs[3]],[torch.zeros(3,128)],m.Projection(),{}, {0:1,1:1},1)

    def test_teacher_rejects_illegal_cached_B(self):
        c=context('b',0,'B'); cache={t['uid']:torch.zeros(128) for t in c['targets']}
        with self.assertRaises(s.Stop):
            m.teacher_loss([c],[torch.zeros(3,128)],m.Projection(),cache,{0:1,1:1},1)

    def test_p2_canonical_and_contribution(self):
        state={'normalizer_mean':np.zeros(768),'normalizer_scale':np.ones(768),
               'p2__0.weight':np.zeros((128,769),np.float32),'p2__0.bias':np.ones(128,np.float32),
               'p2__3.weight':np.full((1,128),.01,np.float32),'p2__3.bias':np.array([-1.],np.float32)}
        c,raw,prob,checks=p.contributions(np.zeros((2,768),np.float32),state,[1,1])
        self.assertEqual(c.shape,(2,128)); self.assertTrue(np.all(prob>=.065159872174263))
        np.testing.assert_allclose(raw,.28,atol=2e-7)
        with self.assertRaises(s.Stop):p.contributions(np.zeros((2,768),np.float32),state,[0,0])

    def test_teacher_nonfinite_scale_rejected(self):
        with self.assertRaises(s.Stop):
            p.normalize(np.zeros((2,128),np.float32),[{'label':0,'context_key':'a'},{'label':1,'context_key':'b'}])

    def test_teacher_RMS_balances_contexts_and_classes(self):
        ts=[dict(label=0,context_key='a'),dict(label=0,context_key='a'),dict(label=0,context_key='b'),dict(label=1,context_key='c')]
        c=np.array([[1.]*128,[3.]*128,[4.]*128,[2.]*128],np.float32)
        cache,scale,denoms=p.normalize(c,ts)
        self.assertEqual(denoms,{'0':2,'1':1}); self.assertAlmostEqual(scale,math.sqrt(.5*((5+16)/2+4)))
        np.testing.assert_array_equal(cache,(c.astype(np.float64)/scale).astype(np.float32))

    def test_selective_rows_skip_unrequested_nan(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'fixture.npz'; values=np.full((5,768),np.nan,np.float32); values[1]=1;values[4]=4
            np.savez_compressed(path,representation=values,secret_labels=np.ones(5))
            audit=dict(numeric_rows_opened=0,opaque_bytes_streamed=0)
            got=p.select_rows(path,[1,4],(5,768),audit)
            self.assertEqual(audit['numeric_rows_opened'],2); self.assertEqual(audit['opaque_bytes_streamed'],5*768*4)
            np.testing.assert_equal(got[:,0],[1,4])
            with self.assertRaises(s.Stop):p.select_rows(path,[0],(5,768),audit)

    def test_selective_duplicate_and_wrong_shape_stop(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'fixture.npz';np.savez(path,representation=np.zeros((2,768),np.float32))
            with self.assertRaises(s.Stop):p.select_rows(path,[1,1],(2,768),dict(numeric_rows_opened=0,opaque_bytes_streamed=0))
            with self.assertRaises(s.Stop):p.select_rows(path,[1],(3,768),dict(numeric_rows_opened=0,opaque_bytes_streamed=0))

    def teacher_fixture(self,folder,missing=False):
        cs=[context('attack',1,events=(0,)),context('normal',0,events=(0,)),context('new',0,'B',events=(0,))]
        r=small_recipe(cs);spec=r['old_teacher_inputs'];spec['representation_shape']=[5,768]
        uids=np.array(['not-allowed','normal:0','new:0','attack:0','held-out'])
        values=np.full((5,768),np.nan,np.float32);values[1]=1;values[3]=4
        flags=np.zeros(5,dtype=bool);flags[3]=missing
        state={'normalizer_mean':np.zeros(768),'normalizer_scale':np.ones(768),
               'p2__0.weight':np.zeros((128,769),np.float32),'p2__0.bias':np.zeros(128,np.float32),
               'p2__3.weight':np.zeros((1,128),np.float32),'p2__3.bias':np.array([-5.],np.float32)}
        state['p2__0.weight'][0,0]=1;state['p2__3.weight'][0,0]=1
        np.savez_compressed(folder/'representations.npz',uid=uids,missing=flags,representation=values,forbidden_label=np.arange(5))
        np.savez(folder/'state.npz',**state,forbidden_state=np.full(10,np.nan))
        (folder/'marker.json').write_text('{}')
        for key,name in [('representations','representations.npz'),('state','state.npz'),('threshold_marker','marker.json')]:
            spec[key]=dict(path=str(folder/name),sha256=s.sha(folder/name))
        return r,cs

    def test_teacher_materialization_full_generated_join(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            folder=Path(td);r,cs=self.teacher_fixture(folder);out=folder/'P';out.mkdir()
            budget=control.Budget(out,time.monotonic(),dict(seconds=30));receipt=p.materialize(r,cs,out,budget)
            rows=s.read_json(out/'teacher_index.json')
            self.assertEqual([t['uid'] for t in rows],['attack:0','normal:0'])
            self.assertEqual([t['source_row'] for t in rows],[3,1])
            self.assertEqual(budget.access['numeric_rows_opened'],2)
            self.assertEqual(budget.access['state_arrays'],6)
            cache=train.load_teacher(cs,r,out,budget)
            self.assertGreater(float(cache['attack:0'][0]),float(cache['normal:0'][0]))
            self.assertEqual(set(cache),{'attack:0','normal:0'})

    def test_missing_teacher_stops_before_numeric_rows(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            folder=Path(td);r,cs=self.teacher_fixture(folder,True);out=folder/'P';out.mkdir()
            budget=control.Budget(out,time.monotonic(),dict(seconds=30))
            with self.assertRaises(s.Stop):p.materialize(r,cs,out,budget)
            self.assertEqual(budget.access['numeric_rows_opened'],0)

    def test_epoch_bucket_objective_conservation(self):
        keys=['c'+str(i) for i in range(67)]
        ordered=s.order(keys,1,'A');chunks=list(s.buckets(ordered,3))
        self.assertEqual([len(x) for x in chunks],[23,22,22])
        values={k:i+1 for i,k in enumerate(keys)}
        epoch_mean=sum((3/67)*sum(values[k] for k in bucket) for bucket in chunks)/3
        self.assertAlmostEqual(epoch_mean,sum(values.values())/67)

    def test_projection_included_in_global_clip(self):
        cs=[context('a',1),context('n',0),context('b',0,'B')];r=small_recipe(cs)
        model=m.Student();d=m.Projection();opt=m.optimizer(model,d,r)
        cache={t['uid']:torch.full((128,),100.) for c in cs[:2] for t in c['targets']}
        v=m.update(model,d,opt,cs[:2],cs[2:],'C2',1,(guard_for(cs),2.),cache,r)
        combined=math.sqrt(v['student_gradient_L2']**2+v['D_gradient_L2']**2)
        self.assertGreater(v['D_gradient_L2'],0.)
        self.assertAlmostEqual(v['clip_factor'],min(1.,1./(combined+1e-6)),places=6)

    def test_train_only_seek_skips_check_numeric(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            folder=Path(td); path=folder/'input.f32le'
            c=context('a',1); raw=c['x'].numpy().astype('<f4').tobytes(); c['offset']=524
            for t in c['targets']:t['feature_prefix_sha256']=s.prefix(raw,t['event'])
            path.write_bytes(np.full(131,np.nan,np.float32).tobytes()+raw)
            budget=control.Budget(folder,time.monotonic(),dict(seconds=30))
            got=train.load_contexts([c],path,budget)
            self.assertTrue(torch.equal(got[0]['x'],c['x']));self.assertEqual(budget.access['feature_bytes_decoded'],len(raw))

    def test_feature_prefix_corruption_stops(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            folder=Path(td); path=folder/'x.f32le'; c=context('a',1);c['offset']=0
            path.write_bytes(c['x'].numpy().tobytes())
            for t in c['targets']:t['feature_prefix_sha256']='bad'
            with self.assertRaises(s.Stop):train.load_contexts([c],path,control.Budget(folder,time.monotonic(),dict(seconds=30)))

    def test_three_arm_generated_fit_and_barrier(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            out=Path(td); cs=[context('a',1),context('n',0),context('b',0,'B')];r=small_recipe(cs)
            cache={t['uid']:torch.ones(128) for c in cs[:2] for t in c['targets']}
            budget=control.Budget(out,time.monotonic(),dict(seconds=60)); initial=m.Student();before=m.state_hash(initial)
            result=train.fit(cs,initial,(guard_for(cs),2.),cache,r,out,budget)
            self.assertEqual(before,m.state_hash(initial));self.assertEqual(budget.access['optimizer_steps'],6)
            self.assertEqual(result['order_hashes']['C0'],result['order_hashes']['C2'])
            for arm in ('C0','C1','C2'):
                model=m.OriginalStudent();model.load_state_dict(torch.load(out/(arm+'.pt'),weights_only=True))
                self.assertEqual(result['candidates'][arm]['initial_state_sha256'],before)
                self.assertEqual(result['candidates'][arm]['counts']['targets'],12)

    def test_C0_update_matches_independent_BCE_reference(self):
        cs=[context('a',1),context('n',0),context('b',0,'B')];r=small_recipe(cs)
        a=m.Student();b=copy.deepcopy(a);oa=m.optimizer(a,None,r);ob=m.optimizer(b,None,r)
        stats=m.update(a,None,oa,cs[:2],cs[2:],'C0',1,({},2.),{},r)
        ob.zero_grad();qa=b([c['x'] for c in cs[:2]],[c['key'] for c in cs[:2]]);qb=b([cs[2]['x']],['b'])
        (m.label_loss(cs[:2],qa)/2).backward();m.label_loss(cs[2:],qb).backward()
        torch.nn.utils.clip_grad_norm_(b.parameters(),1.,foreach=False);ob.step()
        self.assertEqual(m.state_hash(a),m.state_hash(b));self.assertEqual(stats['teacher'],0.)

    def test_low_FPR_ties_and_AUC_bruteforce(self):
        rows=[dict(uid=str(i),label=y,attack_family='f') for i,y in enumerate([1,0,1,0,1,0])]
        q=dict(zip([str(i) for i in range(6)],[3.,3.,2.,1.,0.,-1.]))
        v=e.ranking(rows,q)
        self.assertEqual(v['points']['0.01']['detected'],0)
        pos=[q[t['uid']] for t in rows if t['label']];neg=[q[t['uid']] for t in rows if not t['label']]
        expected=sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
        self.assertAlmostEqual(v['auroc'],expected)

    def test_low_FPR_integer_boundary(self):
        rows=[dict(uid='p',label=1,attack_family='f')]+[dict(uid=str(i),label=0,attack_family='benign') for i in range(100)]
        q={t['uid']:-float(i) for i,t in enumerate(rows)};q['0']=1.
        v=e.ranking(rows,q)
        self.assertEqual(v['points']['0.01']['detected'],1);self.assertEqual(v['points']['0.01']['false_alarms'],1)
        self.assertEqual(v['points']['0.001']['detected'],0)

    def test_family_threshold_is_one_pooled_threshold(self):
        rows=[dict(uid='a',label=1,attack_family='a'),dict(uid='b',label=1,attack_family='b'),dict(uid='n',label=0,attack_family='benign')]
        v=e.ranking(rows,{'a':2.,'b':0.,'n':1.})['points']['0.01']
        self.assertEqual(v['family_recall']['a']['recall'],1.);self.assertEqual(v['family_recall']['b']['recall'],0.)

    def test_prediction_roundtrip_and_invalid_hard(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'pred.csv.gz';q={'a':-1.,'b':0.,'c':.00000003}
            e.save_predictions(path,q);self.assertEqual(e.read_predictions(path,q),q)
            with self.assertRaises(s.Stop):e.read_predictions(path,['a'])

    def test_flips_do_not_cancel(self):
        rows=[dict(uid='a',label=1),dict(uid='b',label=0)]
        v=e.flips(rows,{'a':1,'b':1},{'a':0,'b':0})
        self.assertEqual(v['negative'],1);self.assertEqual(v['positive'],1);self.assertFalse(v['is_zero_regression'])

    def test_unauthorized_entry_stops_before_io(self):
        with patch.object(sys,'argv',['control','run','--stage','P']),patch.object(control,'supervise') as launch:
            with self.assertRaises(s.Stop):control.main()
            launch.assert_not_called()

    def test_duplicate_run_stops(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td,patch.dict(s.OUTPUTS,{'P':Path(td)}),patch.object(sys,'argv',['control','run','--stage','P','--authorization',s.TOKENS['P']]):
            with self.assertRaises(s.Stop):control.main()

    def test_status_missing(self):
        with patch.dict(s.OUTPUTS,{'P':TEST_ROOT/'never-started'}):self.assertEqual(control.status('P')['status'],'NOT_STARTED')

    def test_manifest_corruption_detected(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            out=Path(td);(out/'a.txt').write_text('ok');s.seal(out);s.manifest(out)
            (out/'a.txt').write_text('bad')
            with self.assertRaises(s.Stop):s.manifest(out)

    def supervisor_case(self,behavior,seconds=20):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            out=Path(td)/'stage'
            fixture_path=Path(__file__).with_name('issue27frontend_transfer_fixture_v1.py')
            command=[str(s.PYTHON),'-B',str(fixture_path),'supervise',str(out),behavior,str(seconds)]
            result=json.loads(subprocess.check_output(command,cwd=s.ROOT,text=True,encoding='utf-8',timeout=seconds+20))
            s.manifest(out);return result

    def test_supervisor_success_and_seal(self):
        result=self.supervisor_case('complete');self.assertEqual(result['status'],'COMPLETE',result)

    def test_single_worker_job_rejects_child_process(self):
        result=self.supervisor_case('child');self.assertEqual(result['status'],'COMPLETE',result)

    def test_generated_model_import_and_forward_inside_job(self):
        result=self.supervisor_case('numeric');self.assertEqual(result['status'],'COMPLETE',result)

    def test_supervisor_missing_terminal_stops(self):
        self.assertEqual(self.supervisor_case('missing')['status'],'STOP')

    def test_supervisor_corrupt_output_stops(self):
        self.assertEqual(self.supervisor_case('corrupt')['status'],'STOP')

    def test_supervisor_deadline_no_retry(self):
        v=self.supervisor_case('hang',6);self.assertEqual(v['status'],'STOP');self.assertEqual(v['retries'],0)


def fixture(out,behavior):
    deadline=time.monotonic()+30
    while not (out/'worker_gate.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('fixture gate timeout')
        time.sleep(.05)
    if behavior=='hang':
        time.sleep(30);return
    if behavior=='missing':return
    (out/'generated.txt').write_text('synthetic only',encoding='utf-8')
    h=s.sha(out/'generated.txt')
    s.atomic_json(out/'worker_terminal.json',dict(status='WORK_COMPLETE_VERIFIED',stage='P',recipe_sha256=s.RECIPE_SHA,output_hashes={'generated.txt':h}))
    if behavior=='corrupt':(out/'generated.txt').write_text('tampered',encoding='utf-8')


if __name__=='__main__':
    sys.addaudithook(no_real_numeric)
    if len(sys.argv)>1 and sys.argv[1]=='fixture':
        fixture(Path(sys.argv[2]),sys.argv[3])
    else:
        from issue27frontend_transfer_build_v1 import closure
        tested_pins={p.relative_to(s.ROOT).as_posix():s.sha(p) for p in closure()}
        stream=io.StringIO();started=time.monotonic()
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        print(stream.getvalue())
        out=Path(sys.argv[1]) if len(sys.argv)>1 else TEST_ROOT/'test_result.json'
        s.require(tested_pins == {p.relative_to(s.ROOT).as_posix():s.sha(p) for p in closure()}, 'CODE_CHANGED_DURING_TESTS')
        s.atomic_json(out,dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
                              tests_passed=result.testsRun-len(result.failures)-len(result.errors),seconds=time.monotonic()-started,
                              real_model_forwards=0,real_teacher_rows=0,real_optimizer_steps=0,numeric_access_guard=True,tested_code_pins=tested_pins))
        raise SystemExit(0 if result.wasSuccessful() else 1)
