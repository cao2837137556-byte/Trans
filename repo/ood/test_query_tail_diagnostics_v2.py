"""Generated-only diagnostics checks; no real feature/model/result access."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import torch
from torch.nn import functional as F
import query_tail_core_v2 as k
import query_tail_diagnostics_v2 as d
import query_tail_train_v2 as t


class Quiet:
    stage = ''
    optimizer_updates = 0
    def tick(self, *args, **kwargs):
        pass


def heavy_tail_features(rng, count):
    """Claude's generated t(3) current-feature and uniform QUERY14 fixture."""
    return np.concatenate([rng.standard_t(3,(count,768)),
                           rng.uniform(size=(count,14))],axis=1).astype(np.float32)


def b1_evidence(section, value):
    """Optional generated-only report; normal target tests need no external path."""
    location=os.environ.get('QUERY_TAIL_B1_REPORT')
    if not location:
        return
    path=Path(location)
    path.parent.mkdir(parents=True,exist_ok=True)
    report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    report.update(synthetic_only=True, real_data_used=False,
                  python=sys.version.split()[0], numpy=np.__version__, torch=torch.__version__)
    report[section]=value
    path.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def generated_fixture():
    n, seed = 65, 27
    generator = torch.Generator().manual_seed(seed)
    orders = [torch.randperm(n, generator=generator).numpy() for _ in range(2)]
    labels = np.arange(n)%2
    # Every epoch's final partial batch has no attack. All normal inputs are identical,
    # exercising proportional tie handling and zero-positive probes together.
    for order in orders:
        labels[order[-1]] = 0
    rows = [dict(uid='generated_%03d'%i, partition='LEARN', fit_role='FIT', use='QUERY',
                 label=int(labels[i]), device='device_%s'%(i%2),
                 activity='normal' if labels[i] == 0 else 'TCP', capture_id='capture',
                 session_id='session', component_id='component_%s'%i) for i in range(n)]
    rng = np.random.default_rng(12)
    values = rng.normal(size=(n,768)).astype(np.float32)
    q = rng.uniform(size=(n,14)).astype(np.float32)
    values[labels == 0] = 0
    q[labels == 0] = 0
    design = dict(synthetic_only=True, training=dict(
        epochs=2, batch_size=16, tail_negatives_per_batch=8, negative_tail_mass=.01,
        optimizer_parent_values=dict(lr=3e-4, weight_decay=1e-4, betas=[.9,.999], eps=1e-8),
        diagnostics=dict(enabled=True, loss_log_format='npy_float64',
                         loss_columns=['bce','tail','total'], probe_batches=[1,1207,2414],
                         gradient_timing='pre_step', adam_state_timing='post_step')))
    return design, rows, values, q, (np.zeros(768),np.ones(768)), np.arange(n), np.zeros(n,np.uint8)


class ObjectiveTests(unittest.TestCase):
    def test_sum_and_unchanged_class_pair_weights(self):
        x = torch.tensor([-.3, .7, 1.2], requires_grad=True)
        y = torch.tensor([0.,1.,1.])
        w = np.array([.5,.2,.3]); neg = torch.tensor([-.2,.8], requires_grad=True)
        bce, tail, total = k.objective_components(x,y,w,9,neg)
        expected_bce = (F.binary_cross_entropy_with_logits(x,y,reduction='none')*torch.tensor(w)).sum()*3
        expected_tail = (F.softplus(neg[None,:]-x[1:,None]).mean(1)*torch.tensor(2*w[1:])).sum()*3
        self.assertTrue(torch.equal(bce,expected_bce)); self.assertTrue(torch.equal(tail,expected_tail))
        self.assertTrue(torch.equal(total,bce+tail))
        total.backward()
        self.assertGreater(float(neg.grad.min()),0)
        self.assertLess(float(x.grad[1:].max()),0)
        xb = x.detach().requires_grad_(True)
        bb, tt, rr = k.objective_components(xb,y,w,9)
        self.assertIs(bb,rr); self.assertEqual(float(tt),0)

    def test_no_attack_is_bce_without_halving(self):
        x = torch.tensor([0.,.5],requires_grad=True)
        neg = torch.tensor([1.],requires_grad=True)
        bce,tail,total = k.objective_components(x,torch.zeros(2),np.array([.3,.2]),4,neg)
        self.assertTrue(torch.equal(bce,total)); self.assertEqual(float(tail.detach()),0)
        total.backward(); self.assertIsNone(neg.grad)


