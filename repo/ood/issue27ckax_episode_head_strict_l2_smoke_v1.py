"""CKAX paired head test on immutable CKAW episode features (no review band)."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path: sys.path.insert(0, str(OOD))
import issue27cko_mechanism_frontend_v1 as cko
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao
import issue27ckaw_canonical_interaction_episode_frontend_v1 as ckaw

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception as exc: raise RuntimeError("torch required") from exc

ISSUE="issue27ckax_episode_head_strict_l2_smoke_v1_2026-07-10"
ROOT=cko.ROOT; OUT_BASE=ROOT/"runs"/ISSUE
CKAW=ROOT/"runs"/"issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10_local_150k"
HELD=["iotsim-stream-consumer","iotsim-hydraulic-system","domotic-monitor","combined-cycle","iotsim-ip-camera-street"]
EVAL={"ood_val":"select","ood_stress":"select","future_query":"select","sealed_final_ood":"all","sealed_final_attack":"all"}

class Cache:
 def __init__(self, root:Path, plan_path:str=""):
  plan=Path(plan_path) if plan_path else root/"episode_source_plan.csv"
  self.plan={r.source_group:r.source_cache_key for r in pd.read_csv(plan).itertuples()}; self.root=root/"canonical_episode_cache"; self.data={}
 def get(self,source:str,index:int):
  if source not in self.plan:return None
  if source not in self.data:
   p=np.load(self.root/f"{self.plan[source]}.npz"); self.data[source]={int(i):p["features"][n] for n,i in enumerate(p["recorded_index"])}
  return self.data[source].get(int(index))

class Net(nn.Module):
 def __init__(self,d:int):
  super().__init__(); self.m=nn.Sequential(nn.Linear(d,96),nn.LayerNorm(96),nn.GELU(),nn.Dropout(.15),nn.Linear(96,32),nn.GELU(),nn.Linear(32,2))
 def forward(self,x):return self.m(x)

def rows(cache,frames,role,phase,held,include,cap=4000):
 idx=ckao.role_indices_filtered(frames,role,phase,cap,include=("device_family",held) if include else None,exclude=None if include else ("device_family",held))
 keep=[]; xs=[]
 for i in idx:
  r=frames[role].iloc[int(i)]; x=cache.get(str(r.get("source_group","")),int(r.get("recorded_index",-1)))
  if x is not None: keep.append(int(i)); xs.append(x)
 return np.asarray(keep,dtype=np.int64),np.asarray(xs,dtype=np.float32).reshape((-1,len(ckaw.FEATURE_NAMES)))

def fit_mlp(x,y):
 torch.manual_seed(27); m=Net(x.shape[1]); opt=torch.optim.AdamW(m.parameters(),lr=2e-3,weight_decay=1e-3)
 xt=torch.from_numpy(x); yt=torch.from_numpy(y); w=torch.tensor([1.,max(1.,float((y==0).sum())/max(1,(y==1).sum()))],dtype=torch.float32)
 for _ in range(100): opt.zero_grad(); loss=F.cross_entropy(m(xt),yt,weight=w); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),5.);opt.step()
 m.eval(); return m

def score(model,x,kind):
 if kind=="histgb":return model.predict_proba(x)[:,1]
 with torch.no_grad():return torch.softmax(model(torch.from_numpy(x)),1)[:,1].numpy()

def run(a):
 out=OUT_BASE if not a.run_tag else ROOT/"runs"/f"{ISSUE}_{a.run_tag}";out.mkdir(parents=True,exist_ok=True); started=time.time()
 cache=Cache(Path(a.cache_root),a.plan_path); _,frames,audit,_=cko.load_role_inputs(False); ckao.add_family_columns(frames); metrics=[]; train_audit=[]
 for held in [x.strip() for x in a.held_values.split(",") if x.strip()]:
  parts=[]; ys=[]
  for role,label in [("support_train",1),("id_calib",0),("ood_val",0),("ood_stress",0)]:
   idx,x=rows(cache,frames,role,"fit",held,False,a.train_cap if role!="support_train" else cko.FULL_CAP); parts.append(x);ys.append(np.full(len(x),label));train_audit.append({"held":held,"role":role,"rows":len(x),"phase":"fit"})
  valid=[n for n,p in enumerate(parts) if len(p)]
  if not valid: raise RuntimeError(f"{held}: no legal cached fit rows")
  x=np.vstack([parts[n] for n in valid]);y=np.concatenate([ys[n] for n in valid]); mu=x.mean(0);sd=x.std(0);sd[sd<1e-6]=1.;z=np.nan_to_num((x-mu)/sd).astype(np.float32)
  available={"episode_histgb":HistGradientBoostingClassifier(max_iter=180,max_leaf_nodes=31,l2_regularization=1.).fit(z,y),"episode_mlp":fit_mlp(z,y)}
  models={name:model for name,model in available.items() if name in set(a.candidates.split(","))}
  select=[]
  for role in ["id_calib","ood_val","ood_stress"]:
   _,v=rows(cache,frames,role,"select",held,False,a.eval_cap)
   if len(v): select.append(np.nan_to_num((v-mu)/sd).astype(np.float32))
  if not select: raise RuntimeError(f"{held}: no legal cached select rows")
  for name,model in models.items():
   thr=float(np.quantile(np.concatenate([score(model,v,name.split("_")[1]) for v in select]),.99))
   for role,phase in EVAL.items():
    idx,v=rows(cache,frames,role,phase,held,True,a.eval_cap); p=score(model,np.nan_to_num((v-mu)/sd).astype(np.float32),name.split("_")[1]) if len(v) else np.array([])
    metrics.append({"candidate":name,"held_value":held,"role":role,"rows":len(p),"hard_alarm_rate":float(np.mean(p>=thr)) if len(p) else np.nan,"mean_attack_score":float(np.mean(p)) if len(p) else np.nan,"threshold":thr,"review_rate":0.,"report_only":role.startswith("sealed") or role=="future_query"})
 for path,data in [("metrics.csv",metrics),("train_audit.csv",train_audit)]:pd.DataFrame(data).to_csv(out/path,index=False)
 lines=[f"# {ISSUE}","","Strict held-family smoke; P0 hard-only (review=0).",""]
 lines += ["| candidate | held | role | rows | hard | mean score |","|---|---|---|---:|---:|---:|"]
 for r in metrics: lines.append(f"| {r['candidate']} | {r['held_value']} | {r['role']} | {r['rows']} | {r['hard_alarm_rate']:.4f} | {r['mean_attack_score']:.4f} |")
 (out/"codex_readout.md").write_text("\n".join(lines)+"\n");(out/"run_spec.json").write_text(json.dumps({"held":a.held_values,"train_cap":a.train_cap,"eval_cap":a.eval_cap,"cache":a.cache_root,"report_used_for_fit_or_threshold":False,"raw_label_column_read_by_frontend":False,"seconds":time.time()-started},indent=2));print(json.dumps({"out":str(out),"rows":len(metrics)}))
def main():
 p=argparse.ArgumentParser();p.add_argument("--cache-root",default=str(CKAW));p.add_argument("--plan-path",default="");p.add_argument("--held-values",default=','.join(HELD));p.add_argument("--train-cap",type=int,default=4000);p.add_argument("--eval-cap",type=int,default=3000);p.add_argument("--candidates",default="episode_histgb,episode_mlp");p.add_argument("--run-tag",default="local_150k");run(p.parse_args())
if __name__=="__main__":
 import argparse;main()
