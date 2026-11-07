"""Exact observed-score partitions for strict score>cut; no per-class thresholds."""
import math
import numpy as np
def curve(scores,weights,denominator,cuts):
 order=np.argsort(scores,kind='stable');x=scores[order];w=np.asarray(weights,dtype=np.longdouble)[order]
 tail=np.r_[np.cumsum(w[::-1],dtype=np.longdouble)[::-1],np.longdouble(0)]
 return tail[np.searchsorted(x,cuts,side='right')]/np.longdouble(denominator)
def analyze(groups,source_cut):
 cuts=np.unique(np.concatenate([g['scores'] for g in groups.values()]+[np.array([source_cut])]))
 cuts=np.r_[np.nextafter(cuts[0],-np.inf),cuts]
 curves={k:curve(v['scores'],v['weights'],v['denominator'],cuts) for k,v in groups.items()}
 def masks(keys):
  n=np.ones(len(cuts),bool);a=n.copy();possible=n.copy()
  for k in keys:
   v=curves[k];normal=k.endswith('/NORMAL');limit=np.longdouble('.02' if normal else '.999')
   # Sample count boundaries are exact integer comparisons; weighted near-boundaries remain unconfirmed.
   if '/sample/' in k:
    count=np.rint(v*groups[k]['denominator']).astype(np.int64);d=int(groups[k]['denominator'])
    ok=count*50<d if normal else count*1000>=999*d
   else:
    close=np.abs(v-limit)<np.longdouble('1e-12')
    ok=(v<limit)&~close if normal else (v>=limit)&~close
   if normal:n&=ok
   else:a&=ok
   possible&=(ok if '/sample/' in k else (ok|close))
  return n,a,possible
 def point(i):
  if i is None:return None
  cut=float(cuts[i]);rates={}
  for k,g in groups.items():
   mask=g['scores']>cut;rate=math.fsum(g['weights'][mask])/g['denominator']
   assert abs(rate-float(curves[k][i]))<2e-11
   rates[k]=dict(rate=rate,alarm_count=int(mask.sum()),rows=len(mask),denominator=g['denominator'])
  return dict(cut=cut,rates=rates)
 bases=['sample','hierarchical','HT'];out={}
 for basis in bases+['ALL_BASES']:
  for scope in ['EDGE','ALL_DATASETS']:
   keys=[k for k in groups if (scope=='ALL_DATASETS' or k.startswith('EDGE/')) and (basis=='ALL_BASES' or '/'+basis+'/' in k or (basis=='HT' and scope=='ALL_DATASETS' and not k.startswith('EDGE/')))]
   n,a,amb=masks(keys);ni=np.flatnonzero(n);ai=np.flatnonzero(a);joint=np.flatnonzero(n&a)
   # Lowest permissible cut gives maximal recalls under FPR cap; highest recall-compatible cut minimizes FPR.
   lo=int(ni[0]) if len(ni) else None;hi=int(ai[-1]) if len(ai) else None
   out[scope+'/'+basis]=dict(status='FEASIBLE' if len(joint) else ('BOUNDARY_UNRESOLVED' if np.any(amb) else 'INFEASIBLE'),constraints=keys,
    recall_constrained=point(hi),fpr_constrained=point(lo),feasible_point=point(int(joint[-1])) if len(joint) else None,
    lower_cut=float(cuts[joint[0]]) if len(joint) else None,upper_cut_exclusive=float(cuts[joint[-1]+1]) if len(joint) and joint[-1]+1<len(cuts) else None)
 return dict(source_point=point(int(np.searchsorted(cuts,source_cut))),partitions=len(cuts),results=out)
