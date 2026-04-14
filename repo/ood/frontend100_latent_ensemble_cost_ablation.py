
from __future__ import annotations

import argparse, itertools, json, sys
from datetime import datetime
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_DIR=Path(__file__).resolve().parent
REPO_DIR=THIS_DIR.parent
WORKTREE_ROOT=REPO_DIR.parent
for path in [THIS_DIR, REPO_DIR]:
    if str(path) not in sys.path: sys.path.insert(0, str(path))

import frontend100_latent_seed_ensemble as ens
import frontend100_negative_recipe_rescoring as resc

RAW_QS=[0.9995,0.999,0.998]
ID_QS=[0.99,0.995,0.997]


def clean(o):
    if isinstance(o, dict): return {k:clean(v) for k,v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, tuple): return [clean(v) for v in o]
    if isinstance(o, np.generic): return clean(o.item())
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)): return None
    return o


def md_table(df): return resc.md_table(df)

def tag(x): return str(float(x)).replace('.','p')


def eval_score(sid, sood, satt, high, mixed, budget, label, raw_q, id_q, subset):
    thr=float(np.quantile(sid,id_q)); ood_eval=sood[budget:]
    row=resc.eval_threshold(thr,sid,sood,ood_eval,satt,high,mixed)
    row.update({
        'object_label':label,
        'score_label':'mean_gate',
        'subset':'+'.join(map(str,subset)),
        'n_seed':len(subset),
        'relative_inference_cost':len(subset),
        'raw_q':raw_q,
        'id_q':id_q,
        'policy_name':f'fixed_id_q{tag(id_q)}',
        'threshold_source':'ID-only quantile of subset mean gate score',
        'roc_auc_attack_high_vs_ood_eval':resc.compute_auc(ood_eval,satt[high]),
    })
    return row


def add_map(run_tag):
    p=WORKTREE_ROOT/'runs'/'master_experiment_map_v1.md'
    if not p.exists(): return
    text=p.read_text(encoding='utf-8')
    if f'`{run_tag}`' in text: return
    p.write_text(text.rstrip()+f"\n- `{run_tag}`: 1/2/3-seed ensemble cost-effect ablation for covariance gate; no retraining. Path: `runs/{run_tag}/`.\n",encoding='utf-8')


def update_log(run_tag,best_line):
    p=WORKTREE_ROOT/'runs'/'research_log'/'a_tier_experiment_progress_log.md'
    if not p.exists(): return
    text=p.read_text(encoding='utf-8')
    marker='### 5.20 Ensemble Cost / Seed-Count Ablation'
    block=f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Quantify whether the covariance gate result requires three Transformer checkpoints or can be approximated by 1/2-seed subsets.
- This is a cost/complexity ablation for A-tier deployment discussion; no retraining.

Current result:
- {best_line}

