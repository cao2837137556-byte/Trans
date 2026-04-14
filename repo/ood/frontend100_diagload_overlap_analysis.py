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
from sklearn.covariance import LedoitWolf
from sklearn.metrics import roc_auc_score

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc
import frontend100_score_postprocessing as spp
import frontend100_diagload_sweep_no_compact as dsw

EPS = 1e-12
COMPARE_F = [0.15, 0.2, 0.3, 0.4]


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


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def top_share(contrib: np.ndarray, k: int) -> np.ndarray:
    contrib = np.asarray(contrib, dtype=np.float64)
    total = np.maximum(np.sum(contrib, axis=1), EPS)
    sorted_c = np.sort(contrib, axis=1)[:, ::-1]
    return np.sum(sorted_c[:, : min(k, sorted_c.shape[1])], axis=1) / total


def describe_array(x: np.ndarray, prefix: str) -> Dict:
    x = np.asarray(x, dtype=np.float64)
    if len(x) == 0:
        return {f"{prefix}_{k}": np.nan for k in ["mean", "median", "q10", "q25", "q75", "q90", "min", "max"]}
    return {
        f"{prefix}_mean": float(np.mean(x)),
        f"{prefix}_median": float(np.median(x)),
        f"{prefix}_q10": float(np.quantile(x, 0.10)),
        f"{prefix}_q25": float(np.quantile(x, 0.25)),
        f"{prefix}_q75": float(np.quantile(x, 0.75)),
        f"{prefix}_q90": float(np.quantile(x, 0.90)),
        f"{prefix}_min": float(np.min(x)),
        f"{prefix}_max": float(np.max(x)),
    }


def safe_auc(ood_scores: np.ndarray, attack_scores: np.ndarray) -> float:
    if len(ood_scores) == 0 or len(attack_scores) == 0:
        return float("nan")
    y = np.concatenate([np.zeros(len(ood_scores), dtype=int), np.ones(len(attack_scores), dtype=int)])
    s = np.concatenate([ood_scores, attack_scores]).astype(float)
    if len(np.unique(s)) <= 1:
        return float("nan")
    try:
        return float(roc_auc_score(y, s))
    except Exception:
        return float("nan")


def add_group_stats(rows: List[Dict], *, f: float, domain: str, group: str, mask: np.ndarray, scores: Dict[str, np.ndarray]) -> None:
    idx = np.where(mask)[0]
    row: Dict = {"f": float(f), "domain": domain, "group": group, "count": int(len(idx))}
    for name, arr in scores.items():
        row.update(describe_array(np.asarray(arr)[idx], name))
    rows.append(row)


def sample_manifest_rows(*, f: float, domain: str, group: str, mask: np.ndarray, scores: Dict[str, np.ndarray], base_index: np.ndarray, limit: int | None = None) -> List[Dict]:
    idx = np.where(mask)[0]
    if limit is not None and len(idx) > limit:
        # Keep strongest old-score cases for readability while preserving aggregate stats separately.
        order = np.argsort(np.asarray(scores.get("old_score", np.zeros(len(mask))))[idx])[::-1]
        idx = idx[order[:limit]]
    out = []
    for i in idx:
        r = {"f": float(f), "domain": domain, "group": group, "local_index": int(i), "source_index": int(base_index[i])}
        for name, arr in scores.items():
            r[name] = float(np.asarray(arr)[i])
        out.append(r)
    return out


