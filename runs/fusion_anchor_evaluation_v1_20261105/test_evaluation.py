"""Regression checks for arm attribution, baseline identity, and runtime ownership."""
import ast,json
from pathlib import Path
import numpy as np
import worker as w
HERE=Path(__file__).resolve().parent
def main():
    names=['OLD782','REFIT782','STATS8','FUSION790'];arms={n:dict(cuts=np.zeros(4)) for n in names}
    saved={n+'_RAW':np.ones((2,4)) for n in names};scores={n:{'RAW':saved[n+'_RAW'].copy()} for n in names}
    assert all(v==0 for v in w.baseline_check(['a','b'],['a','b'],saved,scores,arms).values())
    for case in ['uid','score','decision']:
        use={n:{'RAW':v['RAW'].copy()} for n,v in scores.items()};data={n:v.copy() for n,v in saved.items()}
        ids=['b','a'] if case=='uid' else ['a','b']
        if case=='score':use['OLD782']['RAW'][0,0]+=.1
        if case=='decision':use['OLD782']['RAW'][0,0]=.0001;data['OLD782_RAW'][0,0]=-.0001
        try:w.baseline_check(['a','b'],ids,data,use,arms)
        except AssertionError:pass
        else:raise AssertionError('NEGATIVE_CONTROL:'+case)
    class Metrics:
        def gates(self,r):
            assert r['primary']['FUSION790']=='new_anchor' and r['primary']['OLD782']=='old'
            return dict(status='FAIL')
    result=w.candidate_gates({'primary':{'OLD782':'old','FUSION790':'prior_fusion','ANCHOR790':'new_anchor'}},Metrics())
    assert result['status']=='FAIL' and result['evaluated_candidate']=='ANCHOR790'
    tree=ast.parse((HERE/'worker.py').read_text())
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='set_num_interop_threads' for n in ast.walk(tree))
    out=dict(status='PASS',baseline_uid_corruption_rejected=True,baseline_score_corruption_rejected=True,baseline_decision_flip_rejected=True,new_candidate_gate_alias_correct=True,scientific_fail_preserved=True,interop_owner_remains_frozen_backend=True,scope='LOCAL_REGRESSION_NOT_REAL_HPC')
    (HERE/'LOCAL_REGRESSION.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out))
if __name__=='__main__':main()
