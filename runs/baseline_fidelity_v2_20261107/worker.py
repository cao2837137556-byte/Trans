"""Fidelity gates, two additional authors' models and source-only scaling."""
import argparse,gc,os,pickle,sys,time,traceback,zipfile
import numpy as np
import torch
from pipeline_parent import HERE,PROJECT,SOURCE,TRAIN,read,write,sha,dependencies,progress,bootstrap,pipeline,model_factory
from adapters import tabm,tabm_score,tabr,slad,fidelity_checks,nca_encode,nca_chunk_score

def install_faiss():
 target=HERE/'runtime/faiss';target.mkdir(parents=True,exist_ok=True)
 for n,s in read(HERE/'ASSETS.json').items():
  p=HERE/'assets'/n;assert p.stat().st_size==s['bytes'] and sha(p)==s['sha256']
  with zipfile.ZipFile(p) as z:
   assert all(not name.startswith('/') and '..' not in name.split('/') for name in z.namelist());z.extractall(target)
 sys.path.insert(0,str(target));import faiss
 faiss.omp_set_num_threads(1);return faiss.__version__

def pilot(name):
 bootstrap();import context_core as k
 pr=read(HERE/'PIPELINE_RESULT.json');assert pr['status']=='PASS' and sha(HERE/'PILOT_INPUTS.npz')==pr['input_sha256']
 a=np.load(HERE/'PILOT_INPUTS.npz');x=torch.from_numpy(a['fit_x'].copy());y=torch.from_numpy(a['fit_y'].astype(np.int64));torch.manual_seed(27)
 folder=HERE/'artifacts'/name;folder.mkdir(parents=True,exist_ok=True);start=time.monotonic();times=[]
 if name=='SLAD':
  model=slad();progress('SLAD_AUTHOR_FIT',0,1);model.fit(x[y==0].numpy());cfg=dict(epochs=1,epoch_steps=15,actual_steps=16,n_ensemble=20,distribution_size=10,n_unified_features=128,hidden_dims=100,normal_fit_rows=int((y==0).sum()),normalization='frozen shared790 source transform')
  assert all(torch.isfinite(v).all() for v in model.net.state_dict().values())
  def score(t):return np.asarray(model.decision_function(t.numpy()),dtype=np.float64)
 else:
  model=tabm() if name=='TabM' else tabr()[0];cfg=dict(updates=16,batch=16,lr=.002 if name=='TabM' else .0001,weight_decay=.0003 if name=='TabM' else 0.,score='mean_softmax_positive_probability' if name=='TabM' else 'native_binary_logit',tabr_context_size=96 if name=='TabR' else None)
  before={n:v.detach().clone() for n,v in model.state_dict().items()};opt=torch.optim.AdamW(model.parameters(),lr=cfg['lr'],weight_decay=cfg['weight_decay'])
  for step in range(16):
   t=time.monotonic();model.train();idx=torch.randperm(len(x))[:16];opt.zero_grad(set_to_none=True)
   if name=='TabM':loss=torch.nn.functional.cross_entropy(model(x[idx]).flatten(0,1),y[idx].repeat_interleave(32))
   else:
    keep=torch.ones(len(x),dtype=torch.bool);keep[idx]=False
    v=model(x_={'num':x[idx]},y=y[idx],candidate_x_={'num':x[keep]},candidate_y=y[keep],context_size=96,is_train=True).flatten();loss=torch.nn.functional.binary_cross_entropy_with_logits(v,y[idx].float())
   assert torch.isfinite(loss);loss.backward();assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters());opt.step();times.append(time.monotonic()-t);progress(name+'_TRAIN',step+1,16)
  assert any(not torch.equal(before[n],v) for n,v in model.state_dict().items());model.eval()
  def score(t):
   with torch.inference_mode():
    vv=[]
    for start in range(0,len(t),16):
     b=t[start:start+16];v=tabm_score(model,b) if name=='TabM' else model(x_={'num':b},y=None,candidate_x_={'num':x},candidate_y=y,context_size=96,is_train=False).flatten();vv.append(v.numpy())
    return np.concatenate(vv).astype(np.float64)
 train_seconds=time.monotonic()-start;out={};score_seconds={}
 for pool in ('CAL','CIC_DEV','UNSW_DEV','EDGE'):
  t=time.monotonic();progress(name+'_SCORE_'+pool);out[pool]=score(torch.from_numpy(a['cal_x' if pool=='CAL' else pool+'_x'].copy()));assert np.isfinite(out[pool]).all();score_seconds[pool]=time.monotonic()-t
 cut=k.threshold(out['CAL'],read(HERE/'CAL_ROWS.json'),.01);fpr=float(a['cal_w'][out['CAL']>cut].sum());assert fpr<=.010000000001
 probe=torch.from_numpy(a['cal_x'][:8].copy());expected=score(probe)
 if name=='SLAD':
  # Only our own freshly written, SHA-checked object is loaded; never external pickle.
  path=folder/'generated_model.pkl';path.write_bytes(pickle.dumps(model,protocol=4));digest=sha(path);assert sha(path)==digest;model=pickle.loads(path.read_bytes())
 else:
  path=folder/'checkpoint.npz';np.savez(path,**{n:v.detach().numpy() for n,v in model.state_dict().items()});saved=np.load(path);model.load_state_dict({n:torch.from_numpy(saved[n].copy()) for n in saved.files})
 assert np.array_equal(expected,score(probe)),'RELOAD_SCORE_PARITY'
 np.savez(folder/'scores.npz',**out,**{p+'_uid':a[p+'_uid'] for p in ('CIC_DEV','UNSW_DEV','EDGE')})
 return dict(status='PASS',scope='ENGINEERING_FIDELITY_NOT_PAPER_BENCHMARK_REPRODUCTION',method=name,config=cfg,train_seconds=train_seconds,step_seconds=times,score_seconds=score_seconds,reload_exact=True,source_cal_cut=cut,source_cal_weighted_fpr=fpr,checkpoint_sha256=sha(path),score_sha256=sha(folder/'scores.npz'),official_benchmark_replication_pending=True,formal_training_pending=True)

