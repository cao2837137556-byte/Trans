from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = REPO_DIR.parent
OOD_DIR = Path(__file__).resolve().parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import KitNET as kit
import frontend100_negative_recipe_rescoring as resc


@dataclass
class V3Run:
    label: str
    lambda_compact: float
    run_dir: Path
    checkpoint: Path
    attack_rmse_file: Path


def run_cmd(cmd: List[str], cwd: Path) -> None:
    print("[run] " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd))


def parse_lc(text: str) -> List[float]:
    vals = sorted(set(float(x.strip()) for x in text.split(",") if x.strip()))
    if not vals:
        raise ValueError("lambda_compacts cannot be empty")
    return vals


def save_md_table(df: pd.DataFrame, path: Path, cols: List[str]) -> None:
    path.write_text(resc.md_table(df[cols]), encoding="utf-8")


def stage2_indices(stage2_manifest: Dict, smoke: bool, attack_len: int) -> Tuple[np.ndarray, np.ndarray]:
    if smoke:
        high_take = max(1, min(attack_len, attack_len // 2))
        return np.arange(high_take, dtype=np.int64), np.array([], dtype=np.int64)
    idx = resc.build_stage2_indices(stage2_manifest)
    return idx["high"], idx["mixed"]


def contiguous_runs(indices: np.ndarray) -> List[Tuple[int, int]]:
    idx = np.asarray(indices, dtype=np.int64)
    if len(idx) == 0:
        return []
    runs: List[Tuple[int, int]] = []
    s = int(idx[0])
    p = int(idx[0])
    for x in idx[1:]:
        x = int(x)
        if x == p + 1:
            p = x
            continue
        runs.append((s, p))
        s = x
        p = x
    runs.append((s, p))
    return runs


def score_attack(checkpoint: Path, attack_x: np.ndarray, out_file: Path) -> np.ndarray:
    if out_file.exists():
        return np.load(out_file).astype(np.float64)
    model = kit.KitNET.load_checkpoint(checkpoint)
    out = np.zeros(len(attack_x), dtype=np.float64)
    for i in range(len(attack_x)):
        if i > 0 and i % 2000 == 0:
            print(f"  attack scoring: {i}/{len(attack_x)}")
        out[i] = model.process(attack_x[i])
    np.save(out_file, out)
    return out


def lc_label(lc: float) -> str:
    return f"latent_compact_v3_lc{lc:.2f}".replace(".", "p")


def plot_tradeoff(df: pd.DataFrame, out_path: Path) -> None:
    plt.figure(figsize=(10.5, 6.0))
    policy_order = ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"]
    marker = {
        "fixed_id_q99": "s",
        "naive_calibrated_budget5000_target1pct": "x",
        "det_floor_50pct_min_alarm": "o",
    }
    labels = list(dict.fromkeys(df["candidate_label"].tolist()))
    cmap = plt.get_cmap("tab10")
    for i, lbl in enumerate(labels):
        sub = df[(df["candidate_label"] == lbl) & (df["selection_feasible"])]
        if sub.empty:
            continue
        color = cmap(i % 10)
        for p in policy_order:
            row = sub[sub["policy_name"] == p]
            if row.empty:
                continue
            r = row.iloc[0]
            x = float(r["ood_alarm_ratio_eval"])
            y = float(r["attack_detection_high_purity"])
            plt.scatter(x, y, marker=marker[p], color=color, s=90, linewidths=1.5 if p == "naive_calibrated_budget5000_target1pct" else 1.0)
            short = {"fixed_id_q99": "fixed", "naive_calibrated_budget5000_target1pct": "naive", "det_floor_50pct_min_alarm": "det50"}[p]
            plt.text(x + 0.002, y + 0.002, f"{lbl}:{short}", fontsize=8)
    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("High-purity attack detection")
    plt.title("Latent Compact v3 Trade-off (hybrid_cosine)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_distribution(det_data: Dict[str, Dict], labels: List[str], key: str, title: str, out_path: Path) -> None:
    plt.figure(figsize=(10.5, 5.8))
    for lbl in labels:
        arr = np.asarray(det_data[lbl][key], dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        if len(arr) == 0:
            continue
        plt.hist(arr, bins=70, density=True, alpha=0.28, label=lbl)
    plt.xlabel("hybrid_cosine score")
    plt.ylabel("density")
    plt.title(title)
    plt.grid(alpha=0.25)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_attack_segment(det_data: Dict[str, Dict], labels: List[str], high_idx: np.ndarray, out_path: Path) -> None:
    runs = contiguous_runs(high_idx)
    if not runs:
        return
    runs = sorted(runs, key=lambda t: (t[1] - t[0] + 1), reverse=True)
    start, end = runs[0]
    x = np.arange(start, end + 1, dtype=np.int64)
    plt.figure(figsize=(11.0, 5.8))
    for lbl in labels:
        y = np.asarray(det_data[lbl]["attack_scores"], dtype=np.float64)[start : end + 1]
        thr = float(det_data[lbl]["fixed_thr"])
        plt.plot(x, y, linewidth=1.2, label=f"{lbl} attack")
        plt.hlines(thr, xmin=float(start), xmax=float(end), linestyles="--", linewidth=1.0, alpha=0.8, label=f"{lbl} fixed thr")
    plt.xlabel("attack window index")
    plt.ylabel("hybrid_cosine score")
    plt.title(f"High-purity attack segment [{start}, {end}]")
    plt.grid(alpha=0.25)
    plt.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def default_source_root() -> Path:
    return WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"


def train_v3_models(args, out_dir: Path, attack_x: np.ndarray, lambda_compacts: List[float]) -> List[V3Run]:
    cache_dir = out_dir / "cache_attack_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    train_csv = args.train_csv
    train_labels = args.train_labels
    runs: List[V3Run] = []
    for lc in lambda_compacts:
        label = lc_label(lc)
        rel_run_tag = f"{args.run_tag}/{label}_seed{args.seed}"
        run_dir = WORKTREE_ROOT / "runs" / rel_run_tag
        cmd = [
            sys.executable,
            str(REPO_DIR / "ood" / "stage1_probe.py"),
            "--run-tag",
            rel_run_tag,
            "--train-csv",
            str(train_csv),
            "--train-labels",
            str(train_labels),
            "--max-ae",
            str(args.max_ae),
            "--fm-grace",
            str(args.fm_grace),
            "--ad-grace",
            str(args.ad_grace),
            "--train-samples",
            str(args.train_samples),
            "--id-eval-samples",
            str(args.id_eval_samples),
            "--learning-rate",
            str(args.learning_rate),
            "--hidden-ratio",
            str(args.hidden_ratio),
            "--seed",
            str(args.seed),
            "--detector-backend",
            "transformer_latent_contrastive_compact_v2",
            "--latent-margin",
            str(args.margin),
            "--latent-lambda",
            str(args.lambda_margin),
            "--latent-lambda-compact",
            str(lc),
            "--latent-center-ema-alpha",
            str(args.latent_center_ema_alpha),
            "--latent-warmup-steps",
            str(args.latent_warmup_steps),
            "--latent-contrastive-mode",
            "compact_v3",
            "--latent-pooling",
            "mean",
            "--latent-neg-prob-swap",
            "0.5",
            "--latent-neg-prob-permute",
            "0.0",
            "--latent-neg-prob-spike",
            "0.5",
            "--latent-neg-prob-replace",
            "0.0",
            "--skip-benign",
            "--skip-attack",
        ]
        if args.force_retrain:
            cmd.append("--force-retrain")
        run_cmd(cmd, WORKTREE_ROOT)
        ckpt = run_dir / f"kitnet_transformer_latent_contrastive_compact_v2_seed{args.seed}.ckpt"
        if not ckpt.exists():
            raise FileNotFoundError(f"Missing checkpoint: {ckpt}")
        attack_file = cache_dir / f"{label}_seed{args.seed}_attack_scores.npy"
        score_attack(ckpt, attack_x, attack_file)
        runs.append(V3Run(label=label, lambda_compact=lc, run_dir=run_dir, checkpoint=ckpt, attack_rmse_file=attack_file))
    return runs


def load_existing_v3_runs(args, out_dir: Path, attack_x: np.ndarray, lambda_compacts: List[float]) -> List[V3Run]:
    cache_dir = out_dir / "cache_attack_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    runs: List[V3Run] = []
    for lc in lambda_compacts:
        label = lc_label(lc)
        run_dir = out_dir / f"{label}_seed{args.seed}"
        ckpt = run_dir / f"kitnet_transformer_latent_contrastive_compact_v2_seed{args.seed}.ckpt"
        if not ckpt.exists():
            raise FileNotFoundError(f"Missing checkpoint for --skip-train mode: {ckpt}")
        attack_file = cache_dir / f"{label}_seed{args.seed}_attack_scores.npy"
        if not attack_file.exists():
            score_attack(ckpt, attack_x, attack_file)
        runs.append(V3Run(label=label, lambda_compact=lc, run_dir=run_dir, checkpoint=ckpt, attack_rmse_file=attack_file))
    return runs


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    p = argparse.ArgumentParser(description="Latent compact v3 protocol runner (train + rescoring + v3 artifacts).")
    p.add_argument("--run-tag", default=f"frontend100_latent_compact_v3_{today}")
    p.add_argument("--source-root", type=Path, default=default_source_root())
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--margin", type=float, default=5.0)
    p.add_argument("--lambda-margin", type=float, default=0.5)
    p.add_argument("--lambda-compacts", default="0.01,0.05,0.1,0.5")
    p.add_argument("--latent-center-ema-alpha", type=float, default=0.99)
    p.add_argument("--latent-warmup-steps", type=int, default=1000)
    p.add_argument("--max-ae", type=int, default=10)
    p.add_argument("--fm-grace", type=int, default=2000)
    p.add_argument("--ad-grace", type=int, default=6000)
    p.add_argument("--train-samples", type=int, default=8000)
    p.add_argument("--id-eval-samples", type=int, default=5000)
    p.add_argument("--learning-rate", type=float, default=0.1)
    p.add_argument("--hidden-ratio", type=float, default=0.75)
    p.add_argument("--scan-points", type=int, default=901)
    p.add_argument("--calibration-budget", type=int, default=5000)
    p.add_argument("--calibration-target", type=float, default=0.01)
    p.add_argument("--det-floor", type=float, default=0.5)
    p.add_argument("--batch-size", type=int, default=1024)
    p.add_argument(
        "--negative-semantics-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend100_negative_semantics_ablation_2026-04-05",
    )
    p.add_argument("--force-retrain", action="store_true")
    p.add_argument("--force-recompute-latent", action="store_true")
    p.add_argument("--skip-train", action="store_true")
    p.add_argument("--smoke-test", action="store_true")
    p.add_argument("--smoke-max-rows", type=int, default=256)
    args = p.parse_args()

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "latent_compact_v3_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(os.sys.argv) + "\n", encoding="utf-8")

    source_root = args.source_root
    crosscapture = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2_joint = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    args.train_csv = crosscapture / "id_source_100.csv"
    args.train_labels = crosscapture / "no_labels.npy"
    ood_csv = crosscapture / "ood_benign_source_100.csv"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"
    for fp in [args.train_csv, ood_csv, attack_csv]:
        if not fp.exists():
            raise FileNotFoundError(f"Missing required file: {fp}")

    attack_x = pd.read_csv(attack_csv, header=None, nrows=(args.smoke_max_rows if args.smoke_test else None)).to_numpy(dtype=np.float64)
    if len(attack_x) == 0:
        raise RuntimeError("attack input is empty")

    lambda_compacts = parse_lc(args.lambda_compacts)
    if args.smoke_test:
        lambda_compacts = [lambda_compacts[0]]
        args.train_samples = min(args.train_samples, 256)
        args.id_eval_samples = min(args.id_eval_samples, 128)
        args.calibration_budget = min(args.calibration_budget, 64)
        args.scan_points = min(args.scan_points, 101)
        args.fm_grace = min(args.fm_grace, max(16, args.train_samples // 3))
        args.ad_grace = min(args.ad_grace, max(1, args.train_samples - args.fm_grace))

    if args.skip_train:
        v3_runs = load_existing_v3_runs(args, out_dir, attack_x, lambda_compacts)
    else:
        v3_runs = train_v3_models(args, out_dir, attack_x, lambda_compacts)

    if args.smoke_test:
        ck = v3_runs[0].checkpoint
        model = kit.KitNET.load_checkpoint(ck)
        x_id_small = pd.read_csv(args.train_csv, header=None, nrows=(args.train_samples + args.id_eval_samples)).to_numpy(dtype=np.float64)[args.train_samples : args.train_samples + args.id_eval_samples]
        x_ood_small = pd.read_csv(ood_csv, header=None, nrows=args.smoke_max_rows).to_numpy(dtype=np.float64)
        l2_id, l2_ood, _, cos_id, cos_ood, _, _ = resc.compute_latent_center_distance_scores(model, x_id_small, x_ood_small, attack_x, batch_size=min(args.batch_size, 256))
        rmse_id = np.load(v3_runs[0].run_dir / "id_scores.npy").astype(np.float64)
        rmse_ood = np.zeros(len(x_ood_small), dtype=np.float64)
        for i in range(len(x_ood_small)):
            rmse_ood[i] = model.process(x_ood_small[i])
        h_id = resc.zscore(rmse_id, float(np.mean(rmse_id)), resc.safe_std(rmse_id)) + resc.zscore(cos_id, float(np.mean(cos_id)), resc.safe_std(cos_id))
        h_ood = resc.zscore(rmse_ood, float(np.mean(rmse_id)), resc.safe_std(rmse_id)) + resc.zscore(cos_ood, float(np.mean(cos_id)), resc.safe_std(cos_id))
        smoke_lines = [
            "# Local Smoke Test Summary",
            "",
            f"- trained candidate: {v3_runs[0].label}",
            f"- checkpoint exists: {ck.exists()}",
            f"- latent arrays: id={l2_id.shape}, ood={l2_ood.shape}",
            f"- hybrid_cosine finite ratio (id)={float(np.mean(np.isfinite(h_id))):.4f}, (ood)={float(np.mean(np.isfinite(h_ood))):.4f}",
            "- smoke status: PASS (import/path/center/hybrid pipeline executed).",
        ]
        (out_dir / "local_smoketest_summary.md").write_text("\n".join(smoke_lines) + "\n", encoding="utf-8")
        (out_dir / "summary.md").write_text("\n".join(smoke_lines) + "\n", encoding="utf-8")
        (out_dir / "config.json").write_text(json.dumps({"smoke_test": True, "run_tag": args.run_tag}, indent=2), encoding="utf-8")
        (out_dir / "results.csv").write_text("candidate_label,status\n" + f"{v3_runs[0].label},smoke_pass\n", encoding="utf-8")
        print(f"[done] smoke output: {out_dir}")
        return

    extra_specs = []
    for r in v3_runs:
        extra_specs.append(
            "|".join(
                [
                    r.label,
                    "transformer_latent_contrastive_compact_v3",
                    str(r.run_dir),
                    str(r.checkpoint),
                    str(r.attack_rmse_file),
                    "trained_compact_v3",
                    f"lambda_compact={r.lambda_compact:.2f}",
                ]
            )
        )

    rescoring_tag = f"{args.run_tag}/rescoring_hybrid"
    resc_cmd = [
        sys.executable,
        str(REPO_DIR / "ood" / "frontend100_negative_recipe_rescoring.py"),
        "--run-tag",
        rescoring_tag,
        "--source-root",
        str(source_root),
        "--negative-semantics-dir",
        str(args.negative_semantics_dir),
        "--seed",
        str(args.seed),
        "--scan-points",
        str(args.scan_points),
        "--calibration-budget",
        str(args.calibration_budget),
        "--calibration-target",
        str(args.calibration_target),
        "--det-floor",
        str(args.det_floor),
        "--batch-size",
        str(args.batch_size),
    ]
    if args.force_recompute_latent:
        resc_cmd.append("--force-recompute-latent")
    for spec in extra_specs:
        resc_cmd.extend(["--extra-candidate", spec])
    run_cmd(resc_cmd, WORKTREE_ROOT)

    resc_dir = WORKTREE_ROOT / "runs" / rescoring_tag
    resc_results = pd.read_csv(resc_dir / "negative_recipe_rescoring_results.csv")
    keep_labels = ["latent_swap_spike_mix", "transformer_tailreg", "da"] + [r.label for r in v3_runs]
    df = resc_results[
        (resc_results["score_type"] == "hybrid_cosine")
        & (resc_results["candidate_label"].isin(keep_labels))
        & (resc_results["policy_name"].isin(["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"]))
    ].copy()
    df["candidate_label"] = df["candidate_label"].replace({"latent_swap_spike_mix": "latent_swap_spike_mix_no_compact"})
    df = df.sort_values(["candidate_label", "policy_name"])

    results_csv = out_dir / "latent_compact_v3_results.csv"
    results_md = out_dir / "latent_compact_v3_results.md"
    summary_md = out_dir / "latent_compact_v3_summary.md"
    manifest_json = out_dir / "latent_compact_v3_config_manifest.json"
    df.to_csv(results_csv, index=False)
    save_md_table(
        df,
        results_md,
        [
            "candidate_label",
            "policy_name",
            "threshold",
            "ood_alarm_ratio_eval",
            "attack_detection_high_purity",
            "attack_detection_boundary",
            "alarm_reduction_vs_fixed",
            "detection_retention_vs_fixed",
        ],
    )

    plot_tradeoff(df, plot_dir / "tradeoff_main_hybrid_cosine.png")

    stage2_manifest = resc.load_json(stage2_joint / "attack_manifest_stage2.json")
    high_idx, mixed_idx = stage2_indices(stage2_manifest, False, len(attack_x))
    det_data: Dict[str, Dict] = {}
    cache_dir = resc_dir / "cache_rescored_scores"
    for _, row in df[df["policy_name"] == "fixed_id_q99"].iterrows():
        lbl = str(row["candidate_label"])
        src_lbl = "latent_swap_spike_mix" if lbl == "latent_swap_spike_mix_no_compact" else lbl
        run_info = next((r for r in v3_runs if r.label == src_lbl), None)
        if run_info is None and src_lbl in {"transformer_tailreg", "da", "latent_swap_spike_mix"}:
            resc_manifest = resc.load_json(resc_dir / "negative_recipe_rescoring_manifest.json")
            cmeta = next(c for c in resc_manifest["candidates"] if c["candidate_label"] == src_lbl)
            run_dir = Path(cmeta["run_dir"])
            attack_file = Path(cmeta["attack_score_file"])
        else:
            run_dir = run_info.run_dir
            attack_file = run_info.attack_rmse_file
        metrics = resc.load_json(run_dir / "metrics.json")
        rmse_id = np.load(run_dir / "id_scores.npy").astype(np.float64)
        rmse_ood = np.load(resc.pick_ood_score_file(run_dir, metrics)).astype(np.float64)
        rmse_attack = np.load(attack_file).astype(np.float64)
        cos_id = np.load(cache_dir / f"{src_lbl}_latent_id_cos.npy").astype(np.float64)
        cos_ood = np.load(cache_dir / f"{src_lbl}_latent_ood_cos.npy").astype(np.float64)
        cos_attack = np.load(cache_dir / f"{src_lbl}_latent_attack_cos.npy").astype(np.float64)
        rmse_mu = float(np.mean(rmse_id))
        rmse_sigma = resc.safe_std(rmse_id)
        cos_mu = float(np.mean(cos_id))
        cos_sigma = resc.safe_std(cos_id)
        h_id = resc.zscore(rmse_id, rmse_mu, rmse_sigma) + resc.zscore(cos_id, cos_mu, cos_sigma)
        h_ood = resc.zscore(rmse_ood, rmse_mu, rmse_sigma) + resc.zscore(cos_ood, cos_mu, cos_sigma)
        h_attack = resc.zscore(rmse_attack, rmse_mu, rmse_sigma) + resc.zscore(cos_attack, cos_mu, cos_sigma)
        budget = int(min(max(1, args.calibration_budget), len(h_ood) - 1))
        det_data[lbl] = {
            "ood_eval": h_ood[budget:],
            "attack_high": h_attack[high_idx],
            "attack_scores": h_attack,
            "fixed_thr": float(np.quantile(h_id, 0.99)),
            "center_id": cos_id,
            "center_ood_eval": cos_ood[budget:],
            "center_attack_high": cos_attack[high_idx],
        }

    cmp_labels = [x for x in ["latent_swap_spike_mix_no_compact", "transformer_tailreg", "da"] if x in det_data]
    best_v3_fixed = df[(df["candidate_label"].str.startswith("latent_compact_v3_")) & (df["policy_name"] == "fixed_id_q99")].copy()
    best_v3_fixed["util"] = best_v3_fixed["attack_detection_high_purity"] - best_v3_fixed["ood_alarm_ratio_eval"]
    best_v3 = str(best_v3_fixed.sort_values(["util", "attack_detection_high_purity"], ascending=[False, False]).iloc[0]["candidate_label"])
    cmp_labels = [best_v3] + cmp_labels
    plot_distribution(det_data, cmp_labels, "ood_eval", "OOD benign score distribution (hybrid_cosine)", plot_dir / "ood_score_distribution_compare.png")
    plot_distribution(det_data, cmp_labels, "attack_high", "Attack high-purity score distribution (hybrid_cosine)", plot_dir / "attack_score_distribution_compare.png")
    plot_distribution(det_data, cmp_labels, "center_ood_eval", "Center cosine distance on OOD benign (eval)", plot_dir / "center_distance_ood_compare.png")
    plot_attack_segment(det_data, cmp_labels, high_idx, plot_dir / "attack_segment_compare.png")

    def gv(lbl: str, pol: str, col: str) -> float:
        s = df[(df["candidate_label"] == lbl) & (df["policy_name"] == pol) & (df["selection_feasible"])]
        if s.empty:
            return float("nan")
        return float(s.iloc[0][col])

    lines = [
        "# Latent Compact v3 Summary",
        "",
        "## Core setup",
        "- fixed recipe: latent_swap_spike_mix",
        f"- margin/lambda_margin: {args.margin:.1f}/{args.lambda_margin:.1f}",
        f"- lambda_compact scan: {lambda_compacts}",
        f"- center ema alpha: {args.latent_center_ema_alpha:.2f} (detached buffer)",
        f"- warm-up steps: {args.latent_warmup_steps}",
        "- scoring lock: hybrid_cosine only (z stats from ID benign eval split only)",
        "",
        "## Required answers",
        f"1. compactness under hybrid_cosine: best v3 = {best_v3}.",
        f"2. best lambda_compact: {best_v3.replace('latent_compact_v3_lc', '').replace('p', '.')}.",
        f"3. vs no_compact (fixed): alarm delta={gv(best_v3, 'fixed_id_q99', 'ood_alarm_ratio_eval') - gv('latent_swap_spike_mix_no_compact', 'fixed_id_q99', 'ood_alarm_ratio_eval'):+.4f}, det delta={gv(best_v3, 'fixed_id_q99', 'attack_detection_high_purity') - gv('latent_swap_spike_mix_no_compact', 'fixed_id_q99', 'attack_detection_high_purity'):+.4f}.",
        f"4. vs transformer_tailreg (fixed): alarm delta={gv(best_v3, 'fixed_id_q99', 'ood_alarm_ratio_eval') - gv('transformer_tailreg', 'fixed_id_q99', 'ood_alarm_ratio_eval'):+.4f}, det delta={gv(best_v3, 'fixed_id_q99', 'attack_detection_high_purity') - gv('transformer_tailreg', 'fixed_id_q99', 'attack_detection_high_purity'):+.4f}.",
        "5. multi-seed gate: proceed only if best v3 maintains positive fixed utility and det50 feasibility.",
    ]
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "stage": "frontend100_latent_compact_v3",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source_root),
        "seed": args.seed,
        "fixed_recipe": "latent_swap_spike_mix",
        "fixed_params": {
            "margin": args.margin,
            "lambda_margin": args.lambda_margin,
            "lambda_compacts": lambda_compacts,
            "center_ema_alpha": args.latent_center_ema_alpha,
            "warmup_steps": args.latent_warmup_steps,
        },
        "scoring": {
            "score_type": "hybrid_cosine",
            "zscore_source": "ID benign eval split only",
            "rescoring_run_tag": rescoring_tag,
        },
        "trained_v3_runs": [
            {
                "label": r.label,
                "lambda_compact": r.lambda_compact,
                "run_dir": str(r.run_dir),
                "checkpoint": str(r.checkpoint),
                "attack_rmse_file": str(r.attack_rmse_file),
            }
            for r in v3_runs
        ],
        "outputs": {
            "results_csv": str(results_csv),
            "results_md": str(results_md),
            "summary_md": str(summary_md),
            "plots_dir": str(plot_dir),
        },
    }
    manifest_json.write_text(json.dumps(resc.sanitize_for_json(manifest), indent=2, ensure_ascii=False), encoding="utf-8")

    # Protocol aliases
    shutil.copyfile(results_csv, out_dir / "results.csv")
    shutil.copyfile(results_md, out_dir / "results.md")
    shutil.copyfile(summary_md, out_dir / "summary.md")
    shutil.copyfile(manifest_json, out_dir / "config.json")
    (out_dir / "run_spec.json").write_text(
        json.dumps(
            {
                "entry_script": str(Path(__file__).resolve()),
                "run_tag": args.run_tag,
                "mode": "full",
                "negative_recipe": "latent_swap_spike_mix",
                "score_type": "hybrid_cosine",
                "lambda_compacts": lambda_compacts,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"[done] v3 output: {out_dir}")


if __name__ == "__main__":
    main()
