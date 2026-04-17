from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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
import frontend100_diagload_gate_multiseed as gms
import frontend100_diagload_sweep_no_compact as dsw
import frontend100_negative_recipe_rescoring as resc


BASE_F = 0.5
RAW_Q = [0.9995, 0.999, 0.998]
GUARD_Q = [0.95, 0.97, 0.98]


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tag_q(q: float) -> str:
    return str(float(q)).replace(".", "p")


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def eval_binary_decision(
    pred_id: np.ndarray,
    pred_ood: np.ndarray,
    pred_attack: np.ndarray,
    score_for_auc: np.ndarray,
    score_ood_for_auc: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
    budget: int,
    extra: Dict,
) -> Dict:
    ood_eval_pred = pred_ood[budget:]
    out = {
        "row_type": "per_seed",
        "policy_name": "fixed_conditional_gate",
        "threshold": 1.0,
        "threshold_source": "ID-only quantiles; boolean gate",
        "selection_feasible": True,
        "id_alarm_ratio": float(np.mean(pred_id)),
        "ood_alarm_ratio_eval": float(np.mean(ood_eval_pred)),
        "attack_detection_high_purity": float(np.mean(pred_attack[high_idx])),
        "attack_detection_boundary": float(np.mean(pred_attack[mixed_idx])) if len(mixed_idx) else np.nan,
        "roc_auc_attack_high_vs_ood_eval": float(
            resc.compute_auc(
                ood_eval_scores=score_ood_for_auc[budget:],
                attack_high_scores=score_for_auc[high_idx],
            )
        ),
    }
    out.update(extra)
    return out