def nca_scale():
 c=bootstrap();import inputs,context_core as k
 model,_=model_factory('ModernNCA');old=PROJECT/'runs/baseline_qualification_v1_20261107';path=old/'artifacts/ModernNCA/checkpoint.npz';assert sha(path)==read(HERE/'SPEC.json')['old_nca_checkpoint_sha256'];a=np.load(path);model.load_state_dict({n:torch.from_numpy(a[n].copy()) for n in a.files});model.eval()
 pilot_data=np.load(HERE/'PILOT_INPUTS.npz');px=torch.from_numpy(pilot_data['fit_x'].copy());py=torch.from_numpy(pilot_data['fit_y'].astype(np.int64));cq=torch.from_numpy(pilot_data['cal_x'][:8].copy())
 with torch.inference_mode():
  pk=np.concatenate([nca_encode(model,b).numpy() for b in px.split(64)])
  ref=model(cq,None,px,py,False);errors={str(ch):float((ref-nca_chunk_score(model,cq,pk,py.numpy(),ch)).abs().max()) for ch in (64,128,511)}
 assert max(errors.values())<5e-4,'REAL_NCA_CHUNK_PARITY'
 old_cut=read(HERE/'SPEC.json')['old_nca_cut']
 with torch.inference_mode():
  chunked=nca_chunk_score(model,cq,pk,py.numpy(),128)
  assert torch.equal(ref[:,1]-ref[:,0]>old_cut,chunked[:,1]-chunked[:,0]>old_cut),'REAL_NCA_DECISION_PARITY'
 rows,z,q,raw=inputs.source_role('LEARN');fit=np.load(SOURCE/'metadata/FIT.npy');spec=read(TRAIN/'TRAINING_SPEC_FROZEN.json');assert k.c.uid_sha(rows[int(i)]['uid'] for i in fit)==spec['data_identity']['FIT']['uid_sha256'] and len(fit)==617908
 _,norm,arms=c.models();del arms;gc.collect();folder=HERE/'artifacts/NCA_SCALE';folder.mkdir(parents=True,exist_ok=True)
 keys=np.lib.format.open_memmap(folder/'FIT_keys.npy',mode='w+',dtype=np.float32,shape=(len(fit),128));labels=np.asarray([int(rows[int(i)]['label']) for i in fit],dtype=np.int64);np.save(folder/'FIT_labels.npy',labels)
 start=time.monotonic();forecast=None
 with torch.inference_mode():
  for offset in range(0,len(fit),64):
   ix=fit[offset:offset+64];xx=k.normalized((z[ix],c.extra_normalized(raw[ix])),q[ix],np.arange(len(ix)),norm,790);keys[offset:offset+len(ix)]=nca_encode(model,xx).numpy()
   if offset==4032:
    forecast=(time.monotonic()-start)/4096*len(fit)*1.5;write('NCA_FORECAST.json',dict(source_rows=len(fit),seconds_conservative=forecast,cap_seconds=1500))
    if forecast>1500:
     keys.flush();return dict(status='NEEDS_RESOURCES',error='FULL_POOL_ENCODING_FORECAST_EXCEEDS_PHASE_BUDGET',forecast_seconds=forecast,real_parity_errors=errors,full_pool_completed=False)
   if offset%1024==0:progress('NCA_FULL_FIT_KEY_ENCODING',offset,len(fit))
  keys.flush();encoding_seconds=time.monotonic()-start;start=time.monotonic();scores=nca_chunk_score(model,cq,keys,labels,4096);assert torch.isfinite(scores).all();score_seconds=time.monotonic()-start
 np.save(folder/'source_cal8_log_prob.npy',scores.numpy())
 return dict(status='PASS',scope='SOURCE_ONLY_INFERENCE_SCALING',real_parity_errors=errors,full_pool_completed=True,source_fit_rows=len(fit),all_candidates_included=True,encoding_seconds=encoding_seconds,cal8_score_seconds=score_seconds,key_bytes=(folder/'FIT_keys.npy').stat().st_size,key_sha256=sha(folder/'FIT_keys.npy'),labels_sha256=sha(folder/'FIT_labels.npy'),forecast_seconds=forecast,training_gradient_chunking_qualified=False,full_training_pending=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True);phase=p.parse_args().phase;start=time.monotonic()
 try:
  dependencies();torch.set_num_threads(1)
  if phase=='PIPELINE':result=pipeline()
  elif phase=='FIDELITY':version=install_faiss();result=dict(status='PASS',faiss_version=version,checks=fidelity_checks(True),official_benchmark_replication_pending=True)
  elif phase=='NCA_SCALE':result=nca_scale()
  else:
   if phase=='TabR':install_faiss()
   result=pilot(phase)
  dependencies();result['seconds']=time.monotonic()-start;write(phase+'_RESULT.json',result)
 except Exception as e:write(phase+'_STOP.json',dict(status='FAIL',error=str(e),traceback=traceback.format_exc(),seconds=time.monotonic()-start));raise
if __name__=='__main__':main()
