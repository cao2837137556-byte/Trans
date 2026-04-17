
from __future__ import annotations

import argparse, json, sys, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_DIR=Path(__file__).resolve().parent
REPO_DIR=THIS_DIR.parent
WORKTREE_ROOT=REPO_DIR.parent
for path in [THIS_DIR, REPO_DIR]:
    if str(path) not in sys.path: sys.path.insert(0,str(path))

import KitNET as kit
import frontend100_latent_seed_ensemble as ens
import frontend100_negative_recipe_rescoring as resc


def clean(o):
    if isinstance(o, dict): return {k:clean(v) for k,v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, tuple): return [clean(v) for v in o]
    if isinstance(o, np.generic): return clean(o.item())
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)): return None
    return o


def md_table(df): return resc.md_table(df)


def load_stage2():
    source=WORKTREE_ROOT.parents[1]/'KitNET-py-master'/'KitNET-py-master'
    stage2=json.loads((source/'runs'/'frontend100_joint_eval_stage2_2026-04-01'/'attack_manifest_stage2.json').read_text(encoding='utf-8'))
    return resc.build_stage2_indices(stage2)


def build_ensemble_scores(raw_q=0.999):
    raw_scores={'id':[],'ood':[],'attack':[]}; diag_scores={'id':[],'ood':[],'attack':[]}; thrs=[]
    for seed in ens.FORMAL_SEEDS:
        raw,diag,info=ens.load_seed_scores(seed)
        raw_thr=np.quantile(raw['id'],raw_q); diag_thr=np.quantile(diag['id'],0.99)
        thrs.append({'seed':seed,'raw_thr':float(raw_thr),'diag_thr':float(diag_thr)})
        for split in ['id','ood','attack']:
            raw_scores[split].append(raw[split]/raw_thr)
            diag_scores[split].append(diag[split]/diag_thr)
    score={}
    for split in ['id','ood','attack']:
        gate=np.maximum(np.stack(diag_scores[split],axis=0), np.stack(raw_scores[split],axis=0))
        score[split]=np.mean(gate,axis=0)
    return score, thrs


def load_da_scores(seed=101):
    old=WORKTREE_ROOT.parents[1]/'KitNET-py-master'/'KitNET-py-master'
    locked=WORKTREE_ROOT/'runs'/'frontend100_locked_candidate_multiseed_2026-04-06'
    sd=old/'runs'/'frontend100_tailreg_bestcfg_stability_2026-03-28'/f'da_seed{seed}'
    return {
        'id':np.load(sd/'id_scores.npy').astype(float),
        'ood':np.load(sd/'iot23_ood_benign_scores.npy').astype(float),
        'attack':np.load(locked/'cache_attack_scores'/f'da_seed{seed}_attack_scores.npy').astype(float),
    }


def score_stats(scores, high_idx, budget, thr):
    return {
        'id_q50':float(np.quantile(scores['id'],0.5)), 'id_q99':float(np.quantile(scores['id'],0.99)), 'threshold':float(thr),
        'ood_eval_q50':float(np.quantile(scores['ood'][budget:],0.5)), 'ood_eval_q99':float(np.quantile(scores['ood'][budget:],0.99)),
        'attack_high_q50':float(np.quantile(scores['attack'][high_idx],0.5)), 'attack_high_q99':float(np.quantile(scores['attack'][high_idx],0.99)),
    }


def plot_dist(scores, high_idx, budget, thr, title, out):
    fig,ax=plt.subplots(figsize=(9,5.8))
    data=[scores['id'], scores['ood'][budget:], scores['attack'][high_idx]]
    labels=['ID benign','OOD benign eval','attack high']
    finite_blocks=[np.asarray(arr,dtype=float)[np.isfinite(arr)] for arr in data]
    upper=np.concatenate([np.quantile(arr,[0.99,0.999]) for arr in finite_blocks if len(arr)>0])
    lower=np.concatenate([np.quantile(arr,[0.5]) for arr in finite_blocks if len(arr)>0])
    use_log = bool(len(upper) and len(lower) and np.max(upper) / max(np.min(lower), 1e-12) > 1e3)
    xthr=np.log1p(thr) if use_log else thr
    xlabel='log(1 + score)' if use_log else 'score'
    for arr,label in zip(finite_blocks,labels):
        vals=np.log1p(arr) if use_log else arr
        lo,hi=np.quantile(vals,[0.001,0.999])
        clipped=vals[(vals>=lo)&(vals<=hi)]
        ax.hist(clipped,bins=80,density=True,alpha=.35,label=label)
    ax.axvline(xthr,color='black',ls='--',lw=1.2,label='fixed threshold')
    ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel('density'); ax.legend(); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(out,dpi=180); plt.close(fig)


