"""Author model bodies stay byte-pinned; adaptations are explicit and tested."""
import ast,math,sys,types
from pathlib import Path
from typing import Literal,Optional,Union
import numpy as np
import torch
from torch import nn,Tensor
from pipeline_parent import HERE,model_factory,read

def tabm():
 sys.path.insert(0,str(HERE/'vendor/tabm'))
 from tabm import TabM
 return TabM.make(n_num_features=790,cat_cardinalities=[],d_out=2,num_embeddings=None)
def tabm_score(model,x):return model(x).softmax(-1)[...,1].mean(1)

def tabr(faiss_override=None):
 sys.path.insert(0,str(HERE/'vendor/delu_package'));import delu
 if faiss_override is None:
  sys.path.insert(0,str(HERE/'runtime/faiss'));import faiss,faiss.contrib.torch_utils
 else:faiss=faiss_override
 # Compile the unchanged author AST: exclude only CLI/training orchestration imports.
 env=dict(math=math,nn=nn,torch=torch,F=torch.nn.functional,Tensor=Tensor,Optional=Optional,Union=Union,Literal=Literal,delu=delu,faiss=faiss)
 deep=HERE/'vendor/tabr/lib/deep.py';tree=ast.parse(deep.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_d_out');exec(compile(ast.Module(body=[node],type_ignores=[]),str(deep),'exec'),env)
 env['lib']=types.SimpleNamespace(get_d_out=env['get_d_out'])
 src=HERE/'vendor/tabr/bin/tabr.py';node=next(n for n in ast.parse(src.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Model');exec(compile(ast.Module(body=[node],type_ignores=[]),str(src),'exec'),env)
 cfg=dict(n_num_features=790,n_bin_features=0,cat_cardinalities=[],n_classes=2,num_embeddings=None,d_main=128,d_multiplier=2.,encoder_n_blocks=0,predictor_n_blocks=1,mixer_normalization='auto',context_dropout=.1,dropout0=.1,dropout1=0.,normalization='LayerNorm',activation='ReLU')
 return env['Model'](**cfg),cfg

class ExactTorchIndex:
 """Independent test oracle only. Production TabR uses official FAISS wheel."""
 def __init__(self,d):self.d=d
 def reset(self):pass
 def add(self,x):self.x=x
 def search(self,q,k):
  d=((q[:,None,:]-self.x[None,:,:])**2).sum(-1)
  v,i=torch.topk(d,k,largest=False,sorted=True);return v,i

def slad():
 sys.path.insert(0,str(HERE/'vendor/slad'));from algorithms.slad import SLAD
 # Original training loop stops when cnt > epoch_steps; 15 means exactly 16 updates.
 return SLAD(epochs=1,epoch_steps=15,batch_size=128,device='cpu',verbose=0,random_state=27)

def nca_encode(model,x):
 assert not model.training,'INFERENCE_ONLY'
 if model.num_embeddings is not None:
  x=torch.cat((model.num_embeddings(x[:,:model.d_num]).flatten(1),x[:,model.d_num:]),-1)
 x=model.encoder(x)
 return model.post_encoder(x) if model.n_blocks>0 else x

def nca_chunk_score(model,q,keys,labels,chunk=4096):
 """All candidates included; stable float64 reduction, same +1e-7 as author."""
 assert not model.training and model.d_out==2
 z=nca_encode(model,q);m=torch.full((len(q),),-torch.inf,dtype=torch.float64);den=torch.zeros_like(m);num=torch.zeros((len(q),2),dtype=torch.float64)
 for start in range(0,len(keys),chunk):
  k=torch.from_numpy(np.array(keys[start:start+chunk],dtype=np.float32,copy=True));y=torch.from_numpy(np.array(labels[start:start+chunk],dtype=np.int64,copy=True))
  s=(-torch.cdist(z,k,p=2,compute_mode='use_mm_for_euclid_dist')/model.T).double();new=torch.maximum(m,s.max(1).values);old=torch.exp(m-new);w=torch.exp(s-new[:,None]);den=den*old+w.sum(1);num=num*old[:,None]+w@torch.nn.functional.one_hot(y,2).double();m=new
 return torch.log(num/den[:,None]+1e-7)

def fidelity_checks(faiss_required=False):
 torch.set_num_threads(1);torch.manual_seed(27);results={}
 m=tabm();x=torch.randn(8,790);y=torch.arange(8)%2;v=m(x);assert v.shape==(8,32,2)
 loss=torch.nn.functional.cross_entropy(v.flatten(0,1),y.repeat_interleave(32));manual=torch.stack([torch.nn.functional.cross_entropy(v[:,i],y) for i in range(32)]).mean();assert torch.allclose(loss,manual,atol=1e-7)
 m.eval();a=tabm_score(m,x);b=m(x).softmax(-1)[...,1].mean(1);assert torch.equal(a,b)
 example=torch.tensor([[-100.,3.],[-1.,-1.]]);assert example.mean(1)[0]<example.mean(1)[1] and example.sigmoid().mean(1)[0]>example.sigmoid().mean(1)[1]
 results['TabM']=dict(status='PASS',output_classes=2,loss='per-member CE',ensemble='mean probability',legacy_logit_mean_counterexample=True)
 model,cfg=model_factory('ModernNCA');model.eval();pool=torch.randn(97,790);labels=torch.arange(97)%2;q=torch.randn(5,790)
 with torch.inference_mode():
  keys=nca_encode(model,pool).numpy();ref=model(q,None,pool,labels,False);errs=[]
  for chunk in (16,32,65):errs.append(float((ref-nca_chunk_score(model,q,keys,labels.numpy(),chunk)).abs().max()))
 assert max(errs)<5e-4;results['ModernNCA']=dict(status='PASS',chunk_max_log_probability_errors=errs,tolerance=5e-4,inference_only=True)
 sys.path.insert(0,str(HERE/'vendor/slad'));from algorithms.slad import SLADLoss
 yp=torch.randn(5,10,dtype=torch.float64);yt=torch.randn(5,10,dtype=torch.float64);pp=yp.softmax(1);tt=yt.softmax(1);mid=(pp+tt)/2
 direct=(mid*(2*mid.log()-pp.log_softmax(1)-tt.log_softmax(1))).sum(1)
 err=float((SLADLoss(reduction='none')(yp,yt)-direct).abs().max());assert err<1e-12;results['SLAD']=dict(status='PASS',loss_formula_max_abs_error=err,author_log_softmax_of_probabilities_preserved=True)
 import importlib.util
 path=HERE/'vendor/disent_ad/data_preprocess__load_dataset.py';sp=importlib.util.spec_from_file_location('author_dataset',path);mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod);d=mod.DatasetBuilder(x,1,0,'none');assert torch.equal(torch.stack([d[i]['data'] for i in range(len(x))]),x.unsqueeze(-1));results['DisentAD']=dict(status='PASS',patch_input_exact=True)
 oracle=types.SimpleNamespace(IndexFlatL2=ExactTorchIndex)
 t,cfg=tabr(None if faiss_required else oracle);t.eval();other,_=tabr(oracle);other.load_state_dict(t.state_dict());other.eval()
 args=dict(x_={'num':q},y=None,candidate_x_={'num':pool},candidate_y=labels,context_size=16,is_train=False)
 with torch.inference_mode():err=float((t(**args)-other(**args)).abs().max())
 assert err<2e-5;results['TabR']=dict(status='PASS' if faiss_required else 'NATIVE_FAISS_PENDING',official_class_AST_unchanged=True,faiss_vs_exhaustive_logit_error=err)
 return results
