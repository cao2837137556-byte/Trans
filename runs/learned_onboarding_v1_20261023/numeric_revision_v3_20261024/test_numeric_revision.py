"""Regression tests for the independent numeric revision, synthetic inputs only."""
from pathlib import Path
import sys
import unittest

import numpy as np
import torch
from torch import nn

REV = Path(__file__).resolve().parent
sys.path.insert(0,str(REV/'staging/runs/learned_onboarding_v1_20261023/src'))
from stable_inference import stable_forward
import learning
import common


class NumericRevisionTests(unittest.TestCase):
    def setUp(self):
        learning._setup()

    def test_auxiliary_batch_tail_alignment_and_order(self):
        model=learning._old_classifier()
        x=torch.randn(513,782)
        expected=stable_forward(model,x)
        for size in (1,31,127,256):
            actual=torch.cat([stable_forward(model,x[i:i+size]) for i in range(0,len(x),size)])
            self.assertTrue(torch.equal(expected,actual))
        padded=torch.empty(515,784)
        padded[1:514,1:783]=x
        self.assertTrue(torch.equal(expected,stable_forward(model,padded[1:514,1:783])))
        order=torch.randperm(len(x))
        self.assertTrue(torch.equal(expected[order],stable_forward(model,x[order])))

    def test_module_batch_and_query_mask(self):
        model=learning.correction_model()
        x=np.random.default_rng(31).normal(size=(513,50)).astype(np.float32)
        for masked in (False,True):
            primary=learning.score_module(model,x,query_only=masked,batch_size=256)
            split=learning.score_module(model,x,query_only=masked,batch_size=127)
            np.testing.assert_array_equal(primary,split)
            at_boundary=primary.copy()
            cut=float(at_boundary[10])
            np.testing.assert_array_equal(primary>cut,split>cut)

    def test_no_model_input_gradient_rng_or_flag_mutation(self):
        model=learning.correction_model()
        model.train()
        model[0].eval()
        x=torch.randn(17,50,requires_grad=True)
        original=x.detach().clone()
        states={key:value.clone() for key,value in model.state_dict().items()}
        for parameter in model.parameters():
            parameter.grad=torch.ones_like(parameter)
        grads=[parameter.grad.clone() for parameter in model.parameters()]
        flags=[layer.training for layer in model.modules()]
        rng=torch.get_rng_state().clone()
        enabled=torch.is_grad_enabled()
        result=stable_forward(model,x)
        self.assertFalse(result.requires_grad)
        self.assertEqual(enabled,torch.is_grad_enabled())
        self.assertEqual(flags,[layer.training for layer in model.modules()])
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertTrue(torch.equal(original,x.detach()))
        for key,value in model.state_dict().items():
            self.assertTrue(torch.equal(states[key],value))
        for before,parameter in zip(grads,model.parameters()):
            self.assertTrue(torch.equal(before,parameter.grad))

    def test_invalid_inputs_and_nonfinite_model_fail_closed(self):
        model=learning.correction_model()
        for x in (torch.zeros(2,50,dtype=torch.float64),torch.zeros(2,49),
                  torch.full((2,50),float('nan'))):
            with self.assertRaises(ValueError):
                stable_forward(model,x)
        with self.assertRaises(ValueError):
            stable_forward(nn.Sequential(nn.Linear(50,1)),torch.zeros(2,50))
        with torch.no_grad():
            model[0].weight[0,0]=float('inf')
        with self.assertRaises(ValueError):
            stable_forward(model,torch.zeros(2,50))

    def test_runtime_identity_and_original_failure_still_rejected(self):
        runtime=common.environment()
        self.assertEqual(runtime['network_inference_backend'],
                         'learned-onboarding-rowwise-float32-v3-20261024')
        self.assertIn('torch_build_config',runtime)
        primary=np.array([-1.1087712049484253])
        split=np.array([-1.1087733507156372])
        with self.assertRaisesRegex(ValueError,'QUERY_BATCH_SCORE_DRIFT'):
            learning._replay_compare(primary,primary.copy(),split,primary,
                np.zeros(1),-23.301986694335938,np.zeros(1),0.,direct_scores=True)


if __name__=='__main__':
    unittest.main(verbosity=2)
