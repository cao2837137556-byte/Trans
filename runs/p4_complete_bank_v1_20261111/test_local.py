import json,tempfile
from pathlib import Path
import numpy as np
import worker as w
def main():
    rng=np.random.default_rng(27);raw=w.four(rng.normal(0,20,(120,3)));q=np.zeros((120,14));q[:30,0]=q[:30,2]=1;s=rng.uniform(0,1,120);s[30]=0;s[31]=1;b=np.array([119.,121.,122.]);self_=b*.7
    actual=w.correct(raw,s,q,b);expected=w.ac.scores(raw,s,q,b,'P4');assert np.array_equal(actual,expected)
    off=w.correct(raw,s,q,b,False);assert np.all(off<=actual) and np.array_equal(off[30:],actual[30:])
    assert np.all(w.correct(raw,s*.7,q,b)>=actual)
    assert np.all(w.correct(raw,s,q,self_)>=actual)
    assert np.array_equal(w.correct(raw,s,q,np.zeros(3)),raw)
    prob=w.four(rng.uniform(0,.1,(120,3)));p4=w.correct(prob,s,q,np.ones(3));assert (p4<0).any() and np.all(p4<=w.correct(prob,s,q,np.ones(3),power=3))
    assert len(w.SIX)==6 and len(set(w.SIX))==6
    # An existing accepted P4 row is accepted; a changed count is rejected.
    r=dict(pool='A',view='full',head='ensemble',group='NORMAL',guard_stratum='ALL',rows=10,alarm_count=2,sample_rate=.2,hierarchical_rate=.3)
    assert w.check_metric_rows([r],[r])==1
    try:w.check_metric_rows([r],[dict(r,alarm_count=3)])
    except AssertionError:pass
    else:raise AssertionError('P4_BASELINE_DRIFT_ACCEPTED')
    (w.HERE/'LOCAL_VALIDATION.json').write_text(json.dumps(dict(status='PASS',p4_original_arithmetic_exact=True,guard_off_subset=True,bank_and_geometry_monotonicity=True,zero_scale_identity=True,probability_negative_scores_preserved=True,baseline_drift_rejected=True,scope='synthetic only; runtime cache and lineage gates pending',worker_sha256=w.sha(w.HERE/'worker.py')),indent=2)+'\n');print('LOCAL_P4_PASS')
if __name__=='__main__':main()