def count_torch_params(ckpt: Path):
    model=kit.KitNET.load_checkpoint(ckpt)
    total=0
    for det in model.ensembleLayer+[model.outputLayer]:
        if hasattr(det,'model'):
            total += sum(p.numel() for p in det.model.parameters())
    return total, len(model.ensembleLayer)+1, model.detector_backend


def append_map(run_tag):
    p=WORKTREE_ROOT/'runs'/'mainline_docs'/'mainline_experiment_map.md'
    if not p.exists(): return
    text=p.read_text(encoding='utf-8')
    if f'`{run_tag}`' in text: return
    p.write_text(text.rstrip()+f"\n- `{run_tag}`: Final candidate audit for covariance-aware Transformer ensemble vs dA/recurrent/external baselines; includes main table, cost table, score distributions. Path: `runs/{run_tag}/`.\n",encoding='utf-8')


def update_log(run_tag, line):
    p=WORKTREE_ROOT/'runs'/'research_log'/'a_tier_experiment_progress_log.md'
    if not p.exists(): return
    text=p.read_text(encoding='utf-8')
    marker='### 5.21 Final Candidate Audit Package'
    block=f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Consolidate the current A-tier candidate evidence: covariance-aware Transformer ensemble operating region, dA q99/q995 references, external/deep baseline checks, and cost/complexity table.

Current result:
- {line}

