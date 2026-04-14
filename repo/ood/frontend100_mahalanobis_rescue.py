from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import KitNET as kit
import frontend100_latent_scorer_benchmark as lsb
import frontend100_negative_recipe_rescoring as resc

EPS = 1e-8
FLOOR_FACTORS = [0.05, 0.1, 0.2]
BEST_COVREG = 'covariance_regularized_v1_covreg_vm0p2_vx2p0_lv0p5_lc0p05'


def load_json(p: Path) -> Dict:
    return json.loads(p.read_text(encoding='utf-8'))


def clean(o):
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, tuple): return [clean(v) for v in o]
    if isinstance(o, np.generic): return clean(o.item())
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)): return None
    return o


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def mahalanobis(x, mean, precision):
    d = np.asarray(x, dtype=np.float64) - np.asarray(mean, dtype=np.float64)[None, :]
    q = np.sum((d @ precision) * d, axis=1)
    return np.sqrt(np.clip(q, 0, None))


def diag_floor_score(x, mu, var, floor):
    d2 = (np.asarray(x, dtype=np.float64) - mu[None, :]) ** 2
    ve = np.maximum(var, float(floor))
    return np.mean(d2 / (ve[None, :] + EPS), axis=1)


def diag_floor_contrib(x, mu, var, floor):
    d2 = (np.asarray(x, dtype=np.float64) - mu[None, :]) ** 2
    ve = np.maximum(var, float(floor))
    return d2 / (ve[None, :] + EPS)


def diag_floor_clip_score(x, mu, var, floor, clip_vec):
    c = diag_floor_contrib(x, mu, var, floor)
    return np.mean(np.minimum(c, clip_vec[None, :]), axis=1)


def diagload_precision(cov, floor):
    reg = np.asarray(cov, dtype=np.float64) + float(floor) * np.eye(cov.shape[0], dtype=np.float64)
    try:
        return np.linalg.inv(reg)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(reg)


def build_rows(obj, family, scorer, id_s, ood_s, att_s, high_idx, mixed_idx, args, extra=None):
    rows = lsb.build_score_rows(object_label=f'{obj}__{scorer}', detector_family=family, scorer_label=scorer, scorer_family='mahalanobis_rescue', id_scores=id_s, ood_scores=ood_s, attack_scores=att_s, high_idx=high_idx, mixed_idx=mixed_idx, scan_points=args.scan_points, calibration_budget=args.calibration_budget, calibration_target=args.calibration_target)
    for r in rows:
        if extra: r.update(extra)
    return rows


def load_or_extract_latents(label, ckpt, x_fit, x_id, x_ood, x_attack, cache, batch_size):
    paths = {k: cache / f'{label}_{k}.npy' for k in ['h_fit','h_id','h_ood','h_attack']}
    meta_p = cache / f'{label}_latent_meta.json'
    if all(p.exists() for p in paths.values()) and meta_p.exists():
        meta = load_json(meta_p)
        return tuple(np.load(paths[k]).astype(np.float32) for k in ['h_fit','h_id','h_ood','h_attack']) + (meta,)
    model = kit.KitNET.load_checkpoint(ckpt)
    h_fit, fit_meta = lsb.extract_global_latent(model=model, x=x_fit, batch_size=batch_size, negative=False)
    h_id, id_meta = lsb.extract_global_latent(model=model, x=x_id, batch_size=batch_size, negative=False)
    h_ood, ood_meta = lsb.extract_global_latent(model=model, x=x_ood, batch_size=batch_size, negative=False)
    h_attack, attack_meta = lsb.extract_global_latent(model=model, x=x_attack, batch_size=batch_size, negative=False)
    for k, arr in [('h_fit',h_fit),('h_id',h_id),('h_ood',h_ood),('h_attack',h_attack)]: np.save(paths[k], arr.astype(np.float32))
    meta = {'fit_meta': clean(fit_meta), 'id_meta': clean(id_meta), 'ood_meta': clean(ood_meta), 'attack_meta': clean(attack_meta), 'checkpoint': str(ckpt)}
    meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    return h_fit, h_id, h_ood, h_attack, meta


def top_dims(contrib, topk=10):
    mean_c = np.mean(contrib, axis=0)
    order = np.argsort(mean_c)[::-1][:topk]
    return [{'rank': i+1, 'dim': int(d), 'mean_contribution': float(mean_c[d])} for i, d in enumerate(order)]


