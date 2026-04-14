from __future__ import annotations
import argparse, json, os, random, sys
from datetime import datetime
from pathlib import Path
import numpy as np, pandas as pd, torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from sklearn.covariance import LedoitWolf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import KitNET as kit
import frontend100_diagload_sweep_no_compact as dsw
import frontend100_latent_scorer_benchmark as lsb
import frontend100_negative_recipe_rescoring as resc

FORMAL_SEEDS=[101,202,303]
BASE_F=0.5


def clean(obj):
    if isinstance(obj, dict): return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    if isinstance(obj, tuple): return [clean(v) for v in obj]
    if isinstance(obj, Path): return str(obj)
    if isinstance(obj, np.ndarray): return [clean(v) for v in obj.tolist()]
    if isinstance(obj, np.generic): return clean(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)): return None
    return obj

def load_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def md_table(df): return resc.md_table(df)
def tag(x): return str(float(x)).replace('.','p')
def set_seed(seed): random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
def parse_seeds(s): return [int(x.strip()) for x in str(s).split(',') if x.strip()]

def norm_rows(x, mn, mx):
    den=np.maximum(np.asarray(mx,float)-np.asarray(mn,float),1e-12)
    z=(np.asarray(x,float)-mn[None,:])/den[None,:]
    return np.clip(np.nan_to_num(z,nan=0.0,posinf=0.0,neginf=0.0),0.0,1.0)

def denorm_rows(z, mn, mx): return np.asarray(z,float)*(mx[None,:]-mn[None,:])+mn[None,:]