class GradientTests(unittest.TestCase):
    def test_probe_same_graph_no_grad_writes_and_sum_sanity(self):
        p = torch.nn.Parameter(torch.tensor([.1,.2]))
        bce,tail = p.square().sum(),(p-1).square().sum()
        probe,expected = d.gradient_probe(bce,tail,[p],1,True)
        self.assertEqual(probe['status'],'VALID'); self.assertIsNone(p.grad)
        self.assertAlmostEqual(probe['gradient_ratio'],math.sqrt(1.45/.05),places=5)
        self.assertLess(probe['gradient_cosine'],0)
        (bce+tail).backward()
        self.assertTrue(d.backward_sanity(expected,[p],probe)['allclose'])

    def test_200_weighted_heavy_tail_batches_no_false_stop_and_bitwise_grad(self):
        # Reproduce the appendix's non-degenerate graph, including hierarchical
        # row weights and lognormal perturbation; no source features are loaded.
        started=time.perf_counter()
        torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
        total_rows,batch_rows=617908,256
        groups=[(1,471,.25),(1,429350,.4167),(1,53594,.3333),
                (0,131823,.1795),(0,2670,.8205)]
        probabilities=np.array([g[1] for g in groups],dtype=np.float64)
        probabilities/=probabilities.sum()
        rng=np.random.default_rng(1)
        mismatches=0; same=0; observed=[]
        for batch in range(200):
            chosen=rng.choice(len(groups),size=batch_rows,p=probabilities)
            labels=torch.from_numpy(np.array([groups[g][0] for g in chosen],np.float32))
            weights=np.array([.5*groups[g][2]/groups[g][1] for g in chosen])
            weights*=rng.lognormal(0,1,batch_rows)
            inputs=torch.from_numpy(heavy_tail_features(rng,batch_rows))
            negatives=torch.from_numpy(heavy_tail_features(rng,128))
            enabled=k.classifier(27,782); disabled=copy.deepcopy(enabled)
            bce,tail,total=k.objective_components(enabled(inputs).flatten(),labels,
                                                  weights,total_rows,enabled(negatives).flatten())
            probe,expected=d.gradient_probe(bce,tail,enabled.parameters(),int(labels.sum()),True)
            self.assertTrue(all(p.grad is None for p in enabled.parameters()))
            total.backward()
            _,_,plain_total=k.objective_components(disabled(inputs).flatten(),labels,
                                                   weights,total_rows,disabled(negatives).flatten())
            plain_total.backward()
            bitwise=all(torch.equal(a.grad,b.grad) for a,b in
                        zip(enabled.parameters(),disabled.parameters()))
            self.assertTrue(bitwise,'batch %d'%batch); same+=int(bitwise)
            actual_before=[p.grad.clone() for p in enabled.parameters()]
            check=d.backward_sanity(expected,enabled.parameters(),probe)
            self.assertTrue(check['l2_pass']); self.assertFalse(check['allclose_is_stop_gate'])
            self.assertLessEqual(check['l2_difference'],check['l2_threshold'])
            self.assertTrue(all(torch.equal(p.grad,g) for p,g in
                                zip(enabled.parameters(),actual_before)))
            mismatches+=int(not check['allclose'])
            observed.append(check)
        # Keep the observed legacy failure count for audit, without assuming a
        # particular Torch/BLAS version produces the same coordinate rounding.
        b1_evidence('weighted_heavy_tail_batches',dict(
            batches=200, generated_fixture='t(3) 768 + uniform QUERY14; appendix seed 1',
            FIT_count_scaling=total_rows,batch_rows=batch_rows,negatives=128,
            old_elementwise_allclose_failures=mismatches,
            corrected_false_stops=0,bitwise_grad_equal_batches=same,
            max_relative_l2_difference=max(x['relative_l2_difference'] for x in observed),
            max_component_relative_l2_difference=max(x['component_relative_l2_difference'] for x in observed),
            max_abs_difference=max(x['max_abs_difference'] for x in observed),
            seconds=time.perf_counter()-started))

    def test_missing_tail_backward_is_still_rejected(self):
        p=torch.nn.Parameter(torch.tensor([.1,.2]))
        bce,tail=p.square().sum(),(p-1).square().sum()
        probe,expected=d.gradient_probe(bce,tail,[p],1,True)
        # A real missing objective term must fail despite the rounding allowance.
        bce.backward()
        with self.assertRaisesRegex(RuntimeError,'COMPONENT_SUM_BACKWARD_MISMATCH'):
            d.backward_sanity(expected,[p],probe)
        # Also reject a faulty diagnostic expectation that omitted TAIL while
        # the actual original backward contains the full objective.
        p2=torch.nn.Parameter(torch.tensor([.1,.2]))
        bce2,tail2=p2.square().sum(),(p2-1).square().sum()
        full_probe,_=d.gradient_probe(bce2,tail2,[p2],1,True)
        bce_only=torch.autograd.grad(bce2,[p2],retain_graph=True)
        (bce2+tail2).backward()
        with self.assertRaisesRegex(RuntimeError,'COMPONENT_SUM_BACKWARD_MISMATCH'):
            d.backward_sanity(bce_only,[p2],full_probe)
        b1_evidence('missing_tail_control',dict(status='EXPECTED_REJECTION',
                                               cases=['BCE-only backward','BCE-only expectation'],
                                               error='COMPONENT_SUM_BACKWARD_MISMATCH'))

    def test_strong_cancellation_uses_component_scale_not_total_norm(self):
        p=torch.nn.Parameter(torch.tensor([1.,1.]))
        # Float32's independent component reductions and total backward can
        # accumulate these terms in different orders; the final norm is tiny.
        bce=(p*1e8+p*4+p*4).sum(); tail=(-p*1e8).sum()
        probe,expected=d.gradient_probe(bce,tail,[p],1,True)
        (bce+tail).backward()
        check=d.backward_sanity(expected,[p],probe)
        self.assertGreater(check['component_norm_scale'],1e8)
        self.assertLess(check['reference_grad_norm'],1e-6*check['component_norm_scale'])
        self.assertTrue(check['l2_pass'])
        self.assertLessEqual(check['l2_difference'],check['l2_threshold'])
        b1_evidence('strong_cancellation_graph',check)
        # A deterministic IEEE float32 addition-order control covers the old
        # allclose=False branch even when a backend's actual graph reductions
        # happen to agree on all 200 random batches. Both orders lose small terms
        # differently around a 1e8 component and a cancelling -1e8 component.
        large=torch.full_like(p,1e8); small=torch.full_like(p,4.)
        separately_rounded=(large+(small+small))-large
        total_rounded=((large+small)+small)-large
        p.grad=total_rounded.clone()
        scale_probe=dict(bce_grad_norm=float((large+(small+small)).double().norm()),
                         tail_grad_norm=float(large.double().norm()))
        rounding=d.backward_sanity([separately_rounded],[p],scale_probe)
        self.assertFalse(rounding['allclose']); self.assertTrue(rounding['l2_pass'])
        self.assertFalse(rounding['allclose_is_stop_gate'])
        self.assertGreater(rounding['l2_difference'],0)
        b1_evidence('deterministic_rounding_cancellation',rounding)

    def test_sanity_invalid_gradients_and_zero_case(self):
        p=torch.nn.Parameter(torch.tensor([1.,2.]))
        probe,expected=d.gradient_probe(p.sum()*0,p.sum()*0,[p],1,True)
        (p.sum()*0).backward()
        zero=d.backward_sanity(expected,[p],probe)
        self.assertTrue(zero['l2_pass']); self.assertEqual(zero['status'],'ZERO_TOTAL_GRAD')
        self.assertEqual(zero['component_norm_scale'],0)
        self.assertEqual(zero['l2_difference'],0)
        self.assertIsNone(zero['relative_l2_difference'])
        self.assertIsNone(zero['component_relative_l2_difference'])
        with self.assertRaisesRegex(RuntimeError,'SANITY_PARAMETER_COUNT_MISMATCH'):
            d.backward_sanity(expected+expected,[p],probe)
        with self.assertRaisesRegex(RuntimeError,'SANITY_GRAD_SHAPE_MISMATCH'):
            d.backward_sanity([torch.zeros(1)],[p],probe)
        with self.assertRaisesRegex(RuntimeError,'SANITY_NONFINITE_GRAD'):
            d.backward_sanity([torch.full_like(p,float('inf'))],[p],probe)
        p.grad[0]=float('nan')
        with self.assertRaisesRegex(RuntimeError,'SANITY_NONFINITE_GRAD'):
            d.backward_sanity(expected,[p],probe)
        p.grad.zero_()
        for invalid in ({},dict(bce_grad_norm=-1,tail_grad_norm=0),
                        dict(bce_grad_norm=0,tail_grad_norm=float('inf'))):
            with self.subTest(invalid=invalid),self.assertRaisesRegex(RuntimeError,'SANITY_INVALID_COMPONENT_NORMS'):
                d.backward_sanity(expected,[p],invalid)
        p.grad=None
        with self.assertRaisesRegex(RuntimeError,'SANITY_MISSING_BACKWARD_GRAD'):
            d.backward_sanity(expected,[p],probe)
        with self.assertRaisesRegex(RuntimeError,'PROBE_NONFINITE_COMPONENT_GRAD'):
            d.gradient_probe((p*float('inf')).sum(),p.sum()*0,[p],1,True)
        self.assertIsNone(p.grad)

    def test_zero_and_inapplicable_states_are_explicit(self):
        for attack,enabled,bfactor,tfactor,status,ratio in [
                (0,True,1.,0.,'NO_ATTACK',None),
                (1,False,1.,0.,'TAIL_DISABLED',None),
                (1,True,0.,1.,'ZERO_BCE_GRAD',None),
                (1,True,0.,0.,'BOTH_ZERO',None),
                (1,True,1.,0.,'VALID',0.)]:
            with self.subTest(status=status):
                p = torch.nn.Parameter(torch.tensor([1.]))
                probe,_ = d.gradient_probe(p.sum()*bfactor,p.sum()*tfactor,[p],attack,enabled)
                self.assertEqual(probe['status'],status)
                self.assertEqual(probe['gradient_ratio'],ratio)
                self.assertIsNone(probe['gradient_cosine'])
                self.assertIsNone(p.grad)
        p = torch.nn.Parameter(torch.tensor([1.])); p.grad = torch.ones_like(p)
        with self.assertRaisesRegex(RuntimeError,'PROBE_EXPECTS_ZERO_GRAD'):
            d.gradient_probe(p.sum(),p.sum(),[p],1,True)