def plot_scatter(out: Path, old_ood, diag_ood, old_attack, diag_attack, thr_old, thr_diag, f: float) -> None:
    rng = np.random.default_rng(42)
    oidx = np.arange(len(old_ood))
    if len(oidx) > 5000:
        oidx = rng.choice(oidx, size=5000, replace=False)
    aidx = np.arange(len(old_attack))
    if len(aidx) > 5000:
        aidx = rng.choice(aidx, size=5000, replace=False)
    plt.figure(figsize=(8.5, 6.5))
    plt.scatter(old_ood[oidx], diag_ood[oidx], s=7, alpha=0.25, label="OOD benign eval", color="#1f77b4")
    plt.scatter(old_attack[aidx], diag_attack[aidx], s=7, alpha=0.25, label="high-purity attack", color="#d62728")
    plt.axvline(thr_old, color="black", linestyle="--", linewidth=1.0, label="old q99")
    plt.axhline(thr_diag, color="purple", linestyle="--", linewidth=1.0, label=f"diag f={f} q99")
    plt.xlabel("old-best log_weighted score")
    plt.ylabel(f"diagload f={f} Mahalanobis score")
    plt.title(f"Old-best vs diagload f={f}: OOD/attack overlap")
    plt.legend(fontsize=8)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def plot_box(out: Path, stats_df: pd.DataFrame, feature: str, f: float) -> None:
    groups = [
        ("attack_lost", "attack"),
        ("attack_kept", "attack"),
        ("ood_reduced", "ood_eval"),
        ("ood_still_false_alarm", "ood_eval"),
    ]
    # This plot is built from sample manifest externally if available; placeholder handled in caller.


