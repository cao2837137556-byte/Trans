import math
import numpy as np
import reporting
HEADS=('27','127','227','ensemble')

def rate(ix,p,w):
 ix=np.asarray(ix,dtype=np.int64);mass=math.fsum(w[ix]);n=len(ix);alarm=int(p[ix].sum())
 return dict(rows=n,alarm_count=alarm,no_alarm_count=n-alarm,unweighted_rate=alarm/n if n else None,
             weighted_rate=math.fsum(w[ix][p[ix]])/mass if mass else None,weight_mass=mass)

def groups(rows,keep):
 out={'pool':np.asarray(keep,dtype=np.int64)}
 for field in ('device','protocol','scenario'):
  for value in sorted({str(rows[i].get(field,'UNKNOWN')) for i in keep}):out[field+':'+value]=np.asarray([i for i in keep if str(rows[i].get(field,'UNKNOWN'))==value])
 return out

def summarize(rows,predictions,views):
 labels=np.asarray([r['label'] for r in rows]);result={}
 for view,(keep,w) in views.items():
  gg=groups(rows,keep);out={}
  for arm,methods in predictions.items():
   out[arm]={}
   for method,pred in methods.items():
    heads={}
    for j,h in enumerate(HEADS):
     metric={name:{label:rate(ix[labels[ix]==value],pred[:,j],w) for label,value in [('normal',0),('attack',1)]} for name,ix in gg.items()}
     safety=reporting._safety(list(keep),rows,methods['RAW'][:,j],pred[:,j],w)
     heads[h]=dict(groups=metric,c5_safety=safety)
    out[arm][method]=heads
  result[view]=out
 return result

def gates(report,cal=False):
 result=[];r=report['primary'];groupnames=r['FUSION790']['RAW']['ensemble']['groups']
 def check(name,passed,**evidence):result.append(dict(test=name,status='PASS' if passed else 'FAIL',**evidence))
 if not cal:
  for name,groupspec in groupnames.items():
   if name!='pool' and not name.startswith('device:'):continue
   for label,limit,op in [('normal',.01 if name=='pool' else .02,'max'),('attack',.99 if name=='pool' else .97,'min')]:
    v=groupspec[label]['weighted_rate']
    if v is not None:check('absolute/ensemble/'+name+'/'+label,v<=limit+1e-12 if op=='max' else v>=limit-1e-12,value=v,limit=limit)
  for h in HEADS[:3]:
   v=r['FUSION790']['RAW'][h]['groups']['pool']['attack']['weighted_rate']
   if v is not None:check('absolute/seed/'+h,v>=.97-1e-12,value=v,limit=.97)
 for h in HEADS:
  old=r['OLD782']['RAW'][h]['groups'];new=r['FUSION790']['RAW'][h]['groups']
  for g in new:
   if (g=='pool' or g.startswith('scenario:')) if cal else g.startswith('protocol:'):
    a=old[g]['attack'];b=new[g]['attack']
    if a['rows']:check('no_regression/'+h+'/'+g,a['weighted_rate']-b['weighted_rate']<=.001+1e-12,old=a,new=b,max_drop=.001)
  a=old['pool']['normal'];b=new['pool']['normal']
  if a['rows']:check('normal_increase/'+h,b['weighted_rate']-a['weighted_rate']<=.001+1e-12,old=a,new=b,max_increase=.001)
 return dict(status='FAIL' if any(v['status']=='FAIL' for v in result) else 'PASS',checks=result,scope='primary view; all nonempty registered groups; no adaptive selection')

def quant(x):
 return dict(zip(['min','p01','p10','p50','p90','p99','max'],map(float,np.quantile(x,[0,.01,.1,.5,.9,.99,1])))) if len(x) else None

def margins(rows,raw,corrected,cuts,scales,keep):
 result={};labels=np.asarray([r['label'] for r in rows]);group=groups(rows,keep)
 bound=np.r_[.25*scales,float(np.mean(.25*scales,dtype=np.float64))]
 for name,ix in group.items():
  ix=ix[labels[ix]==1]
  if not len(ix):continue
  head={}
  for j,h in enumerate(HEADS):
   m=raw[ix,j]-cuts[j];delta=raw[ix,j]-corrected[ix,j];after=m-delta
   histogram,edges=np.histogram(m,bins=40)
   head[h]=dict(rows=len(ix),raw_margin=quant(m),delta=quant(delta),corrected_margin=quant(after),
               correction_bound=float(bound[j]),margin_over_bound=quant(m/bound[j]) if bound[j]>0 else None,
               fraction_margin_gt_bound=float((m>bound[j]).mean()),withdrawn_raw_TP=int(((m>0)&(after<=0)).sum()),
               raw_margin_histogram=dict(counts=histogram.tolist(),edges=edges.tolist()))
  result[name]=head
 return result
