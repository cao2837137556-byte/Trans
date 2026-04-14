
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit
import frontend100_negative_recipe_rescoring as resc
import frontend100_score_postprocessing as post

PRIMARY_SCORE_VERSION = "hybrid_cosine_default"
NEGATIVE_RECIPE = "latent_swap_spike_mix"


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, np.generic):
        return sanitize_for_json(obj.item())
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    return obj


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: List[str] = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def run_stage1_probe(cmd: List[str]) -> None:
    print("[run] " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def contiguous_runs(indices: np.ndarray) -> List[Tuple[int, int]]:
    idx = np.asarray(indices, dtype=np.int64)
    if len(idx) == 0:
        return []
    runs: List[Tuple[int, int]] = []
    start = int(idx[0])
    prev = int(idx[0])
    for x in idx[1:]:
        x = int(x)
        if x == prev + 1:
            prev = x
            continue
        runs.append((start, prev))
        start = x
        prev = x
    runs.append((start, prev))
    return runs


def detector_style(name: str) -> Dict[str, str]:
    style = {
        "transformer_default_score": {"color": "#2ca02c", "marker": "s"},
        "transformer_tailreg_default_score": {"color": "#1f77b4", "marker": "^"},
        "latent_swap_spike_mix_no_compact_hybrid_cosine_default": {"color": "#d62728", "marker": "o"},
        "mae_latent_contrastive_v1_m0.3_hybrid_cosine_default": {"color": "#ff7f0e", "marker": "D"},
        "mae_latent_contrastive_v1_m0.4_hybrid_cosine_default": {"color": "#9467bd", "marker": "P"},
        "da_default_score": {"color": "#8c564b", "marker": "X"},
    }
    return style.get(name, {"color": "#7f7f7f", "marker": "o"})


def short_policy(policy_name: str) -> str:
    return {
        "fixed_id_q99": "fixed",
        "naive_calibrated_budget5000_target1pct": "naive",
        "det_floor_50pct_min_alarm": "det50",
    }[policy_name]


def plot_tradeoff(rows: pd.DataFrame, out_path: Path, title: str) -> None:
    policy_order = ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"]
    marker_override = {
        "fixed_id_q99": None,
        "naive_calibrated_budget5000_target1pct": "x",
        "det_floor_50pct_min_alarm": None,
    }
    plt.figure(figsize=(9.4, 6.2))
    for detector_label in rows["detector_label"].unique().tolist():
        sub = rows[(rows["detector_label"] == detector_label) & (rows["selection_feasible"])].copy()
        if sub.empty:
            continue
        st = detector_style(detector_label)
        for policy_name in policy_order:
            p = sub[sub["policy_name"] == policy_name]
            if p.empty:
                continue
            r = p.iloc[0]
            marker = marker_override[policy_name] or st["marker"]
            plt.scatter([float(r["ood_alarm_ratio_eval"])], [float(r["attack_detection_high_purity"])], color=st["color"], marker=marker, s=95, linewidths=2.0 if policy_name == "naive_calibrated_budget5000_target1pct" else 1.0)
            plt.text(float(r["ood_alarm_ratio_eval"]) + 0.004, float(r["attack_detection_high_purity"]) + 0.010, f"{detector_label}:{short_policy(policy_name)}", fontsize=7.5)
    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("High-purity attack detection")
    plt.title(title)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_fixed_distribution_compare(detector_data: Dict[str, Dict], labels: List[str], out_path: Path, title: str) -> None:
    eps = 1e-12
    cols = 2
    rows = int(np.ceil(len(labels) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(12.0, 4.1 * rows))
    axes = np.array(axes).reshape(-1)
    for i, label in enumerate(labels):
        ax = axes[i]
        d = detector_data[label]
        ax.hist(np.log10(d["id_scores"] + eps), bins=70, density=True, alpha=0.34, label="ID benign")
        ax.hist(np.log10(d["ood_scores"] + eps), bins=70, density=True, alpha=0.31, label="OOD benign")
        ax.hist(np.log10(d["attack_scores"] + eps), bins=70, density=True, alpha=0.31, label="attack")
        ax.axvline(np.log10(float(d["fixed_threshold"]) + eps), color="black", linestyle="--", linewidth=1.1, label="fixed thr")
        ax.set_title(label)
        ax.set_xlabel("log10(primary score)")
        ax.set_ylabel("density")
        ax.grid(alpha=0.22)
        ax.legend(fontsize=8)
    for j in range(len(labels), len(axes)):
        axes[j].axis("off")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)

def plot_attack_segment_compare(detector_data: Dict[str, Dict], labels: List[str], high_idx: np.ndarray, out_path: Path) -> None:
    eps = 1e-12
    runs = contiguous_runs(high_idx)
    if not runs:
        raise RuntimeError("No stage2 high-purity segment found")
    start, end = sorted(runs, key=lambda t: (t[1] - t[0] + 1), reverse=True)[0]
    x = np.arange(start, end + 1, dtype=np.int64)

    plt.figure(figsize=(10.8, 5.6))
    for label in labels:
        d = detector_data[label]
        ys = d["attack_scores"][start : end + 1]
        thr = float(d["fixed_threshold"])
        plt.plot(x, np.log10(ys + eps), linewidth=1.25, label=f"{label} attack")
        plt.hlines(np.log10(thr + eps), xmin=float(start), xmax=float(end), linestyles="--", linewidth=1.0, alpha=0.85, label=f"{label} fixed thr")
    plt.xlabel("attack window index")
    plt.ylabel("log10(primary score)")
    plt.title(f"High-purity attack segment [{start}, {end}] primary score response")
    plt.grid(alpha=0.25)
    plt.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_score_distributions(selected: Dict[str, Dict], out_path: Path) -> None:
    eps = 1e-12
    plt.figure(figsize=(9.0, 5.8))
    for label, info in selected.items():
        st = detector_style(label)
        vals = np.log10(info["ood_scores"] + eps)
        plt.hist(vals, bins=70, density=True, histtype="step", linewidth=1.8, color=st["color"], label=f"{label} OOD")
    plt.xlabel("log10(primary score)")
    plt.ylabel("density")
    plt.title("OOD benign primary-score distributions")
    plt.grid(alpha=0.25)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def build_scan_df(id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray, high_idx: np.ndarray, mixed_idx: np.ndarray, budget: int, scan_points: int, target_alarm: float) -> Tuple[pd.DataFrame, float, float, np.ndarray]:
    budget = int(min(max(1, budget), len(ood_scores) - 1))
    ood_cal = ood_scores[:budget]
    ood_eval = ood_scores[budget:]
    fixed_thr = float(np.quantile(id_scores, 0.99))
    naive_thr = float(np.quantile(ood_cal, 1.0 - target_alarm))
    ref = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
    thresholds = np.quantile(ref, np.linspace(0.0, 1.0, scan_points))
    thresholds = np.unique(np.concatenate([thresholds, [fixed_thr, naive_thr]])).astype(np.float64)
    rows = [resc.eval_threshold(threshold=float(thr), id_scores=id_scores, ood_scores=ood_scores, ood_eval_scores=ood_eval, attack_scores=attack_scores, high_idx=high_idx, mixed_idx=mixed_idx) for thr in thresholds]
    return pd.DataFrame(rows), fixed_thr, naive_thr, ood_eval


def score_attack(checkpoint: Path, attack_x: np.ndarray, out_npy: Path) -> np.ndarray:
    if out_npy.exists():
        return np.load(out_npy).astype(np.float64)
    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(attack_x), dtype=np.float64)
    for i in range(len(attack_x)):
        if i > 0 and i % 2000 == 0:
            print(f"  attack scoring {checkpoint.name}: {i}/{len(attack_x)}")
        scores[i] = model.process(attack_x[i])
    np.save(out_npy, scores)
    return scores


