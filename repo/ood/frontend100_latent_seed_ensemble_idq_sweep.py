
from __future__ import annotations

import argparse, json, sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for path in [THIS_DIR, REPO_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import frontend100_latent_seed_ensemble as ens
import frontend100_negative_recipe_rescoring as resc

ID_QS = [0.99, 0.995, 0.997, 0.999, 0.9995]
RAW_QS = [0.9995, 0.999, 0.998]


def clean(obj):
    if isinstance(obj, dict): return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    if isinstance(obj, tuple): return [clean(v) for v in obj]
    if isinstance(obj, np.generic): return clean(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)): return None
    return obj


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def tag(x: float) -> str:
    return str(float(x)).replace('.', 'p')


def add_map(run_tag: str):
    p = WORKTREE_ROOT / 'runs' / 'mainline_docs' / 'mainline_experiment_map.md'
    if not p.exists(): return
    text = p.read_text(encoding='utf-8')
    if f'`{run_tag}`' in text: return
    p.write_text(text.rstrip()+f"\n- `{run_tag}`: ID-only fixed quantile sweep for latent seed-ensemble scalar scores; no retraining. Path: `runs/{run_tag}/`.\n", encoding='utf-8')


def update_log(run_tag: str, best_line: str):
    p = WORKTREE_ROOT / 'runs' / 'research_log' / 'a_tier_experiment_progress_log.md'
    if not p.exists(): return
    text = p.read_text(encoding='utf-8')
    marker = '### 5.18 Seed Ensemble ID-Quantile Sweep'
    block = f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Check whether the seed-ensemble scalar scorer only needs a stricter ID-only fixed threshold than q99.
- No OOD/attack statistics are used to define thresholds; ID quantiles only.

Current result:
- {best_line}

