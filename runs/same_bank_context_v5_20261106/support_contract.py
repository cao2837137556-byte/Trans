"""Reproduce the frozen C2/C3/C4 stored-support schema, not a tolerance exception.

C2 stores zero effective support on SYN-no-ACK rows. C3 refreshes only
non-guarded Heim rows. C4 refreshes all rows of its four named B devices.
All other stored entries retain C2's zero. Edge stores geometric support.
Geometric support remains unchanged for three-block distance/donor analysis.
"""
from collections import Counter
import numpy as np

C4_DEVICES=frozenset({
 'unsw-attack-traces-2018:70:ee:50:18:34:43',
 'unsw-attack-traces-2018:00:16:6c:ab:6b:88',
 'unsw-attack-traces-2018:50:c7:bf:00:56:39',
 'unsw-attack-traces-2018:ec:1a:59:79:f4:89',
})

def stored_view(pool,rows,q,geometric):
 assert pool in ['CIC_DEV','UNSW_DEV','EDGE']
 guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)
 zero=guard.copy() if pool=='CIC_DEV' else (
  guard&np.asarray([r['device'] not in C4_DEVICES for r in rows]) if pool=='UNSW_DEV' else np.zeros(len(rows),bool))
 out=np.asarray(geometric,dtype=np.float64).copy();out[zero]=0.
 return out,zero

def audit(pool,rows,q,geometric,frozen):
 actual,zero=stored_view(pool,rows,q,geometric)
 assert actual.shape==np.asarray(frozen).shape==(len(rows),)
 assert np.isfinite(actual).all() and np.isfinite(frozen).all()
 err=np.abs(actual-frozen);bad=np.flatnonzero(err>2e-10)
 details=[dict(uid=rows[i]['uid'],device=rows[i]['device'],protocol=rows[i]['protocol'],
  stored_expected=float(frozen[i]),stored_rebuilt=float(actual[i]),geometric=float(geometric[i]),
  c2_zero_applied=bool(zero[i])) for i in bad[:32]]
 return dict(status='PASS' if not len(bad) else 'FAIL',rows=len(rows),compared_rows=len(rows),excluded_rows=0,
  max_abs_error=float(err.max(initial=0)),mismatch_count=len(bad),mismatch_examples=details,
  c2_zero_rows=int(zero.sum()),c2_zero_by_device=dict(Counter(rows[i]['device'] for i in np.flatnonzero(zero))),
  geometric_vs_stored_max_abs_difference=float(np.abs(geometric-frozen).max(initial=0)),
  definition='C2 effective-zero; C3 non-guarded Heim refresh; C4 four-device all-row refresh; Edge geometric')
