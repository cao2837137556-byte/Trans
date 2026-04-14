from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
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
import frontend100_negative_recipe_rescoring as resc
import frontend100_latent_scorer_benchmark as lsb
import frontend100_diagload_sweep_no_compact as dsw

GATE_Q = [0.9995, 0.999, 0.998]
BASE_F = 0.5


def clean(obj):
    if isinstance(obj, dict): return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    if isinstance(obj, tuple): return [clean(v) for v in obj]
    if isinstance(obj, np.generic): return clean(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)): return None
    return obj


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def tag_q(q: float) -> str:
    return str(float(q)).replace(".", "p")


def extract_or_load_latents(model: kit.KitNET, seed: int, cache_dir: Path, x_fit, x_id, x_ood, x_attack, batch_size: int, force: bool = False):
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "fit": cache_dir / f"latent_swap_spike_mix_seed{seed}_h_fit.npy",
        "id": cache_dir / f"latent_swap_spike_mix_seed{seed}_h_id.npy",
        "ood": cache_dir / f"latent_swap_spike_mix_seed{seed}_h_ood.npy",
        "attack": cache_dir / f"latent_swap_spike_mix_seed{seed}_h_attack.npy",
        "meta": cache_dir / f"latent_swap_spike_mix_seed{seed}_latent_meta.json",
    }
    if (not force) and all(p.exists() for p in files.values()):
        return (np.load(files["fit"]).astype(np.float64), np.load(files["id"]).astype(np.float64), np.load(files["ood"]).astype(np.float64), np.load(files["attack"]).astype(np.float64), load_json(files["meta"]), "reused_cache")
    h_fit, fit_meta = lsb.extract_global_latent(model, x_fit, batch_size, negative=False)
    h_id, id_meta = lsb.extract_global_latent(model, x_id, batch_size, negative=False)
    h_ood, ood_meta = lsb.extract_global_latent(model, x_ood, batch_size, negative=False)
    h_attack, attack_meta = lsb.extract_global_latent(model, x_attack, batch_size, negative=False)
    np.save(files["fit"], h_fit); np.save(files["id"], h_id); np.save(files["ood"], h_ood); np.save(files["attack"], h_attack)
    meta = {"seed": int(seed), "fit_meta": clean(fit_meta), "id_meta": clean(id_meta), "ood_meta": clean(ood_meta), "attack_meta": clean(attack_meta)}
    files["meta"].write_text(json.dumps(clean(meta), indent=2, ensure_ascii=False), encoding="utf-8")
    return h_fit.astype(np.float64), h_id.astype(np.float64), h_ood.astype(np.float64), h_attack.astype(np.float64), meta, "computed_now"


