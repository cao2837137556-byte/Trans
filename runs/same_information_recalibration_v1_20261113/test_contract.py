"""Local regression for the threshold contract and real cached reference metadata."""
import unittest

import numpy as np

from calibration import fit, four, weighted_cut, predictions, hierarchical_weights, WITH_GUARD, NO_GUARD, RAW
from common_round1 import HERE, Inputs, config_at, dump, load, require
from reference_assets import bank


class CalibrationTest(unittest.TestCase):
    def test_minimum_observed_cut_and_ties(self):
        a = np.array([.5,.5,1.,3.])
        w = np.array([.49,.49,.01,.01])
        self.assertEqual(weighted_cut(a,w,.01)['cut'],1.)
        self.assertEqual(weighted_cut(a,w,.01)['strict_tail_mass'],.01)
        self.assertEqual(weighted_cut(np.ones(4),w,.01)['strict_tail_mass'],0.)

    def test_guard_branch_keeps_source_and_prebank(self):
        n=200
        rows=[dict(device='A',capture_id='c',component_id='x',use='REFERENCE',label=0) for _ in range(n)]
        r=np.arange(n,dtype=np.float64)
        q=np.zeros((n,14))
        q[-100:,0]=q[-100:,2]=1
        a=four(np.column_stack((r,r+1,r+2)))
        w,_=hierarchical_weights(rows)
        self.assertAlmostEqual(w.sum(),1.)
        fits=fit(rows,a,q,[40]*4)
        self.assertEqual(fits['fits'][WITH_GUARD]['fitted_rows'],100)
        self.assertEqual(fits['fits'][NO_GUARD]['heads'][0]['cut'],197.)
        self.assertLessEqual(fits['fits'][WITH_GUARD]['heads'][0]['strict_tail_mass'],.01+1e-14)
        mask=np.arange(n)>=20
        p=predictions(a,a,q,mask,[40]*4,fits)
        np.testing.assert_array_equal(p[WITH_GUARD][~mask | (q[:,0]==1)],
                                      p[RAW][~mask | (q[:,0]==1)])
        self.assertNotEqual(int(p[WITH_GUARD].sum()),int(p[NO_GUARD].sum()))

    def test_reference_role_guard(self):
        with self.assertRaisesRegex(ValueError,'TARGET_REFERENCE_NORMAL_ONLY'):
            hierarchical_weights([dict(device='a',capture_id='x',component_id='y',use='QUERY',label=0)])

    def test_reference_weight_is_equal_between_devices_and_captures(self):
        rows=[dict(use='REFERENCE',label=0,device=d,capture_id=c,component_id=z)
              for d,c,z in [('d1','cap1','a'),('d1','cap1','a'),('d1','cap1','b'),
                            ('d1','cap2','c'),('d2','cap3','d')]]
        w,_=hierarchical_weights(rows)
        np.testing.assert_array_equal(w,[.0625,.0625,.125,.25,.5])


def audit_local():
    cfg=config_at()
    store=Inputs(HERE.parents[1],load(HERE/'INPUT_PINS.json'),('reference',),local=True)
    rows={}
    for pool in ('CIC_DEV','UNSW_DEV','EDGE'):
        r,z,q,_=bank(store,cfg,pool,lambda *a,**k:None,local_partial=True)
        weights, keys=hierarchical_weights(r)
        rows[pool]=dict(rows=len(r),components=len(set(keys)),weight_mass=float(weights.sum()),
                         identity='ordered UID verified', e3_q14_verified=z is not None)
        del r,z,q,weights,keys
    require(sum(x['rows'] for x in rows.values())==79069,'LOCAL_REFERENCE_TOTAL')
    all_inputs=Inputs(HERE.parents[1],load(HERE/'INPUT_PINS.json'),('reference','query'),local=True)
    report=all_inputs.verify()
    dump(HERE/'LOCAL_ASSET_AUDIT.json',dict(status='PASS_METADATA_AND_AVAILABLE_BYTES',references=rows,
        sha_verified=sorted(report['checked']), absent_or_sha_unmatched_locally=sorted(report['failures']),
        remote_gate='pending; local absence is not evidence of remote absence',
        local_model_forwards=0, local_query_evaluations=0))
    print('LOCAL_ASSET_AUDIT',len(report['checked']),len(report['failures']))


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(CalibrationTest)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)
    audit_local()