def add_policy_rows(rows: List[Dict], *, detector: str, detector_label: str, score_label: str, source_mode: str, variant: str, row_fixed: pd.Series, row_naive: pd.Series, row_det50: Optional[pd.Series], auc_value: float) -> None:
    def build(policy_name: str, row: Optional[pd.Series], policy_group: str) -> None:
        if row is None:
            rows.append({"detector": detector, "detector_label": detector_label, "score_label": score_label, "variant": variant, "source_mode": source_mode, "policy_name": policy_name, "policy_group": policy_group, "selection_feasible": False, "threshold": float("nan"), "id_alarm_ratio": float("nan"), "ood_alarm_ratio_full": float("nan"), "ood_alarm_ratio_eval": float("nan"), "attack_detection_all": float("nan"), "attack_detection_high_purity": float("nan"), "attack_detection_boundary": float("nan"), "alarm_reduction_vs_fixed": float("nan"), "detection_retention_vs_fixed": float("nan"), "roc_auc_attack_high_vs_ood_eval": float(auc_value)})
            return
        fixed_alarm = float(row_fixed["ood_alarm_ratio_eval"])
        fixed_det = float(row_fixed["attack_detection_high_purity"])
        alarm = float(row["ood_alarm_ratio_eval"])
        det_hp = float(row["attack_detection_high_purity"])
        rows.append({"detector": detector, "detector_label": detector_label, "score_label": score_label, "variant": variant, "source_mode": source_mode, "policy_name": policy_name, "policy_group": policy_group, "selection_feasible": True, "threshold": float(row["threshold"]), "id_alarm_ratio": float(row["id_alarm_ratio"]), "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]), "ood_alarm_ratio_eval": alarm, "attack_detection_all": float(row["attack_detection_all"]), "attack_detection_high_purity": det_hp, "attack_detection_boundary": float(row["attack_detection_boundary"]), "alarm_reduction_vs_fixed": float(fixed_alarm - alarm), "detection_retention_vs_fixed": float(det_hp / fixed_det) if fixed_det > 0 else float("nan"), "roc_auc_attack_high_vs_ood_eval": float(auc_value)})

    build("fixed_id_q99", row_fixed, "reference")
    build("naive_calibrated_budget5000_target1pct", row_naive, "reference")
    build("det_floor_50pct_min_alarm", row_det50, "constrained_rule")


def score_hybrid_candidate(*, label: str, checkpoint: Path, run_dir: Path, x_id: np.ndarray, x_ood: np.ndarray, x_attack: np.ndarray, rmse_attack_scores: np.ndarray, cache_dir: Path, batch_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict, Dict]:
    cache_prefix = cache_dir / label
    sid_path = cache_prefix.with_name(cache_prefix.name + "_id.npy")
    sood_path = cache_prefix.with_name(cache_prefix.name + "_ood.npy")
    satt_path = cache_prefix.with_name(cache_prefix.name + "_attack.npy")
    meta_path = cache_prefix.with_name(cache_prefix.name + "_meta.json")
    if sid_path.exists() and sood_path.exists() and satt_path.exists() and meta_path.exists():
        meta = load_json(meta_path)
        return np.load(sid_path).astype(np.float64), np.load(sood_path).astype(np.float64), np.load(satt_path).astype(np.float64), meta.get("score_stats", {}), meta.get("latent_meta", {})

    rmse_id = np.load(run_dir / "id_scores.npy").astype(np.float64)
    metrics = load_json(run_dir / "metrics.json")
    ood_name = list(metrics["ood_benign"].keys())[0]
    rmse_ood = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
    model = kit.KitNET.load_checkpoint(checkpoint)
    _, _, _, cos_id, cos_ood, cos_attack, latent_meta = resc.compute_latent_center_distance_scores(model=model, x_id=x_id, x_ood=x_ood, x_attack=x_attack, batch_size=batch_size)
    score_versions, stats = post.make_score_versions(rmse_id, rmse_ood, rmse_attack_scores, cos_id, cos_ood, cos_attack)
    sid, sood, satt = score_versions[PRIMARY_SCORE_VERSION]
    np.save(sid_path, sid)
    np.save(sood_path, sood)
    np.save(satt_path, satt)
    meta = {"score_version": PRIMARY_SCORE_VERSION, "score_stats": stats.get(PRIMARY_SCORE_VERSION, {}), "latent_meta": sanitize_for_json(latent_meta)}
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return sid, sood, satt, meta["score_stats"], meta["latent_meta"]


def run_dry_run(args, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")
    source_root = args.source_root
    crosscapture_data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    train_csv = crosscapture_data / "id_source_100.csv"
    train_labels = crosscapture_data / "no_labels.npy"
    ood_benign_csv = crosscapture_data / "ood_benign_source_100.csv"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"
    dry_mask = float(str(args.mask_ratios).split(",")[0])
    rel_run_tag = f"{args.run_tag}/smoke_m{dry_mask:.1f}_seed{args.seed}"
    cmd = [sys.executable, str(REPO_DIR / "ood" / "stage1_probe.py"), "--run-tag", rel_run_tag, "--train-csv", str(train_csv), "--train-labels", str(train_labels), "--max-ae", str(args.max_ae), "--fm-grace", str(min(args.fm_grace, 64)), "--ad-grace", str(min(args.ad_grace, 192)), "--train-samples", "256", "--id-eval-samples", "128", "--learning-rate", str(args.learning_rate), "--hidden-ratio", str(args.hidden_ratio), "--seed", str(args.seed), "--detector-backend", "transformer_mae_latent_contrastive_v1", "--mae-mask-ratio", str(dry_mask), "--latent-margin", str(args.latent_margin), "--latent-lambda", str(args.latent_lambda), "--latent-contrastive-mode", "v1", "--latent-pooling", str(args.latent_pooling), "--latent-center-ema-alpha", str(args.latent_center_ema_alpha), "--latent-warmup-steps", str(args.latent_warmup_steps), "--latent-neg-prob-swap", "0.5", "--latent-neg-prob-permute", "0.0", "--latent-neg-prob-spike", "0.5", "--latent-neg-prob-replace", "0.0", "--skip-benign", "--skip-attack", "--force-retrain"]
    run_stage1_probe(cmd)
    smoke_run_dir = WORKTREE_ROOT / "runs" / rel_run_tag
    ckpt = Path(load_json(smoke_run_dir / "config.json")["checkpoint"])
    x_id = pd.read_csv(train_csv, header=None, nrows=384).to_numpy(dtype=np.float64)[256:384]
    x_ood = pd.read_csv(ood_benign_csv, header=None, nrows=128).to_numpy(dtype=np.float64)
    x_attack = pd.read_csv(attack_csv, header=None, nrows=128).to_numpy(dtype=np.float64)
    rmse_id = score_attack(ckpt, x_id, out_dir / "smoke_id_scores.npy")
    rmse_ood = score_attack(ckpt, x_ood, out_dir / "smoke_ood_scores.npy")
    rmse_attack = score_attack(ckpt, x_attack, out_dir / "smoke_attack_scores.npy")
    model = kit.KitNET.load_checkpoint(ckpt)
    _, _, _, cos_id, cos_ood, cos_attack, latent_meta = resc.compute_latent_center_distance_scores(
        model=model,
        x_id=x_id,
        x_ood=x_ood,
        x_attack=x_attack,
        batch_size=128,
    )
    score_versions, score_stats = post.make_score_versions(rmse_id, rmse_ood, rmse_attack, cos_id, cos_ood, cos_attack)
    sid, sood, satt = score_versions[PRIMARY_SCORE_VERSION]
    score_meta = score_stats.get(PRIMARY_SCORE_VERSION, {})
    thr = float(np.quantile(sid, 0.99))
    plot_score_distributions({"smoke_mae_latent": {"ood_scores": sood}}, out_dir / "smoke_ood_distribution.png")
    summary_lines = ["# Local Smoke Test Summary", "", "- Imported MAE+latent backend and started training successfully.", "- stage1_probe completed a tiny run with backend `transformer_mae_latent_contrastive_v1`.", "- hybrid_cosine_default scoring executed end-to-end on tiny ID/OOD/attack subsets.", f"- primary fixed threshold (tiny smoke) = {thr:.6f}", f"- latent score stats source = {score_meta.get('stats_source', 'unknown')}", f"- latent meta available = {bool(latent_meta)}", f"- score array sizes: id={len(sid)}, ood={len(sood)}, attack={len(satt)}", "- No path/dimension/bootstrap error observed in smoke path."]
    (out_dir / "local_smoketest_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    manifest = {"stage": "frontend100_mae_latent_v1_smoketest", "generated_at": datetime.now().isoformat(timespec="seconds"), "run_tag": args.run_tag, "seed": args.seed, "dry_run": True, "backend": "transformer_mae_latent_contrastive_v1", "mask_ratio": dry_mask, "latent_margin": args.latent_margin, "latent_lambda": args.latent_lambda, "negative_recipe": NEGATIVE_RECIPE, "score_version": PRIMARY_SCORE_VERSION, "smoke_run_dir": str(smoke_run_dir)}
    (out_dir / "config.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] mae_latent_v1 smoke output: {out_dir}")

def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Minimal MAE + latent contrastive fusion experiment on frontend100 stronger OOD.")
    parser.add_argument("--run-tag", default=f"frontend100_mae_latent_v1_{today}")
    parser.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mask-ratios", default="0.3,0.4")
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--fm-grace", type=int, default=2000)
    parser.add_argument("--ad-grace", type=int, default=6000)
    parser.add_argument("--train-samples", type=int, default=8000)
    parser.add_argument("--id-eval-samples", type=int, default=5000)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--latent-margin", type=float, default=5.0)
    parser.add_argument("--latent-lambda", type=float, default=0.5)
    parser.add_argument("--latent-center-ema-alpha", type=float, default=0.01)
    parser.add_argument("--latent-warmup-steps", type=int, default=1000)
    parser.add_argument("--latent-pooling", default="mean")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--force-retrain", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    if args.dry_run:
        run_dry_run(args, out_dir)
        return

    mask_ratios = [float(x.strip()) for x in str(args.mask_ratios).split(",") if x.strip()]
    if not mask_ratios:
        raise ValueError("mask-ratios cannot be empty")

    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "mae_latent_v1_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_rmse_dir = out_dir / "cache_attack_scores"
    cache_rmse_dir.mkdir(parents=True, exist_ok=True)
    cache_primary_dir = out_dir / "cache_primary_scores"
    cache_primary_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source_root = args.source_root
    crosscapture_data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2_joint = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2_manifest = load_json(stage2_joint / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2_manifest)
    high_idx = stage2_idx["high"]
    mixed_idx = stage2_idx["mixed"]
    if len(high_idx) == 0:
        raise RuntimeError("stage2 high-purity indices are empty")

    train_csv = crosscapture_data / "id_source_100.csv"
    train_labels = crosscapture_data / "no_labels.npy"
    ood_benign_csv = crosscapture_data / "ood_benign_source_100.csv"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"
    if not train_csv.exists() or not ood_benign_csv.exists() or not attack_csv.exists():
        raise FileNotFoundError("Missing one of train/ood/attack csv files for frontend100 mainline")

    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)
    x_id_eval = pd.read_csv(train_csv, header=None, nrows=(args.train_samples + args.id_eval_samples)).to_numpy(dtype=np.float64)[args.train_samples : args.train_samples + args.id_eval_samples]
    x_ood = pd.read_csv(ood_benign_csv, header=None).to_numpy(dtype=np.float64)

    latent_ablation_manifest = load_json(WORKTREE_ROOT / "runs" / "frontend100_negative_semantics_ablation_2026-04-05" / "negative_semantics_ablation_manifest.json")
    no_compact_info = latent_ablation_manifest["detector_info"][NEGATIVE_RECIPE]
    no_compact_run_dir = Path(no_compact_info["run_dir"])
    no_compact_ckpt = Path(no_compact_info["checkpoint"])
    no_compact_attack_rmse = np.load(Path(no_compact_info["attack_score_file"])).astype(np.float64)

    baseline_runs = {
        "transformer_default_score": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"transformer_seed{args.seed}",
        "transformer_tailreg_default_score": source_root / "runs" / "frontend100_tailreg_hparam_scan_2026-03-28" / f"tailreg_l0.2_k1.0_seed{args.seed}",
        "da_default_score": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"da_seed{args.seed}",
    }
    baseline_attack = {
        "transformer_default_score": stage1_joint / "transformer_attack_scores.npy",
        "transformer_tailreg_default_score": stage1_joint / "transformer_tailreg_attack_scores.npy",
        "da_default_score": stage1_joint / "da_attack_scores.npy",
    }
    for label, path in baseline_runs.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing baseline run: {path}")
        if not baseline_attack[label].exists():
            raise FileNotFoundError(f"Missing baseline attack scores: {baseline_attack[label]}")

    fusion_entries: List[Dict] = []
    for mask_ratio in mask_ratios:
        det_label = f"mae_latent_contrastive_v1_m{mask_ratio:.1f}_hybrid_cosine_default"
        rel_run_tag = f"{args.run_tag}/{det_label}_seed{args.seed}"
        run_dir = WORKTREE_ROOT / "runs" / rel_run_tag
        cmd = [sys.executable, str(REPO_DIR / "ood" / "stage1_probe.py"), "--run-tag", rel_run_tag, "--train-csv", str(train_csv), "--train-labels", str(train_labels), "--max-ae", str(args.max_ae), "--fm-grace", str(args.fm_grace), "--ad-grace", str(args.ad_grace), "--train-samples", str(args.train_samples), "--id-eval-samples", str(args.id_eval_samples), "--learning-rate", str(args.learning_rate), "--hidden-ratio", str(args.hidden_ratio), "--seed", str(args.seed), "--detector-backend", "transformer_mae_latent_contrastive_v1", "--mae-mask-ratio", str(mask_ratio), "--latent-margin", str(args.latent_margin), "--latent-lambda", str(args.latent_lambda), "--latent-contrastive-mode", "v1", "--latent-pooling", str(args.latent_pooling), "--latent-center-ema-alpha", str(args.latent_center_ema_alpha), "--latent-warmup-steps", str(args.latent_warmup_steps), "--latent-neg-prob-swap", "0.5", "--latent-neg-prob-permute", "0.0", "--latent-neg-prob-spike", "0.5", "--latent-neg-prob-replace", "0.0", "--benign-dataset", f"iot23_ood_benign|{ood_benign_csv}", "--skip-attack"]
        if args.force_retrain:
            cmd.append("--force-retrain")
        run_stage1_probe(cmd)
        ckpt = Path(load_json(run_dir / "config.json")["checkpoint"])
        attack_rmse = score_attack(ckpt, x_attack, cache_rmse_dir / f"{det_label}_attack_rmse.npy")
        fusion_entries.append({"detector": "transformer_mae_latent_contrastive_v1", "detector_label": det_label, "variant": f"mask={mask_ratio:.1f}", "mask_ratio": mask_ratio, "run_dir": run_dir, "checkpoint": ckpt, "attack_rmse": attack_rmse, "source_mode": "trained_now"})

    entries: List[Dict] = []
    for label in ["transformer_default_score", "transformer_tailreg_default_score", "da_default_score"]:
        run_dir = baseline_runs[label]
        metrics = load_json(run_dir / "metrics.json")
        ood_name = list(metrics["ood_benign"].keys())[0]
        entries.append({"detector": label.replace("_default_score", ""), "detector_label": label, "variant": "official_default_score", "score_label": "default_score", "run_dir": run_dir, "checkpoint": Path(load_json(run_dir / "config.json")["checkpoint"]), "source_mode": "baseline_reuse", "id_scores": np.load(run_dir / "id_scores.npy").astype(np.float64), "ood_scores": np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64), "attack_scores": np.load(baseline_attack[label]).astype(np.float64), "score_meta": {"stats_source": "model default score from existing run"}, "latent_meta": None})

    no_compact_id, no_compact_ood, no_compact_attack, no_compact_score_meta, no_compact_latent_meta = score_hybrid_candidate(label="latent_swap_spike_mix_no_compact_hybrid_cosine_default", checkpoint=no_compact_ckpt, run_dir=no_compact_run_dir, x_id=x_id_eval, x_ood=x_ood, x_attack=x_attack, rmse_attack_scores=no_compact_attack_rmse, cache_dir=cache_primary_dir, batch_size=args.batch_size)
    entries.append({"detector": "transformer_latent_no_compact", "detector_label": "latent_swap_spike_mix_no_compact_hybrid_cosine_default", "variant": "no_compact", "score_label": PRIMARY_SCORE_VERSION, "run_dir": no_compact_run_dir, "checkpoint": no_compact_ckpt, "source_mode": "trained_now_reuse", "id_scores": no_compact_id, "ood_scores": no_compact_ood, "attack_scores": no_compact_attack, "score_meta": no_compact_score_meta, "latent_meta": no_compact_latent_meta})

    for ent in fusion_entries:
        sid, sood, satt, score_meta, latent_meta = score_hybrid_candidate(label=ent["detector_label"], checkpoint=ent["checkpoint"], run_dir=ent["run_dir"], x_id=x_id_eval, x_ood=x_ood, x_attack=x_attack, rmse_attack_scores=ent["attack_rmse"], cache_dir=cache_primary_dir, batch_size=args.batch_size)
        entries.append({"detector": ent["detector"], "detector_label": ent["detector_label"], "variant": ent["variant"], "score_label": PRIMARY_SCORE_VERSION, "run_dir": ent["run_dir"], "checkpoint": ent["checkpoint"], "source_mode": ent["source_mode"], "id_scores": sid, "ood_scores": sood, "attack_scores": satt, "score_meta": score_meta, "latent_meta": latent_meta})
    results_rows: List[Dict] = []
    detector_info: Dict[str, Dict] = {}
    for ent in entries:
        scan_df, fixed_thr, naive_thr, ood_eval = build_scan_df(id_scores=ent["id_scores"], ood_scores=ent["ood_scores"], attack_scores=ent["attack_scores"], high_idx=high_idx, mixed_idx=mixed_idx, budget=args.calibration_budget, scan_points=args.scan_points, target_alarm=args.calibration_target)
        fixed_row = scan_df.iloc[(np.abs(scan_df["threshold"] - fixed_thr)).argmin()]
        naive_row = scan_df.iloc[(np.abs(scan_df["threshold"] - naive_thr)).argmin()]
        det50_row = resc.choose_detection_floor(scan_df, 0.50)
        auc_value = resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=ent["attack_scores"][high_idx])
        add_policy_rows(results_rows, detector=ent["detector"], detector_label=ent["detector_label"], score_label=ent["score_label"], source_mode=ent["source_mode"], variant=ent["variant"], row_fixed=fixed_row, row_naive=naive_row, row_det50=det50_row, auc_value=auc_value)
        detector_info[ent["detector_label"]] = {
            "detector": ent["detector"],
            "variant": ent["variant"],
            "score_label": ent["score_label"],
            "source_mode": ent["source_mode"],
            "run_dir": str(ent["run_dir"]),
            "checkpoint": str(ent["checkpoint"]),
            "fixed_threshold": fixed_thr,
            "naive_threshold": naive_thr,
            "id_scores": ent["id_scores"],
            "ood_scores": ent["ood_scores"],
            "attack_scores": ent["attack_scores"],
            "id_stats": resc.score_stats(ent["id_scores"]),
            "ood_stats": resc.score_stats(ent["ood_scores"]),
            "attack_stats": resc.score_stats(ent["attack_scores"]),
            "score_meta": ent["score_meta"],
            "latent_meta": ent["latent_meta"],
            "roc_auc_attack_high_vs_ood_eval": float(auc_value),
        }

    results_df = pd.DataFrame(results_rows).sort_values(["detector_label", "policy_name"]).reset_index(drop=True)
    results_df.to_csv(out_dir / "mae_latent_v1_results.csv", index=False)
    results_df.to_csv(out_dir / "results.csv", index=False)

    fixed_rows = results_df[(results_df["policy_name"] == "fixed_id_q99") & (results_df["selection_feasible"])].copy()
    fusion_fixed = fixed_rows[fixed_rows["detector"] == "transformer_mae_latent_contrastive_v1"].copy()
    fusion_fixed["fixed_utility"] = fusion_fixed["attack_detection_high_purity"] - fusion_fixed["ood_alarm_ratio_eval"]
    best_fusion = fusion_fixed.sort_values(["fixed_utility", "attack_detection_high_purity", "ood_alarm_ratio_eval"], ascending=[False, False, True]).iloc[0]
    best_label = str(best_fusion["detector_label"])
    best_mask = 0.3 if "m0.3" in best_label else 0.4

    show_cols = ["detector_label", "score_label", "variant", "policy_name", "threshold", "ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "alarm_reduction_vs_fixed", "detection_retention_vs_fixed", "roc_auc_attack_high_vs_ood_eval"]
    results_md = md_table(results_df[show_cols])
    (out_dir / "mae_latent_v1_results.md").write_text(results_md, encoding="utf-8")
    (out_dir / "results.md").write_text(results_md, encoding="utf-8")

    plot_tradeoff(results_df, plot_dir / "tradeoff_main_compare.png", title="Transformer vs tailreg vs latent no-compact vs MAE+latent vs dA")
    no_compact_fusion = results_df[results_df["detector_label"].isin(["latent_swap_spike_mix_no_compact_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.3_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.4_hybrid_cosine_default"])].copy()
    plot_tradeoff(no_compact_fusion, plot_dir / "no_compact_vs_fusion_compare.png", title="No-compact latent vs MAE+latent fusion")
    plot_fixed_distribution_compare(detector_info, ["latent_swap_spike_mix_no_compact_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.3_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.4_hybrid_cosine_default", "transformer_tailreg_default_score"], plot_dir / "score_distribution_compare.png", title="Primary-score distributions at fixed threshold")
    plot_score_distributions({k: detector_info[k] for k in ["latent_swap_spike_mix_no_compact_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.3_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.4_hybrid_cosine_default", "transformer_tailreg_default_score", "da_default_score"]}, plot_dir / "ood_score_distribution_compare.png")
    plot_attack_segment_compare(detector_info, ["latent_swap_spike_mix_no_compact_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.3_hybrid_cosine_default", "mae_latent_contrastive_v1_m0.4_hybrid_cosine_default", "da_default_score"], high_idx, plot_dir / "attack_segment_compare.png")

    def get_row(label: str, policy: str) -> pd.Series:
        sub = results_df[(results_df["detector_label"] == label) & (results_df["policy_name"] == policy) & (results_df["selection_feasible"])]
        if sub.empty:
            raise RuntimeError(f"Missing row: {label} / {policy}")
        return sub.iloc[0]

    no_compact_fixed = get_row("latent_swap_spike_mix_no_compact_hybrid_cosine_default", "fixed_id_q99")
    best_fixed = get_row(best_label, "fixed_id_q99")
    tailreg_fixed = get_row("transformer_tailreg_default_score", "fixed_id_q99")
    da_fixed = get_row("da_default_score", "fixed_id_q99")
    mask03_fixed = get_row("mae_latent_contrastive_v1_m0.3_hybrid_cosine_default", "fixed_id_q99")
    mask04_fixed = get_row("mae_latent_contrastive_v1_m0.4_hybrid_cosine_default", "fixed_id_q99")
    det50_best = get_row(best_label, "det_floor_50pct_min_alarm")
    det50_no_compact = get_row("latent_swap_spike_mix_no_compact_hybrid_cosine_default", "det_floor_50pct_min_alarm")
    det50_tailreg = get_row("transformer_tailreg_default_score", "det_floor_50pct_min_alarm")
    naive_best = get_row(best_label, "naive_calibrated_budget5000_target1pct")
    lines: List[str] = []
    lines.append("# MAE + Latent Contrastive v1 Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("- Mainline: original-frontend 100D + stronger OOD.")
    lines.append(f"- Seed: {args.seed} (single-seed mechanism check).")
    lines.append(f"- Locked negative recipe: `{NEGATIVE_RECIPE}` (swap=0.5, spike=0.5, permute=0, replace=0).")
    lines.append(f"- Latent parameters fixed: margin={args.latent_margin:.1f}, lambda={args.latent_lambda:.1f}.")
    lines.append(f"- MAE mask scan: {mask_ratios}.")
    lines.append(f"- Primary score: `{PRIMARY_SCORE_VERSION}`.")
    lines.append("- Positive path: masked input -> full reconstruction target; negative path: full synthetic negative, no mask.")
    lines.append("")
    lines.append("## Required answers")
    lines.append("1. Does MAE+latent move closer than pure latent no-compact to lower alarm without obvious detection damage?")
    lines.append(f"- no_compact fixed: alarm={float(no_compact_fixed['ood_alarm_ratio_eval']):.4f}, det={float(no_compact_fixed['attack_detection_high_purity']):.4f}; best fusion fixed ({best_label}): alarm={float(best_fixed['ood_alarm_ratio_eval']):.4f}, det={float(best_fixed['attack_detection_high_purity']):.4f}.")
    lines.append("2. Which mask ratio looks healthier?")
    lines.append(f"- mask=0.3 fixed: alarm={float(mask03_fixed['ood_alarm_ratio_eval']):.4f}, det={float(mask03_fixed['attack_detection_high_purity']):.4f}; mask=0.4 fixed: alarm={float(mask04_fixed['ood_alarm_ratio_eval']):.4f}, det={float(mask04_fixed['attack_detection_high_purity']):.4f}.")
    lines.append("3. Relative to transformer_tailreg, is the trade-off stronger?")
    lines.append(f"- tailreg fixed: alarm={float(tailreg_fixed['ood_alarm_ratio_eval']):.4f}, det={float(tailreg_fixed['attack_detection_high_purity']):.4f}; best fusion fixed delta: alarm={float(best_fixed['ood_alarm_ratio_eval']) - float(tailreg_fixed['ood_alarm_ratio_eval']):+.4f}, det={float(best_fixed['attack_detection_high_purity']) - float(tailreg_fixed['attack_detection_high_purity']):+.4f}.")
    lines.append("4. Relative to dA, does it enter a more realistic competitive region?")
    lines.append(f"- dA fixed: alarm={float(da_fixed['ood_alarm_ratio_eval']):.4f}, det={float(da_fixed['attack_detection_high_purity']):.4f}; best fusion delta: alarm={float(best_fixed['ood_alarm_ratio_eval']) - float(da_fixed['ood_alarm_ratio_eval']):+.4f}, det={float(best_fixed['attack_detection_high_purity']) - float(da_fixed['attack_detection_high_purity']):+.4f}.")
    lines.append("5. Is this worth a next multi-seed round?")
    lines.append("- Judge from fixed and det50 together; this round is mechanism validation only.")
    lines.append("")
    lines.append("## Additional notes")
    lines.append(f"- Best fusion by fixed utility: {best_label}.")
    lines.append(f"- det50 no_compact: alarm={float(det50_no_compact['ood_alarm_ratio_eval']):.4f}, det={float(det50_no_compact['attack_detection_high_purity']):.4f}; best fusion det50: alarm={float(det50_best['ood_alarm_ratio_eval']):.4f}, det={float(det50_best['attack_detection_high_purity']):.4f}; tailreg det50: alarm={float(det50_tailreg['ood_alarm_ratio_eval']):.4f}, det={float(det50_tailreg['attack_detection_high_purity']):.4f}.")
    lines.append(f"- naive calibrated best fusion: alarm={float(naive_best['ood_alarm_ratio_eval']):.4f}, det={float(naive_best['attack_detection_high_purity']):.4f}.")
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "mae_latent_v1_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    detector_info_small = {}
    for key, value in detector_info.items():
        detector_info_small[key] = {
            "detector": value["detector"],
            "variant": value["variant"],
            "score_label": value["score_label"],
            "source_mode": value["source_mode"],
            "run_dir": value["run_dir"],
            "checkpoint": value["checkpoint"],
            "fixed_threshold": value["fixed_threshold"],
            "naive_threshold": value["naive_threshold"],
            "id_stats": value["id_stats"],
            "ood_stats": value["ood_stats"],
            "attack_stats": value["attack_stats"],
            "score_meta": value["score_meta"],
            "latent_meta": value["latent_meta"],
            "roc_auc_attack_high_vs_ood_eval": value["roc_auc_attack_high_vs_ood_eval"],
        }

    manifest = {
        "stage": "frontend100_mae_latent_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source_root),
        "seed": args.seed,
        "backend": "transformer_mae_latent_contrastive_v1",
        "negative_recipe": NEGATIVE_RECIPE,
        "primary_score": PRIMARY_SCORE_VERSION,
        "mask_ratios": mask_ratios,
        "latent_margin": args.latent_margin,
        "latent_lambda": args.latent_lambda,
        "policy_set": ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"],
        "calibration": {"budget": args.calibration_budget, "target_alarm": args.calibration_target, "scan_points": args.scan_points},
        "train_config": {"max_ae": args.max_ae, "fm_grace": args.fm_grace, "ad_grace": args.ad_grace, "train_samples": args.train_samples, "id_eval_samples": args.id_eval_samples, "learning_rate": args.learning_rate, "hidden_ratio": args.hidden_ratio, "latent_pooling": args.latent_pooling, "latent_center_ema_alpha": args.latent_center_ema_alpha, "latent_warmup_steps": args.latent_warmup_steps, "negative_probs": {"swap": 0.5, "permute": 0.0, "spike": 0.5, "replace": 0.0}, "force_retrain": bool(args.force_retrain)},
        "data_sources": {"train_csv": str(train_csv), "ood_benign_csv": str(ood_benign_csv), "attack_csv": str(attack_csv), "stage2_manifest": str(stage2_joint / "attack_manifest_stage2.json"), "latent_no_compact_run_dir": str(no_compact_run_dir), "baseline_runs": {k: str(v) for k, v in baseline_runs.items()}, "baseline_attack_scores": {k: str(v) for k, v in baseline_attack.items()}},
        "stage2_subsets": {"high_purity_count": int(len(high_idx)), "boundary_mixed_count": int(len(mixed_idx)), "strong_bins": stage2_manifest["selected_bins"]["strong_bins"], "mixed_bins": stage2_manifest["selected_bins"]["mixed_bins"]},
        "recommended": {"detector_label": best_label, "mask_ratio": best_mask, "selection_criterion": "fixed_utility = detection - alarm"},
        "detector_info": sanitize_for_json(detector_info_small),
        "outputs": {"results_csv": str(out_dir / "mae_latent_v1_results.csv"), "results_md": str(out_dir / "mae_latent_v1_results.md"), "summary_md": str(out_dir / "mae_latent_v1_summary.md"), "plots_dir": str(plot_dir)},
    }
    manifest = sanitize_for_json(manifest)
    (out_dir / "mae_latent_v1_config_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "config.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] mae_latent_v1 experiment output: {out_dir}")


if __name__ == "__main__":
    main()