def eval_scores(score_id, score_ood, score_attack, high_idx, mixed_idx, budget: int, policy_name: str, threshold: float, source: str, extra: Dict) -> Dict:
    ood_eval = score_ood[budget:]
    row = resc.eval_threshold(threshold=threshold, id_scores=score_id, ood_scores=score_ood, ood_eval_scores=ood_eval, attack_scores=score_attack, high_idx=high_idx, mixed_idx=mixed_idx)
    auc = resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=score_attack[high_idx])
    out = {
        "row_type": "per_seed",
        "policy_name": policy_name,
        "threshold": float(threshold),
        "threshold_source": source,
        "selection_feasible": True,
        "roc_auc_attack_high_vs_ood_eval": float(auc),
        **row,
    }
    out.update(extra)
    return out


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    metric_cols = ["id_alarm_ratio", "ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "roc_auc_attack_high_vs_ood_eval", "diag_threshold", "raw_threshold"]
    metric_cols = [c for c in metric_cols if c in df.columns]
    agg = df.groupby(["object_label", "score_label", "policy_name"], as_index=False)[metric_cols].agg(["mean", "std", "count"]).reset_index()
    cols=[]
    for c in agg.columns:
        if isinstance(c, tuple): cols.append(c[0] if c[1]=="" else f"{c[0]}_{c[1]}")
        else: cols.append(str(c))
    agg.columns=cols
    agg["row_type"]="aggregate"
    return agg


def pairwise(per: pd.DataFrame, lhs: str, rhs: str, label: str) -> pd.DataFrame:
    a=per[per.object_label.eq(lhs)].copy(); b=per[per.object_label.eq(rhs)].copy()
    m=a.merge(b, on=["seed", "policy_name"], suffixes=("_lhs", "_rhs"))
    rows=[]
    for _,r in m.iterrows():
        rows.append({
            "comparison": label,
            "seed": int(r["seed"]),
            "policy_name": r["policy_name"],
            "alarm_delta": float(r["ood_alarm_ratio_eval_lhs"] - r["ood_alarm_ratio_eval_rhs"]),
            "detection_delta": float(r["attack_detection_high_purity_lhs"] - r["attack_detection_high_purity_rhs"]),
            "auc_delta": float(r["roc_auc_attack_high_vs_ood_eval_lhs"] - r["roc_auc_attack_high_vs_ood_eval_rhs"]),
        })
    return pd.DataFrame(rows)


def plot_tradeoff(agg: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.8, 6.8))
    colors={"dA__default_score":"#9467bd", "old_best__log_weighted":"#2ca02c", "gate_f0p5_raw_q0p9995":"#d62728", "gate_f0p5_raw_q0p999":"#ff7f0e", "gate_f0p5_raw_q0p998":"#1f77b4"}
    for _,r in agg.iterrows():
        obj=str(r["object_label"])
        ax.errorbar([r["ood_alarm_ratio_eval_mean"]], [r["attack_detection_high_purity_mean"]], xerr=[0 if pd.isna(r.get("ood_alarm_ratio_eval_std")) else r["ood_alarm_ratio_eval_std"]], yerr=[0 if pd.isna(r.get("attack_detection_high_purity_std")) else r["attack_detection_high_purity_std"]], fmt="o", color=colors.get(obj,"#7f7f7f"), capsize=3)
        ax.text(r["ood_alarm_ratio_eval_mean"]+0.004, r["attack_detection_high_purity_mean"]+0.006, obj, fontsize=8)
    ax.axvline(0.1209, color="black", linestyle="--", linewidth=1, alpha=0.6, label="seed42 dA alarm ref")
    ax.axhline(0.7896, color="black", linestyle=":", linewidth=1, alpha=0.6, label="seed42 dA det ref")
    ax.set_xlabel("OOD benign alarm ratio (mean ± std)"); ax.set_ylabel("High-purity attack detection (mean ± std)")
    ax.set_title("Covariance gate multi-seed validation")
    ax.grid(alpha=0.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def append_map(run_tag: str) -> None:
    p=WORKTREE_ROOT/"runs"/"master_experiment_map_v1.md"
    if not p.exists(): return
    text=p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text: return
    entry=f"\n- `{run_tag}`: Multi-seed offline validation of no-compact latent covariance gate (`diag_f0.5 q99 OR raw Mahalanobis high-tail`); no retraining. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip()+entry, encoding="utf-8")


def update_research_log(run_tag: str, agg: pd.DataFrame) -> None:
    p=WORKTREE_ROOT/"runs"/"research_log"/"a_tier_experiment_progress_log.md"
    if not p.exists(): return
    text=p.read_text(encoding="utf-8")
    marker=f"### 5.12 Gate Multi-Seed Validation"
    if marker in text: return
    def val(obj, col):
        row=agg[agg.object_label.eq(obj)]
        return float('nan') if row.empty else float(row.iloc[0][col])
    block=f"""
\n### 5.12 Gate Multi-Seed Validation\n\nRun:\n- `runs/{run_tag}/`\n\nPurpose:\n- Validate the covariance gate discovered on seed42 without retraining or changing checkpoints.\n- Gate rules: `diag_f0.5 > q99_ID` OR `raw_maha > q_ID`, with `q∈{{0.9995,0.999,0.998}}`.\n\nKey aggregate results will be read from the run summary. This section should be refined if the gate is promoted to the paper mainline.\n\nCurrent immediate interpretation:\n- if `q0.9995` is stable, it becomes the deployment-like candidate;\n- if only `q0.999`/`q0.998` is strong, use it as high-detection operating region but keep alarm discussion explicit.\n"""
    insert="\n## 6. Current Candidate Ranking"
    if insert in text:
        text=text.replace(insert, block+"\n"+insert)
    else:
        text=text.rstrip()+block
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today=datetime.now().strftime("%Y-%m-%d")
    ap=argparse.ArgumentParser(description="Multi-seed validation for covariance gate.")
    ap.add_argument("--run-tag", default=f"frontend100_diagload_gate_multiseed_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1]/"KitNET-py-master"/"KitNET-py-master")
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--force-recompute-latent", action="store_true")
    args=ap.parse_args()
    seeds=[int(x) for x in args.seeds.split(',') if x.strip()]
    out=WORKTREE_ROOT/"runs"/args.run_tag; out.mkdir(parents=True, exist_ok=True)
    plot_dir=out/"diagload_gate_multiseed_plots"; plot_dir.mkdir(exist_ok=True)
    cache=out/"cache_latents"; cache.mkdir(exist_ok=True)
    (out/"command.txt").write_text("python "+" ".join(sys.argv)+"\n", encoding="utf-8")

    source=args.source_root
    data=source/"runs"/"frontend100_crosscapture_stage1_2026-03-25"/"data"
    x_all=pd.read_csv(data/"id_source_100.csv", header=None, nrows=13000).to_numpy(float)
    x_fit=x_all[:8000]; x_id=x_all[8000:13000]
    x_ood=pd.read_csv(data/"ood_benign_source_100.csv", header=None).to_numpy(float)
    attack_csv=source/"runs"/"frontend100_joint_eval_stage1_2026-03-31"/"data"/"attack_source_100.csv"
    x_attack=pd.read_csv(attack_csv, header=None).to_numpy(float)
    stage2=load_json(source/"runs"/"frontend100_joint_eval_stage2_2026-04-01"/"attack_manifest_stage2.json")
    idx=resc.build_stage2_indices(stage2); high_idx=idx["high"]; mixed_idx=idx["mixed"]
    locked=WORKTREE_ROOT/"runs"/"frontend100_locked_candidate_multiseed_2026-04-06"
    locked_res=pd.read_csv(locked/"multiseed_locked_candidate_results.csv")
    per_rows: List[Dict]=[]; audit=[]

    for seed in seeds:
        print(f"[seed {seed}] gate scoring", flush=True)
        ckpt=locked/f"latent_swap_spike_mix_seed{seed}"/f"kitnet_transformer_latent_contrastive_v1_seed{seed}.ckpt"
        model=kit.KitNET.load_checkpoint(ckpt)
        h_fit,h_id,h_ood,h_attack,meta,mode=extract_or_load_latents(model, seed, cache, x_fit,x_id,x_ood,x_attack,args.batch_size,args.force_recompute_latent)
        lw=LedoitWolf().fit(h_fit); mu=lw.location_; sigma=lw.covariance_
        raw_id,_=dsw.cholesky_diagload_scores(h_id,mu,sigma,0.0); raw_ood,_=dsw.cholesky_diagload_scores(h_ood,mu,sigma,0.0); raw_attack,_=dsw.cholesky_diagload_scores(h_attack,mu,sigma,0.0)
        diag_id,_=dsw.cholesky_diagload_scores(h_id,mu,sigma,BASE_F); diag_ood,_=dsw.cholesky_diagload_scores(h_ood,mu,sigma,BASE_F); diag_attack,_=dsw.cholesky_diagload_scores(h_attack,mu,sigma,BASE_F)
        diag_thr=float(np.quantile(diag_id,0.99))
        for q in GATE_Q:
            raw_thr=float(np.quantile(raw_id,q))
            sid=np.maximum(diag_id/diag_thr, raw_id/raw_thr)
            sood=np.maximum(diag_ood/diag_thr, raw_ood/raw_thr)
            satt=np.maximum(diag_attack/diag_thr, raw_attack/raw_thr)
            obj=f"gate_f0p5_raw_q{tag_q(q)}"
            per_rows.append(eval_scores(sid,sood,satt,high_idx,mixed_idx,args.calibration_budget,"fixed_gate_s_gt_1",1.0,"S=max(diag/q99_ID,raw/q_ID); ID-only thresholds",{"seed":seed,"object_label":obj,"score_label":obj,"detector_family":"latent_swap_spike_mix_gate","diag_threshold":diag_thr,"raw_threshold":raw_thr,"raw_q":q,"base_f":BASE_F}))
        # Add references from prior multiseed per seed fixed rows only.
        for obj_old,obj_new in [("da__default_score","dA__default_score"),("latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0","old_best__log_weighted")]:
            ref=locked_res[(locked_res.row_type.eq('per_seed')) & (locked_res.object_label.eq(obj_old)) & (locked_res.seed.eq(seed)) & (locked_res.policy_name.eq('fixed_id_q99'))]
            if not ref.empty:
                r=ref.iloc[0].to_dict(); r["object_label"]=obj_new; r["score_label"]=obj_new; r["policy_name"]="fixed_gate_s_gt_1"; r["row_type"]="per_seed"; per_rows.append(r)
        audit.append({"seed":seed,"checkpoint":str(ckpt),"latent_mode":mode,"latent_dim":int(h_fit.shape[1]),"diag_thr":diag_thr})

    per=pd.DataFrame(per_rows)
    agg=aggregate(per)
    pairs=[]
    for gate in [f"gate_f0p5_raw_q{tag_q(q)}" for q in GATE_Q]:
        pairs.append(pairwise(per, gate, "dA__default_score", f"{gate}_vs_dA"))
        pairs.append(pairwise(per, gate, "old_best__log_weighted", f"{gate}_vs_old_best"))
    nonempty_pairs=[x for x in pairs if not x.empty]
    pair_per=pd.concat(nonempty_pairs, ignore_index=True) if nonempty_pairs else pd.DataFrame()
    pair_agg=pd.DataFrame()
    if not pair_per.empty:
        pair_agg=pair_per.groupby(["comparison","policy_name"], as_index=False)[["alarm_delta","detection_delta","auc_delta"]].agg(["mean","std","count"]).reset_index()
        cols=[]
        for c in pair_agg.columns:
            cols.append(c[0] if isinstance(c,tuple) and c[1]=="" else (f"{c[0]}_{c[1]}" if isinstance(c,tuple) else str(c)))
        pair_agg.columns=cols
    per.to_csv(out/"diagload_gate_multiseed_results.csv", index=False)
    per.to_csv(out/"results.csv", index=False)
    agg.to_csv(out/"diagload_gate_multiseed_aggregate.csv", index=False)
    if not pair_per.empty: pair_per.to_csv(out/"diagload_gate_multiseed_pairwise_per_seed.csv", index=False)
    if not pair_agg.empty: pair_agg.to_csv(out/"diagload_gate_multiseed_pairwise_aggregate.csv", index=False)
    (out/"diagload_gate_multiseed_results.md").write_text("# Gate Multi-seed Results\n\n## Aggregate\n"+md_table(agg)+"\n\n## Per-seed\n"+md_table(per[["object_label","seed","policy_name","ood_alarm_ratio_eval","attack_detection_high_purity","roc_auc_attack_high_vs_ood_eval","id_alarm_ratio"]])+"\n\n## Pairwise\n"+(md_table(pair_agg) if not pair_agg.empty else "(none)")+"\n", encoding="utf-8")
    plot_tradeoff(agg, plot_dir/"gate_multiseed_tradeoff_mean_std.png")
    # Summary
    def av(obj,col):
        row=agg[agg.object_label.eq(obj)]
        return float('nan') if row.empty else float(row.iloc[0][col])
    lines=["# Covariance Gate Multi-seed Summary","",f"- Seeds: `{seeds}`","- No retraining; reused locked latent_swap_spike_mix checkpoints.","- Gate score: `S=max(diag_f0.5/q99_ID, raw_maha/q_ID)`; fixed decision is `S>1`.","- Tested raw q: `0.9995`, `0.999`, `0.998`.","", "## Aggregate fixed-gate results"]
    display=agg[["object_label","ood_alarm_ratio_eval_mean","ood_alarm_ratio_eval_std","attack_detection_high_purity_mean","attack_detection_high_purity_std","id_alarm_ratio_mean","id_alarm_ratio_std","roc_auc_attack_high_vs_ood_eval_mean","roc_auc_attack_high_vs_ood_eval_std"]].sort_values("object_label")
    lines.append(md_table(display))
    lines += ["", "## Required interpretation"]
    for q in GATE_Q:
        obj=f"gate_f0p5_raw_q{tag_q(q)}"
        lines.append(f"- `{obj}`: alarm={av(obj,'ood_alarm_ratio_eval_mean'):.4f} ± {av(obj,'ood_alarm_ratio_eval_std'):.4f}, det={av(obj,'attack_detection_high_purity_mean'):.4f} ± {av(obj,'attack_detection_high_purity_std'):.4f}, ID alarm={av(obj,'id_alarm_ratio_mean'):.4f} ± {av(obj,'id_alarm_ratio_std'):.4f}.")
    lines.append(f"- `dA__default_score`: alarm={av('dA__default_score','ood_alarm_ratio_eval_mean'):.4f} ± {av('dA__default_score','ood_alarm_ratio_eval_std'):.4f}, det={av('dA__default_score','attack_detection_high_purity_mean'):.4f} ± {av('dA__default_score','attack_detection_high_purity_std'):.4f}.")
    if not pair_agg.empty:
        lines += ["", "## Pairwise deltas vs dA/old-best", md_table(pair_agg)]
    lines += ["", "## Decision", "- Treat this as the formal stability check for the single-seed gate discovery. If no gate has both mean alarm near dA and higher mean detection than dA, the gate remains a promising single-seed discovery rather than a locked A-tier result."]
    summary="\n".join(lines)+"\n"
    (out/"diagload_gate_multiseed_summary.md").write_text(summary, encoding="utf-8")
    (out/"summary.md").write_text(summary, encoding="utf-8")
    cfg={"stage":"frontend100_diagload_gate_multiseed","generated_at":datetime.now().isoformat(timespec="seconds"),"run_tag":args.run_tag,"no_training":True,"seeds":seeds,"gate_score":"S=max(diag_f0.5/q99_ID, raw_maha/q_ID)","raw_q":GATE_Q,"base_f":BASE_F,"threshold_stats_source":"ID benign only","run_audit":clean(audit),"outputs":{"results":str(out/"diagload_gate_multiseed_results.csv"),"summary":str(out/"summary.md"),"plots":str(plot_dir)}}
    (out/"diagload_gate_multiseed_manifest.json").write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False), encoding="utf-8")
    (out/"config.json").write_text(json.dumps(clean(cfg),indent=2,ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag); update_research_log(args.run_tag, agg)
    print(f"[done] gate multiseed output: {out}", flush=True)

if __name__=='__main__': main()