def plot_tradeoff(df, out):
    fixed = df[(df.policy_name=='fixed_id_q99') & (df.selection_feasible==True)].copy()
    plt.figure(figsize=(10, 6.4))
    for _, r in fixed.iterrows():
        color = '#1f77b4' if 'diag_floor' in r.scorer_label else ('#d62728' if 'diagload' in r.scorer_label else '#444444')
        marker = 'o' if 'covreg' in r.object_label else 's'
        plt.scatter(float(r.ood_alarm_ratio_eval), float(r.attack_detection_high_purity), color=color, marker=marker, s=80)
        if ('covreg' in r.object_label and ('0p1' in r.scorer_label or 'original' in r.scorer_label)) or ('no_compact' in r.object_label and ('0p1' in r.scorer_label or 'original' in r.scorer_label)) or r.scorer_label in ['default_score','log_weighted_z_rmse0.5_cos1.0_old']:
            plt.text(float(r.ood_alarm_ratio_eval)+0.004, float(r.attack_detection_high_purity)+0.006, f"{r.object_label.replace('__',' : ')}\n{r.scorer_label}", fontsize=6.8)
    plt.xlabel('OOD benign alarm ratio (fixed q99)'); plt.ylabel('High-purity attack detection'); plt.title('Mahalanobis epsilon-floor rescue: fixed trade-off'); plt.grid(alpha=.25); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_tail(score_pack, out):
    plt.figure(figsize=(9,5.5))
    for label, arr in score_pack.items():
        vals = np.asarray(arr, dtype=np.float64); vals = vals[np.isfinite(vals)]
        plt.hist(np.log10(vals + EPS), bins=80, density=True, histtype='step', linewidth=1.7, label=label)
    plt.xlabel('log10(score)'); plt.ylabel('density'); plt.title('OOD benign high-tail shrinkage check'); plt.grid(alpha=.25); plt.legend(fontsize=8); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_floor_hits(diag, out):
    d = pd.DataFrame(diag)
    plt.figure(figsize=(8.5,5)); plt.bar(np.arange(len(d)), d.floor_hit_ratio.to_numpy(float)); plt.xticks(np.arange(len(d)), d.scorer_label, rotation=25, ha='right'); plt.ylabel('floor-hit dimension ratio'); plt.title('Dimensions hit by variance floor'); plt.grid(axis='y', alpha=.25); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_top_contrib(rows, out):
    d = pd.DataFrame(rows)
    d = d[d['rank'] <= 8]
    labels = d['object_scorer'].unique().tolist()
    fig, axes = plt.subplots(len(labels), 1, figsize=(8.8, max(3, 2.8*len(labels))))
    if len(labels)==1: axes=[axes]
    for ax, lab in zip(axes, labels):
        s = d[d.object_scorer==lab]
        ax.bar(s['dim'].astype(str), s['mean_contribution'].astype(float)); ax.set_title(lab); ax.set_ylabel('mean contrib'); ax.grid(axis='y', alpha=.25)
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    ap = argparse.ArgumentParser(description='Mahalanobis epsilon-floor rescue offline benchmark.')
    ap.add_argument('--run-tag', default=f'frontend100_mahalanobis_rescue_{today}')
    ap.add_argument('--source-root', type=Path, default=WORKTREE_ROOT.parents[1] / 'KitNET-py-master' / 'KitNET-py-master')
    ap.add_argument('--batch-size', type=int, default=1024); ap.add_argument('--scan-points', type=int, default=901); ap.add_argument('--calibration-budget', type=int, default=5000); ap.add_argument('--calibration-target', type=float, default=0.01)
    ap.add_argument('--train-samples', type=int, default=8000); ap.add_argument('--id-eval-samples', type=int, default=5000)
    args = ap.parse_args()
    out = WORKTREE_ROOT / 'runs' / args.run_tag; out.mkdir(parents=True, exist_ok=True); plot_dir = out / 'mahalanobis_rescue_plots'; plot_dir.mkdir(exist_ok=True); cache = out / 'cache_latents'; cache.mkdir(exist_ok=True)
    (out / 'command.txt').write_text('python ' + ' '.join(sys.argv) + '\n', encoding='utf-8')
    root = args.source_root; data = root / 'runs' / 'frontend100_crosscapture_stage1_2026-03-25' / 'data'; joint1 = root / 'runs' / 'frontend100_joint_eval_stage1_2026-03-31'; joint2 = root / 'runs' / 'frontend100_joint_eval_stage2_2026-04-01'
    train_csv = data / 'id_source_100.csv'; ood_csv = data / 'ood_benign_source_100.csv'; attack_csv = joint1 / 'data' / 'attack_source_100.csv'
    stage2 = load_json(joint2 / 'attack_manifest_stage2.json'); idx = resc.build_stage2_indices(stage2); high_idx, mixed_idx = idx['high'], idx['mixed']
    x_all = pd.read_csv(train_csv, header=None, nrows=args.train_samples+args.id_eval_samples).to_numpy(float); x_fit, x_id = x_all[:args.train_samples], x_all[args.train_samples:args.train_samples+args.id_eval_samples]
    x_ood = pd.read_csv(ood_csv, header=None).to_numpy(float); x_attack = pd.read_csv(attack_csv, header=None).to_numpy(float)
    cov_manifest = load_json(WORKTREE_ROOT / 'runs' / 'frontend100_covariance_regularized_v1_2026-04-07' / 'covariance_regularized_v1_config_manifest.json')
    cov_run = [r for r in cov_manifest['covreg_runs'] if r['label'] == BEST_COVREG][0]
    resc_manifest = load_json(WORKTREE_ROOT / 'runs' / 'frontend100_negative_recipe_rescoring_2026-04-05' / 'negative_recipe_rescoring_manifest.json')
    cmap = {c['candidate_label']: c for c in resc_manifest['candidates']}
    candidates = {
        'no_compact_latent': {'checkpoint': Path(cmap['latent_swap_spike_mix']['checkpoint']), 'family': 'latent_swap_spike_mix_no_compact'},
        'covreg_best': {'checkpoint': Path(cov_run['checkpoint']), 'family': 'covariance_regularized_v1'},
    }
    rows, diag_rows, contrib_rows = [], [], []
    tail_packs = {}
    # reference old-best/default rows
    covres = pd.read_csv(WORKTREE_ROOT / 'runs' / 'frontend100_covariance_regularized_v1_2026-04-07' / 'covariance_regularized_v1_results.csv')
    refs = ['latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old', f'{BEST_COVREG}__log_weighted_z_rmse0.5_cos1.0', 'transformer_tailreg__default_score', 'da__default_score']
    rows.extend(covres[covres.object_label.isin(refs)].to_dict('records'))
    for label, info in candidates.items():
        h_fit, h_id, h_ood, h_attack, meta = load_or_extract_latents(label, info['checkpoint'], x_fit, x_id, x_ood, x_attack, cache, args.batch_size)
        lw = LedoitWolf().fit(np.asarray(h_fit, dtype=np.float64))
        mu = np.asarray(lw.location_, dtype=np.float64); cov = np.asarray(lw.covariance_, dtype=np.float64); prec = np.asarray(lw.precision_, dtype=np.float64)
        var = np.var(np.asarray(h_fit, dtype=np.float64), axis=0)
        var_med = float(np.median(var)); cov_diag_med = float(np.median(np.diag(cov)))
        # original LW
        s_id = mahalanobis(h_id, mu, prec); s_ood = mahalanobis(h_ood, mu, prec); s_att = mahalanobis(h_attack, mu, prec)
        rows.extend(build_rows(label, info['family'], 'mahalanobis_ledoitwolf_original', s_id, s_ood, s_att, high_idx, mixed_idx, args, {'fit_source':'ID benign train', 'floor_factor':np.nan, 'floor_value':np.nan}))
        tail_packs[f'{label}_original'] = s_ood[args.calibration_budget:]
        # original contribution approx based on diagonal terms only for top dim diagnosis
        c0 = diag_floor_contrib(h_ood[args.calibration_budget:], mu, var, 0.0)
        for rr in top_dims(c0):
            rr.update({'object_scorer': f'{label}_original_diag_contrib'})
            contrib_rows.append(rr)
        for fac in FLOOR_FACTORS:
            floor = max(var_med * fac, EPS)
            sid = diag_floor_score(h_id, mu, var, floor); sood = diag_floor_score(h_ood, mu, var, floor); satt = diag_floor_score(h_attack, mu, var, floor)
            scorer = f'diag_floor_f{str(fac).replace(".","p")}'
            rows.extend(build_rows(label, info['family'], scorer, sid, sood, satt, high_idx, mixed_idx, args, {'fit_source':'ID benign train', 'floor_factor':fac, 'floor_value':floor, 'floor_base':'median(var_diag)'}))
            tail_packs[f'{label}_{scorer}'] = sood[args.calibration_budget:]
            contrib = diag_floor_contrib(h_ood[args.calibration_budget:], mu, var, floor)
            hit = var < floor
            diag_rows.append({'object_label': label, 'scorer_label': scorer, 'floor_type':'diag_variance_floor', 'floor_factor':fac, 'floor_value':floor, 'variance_median':var_med, 'floor_hit_dims':int(np.sum(hit)), 'floor_hit_ratio':float(np.mean(hit)), 'var_min':float(np.min(var)), 'var_p01':float(np.quantile(var,.01)), 'var_p05':float(np.quantile(var,.05)), 'var_p50':var_med, 'var_max':float(np.max(var)), 'ood_top1_contrib_share_mean':float(np.mean(np.max(contrib,axis=1)/(np.sum(contrib,axis=1)+EPS))), 'ood_top5_contrib_share_mean':float(np.mean(np.sort(contrib,axis=1)[:,-5:].sum(axis=1)/(np.sum(contrib,axis=1)+EPS)))})
            for rr in top_dims(contrib): rr.update({'object_scorer': f'{label}_{scorer}'}); contrib_rows.extend([rr])
            # clipped contribution using ID-cal q99 per dim
            clip_vec = np.quantile(diag_floor_contrib(h_id, mu, var, floor), 0.99, axis=0)
            sidc = diag_floor_clip_score(h_id, mu, var, floor, clip_vec); soodc = diag_floor_clip_score(h_ood, mu, var, floor, clip_vec); sattc = diag_floor_clip_score(h_attack, mu, var, floor, clip_vec)
            rows.extend(build_rows(label, info['family'], scorer + '_clipq99', sidc, soodc, sattc, high_idx, mixed_idx, args, {'fit_source':'ID benign train; clip q99 from ID calibration', 'floor_factor':fac, 'floor_value':floor, 'floor_base':'median(var_diag)', 'clip':'per-dim ID q99'}))
        for fac in FLOOR_FACTORS:
            floor = max(cov_diag_med * fac, EPS); p = diagload_precision(cov, floor)
            sid = mahalanobis(h_id, mu, p); sood = mahalanobis(h_ood, mu, p); satt = mahalanobis(h_attack, mu, p)
            scorer = f'ledoitwolf_diagload_f{str(fac).replace(".","p")}'
            rows.extend(build_rows(label, info['family'], scorer, sid, sood, satt, high_idx, mixed_idx, args, {'fit_source':'ID benign train', 'floor_factor':fac, 'floor_value':floor, 'floor_base':'median(diag(Sigma_LW))'}))
            tail_packs[f'{label}_{scorer}'] = sood[args.calibration_budget:]
            diag_rows.append({'object_label': label, 'scorer_label': scorer, 'floor_type':'full_cov_diag_loading', 'floor_factor':fac, 'floor_value':floor, 'variance_median':cov_diag_med, 'floor_hit_dims':int(np.sum(np.diag(cov)<floor)), 'floor_hit_ratio':float(np.mean(np.diag(cov)<floor)), 'var_min':float(np.min(np.diag(cov))), 'var_p01':float(np.quantile(np.diag(cov),.01)), 'var_p05':float(np.quantile(np.diag(cov),.05)), 'var_p50':cov_diag_med, 'var_max':float(np.max(np.diag(cov))), 'ood_top1_contrib_share_mean':np.nan, 'ood_top5_contrib_share_mean':np.nan})
    res = pd.DataFrame(rows).sort_values(['detector_family','object_label','scorer_label','policy_name']).reset_index(drop=True)
    res.to_csv(out / 'mahalanobis_rescue_results.csv', index=False); res.to_csv(out / 'results.csv', index=False)
    diag = pd.DataFrame(diag_rows); diag.to_csv(out / 'mahalanobis_rescue_diagnostics.csv', index=False)
    pd.DataFrame(contrib_rows).to_csv(out / 'mahalanobis_rescue_top_contributing_dims.csv', index=False)
    show = ['object_label','detector_family','scorer_label','policy_name','threshold','ood_alarm_ratio_eval','attack_detection_high_purity','attack_detection_boundary','roc_auc_attack_high_vs_ood_eval','selection_feasible']
    (out / 'mahalanobis_rescue_results.md').write_text(md_table(res[show]), encoding='utf-8'); (out / 'results.md').write_text(md_table(res[show]), encoding='utf-8')
    plot_tradeoff(res, plot_dir / 'fixed_tradeoff_rescue.png')
    # keep selected tails to avoid unreadable plot
    selected_tail = {k:v for k,v in tail_packs.items() if ('original' in k or 'diag_floor_f0p1' in k or 'ledoitwolf_diagload_f0p1' in k)}
    plot_tail(selected_tail, plot_dir / 'ood_tail_original_vs_floor.png')
    plot_floor_hits(diag, plot_dir / 'floor_hit_ratio.png')
    plot_top_contrib(pd.DataFrame(contrib_rows), plot_dir / 'dimension_contribution_top_dims.png')
    fixed = res[(res.policy_name=='fixed_id_q99') & (res.selection_feasible==True)].copy(); fixed['utility']=fixed.attack_detection_high_purity.astype(float)-fixed.ood_alarm_ratio_eval.astype(float)
    best = fixed[fixed.object_label.str.contains('covreg_best|no_compact_latent')].sort_values(['utility','attack_detection_high_purity'], ascending=[False,False]).head(1)
    def val(obj, scorer, col):
        s=fixed[(fixed.object_label==obj) & (fixed.scorer_label==scorer)]
        return float('nan') if s.empty else float(s.iloc[0][col])
    lines = ['# Mahalanobis Epsilon-Floor Rescue Summary','', '## Setup', '- Offline rescoring only: no training and no checkpoint modification.', '- Fit statistics use ID benign training split only; thresholds/z-like policies use ID benign calibration only.', '- Objects: no_compact latent, covreg_v1 best, transformer_tailreg default, dA default.', '', '## Required answers']
    lines.append(f"- Best rescue fixed row: `{best.iloc[0].object_label if not best.empty else 'NA'}` / `{best.iloc[0].scorer_label if not best.empty else 'NA'}` alarm={float(best.iloc[0].ood_alarm_ratio_eval) if not best.empty else float('nan'):.4f}, det={float(best.iloc[0].attack_detection_high_purity) if not best.empty else float('nan'):.4f}.")
    lines.append(f"- covreg original Mahalanobis fixed: alarm={val('covreg_best__mahalanobis_ledoitwolf_original','mahalanobis_ledoitwolf_original','ood_alarm_ratio_eval'):.4f}, det={val('covreg_best__mahalanobis_ledoitwolf_original','mahalanobis_ledoitwolf_original','attack_detection_high_purity'):.4f}.")
    lines.append(f"- no_compact original Mahalanobis fixed: alarm={val('no_compact_latent__mahalanobis_ledoitwolf_original','mahalanobis_ledoitwolf_original','ood_alarm_ratio_eval'):.4f}, det={val('no_compact_latent__mahalanobis_ledoitwolf_original','mahalanobis_ledoitwolf_original','attack_detection_high_purity'):.4f}.")
    lines.append('- If floor/diagload lowers alarm without collapsing detection, collapse dims are likely a scorer denominator issue; if not, the problem is broader than a few tiny variances.')
    lines.append(''); lines.append('## Floor diagnostics'); lines.append(md_table(diag[['object_label','scorer_label','floor_type','floor_factor','floor_value','floor_hit_ratio','var_p50','var_min','ood_top1_contrib_share_mean','ood_top5_contrib_share_mean']]))
    lines.append(''); lines.append('## Decision'); lines.append('- Use fixed rows plus floor diagnostics to decide whether covreg_v2 should add EMA variance buffer / tail-aligned objective.')
    summary='\n'.join(lines)+'\n'; (out/'mahalanobis_rescue_summary.md').write_text(summary, encoding='utf-8'); (out/'summary.md').write_text(summary, encoding='utf-8')
    manifest={'stage':'frontend100_mahalanobis_rescue','generated_at':datetime.now().isoformat(timespec='seconds'),'run_tag':args.run_tag,'no_training':True,'objects':candidates,'floor_factors':FLOOR_FACTORS,'outputs':{'results_csv':str(out/'mahalanobis_rescue_results.csv'),'diagnostics_csv':str(out/'mahalanobis_rescue_diagnostics.csv'),'top_dims_csv':str(out/'mahalanobis_rescue_top_contributing_dims.csv'),'plots_dir':str(plot_dir)}}
    (out/'mahalanobis_rescue_manifest.json').write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding='utf-8'); (out/'config.json').write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding='utf-8')
    mapp = WORKTREE_ROOT/'runs'/'master_experiment_map_v1.md'
    if mapp.exists():
        text=mapp.read_text(encoding='utf-8')
        if f'`{args.run_tag}`' not in text: mapp.write_text(text.rstrip()+f"\n- `{args.run_tag}`: Mahalanobis epsilon-floor rescue offline rescoring; no retraining. Path: `runs/{args.run_tag}/`.\n", encoding='utf-8')
    print(f'[done] mahalanobis rescue output: {out}', flush=True)

if __name__ == '__main__':
    main()
