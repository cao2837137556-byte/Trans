"""Generated-only tests for the new A inference and paired comparison entry."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
import torch
import issue27frontend_a_expanded_eval_v1 as a


def rows():
    return [dict(uid=str(i),label=y,old_hard=old,ab_hard=ab,a_hard=aa,ab_logit=1. if ab else -1.,a_logit=1. if aa else -1.,
                 pool='attack' if y else 'normal',role='future_query',attack_family='attack' if y else 'benign',
                 context_key='c'+str(i),source_group='source',owner='A',context_in_ab_train=False,member_in_ab_train=False)
            for i,(y,old,aa,ab) in enumerate([(1,1,1,0),(1,1,0,1),(0,0,1,0),(0,0,0,1)])]


class Contracts(unittest.TestCase):
    def test_metrics_three_views(self):
        m=a.compare(rows());self.assertEqual(m['old_vs_A']['attack']['ab_recall'],.5)
        self.assertEqual(m['A_vs_AB']['attack']['old_correct_new_wrong'],1)
        self.assertEqual(m['A_vs_AB']['overall']['old_wrong_new_correct'],2)

    def test_serialization(self):
        m=a.compare(rows());self.assertEqual(m,json.loads(json.dumps(m)))

    def test_prediction_schema_preserves_AB(self):
        r=rows()[0];o={k:v for k,v in r.items() if k not in ('a_logit','a_hard')};a.validate_prediction(r,o)
        r['ab_logit']=2.
        with self.assertRaisesRegex(RuntimeError,'BASELINE_ROW_CHANGED'):a.validate_prediction(r,o)

    def test_zero_tie_and_nonfinite(self):
        r=rows()[0];o={k:v for k,v in r.items() if k not in ('a_logit','a_hard')};r['a_logit']=0.;a.validate_prediction(r,o)
        for value in (-.1,float('nan')):
            r['a_logit']=value
            with self.assertRaisesRegex(RuntimeError,'A_HARD_RULE'):a.validate_prediction(r,o)

    def fixture(self,folder):
        d=folder/'members'/'m';d.mkdir(parents=True)
        x=np.arange(3*131,dtype=np.float32).reshape(3,131)/1000;raw=x.astype('<f4').tobytes();(d/'features.f32le').write_bytes(raw)
        target={'uid':'u','event':1,'feature_prefix_sha256':a.prefix_hash(raw,1)}
        c={'key':'c','member_id':'m','offset':0,'length':3,'targets':[target]}
        original={'uid':'u','context_key':'c','member_id':'m','event_index':1,'feature_prefix_sha256':target['feature_prefix_sha256'],'ab_logit':-.2,'ab_hard':0}
        return x,[c],{'u':original}

    def test_real_student_generated_input_single_forward(self):
        import issue27frontend_paired_train_model_v1 as m
        m.configure();model=m.Student().eval();before=m.state_hash(model)
        with tempfile.TemporaryDirectory(dir=a.s.ROOT/'tmp') as d:
            folder=Path(d);x,cs,rs=self.fixture(folder)
            with torch.inference_mode():expected=float(model([torch.from_numpy(x)],['c'])[0][1])
            counts=a.infer_contexts(model,cs,rs,folder,a.Progress(folder,time.monotonic()),torch,np)
            self.assertEqual(counts,(1,3));self.assertEqual(rs['u']['a_logit'],expected)
            self.assertEqual(rs['u']['ab_logit'],-.2);self.assertEqual(before,m.state_hash(model))

    def test_prefix_mismatch_before_any_forward(self):
        with tempfile.TemporaryDirectory(dir=a.s.ROOT/'tmp') as d:
            folder=Path(d);x,cs,rs=self.fixture(folder);rs['u']['feature_prefix_sha256']='bad'
            def forbidden(*args):raise AssertionError('forward must not happen')
            with self.assertRaisesRegex(RuntimeError,'PREFIX_SHA'):
                a.infer_contexts(forbidden,cs,rs,folder,a.Progress(folder,time.monotonic()),torch,np)

    def test_target_join_mismatch_before_forward(self):
        with tempfile.TemporaryDirectory(dir=a.s.ROOT/'tmp') as d:
            folder=Path(d);x,cs,rs=self.fixture(folder);rs['u']['event_index']=0
            with self.assertRaisesRegex(RuntimeError,'INPUT_TARGET_JOIN'):
                a.infer_contexts(None,cs,rs,folder,a.Progress(folder,time.monotonic()),torch,np)

    def test_report_has_distinct_A_AB_columns(self):
        with tempfile.TemporaryDirectory(dir=a.s.ROOT/'tmp') as d:
            p=Path(d);a.report(p,a.compare(rows()));text=(p/'result.md').read_text(encoding='utf-8')
            self.assertIn('| 旧P2 | 新A | 新AB |',text);self.assertIn('A检出、AB漏检：1条',text)

    def test_supervisor_failure_no_retry(self):
        with tempfile.TemporaryDirectory(dir=a.s.ROOT/'tmp') as d:
            out=Path(d)/'attempt'
            result=a.supervise([str(a.s.PYTHON),'-c','raise SystemExit(7)'],out)
            self.assertEqual(result['status'],'STOP');self.assertEqual(result['retries'],0)
            self.assertFalse((out/'result.md').exists());self.assertTrue((out/'SHA256SUMS').exists())
            with self.assertRaises(FileExistsError):a.supervise([],out)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    a.PACKAGE.mkdir(exist_ok=True)
    a.s.atomic_json(a.PACKAGE/'tests.json',{'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,
        'tests_passed':result.testsRun-len(result.errors)-len(result.failures),'real_model_loads':0,'raw_decodes':0,
        'failures':[(str(t),v) for t,v in result.errors+result.failures]})
    raise SystemExit(0 if result.wasSuccessful() else 1)
