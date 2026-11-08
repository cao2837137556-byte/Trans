"""Real-input engineering qualification only. Never promote pilot scores."""
import argparse, gc, hashlib, importlib.util, json, os, shutil, sys, time, traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
EVAL=PROJECT/'runs/device_context_evaluation_v1_20261105'
TRAIN=PROJECT/'runs/device_context_head_training_v2_20261105'
SOURCE=PROJECT/'runs/device_context_training_v2_20261105'

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(name,v):
 p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):write((os.environ.get('BASELINE_METHOD','PREFLIGHT'))+'_DETAIL.json',dict(detail=stage,done=int(done),total=int(total),updated_unix=time.time(),**kw))
def dependencies():
 pins=read(HERE/'INPUT_PINS.json')
 for n,h in pins.items():assert sha(PROJECT/n)==h,'DEPENDENCY_SHA:'+n
 for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,'PACKAGE_SHA:'+n
 return len(pins)
def choose(rows,indices,n):
 """Deterministic UID-stratified engineering slice; independent of any score."""
 import numpy as np
 groups={}
 for i in indices:
  r=rows[int(i)];key=tuple(str(r.get(k,'')) for k in ('label','device','protocol'))
  groups.setdefault(key,[]).append(int(i))
 lists=[sorted(v,key=lambda i:rows[i]['uid']) for _,v in sorted(groups.items())]
 out=[];j=0
 while len(out)<min(n,len(indices)):
  for v in lists:
   if j<len(v):out.append(v[j])
   if len(out)==min(n,len(indices)):break
  j+=1
 return np.asarray(out,dtype=np.int64)
def bootstrap():
 sys.path.insert(0,str(EVAL));sys.path.insert(0,str(TRAIN))
 import common as c
 c.progress=progress
 import torch
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
 return c
def pipeline():
 import numpy as np
 c=bootstrap();c.verify();k,norm,arms=c.models();del arms;gc.collect()
 import inputs
 inputs.progress=progress
 rows,z,q,ctx=inputs.source_role('LEARN')
 fit=np.load(SOURCE/'metadata/FIT.npy');cal=np.load(SOURCE/'metadata/CAL.npy')
 assert len(fit)==617908 and len(cal)==148819 and not set(fit)&set(cal)
 assert len(set(r['uid'] for r in rows))==len(rows)==766727
 spec=read(TRAIN/'TRAINING_SPEC_FROZEN.json')
 for role,indices in [('FIT',fit),('CAL',cal)]:
  assert k.c.uid_sha(rows[int(i)]['uid'] for i in indices)==spec['data_identity'][role]['uid_sha256'],'SOURCE_ROLE_UID'
  assert all(rows[int(i)]['fit_role']==role and rows[int(i)]['partition']=='LEARN' for i in indices),'SOURCE_ROLE_CONTENT'
 fi=choose(rows,fit,1024);cn=cal[[int(rows[int(i)]['label'])==0 for i in cal]];ci=choose(rows,cn,1024)
 def materialize(ix):return k.normalized((z,c.extra_normalized(ctx)),q,ix,norm,790).numpy().copy()
 data=dict(fit_x=materialize(fi),fit_y=np.asarray([int(rows[i]['label']) for i in fi]),cal_x=materialize(ci),cal_w=k.class_weights([rows[i] for i in ci]),fit_uid=np.asarray([rows[i]['uid'] for i in fi]),cal_uid=np.asarray([rows[i]['uid'] for i in ci]))
 assert set(data['fit_y'])=={0,1} and not set(data['fit_uid'])&set(data['cal_uid'])
 write('CAL_ROWS.json',[rows[i] for i in ci]);del rows,z,q,ctx;gc.collect()
 for pool in ('CIC_DEV','UNSW_DEV'):
  rr,zz,qq,cc=inputs.source_role(pool);ix=choose(rr,np.arange(len(rr)),64)
  data[pool+'_x']=k.normalized((zz,c.extra_normalized(cc)),qq,ix,norm,790).numpy().copy();data[pool+'_uid']=np.asarray([rr[i]['uid'] for i in ix])
  del rr,zz,qq,cc;gc.collect()
 progress('REAL_CAUSAL_DECODE')
 import edge_context as ec
 isolated=HERE/'causal';isolated.mkdir(exist_ok=True)
 for n in ('EDGE_CARD.json','stream_core.py'):shutil.copyfile(EVAL/n,isolated/n)
 ec.HERE=isolated;ec.write=lambda n,v:write('causal/'+n,v);ec.progress=progress
 causal=ec.build(small=True)
 d=inputs.edge()
 import preflight_encoder as pe
 pe.progress=progress;encoded=pe.run(d,norm)
 ix,cc=ec.join(d['rows'],small=True)
 data['EDGE_x']=k.normalized((d['z'][ix],cc),d['q'][ix],np.arange(len(ix)),norm,790).numpy().copy();data['EDGE_uid']=np.asarray([d['rows'][i]['uid'] for i in ix])
 for name,x in data.items():
  if name.endswith('_x'):assert x.shape[1]==790 and np.isfinite(x).all()
 np.savez(HERE/'PILOT_INPUTS.npz',**data)
 return dict(status='PASS',scope='ENGINEERING_ONLY',causal=causal,encoder=encoded,input_sha256=sha(HERE/'PILOT_INPUTS.npz'),fit_rows=len(fi),cal_normal_rows=len(ci),target_rows={p:len(data[p+'_x']) for p in ('CIC_DEV','UNSW_DEV','EDGE')},full_training_qualified=False)