def make_negatives(x, mn, mx, std_norm, rng):
    z=norm_rows(x,mn,mx); neg=z.copy(); n,d=neg.shape; counts={'swap':0,'spike':0}
    for i in range(n):
        if bool(rng.random()<0.5) and d>=4:
            counts['swap']+=1; block=max(2,min(d//3,max(2,d//10)))
            lhi=max(1,(d//2)-block+1); rlo=min(max(d//2,0),max(0,d-block)); rhi=max(rlo,d-block)
            ls=int(rng.integers(0,lhi)); rs=int(rng.integers(rlo,rhi+1))
            a=neg[i,ls:ls+block].copy(); b=neg[i,rs:rs+block].copy()
            if block>2: b=np.roll(b,1)
            neg[i,ls:ls+block]=np.clip(0.75*b+0.25*a,0.0,1.0)
            neg[i,rs:rs+block]=np.clip(0.75*a+0.25*b,0.0,1.0)
        else:
            counts['spike']+=1; k=max(1,min(d,int(np.ceil(0.05*d)))); idx=rng.choice(d,size=k,replace=False)
            scale=rng.uniform(1.08,1.35,size=k); sign=rng.choice(np.array([-1.0,1.0]),size=k)
            off=rng.uniform(2.0,3.0,size=k)*sign*std_norm[idx]
            neg[i,idx]=np.clip(neg[i,idx]*scale+off,0.0,1.0)
    return denorm_rows(neg,mn,mx), counts

def extract_latent(model, x, bs, cache=None):
    meta_path=None
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True); meta_path=cache.with_suffix('.json')
        if cache.exists() and meta_path.exists(): return np.load(cache).astype(np.float32), json.loads(meta_path.read_text(encoding='utf-8'))
    h, meta = lsb.extract_global_latent(model, x, batch_size=bs, negative=False)
    h=h.astype(np.float32)
    if cache is not None and meta_path is not None:
        np.save(cache,h); meta_path.write_text(json.dumps(clean(meta), indent=2, ensure_ascii=False), encoding='utf-8')
    return h, meta

def load_bundle(seed, raw_q, locked_dir, latent_cache, x_fit, x_id, bs, run_cache):
    ckpt=locked_dir/f'latent_swap_spike_mix_seed{seed}'/f'kitnet_transformer_latent_contrastive_v1_seed{seed}.ckpt'
    if not ckpt.exists(): raise FileNotFoundError(ckpt)
    model=kit.KitNET.load_checkpoint(ckpt)
    fitf=latent_cache/f'latent_swap_spike_mix_seed{seed}_h_fit.npy'; idf=latent_cache/f'latent_swap_spike_mix_seed{seed}_h_id.npy'
    if fitf.exists() and idf.exists():
        h_fit=np.load(fitf).astype(np.float64); h_id=np.load(idf).astype(np.float64)
    else:
        h_fit,_=extract_latent(model,x_fit,bs,run_cache/f'teacher_{seed}_fit.npy'); h_id,_=extract_latent(model,x_id,bs,run_cache/f'teacher_{seed}_id.npy')
        h_fit=h_fit.astype(np.float64); h_id=h_id.astype(np.float64)
    lw=LedoitWolf().fit(h_fit); mu=lw.location_.astype(np.float64); sigma=lw.covariance_.astype(np.float64)
    raw_id,_=dsw.cholesky_diagload_scores(h_id,mu,sigma,0.0); diag_id,_=dsw.cholesky_diagload_scores(h_id,mu,sigma,BASE_F)
    return {'seed':int(seed),'checkpoint':ckpt,'model':model,'mu':mu,'sigma':sigma,'raw_thr':float(np.quantile(raw_id,raw_q)),'diag_thr':float(np.quantile(diag_id,0.99)),'raw_q':float(raw_q)}

def score_bundle(bundle,h):
    raw,_=dsw.cholesky_diagload_scores(h,bundle['mu'],bundle['sigma'],0.0); diag,_=dsw.cholesky_diagload_scores(h,bundle['mu'],bundle['sigma'],BASE_F)
    raw_n=raw/max(bundle['raw_thr'],1e-12); diag_n=diag/max(bundle['diag_thr'],1e-12)
    return {'raw':raw.astype(np.float64),'diag':diag.astype(np.float64),'raw_n':raw_n.astype(np.float64),'diag_n':diag_n.astype(np.float64),'gate':np.maximum(raw_n,diag_n).astype(np.float64)}

def teacher_scores(bundles, x, bs, cache_dir, key):
    diag=[]; raw=[]; gate=[]
    for b in bundles:
        h,_=extract_latent(b['model'],x,bs,cache_dir/f'{key}_teacher_seed{b["seed"]}.npy'); s=score_bundle(b,h.astype(np.float64))
        diag.append(s['diag_n']); raw.append(s['raw_n']); gate.append(s['gate'])
    return {'diag':np.mean(np.stack(diag,0),0),'raw':np.mean(np.stack(raw,0),0),'gate':np.mean(np.stack(gate,0),0)}

def load_student_model(seed, locked_dir):
    ckpt=locked_dir/f'latent_swap_spike_mix_seed{seed}'/f'kitnet_transformer_latent_contrastive_v1_seed{seed}.ckpt'
    if not ckpt.exists(): raise FileNotFoundError(ckpt)
    return kit.KitNET.load_checkpoint(ckpt), ckpt

class DistillDS(Dataset):
    def __init__(self,x,td,tr,tg):
        self.x=torch.from_numpy(np.asarray(x,np.float32)); self.td=torch.from_numpy(np.asarray(td,np.float32)); self.tr=torch.from_numpy(np.asarray(tr,np.float32)); self.tg=torch.from_numpy(np.asarray(tg,np.float32))
    def __len__(self): return int(self.x.shape[0])
    def __getitem__(self,i): return self.x[i], self.td[i], self.tr[i], self.tg[i]

class DistillHead(nn.Module):
    def __init__(self,d,h):
        super().__init__(); self.norm=nn.LayerNorm(d); self.body=nn.Sequential(nn.Linear(d,h),nn.ReLU(),nn.Linear(h,h),nn.ReLU()); self.diag=nn.Linear(h,1); self.raw=nn.Linear(h,1)
    def forward(self,x):
        z=self.body(self.norm(x)); d=F.softplus(self.diag(z)).squeeze(-1); r=F.softplus(self.raw(z)).squeeze(-1); return d,r,torch.maximum(d,r)

def fit_std(h):
    mean=np.mean(h,0).astype(np.float32); std=np.maximum(np.std(h,0).astype(np.float32),1e-6)
    return {'mean':mean,'std':std}

def apply_std(h, stats): return ((np.asarray(h,np.float32)-stats['mean'][None,:])/stats['std'][None,:]).astype(np.float32)

def split_idx(n_pos,n_neg,val_ratio,rng):
    pos=np.arange(n_pos,dtype=np.int64); neg=np.arange(n_neg,dtype=np.int64)+n_pos; rng.shuffle(pos); rng.shuffle(neg)
    vp=max(1,int(round(val_ratio*n_pos))); vn=max(1,int(round(val_ratio*n_neg)))
    va=np.concatenate([pos[:vp],neg[:vn]]); tr=np.concatenate([pos[vp:],neg[vn:]]); rng.shuffle(tr); rng.shuffle(va); return tr,va

def train_head(train_x, td, tr, tg, batch_size, epochs, lr, wd, hidden_dim, ld, lrw, lg, patience, seed, device):
    rng=np.random.default_rng(seed); n_tot=int(train_x.shape[0]); n_pos=n_tot//2; n_neg=n_tot-n_pos; tr_idx,va_idx=split_idx(n_pos,n_neg,0.1,rng)
    dl_tr=DataLoader(DistillDS(train_x[tr_idx],td[tr_idx],tr[tr_idx],tg[tr_idx]),batch_size=batch_size,shuffle=True); dl_va=DataLoader(DistillDS(train_x[va_idx],td[va_idx],tr[va_idx],tg[va_idx]),batch_size=batch_size,shuffle=False)
    m=DistillHead(int(train_x.shape[1]),hidden_dim).to(device); opt=torch.optim.AdamW(m.parameters(),lr=lr,weight_decay=wd)
    best_state=None; best=float('inf'); bad=0; rows=[]
    def loss_fn(xb,yd,yr,yg):
        pd,pr,pg=m(xb); ld1=F.smooth_l1_loss(torch.log1p(pd),torch.log1p(yd)); lr1=F.smooth_l1_loss(torch.log1p(pr),torch.log1p(yr)); lg1=F.smooth_l1_loss(torch.log1p(pg),torch.log1p(yg)); return ld*ld1+lrw*lr1+lg*lg1,ld1,lr1,lg1
    for ep in range(1,epochs+1):
        m.train(); tr_sum={'loss':0.0,'n':0}
        for xb,yd,yr,yg in dl_tr:
            xb=xb.to(device); yd=yd.to(device); yr=yr.to(device); yg=yg.to(device); opt.zero_grad(); loss,_,_,_=loss_fn(xb,yd,yr,yg); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(),5.0); opt.step(); bsz=int(xb.shape[0]); tr_sum['loss']+=float(loss.item())*bsz; tr_sum['n']+=bsz
        m.eval(); va_sum={'loss':0.0,'n':0}
        with torch.no_grad():
            for xb,yd,yr,yg in dl_va:
                xb=xb.to(device); yd=yd.to(device); yr=yr.to(device); yg=yg.to(device); loss,_,_,_=loss_fn(xb,yd,yr,yg); bsz=int(xb.shape[0]); va_sum['loss']+=float(loss.item())*bsz; va_sum['n']+=bsz
        row={'epoch':ep,'train_loss':tr_sum['loss']/max(tr_sum['n'],1),'val_loss':va_sum['loss']/max(va_sum['n'],1)}; rows.append(row)
        if row['val_loss']+1e-9<best: best=row['val_loss']; best_state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()}; bad=0
        else: bad+=1
        if bad>=patience: break
    if best_state is None: raise RuntimeError('no valid best state')
    m.load_state_dict(best_state); return m,pd.DataFrame(rows)

def predict_head(m,x,batch_size,device):
    x_t=torch.from_numpy(np.asarray(x,np.float32)); outs={'diag':[],'raw':[],'gate':[]}; m.eval()
    with torch.no_grad():
        for st in range(0,len(x_t),batch_size):
            xb=x_t[st:st+batch_size].to(device); d,r,g=m(xb); outs['diag'].append(d.cpu().numpy()); outs['raw'].append(r.cpu().numpy()); outs['gate'].append(g.cpu().numpy())
    return {k:np.concatenate(v,0).astype(np.float64) for k,v in outs.items()}

def corr(a,b):
    a=np.asarray(a,np.float64); b=np.asarray(b,np.float64); m=np.isfinite(a)&np.isfinite(b)
    if int(np.sum(m))<3: return float('nan')
    aa=a[m]; bb=b[m]
    if float(np.std(aa))<1e-12 or float(np.std(bb))<1e-12: return float('nan')
    return float(np.corrcoef(aa,bb)[0,1])

def eval_rows(obj, score_label, role, sid, sood, satt, high_idx, mixed_idx, budget, cal_target, scan_points, extra=None):
    budget=int(min(max(1,budget),len(sood)-1)); ocal=sood[:budget]; oeval=sood[budget:]
    ths=np.unique(np.quantile(np.concatenate([sid,sood,satt]), np.linspace(0.0,1.0,scan_points)))
    def one(pname,thr,src):
        base=resc.eval_threshold(float(thr),sid,sood,oeval,satt,high_idx,mixed_idx)
        out={'object_label':obj,'score_label':score_label,'model_role':role,'policy_name':pname,'threshold':float(thr),'threshold_source':src,'selection_feasible':True,'roc_auc_attack_high_vs_ood_eval':float(resc.compute_auc(oeval,satt[high_idx])),**base}
        if extra: out.update(extra)
        return out
    rows=[one('fixed_id_q0p99',float(np.quantile(sid,0.99)),'id_only_q0p99_of_this_scorer'),one('fixed_id_q0p995',float(np.quantile(sid,0.995)),'id_only_q0p995_of_this_scorer'),one('naive_calibrated_budget5000_target1pct',float(np.quantile(ocal,1.0-cal_target)),'ood_calibration_q99_budget5000')]
    scan=pd.DataFrame([resc.eval_threshold(float(t),sid,sood,oeval,satt,high_idx,mixed_idx) for t in ths]); det50=resc.choose_detection_floor(scan,0.50)
    if det50 is None:
        row={'object_label':obj,'score_label':score_label,'model_role':role,'policy_name':'det_floor_50pct_min_alarm','threshold':float('nan'),'threshold_source':'scan_min_alarm_subject_to_detection_floor','selection_feasible':False,'roc_auc_attack_high_vs_ood_eval':float(resc.compute_auc(oeval,satt[high_idx])),'id_alarm_ratio':float('nan'),'ood_alarm_ratio_full':float('nan'),'ood_alarm_ratio_eval':float('nan'),'attack_detection_all':float('nan'),'attack_detection_high_purity':float('nan'),'attack_detection_boundary':float('nan')}
        if extra:
            row.update(extra)
        rows.append(row)
    else:
        rows.append(one('det_floor_50pct_min_alarm',float(det50['threshold']),'scan_min_alarm_subject_to_detection_floor'))
        if extra: rows[-1].update(extra)
    return rows

def plot_curve(df,out):
    plt.figure(figsize=(6.8,4.5)); plt.plot(df['epoch'],df['train_loss'],marker='o',label='train'); plt.plot(df['epoch'],df['val_loss'],marker='o',label='val'); plt.xlabel('epoch'); plt.ylabel('loss'); plt.title('Distillation training'); plt.grid(alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(out,dpi=180); plt.close()

def plot_tradeoff(df,out,policy):
    sub=df[(df['policy_name']==policy)&(df['selection_feasible'])].copy(); plt.figure(figsize=(8.2,5.6))
    for _,r in sub.iterrows():
        role=str(r.get('model_role','unknown')); label=str(r['object_label']); color='#444444'; marker='x'
        if role=='teacher_ensemble': color,marker='#d62728','D'
        elif role=='single_seed_gate': color,marker='#1f77b4','o'
        elif role=='distilled_head': color,marker='#2ca02c','s'
        plt.scatter(float(r['ood_alarm_ratio_eval']),float(r['attack_detection_high_purity']),color=color,marker=marker,s=95); plt.text(float(r['ood_alarm_ratio_eval'])+0.004,float(r['attack_detection_high_purity'])+0.004,label,fontsize=8)
    plt.xlabel('OOD benign alarm ratio'); plt.ylabel('High-purity attack detection'); plt.title(f'Fixed trade-off ({policy})'); plt.grid(alpha=0.25); plt.tight_layout(); plt.savefig(out,dpi=180); plt.close()

def plot_dist(packs, labels, thr_map, out):
    n=len(labels); fig,axes=plt.subplots(n,1,figsize=(8.8,3.4*n), squeeze=False)
    for i,lbl in enumerate(labels):
        ax=axes[i,0]; d=packs[lbl]; thr=np.log1p(float(thr_map[lbl]))
        ax.hist(np.log1p(d['id']),bins=70,density=True,alpha=0.35,label='ID benign')
        ax.hist(np.log1p(d['ood']),bins=70,density=True,alpha=0.30,label='OOD benign')
        ax.hist(np.log1p(d['attack']),bins=70,density=True,alpha=0.30,label='attack')
        ax.axvline(thr,color='black',linestyle='--',linewidth=1.1,label='fixed thr'); ax.set_title(lbl); ax.set_xlabel('log(1 + score)'); ax.set_ylabel('density'); ax.grid(alpha=0.22); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out,dpi=180); plt.close(fig)

def plot_scatter(t,s,out):
    fig,axes=plt.subplots(1,3,figsize=(13.0,4.1))
    for ax,split in zip(axes,['id','ood','attack']):
        ax.scatter(t[split],s[split],s=9,alpha=0.35); lo=float(min(np.min(t[split]),np.min(s[split]))); hi=float(max(np.max(t[split]),np.max(s[split]))); ax.plot([lo,hi],[lo,hi],color='black',linestyle='--',linewidth=1.0); ax.set_title(split); ax.set_xlabel('teacher gate'); ax.set_ylabel('student gate'); ax.grid(alpha=0.22)
    fig.tight_layout(); fig.savefig(out,dpi=180); plt.close(fig)

def score_stats(x):
    x=np.asarray(x,np.float64); q=np.quantile(x,[0.01,0.05,0.5,0.95,0.99])
    return {'n':int(len(x)),'mean':float(np.mean(x)),'std':float(np.std(x)),'min':float(np.min(x)),'p01':float(q[0]),'p05':float(q[1]),'p50':float(q[2]),'p95':float(q[3]),'p99':float(q[4]),'max':float(np.max(x))}

def main():
    today=datetime.now().strftime('%Y-%m-%d')
    ap=argparse.ArgumentParser(description='Minimal frozen-backbone ensemble distillation.')
    ap.add_argument('--run-tag', default=f'frontend100_ensemble_distillation_v1_{today}')
    ap.add_argument('--source-root', type=Path, default=WORKTREE_ROOT.parents[1]/'KitNET-py-master'/'KitNET-py-master')
    ap.add_argument('--locked-dir', type=Path, default=WORKTREE_ROOT/'runs'/'frontend100_locked_candidate_multiseed_2026-04-06')
    ap.add_argument('--teacher-latent-cache', type=Path, default=WORKTREE_ROOT/'runs'/'frontend100_diagload_gate_multiseed_2026-04-08'/'cache_latents')
    ap.add_argument('--teacher-seeds', default='101,202,303')
    ap.add_argument('--teacher-raw-q', type=float, default=0.999)
    ap.add_argument('--student-seed', type=int, default=202)
    ap.add_argument('--train-samples', type=int, default=8000)
    ap.add_argument('--id-eval-samples', type=int, default=5000)
    ap.add_argument('--ood-limit', type=int, default=0)
    ap.add_argument('--attack-limit', type=int, default=0)
    ap.add_argument('--latent-batch-size', type=int, default=1024)
    ap.add_argument('--distill-batch-size', type=int, default=512)
    ap.add_argument('--epochs', type=int, default=40)
    ap.add_argument('--patience', type=int, default=6)
    ap.add_argument('--distill-lr', type=float, default=1e-3)
    ap.add_argument('--weight-decay', type=float, default=1e-4)
    ap.add_argument('--hidden-dim', type=int, default=256)
    ap.add_argument('--lambda-diag', type=float, default=0.5)
    ap.add_argument('--lambda-raw', type=float, default=0.5)
    ap.add_argument('--lambda-gate', type=float, default=1.0)
    ap.add_argument('--scan-points', type=int, default=901)
    ap.add_argument('--calibration-budget', type=int, default=5000)
    ap.add_argument('--calibration-target', type=float, default=0.01)
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    args=ap.parse_args(); set_seed(args.seed); teacher_seeds=parse_seeds(args.teacher_seeds); device=torch.device(args.device)

    out=WORKTREE_ROOT/'runs'/args.run_tag; out.mkdir(parents=True, exist_ok=True); cache=out/'cache'; cache.mkdir(exist_ok=True); plot_dir=out/'ensemble_distillation_v1_plots'; plot_dir.mkdir(exist_ok=True)
    (out/'command.txt').write_text('python ' + ' '.join(os.sys.argv) + '\n', encoding='utf-8')

    cc=args.source_root/'runs'/'frontend100_crosscapture_stage1_2026-03-25'/'data'; s1=args.source_root/'runs'/'frontend100_joint_eval_stage1_2026-03-31'; s2=args.source_root/'runs'/'frontend100_joint_eval_stage2_2026-04-01'
    stage2=load_json(s2/'attack_manifest_stage2.json'); idx=resc.build_stage2_indices(stage2); high_idx=idx['high']; mixed_idx=idx['mixed']
    x_all=pd.read_csv(cc/'id_source_100.csv', header=None, nrows=args.train_samples+args.id_eval_samples).to_numpy(dtype=np.float64)
    if len(x_all)<args.train_samples+args.id_eval_samples: raise RuntimeError('train csv rows fewer than requested train_samples + id_eval_samples')
    x_fit=x_all[:args.train_samples]; x_id=x_all[args.train_samples:args.train_samples+args.id_eval_samples]; x_ood=pd.read_csv(cc/'ood_benign_source_100.csv', header=None).to_numpy(dtype=np.float64); x_attack=pd.read_csv(s1/'data'/'attack_source_100.csv', header=None).to_numpy(dtype=np.float64)
    if args.ood_limit>0: x_ood=x_ood[:args.ood_limit]
    if args.attack_limit>0:
        x_attack=x_attack[:args.attack_limit]; high_idx=high_idx[high_idx<len(x_attack)]; mixed_idx=mixed_idx[mixed_idx<len(x_attack)]
    if len(high_idx)==0: raise RuntimeError('attack high-purity index set is empty after attack_limit')

    mn=np.min(x_fit,0).astype(np.float64); mx=np.max(x_fit,0).astype(np.float64); std_norm=np.std(norm_rows(x_fit,mn,mx),0).astype(np.float64); rng=np.random.default_rng(args.seed); x_neg, neg_counts = make_negatives(x_fit,mn,mx,std_norm,rng)

    bundles=[load_bundle(seed,args.teacher_raw_q,args.locked_dir,args.teacher_latent_cache,x_fit,x_id,args.latent_batch_size,cache/'teacher_bundle_cache') for seed in teacher_seeds]
    t_fit=teacher_scores(bundles,x_fit,args.latent_batch_size,cache/'teacher_scores','fit'); t_neg=teacher_scores(bundles,x_neg,args.latent_batch_size,cache/'teacher_scores','neg'); t_id=teacher_scores(bundles,x_id,args.latent_batch_size,cache/'teacher_scores','id'); t_ood=teacher_scores(bundles,x_ood,args.latent_batch_size,cache/'teacher_scores','ood'); t_attack=teacher_scores(bundles,x_attack,args.latent_batch_size,cache/'teacher_scores','attack')

    student, student_ckpt=load_student_model(args.student_seed,args.locked_dir)
    h_fit, fit_meta = extract_latent(student,x_fit,args.latent_batch_size,cache/f'student_seed{args.student_seed}_fit.npy'); h_neg,_=extract_latent(student,x_neg,args.latent_batch_size,cache/f'student_seed{args.student_seed}_neg.npy'); h_id,_=extract_latent(student,x_id,args.latent_batch_size,cache/f'student_seed{args.student_seed}_id.npy'); h_ood,_=extract_latent(student,x_ood,args.latent_batch_size,cache/f'student_seed{args.student_seed}_ood.npy'); h_attack,_=extract_latent(student,x_attack,args.latent_batch_size,cache/f'student_seed{args.student_seed}_attack.npy')
    stats=fit_std(h_fit); train_x=np.concatenate([apply_std(h_fit,stats), apply_std(h_neg,stats)],0); train_diag=np.concatenate([t_fit['diag'], t_neg['diag']],0).astype(np.float32); train_raw=np.concatenate([t_fit['raw'], t_neg['raw']],0).astype(np.float32); train_gate=np.concatenate([t_fit['gate'], t_neg['gate']],0).astype(np.float32)
    head, curve = train_head(train_x, train_diag, train_raw, train_gate, args.distill_batch_size, args.epochs, args.distill_lr, args.weight_decay, args.hidden_dim, args.lambda_diag, args.lambda_raw, args.lambda_gate, args.patience, args.seed, device)
    curve.to_csv(out/'ensemble_distillation_v1_training_curve.csv', index=False)
    torch.save({'state_dict':head.state_dict(),'input_dim':int(train_x.shape[1]),'hidden_dim':int(args.hidden_dim),'feature_stats':clean(stats),'student_seed':int(args.student_seed),'teacher_seeds':teacher_seeds,'teacher_raw_q':float(args.teacher_raw_q)}, out/'distilled_gate_head.pt')
    p_id=predict_head(head,apply_std(h_id,stats),args.distill_batch_size,device); p_ood=predict_head(head,apply_std(h_ood,stats),args.distill_batch_size,device); p_attack=predict_head(head,apply_std(h_attack,stats),args.distill_batch_size,device)
    sb=next((b for b in bundles if b['seed']==args.student_seed), None)
    if sb is None: sb=load_bundle(args.student_seed,args.teacher_raw_q,args.locked_dir,args.teacher_latent_cache,x_fit,x_id,args.latent_batch_size,cache/'student_bundle_cache')
    s_id=score_bundle(sb,h_id.astype(np.float64)); s_ood=score_bundle(sb,h_ood.astype(np.float64)); s_attack=score_bundle(sb,h_attack.astype(np.float64))

    teacher_obj=f'teacher_mean_gate_rawq{tag(args.teacher_raw_q)}'; single_obj=f'single_seed{args.student_seed}_gate_rawq{tag(args.teacher_raw_q)}'; distill_obj=f'distilled_head_seed{args.student_seed}'
    rows=[]
    rows.extend(eval_rows(teacher_obj,'teacher_gate','teacher_ensemble',t_id['gate'],t_ood['gate'],t_attack['gate'],high_idx,mixed_idx,args.calibration_budget,args.calibration_target,args.scan_points,{'teacher_seed_count':len(teacher_seeds),'student_seed':args.student_seed}))
    rows.extend(eval_rows(single_obj,'single_seed_gate','single_seed_gate',s_id['gate'],s_ood['gate'],s_attack['gate'],high_idx,mixed_idx,args.calibration_budget,args.calibration_target,args.scan_points,{'teacher_seed_count':1,'student_seed':args.student_seed}))
    rows.extend(eval_rows(distill_obj,'distilled_gate','distilled_head',p_id['gate'],p_ood['gate'],p_attack['gate'],high_idx,mixed_idx,args.calibration_budget,args.calibration_target,args.scan_points,{'teacher_seed_count':len(teacher_seeds),'student_seed':args.student_seed}))
    ref=WORKTREE_ROOT/'runs'/'frontend100_final_candidate_audit_2026-04-08'/'final_candidate_main_table.csv'
    if ref.exists():
        for _,r in pd.read_csv(ref).iterrows():
            obj=str(r['object_label'])
            if obj.startswith('dA fixed_id_q0p99') or obj.startswith('dA fixed_id_q0p995'):
                rows.append({'object_label':obj,'score_label':'reference','model_role':'reference','policy_name':'fixed_id_q0p99' if 'q0p995' not in obj else 'fixed_id_q0p995','threshold':float('nan'),'threshold_source':str(r.get('note','reference')),'selection_feasible':True,'roc_auc_attack_high_vs_ood_eval':float(r['roc_auc']),'id_alarm_ratio':float(r['id_alarm']),'ood_alarm_ratio_full':float(r['ood_alarm']),'ood_alarm_ratio_eval':float(r['ood_alarm']),'attack_detection_all':float(r['high_purity_detection']),'attack_detection_high_purity':float(r['high_purity_detection']),'attack_detection_boundary':float('nan'),'teacher_seed_count':0,'student_seed':args.student_seed})
    res=pd.DataFrame(rows); res.to_csv(out/'ensemble_distillation_v1_results.csv', index=False); res.to_csv(out/'results.csv', index=False)
    corr_df=pd.DataFrame([{'split':'id','pearson_gate':corr(t_id['gate'],p_id['gate'])},{'split':'ood','pearson_gate':corr(t_ood['gate'],p_ood['gate'])},{'split':'attack','pearson_gate':corr(t_attack['gate'],p_attack['gate'])}]); corr_df.to_csv(out/'ensemble_distillation_v1_teacher_student_corr.csv', index=False)
    stat_rows=[]
    for label,pack in [(teacher_obj,t_id['gate']),(single_obj,s_id['gate']),(distill_obj,p_id['gate'])]: stat_rows.append({'label':label,'split':'id',**score_stats(pack)})
    for label,pack in [(teacher_obj,t_ood['gate']),(single_obj,s_ood['gate']),(distill_obj,p_ood['gate'])]: stat_rows.append({'label':label,'split':'ood',**score_stats(pack)})
    for label,pack in [(teacher_obj,t_attack['gate']),(single_obj,s_attack['gate']),(distill_obj,p_attack['gate'])]: stat_rows.append({'label':label,'split':'attack',**score_stats(pack)})
    pd.DataFrame(stat_rows).to_csv(out/'ensemble_distillation_v1_score_stats.csv', index=False)

    plot_curve(curve, plot_dir/'training_curve.png'); plot_tradeoff(res, plot_dir/'fixed_tradeoff_q99.png', 'fixed_id_q0p99'); plot_tradeoff(res, plot_dir/'fixed_tradeoff_q995.png', 'fixed_id_q0p995')
    packs={teacher_obj:{'id':t_id['gate'],'ood':t_ood['gate'],'attack':t_attack['gate']}, single_obj:{'id':s_id['gate'],'ood':s_ood['gate'],'attack':s_attack['gate']}, distill_obj:{'id':p_id['gate'],'ood':p_ood['gate'],'attack':p_attack['gate']}}
    q995={k:float(np.quantile(v['id'],0.995)) for k,v in packs.items()}; plot_dist(packs,[teacher_obj,single_obj,distill_obj],q995,plot_dir/'score_distribution_q995.png'); plot_scatter({'id':t_id['gate'],'ood':t_ood['gate'],'attack':t_attack['gate']},{'id':p_id['gate'],'ood':p_ood['gate'],'attack':p_attack['gate']},plot_dir/'teacher_vs_student_gate_scatter.png')

    show=['object_label','model_role','policy_name','ood_alarm_ratio_eval','attack_detection_high_purity','id_alarm_ratio','roc_auc_attack_high_vs_ood_eval']; (out/'ensemble_distillation_v1_results.md').write_text('# Ensemble Distillation v1 Results\n\n'+md_table(res[show]), encoding='utf-8')
    def gv(obj,pol,col):
        row=res[(res['object_label']==obj)&(res['policy_name']==pol)]
        return float('nan') if row.empty else float(row.iloc[0][col])
    summary='\n'.join([
        '# Ensemble Distillation v1 Summary','',
        '- Goal: distill the 3-seed covariance-aware gate teacher into a single-checkpoint scorer head.',
        '- Scope: backbone frozen; only the dual-branch latent scorer head is trained.',
        f'- Teacher seeds: `{teacher_seeds}`; student seed: `{args.student_seed}`; teacher raw q: `{args.teacher_raw_q}`.',
        f'- Synthetic negatives: `latent_swap_spike_mix_aligned_raw_generator`, counts `{neg_counts}`.','',
        '## Fixed ID q0.99',
        f'- Teacher: alarm={gv(teacher_obj,"fixed_id_q0p99","ood_alarm_ratio_eval"):.4f}, det={gv(teacher_obj,"fixed_id_q0p99","attack_detection_high_purity"):.4f}.',
        f'- Single-seed gate: alarm={gv(single_obj,"fixed_id_q0p99","ood_alarm_ratio_eval"):.4f}, det={gv(single_obj,"fixed_id_q0p99","attack_detection_high_purity"):.4f}.',
        f'- Distilled head: alarm={gv(distill_obj,"fixed_id_q0p99","ood_alarm_ratio_eval"):.4f}, det={gv(distill_obj,"fixed_id_q0p99","attack_detection_high_purity"):.4f}.','',
        '## Fixed ID q0.995',
        f'- Teacher: alarm={gv(teacher_obj,"fixed_id_q0p995","ood_alarm_ratio_eval"):.4f}, det={gv(teacher_obj,"fixed_id_q0p995","attack_detection_high_purity"):.4f}.',
        f'- Single-seed gate: alarm={gv(single_obj,"fixed_id_q0p995","ood_alarm_ratio_eval"):.4f}, det={gv(single_obj,"fixed_id_q0p995","attack_detection_high_purity"):.4f}.',
        f'- Distilled head: alarm={gv(distill_obj,"fixed_id_q0p995","ood_alarm_ratio_eval"):.4f}, det={gv(distill_obj,"fixed_id_q0p995","attack_detection_high_purity"):.4f}.','',
        '## Teacher-Student Correlation', md_table(corr_df), '',
        '## Next Decision',
        '- If the distilled head closes a meaningful part of the single-seed-to-teacher gap, promote this branch.',
        '- If it fails clearly, stop changing scorers and move to joint fine-tuning or stop this line.'
    ]) + '\n'
    (out/'ensemble_distillation_v1_summary.md').write_text(summary, encoding='utf-8'); (out/'summary.md').write_text(summary, encoding='utf-8')
    manifest={'stage':'frontend100_ensemble_distillation_v1','generated_at':datetime.now().isoformat(timespec='seconds'),'run_tag':args.run_tag,'source_root':str(args.source_root),'locked_dir':str(args.locked_dir),'teacher_latent_cache':str(args.teacher_latent_cache),'teacher_seeds':teacher_seeds,'teacher_raw_q':float(args.teacher_raw_q),'student_seed':int(args.student_seed),'frozen_backbone':True,'student_checkpoint':str(student_ckpt),'fit_latent_meta':clean(fit_meta),'feature_stats':clean(stats),'negative_counts':clean(neg_counts),'train_config':{'train_samples':int(args.train_samples),'id_eval_samples':int(args.id_eval_samples),'ood_limit':int(args.ood_limit),'attack_limit':int(args.attack_limit),'latent_batch_size':int(args.latent_batch_size),'distill_batch_size':int(args.distill_batch_size),'epochs':int(args.epochs),'patience':int(args.patience),'distill_lr':float(args.distill_lr),'weight_decay':float(args.weight_decay),'hidden_dim':int(args.hidden_dim),'lambda_diag':float(args.lambda_diag),'lambda_raw':float(args.lambda_raw),'lambda_gate':float(args.lambda_gate),'seed':int(args.seed),'device':str(device)},'teacher_bundles':[{'seed':int(b['seed']),'checkpoint':str(b['checkpoint']),'raw_threshold':float(b['raw_thr']),'diag_threshold':float(b['diag_thr']),'raw_q':float(b['raw_q'])} for b in bundles],'outputs':{'results_csv':str(out/'ensemble_distillation_v1_results.csv'),'results_md':str(out/'ensemble_distillation_v1_results.md'),'summary_md':str(out/'ensemble_distillation_v1_summary.md'),'corr_csv':str(out/'ensemble_distillation_v1_teacher_student_corr.csv'),'curve_csv':str(out/'ensemble_distillation_v1_training_curve.csv'),'plots_dir':str(plot_dir),'distilled_head':str(out/'distilled_gate_head.pt')}}
    (out/'ensemble_distillation_v1_manifest.json').write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding='utf-8'); (out/'config.json').write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'[done] ensemble distillation v1 output: {out}')

if __name__ == '__main__':
    main()



