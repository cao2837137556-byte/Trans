"""Exact ReLU path contributions; descriptions do not establish causal attribution."""
import collections
import numpy as np
FIELDS=['pps_1s','ip_Bps_1s','unique_src_1s','unique_5tuple_1s','pps_10s','ip_Bps_10s','unique_src_10s','unique_5tuple_10s']

def quant(x):
 x=np.asarray(x);x=x[np.isfinite(x)]
 return dict(zip(['min','p01','p10','p50','p90','p99','max'],np.quantile(x,[0,.01,.1,.5,.9,.99,1]).tolist())) if len(x) else None

def counts(rows,ix,field):return dict(collections.Counter(str(rows[i].get(field,'UNKNOWN')) for i in ix))

def exact(model,x):
 w=model[0].weight.detach().numpy().astype(np.float64);b=model[0].bias.detach().numpy().astype(np.float64)
 v=model[2].weight.detach().numpy()[0].astype(np.float64);bias=float(model[2].bias.detach().numpy()[0]);x=np.asarray(x,np.float64)
 wc=w[:,-8:];xc=x[:,-8:];end=x@w.T+b;delta=xc@wc.T;start=end-delta
 slope=np.zeros_like(start);both=(start>0)&(end>0);slope[both]=1
 up=(start<=0)&(end>0);down=(start>0)&(end<=0)
 slope[up]=end[up]/delta[up];slope[down]=-start[down]/delta[down]
 ig=xc*((slope*v)@wc);gradient=((end>0)*v)@wc
 score=np.maximum(end,0)@v+bias;base=np.maximum(start,0)@v+bias
 assert np.max(np.abs(ig.sum(1)-(score-base)))<1e-8
 return score,base,ig,gradient

def contribution_summary(scores,base,ig,grad,cuts,ix):
 if not len(ix):return dict(rows=0)
 out=dict(rows=len(ix),margin=quant(scores[ix]-cuts),baseline_margin=quant(base[ix]-cuts),context_total=quant(ig[ix].sum(1)),negative_contribution_dominates=int((np.maximum(-ig[ix],0).sum(1)>np.maximum(ig[ix],0).sum(1)).sum()),fields={})
 for j,name in enumerate(FIELDS):
  out['fields'][name]=dict(ig=quant(ig[ix,j]),mean_ig=float(ig[ix,j].mean()),local_gradient=quant(grad[ix,j]),gradient_positive_fraction=float((grad[ix,j]>0).mean()),gradient_negative_fraction=float((grad[ix,j]<0).mean()),negative_ig_fraction=float((ig[ix,j]<0).mean()))
 return out

def physical_misses(d,physical,refrows,refphys,raw,cuts):
 rows=d['rows'];out={};refp={}
 for proto in [6,17]:
  v=refphys[[i for i,r in enumerate(refrows) if r['protocol']==proto]]
  refp[proto]=np.quantile(v,.99,axis=0)
 for role,expected in [('UDP',268),('HTTP',34)]:
  ix=np.asarray([i for i,r in enumerate(rows) if r['source_role']==role and raw[i,3]<=cuts[3]])
  assert len(ix)==expected,'RAW_MISS_REPRODUCTION'
  age=np.asarray([physical[rows[i]['uid']]['age_seconds'] for i in ix]);inb=np.asarray([physical[rows[i]['uid']]['inbound'] for i in ix]);x=np.asarray([physical[rows[i]['uid']]['features'] for i in ix])
  p99=refp[17 if role=='UDP' else 6];high=(x[:,0]>p99[0])|(x[:,4]>p99[4]);cold=(age<10)|~inb
  masks={'ALL':np.ones(len(ix),bool),'warm_lt1':age<1,'warm_lt10':age<10,'noninbound':~inb,'warm_or_noninbound':cold,'mature_inbound_high_pps':~cold&high,'mature_inbound_normal_range_pps':~cold&~high}
  summary={}
  for name,mask in masks.items():
   chosen=ix[mask];summary[name]=dict(rows=int(mask.sum()),fraction=float(mask.mean()),raw_margin=quant(raw[chosen,3]-cuts[3]),features={f:quant(x[mask,j]) for j,f in enumerate(FIELDS)},http_strata=counts(rows,chosen,'stratum'),captures=counts(rows,chosen,'capture_id'))
  out[role]=dict(rows=len(ix),reference_p99=dict(zip(FIELDS,p99.tolist())),groups=summary,interpretation='Descriptive physical categories; not proof of impossible detection, not label removal')
 return out

def false_alarm_trace(rows,raw,corrected,cuts,scales,old,geom):
 out={};s=old['support'];g=1-(1-s)**3;normal=np.asarray([r['label']==0 for r in rows]);bound=np.r_[.25*scales,np.mean(.25*scales)]
 for j,head in enumerate(['27','127','227','ensemble']):
  ix=np.flatnonzero(normal&(corrected[:,j]>cuts[j]));margin=raw[:,j]-cuts[j]
  masks={'support_zero':s[ix]==0,'support_low_0_to_08':(s[ix]>0)&(s[ix]<.8),'support_ge08':s[ix]>=.8}
  parts={}
  for name,mask in masks.items():
   use=ix[mask];rz=[];rq=[]
   for i in use:
    radii=geom['protocols'][str(rows[i]['protocol'])]
    if radii['status']=='READY':
     rz.append(old['second_dz'][i]/radii['rho_z'] if radii['rho_z'] else (0 if old['second_dz'][i]==0 else np.inf));rq.append(old['second_dq'][i]/radii['rho_q'] if radii['rho_q'] else (0 if old['second_dq'][i]==0 else np.inf))
   parts[name]=dict(rows=len(use),fraction=len(use)/len(ix) if len(ix) else None,reasons=counts([{'reason':r} for r in old['reason']],use,'reason'),support=quant(s[use]),kernel=quant(g[use]),raw_margin=quant(margin[use]),actual_deduction=quant(raw[use,j]-corrected[use,j]),above_max_cap=int((margin[use]>bound[j]).sum()),above_support_scaled_cap=int((margin[use]>bound[j]*g[use]).sum()),second_dz_over_rho=quant(rz),second_dq_over_rho=quant(rq),nonfinite_ratio_count=int(np.sum(~np.isfinite(rz))+np.sum(~np.isfinite(rq))))
  assert sum(v['rows'] for v in parts.values())==len(ix)
  out[head]=dict(rows=len(ix),maximum_cap=float(bound[j]),categories=parts)
 return out
