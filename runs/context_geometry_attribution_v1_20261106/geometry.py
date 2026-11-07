"""Frozen two-dimensional geometry plus a source-only context intersection."""
import collections,math
import numpy as np

def rms(a,b):
 return np.sqrt(np.mean((np.asarray(a,np.float64)[:,None,:]-np.asarray(b,np.float64)[None,:,:])**2,axis=2))

def legal_indices(row,refs):
 if not refs:return [],'NO_REFERENCE_BANK'
 end=refs[0]['reference_end']
 assert all(r['reference_end']==end for r in refs)
 if row['timestamp']<=end:return [],'BANK_NOT_YET_AVAILABLE'
 frameends={r['bank_end_frame'] for r in refs if r['capture_id']==row['capture_id'] and 'bank_end_frame' in r}
 assert len(frameends)<=1
 if frameends and row['frame']<=next(iter(frameends)):return [],'BANK_FRAME_NOT_YET_AVAILABLE'
 ix=[i for i,r in enumerate(refs) if r['capture_id']!=row['capture_id'] or r['frame']<row['frame']]
 if len({refs[i]['component_id'] for i in ix})<2:return [],'FEWER_THAN_TWO_LEGAL_COMPONENTS'
 return ix,'ELIGIBLE'

def fit_context(rows,x,refs,rc,core,geometry,progress):
 assert rows and all(r['partition']=='LEARN' and r['fit_role']=='FIT' and r['label']==0 and r['use']!='REFERENCE' for r in rows)
 assert all(r['partition']=='LEARN' and r['label']==0 and r['use']=='REFERENCE' for r in refs)
 assert not set(r['uid'] for r in rows)&set(r['uid'] for r in refs)
 groups=collections.defaultdict(list)
 for i,r in enumerate(refs):groups[(r['partition'],r['device'],r['protocol'])].append(i)
 second=np.full(len(rows),np.inf);patterns=collections.defaultdict(list)
 for i,r in enumerate(rows):
  ix=sorted(groups.get((r['partition'],r['device'],r['protocol']),[]),key=lambda j:refs[j]['uid'])
  legal,_=legal_indices(r,[refs[j] for j in ix])
  if legal:patterns[tuple(ix[j] for j in legal)].append(i)
 for jj,(ri,ix) in enumerate(patterns.items()):
  comp=[refs[j]['component_id'] for j in ri]
  for start in range(0,len(ix),512):
   use=ix[start:start+512];second[use],_=core._second_distinct(rms(x[use],rc[list(ri)]),comp)
  progress('CALIBRATE_SOURCE_CONTEXT_RADIUS',jj+1,len(patterns))
 out={}
 for proto in [6,17]:
  ix=[i for i,r in enumerate(rows) if r['protocol']==proto and np.isfinite(second[i])]
  expected=geometry['protocols'][str(proto)]
  if not ix:
   assert expected['status']=='NO_SOURCE_GEOMETRY_SUPPORT';out[str(proto)]={'status':'NO_SOURCE_GEOMETRY_SUPPORT'};continue
  rr=[rows[i] for i in ix];digest=core._uid_hash([r['uid'] for r in rr])
  assert expected['eligible_uid_sha256']==digest and expected['rows']==len(ix),'SOURCE_GEOMETRY_ELIGIBILITY_DRIFT'
  w=core.class_weights(rr)
  out[str(proto)]=dict(status='READY',rho_c=core.weighted_quantile(second[ix],w,.9),rows=len(ix),eligible_uid_sha256=digest,quantile=.9,weight_sum=math.fsum(w))
 return out,second

def evaluate(d,refs,rz,rq,rc,norm,geom,rhoc,core,progress):
 u=[r['uid'] for r in refs];bank=core.ReferenceBank(refs,rz,rq,norm,feature_uids=u,q_uids=u,allow_prebank_history=True)
 rows=d['rows'];uu=[r['uid'] for r in rows]
 old=bank.own(rows,d['z'][:,:768],d['q'],geom,feature_uids=uu,q_uids=uu)
 assert np.max(np.abs(old['support']-d['support']))<=2e-10,'OLD_GEOMETRY_PARITY'
 new=np.zeros(len(rows));matched_dc=np.full((len(rows),2),np.nan);second_dc=np.full(len(rows),np.nan)
 for i,pair in enumerate(old['matched_reference_uids']):
  if pair[0] is not None:
   ix=[bank.by_uid[v] for v in pair];matched_dc[i]=rms(d['context'][i:i+1],rc[ix])[0]
 patterns=collections.defaultdict(list)
 for i,r in enumerate(rows):
  if not old['eligible'][i]:continue
  ix=bank.groups.get((r['partition'],r['device'],r['protocol']),[])
  legal,_=legal_indices(r,[refs[j] for j in ix]);assert legal
  patterns[tuple(ix[j] for j in legal)].append(i)
 done=0
 for ri,ix in patterns.items():
  ri=np.asarray(ri);comp=[refs[j]['component_id'] for j in ri];proto=rows[ix[0]]['protocol'];radii=core._radius(geom,proto);cr=rhoc[str(proto)]
  chunk=max(1,min(512,65536//len(ri)))
  for start in range(0,len(ix),chunk):
   use=np.asarray(ix[start:start+chunk]);dc=rms(d['context'][use],rc[ri]);second_dc[use],_=core._second_distinct(dc,comp)
   # max intersection can never create support where frozen two-block geometry has zero.
   positive=old['support'][use]>0
   if np.any(positive) and radii is not None and cr['status']=='READY':
    use2=use[positive];z=core._unit(d['z'][use2,:768],norm)
    dz=np.clip(1-z@bank.z[ri].T,0,2);dq=rms(d['q'][use2],bank.q14[ri])
    joint=np.maximum(np.maximum(core._ratio(dz,radii[0]),core._ratio(dq,radii[1])),core._ratio(dc[positive],cr['rho_c']))
    sec,_=core._second_distinct(joint,comp);new[use2]=np.clip(1-sec,0,1)
   done+=len(use)
   if start%max(chunk,chunk*50)==0:progress('THREE_BLOCK_REFERENCE_DISTANCE',done,len(rows))
 assert np.all(new<=old['support']+2e-10),'INTERSECTION_SUPPORT_MONOTONICITY'
 return old,new,matched_dc,second_dc

def reference_context_profile(refs,rc,core):
 out={}
 for proto in [6,17]:
  vals=[]
  for i,r in enumerate(refs):
   if r['protocol']!=proto:continue
   ix=[j for j,s in enumerate(refs) if (s['partition'],s['device'],s['protocol'])==(r['partition'],r['device'],proto) and s['component_id']!=r['component_id']]
   if len({refs[j]['component_id'] for j in ix})>=2:
    sec,_=core._second_distinct(rms(rc[i:i+1],rc[ix]),[refs[j]['component_id'] for j in ix]);vals.append(float(sec[0]))
  out[str(proto)]=dict(rows=len(vals),quantiles=np.quantile(vals,[0,.5,.9,.99,1]).tolist() if vals else None,scope='descriptive bank leave-one-component-out; not radius fitting')
 return out
