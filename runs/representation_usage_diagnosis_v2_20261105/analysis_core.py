"""Frozen-head functional diagnostics. Synthetic interventions are not deployment scores."""
import hashlib,math
import numpy as np
BLOCKS=('E3','Q14','CONTEXT8')
SLICES=(slice(0,768),slice(768,782),slice(782,790))

def quant(x):
 x=np.asarray(x)
 return None if not x.size else dict(zip(['min','p01','p10','p50','p90','p99','max'],map(float,np.quantile(x,[0,.01,.1,.5,.9,.99,1]))))

def permutation(rows,seed):
 """No labels, outcome scores or capture activity are used to construct donors."""
 mapping=np.arange(len(rows));groups={};singletons=0
 for i,r in enumerate(rows):groups.setdefault(r['protocol'],[]).append(i)
 for ix in groups.values():
  ix=sorted(ix,key=lambda i:hashlib.sha256((str(seed)+':'+rows[i]['uid']).encode()).digest())
  if len(ix)==1:singletons+=1
  mapping[ix]=np.roll(ix,1)
 assert sorted(mapping.tolist())==list(range(len(rows)))
 assert all(rows[i]['protocol']==rows[j]['protocol'] for i,j in enumerate(mapping))
 return mapping,singletons

def shapley(coalitions):
 # coalition dimension immediately follows row; remaining dimensions are heads.
 out=np.zeros((len(coalitions),3)+coalitions.shape[2:],np.float64)
 for block in range(3):
  for mask in range(8):
   if mask&(1<<block):continue
   count=bin(mask).count('1');weight=math.factorial(count)*math.factorial(2-count)/6
   out[:,block]+=weight*(coalitions[:,mask|(1<<block)]-coalitions[:,mask])
 assert np.max(np.abs(out.sum(1)-(coalitions[:,7]-coalitions[:,0])))<1e-9
 return out

def decompose(model,x,dimension):
 """All exact block coalitions of a float64 copy of the frozen 2-layer ReLU head."""
 w=model[0].weight.detach().numpy().astype(np.float64);b=model[0].bias.detach().numpy().astype(np.float64)
 v=model[2].weight.detach().numpy()[0].astype(np.float64);bias=float(model[2].bias.detach().numpy()[0]);x=np.asarray(x,dtype=np.float64)
 parts=[];local=[]
 for sl in SLICES:
  indices=np.arange(790)[sl]
  if dimension==8:indices=np.arange(8) if sl.start==782 else np.asarray([],int)
  else:indices=indices[indices<dimension]
  local.append(indices);parts.append(x[:,indices]@w[:,indices].T)
 outputs=np.empty((len(x),8));grad=np.zeros((len(x),3));act=(sum(parts)+b)>0
 input_grad=(act*v)@w
 for j,indices in enumerate(local):
  if len(indices):grad[:,j]=np.linalg.norm(input_grad[:,indices],axis=1)
 for mask in range(8):
  h=np.broadcast_to(b,(len(x),len(b))).copy()
  for j,part in enumerate(parts):
   if mask&(1<<j):h+=part
  outputs[:,mask]=np.maximum(h,0)@v+bias
 return outputs,grad,np.mean(np.abs(input_grad),axis=0)

def group_indices(rows):
 groups={'pool':np.arange(len(rows))}
 for field in ['label','protocol','device','scenario','capture_id']:
  value={}
  for i,r in enumerate(rows):value.setdefault(str(r.get(field,'UNKNOWN')),[]).append(i)
  for name,ix in value.items():groups[field+':'+name]=np.asarray(ix)
 return groups

def rate(ix,p,w):
 ix=np.asarray(ix,dtype=np.int64);mass=float(w[ix].sum());n=len(ix);alarms=int(p[ix].sum())
 return dict(rows=n,alarms=alarms,sample_rate=alarms/n if n else None,weighted_rate=float(w[ix][p[ix]].sum())/mass if mass else None)

def metrics(rows,decisions,weights,groups=None):
 labels=np.asarray([r['label'] for r in rows]);out={}
 for group,ix in (group_indices(rows) if groups is None else groups).items():
  out[group]={label:{h:rate(ix[labels[ix]==lab],decisions[:,j],weights) for j,h in enumerate(['27','127','227','ensemble'])} for label,lab in [('normal',0),('attack',1)]}
 return out

def changed(base,actual,cut,ix):
 before=base[ix]>cut;after=actual[ix]>cut
 return dict(rows=len(ix),delta=quant(actual[ix]-base[ix]),absolute_delta=quant(np.abs(actual[ix]-base[ix])),changed_decisions=int(np.sum(before!=after)),added_alarms=int(np.sum(~before&after)),removed_alarms=int(np.sum(before&~after)))
