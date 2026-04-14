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
import frontend100_score_postprocessing as spp


def lj(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def run_cmd(cmd: List[str]) -> None:
    print("[run]", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def score_attack_if_needed(checkpoint: Path, attack_x: np.ndarray, cache_path: Path) -> Tuple[np.ndarray, str]:
    if cache_path.exists():
        return np.load(cache_path).astype(np.float64), "reused_cache"
    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(attack_x), dtype=np.float64)
    for i in range(len(attack_x)):
        if i > 0 and i % 2000 == 0:
            print(f"  attack scoring {checkpoint.name}: {i}/{len(attack_x)}")
        scores[i] = model.process(attack_x[i])
    np.save(cache_path, scores)
    return scores, "computed_now"


def eval_rows(
    object_label: str,
    detector_family: str,
    score_label: str,
    seed: int,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
    scan_points: int,
    calibration_budget: int,
    calibration_target: float,
    fixed_threshold: float,
    fixed_threshold_source: str,
) -> List[Dict]:
    budget = int(min(max(1, calibration_budget), len(ood_scores) - 1))
    ood_cal = ood_scores[:budget]
    ood_eval = ood_scores[budget:]
    naive_thr = float(np.quantile(ood_cal, 1.0 - calibration_target))
    ref = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
    thresholds = np.quantile(ref, np.linspace(0.0, 1.0, scan_points))
    thresholds = np.unique(np.concatenate([thresholds, [fixed_threshold, naive_thr]])).astype(np.float64)
    scan_df = pd.DataFrame([
        resc.eval_threshold(
            threshold=float(thr),
            id_scores=id_scores,
            ood_scores=ood_scores,
            ood_eval_scores=ood_eval,
            attack_scores=attack_scores,
            high_idx=high_idx,
            mixed_idx=mixed_idx,
        )
        for thr in thresholds
    ])
    fixed_row = scan_df.iloc[(np.abs(scan_df["threshold"] - fixed_threshold)).argmin()]
    naive_row = scan_df.iloc[(np.abs(scan_df["threshold"] - naive_thr)).argmin()]
    det50_row = resc.choose_detection_floor(scan_df, 0.50)
    auc = resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=attack_scores[high_idx])

    def one(policy_name: str, row: Optional[pd.Series], src: str) -> Dict:
        return {
            "row_type": "per_seed",
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": int(seed),
            "policy_name": policy_name,
            "selection_feasible": row is not None,
            "threshold": float("nan") if row is None else float(row["threshold"]),
            "threshold_source": src,
            "id_alarm_ratio": float("nan") if row is None else float(row["id_alarm_ratio"]),
            "ood_alarm_ratio_full": float("nan") if row is None else float(row["ood_alarm_ratio_full"]),
            "ood_alarm_ratio_eval": float("nan") if row is None else float(row["ood_alarm_ratio_eval"]),
            "attack_detection_all": float("nan") if row is None else float(row["attack_detection_all"]),
            "attack_detection_high_purity": float("nan") if row is None else float(row["attack_detection_high_purity"]),
            "attack_detection_boundary": float("nan") if row is None else float(row["attack_detection_boundary"]),
            "roc_auc_attack_high_vs_ood_eval": float(auc),
        }

    return [
        one("fixed_id_q99", fixed_row, fixed_threshold_source),
        one("naive_calibrated_budget5000_target1pct", naive_row, "ood_cal_q99_of_this_score"),
        one("det_floor_50pct_min_alarm", det50_row, "scan_min_alarm_subject_to_detection_floor"),
    ]


def flat(df: pd.DataFrame) -> pd.DataFrame:
    cols = []
    for c in df.columns:
        if isinstance(c, tuple):
            cols.append(c[0] if c[1] == "" else f"{c[0]}_{c[1]}")
        else:
            cols.append(str(c))
    df.columns = cols
    df.rename(columns={"object_label_": "object_label", "detector_family_": "detector_family", "score_label_": "score_label", "policy_name_": "policy_name", "comparison_": "comparison"}, inplace=True)
    return df


