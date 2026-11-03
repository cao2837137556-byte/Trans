"""Behavioral tests: numeric parity, leakage gates, learning objective and failures."""
import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
import legacy_reference_executor_common_v1 as c
import legacy_reference_executor_model_v1 as m
import legacy_reference_executor_train_v1 as t
import legacy_reference_executor_evaluate_v1 as e
import legacy_reference_executor_features_v1 as f
from legacy_reference_executor_fixture_v1 import create
class ExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        (c.PACKAGE/'synthetic').mkdir(parents=True,exist_ok=True)
        cls.root=Path(tempfile.mkdtemp(prefix='unit_',dir=c.PACKAGE/'synthetic'))
        cls.fixture=c.load(create(cls.root/'inputs'));cls.recipe=cls.fixture['recipe']
        cls.state=f.load_state(cls.recipe,cls.fixture)
        cls.base=m.FrozenR(cls.state)
        cls.features=np.random.default_rng(123).normal(size=(7,768)).astype(np.float32)
    def inputs(self):
        z,h,b=self.base.inputs(self.features);refs=torch.randn(7,4,768);mask=torch.ones((7,4),dtype=torch.bool)
        return z,h,b,refs,mask
    def reports(self):
        device=self.recipe['data']['devices'];expected=[d for d in device if d['partition']=='DEV']
        def make(fpr):
            return dict(devices=[dict(group={'device':d['device']},metrics={'normal':dict(rows=100,weighted_rate=fpr),'attack':dict(rows=100,weighted_rate=.98)}) for d in expected],
                        device_attack_modes=[dict(group={'device':d['device'],'activity':'UDP'},metrics={'attack':dict(rows=100,weighted_rate=.98)}) for d in expected])
        return {'R':make(.2),'Q':make(.1),'M':make(.1),'C':make(.1)}
    def test_parameter_counts(self):
        for arm,count in m.PARAMETERS.items():self.assertEqual(sum(p.numel() for p in m.Residual(arm).parameters()),count)
    def test_zero_residual_equals_original_bitwise(self):
        x=self.inputs()
        original=t.FrozenR(self.state).net(torch.from_numpy(__import__('legacy_cic2022_enhancement_train_v1').normalize_features(self.features,self.state))).detach().reshape(-1)
        for arm in m.PARAMETERS:self.assertTrue(torch.equal(m.Residual(arm)(*x),original))
    def test_nonzero_head_no_reference_is_exact_fallback(self):
        z,h,b,refs,mask=self.inputs();mask[:]=False;refs[:]=float('nan')
        for arm in m.PARAMETERS:
            head=m.Residual(arm);torch.nn.init.ones_(head.last.weight);torch.nn.init.ones_(head.last.bias)
            self.assertTrue(torch.equal(head(z,h,b,refs,mask),b))
    def test_M_population_std_and_mask(self):
        z,h,b,refs,mask=self.inputs();refs[:]=999.;refs[:,0]=2.;refs[:,1]=4.;mask[:,2:]=False
        head=m.Residual('M');captured=[];handle=head.hidden.register_forward_pre_hook(lambda module,args:captured.append(args[0].detach()))
        head(z,h,b,refs,mask);handle.remove()
        self.assertTrue(torch.equal(captured[0][:,768:1536],torch.full((7,768),3.)))
        self.assertTrue(torch.equal(captured[0][:,1536:2304],torch.ones((7,768))))
    def test_C_padding_cannot_win_max(self):
        z,h,b,refs,mask=self.inputs();mask[:,1:]=False
        head=m.Residual('C');torch.nn.init.ones_(head.last.weight)
        one=head(z,h,b,refs[:,:1],mask[:,:1]);refs[:,1:]=1e9
        self.assertTrue(torch.allclose(one,head(z,h,b,refs,mask),atol=1e-6,rtol=1e-6))
    def test_C_reference_order_invariant(self):
        z,h,b,refs,mask=self.inputs();head=m.Residual('C');torch.nn.init.ones_(head.last.weight)
        self.assertTrue(torch.allclose(head(z,h,b,refs,mask),head(z,h,b,refs.flip(1),mask.flip(1)),atol=1e-6))
    def test_fixed_normalization_and_R_unchanged(self):
        original=copy.deepcopy(self.state);self.base.inputs(self.features);self.base.unchanged()
        for k in original:self.assertTrue(np.array_equal(original[k],self.state[k]))
    def test_weighted_tail_batch_matches_full_objective_gradient(self):
        x=torch.tensor([-.4,.8,.1,2.,-1.],requires_grad=True);y=torch.tensor([0.,1.,0.,1.,0.]);w=torch.tensor([.1,.2,.3,.15,.25],dtype=torch.float64)
        full=t.loss_value(x,y,w,5);g=torch.autograd.grad(full,x)[0]
        parts=sum(t.loss_value(x[ix],y[ix],w[ix],5)*len(ix)/5 for ix in ([0,1,2],[3,4]))
        self.assertTrue(torch.allclose(full,parts));self.assertTrue(torch.allclose(g,torch.autograd.grad(parts,x)[0]))
    def test_DEV_forbidden_to_optimizer(self):
        rows=list(c.rows(self.recipe['data']['manifests']['DEV']['path']))
        with self.assertRaisesRegex(c.Stop,'LEARN_ONLY'):t.validate_training(rows)
    def test_changed_weight_rejected(self):
        rows=list(c.rows(self.recipe['data']['manifests']['LEARN']['path']));rows[0]['balanced_bce_weight_denominator']+=1
        with self.assertRaisesRegex(c.Stop,'WEIGHT_HIERARCHY'):t.validate_training(rows)
    def test_reference_role_and_time_guard(self):
        rows=list(c.rows(self.recipe['data']['manifests']['REFERENCE']['path']))
        bank=m.ReferenceBank(rows,np.zeros((len(rows),768),np.float32),self.base)
        query=dict(rows[0],timestamp=50.,partition='DEV')
        with self.assertRaisesRegex(c.Stop,'ROLE_OR_TIME'):bank.batch([query])
        query=dict(rows[0],timestamp=0.)
        with self.assertRaisesRegex(c.Stop,'ROLE_OR_TIME'):bank.batch([query])
    def test_gate_requires_joint_benefit(self):
        r=self.reports();gate=e.gate_from_reports(r,self.recipe['data']['devices'],'fixture',True)
        self.assertTrue(gate['open']);self.assertEqual(gate['passing_arms'],['M','C'])
        for arm in ('M','C'):r[arm]=copy.deepcopy(r['R'])
        self.assertFalse(e.gate_from_reports(r,self.recipe['data']['devices'],'fixture',True)['open'])
    def test_gate_protects_every_device_mode(self):
        r=self.reports()
        for arm in ('M','C'):r[arm]['device_attack_modes'][0]['metrics']['attack']['weighted_rate']=.95
        self.assertFalse(e.gate_from_reports(r,self.recipe['data']['devices'],'fixture',True)['open'])
    def test_missing_device_cell_closes_gate(self):
        r=self.reports()
        for arm in ('M','C'):r[arm]['devices'].pop()
        self.assertFalse(e.gate_from_reports(r,self.recipe['data']['devices'],'fixture',True)['open'])
    def test_gate_requires_all_endpoints(self):
        self.assertFalse(e.gate_from_reports(self.reports(),self.recipe['data']['devices'],'fixture',False)['open'])
    def test_holdout_refused_before_any_output(self):
        out=self.root/'forbidden'
        with self.assertRaisesRegex(c.Stop,'GATE_CLOSED'):f.prepare(self.recipe,out,'HOLDOUT',None,self.fixture)
        self.assertFalse(out.exists())
    def test_authorization_denied_before_asset_read(self):
        with patch.object(c,'load',side_effect=AssertionError('asset was read')):
            with self.assertRaisesRegex(c.Stop,'AUTHORIZATION_REQUIRED'):c.authorize('anything',False)
    def test_wrong_recipe_digest_closes_holdout(self):
        with self.assertRaisesRegex(c.Stop,'GATE_CLOSED'):f.require_holdout(dict(open=True,recipe_digest='wrong',all_nine_endpoints_sealed=True),'right')
    def test_paired_error_counts_not_hidden_by_average(self):
        rows=list(c.rows(self.recipe['data']['manifests']['DEV']['path']))
        baseline=np.array([3. if x['label'] else -5. for x in rows],np.float32);new=baseline.copy();ix=next(i for i,r in enumerate(rows) if r['label']);new[ix]=-5.
        report=e.report(rows,new,self.recipe['legacy']['threshold_probability'],baseline)
        self.assertEqual(sum(x['new_misses'] for x in report['paired_attack_changes']),1)
    def test_philips_service_control_uses_local_inbound_only(self):
        rows=[dict(uid=str(i),label=0,device='Philips Hue Bridge',activity='normal',capture_id='c',label_metric_weight_denominator=3,
                   protocol=6,report_direction=d,report_local_port=p) for i,(d,p) in enumerate([('inbound',80),('outbound',80),('inbound',443)])]
        result=e.report(rows,np.ones(3,np.float32),.5)
        self.assertEqual(result['philips_local_inbound_tcp80']['normal']['rows'],1)
    def test_same_seed_exposures_match_across_arms(self):
        rows=list(c.rows(self.recipe['data']['manifests']['LEARN']['path']))
        refs=[r for r in c.rows(self.recipe['data']['manifests']['REFERENCE']['path']) if r['partition']=='LEARN']
        x=np.random.default_rng(1).normal(size=(len(rows),768)).astype(np.float32);rx=np.zeros((len(refs),768),np.float32)
        receipts=[t.train_endpoint(self.recipe,self.state,x,rows,rx,refs,arm,27,self.root/('match_'+arm),True) for arm in ('Q','M','C')]
        self.assertEqual(len({r['permutation_sha256'] for r in receipts}),1);self.assertEqual(len({r['weight_sha256'] for r in receipts}),1)
        self.assertTrue(all(r['updates']==6 for r in receipts))
if __name__=='__main__':unittest.main(verbosity=2)

