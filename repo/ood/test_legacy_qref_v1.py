"""Behavioral checks on generated tensors only; no real feature/checkpoint access."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import itertools
import math
import tempfile
import unittest
import numpy as np
import torch
import legacy_qref_common_v1 as c
import legacy_qref_data_v1 as d
import legacy_qref_model_v1 as m
import legacy_qref_train_v1 as t
import legacy_qref_evaluate_v1 as e
import legacy_qref_runner_v1 as run
from legacy_qref_fixture_v1 import fixture
from legacy_reference_executor_model_v1 import FrozenR, Residual

ROOT=Path(__file__).resolve().parents[2]


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(4)
        cls.frozen=c.load_recipe(ROOT)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='qref_synthetic_')
        self.root=Path(self.temp.name)
        self.recipe,self.data=fixture(self.frozen)
        rows=self.data['rows']['REFERENCE'];ix=[i for i,r in enumerate(rows) if r['partition']=='LEARN']
        self.bank=m.Bank([rows[i] for i in ix],self.data['tensors']['REFERENCE'][0][ix],{'LEARN'})

    def tearDown(self):self.temp.cleanup()

    def query(self):
        i=int(self.data['roles']['FIT'][0]);return self.data['rows']['LEARN'][i],self.data['tensors']['LEARN'][0][i:i+1]

    def test_frozen_digest(self):self.assertEqual(c.sha(ROOT/c.RECIPE_REL),c.RECIPE_SHA)

    def test_recipe_is_immutable_under_fixture(self):
        self.assertEqual(self.frozen['training']['hyperparameters']['epochs'],40)
        self.assertNotIn('synthetic_only',self.frozen)

    def test_fit_cal_disjoint(self):
        self.assertFalse(set(self.data['roles']['FIT']) & set(self.data['roles']['CAL']))

    def test_reference_component_forced_fit(self):
        rows=deepcopy(self.data['rows']['LEARN']);ref=self.bank.rows[0]
        i=next(i for i,r in enumerate(rows) if r['device']==ref['device'])
        rows[i]['component_id']=ref['component_id']
        split=d.split(rows,self.bank.rows,self.recipe['data']['split_salt'])
        self.assertIn(i,split['FIT'])

    def test_holdout_metadata_rejected(self):
        row,z=self.query();row=dict(row,partition='DEVICE_HOLDOUT')
        with self.assertRaisesRegex(c.Stop,'ROLE'):d.metadata_valid([row],{'LEARN'})

    def test_dev_reference_rejected_in_train_bank(self):
        refs=deepcopy(self.bank.rows);refs[0]['partition']='DEV'
        with self.assertRaisesRegex(c.Stop,'ROLE'):m.Bank(refs,self.bank.z,{'LEARN'})

    def test_duplicate_reference_component_rejected(self):
        refs=deepcopy(self.bank.rows);refs[1]['component_id']=refs[0]['component_id']
        with self.assertRaisesRegex(c.Stop,'COMPONENT'):m.Bank(refs,self.bank.z,{'LEARN'})

    def test_future_full_bank_invalid_even_with_earlier_subset(self):
        row,z=self.query();refs=deepcopy(self.bank.rows)
        for r in refs:r['reference_end']=200.
        bank=m.Bank(refs,self.bank.z,{'LEARN'})
        values,valid=bank.own(z,[row],m.Raw(),self.recipe,minimum=1,budget=1)
        self.assertFalse(valid.any());self.assertEqual(values.item(),0)

    def test_same_protocol_only(self):
        row,z=self.query();row=dict(row,protocol=6)
        _,valid=self.bank.own(z,[row],m.Raw(),self.recipe,minimum=1)
        self.assertFalse(valid.any())

    def test_singleton_train_but_not_inference(self):
        row,z=self.query();key=(row['device'],row['protocol']);u=self.bank.rows[self.bank.groups[key][0]]['uid']
        override={key:[u]}
        _,train_valid=self.bank.own(z,[row],m.Raw(),self.recipe,minimum=1,override=override)
        _,eval_valid=self.bank.own(z,[row],m.Raw(),self.recipe,minimum=2,override=override)
        self.assertTrue(train_valid.all());self.assertFalse(eval_valid.any())

    def test_empty_inner_never_projects_query(self):
        row,z=self.query()
        with patch.object(m.Raw,'forward',side_effect=AssertionError('must not project')):
            score,valid=self.bank.own(z*0,[row],m.Raw(),self.recipe,empty=True)
        self.assertTrue(np.array_equal(m.veto([True],score.numpy(),valid.numpy(),0),[True]))

    def test_subset_deterministic_without_duplicates(self):
        key=self.bank.keys[0]
        a=self.bank.subset(key,self.recipe,27,0);b=self.bank.subset(key,self.recipe,27,0)
        self.assertEqual(a,b);self.assertEqual(len(a),len(set(a)));self.assertEqual(len(a),2)

    def test_tied_similarity_gradient_uses_uid_first_two(self):
        q=torch.tensor([[1.,0.]],requires_grad=True);ref=torch.ones((3,2),requires_grad=True)
        score=m.top_score(q,ref);score.sum().backward()
        self.assertTrue(torch.equal(ref.grad[2],torch.zeros(2)))
        self.assertGreater(float(ref.grad[:2].abs().sum()),0)

    def test_query_and_reference_gradients_flow(self):
        q=torch.randn(2,768,requires_grad=True);ref=torch.randn(3,768,requires_grad=True);model=m.Metric(27)
        m.top_score(model(q),model(ref)).sum().backward()
        self.assertGreater(float(q.grad.abs().sum()),0);self.assertGreater(float(ref.grad.abs().sum()),0)
        self.assertGreater(float(model.W.grad.abs().sum()),0)

    def test_metric_parameter_count(self):self.assertEqual(sum(p.numel() for p in m.Metric(27).parameters()),49152)

    def test_zero_norm_stops(self):
        with self.assertRaisesRegex(c.Stop,'NORM'):m.unit(torch.zeros(1,768))

    def test_nan_stops(self):
        with self.assertRaisesRegex(c.Stop,'FINITE'):m.unit(torch.full((1,768),float('nan')))

    def test_subset_top2_monotonic(self):
        q=m.unit(torch.randn(3,768));ref=m.unit(torch.randn(6,768));full=m.top_score(q,ref)
        for pair in itertools.combinations(range(6),2):
            self.assertTrue(bool((m.top_score(q,ref[list(pair)])<=full+1e-6).all()))

    def test_worst_reference_covers_own(self):
        row,z=self.query();model=m.Metric(27)
        own,valid=self.bank.own(z,[row],model,self.recipe,minimum=1)
        mat,mask=self.bank.matrix(z,[row],model,self.recipe,minimum=1)
        self.assertTrue(valid.all());self.assertGreaterEqual(float(mat.max().detach()),float(own.detach())-1e-6)

    def test_counterfactual_future_mask(self):
        row,z=self.query();row=dict(row,timestamp=.5)
        _,mask=self.bank.matrix(z,[row],m.Raw(),self.recipe,minimum=1)
        self.assertFalse(mask.any())

    def test_training_cal_rejected(self):
        row,z=self.query();row=dict(row,fit_role='CAL')
        with self.assertRaisesRegex(c.Stop,'FIT_ONLY'):d.weights([row])

    def test_training_dev_rejected(self):
        row,z=self.query();row=dict(row,partition='DEV')
        with self.assertRaisesRegex(c.Stop,'FIT_ONLY'):d.weights([row])

    def test_weight_mass_and_hard_boost(self):
        rr=[self.data['rows']['LEARN'][int(i)] for i in self.data['roles']['FIT']]
        hard={r['uid'] for r in rr if r['label']==0 and r['device']=='Amcrest Camera'}
        w=d.weights(rr,hard)
        self.assertAlmostEqual(float(w.sum()),1)
        self.assertAlmostEqual(float(w[[i for i,r in enumerate(rr) if r['label']==1]].sum()),.5)
        self.assertGreater(sum(w[i] for i,r in enumerate(rr) if r['uid'] in hard),.25)

    def test_attack_cannot_be_hard_normal(self):
        rr=[self.data['rows']['LEARN'][int(i)] for i in self.data['roles']['FIT']]
        hard={next(r['uid'] for r in rr if r['label']==1)}
        with self.assertRaisesRegex(c.Stop,'H_NOT_FIT_NORMAL'):d.weights(rr,hard)

    def test_helper_cannot_fit_held_device(self):
        row,z=self.query()
        with self.assertRaisesRegex(c.Stop,'HELD_DEVICE'):
            t.train(self.recipe,[row],z,torch.zeros(1,128),torch.zeros(1),self.bank,'HELPER',27,
                self.root/'never',None,held_devices=[row['device']],synthetic=True)
        self.assertFalse((self.root/'never').exists())

    def test_cal_refuses_fit(self):
        row,z=self.query()
        with self.assertRaisesRegex(c.Stop,'CAL_ROLE'):e.calibrate({},z,[row],self.bank,self.recipe,self.root/'never',None,True)

    def test_cal_refuses_dev_donor(self):
        row,z=self.query();row=dict(row,fit_role='CAL')
        bank=deepcopy(self.bank);bank.rows[0]['partition']='DEV'
        with self.assertRaisesRegex(c.Stop,'DONOR_ROLE'):e.calibrate({},z,[row],bank,self.recipe,self.root/'never',None,True)

    def test_cal_strict_and_no_useful_cut(self):
        for scores in ([.2,.8],[1.],[-.1,-.5]):
            cut=m.protected_cut(scores)
            self.assertFalse(m.veto([True]*len(scores),scores,[True]*len(scores),cut).tolist().count(False))
            self.assertTrue(m.veto([True],[cut],[True],cut)[0])
        self.assertGreater(m.protected_cut([1]),1)

    def test_cal_nonfinite_rejected(self):
        with self.assertRaisesRegex(c.Stop,'CAL_SCORES'):m.protected_cut([float('nan')])

    def test_ensemble_average_before_max(self):
        scores=[np.array([1.,0.]),np.array([0.,1.]),np.array([0.,0.])]
        self.assertAlmostEqual(float(m.evidence_ensemble(scores).max()),1/3)

    def test_veto_monotonicity(self):
        for q,valid,above in itertools.product((False,True),repeat=3):
            pred=m.veto([q],[1. if above else -1.],[valid],0)[0]
            self.assertFalse(pred and not q)
            if not valid:self.assertEqual(pred,q)

    def test_outer_unregistered_is_exact_R(self):
        model=Residual('Q');torch.nn.init.ones_(model.last.weight);torch.nn.init.ones_(model.last.bias)
        b=torch.tensor([.12345,-.56789]);z=torch.randn(2,768);h=torch.randn(2,128)
        pred=t.q_forward(model,z,h,b,registered=torch.zeros(2,dtype=torch.bool))
        self.assertTrue(torch.equal(pred,b))

    def test_ensemble_outer_fallback_bypasses_float_average(self):
        models={'Q_'+str(s):Residual('Q') for s in c.SEEDS}
        b=torch.tensor([.12345,-.56789]);progress=c.Progress(self.root/'outer',0)
        scores=run.q_scores(models,torch.randn(2,768),torch.randn(2,128),b,progress,torch.zeros(2,dtype=torch.bool))
        self.assertTrue(np.array_equal(scores['Q'],b.numpy()))

    def test_target_runtime_probe_is_synthetic(self):
        result=run.runtime_probe(self.frozen)
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['real_checkpoint_reads'],0)

    def test_base_normalizer_and_R_not_changed(self):
        rng=np.random.RandomState(27)
        state={'normalizer_mean':rng.randn(768),'normalizer_scale':np.ones(768,dtype=np.float64)*2,
            'p2__0.weight':rng.randn(128,769).astype(np.float32)*.01,'p2__0.bias':np.zeros(128,dtype=np.float32),
            'p2__3.weight':rng.randn(1,128).astype(np.float32)*.01,'p2__3.bias':np.zeros(1,dtype=np.float32)}
        raw=rng.randn(3,768).astype(np.float32);base=FrozenR(state);z,h,b=base.inputs(raw)
        self.assertTrue(np.array_equal(z.numpy(),((raw.astype(np.float64)-state['normalizer_mean'])/2).astype(np.float32)))
        base.unchanged();self.assertFalse(any(p.requires_grad for p in base.net.parameters()))

    def test_wrong_control_query_identity_rejected(self):
        recipe=deepcopy(self.recipe);recipe['evaluation']['controls'][0]['query_uid_sha256']='bad'
        with self.assertRaisesRegex(c.Stop,'QUERY_IDENTITY'):d.validate_controls(self.data['rows']['DEV'],self.data['rows']['REFERENCE'],recipe)

    def test_wrong_control_protocol_rejected(self):
        refs=deepcopy(self.data['rows']['REFERENCE']);donor=self.recipe['evaluation']['controls'][0]['wrong_reference_uids'][0]
        next(r for r in refs if r['uid']==donor)['protocol']=6
        with self.assertRaisesRegex(c.Stop,'PROTOCOL'):d.validate_controls(self.data['rows']['DEV'],refs,self.recipe)

    def test_no_real_authority_before_any_file_read(self):
        with patch.object(c,'read',side_effect=AssertionError('no I/O')):
            with self.assertRaisesRegex(c.Stop,'NOT_AUTHORIZED'):run.authorize('missing','missing','missing',None,False)

    def test_output_cannot_restart(self):
        p=c.Progress(self.root/'job',10)
        with self.assertRaises(FileExistsError):c.Progress(self.root/'job',10)

    def test_progress_open_reader_does_not_block(self):
        p=c.Progress(self.root/'job',10);f=next((p.out/'progress').glob('*.json'))
        with f.open() as held:p.tick();self.assertIn('RUNNING',held.read())
        self.assertEqual(len(list((p.out/'progress').glob('*.json'))),2)

    def test_user_stop(self):
        p=c.Progress(self.root/'job',10);(p.out/'STOP_REQUESTED').touch()
        with self.assertRaisesRegex(c.Stop,'USER_STOP'):p.guard()

    def test_memory_limit(self):
        p=c.Progress(self.root/'job',10)
        with patch.object(c,'rss_bytes',return_value=65*1024**3):
            with self.assertRaisesRegex(c.Stop,'MEMORY_LIMIT'):p.guard()

    def test_wall_limit(self):
        p=c.Progress(self.root/'job',10,hours=0)
        with self.assertRaisesRegex(c.Stop,'WALL_TIME'):p.guard()

    def test_disk_limit(self):
        p=c.Progress(self.root/'job',10,disk_gib=0)
        with self.assertRaisesRegex(c.Stop,'DISK_LIMIT'):p.guard()

    def test_seal_detects_extra_file(self):
        folder=self.root/'sealed';folder.mkdir();c.write(folder/'a.json',{'ok':1});c.seal(folder)
        c.write(folder/'extra.json',{'ok':2})
        with self.assertRaisesRegex(c.Stop,'FILE_SET'):c.verify(folder)

    def test_seal_detects_content_change(self):
        folder=self.root/'sealed';folder.mkdir();c.write(folder/'a.json',{'ok':1});c.seal(folder)
        (folder/'a.json').write_text('{}')
        with self.assertRaisesRegex(c.Stop,'IDENTITY'):c.verify(folder)

    def test_path_escape(self):
        with self.assertRaisesRegex(c.Stop,'PATH_ESCAPE'):c.confined(self.root,'../other')

    def test_windows_manifest_path_on_any_OS(self):
        self.assertEqual(c.confined(self.root,'a\\b'),self.root/'a'/'b')

    def test_paired_session_loss_report(self):
        rr=[dict(label=1,device='d',session_id='a'),dict(label=1,device='d',session_id='b')]
        got=e.paired(rr,np.array([False,True]),np.array([True,True]))
        self.assertEqual(got['new_attack_misses'],1);self.assertEqual(got['newly_wholly_missed_sessions'],1)

    def gate_reports(self):
        rows=self.data['rows']['DEV'];q=np.ones(len(rows),dtype=bool)
        pred=np.array([r['label']==1 for r in rows]);valid=q.copy()
        base=e.report(rows,q,q,valid);good=e.report(rows,pred,q,valid)
        names=['FULL','RAW','NO_CF','FULL_matched_correct','FULL_matched_wrong']
        names += ['FULL_'+str(s) for s in c.SEEDS]
        names += ['FULL_matched_'+v+'_'+str(s) for v in ('correct','wrong') for s in c.SEEDS]
        return dict(Q=base,**{k:deepcopy(good) for k in names})

    def test_system_gain_is_not_learning_innovation(self):
        gate=e.gates(self.gate_reports(),self.recipe)
        self.assertTrue(gate['system_pass']);self.assertFalse(gate['learned_mechanism_supported'])
        self.assertFalse(gate['personalized_reference_supported']);self.assertFalse(gate['holdout_open'])

    def test_attack_loss_fails_despite_perfect_normal(self):
        reports=self.gate_reports();reports['FULL']['paired']['new_attack_misses']=1
        gate=e.gates(reports,self.recipe)
        self.assertFalse(gate['system_pass']);self.assertIn('NEW_ATTACK_MISSES',gate['reasons'])

    def test_focal_denominator_cannot_be_dropped(self):
        reports=self.gate_reports()
        reports['FULL']['groups']['device/activity']=[x for x in reports['FULL']['groups']['device/activity'] if x['group']['device']!='Eufy Home Base']
        self.assertIn('FOCAL_DENOMINATOR',e.gates(reports,self.recipe)['reasons'])


if __name__=='__main__':unittest.main(verbosity=2)