def aggregate(per_seed_df: pd.DataFrame) -> pd.DataFrame:
    metric_cols = ["ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "roc_auc_attack_high_vs_ood_eval"]
    agg = per_seed_df[per_seed_df["selection_feasible"]].groupby(["object_label", "detector_family", "score_label", "policy_name"], as_index=False)[metric_cols].agg(["mean", "std", "count"]).reset_index()
    agg = flat(agg)
    agg["row_type"] = "aggregate"
    return agg


def pairwise(per_seed_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    cols = ["seed", "policy_name", "object_label", "ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]
    pivot = per_seed_df[per_seed_df["selection_feasible"]][cols].pivot_table(index=["seed", "policy_name"], columns="object_label", values=["ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"])
    pivot.columns = [f"{a}__{b}" for a, b in pivot.columns]
    pivot = pivot.reset_index()
    specs = [
        ("candidate_new_vs_oldscore", "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0", "latent_swap_spike_mix__hybrid_cosine_default"),
        ("candidate_new_vs_transformer_tailreg", "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0", "transformer_tailreg__default_score"),
        ("candidate_new_vs_da", "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0", "da__default_score"),
    ]
    rows: List[Dict] = []
    for _, row in pivot.iterrows():
        for label, lhs, rhs in specs:
            a_alarm = row.get(f"ood_alarm_ratio_eval__{lhs}")
            b_alarm = row.get(f"ood_alarm_ratio_eval__{rhs}")
            a_det = row.get(f"attack_detection_high_purity__{lhs}")
            b_det = row.get(f"attack_detection_high_purity__{rhs}")
            a_auc = row.get(f"roc_auc_attack_high_vs_ood_eval__{lhs}")
            b_auc = row.get(f"roc_auc_attack_high_vs_ood_eval__{rhs}")
            if pd.isna(a_alarm) or pd.isna(b_alarm) or pd.isna(a_det) or pd.isna(b_det):
                continue
            rows.append({
                "row_type": "pairwise_delta_per_seed",
                "comparison": label,
                "seed": int(row["seed"]),
                "policy_name": row["policy_name"],
                "alarm_delta": float(a_alarm - b_alarm),
                "detection_delta": float(a_det - b_det),
                "auc_delta": float(a_auc - b_auc) if (pd.notna(a_auc) and pd.notna(b_auc)) else float("nan"),
            })
    per = pd.DataFrame(rows)
    if per.empty:
        return per, pd.DataFrame()
    agg = per.groupby(["comparison", "policy_name"], as_index=False)[["alarm_delta", "detection_delta", "auc_delta"]].agg(["mean", "std", "count"]).reset_index()
    agg = flat(agg)
    agg["row_type"] = "pairwise_delta_aggregate"
    return per, agg

def plot_tradeoff(agg: pd.DataFrame, out_path: Path) -> None:
    colors = {
        "transformer__default_score": "#2ca02c",
        "transformer_tailreg__default_score": "#1f77b4",
        "da__default_score": "#9467bd",
        "latent_swap_spike_mix__hybrid_cosine_default": "#ff7f0e",
        "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0": "#d62728",
    }
    short = {
        "fixed_id_q99": "fixed",
        "naive_calibrated_budget5000_target1pct": "naive",
        "det_floor_50pct_min_alarm": "det50",
    }
    marks = {"fixed_id_q99": "o", "naive_calibrated_budget5000_target1pct": "x", "det_floor_50pct_min_alarm": "s"}
    fig, ax = plt.subplots(figsize=(10.5, 7.4))
    for _, row in agg.iterrows():
        obj = str(row["object_label"])
        ax.errorbar(
            [float(row["ood_alarm_ratio_eval_mean"])],
            [float(row["attack_detection_high_purity_mean"])],
            xerr=[0.0 if pd.isna(row["ood_alarm_ratio_eval_std"]) else float(row["ood_alarm_ratio_eval_std"])],
            yerr=[0.0 if pd.isna(row["attack_detection_high_purity_std"]) else float(row["attack_detection_high_purity_std"])],
            fmt=marks.get(str(row["policy_name"]), "o"),
            color=colors.get(obj, "#7f7f7f"),
            ecolor=colors.get(obj, "#7f7f7f"),
            markersize=7,
            capsize=3,
        )
        ax.text(float(row["ood_alarm_ratio_eval_mean"]) + 0.004, float(row["attack_detection_high_purity_mean"]) + 0.006, f"{obj}:{short.get(str(row['policy_name']), str(row['policy_name']))}", fontsize=8)
    ax.set_xlabel("OOD benign alarm ratio (mean ± std)")
    ax.set_ylabel("High-purity attack detection (mean ± std)")
    ax.set_title("Locked candidate multi-seed trade-off")
    ax.grid(alpha=0.28)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_subset(agg: pd.DataFrame, out_path: Path, object_labels: List[str], title: str) -> None:
    sub = agg[agg["object_label"].isin(object_labels)].copy()
    colors = {
        "transformer_tailreg__default_score": "#1f77b4",
        "da__default_score": "#9467bd",
        "latent_swap_spike_mix__hybrid_cosine_default": "#ff7f0e",
        "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0": "#d62728",
    }
    short = {"fixed_id_q99": "fixed", "naive_calibrated_budget5000_target1pct": "naive", "det_floor_50pct_min_alarm": "det50"}
    fig, ax = plt.subplots(figsize=(9.2, 6.6))
    for _, row in sub.iterrows():
        obj = str(row["object_label"])
        ax.errorbar(
            [float(row["ood_alarm_ratio_eval_mean"])],
            [float(row["attack_detection_high_purity_mean"])],
            xerr=[0.0 if pd.isna(row["ood_alarm_ratio_eval_std"]) else float(row["ood_alarm_ratio_eval_std"])],
            yerr=[0.0 if pd.isna(row["attack_detection_high_purity_std"]) else float(row["attack_detection_high_purity_std"])],
            fmt={"fixed_id_q99": "o", "naive_calibrated_budget5000_target1pct": "x", "det_floor_50pct_min_alarm": "s"}.get(str(row["policy_name"]), "o"),
            color=colors.get(obj, "#7f7f7f"),
            ecolor=colors.get(obj, "#7f7f7f"),
            markersize=8,
            capsize=3,
        )
        ax.text(float(row["ood_alarm_ratio_eval_mean"]) + 0.004, float(row["attack_detection_high_purity_mean"]) + 0.006, f"{obj}:{short.get(str(row['policy_name']), str(row['policy_name']))}", fontsize=8)
    ax.set_xlabel("OOD benign alarm ratio (mean ± std)")
    ax.set_ylabel("High-purity attack detection (mean ± std)")
    ax.set_title(title)
    ax.grid(alpha=0.28)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def get_agg(agg: pd.DataFrame, object_label: str, policy_name: str, col: str) -> float:
    row = agg[(agg["object_label"] == object_label) & (agg["policy_name"] == policy_name)]
    if row.empty:
        return float("nan")
    return float(row.iloc[0][col])


def get_pair(agg: pd.DataFrame, comparison: str, policy_name: str, col: str) -> float:
    row = agg[(agg["comparison"] == comparison) & (agg["policy_name"] == policy_name)]
    if row.empty:
        return float("nan")
    return float(row.iloc[0][col])


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Minimal multiseed verification for locked latent candidate.")
    parser.add_argument("--run-tag", default=f"frontend100_locked_candidate_multiseed_{today}")
    parser.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    parser.add_argument("--seed-root", type=Path, default=None)
    parser.add_argument("--seeds", default="")
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--train-samples", type=int, default=8000)
    parser.add_argument("--id-eval-samples", type=int, default=5000)
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--fm-grace", type=int, default=2000)
    parser.add_argument("--ad-grace", type=int, default=6000)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--margin", type=float, default=5.0)
    parser.add_argument("--lambda-margin", type=float, default=0.5)
    parser.add_argument("--latent-pooling", default="mean")
    parser.add_argument("--latent-center-ema-alpha", type=float, default=0.01)
    parser.add_argument("--latent-warmup-steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--force-retrain", action="store_true")
    parser.add_argument("--force-recompute-latent", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "multiseed_locked_candidate_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    candidate_latent_cache = out_dir / "cache_candidate_latent"
    candidate_latent_cache.mkdir(parents=True, exist_ok=True)
    attack_cache_dir = out_dir / "cache_attack_scores"
    attack_cache_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source_root = args.source_root
    seed_root = args.seed_root or (source_root / "runs" / "frontend100_tailreg_bestcfg_stability_2026-03-28")
    protocol = lj(seed_root / "config.json")
    seeds = [int(x) for x in args.seeds.split(",") if str(x).strip()] if args.seeds else [int(x) for x in (protocol.get("protocol", {}) or {}).get("seeds", [101, 202, 303])]

    crosscapture_data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    train_csv = crosscapture_data / "id_source_100.csv"
    train_labels = crosscapture_data / "no_labels.npy"
    ood_benign_csv = crosscapture_data / "ood_benign_source_100.csv"
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"
    stage2_joint = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2_idx = resc.build_stage2_indices(lj(stage2_joint / "attack_manifest_stage2.json"))
    high_idx = stage2_idx["high"]
    mixed_idx = stage2_idx["mixed"]

    if args.dry_run:
        ok = train_csv.exists() and train_labels.exists() and ood_benign_csv.exists() and attack_csv.exists() and all((seed_root / f"transformer_seed{s}").exists() for s in seeds)
        text = "\n".join([
            "# Local Smoketest Summary",
            "",
            f"- Seed protocol: {seeds}",
            f"- Baseline seed root: `{seed_root}`",
            f"- Candidate recipe: `latent_swap_spike_mix`",
            f"- Candidate score: `log_weighted_z_rmse0.5_cos1.0`",
            f"- train_csv exists: {train_csv.exists()}",
            f"- ood_benign_csv exists: {ood_benign_csv.exists()}",
            f"- attack_csv exists: {attack_csv.exists()}",
            f"- stage2 high count: {len(high_idx)}",
            f"- dry-run status: {'PASS' if ok else 'FAIL'}",
        ]) + "\n"
        (out_dir / "local_smoketest_summary.md").write_text(text, encoding="utf-8")
        (out_dir / "summary.md").write_text(text, encoding="utf-8")
        print(f"[dry-run] output: {out_dir}")
        return
    x_train_all = pd.read_csv(train_csv, header=None, nrows=args.train_samples + args.id_eval_samples).to_numpy(dtype=np.float64)
    x_id = x_train_all[args.train_samples : args.train_samples + args.id_eval_samples]
    x_ood = pd.read_csv(ood_benign_csv, header=None).to_numpy(dtype=np.float64)
    attack_x = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)

    per_seed_rows: List[Dict] = []
    run_audit: List[Dict] = []
    candidate_score_stats: Dict[str, Dict] = {}

    for seed in seeds:
        print(f"[seed {seed}] candidate")
        rel_run_tag = f"{args.run_tag}/latent_swap_spike_mix_seed{seed}"
        candidate_run_dir = WORKTREE_ROOT / "runs" / rel_run_tag
        stage1_cmd = [
            sys.executable, str(REPO_DIR / "ood" / "stage1_probe.py"),
            "--run-tag", rel_run_tag,
            "--train-csv", str(train_csv), "--train-labels", str(train_labels),
            "--max-ae", str(args.max_ae), "--fm-grace", str(args.fm_grace), "--ad-grace", str(args.ad_grace),
            "--train-samples", str(args.train_samples), "--id-eval-samples", str(args.id_eval_samples),
            "--learning-rate", str(args.learning_rate), "--hidden-ratio", str(args.hidden_ratio), "--seed", str(seed),
            "--detector-backend", "transformer_latent_contrastive_v1",
            "--latent-margin", str(args.margin), "--latent-lambda", str(args.lambda_margin), "--latent-lambda-compact", "0.0",
            "--latent-center-ema-alpha", str(args.latent_center_ema_alpha), "--latent-warmup-steps", str(args.latent_warmup_steps),
            "--latent-contrastive-mode", "v1", "--latent-pooling", str(args.latent_pooling),
            "--latent-neg-prob-swap", "0.5", "--latent-neg-prob-permute", "0.0", "--latent-neg-prob-spike", "0.5", "--latent-neg-prob-replace", "0.0",
            "--benign-dataset", f"iot23_ood_benign|{ood_benign_csv}", "--skip-attack",
        ]
        if args.force_retrain or not (candidate_run_dir / "config.json").exists():
            if args.force_retrain:
                stage1_cmd.append("--force-retrain")
            run_cmd(stage1_cmd)
            train_mode = "trained_now"
        else:
            train_mode = "reused_existing"

        candidate_cfg = lj(candidate_run_dir / "config.json")
        candidate_metrics = lj(candidate_run_dir / "metrics.json")
        candidate_ckpt = Path(candidate_cfg["checkpoint"])
        candidate_attack_file = attack_cache_dir / f"latent_swap_spike_mix_seed{seed}_attack_scores.npy"
        candidate_attack_scores, attack_mode = score_attack_if_needed(candidate_ckpt, attack_x, candidate_attack_file)
        candidate_id = np.load(candidate_run_dir / "id_scores.npy").astype(np.float64)
        ood_name = list(candidate_metrics["ood_benign"].keys())[0]
        candidate_ood = np.load(candidate_run_dir / f"{ood_name}_scores.npy").astype(np.float64)

        cos_id_file = candidate_latent_cache / f"latent_swap_spike_mix_seed{seed}_cos_id.npy"
        cos_ood_file = candidate_latent_cache / f"latent_swap_spike_mix_seed{seed}_cos_ood.npy"
        cos_attack_file = candidate_latent_cache / f"latent_swap_spike_mix_seed{seed}_cos_attack.npy"
        center_meta_file = candidate_latent_cache / f"latent_swap_spike_mix_seed{seed}_center_meta.json"
        if (not args.force_recompute_latent) and cos_id_file.exists() and cos_ood_file.exists() and cos_attack_file.exists() and center_meta_file.exists():
            cos_id = np.load(cos_id_file).astype(np.float64)
            cos_ood = np.load(cos_ood_file).astype(np.float64)
            cos_attack = np.load(cos_attack_file).astype(np.float64)
            center_mode = "reused_cache"
        else:
            model = kit.KitNET.load_checkpoint(candidate_ckpt)
            _, _, _, cos_id, cos_ood, cos_attack, center_meta = resc.compute_latent_center_distance_scores(model=model, x_id=x_id, x_ood=x_ood, x_attack=attack_x, batch_size=args.batch_size)
            np.save(cos_id_file, cos_id)
            np.save(cos_ood_file, cos_ood)
            np.save(cos_attack_file, cos_attack)
            center_meta_file.write_text(json.dumps(resc.sanitize_for_json(center_meta), indent=2, ensure_ascii=False), encoding="utf-8")
            center_mode = "computed_now"

        versions, score_stats = spp.make_score_versions(candidate_id, candidate_ood, candidate_attack_scores, cos_id, cos_ood, cos_attack)
        for score_version in ["hybrid_cosine_default", "log_weighted_z_rmse0.5_cos1.0"]:
            sid, sood, satt = versions[score_version]
            per_seed_rows.extend(eval_rows(
                object_label=f"latent_swap_spike_mix__{score_version}", detector_family="latent_swap_spike_mix", score_label=score_version, seed=seed,
                id_scores=sid, ood_scores=sood, attack_scores=satt, high_idx=high_idx, mixed_idx=mixed_idx,
                scan_points=args.scan_points, calibration_budget=args.calibration_budget, calibration_target=args.calibration_target,
                fixed_threshold=float(np.quantile(sid, 0.99)), fixed_threshold_source="id_q99_of_this_score",
            ))
            candidate_score_stats[f"latent_swap_spike_mix_seed{seed}__{score_version}"] = score_stats[score_version]

        run_audit.append({
            "seed": seed, "candidate_run_dir": str(candidate_run_dir), "candidate_checkpoint": str(candidate_ckpt),
            "candidate_train_mode": train_mode, "candidate_attack_score_mode": attack_mode, "candidate_center_mode": center_mode,
            "candidate_attack_score_file": str(candidate_attack_file), "candidate_center_meta_file": str(center_meta_file),
        })

        for det in ["transformer", "transformer_tailreg", "da"]:
            print(f"[seed {seed}] baseline {det}")
            run_dir = seed_root / f"{det}_seed{seed}"
            cfg = lj(run_dir / "config.json")
            metrics = lj(run_dir / "metrics.json")
            ood_name = list(metrics["ood_benign"].keys())[0]
            id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
            ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
            ckpt = Path(cfg["checkpoint"])
            attack_file = attack_cache_dir / f"{det}_seed{seed}_attack_scores.npy"
            attack_scores, attack_mode = score_attack_if_needed(ckpt, attack_x, attack_file)
            per_seed_rows.extend(eval_rows(
                object_label=f"{det}__default_score", detector_family=det, score_label="default_score", seed=seed,
                id_scores=id_scores, ood_scores=ood_scores, attack_scores=attack_scores, high_idx=high_idx, mixed_idx=mixed_idx,
                scan_points=args.scan_points, calibration_budget=args.calibration_budget, calibration_target=args.calibration_target,
                fixed_threshold=float(metrics["threshold_value"]), fixed_threshold_source="official_metrics_threshold",
            ))
            run_audit.append({
                "seed": seed, "baseline_detector": det, "baseline_run_dir": str(run_dir), "baseline_checkpoint": str(ckpt),
                "baseline_attack_score_mode": attack_mode, "baseline_attack_score_file": str(attack_file),
            })

    per_seed_df = pd.DataFrame(per_seed_rows).sort_values(["object_label", "seed", "policy_name"])
    agg = aggregate(per_seed_df)
    pair_per, pair_agg = pairwise(per_seed_df)
    results_df = pd.concat([per_seed_df, agg], ignore_index=True, sort=False)
    results_csv = out_dir / "multiseed_locked_candidate_results.csv"
    results_df.to_csv(results_csv, index=False)
    agg.to_csv(out_dir / "multiseed_locked_candidate_aggregate.csv", index=False)
    if not pair_per.empty:
        pair_per.to_csv(out_dir / "multiseed_locked_candidate_pairwise_per_seed.csv", index=False)
    if not pair_agg.empty:
        pair_agg.to_csv(out_dir / "multiseed_locked_candidate_pairwise_aggregate.csv", index=False)

    plot_tradeoff(agg, plot_dir / "locked_candidate_tradeoff_mean_std.png")
    plot_subset(agg, plot_dir / "locked_candidate_vs_tailreg_da.png", ["latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0", "transformer_tailreg__default_score", "da__default_score"], "Candidate vs tailreg vs dA")
    plot_subset(agg, plot_dir / "locked_candidate_old_vs_new_score.png", ["latent_swap_spike_mix__hybrid_cosine_default", "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0"], "Candidate old score vs new score")

    agg_cols = ["object_label", "policy_name", "ood_alarm_ratio_eval_mean", "ood_alarm_ratio_eval_std", "attack_detection_high_purity_mean", "attack_detection_high_purity_std", "attack_detection_boundary_mean", "attack_detection_boundary_std", "roc_auc_attack_high_vs_ood_eval_mean", "roc_auc_attack_high_vs_ood_eval_std", "ood_alarm_ratio_eval_count"]
    parts = ["# Locked Candidate Multi-seed Results", "", "## Aggregate (mean ± std)", md_table(agg[agg_cols].sort_values(["object_label", "policy_name"]))]
    if not pair_agg.empty:
        parts += ["", "## Pairwise Deltas (mean ± std)", md_table(pair_agg.sort_values(["comparison", "policy_name"]))]
    parts += ["", "## Per-seed", md_table(per_seed_df[["object_label", "seed", "policy_name", "ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]].sort_values(["object_label", "seed", "policy_name"]))]
    results_md = "\n".join(parts) + "\n"
    (out_dir / "multiseed_locked_candidate_results.md").write_text(results_md, encoding="utf-8")
    (out_dir / "results.md").write_text(results_md, encoding="utf-8")
    (out_dir / "results.csv").write_text(results_csv.read_text(encoding="utf-8"), encoding="utf-8")

    cand_new = "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0"
    cand_old = "latent_swap_spike_mix__hybrid_cosine_default"
    tailreg = "transformer_tailreg__default_score"
    da = "da__default_score"
    lines = [
        "# Locked Candidate Multi-seed Summary", "", "## Setup",
        f"- Seeds: `{seeds}`",
        "- Locked candidate recipe: `latent_swap_spike_mix`",
        "- Locked main score: `log_weighted_z_rmse0.5_cos1.0`",
        "- Candidate old score control: `hybrid_cosine_default`",
        "- Baselines: `transformer`, `transformer_tailreg`, `da` under official default score.",
        "- Calibration: budget=5000, target=1%, det_floor=50%.", "",
        "## Required answers",
        "1. Is the current main candidate stably better than the same recipe with the old score?",
        f"- fixed new: alarm={get_agg(agg, cand_new, 'fixed_id_q99', 'ood_alarm_ratio_eval_mean'):.4f} ± {get_agg(agg, cand_new, 'fixed_id_q99', 'ood_alarm_ratio_eval_std'):.4f}, det={get_agg(agg, cand_new, 'fixed_id_q99', 'attack_detection_high_purity_mean'):.4f} ± {get_agg(agg, cand_new, 'fixed_id_q99', 'attack_detection_high_purity_std'):.4f}.",
        f"- fixed old: alarm={get_agg(agg, cand_old, 'fixed_id_q99', 'ood_alarm_ratio_eval_mean'):.4f} ± {get_agg(agg, cand_old, 'fixed_id_q99', 'ood_alarm_ratio_eval_std'):.4f}, det={get_agg(agg, cand_old, 'fixed_id_q99', 'attack_detection_high_purity_mean'):.4f} ± {get_agg(agg, cand_old, 'fixed_id_q99', 'attack_detection_high_purity_std'):.4f}.",
        "2. Is the current main candidate stably better than transformer_tailreg?",
        f"- fixed candidate vs tailreg: alarm delta={get_pair(pair_agg, 'candidate_new_vs_transformer_tailreg', 'fixed_id_q99', 'alarm_delta_mean') if not pair_agg.empty else float('nan'):.4f}, det delta={get_pair(pair_agg, 'candidate_new_vs_transformer_tailreg', 'fixed_id_q99', 'detection_delta_mean') if not pair_agg.empty else float('nan'):.4f}.",
        "3. Relative to dA, where does the candidate stand?",
        f"- fixed candidate vs dA: alarm delta={get_pair(pair_agg, 'candidate_new_vs_da', 'fixed_id_q99', 'alarm_delta_mean') if not pair_agg.empty else float('nan'):.4f}, det delta={get_pair(pair_agg, 'candidate_new_vs_da', 'fixed_id_q99', 'detection_delta_mean') if not pair_agg.empty else float('nan'):.4f}.",
        "4. Does naive calibration still collapse detection across seeds?",
        f"- naive detection means: candidate={get_agg(agg, cand_new, 'naive_calibrated_budget5000_target1pct', 'attack_detection_high_purity_mean'):.4f}, tailreg={get_agg(agg, tailreg, 'naive_calibrated_budget5000_target1pct', 'attack_detection_high_purity_mean'):.4f}, dA={get_agg(agg, da, 'naive_calibrated_budget5000_target1pct', 'attack_detection_high_purity_mean'):.4f}.",
        "5. Is this enough to upgrade as the formal Transformer strongest candidate?",
        "- Read the fixed and det50 aggregate rows together with pairwise deltas; this round is the stability/verification pass, not a new search round.",
    ]
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "multiseed_locked_candidate_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    manifest = {
        "stage": "multiseed_locked_candidate_verification", "generated_at": datetime.now().isoformat(timespec="seconds"), "run_tag": args.run_tag,
        "source_root": str(source_root), "seed_root": str(seed_root), "seeds": seeds,
        "candidate_recipe": "latent_swap_spike_mix", "candidate_main_score": "log_weighted_z_rmse0.5_cos1.0", "candidate_old_score": "hybrid_cosine_default",
        "baselines": ["transformer", "transformer_tailreg", "da"],
        "train_config": {"train_samples": args.train_samples, "id_eval_samples": args.id_eval_samples, "max_ae": args.max_ae, "fm_grace": args.fm_grace, "ad_grace": args.ad_grace, "learning_rate": args.learning_rate, "hidden_ratio": args.hidden_ratio, "margin": args.margin, "lambda_margin": args.lambda_margin, "latent_pooling": args.latent_pooling, "latent_center_ema_alpha": args.latent_center_ema_alpha, "latent_warmup_steps": args.latent_warmup_steps, "negative_probs": {"swap": 0.5, "permute": 0.0, "spike": 0.5, "replace": 0.0}},
        "calibration": {"budget": args.calibration_budget, "target_alarm": args.calibration_target, "det_floor": 0.5},
        "stats_leakage_rule": "All candidate z/log-z stats are computed from ID benign evaluation split only.",
        "candidate_score_stats": resc.sanitize_for_json(candidate_score_stats), "run_audit": resc.sanitize_for_json(run_audit),
        "outputs": {"results_csv": str(results_csv), "results_md": str(out_dir / 'multiseed_locked_candidate_results.md'), "summary_md": str(out_dir / 'multiseed_locked_candidate_summary.md'), "plots_dir": str(plot_dir)},
    }
    manifest_text = json.dumps(resc.sanitize_for_json(manifest), indent=2, ensure_ascii=False)
    (out_dir / "multiseed_locked_candidate_manifest.json").write_text(manifest_text, encoding="utf-8")
    (out_dir / "config.json").write_text(manifest_text, encoding="utf-8")
    print(f"[done] locked-candidate multiseed output: {out_dir}")


if __name__ == "__main__":
    main()
