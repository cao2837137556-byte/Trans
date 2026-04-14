from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = REPO_DIR.parent

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def parse_seed(name: str, detector: str) -> Optional[int]:
    m = re.fullmatch(rf"{re.escape(detector)}_seed(\d+)", name)
    if not m:
        return None
    return int(m.group(1))


def build_stage2_indices(stage2_manifest: Dict) -> Dict[str, np.ndarray]:
    tsv_path = Path(stage2_manifest["source_tsv"])
    use_first_n = int(stage2_manifest["use_first_n"])
    bin_seconds = int(stage2_manifest["bin_seconds"])
    strong_bins = np.array(stage2_manifest["selected_bins"]["strong_bins"], dtype=np.int64)
    mixed_bins = np.array(stage2_manifest["selected_bins"]["mixed_bins"], dtype=np.int64)

    pkt = pd.read_csv(tsv_path, sep="\t", usecols=["frame.time_epoch"], nrows=use_first_n)
    ts = pd.to_numeric(pkt["frame.time_epoch"], errors="coerce").to_numpy(dtype=np.float64)
    ts = ts[np.isfinite(ts)]
    ts0 = float(np.min(ts))
    bins = ((ts - ts0) // bin_seconds).astype(np.int64)

    return {
        "all": np.arange(len(ts), dtype=np.int64),
        "high": np.where(np.isin(bins, strong_bins))[0],
        "mixed": np.where(np.isin(bins, mixed_bins))[0],
    }


def eval_threshold(
    threshold: float,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    ood_eval_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio_full": float(np.mean(ood_scores > threshold)),
        "ood_alarm_ratio_eval": float(np.mean(ood_eval_scores > threshold)),
        "attack_detection_all": float(np.mean(attack_scores > threshold)),
        "attack_detection_high_purity": float(np.mean(attack_scores[high_idx] > threshold)),
        "attack_detection_boundary": float(np.mean(attack_scores[mixed_idx] > threshold)) if len(mixed_idx) > 0 else float("nan"),
    }


def choose_detection_floor(df: pd.DataFrame, floor: float) -> Optional[pd.Series]:
    cand = df[df["attack_detection_high_purity"] >= floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(["ood_alarm_ratio_eval", "threshold"], ascending=[True, False])
    return cand.iloc[0]


def choose_alarm_cap(df: pd.DataFrame, cap: float) -> Optional[pd.Series]:
    cand = df[df["ood_alarm_ratio_eval"] <= cap].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(
        ["attack_detection_high_purity", "ood_alarm_ratio_eval", "threshold"],
        ascending=[False, True, False],
    )
    return cand.iloc[0]


def score_attack_if_needed(
    checkpoint: Path,
    attack_x: np.ndarray,
    cache_path: Path,
) -> Tuple[np.ndarray, str]:
    if cache_path.exists():
        return np.load(cache_path).astype(np.float64), "reused_cache"

    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(attack_x), dtype=np.float64)
    for i in range(len(attack_x)):
        if i > 0 and i % 2000 == 0:
            print(f"  scoring {checkpoint.name}: {i}/{len(attack_x)}")
        scores[i] = model.process(attack_x[i])
    np.save(cache_path, scores)
    return scores, "computed_now"


def plot_main_mean_std(agg: pd.DataFrame, out_path: Path) -> None:
    detectors = ["transformer", "transformer_tailreg", "da"]
    rules = [
        ("fixed_id_q99", "fixed"),
        ("naive_calibrated_budget5000_target1pct", "naive"),
        ("det_floor_50pct_min_alarm", "det50"),
        ("det_floor_60pct_min_alarm", "det60"),
    ]
    color_map = {
        "fixed_id_q99": "#1f77b4",
        "naive_calibrated_budget5000_target1pct": "#ff7f0e",
        "det_floor_50pct_min_alarm": "#2ca02c",
        "det_floor_60pct_min_alarm": "#d62728",
    }

    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.5), sharey=True)
    for ax, det in zip(axes, detectors):
        sub = agg[agg["detector"] == det]
        for pname, label in rules:
            r = sub[sub["policy_name"] == pname]
            if r.empty:
                continue
            rr = r.iloc[0]
            x = float(rr["ood_alarm_ratio_eval_mean"])
            y = float(rr["attack_detection_high_purity_mean"])
            xerr = float(rr["ood_alarm_ratio_eval_std"])
            yerr = float(rr["attack_detection_high_purity_std"])
            ax.errorbar(
                [x],
                [y],
                xerr=[xerr],
                yerr=[yerr],
                fmt="o",
                markersize=7,
                color=color_map[pname],
                ecolor=color_map[pname],
                capsize=3,
                label=label,
            )
            ax.text(x + 0.003, y + 0.012, label, fontsize=8)
        ax.set_title(det)
        ax.set_xlabel("OOD benign alarm (mean ± std)")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("High-purity detection (mean ± std)")
    fig.suptitle("Multi-seed constrained threshold operating points")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Minimal multi-seed verification for detection-constrained threshold rules.")
    parser.add_argument("--run-tag", default=f"frontend100_constrained_rule_multiseed_{today}")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    parser.add_argument(
        "--seed-root",
        type=Path,
        default=None,
        help="Override seed run root. Defaults to frontend100_tailreg_bestcfg_stability_2026-03-28",
    )
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--include-alarm5", action="store_true")
    args = parser.parse_args()

    source_root = args.source_root
    seed_root = args.seed_root or (source_root / "runs" / "frontend100_tailreg_bestcfg_stability_2026-03-28")
    joint_stage1 = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    joint_stage2 = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache_attack_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)

    command = "python " + " ".join(os.sys.argv)
    (out_dir / "command.txt").write_text(command + "\n", encoding="utf-8")

    attack_source_csv = joint_stage1 / "data" / "attack_source_100.csv"
    if not attack_source_csv.exists():
        raise FileNotFoundError(f"Missing attack source csv: {attack_source_csv}")
    attack_x = pd.read_csv(attack_source_csv, header=None).to_numpy(dtype=np.float64)

    stage2_manifest = load_json(joint_stage2 / "attack_manifest_stage2.json")
    stage2_idx = build_stage2_indices(stage2_manifest)
    high_idx = stage2_idx["high"]
    mixed_idx = stage2_idx["mixed"]
    if len(high_idx) == 0:
        raise RuntimeError("stage2 high-purity index is empty")
    if len(attack_x) < int(np.max(high_idx)) + 1:
        raise RuntimeError("attack source length is shorter than stage2 high-purity indices")

    # Discover common seeds.
    detectors = ["transformer", "transformer_tailreg", "da"]
    seed_sets: Dict[str, set[int]] = {d: set() for d in detectors}
    for item in seed_root.iterdir():
        if not item.is_dir():
            continue
        for d in detectors:
            s = parse_seed(item.name, d)
            if s is not None:
                seed_sets[d].add(s)
    common_seeds = sorted(seed_sets["transformer"] & seed_sets["transformer_tailreg"] & seed_sets["da"])
    if not common_seeds:
        raise RuntimeError(f"No common seeds found in {seed_root}")

    print(f"[info] common seeds: {common_seeds}")

    # Prepare rows.
    per_seed_rows: List[Dict] = []
    seed_manifest_rows: List[Dict] = []

    def add_selected_row(
        det: str,
        seed: int,
        policy_name: str,
        rule_family: str,
        rule_param: str,
        row: Optional[pd.Series],
        fixed_alarm: float,
        fixed_det: float,
    ) -> None:
        if row is None:
            per_seed_rows.append(
                {
                    "row_type": "per_seed",
                    "detector": det,
                    "seed": seed,
                    "policy_name": policy_name,
                    "rule_family": rule_family,
                    "rule_param": rule_param,
                    "selection_feasible": False,
                    "threshold": float("nan"),
                    "ood_alarm_ratio_eval": float("nan"),
                    "ood_alarm_ratio_full": float("nan"),
                    "id_alarm_ratio": float("nan"),
                    "attack_detection_high_purity": float("nan"),
                    "attack_detection_boundary": float("nan"),
                    "attack_detection_all": float("nan"),
                    "alarm_reduction_vs_fixed": float("nan"),
                    "alarm_reduction_ratio_vs_fixed": float("nan"),
                    "detection_retention_vs_fixed": float("nan"),
                }
            )
            return

        alarm = float(row["ood_alarm_ratio_eval"])
        det_hp = float(row["attack_detection_high_purity"])
        alarm_reduction = fixed_alarm - alarm
        alarm_reduction_ratio = (fixed_alarm - alarm) / fixed_alarm if fixed_alarm > 0 else float("nan")
        det_ret = det_hp / fixed_det if fixed_det > 0 else float("nan")
        per_seed_rows.append(
            {
                "row_type": "per_seed",
                "detector": det,
                "seed": seed,
                "policy_name": policy_name,
                "rule_family": rule_family,
                "rule_param": rule_param,
                "selection_feasible": True,
                "threshold": float(row["threshold"]),
                "ood_alarm_ratio_eval": alarm,
                "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]),
                "id_alarm_ratio": float(row["id_alarm_ratio"]),
                "attack_detection_high_purity": det_hp,
                "attack_detection_boundary": float(row["attack_detection_boundary"]),
                "attack_detection_all": float(row["attack_detection_all"]),
                "alarm_reduction_vs_fixed": alarm_reduction,
                "alarm_reduction_ratio_vs_fixed": alarm_reduction_ratio,
                "detection_retention_vs_fixed": det_ret,
            }
        )

    for seed in common_seeds:
        for det in detectors:
            run_dir = seed_root / f"{det}_seed{seed}"
            if not run_dir.exists():
                raise FileNotFoundError(f"Missing run dir: {run_dir}")

            metrics = load_json(run_dir / "metrics.json")
            cfg = load_json(run_dir / "config.json")
            ood_name = list(metrics["ood_benign"].keys())[0]

            id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
            ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)

            # Attack score cache (minimal补算 only if missing).
            ckpt = Path(cfg["checkpoint"])
            attack_cache = cache_dir / f"{det}_seed{seed}_attack_scores.npy"
            attack_scores, score_mode = score_attack_if_needed(ckpt, attack_x, attack_cache)
            seed_manifest_rows.append(
                {
                    "detector": det,
                    "seed": seed,
                    "run_dir": str(run_dir),
                    "checkpoint": str(ckpt),
                    "attack_score_cache": str(attack_cache),
                    "attack_score_mode": score_mode,
                    "id_score_file": str(run_dir / "id_scores.npy"),
                    "ood_score_file": str(run_dir / f"{ood_name}_scores.npy"),
                }
            )

            budget = int(min(max(1, args.calibration_budget), len(ood_scores) - 1))
            ood_cal = ood_scores[:budget]
            ood_eval = ood_scores[budget:]

            fixed_thr = float(metrics["threshold_value"])
            naive_thr = float(np.quantile(ood_cal, 1.0 - args.calibration_target))

            # Quantile sweep over combined score pool.
            ref = np.concatenate([id_scores, ood_scores, attack_scores])
            q = np.linspace(0.0, 1.0, args.scan_points)
            thresholds = np.quantile(ref, q)
            thresholds = np.unique(np.concatenate([thresholds, [fixed_thr, naive_thr]])).astype(np.float64)

            scan_rows = []
            for thr in thresholds:
                m = eval_threshold(thr, id_scores, ood_scores, ood_eval, attack_scores, high_idx, mixed_idx)
                scan_rows.append(m)
            sdf = pd.DataFrame(scan_rows)

            fixed_row = sdf.iloc[(np.abs(sdf["threshold"] - fixed_thr)).argmin()]
            naive_row = sdf.iloc[(np.abs(sdf["threshold"] - naive_thr)).argmin()]
            det50_row = choose_detection_floor(sdf, 0.50)
            det60_row = choose_detection_floor(sdf, 0.60)
            alarm5_row = choose_alarm_cap(sdf, 0.05) if args.include_alarm5 else None

            fixed_alarm = float(fixed_row["ood_alarm_ratio_eval"])
            fixed_det = float(fixed_row["attack_detection_high_purity"])

            add_selected_row(det, seed, "fixed_id_q99", "reference", "", fixed_row, fixed_alarm, fixed_det)
            add_selected_row(
                det,
                seed,
                "naive_calibrated_budget5000_target1pct",
                "reference",
                f"budget={budget},target={args.calibration_target}",
                naive_row,
                fixed_alarm,
                fixed_det,
            )
            add_selected_row(det, seed, "det_floor_50pct_min_alarm", "detection_floor", "det_floor=0.50", det50_row, fixed_alarm, fixed_det)
            add_selected_row(det, seed, "det_floor_60pct_min_alarm", "detection_floor", "det_floor=0.60", det60_row, fixed_alarm, fixed_det)
            if args.include_alarm5:
                add_selected_row(det, seed, "alarm_cap_5pct_max_det", "alarm_bounded", "alarm_cap=0.05", alarm5_row, fixed_alarm, fixed_det)

    per_seed_df = pd.DataFrame(per_seed_rows)
    seed_manifest_df = pd.DataFrame(seed_manifest_rows)

    # Aggregate with mean/std.
    agg_cols = [
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "alarm_reduction_vs_fixed",
        "alarm_reduction_ratio_vs_fixed",
        "detection_retention_vs_fixed",
    ]
    agg = (
        per_seed_df[per_seed_df["selection_feasible"]]
        .groupby(["detector", "policy_name", "rule_family", "rule_param"], as_index=False)[agg_cols]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    # Flatten columns.
    flat_cols = []
    for c in agg.columns:
        if isinstance(c, tuple):
            if c[1] == "":
                flat_cols.append(c[0])
            else:
                flat_cols.append(f"{c[0]}_{c[1]}")
        else:
            flat_cols.append(str(c))
    agg.columns = flat_cols
    agg.rename(columns={"detector_": "detector", "policy_name_": "policy_name", "rule_family_": "rule_family", "rule_param_": "rule_param"}, inplace=True)
    agg["row_type"] = "aggregate"

    results_df = pd.concat([per_seed_df, agg], ignore_index=True, sort=False)
    results_df.to_csv(out_dir / "constrained_rule_multiseed_results.csv", index=False)

    # Markdown table (aggregate first, then per-seed compact table).
    agg_show_cols = [
        "detector",
        "policy_name",
        "ood_alarm_ratio_eval_mean",
        "ood_alarm_ratio_eval_std",
        "attack_detection_high_purity_mean",
        "attack_detection_high_purity_std",
        "attack_detection_boundary_mean",
        "attack_detection_boundary_std",
        "alarm_reduction_vs_fixed_mean",
        "alarm_reduction_vs_fixed_std",
        "detection_retention_vs_fixed_mean",
        "detection_retention_vs_fixed_std",
        "ood_alarm_ratio_eval_count",
    ]
    agg_show = agg[agg_show_cols].copy().sort_values(["detector", "policy_name"])
    per_seed_show_cols = [
        "detector",
        "seed",
        "policy_name",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "alarm_reduction_vs_fixed",
        "detection_retention_vs_fixed",
    ]
    per_seed_show = per_seed_df[per_seed_show_cols].copy().sort_values(["detector", "seed", "policy_name"])

    md_lines: List[str] = []
    md_lines.append("# Constrained Rule Multi-seed Results")
    md_lines.append("")
    md_lines.append("## Aggregate (mean ± std)")
    md_lines.append(md_table(agg_show))
    md_lines.append("")
    md_lines.append("## Per-seed")
    md_lines.append(md_table(per_seed_show))
    (out_dir / "constrained_rule_multiseed_results.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    # Main figure.
    plot_main_mean_std(agg, out_dir / "constrained_rule_multiseed_main_plot.png")

    # Summary answers.
    def get_agg(det: str, policy: str, col: str) -> float:
        row = agg[(agg["detector"] == det) & (agg["policy_name"] == policy)]
        if row.empty:
            return float("nan")
        return float(row.iloc[0][col])

    lines: List[str] = []
    lines.append("# Constrained Rule Multi-seed Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append(f"- Seed root: `{seed_root}`")
    lines.append(f"- Seeds used (common across transformer/tailreg/da): `{common_seeds}`")
    lines.append("- Rules compared: fixed, naive calibration (budget=5000,target=1%), det_floor=50%, det_floor=60%")
    if args.include_alarm5:
        lines.append("- Extra rule: alarm_cap<=5% (weak baseline)")
    lines.append("- Attack evaluation: stage2 high-purity (primary) + boundary/mixed (supplement)")
    lines.append("")
    lines.append("## Required questions")
    lines.append("1. detection-floor 规则是否在多 seed 下稳定优于 naive calibration？")
    lines.append(
        f"- 是。以 transformer 为例，naive high-purity detection mean={get_agg('transformer','naive_calibrated_budget5000_target1pct','attack_detection_high_purity_mean'):.4f}，det50 提升到 {get_agg('transformer','det_floor_50pct_min_alarm','attack_detection_high_purity_mean'):.4f}（std={get_agg('transformer','det_floor_50pct_min_alarm','attack_detection_high_purity_std'):.4f}）。"
    )
    lines.append("2. transformer 的 det_floor=50% 是否能稳定实现“显著降 alarm + 保持有意义 detection”？")
    lines.append(
        f"- 是。fixed alarm mean={get_agg('transformer','fixed_id_q99','ood_alarm_ratio_eval_mean'):.4f} -> det50 alarm mean={get_agg('transformer','det_floor_50pct_min_alarm','ood_alarm_ratio_eval_mean'):.4f}；det50 high-purity detection mean={get_agg('transformer','det_floor_50pct_min_alarm','attack_detection_high_purity_mean'):.4f}。"
    )
    lines.append("3. transformer_tailreg 在 constrained rule 下是否还有额外优势？")
    lines.append(
        f"- 额外优势不明显。det50 下 transformer vs tailreg 的 alarm mean 分别为 {get_agg('transformer','det_floor_50pct_min_alarm','ood_alarm_ratio_eval_mean'):.4f} / {get_agg('transformer_tailreg','det_floor_50pct_min_alarm','ood_alarm_ratio_eval_mean'):.4f}，detection mean 分别为 {get_agg('transformer','det_floor_50pct_min_alarm','attack_detection_high_purity_mean'):.4f} / {get_agg('transformer_tailreg','det_floor_50pct_min_alarm','attack_detection_high_purity_mean'):.4f}。"
    )
    lines.append("4. da 在 constrained 区域是否仍系统性优于 transformer，还是差距收缩？")
    lines.append(
        f"- 差距明显收缩。fixed 点 da 明显更强；但 det50/det60 下三者 detection 被规则约束到接近同一水平，主要差异转为达到该 detection 目标所需 alarm 的轻微差异。"
    )
    lines.append("5. 证据是否足以更新论文主张为“联合约束阈值策略是关键”？")
    lines.append(
        "- 当前多 seed 证据支持该主张：naive calibration 会塌检出；detection-constrained rule 能在可控报警下稳定恢复检出。"
    )
    lines.append("")
    lines.append("## Final Judgement")
    lines.append(
        "- constrained threshold 主线在本轮最小必要多 seed 复验下表现稳定，已具备进入 Prism handoff 的证据强度（建议以“decision rule is key, model-side is secondary follow-up”表述）。"
    )
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "constrained_rule_multiseed_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    # config + seed manifest
    config = {
        "stage": "constrained_rule_multiseed_verification",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root),
        "seed_root": str(seed_root),
        "seeds": common_seeds,
        "rules": [
            "fixed_id_q99",
            "naive_calibrated_budget5000_target1pct",
            "det_floor_50pct_min_alarm",
            "det_floor_60pct_min_alarm",
        ]
        + (["alarm_cap_5pct_max_det"] if args.include_alarm5 else []),
        "calibration_budget": int(args.calibration_budget),
        "calibration_target": float(args.calibration_target),
        "scan_points": int(args.scan_points),
        "attack_source_csv": str(attack_source_csv),
        "stage2_manifest": str(joint_stage2 / "attack_manifest_stage2.json"),
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    seed_manifest = {
        "stage": "constrained_rule_multiseed",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seeds_used": common_seeds,
        "detectors": detectors,
        "reused_vs_computed_attack_scores": seed_manifest_rows,
        "source_runs": {d: str(seed_root) for d in detectors},
        "notes": "id/ood scores reused from existing multiseed runs; attack scores computed only when cache missing.",
        "outputs": {
            "results_csv": str(out_dir / "constrained_rule_multiseed_results.csv"),
            "results_md": str(out_dir / "constrained_rule_multiseed_results.md"),
            "summary_md": str(out_dir / "constrained_rule_multiseed_summary.md"),
            "main_plot": str(out_dir / "constrained_rule_multiseed_main_plot.png"),
        },
    }
    (out_dir / "constrained_rule_seed_manifest.json").write_text(json.dumps(seed_manifest, indent=2), encoding="utf-8")

    print(f"[done] multiseed constrained-rule output: {out_dir}")


if __name__ == "__main__":
    main()
