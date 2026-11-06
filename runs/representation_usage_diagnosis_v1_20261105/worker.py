"""Read-only model usage, error attribution and C5 counterfactual diagnosis."""
import argparse,gc,hashlib,json,os,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent/'device_context_evaluation_v1_20261105'
PHASE='PREFLIGHT'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(n,v):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):
 rss=psutil.Process().memory_info().rss;assert rss<7*1024**3,'MEMORY_LIMIT'
 write(PHASE+'_PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),rss_mib=rss/2**20,updated_unix=time.time(),**kw))
def initialize():
 for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,'LOCAL_PIN:'+n
 for n,h in read(HERE/'PARENT_PINS.json').items():assert sha(PARENT/n)==h,'PARENT_PIN:'+n
 sys.path.insert(0,str(PARENT));import common as c
 c.verify();c.progress=progress
 import inputs,edge_context
 inputs.progress=progress;edge_context.progress=progress;edge_context.write=write
 return c,inputs,edge_context

import analysis_core as ac
HEADS=['27','127','227','ensemble']

def data_load(pool,c,inputs,context,small=False):
 d=inputs.edge() if pool=='EDGE' else inputs.ab(pool)
 for r in d['rows']:
  r.setdefault('scenario',r.get('activity',r.get('source_role','UNKNOWN')))
  r.setdefault('source_role','NORMAL' if r['label']==0 else r['scenario'])
 if pool=='EDGE':
  ix,d['context']=context.join(d['rows']);assert len(ix)==60000
  import reporting
  d['views']={'primary':(np.arange(len(ix)),reporting._hierarchical_weights(d['rows']))}
 result=read(PARENT/('EDGE_RESULT.json' if pool=='EDGE' else 'AB_RESULT.json'));s=result['scores'] if pool=='EDGE' else result['pools'][pool]['scores']
 assert sha(s['path'])==s['sha256'];saved=np.load(s['path']);assert saved['uid'].tolist()==[r['uid'] for r in d['rows']]
 d['saved']={n:saved[n].copy() for n in saved.files if n!='uid'}
 if small:
  choices={}
  for i,r in sorted(enumerate(d['rows']),key=lambda p:p[1]['uid']):choices.setdefault((r['device'],r['protocol'],r['label'],r['source_role']),[]).append(i)
  ix=np.asarray(sorted(i for v in choices.values() for i in v[:8]))
  d={key:([v[i] for i in ix] if key=='rows' else {k:a[ix] for k,a in v.items()} if key=='saved' else v[ix]) for key,v in d.items() if key in ['rows','z','q','context','support','saved']}
  d['views']={'primary':(np.arange(len(ix)),np.ones(len(ix)))}
 return d

def fit_profile(c):
 vals=np.load(c.pin(c.SOURCE/'features8/LEARN.npy',c.read(c.HERE/'SOURCE_FEATURE_ACCEPTANCE.json')['arrays']['LEARN']['sha256']),mmap_mode='r');ix=np.load(c.SOURCE/'metadata/FIT.npy')
 meta=np.load(c.SOURCE/'metadata/LEARN.npz');uids=[u.decode() for u in meta['uid'][ix]]
 k,_,_=c.models();assert k.c.uid_sha(uids)==read(PARENT/'TRAINING_SPEC_FROZEN.json')['data_identity']['FIT']['uid_sha256']
 x=c.extra_normalized(vals[ix]);profile=dict(rows=len(ix),min=x.min(0).tolist(),max=x.max(0).tolist(),quantiles=np.quantile(x,[.001,.01,.5,.99,.999],axis=0).tolist(),definition='Existing FIT only, normalized context8; descriptive coverage, not fitted model/threshold')
 write('FIT_CONTEXT_PROFILE.json',profile);return profile

def input_matrix(d,k,norm,dimension):
 n=len(d['rows']);x=np.empty((n,dimension),np.float32)
 for start in range(0,n,1024):
  ix=np.arange(start,min(start+1024,n));actual=k.normalized((d['z'],d['context']),d['q'],ix,norm,dimension).numpy()
  if dimension==8:expected=d['context'][ix]
  else:
   z=((np.asarray(d['z'][ix,:768],dtype=np.float64)-norm[0])/norm[1]).astype(np.float32);expected=np.concatenate((z,d['q'][ix]),axis=1)
   if dimension==790:expected=np.concatenate((expected,d['context'][ix]),axis=1)
  assert np.array_equal(actual,expected),'BLOCK_CONCAT_OR_NORMALIZATION';x[ix]=actual
 return x

def direct(model,x):
 import torch
 out=np.empty(len(x),np.float64)
 with torch.inference_mode():
  for start in range(0,len(x),1024):out[start:start+1024]=model(torch.from_numpy(np.ascontiguousarray(x[start:start+1024]))).flatten().numpy()
 return out

def input_profile(d,x):
 result={};cohorts={}
 for i,r in enumerate(d['rows']):cohorts.setdefault(str(r['label'])+':'+str(r['protocol'])+':'+r['source_role'],[]).append(i)
 for group,take in cohorts.items():
  ix=np.asarray(take);out={}
  for name,sl in zip(ac.BLOCKS,ac.SLICES):
   values=x[ix,sl];std=np.std(values.astype(np.float64),axis=0)
   out[name]=dict(rows=len(ix),dimensions=values.shape[1],varying_dimensions_above_1e_6=int((std>1e-6).sum()),std=ac.quant(std),norm=ac.quant(np.linalg.norm(values,axis=1)),unique_float32_rows=len({hashlib.sha256(row.tobytes()).digest() for row in values}))
  hashes={d['rows'][i].get('_input_tensor_sha256') for i in ix};out['tokenized_input_unique']=len(hashes) if None not in hashes else None;result[group]=out
 return result

def evaluate(pool,d,c,k,norm,arms,profile):
 started=time.monotonic();n=len(d['rows']);groups=ac.group_indices(d['rows']);cohorts={g:ix for g,ix in groups.items() if g=='pool' or g.startswith(('label:','protocol:','scenario:'))}
 take,w=d['views']['primary'];primary={g:np.intersect1d(ix,take) for g,ix in cohorts.items()};result=dict(rows=n,primary_rows=len(take),arms={},interpretation='Frozen-head sensitivity; zero and shuffled blocks can be off-manifold; not replacement operating points')
 x790=input_matrix(d,k,norm,790);result['input_profile']=input_profile(d,x790)
 permutations=[ac.permutation(d['rows'],seed)[0] for seed in (20261105,20261106)]
 all_scores={};all_masks={};all_shap={};gradient_profiles={};direct_errors={};arrays={}
 for name,arm in arms.items():
  dim=arm['dimension'];x=x790[:,782:] if dim==8 else x790[:,:dim];coalitions=np.empty((n,8,3));grad=np.empty((n,3,3));raw=np.empty((n,3));gradient_profiles[name]={}
  permuted={block+'_'+str(seed):np.empty((n,3)) for block in ac.BLOCKS for seed in (20261105,20261106)}
  for j,model in enumerate(arm['models']):
   raw[:,j]=direct(model,x);gmean=np.zeros(dim)
   for start in range(0,n,1024):
    end=min(start+1024,n);v,g,gm=ac.decompose(model,x[start:end],dim);coalitions[start:end,:,j]=v;grad[start:end,:,j]=g;gmean+=gm*(end-start)/n
    if start%16384==0:progress(pool+'_'+name+'_DECOMPOSITION',start,n,head=HEADS[j])
   gradient_profiles[name][HEADS[j]]=gmean.tolist()
   for block,sl in zip(ac.BLOCKS,ac.SLICES):
    local=slice(0,8) if dim==8 and block=='CONTEXT8' else slice(0,0) if dim==8 else slice(sl.start,min(sl.stop,dim))
    for seed,mapping in zip((20261105,20261106),permutations):
     out=permuted[block+'_'+str(seed)][:,j]
     for start in range(0,n,1024):
      end=min(start+1024,n);batch=x[start:end].copy();batch[:,local]=x[mapping[start:end],local];out[start:end]=direct(model,batch)
  raw=c.four(raw);saved=d['saved'][name+'_RAW'];error=float(np.max(np.abs(raw-saved)));assert error<=.002,'FROZEN_FORWARD_PARITY'
  assert np.array_equal(raw>arm['cuts'],saved>arm['cuts']),'FROZEN_FORWARD_DECISIONS'
  approximation=c.four(coalitions[:,7]);numeric=float(np.max(np.abs(approximation-raw)));assert numeric<=.002,'DECOMPOSITION_NUMERICS'
  full=np.stack([c.four(coalitions[:,mask]) for mask in range(8)],axis=1);phi=ac.shapley(full)
  details=dict(forward_error=error,decomposition_error=numeric,decomposition_decision_roundoff=int(np.sum((approximation>arm['cuts'])!=(raw>arm['cuts']))),coalitions={},permutations={},attribution={})
  for mask in range(8):details['coalitions'][str(mask)]=ac.metrics(d['rows'],full[:,mask]>arm['cuts'],w,primary)
  for key,values in permuted.items():
   values=c.four(values);details['permutations'][key]=dict(metrics=ac.metrics(d['rows'],values>arm['cuts'],w,primary),sensitivity={g:{h:ac.changed(raw[:,j],values[:,j],arm['cuts'][j],ix) for j,h in enumerate(HEADS)} for g,ix in primary.items()});arrays[name+'_PERM_'+key]=values
  for group,ix in primary.items():
   details['attribution'][group]={h:{block:dict(signed=ac.quant(phi[ix,b,j]),absolute=ac.quant(np.abs(phi[ix,b,j])),input_gradient_l2=ac.quant(grad[ix,b,j]) if j<3 else None) for b,block in enumerate(ac.BLOCKS)} for j,h in enumerate(HEADS)}
  all_scores[name]=raw;all_masks[name]=full;all_shap[name]=phi;result['arms'][name]=details;arrays[name+'_COALITIONS']=full;arrays[name+'_SHAPLEY']=phi
 result['permutation_changes']={str(seed):{block:int(np.any(x790[:,sl]!=x790[mapping,sl],axis=1).sum()) for block,sl in zip(ac.BLOCKS,ac.SLICES)} for seed,mapping in zip((20261105,20261106),permutations)}
 # Factor score function, frozen threshold and frozen correction scale independently.
 result['c5_factorial']={};factor={}
 for scorearm in ['OLD782','FUSION790']:
  for cutarm in ['OLD782','FUSION790']:
   for scalearm in ['OLD782','FUSION790']:
    key=scorearm+'__cut_'+cutarm+'__scale_'+scalearm;values=c.four(c.correction(all_scores[scorearm][:,:3],d['support'],d['q'],arms[scalearm]['scales']));pred=values>arms[cutarm]['cuts'];factor[key]=pred
    result['c5_factorial'][key]=ac.metrics(d['rows'],pred,w,primary)
    if scorearm==cutarm==scalearm:assert np.array_equal(pred,d['saved'][scorearm+'_C5_P3']>arms[scorearm]['cuts']),'C5_IDENTITY'
 # All capture/device/protocol normal error groups, including disagreements, stay on HPC.
 errors={};normal=np.asarray([r['label']==0 for r in d['rows']]);bounds=np.asarray([profile['min'],profile['max']]);outside=((d['context']<bounds[0])|(d['context']>bounds[1])).any(1)
 for j,h in enumerate(HEADS):
  old=factor['OLD782__cut_OLD782__scale_OLD782'][:,j];new=factor['FUSION790__cut_FUSION790__scale_FUSION790'][:,j];sets={'new_FP':normal&new,'new_only_FP':normal&new&~old,'removed_FP':normal&old&~new,'shared_FP':normal&old&new,'new_TN':normal&~new}
  errors[h]={}
  for group,ix in groups.items():
   ix=np.intersect1d(ix,d['views']['primary'][0]);errors[h][group]={}
   for name,mask in sets.items():
    takeix=ix[mask[ix]];errors[h][group][name]=dict(rows=len(takeix),weight_mass=float(w[takeix].sum()),raw_margin=ac.quant(all_scores['FUSION790'][takeix,j]-arms['FUSION790']['cuts'][j]),support=ac.quant(d['support'][takeix]),outside_fit_range_count=int(outside[takeix].sum()),context_quantiles=[ac.quant(d['context'][takeix,col]) for col in range(8)],block_shapley={block:ac.quant(all_shap['FUSION790'][takeix,b,j]) for b,block in enumerate(ac.BLOCKS)})
 result['seed_FP_overlap']={h:{hh:int(np.sum(normal&factor['FUSION790__cut_FUSION790__scale_FUSION790'][:,j]&factor['FUSION790__cut_FUSION790__scale_FUSION790'][:,jj])) for jj,hh in enumerate(HEADS)} for j,h in enumerate(HEADS)}
 artifact=PHASE+'_'+pool
 write(artifact+'_ERROR_GROUPS.json',errors);write(artifact+'_GRADIENT_DIMENSIONS.json',gradient_profiles);write(artifact+'_DETAILS.json',result)
 np.savez(HERE/(artifact+'_DIAGNOSTICS.npz'),uid=np.asarray([r['uid'] for r in d['rows']]),**arrays)
 brief=lambda values:{g:v for g,v in values.items() if g in ['pool','label:0','label:1','protocol:6','protocol:17','scenario:HTTP','scenario:UDP']}
 return dict(rows=n,primary_rows=len(d['views']['primary'][0]),status='PASS',seconds=time.monotonic()-started,forward_checks={name:{k:v[k] for k in ['forward_error','decomposition_error','decomposition_decision_roundoff']} for name,v in result['arms'].items()},input_profile=result['input_profile'],permutation_changes=result['permutation_changes'],seed_FP_overlap=result['seed_FP_overlap'],normal_errors_primary={h:v['pool'] for h,v in errors.items()},artifacts={suffix:dict(sha256=sha(HERE/(artifact+'_'+suffix)),bytes=(HERE/(artifact+'_'+suffix)).stat().st_size) for suffix in ['DETAILS.json','ERROR_GROUPS.json','GRADIENT_DIMENSIONS.json','DIAGNOSTICS.npz']},functional_summary={name:{'attribution':brief(v['attribution']), 'coalitions':{mask:brief(values) for mask,values in v['coalitions'].items()}, 'permutations':{key:brief(value['sensitivity']) for key,value in v['permutations'].items()}} for name,v in result['arms'].items()},c5_factorial={key:brief(values) for key,values in result['c5_factorial'].items()})

def main():
 global PHASE
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['PREFLIGHT','DIAGNOSE'],required=True);PHASE=parser.parse_args().phase;start=time.monotonic()
 c,inputs,context=initialize();k,norm,arms=c.models();profile=fit_profile(c);out={}
 parameters={}
 for name,arm in arms.items():
  parameters[name]={}
  for j,model in enumerate(arm['models']):
   w=model[0].weight.detach().numpy();parts={}
   for b,sl in zip(ac.BLOCKS,ac.SLICES):
    value=w[:,0:8] if arm['dimension']==8 and b=='CONTEXT8' else w[:,0:0] if arm['dimension']==8 else w[:,sl]
    parts[b]=dict(columns=value.shape[1],nonzero_weights=int(np.count_nonzero(value)),frobenius_norm=float(np.linalg.norm(value)),rms=float(np.sqrt(np.mean(value**2))) if value.size else None)
   if name=='FUSION790':parts['delta_from_old_782']=float(np.linalg.norm(w[:,:782]-arms['OLD782']['models'][j][0].weight.detach().numpy()))
   parameters[name][HEADS[j]]=parts
 write('PARAMETER_AUDIT.json',parameters)
 if PHASE=='PREFLIGHT':
  old_here=context.HERE;context.HERE=HERE
  try:context.build(small=True)
  finally:context.HERE=old_here
  full=inputs.edge();from preflight_encoder import run
  encoder=run(full,norm);del full;gc.collect()
 for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
  d=data_load(pool,c,inputs,context,small=PHASE=='PREFLIGHT');out[pool]=evaluate(pool,d,c,k,norm,arms,profile);del d;gc.collect()
 result=dict(status='PASS',phase=PHASE,seconds=time.monotonic()-start,pools=out,training=False,threshold_fitting=False,model_selection=False)
 if PHASE=='PREFLIGHT':
  # Keep diagnostic performance on synthetic slices out of the delivery summary.
  result['pools']={pool:{key:v[key] for key in ['rows','status','forward_checks','artifacts']} for pool,v in out.items()};result['real_encoder_distance']=encoder
 write(PHASE+'_RESULT.json',result);progress(PHASE+'_COMPLETE',1,1)

if __name__=='__main__':
 try:main()
 except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=type(e).__name__+':'+str(e),traceback=traceback.format_exc()));raise