class AdamTests(unittest.TestCase):
    def test_step_one_bias_correction_and_query_columns(self):
        model = k.classifier(27,782)
        opt = torch.optim.AdamW(model.parameters(),lr=3e-4,betas=(.9,.999),eps=1e-8,
                                weight_decay=1e-4,foreach=False)
        with self.assertRaisesRegex(RuntimeError,'ADAM_STATE_MISSING_POST_STEP'):
            d.adam_probe(model,opt)
        # Known nonzero gradients on one coordinate range, zero on query columns.
        for p in model.parameters():
            p.grad = torch.full_like(p,2e-8)
        model[0].weight.grad[:,768:] = 0
        opt.step()
        before = copy.deepcopy(opt.state_dict())
        read = d.adam_probe(model,opt)
        allp = read['groups']['all_parameters']; query = read['groups']['query14_columns']
        self.assertEqual(allp['step_min'],1); self.assertEqual(allp['step_max'],1)
        self.assertEqual(query['coordinates'],128*14)
        self.assertEqual(query['zero_second_moment_count'],128*14)
        self.assertEqual(query['below_eps_count'],128*14)
        self.assertEqual(query['active_first_moment_count'],0)
        self.assertIsNone(query['active_first_moment_below_eps_fraction'])
        self.assertAlmostEqual(allp['sqrt_vhat_median'],2e-8,delta=2e-15)
        self.assertAlmostEqual(allp['sqrt_vhat_max'],2e-8,delta=2e-15)
        self.assertEqual(allp['below_eps_count'],128*14)
        for key, state in before['state'].items():
            for field,value in state.items():
                now=opt.state_dict()['state'][key][field]
                self.assertTrue(torch.equal(value,now) if torch.is_tensor(value) else value==now)
        # The second step must use step=2, not the global training counter or step=1.
        for p in model.parameters(): p.grad.fill_(4e-8)
        opt.step()
        read=d.adam_probe(model,opt)
        state=opt.state[model[2].bias]
        expected=float(torch.sqrt(state['exp_avg_sq'].double()/(1-.999**2)))
        self.assertEqual(read['groups']['all_parameters']['step_min'],2)
        self.assertAlmostEqual(read['groups']['output_layer']['sqrt_vhat_median'],expected,places=16)
        plain=k.classifier(27,768); plain_opt=torch.optim.AdamW(plain.parameters(),foreach=False)
        for p in plain.parameters(): p.grad=torch.zeros_like(p)
        plain_opt.step()
        self.assertEqual(d.adam_probe(plain,plain_opt)['groups']['query14_columns']['status'],'NOT_APPLICABLE')


