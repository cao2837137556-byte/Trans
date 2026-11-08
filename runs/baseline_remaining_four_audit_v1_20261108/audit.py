import sys,json,hashlib,types
from pathlib import Path
import torch
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'baseline_author_defaults_v1_20261108'
sys.path.insert(0,str(OLD));import adapters,pipeline_parent as pp
torch.set_num_threads(1);torch.manual_seed(27)
results={}
m=adapters.tabm();x=torch.randn(4,790);y=torch.tensor([0,1,0,1]);v=m(x);loss=torch.nn.functional.cross_entropy(v.flatten(0,1),y.repeat_interleave(32));loss.backward()
results['TabM']=dict(shape=list(v.shape),finite_loss=bool(torch.isfinite(loss)),parameters=sum(p.numel() for p in m.parameters()),stop_rule='author validation accuracy patience16; clip norm1; group-disjoint source validation still required')
m,cfg=adapters.tabr(types.SimpleNamespace(IndexFlatL2=adapters.ExactTorchIndex));cfg.update(d_main=265,context_dropout=.38920071545944357,dropout0=.38852797479169876)
m=type(m)(**cfg);q=torch.randn(4,790);pool=torch.randn(32,790);labels=torch.arange(32)%2
v=m(x_={'num':q},y=y,candidate_x_={'num':pool},candidate_y=labels,context_size=16,is_train=True);loss=torch.nn.functional.binary_cross_entropy_with_logits(v.flatten(),y.float());loss.backward()
results['TabR']=dict(constructor_and_backward=True,shape=list(v.shape),finite_loss=bool(torch.isfinite(loss)),small_pool_oracle_only=True,archived_default_config_binding='mixer_dropout -> context_dropout plausible from current code but historical rename evidence not found; not yet certified',production_context_size=96)
m,cfg=pp.model_factory('ModernNCA');shapes={}
def hook(module,args,out):shapes['periodic']=list(out.shape)
h=m.num_embeddings[0].register_forward_hook(hook);pool=torch.randn(64,790);labels=torch.arange(64)%2
loss=torch.nn.functional.nll_loss(m(pool[:4],labels[:4],pool[4:],labels[4:],True),labels[:4]);loss.backward();h.remove()
n=int((617908-512)*.5)
results['ModernNCA']=dict(small_pool_backward=True,observed_periodic_shape=shapes['periodic'],sampled_full_candidates=n,float32_periodic_concat_gib=n*790*154*4/2**30,float32_embedding_output_gib=n*790*34*4/2**30,scope='individual tensor sizes, not total peak; full backward NOT qualified; float64 doubles these values')
m,cfg=pp.model_factory('DisentAD');x=torch.randn(2,790,1);r,d=m(x);(r+d).backward();m.eval()
with torch.no_grad():score=m(x)
results['DisentAD']=dict(patch1_dim128_forward_backward=True,score_shape=list(score.shape),finite_scores=bool(torch.isfinite(score).all()),selection='lowest mean training loss checkpoint; never best target test AP',batch512_single_attention_gib=512*2*790*790*4/2**30,scope='attention tensor only; full adapted epoch pending')
(HERE/'AUDIT.json').write_text(json.dumps(dict(status='LOCAL_REVIEW_COMPLETE_NOT_HPC_RELEASE',fixed_portfolio=['TabM','TabR','DisentAD','ModernNCA','SLAD','DTE-C','CatBoost'],methods=results),indent=2))
print(json.dumps(results,indent=2))