Interpretation:
- Use this as the current decision package before any new model-side work. The claim should remain an operating-region claim, not an unconditional single-model q99 win.
"""
    if marker in text:
        head,tail=text.split(marker,1); nxt=tail.find('\n### ',5); text=head.rstrip()+'\n\n'+block.strip()+(tail[nxt:] if nxt>=0 else '\n')
    else:
        ins='\n## 6. Current Candidate Ranking'; text=text.replace(ins,block+'\n'+ins) if ins in text else text.rstrip()+block
    p.write_text(text,encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-tag',default='frontend100_final_candidate_audit_2026-04-08'); ap.add_argument('--budget',type=int,default=5000); args=ap.parse_args()
    out=WORKTREE_ROOT/'runs'/args.run_tag; out.mkdir(parents=True,exist_ok=True); plot_dir=out/'final_candidate_audit_plots'; plot_dir.mkdir(exist_ok=True)
    (out/'command.txt').write_text('python '+' '.join(sys.argv)+'\n',encoding='utf-8')
    idx=load_stage2(); high=idx['high']; mixed=idx['mixed']

    # Tables from prior finalized runs.
    idq=pd.read_csv(WORKTREE_ROOT/'runs'/'frontend100_latent_seed_ensemble_idq_sweep_2026-04-08'/'latent_seed_ensemble_idq_sweep_results.csv')
    daq=pd.read_csv(WORKTREE_ROOT/'runs'/'frontend100_latent_seed_ensemble_idq_sweep_2026-04-08'/'dA_idq_reference_aggregate.csv')
    ext=pd.read_csv(WORKTREE_ROOT/'runs'/'frontend100_external_baselines_2026-04-08'/'external_baseline_aggregate.csv')
    rec=pd.read_csv(WORKTREE_ROOT/'runs'/'frontend100_recurrent_deep_baselines_2026-04-08'/'recurrent_deep_baseline_aggregate.csv')
    cost_ab=pd.read_csv(WORKTREE_ROOT/'runs'/'frontend100_latent_ensemble_cost_ablation_2026-04-08'/'latent_ensemble_cost_ablation_results.csv')

    main_rows=[]
    def add(name, alarm, det, id_alarm, auc, source, note):
        main_rows.append({'object_label':name,'ood_alarm':float(alarm),'high_purity_detection':float(det),'id_alarm':float(id_alarm),'roc_auc':float(auc),'source':source,'note':note})
    # Transformer candidate variants.
    for obj,pol,note in [
        ('mean_gate_rawq0p999','fixed_id_q0p995','current main candidate'),
        ('mean_gate_rawq0p9995','fixed_id_q0p995','lower-alarm candidate'),
        ('mean_gate_rawq0p998','fixed_id_q0p997','conservative ID q997 candidate'),
    ]:
        r=idq[(idq.object_label.eq(obj))&(idq.policy_name.eq(pol))].iloc[0]
        add(f'Transformer ensemble {obj}/{pol}',r.ood_alarm_ratio_eval,r.attack_detection_high_purity,r.id_alarm_ratio,r.roc_auc_attack_high_vs_ood_eval,'latent_seed_ensemble_idq_sweep',note)
    for pol,note in [('fixed_id_q0p99','dA q99 reference'),('fixed_id_q0p995','dA same-ID-alarm reference')]:
        r=daq[daq.policy_name.eq(pol)].iloc[0]
        add(f'dA {pol}',r.ood_alarm_ratio_eval_mean,r.attack_detection_high_purity_mean,r.id_alarm_ratio_mean,r.roc_auc_attack_high_vs_ood_eval_mean,'dA_idq_reference',note)
    # Deep/external baseline compact rows.
    # external names use method/model columns; handle robustly.
    for label in ['IsolationForest','OneClassSVM','LOF','RandomForest']:
        cand=ext[ext.astype(str).apply(lambda col: col.str.contains(label, case=False, regex=False)).any(axis=1)]
        if not cand.empty:
            r=cand.sort_values('ood_alarm_ratio_eval_mean').iloc[0]
            add(f'external {label}',r.ood_alarm_ratio_eval_mean,r.attack_detection_high_purity_mean,r.id_alarm_ratio_mean,r.roc_auc_attack_high_vs_ood_eval_mean,'external_baselines','minimal external baseline')
    for label in ['gru_ae_L4_last','lstm_ae_L4_last']:
        r=rec[(rec.object_label.eq(label))&(rec.policy_name.eq('fixed_id_q99'))].iloc[0]
        add(f'recurrent {label}',r.ood_alarm_ratio_eval_mean,r.attack_detection_high_purity_mean,r.id_alarm_ratio_mean,r.roc_auc_attack_high_vs_ood_eval_mean,'recurrent_deep_baselines','deep sequence baseline')
    main=pd.DataFrame(main_rows).sort_values(['ood_alarm','high_purity_detection'],ascending=[True,False])
    main.to_csv(out/'final_candidate_main_table.csv',index=False)

    # Cost table.
    ck_base=WORKTREE_ROOT/'runs'/'frontend100_locked_candidate_multiseed_2026-04-06'
    trans_ckpts=[ck_base/f'latent_swap_spike_mix_seed{s}'/f'kitnet_transformer_latent_contrastive_v1_seed{s}.ckpt' for s in [101,202,303]]
    params, detectors, backend=count_torch_params(trans_ckpts[0])
    old=WORKTREE_ROOT.parents[1]/'KitNET-py-master'/'KitNET-py-master'
    da_ckpts=[old/'runs'/'frontend100_tailreg_bestcfg_stability_2026-03-28'/f'da_seed{s}'/f'kitnet_da_seed{s}.ckpt' for s in [101,202,303]]
    da_model=kit.KitNET.load_checkpoint(da_ckpts[0])
    cost=pd.DataFrame([
        {'object_label':'dA single seed','n_checkpoints':1,'relative_forward_passes':1,'checkpoint_bytes':int(da_ckpts[0].stat().st_size),'torch_param_count':0,'kitnet_subdetectors':len(da_model.ensembleLayer)+1,'note':'dA has numpy AE parameters; torch_param_count not applicable'},
        {'object_label':'Transformer latent single seed','n_checkpoints':1,'relative_forward_passes':1,'checkpoint_bytes':int(trans_ckpts[0].stat().st_size),'torch_param_count':params,'kitnet_subdetectors':detectors,'note':backend},
        {'object_label':'Transformer latent 3-seed ensemble','n_checkpoints':3,'relative_forward_passes':3,'checkpoint_bytes':int(sum(p.stat().st_size for p in trans_ckpts)),'torch_param_count':params*3,'kitnet_subdetectors':detectors*3,'note':'current main candidate uses mean of 3 seed scores'},
    ])
    cost.to_csv(out/'final_candidate_cost_table.csv',index=False)

    # Score distributions.
    ens_scores, thrs=build_ensemble_scores(0.999)
    ens_thr=float(np.quantile(ens_scores['id'],0.995))
    da_scores=load_da_scores(seed=101)
    da_thr_q99=float(np.quantile(da_scores['id'],0.99)); da_thr_q995=float(np.quantile(da_scores['id'],0.995))
    dist_rows=[]
    dist_rows.append({'object_label':'Transformer ensemble rawq0.999 idq0.995',**score_stats(ens_scores,high,args.budget,ens_thr)})
    dist_rows.append({'object_label':'dA seed101 q99',**score_stats(da_scores,high,args.budget,da_thr_q99)})
    dist_rows.append({'object_label':'dA seed101 q995',**score_stats(da_scores,high,args.budget,da_thr_q995)})
    pd.DataFrame(dist_rows).to_csv(out/'final_candidate_score_distribution_stats.csv',index=False)
    plot_dist(ens_scores,high,args.budget,ens_thr,'Transformer ensemble score distributions (rawq0.999, idq0.995)',plot_dir/'transformer_ensemble_score_distribution.png')
    plot_dist(da_scores,high,args.budget,da_thr_q99,'dA seed101 score distributions (q99 threshold)',plot_dir/'da_score_distribution_q99.png')
    # main tradeoff plot
    fig,ax=plt.subplots(figsize=(10,6.5))
    for _,r in main.iterrows():
        ax.scatter(r.ood_alarm,r.high_purity_detection,s=70)
        ax.text(r.ood_alarm+0.003,r.high_purity_detection+0.004,r.object_label,fontsize=7)
    ax.axvline(0.1322,color='black',ls='--',lw=1,label='dA q99 alarm mean'); ax.axhline(0.8014,color='black',ls=':',lw=1,label='dA q99 det mean')
    ax.set_xlabel('OOD benign alarm'); ax.set_ylabel('High-purity attack detection'); ax.set_title('Final candidate audit: main operating points'); ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(plot_dir/'final_candidate_main_tradeoff.png',dpi=180); plt.close(fig)

    line='3-seed Transformer ensemble rawq0.999/idq0.995 has alarm=0.1261 and detection=0.8444; dA q99 has alarm=0.1322 and detection=0.8014; dA q995 has alarm=0.1045 and detection=0.7690.'
    summary='\n'.join(['# Final Candidate Audit Summary','', '- This package consolidates the current A-tier candidate evidence without new model training.', f'- {line}', '- The claim should be framed as an ID-only operating-region result with 3x Transformer inference cost, not a single-model unconditional q99 win.', '', '## Main Table', md_table(main), '', '## Cost Table', md_table(cost), '', '## Score Distribution Stats', md_table(pd.DataFrame(dist_rows)), '', '## Interpretation', '- Current strongest paper candidate: `Transformer 3-seed covariance ensemble, rawq=0.999, fixed_id_q0.995`.', '- Recurrent AE and simple external baselines do not solve stronger OOD fixed alarms.', '- The cost/complexity section must explicitly mention 3 checkpoints / 3 relative forward passes.'])+'\n'
    (out/'summary.md').write_text(summary,encoding='utf-8'); (out/'final_candidate_audit_summary.md').write_text(summary,encoding='utf-8'); (out/'final_candidate_main_table.md').write_text('# Final Candidate Main Table\n\n'+md_table(main)+'\n## Cost\n'+md_table(cost),encoding='utf-8')
    cfg={'stage':'frontend100_final_candidate_audit','generated_at':datetime.now().isoformat(timespec='seconds'),'run_tag':args.run_tag,'no_new_training':True,'main_candidate':'Transformer 3-seed covariance ensemble rawq0.999 fixed_id_q0.995','threshold_source':'ID benign only','score_thresholds':{'ensemble_rawq0.999_idq0.995':ens_thr,'dA_seed101_q99':da_thr_q99,'dA_seed101_q995':da_thr_q995},'ensemble_seed_thresholds':thrs,'outputs':{'summary':str(out/'summary.md'),'main_table':str(out/'final_candidate_main_table.csv'),'cost_table':str(out/'final_candidate_cost_table.csv'),'plots':str(plot_dir)}}
    (out/'config.json').write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False),encoding='utf-8'); (out/'final_candidate_audit_manifest.json').write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False),encoding='utf-8')
    append_map(args.run_tag); update_log(args.run_tag,line); print('[done]',out)

if __name__=='__main__': main()