class InvarianceTests(unittest.TestCase):
    def test_heavy_tail_r3_two_epochs_logging_on_off_bitwise(self):
        started=time.perf_counter()
        args=list(generated_fixture())
        generated=heavy_tail_features(np.random.default_rng(44),len(args[1]))
        args[2],args[3]=generated[:,:768].copy(),generated[:,768:].copy()
        normal=[i for i,row in enumerate(args[1]) if row['label']==0]
        self.assertGreater(len(np.unique(generated[normal],axis=0)),1)
        real_adam=torch.optim.AdamW; real_classifier=k.classifier
        optimizers=[]; calls=[]
        def classifier(seed,dimension):
            model=real_classifier(seed,dimension)
            current=[]; calls.append(current)
            model.register_forward_hook(lambda _module,inputs,_output:current.append(tuple(inputs[0].shape)))
            return model
        def factory(*values,**kwargs):
            optimizer=real_adam(*values,**kwargs); optimizers.append(optimizer); return optimizer
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(t.torch.optim,'AdamW',side_effect=factory),patch.object(k,'classifier',side_effect=classifier):
                on=t.train(*args,'QUERY_TAIL',27,Path(tmp)/'on',Quiet(),synthetic=True,logging_enabled=True)
                off=t.train(*args,'QUERY_TAIL',27,Path(tmp)/'off',Quiet(),synthetic=True,logging_enabled=False)
            self.assertEqual(calls[0],calls[1]); self.assertEqual(len(calls[0]),22)
            for name,value in on.state_dict().items():
                self.assertTrue(torch.equal(value,off.state_dict()[name]),name)
            for a,b in zip(on.parameters(),off.parameters()):
                self.assertTrue(torch.equal(a.grad,b.grad))
                self.assertEqual(set(optimizers[0].state[a]),set(optimizers[1].state[b]))
                for name,value in optimizers[0].state[a].items():
                    other=optimizers[1].state[b][name]
                    self.assertTrue(torch.equal(value,other) if torch.is_tensor(value) else value==other,name)
            endpoints=[k.c.read(Path(tmp)/side/'endpoint.json') for side in ('on','off')]
            fields=('updates','order_hashes','uid_sha256','weight_sha256','normalizer_digest',
                    'initial_sha256','head_sha256','design_digest')
            for field in fields:
                self.assertEqual(endpoints[0][field],endpoints[1][field],field)
            self.assertEqual(endpoints[0]['updates'],10)
            epoch_shas=[]
            for epoch in (1,2):
                filename='epoch_%02d.json'%epoch
                left,right=(Path(tmp)/side/filename for side in ('on','off'))
                self.assertEqual(left.read_bytes(),right.read_bytes())
                self.assertEqual(k.c.sha(left),k.c.sha(right)); epoch_shas.append(k.c.sha(left))
                data=k.c.read(left)
                self.assertEqual(data['tail_sample_count'],40)
                self.assertGreaterEqual(data['tail']['rows'],1)
            probes=[json.loads(line) for line in (Path(tmp)/'on/fixed_probes.jsonl').read_text().splitlines()]
            self.assertEqual(len(probes),6)
            self.assertTrue(any(p['gradient']['tail_grad_norm']>0 for p in probes))
            self.assertTrue(all(p['gradient']['backward_sanity']['l2_pass'] for p in probes))
            self.assertTrue(all(not p['gradient']['backward_sanity']['allclose_is_stop_gate'] for p in probes))
            schema=k.c.read(Path(tmp)/'on/diagnostics_schema.json')
            self.assertEqual(schema['status'],'COMPLETE'); self.assertEqual(schema['completed_optimizer_updates'],10)
            k.c.verify(Path(tmp)/'on'); k.c.verify(Path(tmp)/'off')
            b1_evidence('heavy_tail_training_invariance',dict(
                arm='QUERY_TAIL (R3)',seed=27,epochs=2,rows=65,batch_size=16,updates=10,
                forward_calls=22,normal_inputs='non-identical t(3) + uniform QUERY14',
                bitwise_equal=['model parameters','terminal .grad','Adam step/moments',
                               'initial/head SHA','order stream','sample stream','tail audits','epoch JSON/SHA'],
                epoch_sha256=epoch_shas,head_sha256=endpoints[0]['head_sha256'],
                probe_rows=6,seconds=time.perf_counter()-started))

    def test_two_epochs_logging_on_off_bitwise_terminal_and_streams(self):
        # Same design and independent fresh initializers; only read-only diagnostics differ.
        args = generated_fixture()
        real_adam = torch.optim.AdamW
        real_classifier = k.classifier
        for arm in k.ARMS:
            with self.subTest(arm=arm),tempfile.TemporaryDirectory() as tmp:
                optimizers=[]
                forward_calls=[]
                def classifier(seed,dimension):
                    model=real_classifier(seed,dimension)
                    calls=[]; forward_calls.append(calls)
                    model.register_forward_hook(lambda _module, inputs, _output: calls.append(tuple(inputs[0].shape)))
                    return model
                def factory(*values,**kwargs):
                    optimizer=real_adam(*values,**kwargs); optimizers.append(optimizer); return optimizer
                with patch.object(t.torch.optim,'AdamW',side_effect=factory),patch.object(k,'classifier',side_effect=classifier):
                    a=t.train(*args,arm,27,Path(tmp)/'on',Quiet(),synthetic=True,logging_enabled=True)
                    b=t.train(*args,arm,27,Path(tmp)/'off',Quiet(),synthetic=True,logging_enabled=False)
                self.assertEqual(forward_calls[0],forward_calls[1])
                self.assertEqual(len(forward_calls[0]),10 if arm=='QUERY_BCE' else 22)
                for name, value in a.state_dict().items():
                    self.assertTrue(torch.equal(value,b.state_dict()[name]),name)
                for pa,pb in zip(a.parameters(),b.parameters()):
                    self.assertTrue(torch.equal(pa.grad,pb.grad))
                    sa,sb=optimizers[0].state[pa],optimizers[1].state[pb]
                    for key,value in sa.items():
                        self.assertTrue(torch.equal(value,sb[key]) if torch.is_tensor(value) else value==sb[key],key)
                endpoints=[k.c.read(Path(tmp)/side/'endpoint.json') for side in ('on','off')]
                for key in ('updates','order_hashes','uid_sha256','weight_sha256','normalizer_digest',
                            'initial_sha256','head_sha256','design_digest'):
                    self.assertEqual(endpoints[0][key],endpoints[1][key],key)
                self.assertEqual(endpoints[0]['updates'],10)
                for epoch in (1,2):
                    ea=k.c.read(Path(tmp)/'on'/('epoch_%02d.json'%epoch))
                    eb=k.c.read(Path(tmp)/'off'/('epoch_%02d.json'%epoch))
                    self.assertEqual(ea,eb)
                    if arm!='QUERY_BCE':
                        self.assertGreater(ea['tail']['rows'],1)
                        self.assertEqual(ea['tail_sample_count'],5*8)
                losses=np.load(Path(tmp)/'on/batch_losses.npy')
                self.assertEqual(losses.shape,(10,3)); self.assertEqual(losses.dtype,np.float64)
                np.testing.assert_array_equal(losses[:,0]+losses[:,1],losses[:,2])
                schema=k.c.read(Path(tmp)/'on/diagnostics_schema.json')
                self.assertEqual(schema['status'],'COMPLETE'); self.assertEqual(schema['written_rows'],10)
                self.assertEqual(schema['completed_optimizer_updates'],10)
                self.assertEqual(schema['probe_batches'],[1,3,5]); self.assertEqual(schema['probe_rows'],6)
                self.assertEqual(schema['observed_component_dtypes']['bce'],['float64'])
                self.assertEqual(schema['observed_component_dtypes']['total'],['float64'])
                self.assertEqual(schema['observed_component_dtypes']['tail'],
                                 ['float64'] if arm=='QUERY_BCE' else ['float32','float64'])
                probes=[json.loads(line) for line in (Path(tmp)/'on/fixed_probes.jsonl').read_text().splitlines()]
                self.assertEqual([(p['epoch'],p['batch']) for p in probes],[(e,b) for e in (1,2) for b in (1,3,5)])
                for p in probes:
                    self.assertTrue(p['gradient']['backward_sanity']['allclose'])
                    self.assertEqual(p['adam']['groups']['all_parameters']['step_min'],p['global_update'])
                    if p['batch']==5:
                        self.assertEqual(p['gradient']['attack_count'],0)
                        self.assertEqual(p['gradient']['status'],'TAIL_DISABLED' if arm=='QUERY_BCE' else 'NO_ATTACK')
                        self.assertIsNone(p['gradient']['gradient_ratio'])
                self.assertFalse((Path(tmp)/'off/batch_losses.npy').exists())
                k.c.verify(Path(tmp)/'on'); k.c.verify(Path(tmp)/'off')

    def test_failure_flushes_partial_rows_closes_and_keeps_first_exception(self):
        args=generated_fixture(); logs=[]; real_log=d.DiagnosticLog
        def log_factory(*values,**kwargs):
            log=real_log(*values,**kwargs); logs.append(log); return log
        failure=ValueError('GENERATED_FIRST_FAILURE')
        class FailingProgress(Quiet):
            def tick(self,*args,**kwargs):
                raise failure
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'failed'
            with patch.object(d,'DiagnosticLog',side_effect=log_factory):
                with self.assertRaises(ValueError) as captured:
                    t.train(*args,'QUERY_BCE',27,out,FailingProgress(),synthetic=True)
            self.assertIs(captured.exception,failure)
            schema=k.c.read(out/'diagnostics_schema.json')
            self.assertEqual(schema['status'],'FAILED')
            self.assertEqual(schema['written_rows'],1); self.assertEqual(schema['probe_rows'],1)
            self.assertEqual(schema['completed_optimizer_updates'],1)
            self.assertEqual(schema['first_failure'],dict(type='ValueError',message='GENERATED_FIRST_FAILURE'))
            self.assertEqual(schema['loss_timing'],'pre_step')
            self.assertTrue(np.isfinite(np.load(out/'batch_losses.npy')[0]).all())
            self.assertTrue(logs[0].probe_stream.closed); self.assertTrue(logs[0].losses._mmap.closed)
            self.assertFalse((out/'head.npz').exists()); self.assertFalse((out/'endpoint.json').exists())
            self.assertFalse((out/'SHA256SUMS').exists())

    def test_pre_step_probe_failure_marks_uncompleted_loss_row(self):
        args=generated_fixture(); failure=ValueError('GENERATED_PRE_STEP_FAILURE')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'failed'
            with patch.object(d,'gradient_probe',side_effect=failure):
                with self.assertRaises(ValueError) as captured:
                    t.train(*args,'QUERY_TAIL',27,out,Quiet(),synthetic=True)
            self.assertIs(captured.exception,failure)
            schema=k.c.read(out/'diagnostics_schema.json')
            self.assertEqual(schema['status'],'FAILED')
            self.assertEqual(schema['written_rows'],1)
            self.assertEqual(schema['completed_optimizer_updates'],0)
            self.assertEqual(schema['probe_rows'],0)
            self.assertFalse((out/'head.npz').exists())

    def test_cleanup_failures_do_not_replace_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=d.DiagnosticLog(tmp,2,1,2,[1])
            failure=ValueError('AUTHORITATIVE_FIRST_FAILURE')
            real_close=log.close
            def failing_close():
                real_close()
                raise OSError('GENERATED_SECONDARY_CLOSE_FAILURE')
            with patch.object(log,'checkpoint',side_effect=OSError('GENERATED_SECONDARY_FLUSH_FAILURE')):
                with patch.object(log,'close',side_effect=failing_close):
                    with self.assertRaises(ValueError) as captured:
                        with d.diagnostic_context(log):
                            raise failure
            self.assertIs(captured.exception,failure)
            self.assertTrue(log.probe_stream.closed); self.assertTrue(log.losses._mmap.closed)

    def test_incomplete_logs_never_write_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=d.DiagnosticLog(tmp,2,1,2,[1])
            try:
                components=(torch.tensor(1.,dtype=torch.float64),torch.tensor(0.),torch.tensor(1.,dtype=torch.float64))
                log.loss(components); log.step_completed()
                log.checkpoint()
                with self.assertRaisesRegex(RuntimeError,'LOSS_LOG_INCOMPLETE'):
                    log.checkpoint(complete=True)
                self.assertEqual(k.c.read(Path(tmp)/'diagnostics_schema.json')['status'],'RUNNING')
                log.loss(components); log.step_completed()
                with self.assertRaisesRegex(RuntimeError,'PROBE_LOG_INCOMPLETE'):
                    log.checkpoint(complete=True)
                self.assertEqual(k.c.read(Path(tmp)/'diagnostics_schema.json')['status'],'RUNNING')
                log.probe(dict(epoch=1,batch=1,global_update=1))
                log.probe(dict(epoch=2,batch=1,global_update=2))
                log.checkpoint(complete=True)
                self.assertEqual(k.c.read(Path(tmp)/'diagnostics_schema.json')['status'],'COMPLETE')
            finally:
                log.close()


if __name__=='__main__': unittest.main()