Interpretation:
- If this sweep reaches dA-level alarm with higher detection, the deployment rule can be framed as a stricter ID-quantile fixed threshold.
- If not, the remaining issue is not merely q99 threshold anchoring.
"""
    if marker in text:
        head, tail = text.split(marker, 1)
        nxt = tail.find('\n### ', 5)
        text = head.rstrip() + '\n\n' + block.strip() + (tail[nxt:] if nxt >= 0 else '\n')
    else:
        insert = '\n## 6. Current Candidate Ranking'
        text = text.replace(insert, block + '\n' + insert) if insert in text else text.rstrip()+block
    p.write_text(text, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-tag', default='frontend100_latent_seed_ensemble_idq_sweep_2026-04-08')
    ap.add_argument('--calibration-budget', type=int, default=5000)
    args = ap.parse_args()
    out = WORKTREE_ROOT / 'runs' / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / 'latent_seed_ensemble_idq_plots'; plot_dir.mkdir(exist_ok=True)
    (out/'command.txt').write_text('python ' + ' '.join(sys.argv) + '\n', encoding='utf-8')

    source_root = WORKTREE_ROOT.parents[1] / 'KitNET-py-master' / 'KitNET-py-master'
    stage2 = ens.load_json(source_root / 'runs' / 'frontend100_joint_eval_stage2_2026-04-01' / 'attack_manifest_stage2.json')
    idx = resc.build_stage2_indices(stage2); high_idx = idx['high']; mixed_idx = idx['mixed']

    raw_scores = {'id': [], 'ood': [], 'attack': []}; diag_scores = {'id': [], 'ood': [], 'attack': []}; audit=[]
    for seed in ens.FORMAL_SEEDS:
        raw, diag, info = ens.load_seed_scores(seed)
        audit.append(info)
        for split in ['id','ood','attack']:
            raw_scores[split].append(raw[split]); diag_scores[split].append(diag[split])
    raw_scores = {k: np.stack(v, axis=0) for k,v in raw_scores.items()}
    diag_scores = {k: np.stack(v, axis=0) for k,v in diag_scores.items()}

    rows=[]
    for raw_q in RAW_QS:
        raw_thr = np.array([np.quantile(raw_scores['id'][i], raw_q) for i in range(len(ens.FORMAL_SEEDS))])
        diag_thr = np.array([np.quantile(diag_scores['id'][i], 0.99) for i in range(len(ens.FORMAL_SEEDS))])
        norm_gate={}
        for split in ['id','ood','attack']:
            diag_norm = diag_scores[split] / diag_thr[:, None]
            raw_norm = raw_scores[split] / raw_thr[:, None]
            norm_gate[split] = np.maximum(diag_norm, raw_norm)
        score_variants = {
            f'mean_gate_rawq{tag(raw_q)}': (np.mean(norm_gate['id'],axis=0), np.mean(norm_gate['ood'],axis=0), np.mean(norm_gate['attack'],axis=0)),
            f'median_gate_rawq{tag(raw_q)}': (np.median(norm_gate['id'],axis=0), np.median(norm_gate['ood'],axis=0), np.median(norm_gate['attack'],axis=0)),
        }
        for label,(sid,sood,satt) in score_variants.items():
            for id_q in ID_QS:
                thr = float(np.quantile(sid, id_q))
                extra={'object_label': label, 'score_label': label, 'policy_name': f'fixed_id_q{tag(id_q)}', 'threshold_source': f'id_only_q{tag(id_q)}', 'id_q': id_q, 'raw_q': raw_q}
                row = ens.eval_at_threshold(sid, sood, satt, high_idx, mixed_idx, args.calibration_budget, thr, extra['policy_name'], extra['threshold_source'], extra)
                rows.append(row)
    df = pd.DataFrame(rows)
    df = df.sort_values(['ood_alarm_ratio_eval','attack_detection_high_purity'], ascending=[True, False])
    df.to_csv(out/'latent_seed_ensemble_idq_sweep_results.csv', index=False)
    df.to_csv(out/'results.csv', index=False)

    dA_alarm=0.1322; dA_det=0.8014
    hit = df[(df.ood_alarm_ratio_eval <= dA_alarm) & (df.attack_detection_high_purity >= dA_det)]
    if not hit.empty:
        best = hit.sort_values(['attack_detection_high_purity','ood_alarm_ratio_eval'], ascending=[False,True]).iloc[0]
        best_line = f"A-target hit `{best.object_label}` {best.policy_name}: alarm={best.ood_alarm_ratio_eval:.4f}, det={best.attack_detection_high_purity:.4f}."
    else:
        close = df.iloc[0]
        best_line = f"No A-target hit; lowest-alarm `{close.object_label}` {close.policy_name}: alarm={close.ood_alarm_ratio_eval:.4f}, det={close.attack_detection_high_purity:.4f}."

    (out/'latent_seed_ensemble_idq_sweep_results.md').write_text('# Seed Ensemble ID-Q Sweep Results\n\n' + md_table(df[['object_label','policy_name','threshold_source','ood_alarm_ratio_eval','attack_detection_high_purity','id_alarm_ratio','roc_auc_attack_high_vs_ood_eval']]), encoding='utf-8')

    fig, ax = plt.subplots(figsize=(10,7))
    for _,r in df.iterrows():
        ax.scatter(r.ood_alarm_ratio_eval, r.attack_detection_high_purity, s=55)
        ax.text(r.ood_alarm_ratio_eval+0.003, r.attack_detection_high_purity+0.003, f"{r.object_label}/{r.policy_name}", fontsize=6)
    ax.axvline(dA_alarm, color='black', ls='--', lw=1, label='dA alarm mean')
    ax.axhline(dA_det, color='black', ls=':', lw=1, label='dA det mean')
    ax.set_xlabel('OOD benign alarm ratio'); ax.set_ylabel('High-purity attack detection')
    ax.set_title('Seed ensemble ID-only fixed-quantile sweep')
    ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(plot_dir/'idq_sweep_tradeoff.png', dpi=180); plt.close(fig)

    summary = '\n'.join([
        '# Seed Ensemble ID-Quantile Sweep Summary','',
        '- No training and no checkpoint modification.',
        '- Thresholds are stricter ID-only fixed quantiles, not OOD/attack-derived thresholds.',
        f'- {best_line}','',
        '## Results', md_table(df[['object_label','policy_name','ood_alarm_ratio_eval','attack_detection_high_purity','id_alarm_ratio','roc_auc_attack_high_vs_ood_eval']])
    ]) + '\n'
    (out/'summary.md').write_text(summary, encoding='utf-8')
    (out/'latent_seed_ensemble_idq_sweep_summary.md').write_text(summary, encoding='utf-8')
    cfg={'stage':'frontend100_latent_seed_ensemble_idq_sweep','run_tag':args.run_tag,'generated_at':datetime.now().isoformat(timespec='seconds'),'no_training':True,'seeds':ens.FORMAL_SEEDS,'raw_qs':RAW_QS,'id_qs':ID_QS,'threshold_stats_source':'ID benign only','audit':clean(audit),'outputs':{'summary':str(out/'summary.md'),'results':str(out/'latent_seed_ensemble_idq_sweep_results.csv'),'plots':str(plot_dir)}}
    (out/'config.json').write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False), encoding='utf-8')
    (out/'latent_seed_ensemble_idq_sweep_manifest.json').write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False), encoding='utf-8')
    add_map(args.run_tag); update_log(args.run_tag, best_line)
    print('[done]', out)

if __name__ == '__main__':
    main()