Interpretation:
- If 2-seed subsets are unstable, the 3-seed ensemble should be framed as a stability/cost trade-off rather than a simple single-model replacement.
"""
    if marker in text:
        head,tail=text.split(marker,1); nxt=tail.find('\n### ',5); text=head.rstrip()+'\n\n'+block.strip()+(tail[nxt:] if nxt>=0 else '\n')
    else:
        ins='\n## 6. Current Candidate Ranking'; text=text.replace(ins, block+'\n'+ins) if ins in text else text.rstrip()+block
    p.write_text(text,encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-tag',default='frontend100_latent_ensemble_cost_ablation_2026-04-08'); ap.add_argument('--calibration-budget',type=int,default=5000); args=ap.parse_args()
    out=WORKTREE_ROOT/'runs'/args.run_tag; out.mkdir(parents=True,exist_ok=True); plot_dir=out/'latent_ensemble_cost_plots'; plot_dir.mkdir(exist_ok=True)
    (out/'command.txt').write_text('python '+' '.join(sys.argv)+'\n',encoding='utf-8')
    source=WORKTREE_ROOT.parents[1]/'KitNET-py-master'/'KitNET-py-master'
    stage2=ens.load_json(source/'runs'/'frontend100_joint_eval_stage2_2026-04-01'/'attack_manifest_stage2.json')
    idx=resc.build_stage2_indices(stage2); high=idx['high']; mixed=idx['mixed']
    raw_scores={'id':{},'ood':{},'attack':{}}; diag_scores={'id':{},'ood':{},'attack':{}}; audit=[]
    for seed in ens.FORMAL_SEEDS:
        raw,diag,info=ens.load_seed_scores(seed); audit.append(info)
        for split in ['id','ood','attack']:
            raw_scores[split][seed]=raw[split]; diag_scores[split][seed]=diag[split]
    rows=[]
    for n in [1,2,3]:
        for subset in itertools.combinations(ens.FORMAL_SEEDS,n):
            for raw_q in RAW_QS:
                per_split={}
                for split in ['id','ood','attack']:
                    vals=[]
                    for seed in subset:
                        diag_thr=np.quantile(diag_scores['id'][seed],0.99)
                        raw_thr=np.quantile(raw_scores['id'][seed],raw_q)
                        vals.append(np.maximum(diag_scores[split][seed]/diag_thr, raw_scores[split][seed]/raw_thr))
                    per_split[split]=np.mean(np.stack(vals,axis=0),axis=0)
                for id_q in ID_QS:
                    label=f'mean_gate_n{n}_rawq{tag(raw_q)}_idq{tag(id_q)}'
                    rows.append(eval_score(per_split['id'],per_split['ood'],per_split['attack'],high,mixed,args.calibration_budget,label,raw_q,id_q,subset))
    df=pd.DataFrame(rows)
    df.to_csv(out/'latent_ensemble_cost_ablation_results.csv',index=False); df.to_csv(out/'results.csv',index=False)
    agg=df.groupby(['n_seed','raw_q','id_q'],as_index=False)[['ood_alarm_ratio_eval','attack_detection_high_purity','id_alarm_ratio','roc_auc_attack_high_vs_ood_eval']].agg(['mean','std','count']).reset_index()
    cols=[]
    for c in agg.columns: cols.append(c[0] if isinstance(c,tuple) and c[1]=='' else (f'{c[0]}_{c[1]}' if isinstance(c,tuple) else str(c)))
    agg.columns=cols
    agg.to_csv(out/'latent_ensemble_cost_ablation_aggregate.csv',index=False)
    # Best under A target, else close.
    dA_alarm=0.1322; dA_det=0.8014
    hit=df[(df.ood_alarm_ratio_eval<=dA_alarm)&(df.attack_detection_high_purity>=dA_det)].copy()
    if not hit.empty:
        best=hit.sort_values(['n_seed','attack_detection_high_purity','ood_alarm_ratio_eval'],ascending=[True,False,True]).iloc[0]
        best_line=f"Smallest A-target subset `{best.object_label}` subset={best.subset}: alarm={best.ood_alarm_ratio_eval:.4f}, det={best.attack_detection_high_purity:.4f}, relative_cost={best.relative_inference_cost}."
    else:
        best=df.sort_values(['ood_alarm_ratio_eval','attack_detection_high_purity'],ascending=[True,False]).iloc[0]
        best_line=f"No subset hits A target; lowest alarm `{best.object_label}` subset={best.subset}: alarm={best.ood_alarm_ratio_eval:.4f}, det={best.attack_detection_high_purity:.4f}."
    # plots
    fixed=df.copy()
    fig,ax=plt.subplots(figsize=(10,7))
    colors={1:'tab:blue',2:'tab:orange',3:'tab:green'}
    for _,r in fixed.iterrows():
        ax.scatter(r.ood_alarm_ratio_eval,r.attack_detection_high_purity,s=45,color=colors.get(int(r.n_seed),'gray'),alpha=.75)
    ax.axvline(dA_alarm,color='black',ls='--',lw=1,label='dA alarm mean'); ax.axhline(dA_det,color='black',ls=':',lw=1,label='dA det mean')
    for n,c in colors.items(): ax.scatter([],[],color=c,label=f'{n} seed(s)')
    ax.set_xlabel('OOD benign alarm'); ax.set_ylabel('High-purity attack detection'); ax.set_title('Ensemble cost / seed-count ablation'); ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(plot_dir/'ensemble_cost_tradeoff.png',dpi=180); plt.close(fig)
    # aggregate line for main rawq=.999 idq=.995
    focus=agg[(np.isclose(agg.raw_q,0.999))&(np.isclose(agg.id_q,0.995))].sort_values('n_seed')
    if not focus.empty:
        fig,ax=plt.subplots(figsize=(8,5)); ax.errorbar(focus.n_seed,focus.ood_alarm_ratio_eval_mean,yerr=focus.ood_alarm_ratio_eval_std,marker='o',label='alarm'); ax.errorbar(focus.n_seed,focus.attack_detection_high_purity_mean,yerr=focus.attack_detection_high_purity_std,marker='^',label='det'); ax.axhline(dA_alarm,color='black',ls='--',lw=1); ax.axhline(dA_det,color='black',ls=':',lw=1); ax.set_xlabel('number of ensemble seeds'); ax.set_ylabel('ratio'); ax.set_title('Focus rule rawq=0.999, idq=0.995'); ax.grid(alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(plot_dir/'focus_rule_cost_curve.png',dpi=180); plt.close(fig)
    summary='\n'.join(['# Latent Ensemble Cost Ablation Summary','', '- No training/checkpoint changes.', '- Tests 1/2/3-seed subsets for mean covariance gate score.', f'- {best_line}', '', '## Aggregate', md_table(agg), '', '## Per subset', md_table(df[['object_label','subset','n_seed','raw_q','id_q','ood_alarm_ratio_eval','attack_detection_high_purity','id_alarm_ratio','roc_auc_attack_high_vs_ood_eval']])])+'\n'
    (out/'summary.md').write_text(summary,encoding='utf-8'); (out/'latent_ensemble_cost_ablation_summary.md').write_text(summary,encoding='utf-8'); (out/'latent_ensemble_cost_ablation_results.md').write_text('# Results\n\n'+md_table(df),encoding='utf-8')
    cfg={'stage':'frontend100_latent_ensemble_cost_ablation','generated_at':datetime.now().isoformat(timespec='seconds'),'run_tag':args.run_tag,'no_training':True,'seeds':ens.FORMAL_SEEDS,'raw_qs':RAW_QS,'id_qs':ID_QS,'relative_cost':'number of Transformer checkpoints evaluated','best_line':best_line,'audit':audit,'outputs':{'summary':str(out/'summary.md'),'results':str(out/'latent_ensemble_cost_ablation_results.csv'),'plots':str(plot_dir)}}
    (out/'config.json').write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False),encoding='utf-8'); (out/'latent_ensemble_cost_ablation_manifest.json').write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False),encoding='utf-8')
    add_map(args.run_tag); update_log(args.run_tag,best_line); print('[done]',out)
if __name__=='__main__': main()
