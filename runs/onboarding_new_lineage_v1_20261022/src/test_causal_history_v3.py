import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import constrained_onboarding_core_v2 as old
import constrained_onboarding_core_v3 as new
import constrained_onboarding_runner_v3 as runner
from causal_reference_overlap_v1 import require_prebank_history
from test_constrained_onboarding_integration_v1 import fixture,data

class CausalHistoryTests(unittest.TestCase):
    def test_nonoverlapping_pipeline_preserves_frozen_scores_and_calibration(self):
        import constrained_onboarding_runner_v2 as previous
        protocol=Path(__file__).parent/'frozen_onboarding/protocol.json'
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'old',Path(td)/'new'
            previous.run_development(fixture(),a,protocol)
            runner.run_development(fixture(),b,protocol)
            for p in a.rglob('*'):
                if p.name in ('scores.npz','decisions.npz'):
                    with np.load(p,allow_pickle=False) as x,np.load(b/p.relative_to(a),allow_pickle=False) as y:
                        self.assertEqual(x.files,y.files)
                        for key in x.files:self.assertEqual(x[key].tobytes(),y[key].tobytes())
            for p in (a/'calibration').glob('*.json'):
                self.assertEqual(p.read_bytes(),(b/'calibration'/p.name).read_bytes())

    def rows(self):
        base=dict(source_sha256='s',owner='owner',session_id='session',capture_id='capture',device='camera',
            partition='DEV',protocol=6,use='REFERENCE',label=0,reference_end=10.,bank_end_frame=10,
            label_metric_weight_denominator=1)
        refs=[dict(base,uid='r1',component_id='c1',timestamp=2.,frame=2),dict(base,uid='r2',component_id='c2',timestamp=3.,frame=3)]
        return refs
    def bank(self,cls,refs,**kw):
        d=data(refs)
        return cls.ReferenceBank(refs,d['e3'],d['q14'],(np.zeros(768),np.ones(768)),feature_uids=d['feature_uids'],q_uids=d['q_uids'],**kw)
    def trace(self,bank,rows):
        d=data(rows);return bank.own(rows,d['e3'],d['q14'],None,feature_uids=d['feature_uids'],q_uids=d['q_uids'],_raw_distances=True)
    def test_prebank_history_is_retained_and_never_self_matched(self):
        refs=self.rows();early=dict(refs[0],use='QUERY');later=dict(early,uid='late',frame=11,timestamp=11.)
        with self.assertRaisesRegex(ValueError,'QUERY_IS_REFERENCE'):self.trace(self.bank(old,refs),[early,later])
        trace=self.trace(self.bank(new,refs,allow_prebank_history=True),[early,later])
        self.assertEqual(trace['reason'][0],'BANK_NOT_YET_AVAILABLE')
        self.assertEqual(trace['support'][0],0);self.assertFalse(trace['eligible'][0])
        self.assertTrue(all(v is None for v in trace['matched_reference_uids'][0]))
        logits=np.array([[.4,-.0,2.],[.4,1.,2.]],dtype=np.float32)
        scores=new.apply_correction(logits,trace['support'],np.ones(3),.25)
        self.assertEqual(scores[0].tobytes(),logits[0].astype(np.float64).tobytes())
        self.assertEqual(len(scores),2)
        original=self.trace(self.bank(old,refs),[later])
        for key in original:
            np.testing.assert_equal(trace[key][1:],original[key])
    def test_forged_identity_source_overlap_and_future_replay_rejected(self):
        ref=self.rows()[0];query=dict(ref,use='QUERY')
        require_prebank_history(query,ref)
        for field,value in [('timestamp',11.),('frame',11),('device','other'),('source_sha256','other'),('label',1),('partition','LEARN')]:
            with self.subTest(field=field),self.assertRaises(ValueError):require_prebank_history(dict(query,**{field:value}),ref)
        with self.assertRaisesRegex(ValueError,'NOT_BEFORE_COMPLETE_BANK'):
            require_prebank_history(query,dict(ref,reference_end=1.))
        with self.assertRaisesRegex(ValueError,'ROLE_OR_SOURCE'):
            require_prebank_history(dict(query,partition='LEARN'),dict(ref,partition='LEARN'))
    def test_full_runner_keeps_fixed_query_set_and_early_head_decisions(self):
        bundle=fixture();pool='CIC_DEV';target=bundle['targets'][pool]
        # Dedicated OLD_BANK stays disjoint. New policies observe the same early
        # physical event that is also retained in the fixed reporting query set.
        for policy in ('B0','B1'):
            bank=target['banks'][policy]
            for i,r in enumerate(bank['rows']):
                r.update(uid='history-'+str(i),bank_end_frame=10)
            bank.update(feature_uids=[r['uid'] for r in bank['rows']],q_uids=[r['uid'] for r in bank['rows']])
        early=dict(target['banks']['B0']['rows'][0],use='QUERY')
        rr=[early]+target['rows'];updated=data(rr,[.5,.5,10.]);updated['banks']=target['banks'];bundle['targets'][pool]=updated
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'result';result=runner.run_development(bundle,out,Path(__file__).parent/'frozen_onboarding/protocol.json')
            self.assertEqual(result['status'],'COMPLETE')
            with np.load(out/pool/'B0/scores.npz',allow_pickle=False) as scores:
                self.assertEqual(scores['uid'].tolist(),[r['uid'] for r in rr])
                self.assertEqual(scores['head'][0].astype(np.float64).tobytes(),scores['corrected'][0].tobytes())
            with np.load(out/pool/'B0/decisions.npz',allow_pickle=False) as decisions:
                np.testing.assert_array_equal(decisions['head'][0],decisions['full'][0])
            self.assertTrue((out/'prebank_history_audit.json').is_file())

if __name__=='__main__':unittest.main()