def plot_group_feature_box(sample_df: pd.DataFrame, out: Path, f: float, features: List[str]) -> None:
    sub = sample_df[sample_df["f"].eq(float(f))].copy()
    keep = ["attack_lost", "attack_kept", "ood_reduced", "ood_still_false_alarm"]
    sub = sub[sub["group"].isin(keep)]
    fig, axes = plt.subplots(1, len(features), figsize=(5.0 * len(features), 5.0), squeeze=False)
    for ax, feat in zip(axes[0], features):
        data = [sub[sub["group"].eq(g)][feat].to_numpy(float) for g in keep]
        ax.boxplot(data, labels=keep, showfliers=False)
        ax.set_title(feat)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(alpha=0.25)
    fig.suptitle(f"Lost attack vs reduced OOD signatures (f={f})")
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_auc(auc_df: pd.DataFrame, out: Path) -> None:
    sub = auc_df[auc_df["comparison"].eq("lost_attack_vs_reduced_ood")].copy()
    if sub.empty:
        return
    piv = sub.pivot(index="feature", columns="f", values="auc_attack_vs_ood")
    fig, ax = plt.subplots(figsize=(9.0, 5.5))
    for f in piv.columns:
        ax.plot(piv.index, piv[f], marker="o", label=f"f={f}")
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1)
    ax.set_ylabel("AUC: lost attack > reduced OOD")
    ax.set_title("Can remaining features separate lost attack from reduced false alarms?")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Offline lost-attack vs false-alarm overlap analysis for no-compact latent diagload; no retraining. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Lost attack vs reduced OOD false-alarm overlap analysis.")
    ap.add_argument("--run-tag", default=f"frontend100_diagload_overlap_analysis_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    plot_dir = out / "diagload_overlap_plots"
    out.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    manifest = load_json(WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "negative_recipe_rescoring_manifest.json")
    cmap = {c["candidate_label"]: c for c in manifest["candidates"]}
    cand = cmap["latent_swap_spike_mix"]
    run_dir = Path(cand["run_dir"])
    metrics = load_json(run_dir / "metrics.json")

    rmse_id = np.load(run_dir / "id_scores.npy").astype(np.float64)
    rmse_ood = np.load(resc.pick_ood_score_file(run_dir, metrics)).astype(np.float64)
    rmse_attack = np.load(Path(cand["attack_score_file"])).astype(np.float64)
    score_cache = WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "cache_rescored_scores"
    cos_id = np.load(score_cache / "latent_swap_spike_mix_latent_id_cos.npy").astype(np.float64)
    cos_ood = np.load(score_cache / "latent_swap_spike_mix_latent_ood_cos.npy").astype(np.float64)
    cos_attack = np.load(score_cache / "latent_swap_spike_mix_latent_attack_cos.npy").astype(np.float64)
    versions, score_stats = spp.make_score_versions(rmse_id, rmse_ood, rmse_attack, cos_id, cos_ood, cos_attack)
    old_sid, old_sood, old_satt = versions["log_weighted_z_rmse0.5_cos1.0"]

    latent_cache = WORKTREE_ROOT / "runs" / "frontend100_diagload_sweep_no_compact_2026-04-08" / "cache_latents"
    if not latent_cache.exists():
        latent_cache = WORKTREE_ROOT / "runs" / "frontend100_mahalanobis_rescue_2026-04-07" / "cache_latents"
    h_fit = np.load(latent_cache / "no_compact_latent_h_fit.npy").astype(np.float64)
    h_id = np.load(latent_cache / "no_compact_latent_h_id.npy").astype(np.float64)
    h_ood = np.load(latent_cache / "no_compact_latent_h_ood.npy").astype(np.float64)
    h_attack = np.load(latent_cache / "no_compact_latent_h_attack.npy").astype(np.float64)

    lw = LedoitWolf().fit(h_fit)
    mu = np.asarray(lw.location_, dtype=np.float64)
    sigma = np.asarray(lw.covariance_, dtype=np.float64)

    joint2 = args.source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2 = load_json(joint2 / "attack_manifest_stage2.json")
    idx = resc.build_stage2_indices(stage2)
    high_idx = np.asarray(idx["high"], dtype=np.int64)

    budget = int(args.calibration_budget)
    ood_eval_slice = slice(budget, None)
    ood_eval_index = np.arange(budget, len(old_sood), dtype=int)
    attack_high_index = high_idx.copy()

    diag_scores: Dict[float, Dict[str, np.ndarray]] = {}
    diag_contrib_eval: Dict[float, np.ndarray] = {}
    diag_contrib_attack_high: Dict[float, np.ndarray] = {}
    for f in [0.0] + COMPARE_F:
        sid, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, f, return_contrib=False)
        sood, _ = dsw.cholesky_diagload_scores(h_ood, mu, sigma, f, return_contrib=False)
        satt, _ = dsw.cholesky_diagload_scores(h_attack, mu, sigma, f, return_contrib=False)
        _, ceval, _ = dsw.cholesky_diagload_scores(h_ood[ood_eval_slice], mu, sigma, f, return_contrib=True)
        _, catt, _ = dsw.cholesky_diagload_scores(h_attack[high_idx], mu, sigma, f, return_contrib=True)
        diag_scores[float(f)] = {"id": sid, "ood": sood, "attack": satt, "threshold": np.quantile(sid, 0.99)}
        diag_contrib_eval[float(f)] = ceval
        diag_contrib_attack_high[float(f)] = catt

    old_thr = float(np.quantile(old_sid, 0.99))
    old_ood_eval = old_sood[ood_eval_slice]
    old_attack_high = old_satt[high_idx]
    rmse_ood_eval = rmse_ood[ood_eval_slice]
    rmse_attack_high = rmse_attack[high_idx]
    cos_ood_eval = cos_ood[ood_eval_slice]
    cos_attack_high = cos_attack[high_idx]
    raw_ood_eval = diag_scores[0.0]["ood"][ood_eval_slice]
    raw_attack_high = diag_scores[0.0]["attack"][high_idx]

    group_rows: List[Dict] = []
    sample_rows: List[Dict] = []
    sep_rows: List[Dict] = []
    direction_rows: List[Dict] = []

    for f in COMPARE_F:
        ds = diag_scores[float(f)]
        diag_thr = float(ds["threshold"])
        diag_ood_eval = ds["ood"][ood_eval_slice]
        diag_attack_high = ds["attack"][high_idx]
        old_attack_detect = old_attack_high > old_thr
        diag_attack_detect = diag_attack_high > diag_thr
        old_ood_alarm = old_ood_eval > old_thr
        diag_ood_alarm = diag_ood_eval > diag_thr

        masks = {
            "attack_lost": (old_attack_detect & ~diag_attack_detect),
            "attack_kept": (old_attack_detect & diag_attack_detect),
            "attack_gained": (~old_attack_detect & diag_attack_detect),
            "attack_missed_by_both": (~old_attack_detect & ~diag_attack_detect),
        }
        ood_masks = {
            "ood_reduced": (old_ood_alarm & ~diag_ood_alarm),
            "ood_still_false_alarm": (old_ood_alarm & diag_ood_alarm),
            "ood_new_false_alarm": (~old_ood_alarm & diag_ood_alarm),
            "ood_clean_by_both": (~old_ood_alarm & ~diag_ood_alarm),
        }
        attack_scores = {
            "rmse": rmse_attack_high,
            "latent_cosine": cos_attack_high,
            "old_score": old_attack_high,
            "raw_maha": raw_attack_high,
            f"diag_f{dsw.tag_float(f)}": diag_attack_high,
            "diag_margin": diag_attack_high - diag_thr,
            "old_margin": old_attack_high - old_thr,
            "top1_contrib_share": top_share(diag_contrib_attack_high[float(f)], 1),
            "top5_contrib_share": top_share(diag_contrib_attack_high[float(f)], 5),
            "top10_contrib_share": top_share(diag_contrib_attack_high[float(f)], 10),
        }
        ood_scores = {
            "rmse": rmse_ood_eval,
            "latent_cosine": cos_ood_eval,
            "old_score": old_ood_eval,
            "raw_maha": raw_ood_eval,
            f"diag_f{dsw.tag_float(f)}": diag_ood_eval,
            "diag_margin": diag_ood_eval - diag_thr,
            "old_margin": old_ood_eval - old_thr,
            "top1_contrib_share": top_share(diag_contrib_eval[float(f)], 1),
            "top5_contrib_share": top_share(diag_contrib_eval[float(f)], 5),
            "top10_contrib_share": top_share(diag_contrib_eval[float(f)], 10),
        }
        for g, m in masks.items():
            add_group_stats(group_rows, f=f, domain="attack_high", group=g, mask=m, scores=attack_scores)
            sample_rows.extend(sample_manifest_rows(f=f, domain="attack_high", group=g, mask=m, scores=attack_scores, base_index=attack_high_index, limit=None if g in ["attack_lost", "attack_kept"] else 300))
        for g, m in ood_masks.items():
            add_group_stats(group_rows, f=f, domain="ood_eval", group=g, mask=m, scores=ood_scores)
            sample_rows.extend(sample_manifest_rows(f=f, domain="ood_eval", group=g, mask=m, scores=ood_scores, base_index=ood_eval_index, limit=None if g in ["ood_reduced", "ood_still_false_alarm"] else 300))

        # Separation between the exact failure pair: attack lost by diagload vs OOD false alarms removed by diagload.
        lost = masks["attack_lost"]
        reduced = ood_masks["ood_reduced"]
        for feature in ["rmse", "latent_cosine", "old_score", "raw_maha", f"diag_f{dsw.tag_float(f)}", "old_margin", "diag_margin", "top1_contrib_share", "top5_contrib_share", "top10_contrib_share"]:
            sep_rows.append({
                "f": float(f),
                "comparison": "lost_attack_vs_reduced_ood",
                "feature": feature,
                "attack_count": int(np.sum(lost)),
                "ood_count": int(np.sum(reduced)),
                "attack_mean": float(np.mean(attack_scores[feature][lost])) if np.any(lost) else np.nan,
                "ood_mean": float(np.mean(ood_scores[feature][reduced])) if np.any(reduced) else np.nan,
                "auc_attack_vs_ood": safe_auc(ood_scores[feature][reduced], attack_scores[feature][lost]),
            })

        for domain, group, mask, contrib, base_index in [
            ("attack_high", "attack_lost", masks["attack_lost"], diag_contrib_attack_high[float(f)], attack_high_index),
            ("ood_eval", "ood_reduced", ood_masks["ood_reduced"], diag_contrib_eval[float(f)], ood_eval_index),
            ("ood_eval", "ood_still_false_alarm", ood_masks["ood_still_false_alarm"], diag_contrib_eval[float(f)], ood_eval_index),
        ]:
            if np.sum(mask) == 0:
                continue
            cmean = np.mean(contrib[mask], axis=0)
            for rank, dim in enumerate(np.argsort(cmean)[::-1][:15], start=1):
                direction_rows.append({"f": float(f), "domain": domain, "group": group, "rank": int(rank), "whitened_direction": int(dim), "mean_contribution": float(cmean[dim])})

        if abs(f - 0.4) < 1e-9:
            plot_scatter(plot_dir / "old_vs_diagload_f0p4_scatter.png", old_ood_eval, diag_ood_eval, old_attack_high, diag_attack_high, old_thr, diag_thr, f)
        if abs(f - 0.3) < 1e-9:
            plot_scatter(plot_dir / "old_vs_diagload_f0p3_scatter.png", old_ood_eval, diag_ood_eval, old_attack_high, diag_attack_high, old_thr, diag_thr, f)

    group_df = pd.DataFrame(group_rows)
    sample_df = pd.DataFrame(sample_rows)
    sep_df = pd.DataFrame(sep_rows)
    direction_df = pd.DataFrame(direction_rows)
    group_df.to_csv(out / "failure_overlap_group_stats.csv", index=False)
    sample_df.to_csv(out / "failure_overlap_sample_manifest.csv", index=False)
    sep_df.to_csv(out / "failure_overlap_separation_auc.csv", index=False)
    direction_df.to_csv(out / "failure_overlap_direction_contributions.csv", index=False)
    # compatibility filenames
    group_df.to_csv(out / "failure_overlap_results.csv", index=False)

    if not sample_df.empty:
        plot_group_feature_box(sample_df, plot_dir / "lost_vs_reduced_score_boxplot_f0p4.png", 0.4, ["rmse", "latent_cosine", "old_score", "raw_maha", "diag_f0p4", "top5_contrib_share"])
        plot_group_feature_box(sample_df, plot_dir / "lost_vs_reduced_score_boxplot_f0p3.png", 0.3, ["rmse", "latent_cosine", "old_score", "raw_maha", "diag_f0p3", "top5_contrib_share"])
    plot_auc(sep_df, plot_dir / "lost_attack_vs_reduced_ood_auc.png")

    # Decision summaries
    fixed_csv = WORKTREE_ROOT / "runs" / "frontend100_diagload_sweep_no_compact_2026-04-08" / "diagload_sweep_results.csv"
    fixed_df = pd.read_csv(fixed_csv)
    fixed_rows = fixed_df[fixed_df["policy_name"].eq("fixed_id_q99")].copy()
    summary_rows = []
    for f in COMPARE_F:
        scorer = f"mahalanobis_diagload_f{dsw.tag_float(f)}"
        row = fixed_rows[fixed_rows["scorer_label"].eq(scorer)].iloc[0]
        lost_count = int(group_df[(group_df["f"].eq(float(f))) & (group_df["domain"].eq("attack_high")) & (group_df["group"].eq("attack_lost"))]["count"].iloc[0])
        reduced_count = int(group_df[(group_df["f"].eq(float(f))) & (group_df["domain"].eq("ood_eval")) & (group_df["group"].eq("ood_reduced"))]["count"].iloc[0])
        top_sep = sep_df[(sep_df["f"].eq(float(f))) & (sep_df["comparison"].eq("lost_attack_vs_reduced_ood"))].sort_values("auc_attack_vs_ood", ascending=False).head(3)
        summary_rows.append({
            "f": float(f),
            "fixed_alarm": float(row["ood_alarm_ratio_eval"]),
            "fixed_detection": float(row["attack_detection_high_purity"]),
            "lost_attack_count_vs_old_best": lost_count,
            "reduced_ood_false_alarm_count_vs_old_best": reduced_count,
            "best_separating_feature": str(top_sep.iloc[0]["feature"]) if not top_sep.empty else "",
            "best_auc_lost_attack_vs_reduced_ood": float(top_sep.iloc[0]["auc_attack_vs_ood"]) if not top_sep.empty else np.nan,
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out / "failure_overlap_decision_table.csv", index=False)

    f04 = summary_df[summary_df["f"].eq(0.4)].iloc[0]
    f03 = summary_df[summary_df["f"].eq(0.3)].iloc[0]
    sep_f04 = sep_df[sep_df["f"].eq(0.4)].sort_values("auc_attack_vs_ood", ascending=False)
    best_f04 = sep_f04.iloc[0] if not sep_f04.empty else None
    can_score_rescue = bool(best_f04 is not None and float(best_f04["auc_attack_vs_ood"]) >= 0.75)

    lines = [
        "# Diagload Failure Overlap Analysis Summary",
        "",
        "## Setup",
        "- Offline analysis only: no retraining and no checkpoint modification.",
        "- Object: latent_swap_spike_mix_no_compact.",
        "- Reference scorer: old-best log_weighted_z_rmse0.5_cos1.0.",
        "- Compared diagload f values: 0.15, 0.2, 0.3, 0.4.",
        "- Key question: when diagload lowers OOD alarm, are the lost attacks separable from the reduced OOD false alarms by another score signature?",
        "",
        "## Decision Table",
        md_table(summary_df),
        "",
        "## Main Diagnosis",
        f"- f=0.3 fixed alarm={float(f03['fixed_alarm']):.4f}, det={float(f03['fixed_detection']):.4f}; it loses {int(f03['lost_attack_count_vs_old_best'])} old-best high-purity detections while reducing {int(f03['reduced_ood_false_alarm_count_vs_old_best'])} OOD false alarms.",
        f"- f=0.4 fixed alarm={float(f04['fixed_alarm']):.4f}, det={float(f04['fixed_detection']):.4f}; it loses {int(f04['lost_attack_count_vs_old_best'])} old-best high-purity detections while reducing {int(f04['reduced_ood_false_alarm_count_vs_old_best'])} OOD false alarms.",
    ]
    if best_f04 is not None:
        lines.append(f"- For f=0.4, best separator between lost attacks and reduced OOD false alarms is `{best_f04['feature']}` with AUC={float(best_f04['auc_attack_vs_ood']):.4f}.")
    if can_score_rescue:
        lines.append("- Interpretation: there is nontrivial residual separation; a small gated/composite scorer may still be worth a narrow offline test before new training.")
    else:
        lines.append("- Interpretation: residual separation is weak; if all features stay near chance, scorer-only rescue is unlikely and training-side tail/representation repair is needed.")
    lines += [
        "",
        "## Outputs",
        "- failure_overlap_group_stats.csv",
        "- failure_overlap_sample_manifest.csv",
        "- failure_overlap_separation_auc.csv",
        "- failure_overlap_direction_contributions.csv",
        "- failure_overlap_decision_table.csv",
        "- diagload_overlap_plots/",
    ]
    summary = "\n".join(lines) + "\n"
    (out / "failure_overlap_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_diagload_overlap_analysis",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "no_training": True,
        "no_checkpoint_modification": True,
        "object": "latent_swap_spike_mix_no_compact",
        "old_best": "log_weighted_z_rmse0.5_cos1.0",
        "compare_f": COMPARE_F,
        "calibration_budget": budget,
        "inputs": {
            "negative_recipe_manifest": str(WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "negative_recipe_rescoring_manifest.json"),
            "latent_cache": str(latent_cache),
            "diagload_sweep_results": str(fixed_csv),
        },
        "outputs": {
            "group_stats": str(out / "failure_overlap_group_stats.csv"),
            "sample_manifest": str(out / "failure_overlap_sample_manifest.csv"),
            "separation_auc": str(out / "failure_overlap_separation_auc.csv"),
            "direction_contributions": str(out / "failure_overlap_direction_contributions.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "failure_overlap_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] overlap analysis output: {out}")


if __name__ == "__main__":
    main()