def eval_score_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, policy_name, threshold, extra):
    row = resc.eval_threshold(
        threshold=threshold,
        id_scores=score_id,
        ood_scores=score_ood,
        ood_eval_scores=score_ood[budget:],
        attack_scores=score_attack,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    out = {
        "row_type": "per_seed",
        "policy_name": policy_name,
        "threshold": float(threshold),
        "threshold_source": "ID-only quantile",
        "selection_feasible": True,
        "roc_auc_attack_high_vs_ood_eval": float(
            resc.compute_auc(ood_eval_scores=score_ood[budget:], attack_high_scores=score_attack[high_idx])
        ),
        **row,
    }
    out.update(extra)
    return out


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "id_alarm_ratio",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    metrics = [c for c in metrics if c in df.columns]
    agg = (
        df.groupby(["object_label", "score_label", "policy_name"], as_index=False)[metrics]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    cols = []
    for c in agg.columns:
        if isinstance(c, tuple):
            cols.append(c[0] if c[1] == "" else f"{c[0]}_{c[1]}")
        else:
            cols.append(str(c))
    agg.columns = cols
    agg["row_type"] = "aggregate"
    return agg


def pairwise(per: pd.DataFrame, lhs: str, rhs: str, label: str) -> pd.DataFrame:
    a = per[per.object_label.eq(lhs)].copy()
    b = per[per.object_label.eq(rhs)].copy()
    m = a.merge(b, on=["seed", "policy_name"], suffixes=("_lhs", "_rhs"))
    rows = []
    for _, r in m.iterrows():
        rows.append(
            {
                "comparison": label,
                "seed": int(r["seed"]),
                "policy_name": r["policy_name"],
                "alarm_delta": float(r["ood_alarm_ratio_eval_lhs"] - r["ood_alarm_ratio_eval_rhs"]),
                "detection_delta": float(
                    r["attack_detection_high_purity_lhs"] - r["attack_detection_high_purity_rhs"]
                ),
                "auc_delta": float(
                    r["roc_auc_attack_high_vs_ood_eval_lhs"] - r["roc_auc_attack_high_vs_ood_eval_rhs"]
                ),
            }
        )
    return pd.DataFrame(rows)


def plot_tradeoff(agg: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    for _, r in agg.iterrows():
        obj = str(r["object_label"])
        if obj.startswith("cond_gate"):
            color = "#d62728" if "raw_q0p9995" in obj else ("#ff7f0e" if "raw_q0p999" in obj else "#1f77b4")
            marker = "o"
            alpha = 0.85
        elif obj == "dA__default_score":
            color = "#9467bd"
            marker = "s"
            alpha = 1.0
        elif obj == "old_best__log_weighted":
            color = "#2ca02c"
            marker = "^"
            alpha = 1.0
        else:
            color = "#7f7f7f"
            marker = "x"
            alpha = 0.8
        ax.errorbar(
            [r["ood_alarm_ratio_eval_mean"]],
            [r["attack_detection_high_purity_mean"]],
            xerr=[0 if pd.isna(r.get("ood_alarm_ratio_eval_std")) else r["ood_alarm_ratio_eval_std"]],
            yerr=[
                0
                if pd.isna(r.get("attack_detection_high_purity_std"))
                else r["attack_detection_high_purity_std"]
            ],
            fmt=marker,
            color=color,
            alpha=alpha,
            capsize=3,
        )
        if obj in {"dA__default_score", "old_best__log_weighted"} or "guard_q0p97" in obj:
            ax.text(
                r["ood_alarm_ratio_eval_mean"] + 0.004,
                r["attack_detection_high_purity_mean"] + 0.006,
                obj,
                fontsize=8,
            )
    ax.axvline(0.1322, color="black", linestyle="--", linewidth=1, alpha=0.55, label="dA multiseed alarm mean")
    ax.axhline(0.8014, color="black", linestyle=":", linewidth=1, alpha=0.55, label="dA multiseed det mean")
    ax.set_xlabel("OOD benign alarm ratio (mean +/- std)")
    ax.set_ylabel("High-purity attack detection (mean +/- std)")
    ax.set_title("Conditional covariance gate multi-seed validation")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_guard_grid(agg: pd.DataFrame, out: Path) -> None:
    cond = agg[agg.object_label.str.startswith("cond_gate")].copy()
    if cond.empty:
        return
    cond["raw_q"] = cond["object_label"].str.extract(r"raw_q([0-9p]+)_guard").iloc[:, 0]
    cond["guard_q"] = cond["object_label"].str.extract(r"guard_q([0-9p]+)").iloc[:, 0]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharex=True)
    for raw_q, g in cond.groupby("raw_q"):
        g = g.sort_values("guard_q")
        x = [float(str(v).replace("p", ".")) for v in g["guard_q"]]
        axes[0].plot(x, g["ood_alarm_ratio_eval_mean"], marker="o", label=f"raw {raw_q}")
        axes[1].plot(x, g["attack_detection_high_purity_mean"], marker="o", label=f"raw {raw_q}")
    axes[0].axhline(0.1322, color="black", linestyle="--", linewidth=1, alpha=0.6)
    axes[1].axhline(0.8014, color="black", linestyle="--", linewidth=1, alpha=0.6)
    axes[0].set_title("Mean OOD alarm vs guard quantile")
    axes[1].set_title("Mean attack detection vs guard quantile")
    for ax in axes:
        ax.set_xlabel("diag guard quantile")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("alarm")
    axes[1].set_ylabel("detection")
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = (
        f"\n- `{run_tag}`: Conditional covariance gate multi-seed offline validation "
        f"(`diag_q99 OR (raw_q AND diag_guard_q)`); no retraining. Path: `runs/{run_tag}/`.\n"
    )
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_research_log(run_tag: str, summary_block: str) -> None:
    p = WORKTREE_ROOT / "runs" / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = f"### 5.14 Conditional Covariance Gate Multi-Seed"
    if marker in text:
        return
    insert = "\n## 6. Current Candidate Ranking"
    block = f"\n{marker}\n\nRun:\n- `runs/{run_tag}/`\n\n{summary_block}\n"
    if insert in text:
        text = text.replace(insert, block + "\n" + insert)
    else:
        text = text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Conditional covariance gate multi-seed validation.")
    ap.add_argument("--run-tag", default=f"frontend100_conditional_gate_multiseed_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--force-recompute-latent", action="store_true")
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "conditional_gate_multiseed_plots"
    plot_dir.mkdir(exist_ok=True)
    cache = out / "cache_latents"
    cache.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source = args.source_root
    data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    x_all = pd.read_csv(data / "id_source_100.csv", header=None, nrows=13000).to_numpy(float)
    x_fit = x_all[:8000]
    x_id = x_all[8000:13000]
    x_ood = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(float)
    attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"
    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(float)
    stage2 = load_json(source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    idx = resc.build_stage2_indices(stage2)
    high_idx = idx["high"]
    mixed_idx = idx["mixed"]

    locked = WORKTREE_ROOT / "runs" / "frontend100_locked_candidate_multiseed_2026-04-06"
    locked_res = pd.read_csv(locked / "multiseed_locked_candidate_results.csv")
    prior_gate = WORKTREE_ROOT / "runs" / "frontend100_diagload_gate_multiseed_2026-04-08" / "diagload_gate_multiseed_results.csv"
    prior_gate_res = pd.read_csv(prior_gate) if prior_gate.exists() else pd.DataFrame()
    per_rows: List[Dict] = []
    branch_rows: List[Dict] = []
    audit: List[Dict] = []

    for seed in seeds:
        print(f"[seed {seed}] conditional gate scoring", flush=True)
        ckpt = locked / f"latent_swap_spike_mix_seed{seed}" / f"kitnet_transformer_latent_contrastive_v1_seed{seed}.ckpt"
        model = kit.KitNET.load_checkpoint(ckpt)
        h_fit, h_id, h_ood, h_attack, meta, mode = gms.extract_or_load_latents(
            model,
            seed,
            cache,
            x_fit,
            x_id,
            x_ood,
            x_attack,
            args.batch_size,
            args.force_recompute_latent,
        )
        lw = LedoitWolf().fit(h_fit)
        mu = lw.location_
        sigma = lw.covariance_
        raw_id, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, 0.0)
        raw_ood, _ = dsw.cholesky_diagload_scores(h_ood, mu, sigma, 0.0)
        raw_attack, _ = dsw.cholesky_diagload_scores(h_attack, mu, sigma, 0.0)
        diag_id, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, BASE_F)
        diag_ood, _ = dsw.cholesky_diagload_scores(h_ood, mu, sigma, BASE_F)
        diag_attack, _ = dsw.cholesky_diagload_scores(h_attack, mu, sigma, BASE_F)
        diag_q99 = float(np.quantile(diag_id, 0.99))
        diag_main_id = diag_id > diag_q99
        diag_main_ood = diag_ood > diag_q99
        diag_main_attack = diag_attack > diag_q99

        # References from previous formal multi-seed run.
        for obj_old, obj_new in [
            ("da__default_score", "dA__default_score"),
            ("latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0", "old_best__log_weighted"),
        ]:
            ref = locked_res[
                (locked_res.row_type.eq("per_seed"))
                & (locked_res.object_label.eq(obj_old))
                & (locked_res.seed.eq(seed))
                & (locked_res.policy_name.eq("fixed_id_q99"))
            ]
            if not ref.empty:
                r = ref.iloc[0].to_dict()
                r["object_label"] = obj_new
                r["score_label"] = obj_new
                r["policy_name"] = "fixed_conditional_gate"
                r["row_type"] = "per_seed"
                per_rows.append(r)
        if not prior_gate_res.empty:
            for obj in ["gate_f0p5_raw_q0p9995", "gate_f0p5_raw_q0p999"]:
                ref = prior_gate_res[
                    (prior_gate_res.row_type.eq("per_seed"))
                    & (prior_gate_res.object_label.eq(obj))
                    & (prior_gate_res.seed.eq(seed))
                ]
                if not ref.empty:
                    r = ref.iloc[0].to_dict()
                    r["object_label"] = "prior_" + obj
                    r["score_label"] = "prior_" + obj
                    r["policy_name"] = "fixed_conditional_gate"
                    r["row_type"] = "per_seed"
                    per_rows.append(r)

        for raw_q in RAW_Q:
            raw_thr = float(np.quantile(raw_id, raw_q))
            raw_id_hit = raw_id > raw_thr
            raw_ood_hit = raw_ood > raw_thr
            raw_attack_hit = raw_attack > raw_thr
            for guard_q in GUARD_Q:
                guard_thr = float(np.quantile(diag_id, guard_q))
                guard_id = diag_id > guard_thr
                guard_ood = diag_ood > guard_thr
                guard_attack = diag_attack > guard_thr
                raw_guard_id = raw_id_hit & guard_id
                raw_guard_ood = raw_ood_hit & guard_ood
                raw_guard_attack = raw_attack_hit & guard_attack
                pred_id = diag_main_id | raw_guard_id
                pred_ood = diag_main_ood | raw_guard_ood
                pred_attack = diag_main_attack | raw_guard_attack
                # Continuous support score is only for AUC diagnostics, not threshold selection.
                score_id = np.maximum(diag_id / diag_q99, np.minimum(raw_id / raw_thr, diag_id / guard_thr))
                score_ood = np.maximum(diag_ood / diag_q99, np.minimum(raw_ood / raw_thr, diag_ood / guard_thr))
                score_attack = np.maximum(
                    diag_attack / diag_q99, np.minimum(raw_attack / raw_thr, diag_attack / guard_thr)
                )
                obj = f"cond_gate_f0p5_raw_q{tag_q(raw_q)}_guard_q{tag_q(guard_q)}"
                per_rows.append(
                    eval_binary_decision(
                        pred_id,
                        pred_ood,
                        pred_attack,
                        score_attack,
                        score_ood,
                        high_idx,
                        mixed_idx,
                        args.calibration_budget,
                        {
                            "seed": seed,
                            "object_label": obj,
                            "score_label": obj,
                            "detector_family": "latent_swap_spike_mix_conditional_gate",
                            "base_f": BASE_F,
                            "raw_q": raw_q,
                            "diag_guard_q": guard_q,
                            "diag_q99_threshold": diag_q99,
                            "raw_threshold": raw_thr,
                            "diag_guard_threshold": guard_thr,
                        },
                    )
                )
                branch_rows.append(
                    {
                        "seed": seed,
                        "object_label": obj,
                        "raw_q": raw_q,
                        "diag_guard_q": guard_q,
                        "diag_ood_alarm": float(np.mean(diag_main_ood[args.calibration_budget :])),
                        "raw_ood_alarm": float(np.mean(raw_ood_hit[args.calibration_budget :])),
                        "raw_guard_ood_alarm": float(np.mean(raw_guard_ood[args.calibration_budget :])),
                        "gate_ood_alarm": float(np.mean(pred_ood[args.calibration_budget :])),
                        "diag_attack_detection_high": float(np.mean(diag_main_attack[high_idx])),
                        "raw_attack_detection_high": float(np.mean(raw_attack_hit[high_idx])),
                        "raw_guard_attack_detection_high": float(np.mean(raw_guard_attack[high_idx])),
                        "gate_attack_detection_high": float(np.mean(pred_attack[high_idx])),
                        "raw_ood_guard_pass_ratio": float(
                            np.mean(guard_ood[args.calibration_budget :][raw_ood_hit[args.calibration_budget :]])
                        )
                        if np.any(raw_ood_hit[args.calibration_budget :])
                        else np.nan,
                        "raw_attack_guard_pass_ratio_high": float(np.mean(guard_attack[high_idx][raw_attack_hit[high_idx]]))
                        if np.any(raw_attack_hit[high_idx])
                        else np.nan,
                    }
                )
        audit.append(
            {
                "seed": seed,
                "checkpoint": str(ckpt),
                "latent_mode": mode,
                "latent_dim": int(h_fit.shape[1]),
                "diag_q99_threshold": diag_q99,
            }
        )

    per = pd.DataFrame(per_rows)
    branch = pd.DataFrame(branch_rows)
    agg = aggregate(per)
    pair_frames = []
    for obj in sorted(per.object_label.unique()):
        if obj.startswith("cond_gate"):
            pair_frames.append(pairwise(per, obj, "dA__default_score", f"{obj}_vs_dA"))
            pair_frames.append(pairwise(per, obj, "old_best__log_weighted", f"{obj}_vs_old_best"))
            if "prior_gate_f0p5_raw_q0p9995" in per.object_label.unique():
                pair_frames.append(pairwise(per, obj, "prior_gate_f0p5_raw_q0p9995", f"{obj}_vs_prior_q9995"))
    pair_frames = [p for p in pair_frames if not p.empty]
    pair_per = pd.concat(pair_frames, ignore_index=True) if pair_frames else pd.DataFrame()
    pair_agg = pd.DataFrame()
    if not pair_per.empty:
        pair_agg = (
            pair_per.groupby(["comparison", "policy_name"], as_index=False)[["alarm_delta", "detection_delta", "auc_delta"]]
            .agg(["mean", "std", "count"])
            .reset_index()
        )
        cols = []
        for c in pair_agg.columns:
            cols.append(c[0] if isinstance(c, tuple) and c[1] == "" else (f"{c[0]}_{c[1]}" if isinstance(c, tuple) else str(c)))
        pair_agg.columns = cols

    per.to_csv(out / "conditional_gate_multiseed_results.csv", index=False)
    per.to_csv(out / "results.csv", index=False)
    agg.to_csv(out / "conditional_gate_multiseed_aggregate.csv", index=False)
    branch.to_csv(out / "conditional_gate_branch_diagnostics.csv", index=False)
    if not pair_per.empty:
        pair_per.to_csv(out / "conditional_gate_pairwise_per_seed.csv", index=False)
    if not pair_agg.empty:
        pair_agg.to_csv(out / "conditional_gate_pairwise_aggregate.csv", index=False)

    plot_tradeoff(agg, plot_dir / "conditional_gate_tradeoff_mean_std.png")
    plot_guard_grid(agg, plot_dir / "conditional_gate_guard_grid.png")

    result_md = "# Conditional Gate Multi-seed Results\n\n"
    result_md += "## Aggregate\n" + md_table(agg) + "\n\n"
    result_md += (
        "## Per-seed\n"
        + md_table(
            per[
                [
                    "object_label",
                    "seed",
                    "ood_alarm_ratio_eval",
                    "attack_detection_high_purity",
                    "id_alarm_ratio",
                    "roc_auc_attack_high_vs_ood_eval",
                ]
            ].sort_values(["object_label", "seed"])
        )
        + "\n\n"
    )
    result_md += "## Branch diagnostics\n" + md_table(branch) + "\n\n"
    if not pair_agg.empty:
        result_md += "## Pairwise aggregate\n" + md_table(pair_agg) + "\n"
    (out / "conditional_gate_multiseed_results.md").write_text(result_md, encoding="utf-8")

    def av(obj: str, col: str) -> float:
        row = agg[agg.object_label.eq(obj)]
        return float("nan") if row.empty else float(row.iloc[0][col])

    cond_agg = agg[agg.object_label.str.startswith("cond_gate")].copy()
    cond_agg["utility_vs_da"] = (
        cond_agg["attack_detection_high_purity_mean"] - 0.8014
    ) - 0.5 * np.maximum(cond_agg["ood_alarm_ratio_eval_mean"] - 0.1322, 0)
    best = cond_agg.sort_values("utility_vs_da", ascending=False).head(1)
    best_obj = str(best.iloc[0]["object_label"]) if not best.empty else "(none)"
    summary_lines = [
        "# Conditional Covariance Gate Multi-seed Summary",
        "",
        f"- Seeds: `{seeds}`.",
        "- No retraining; reused locked `latent_swap_spike_mix` checkpoints.",
        "- Rule: `diag_f0.5 > q99_ID OR (raw_maha > raw_q_ID AND diag_f0.5 > diag_guard_q_ID)`.",
        "- All thresholds use ID benign only.",
        "",
        "## Aggregate Results",
        md_table(
            agg[
                [
                    "object_label",
                    "ood_alarm_ratio_eval_mean",
                    "ood_alarm_ratio_eval_std",
                    "attack_detection_high_purity_mean",
                    "attack_detection_high_purity_std",
                    "id_alarm_ratio_mean",
                    "id_alarm_ratio_std",
                ]
            ].sort_values("object_label")
        ),
        "",
        "## Best Candidate Under Diagnostic Utility",
        f"- `{best_obj}`.",
        f"- dA reference: alarm={av('dA__default_score','ood_alarm_ratio_eval_mean'):.4f} 卤 {av('dA__default_score','ood_alarm_ratio_eval_std'):.4f}, det={av('dA__default_score','attack_detection_high_purity_mean'):.4f} 卤 {av('dA__default_score','attack_detection_high_purity_std'):.4f}.",
    ]
    if best_obj != "(none)":
        summary_lines.append(
            f"- Best conditional gate: alarm={av(best_obj,'ood_alarm_ratio_eval_mean'):.4f} 卤 {av(best_obj,'ood_alarm_ratio_eval_std'):.4f}, det={av(best_obj,'attack_detection_high_purity_mean'):.4f} 卤 {av(best_obj,'attack_detection_high_purity_std'):.4f}."
        )
    summary_lines += [
        "",
        "## Interpretation",
        "- If the conditional gate materially lowers mean alarm versus the prior OR gate while retaining detection, it supports a guarded raw-branch scorer fix.",
        "- If alarm remains far above dA or detection falls below dA, the failure is not just an unguarded raw branch; latent tail stability must be addressed in representation/training or with broader baselines.",
    ]
    summary = "\n".join(summary_lines) + "\n"
    (out / "conditional_gate_multiseed_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_conditional_gate_multiseed",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "no_training": True,
        "seeds": seeds,
        "rule": "diag_f0.5 > q99_ID OR (raw_maha > raw_q_ID AND diag_f0.5 > diag_guard_q_ID)",
        "base_f": BASE_F,
        "raw_q": RAW_Q,
        "diag_guard_q": GUARD_Q,
        "threshold_stats_source": "ID benign only",
        "run_audit": clean(audit),
        "outputs": {
            "results": str(out / "conditional_gate_multiseed_results.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "conditional_gate_multiseed_manifest.json").write_text(
        json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    update_research_log(
        args.run_tag,
        "- Tested guarded raw Mahalanobis rescue rules after the unguarded OR gate failed multi-seed.\n"
        "- This run determines whether seed303's raw-branch OOD alarm explosion can be fixed at the decision layer.",
    )
    print(f"[done] conditional gate output: {out}", flush=True)


if __name__ == "__main__":
    main()

