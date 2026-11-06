import json
from pathlib import Path
import numpy as np
import coverage_core as c
def main(path=None):
    rows=[dict(device=d,activity='a',protocol=17) for d in ['a','a','b','b']]*2
    keys,ids=c.groups(rows,['device','activity','protocol']);y=np.array([0]*4+[1]*4)
    w=np.array([.125]*4+[.125]*4);sel=np.array([1,0,0,0,1,0,0,0],bool)
    b=np.array([2.,1.,3.,0.,4.,4.,4.,4.]);s=b-np.array([0.,0.,0.,0.,0.,0.,.2,0.]);z=np.zeros(8)
    a=c.summarize(keys,ids,y,w,sel,b,s,z,z,1.5,1.,1.)
    assert a['normal']['summary']['missing_strata']==1
    assert a['normal']['summary']['missing_stratum_class_mass']==.5
    assert a['normal']['summary']['residual_alarm_mass_in_missing_strata']==.25
    assert a['attack']['summary']['selected_share_of_original_risk']==0
    assert sum(v['rows'] for v in a['normal']['records'])==4
    # Finite difference of attack squared hinge w.r.t. score.
    eps=1e-6;f=lambda t:max((4-t)-.01,0)**2
    assert abs((f(3.8+eps)-f(3.8-eps))/(2*eps)+.38)<1e-8
    labels=np.repeat([0,1],17000);weights=np.ones(34000)/34000;actual=np.zeros(34000,bool);actual[:8192]=True;actual[17000:25192]=True
    m=c.proposed_samples(labels,weights,actual);m2=c.proposed_samples(labels,weights,actual)
    assert all(np.array_equal(m[k],m2[k]) for k in m)
    assert [int(x.sum()) for x in m.values()]==[16384,32768,16384]
    assert all(int(mask[labels==0].sum())==int(mask[labels==1].sum()) for mask in m.values())
    r=dict(status='PASS',tests=['missing_semantic_stratum_detected','weighted_missing_mass','active_tail_outside_sample','group_count_conservation','score_derivative_finite_difference','deterministic_source_only_counterfactual_membership'])
    Path(path or Path(__file__).with_name('LOCAL_REGRESSION.json')).write_text(json.dumps(r,indent=2));print(json.dumps(r))
if __name__=='__main__':main()