def model_factory(name):
 import torch
 torch.manual_seed(27)
 if name=='TabM':
  sys.path.insert(0,str(HERE/'vendor/tabm'));from tabm import TabM
  config=dict(n_num_features=790,cat_cardinalities=[],d_out=1,num_embeddings=None)
  return TabM.make(**config),dict(architecture=config,optimizer='AdamW',lr=.002,weight_decay=.0003,batch=16)
 if name=='ModernNCA':
  sys.path.insert(0,str(HERE/'vendor/modern_nca'));from TALENT.model.models.modernNCA import ModernNCA
  cfg=read(HERE/'vendor/modern_nca/TALENT__configs__default__modernNCA.json')['modernNCA'];config=dict(d_in=790,d_num=790,d_out=2,**cfg['model'])
  return ModernNCA(**config),dict(architecture=config,optimizer='AdamW',**cfg['training'],batch=16)
 assert name=='DisentAD'
 spec=importlib.util.spec_from_file_location('disnet',HERE/'vendor/disent_ad/network__dis_net.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod.DisNet(dim=128,att_dim=1),dict(architecture=dict(dim=128,att_dim=1,num_heads=2,patch_size=1,overlap=0),optimizer='Adam',lr=.0001,weight_decay=0.,batch=4)
def model_run(name):
 import numpy as np
 c=bootstrap();import torch,context_core as k
 assert read(HERE/'PIPELINE_RESULT.json')['status']=='PASS'
 assert sha(HERE/'PILOT_INPUTS.npz')==read(HERE/'PIPELINE_RESULT.json')['input_sha256']
 a=np.load(HERE/'PILOT_INPUTS.npz');x=torch.from_numpy(a['fit_x'].copy());y=torch.from_numpy(a['fit_y'].astype(np.int64));cx=torch.from_numpy(a['cal_x'].copy())
 if name=='DisentAD':x=x[y==0];y=y[y==0]
 model,cfg=model_factory(name);opt=getattr(torch.optim,cfg['optimizer'])(model.parameters(),lr=cfg['lr'],weight_decay=cfg['weight_decay'])
 before={key:v.detach().clone() for key,v in model.state_dict().items()};losses=[];step_times=[]
 def forward(t):
  if name=='TabM':return model(t).squeeze(-1).mean(1)
  if name=='ModernNCA':
   v=model(t,None,x,y,False);return v[:,1]-v[:,0]
  return model(t.unsqueeze(-1))
 for step in range(16):
  model.train();start=time.monotonic();ix=torch.randperm(len(x))[:cfg['batch']];opt.zero_grad(set_to_none=True)
  if name=='TabM':
   out=model(x[ix]).squeeze(-1);loss=torch.nn.functional.binary_cross_entropy_with_logits(out,y[ix,None].float().expand_as(out))
  elif name=='ModernNCA':
   mask=torch.ones(len(x),dtype=torch.bool);mask[ix]=False
   loss=torch.nn.functional.nll_loss(model(x[ix],y[ix],x[mask],y[mask],True),y[ix])
  else:
   rec,dis=model(x[ix].unsqueeze(-1));loss=rec+dis
  assert torch.isfinite(loss),'NONFINITE_LOSS';loss.backward();assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters());opt.step()
  losses.append(float(loss.detach()));step_times.append(time.monotonic()-start);progress(name+'_TRAIN',step+1,16,loss=losses[-1])
 assert any(not torch.equal(before[key],v) for key,v in model.state_dict().items()),'NO_PARAMETER_UPDATE'
 model.eval();folder=HERE/'artifacts'/name;folder.mkdir(parents=True,exist_ok=True)
 np.savez(folder/'checkpoint.npz',**{key:v.detach().numpy() for key,v in model.state_dict().items()})
 score_times={};outputs={}
 with torch.inference_mode():
  for pool,t in [('CAL',cx)]+[(p,torch.from_numpy(a[p+'_x'].copy())) for p in ('CIC_DEV','UNSW_DEV','EDGE')]:
   start=time.monotonic();v=[]
   for b in range(0,len(t),cfg['batch']):
    v.append(forward(t[b:b+cfg['batch']]).numpy());progress(name+'_SCORE_'+pool,min(len(t),b+cfg['batch']),len(t))
   outputs[pool]=np.concatenate(v).astype(np.float64);score_times[pool]=time.monotonic()-start;assert np.isfinite(outputs[pool]).all()
  expected=forward(cx[:4]).clone();saved=np.load(folder/'checkpoint.npz');model.load_state_dict({key:torch.from_numpy(saved[key].copy()) for key in saved.files});actual=forward(cx[:4]);assert torch.equal(expected,actual),'RELOAD_PARITY'
 cut=k.threshold(outputs['CAL'],read(HERE/'CAL_ROWS.json'),.01)
 # Parent threshold may be a scalar only; explicit check protects decision semantics.
 cut=float(cut);fpr=float(np.sum(a['cal_w'][outputs['CAL']>cut]));assert fpr<=.010000000001
 np.savez(folder/'scores.npz',**outputs,**{p+'_uid':a[p+'_uid'] for p in ('CIC_DEV','UNSW_DEV','EDGE')})
 receipt=dict(status='PASS',scope='ENGINEERING_ONLY_NOT_EFFICACY',method=name,config=cfg,seed=27,updates=16,fit_rows=len(x),cal_normal_rows=len(cx),parameters=sum(p.numel() for p in model.parameters()),loss_first=losses[0],loss_last=losses[-1],step_seconds=step_times,score_seconds=score_times,source_cal_cut=cut,source_cal_weighted_fpr=fpr,checkpoint_sha256=sha(folder/'checkpoint.npz'),score_sha256=sha(folder/'scores.npz'),reload_exact=True,full_training_qualified=False,formal_tuning_pending=True)
 if name=='ModernNCA':receipt['scaling_warning']='1024-row retrieval pilot; 617908-row pool requires separate chunking/GPU/resource gate. No linear runtime certification.'
 return receipt
def main():
 phase=argparse.ArgumentParser();phase.add_argument('--phase',required=True);name=phase.parse_args().phase
 start=time.monotonic()
 try:
  dependencies();result=pipeline() if name=='PIPELINE' else model_run(name);dependencies()
  result['seconds']=time.monotonic()-start;write(name+'_RESULT.json',result)
 except Exception as e:
  write(name+'_STOP.json',dict(status='FAIL',error=str(e),traceback=traceback.format_exc(),seconds=time.monotonic()-start));raise
if __name__=='__main__':main()
