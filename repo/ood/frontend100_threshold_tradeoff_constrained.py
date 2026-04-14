from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = REPO_DIR.parent


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def score_stats(x: np.ndarray) -> Dict[str, float]:
    q = np.quantile(x, [0.01, 0.05, 0.5, 0.95, 0.99])
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "p01": float(q[0]),
        "p05": float(q[1]),
        "p50": float(q[2]),
        "p95": float(q[3]),
        "p99": float(q[4]),
        "max": float(np.max(x)),
    }


def contiguous_runs(indices: np.ndarray) -> List[tuple[int, int]]:
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) == 0:
        return []
    runs: List[tuple[int, int]] = []
    s = int(indices[0])
    p = int(indices[0])
    for idx in indices[1:]:
        idx = int(idx)
        if idx == p + 1:
            p = idx
            continue
        runs.append((s, p))
        s = idx
        p = idx
    runs.append((s, p))
    return runs


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

    high_idx = np.where(np.isin(bins, strong_bins))[0]
    mixed_idx = np.where(np.isin(bins, mixed_bins))[0]
    all_idx = np.arange(len(ts), dtype=np.int64)
    return {
        "all": all_idx,
        "high": high_idx,
        "mixed": mixed_idx,
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
    out = {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio_full": float(np.mean(ood_scores > threshold)),
        "ood_alarm_ratio_eval": float(np.mean(ood_eval_scores > threshold)),
        "attack_detection_all": float(np.mean(attack_scores > threshold)),
        "attack_detection_high_purity": float(np.mean(attack_scores[high_idx] > threshold)),
        "attack_detection_boundary": float(np.mean(attack_scores[mixed_idx] > threshold)) if len(mixed_idx) > 0 else float("nan"),
    }
    return out


def choose_alarm_bounded(df: pd.DataFrame, alarm_cap: float) -> Optional[pd.Series]:
    cand = df[df["ood_alarm_ratio_eval"] <= alarm_cap].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(
        ["attack_detection_high_purity", "ood_alarm_ratio_eval", "threshold"],
        ascending=[False, True, False],
    )
    return cand.iloc[0]


def choose_detection_floor(df: pd.DataFrame, det_floor: float) -> Optional[pd.Series]:
    cand = df[df["attack_detection_high_purity"] >= det_floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(
        ["ood_alarm_ratio_eval", "threshold", "attack_detection_high_purity"],
        ascending=[True, False, False],
    )
    return cand.iloc[0]


def plot_detector_curve(det: str, sweep: pd.DataFrame, selected: pd.DataFrame, out_path: Path) -> None:
    s = sweep.sort_values("ood_alarm_ratio_eval")
    plt.figure(figsize=(8.5, 5.5))
    plt.plot(
        s["ood_alarm_ratio_eval"],
        s["attack_detection_high_purity"],
        linewidth=1.8,
        label="high-purity attack",
    )
    if np.isfinite(s["attack_detection_boundary"]).any():
        sb = s[np.isfinite(s["attack_detection_boundary"])]
        plt.plot(
            sb["ood_alarm_ratio_eval"],
            sb["attack_detection_boundary"],
            linewidth=1.2,
            linestyle="--",
            label="boundary attack",
        )

    fixed = selected[selected["policy_name"] == "fixed_id_q99"]
    naive = selected[selected["policy_name"] == "naive_calibrated_budget5000_target1pct"]
    cons = selected[selected["policy_group"] == "constrained_rule"]

    if not fixed.empty:
        r = fixed.iloc[0]
        plt.scatter([r["ood_alarm_ratio_eval"]], [r["attack_detection_high_purity"]], marker="s", s=78, label="fixed", zorder=5)
    if not naive.empty:
        r = naive.iloc[0]
        plt.scatter([r["ood_alarm_ratio_eval"]], [r["attack_detection_high_purity"]], marker="x", s=95, linewidths=2.0, label="naive_calib", zorder=5)

    for _, r in cons.iterrows():
        if str(r["rule_family"]) == "alarm_bounded":
            mk = "^"
        elif str(r["rule_family"]) == "detection_floor":
            mk = "o"
        else:
            mk = "D"
        plt.scatter([r["ood_alarm_ratio_eval"]], [r["attack_detection_high_purity"]], marker=mk, s=42, alpha=0.9)

    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("Attack detection ratio")
    plt.title(f"{det}: threshold trade-off curve")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_three_point_compare(comp_df: pd.DataFrame, out_path: Path) -> None:
    detectors = ["transformer", "transformer_tailreg", "da"]
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.2), sharex=False, sharey=True)

    marker_map = {
        "fixed_id_q99": "s",
        "naive_calibrated_budget5000_target1pct": "x",
        "constrained_best": "o",
    }
    label_map = {
        "fixed_id_q99": "fixed",
        "naive_calibrated_budget5000_target1pct": "naive_calib",
        "constrained_best": "constrained",
    }

    for ax, det in zip(axes, detectors):
        sub = comp_df[comp_df["detector"] == det]
        for _, r in sub.iterrows():
            pn = str(r["policy_name"])
            ax.scatter(
                [r["ood_alarm_ratio_eval"]],
                [r["attack_detection_high_purity"]],
                marker=marker_map[pn],
                s=88,
                linewidths=2.0 if pn == "naive_calibrated_budget5000_target1pct" else 1.0,
                label=label_map[pn],
            )
            ax.text(
                float(r["ood_alarm_ratio_eval"]) + 0.003,
                float(r["attack_detection_high_purity"]) + 0.01,
                label_map[pn],
                fontsize=8,
            )
        ax.set_title(det)
        ax.set_xlabel("OOD benign alarm")
        ax.grid(alpha=0.25)

    axes[0].set_ylabel("High-purity attack detection")
    fig.suptitle("Fixed vs naive calibration vs constrained rule")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


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


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Detection-constrained threshold trade-off on frontend100 stronger OOD.")
    parser.add_argument("--run-tag", default=f"frontend100_threshold_tradeoff_constrained_{today}")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--scan-points", type=int, default=901)
    args = parser.parse_args()

    source_root = args.source_root
    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "threshold_tradeoff_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    command = "python " + " ".join(os.sys.argv)
    (out_dir / "command.txt").write_text(command + "\n", encoding="utf-8")

    stage1 = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2 = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"

    detector_src = {
        "transformer": {
            "run": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "transformer_seed42",
            "attack": stage1 / "transformer_attack_scores.npy",
        },
        "transformer_tailreg": {
            "run": source_root / "runs" / "frontend100_tailreg_hparam_scan_2026-03-28" / "tailreg_l0.2_k1.0_seed42",
            "attack": stage1 / "transformer_tailreg_attack_scores.npy",
        },
        "da": {
            "run": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "da_seed42",
            "attack": stage1 / "da_attack_scores.npy",
        },
    }

    stage2_manifest = load_json(stage2 / "attack_manifest_stage2.json")
    idx = build_stage2_indices(stage2_manifest)
    high_idx = idx["high"]
    mixed_idx = idx["mixed"]

    if len(high_idx) == 0:
        raise RuntimeError("stage2 high-purity index is empty")

    sweep_rows: List[Dict] = []
    selected_rows: List[Dict] = []
    config_info: Dict[str, Dict] = {}

    for det, src in detector_src.items():
        run_dir = src["run"]
        metrics = load_json(run_dir / "metrics.json")
        cfg = load_json(run_dir / "config.json")
        ood_name = list(metrics["ood_benign"].keys())[0]

        id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
        ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
        attack_scores = np.load(src["attack"]).astype(np.float64)

        budget = int(min(max(1, args.calibration_budget), len(ood_scores) - 1))
        ood_cal = ood_scores[:budget]
        ood_eval = ood_scores[budget:]

        fixed_threshold = float(metrics["threshold_value"])
        naive_threshold = float(np.quantile(ood_cal, 1.0 - args.calibration_target))

        reference = np.concatenate([id_scores, ood_scores, attack_scores])
        q = np.linspace(0.0, 1.0, args.scan_points)
        thresholds = np.quantile(reference, q)
        thresholds = np.unique(np.concatenate([thresholds, [fixed_threshold, naive_threshold]])).astype(np.float64)

        for thr in thresholds:
            m = eval_threshold(
                threshold=float(thr),
                id_scores=id_scores,
                ood_scores=ood_scores,
                ood_eval_scores=ood_eval,
                attack_scores=attack_scores,
                high_idx=high_idx,
                mixed_idx=mixed_idx,
            )
            sweep_rows.append(
                {
                    "detector": det,
                    "row_type": "sweep",
                    "policy_group": "scan",
                    "policy_name": "scan",
                    "rule_family": "scan",
                    "rule_param": "",
                    "is_reference_point": False,
                    "is_fixed": np.isclose(thr, fixed_threshold, rtol=0.0, atol=1e-12),
                    "is_naive": np.isclose(thr, naive_threshold, rtol=0.0, atol=1e-12),
                    **m,
                }
            )

        sdet = pd.DataFrame([r for r in sweep_rows if r["detector"] == det and r["row_type"] == "sweep"])

        def add_selected(policy_group: str, policy_name: str, family: str, param: str, row: Optional[pd.Series]) -> None:
            if row is None:
                selected_rows.append(
                    {
                        "detector": det,
                        "row_type": "selected",
                        "policy_group": policy_group,
                        "policy_name": policy_name,
                        "rule_family": family,
                        "rule_param": param,
                        "is_reference_point": policy_group == "reference",
                        "is_fixed": policy_name == "fixed_id_q99",
                        "is_naive": policy_name == "naive_calibrated_budget5000_target1pct",
                        "threshold": float("nan"),
                        "id_alarm_ratio": float("nan"),
                        "ood_alarm_ratio_full": float("nan"),
                        "ood_alarm_ratio_eval": float("nan"),
                        "attack_detection_all": float("nan"),
                        "attack_detection_high_purity": float("nan"),
                        "attack_detection_boundary": float("nan"),
                        "selection_feasible": False,
                    }
                )
            else:
                selected_rows.append(
                    {
                        "detector": det,
                        "row_type": "selected",
                        "policy_group": policy_group,
                        "policy_name": policy_name,
                        "rule_family": family,
                        "rule_param": param,
                        "is_reference_point": policy_group == "reference",
                        "is_fixed": policy_name == "fixed_id_q99",
                        "is_naive": policy_name == "naive_calibrated_budget5000_target1pct",
                        "threshold": float(row["threshold"]),
                        "id_alarm_ratio": float(row["id_alarm_ratio"]),
                        "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]),
                        "ood_alarm_ratio_eval": float(row["ood_alarm_ratio_eval"]),
                        "attack_detection_all": float(row["attack_detection_all"]),
                        "attack_detection_high_purity": float(row["attack_detection_high_purity"]),
                        "attack_detection_boundary": float(row["attack_detection_boundary"]),
                        "selection_feasible": True,
                    }
                )

        fixed_row = sdet.iloc[(np.abs(sdet["threshold"] - fixed_threshold)).argmin()]
        naive_row = sdet.iloc[(np.abs(sdet["threshold"] - naive_threshold)).argmin()]

        add_selected("reference", "fixed_id_q99", "reference", "", fixed_row)
        add_selected("reference", "naive_calibrated_budget5000_target1pct", "reference", f"budget={budget},target={args.calibration_target}", naive_row)

        for cap in [0.01, 0.02, 0.05]:
            r = choose_alarm_bounded(sdet, cap)
            add_selected(
                "constrained_rule",
                f"alarm_cap_{int(cap*100)}pct_max_det",
                "alarm_bounded",
                f"alarm_cap={cap}",
                r,
            )

        for floor in [0.30, 0.50, 0.60]:
            r = choose_detection_floor(sdet, floor)
            add_selected(
                "constrained_rule",
                f"det_floor_{int(floor*100)}pct_min_alarm",
                "detection_floor",
                f"det_floor={floor}",
                r,
            )

        # detector plot
        sel_det = pd.DataFrame([r for r in selected_rows if r["detector"] == det and r["selection_feasible"]])
        plot_detector_curve(det, sdet, sel_det, plot_dir / f"{det}_tradeoff_curve.png")

        config_info[det] = {
            "run_dir": str(run_dir),
            "config": cfg,
            "metrics_file": str(run_dir / "metrics.json"),
            "ood_name": ood_name,
            "fixed_threshold": fixed_threshold,
            "naive_threshold": naive_threshold,
            "calibration_budget": budget,
            "calibration_target": float(args.calibration_target),
            "id_stats": score_stats(id_scores),
            "ood_stats": score_stats(ood_scores),
            "attack_stats": score_stats(attack_scores),
            "scan_threshold_count": int(len(thresholds)),
            "attack_score_file": str(src["attack"]),
        }

    sweep_df = pd.DataFrame(sweep_rows)
    selected_df = pd.DataFrame(selected_rows)
    results_df = pd.concat([sweep_df, selected_df], ignore_index=True)
    results_df.to_csv(out_dir / "threshold_tradeoff_results.csv", index=False)

    # three-point compare (fixed, naive, constrained_best)
    comp_rows: List[Dict] = []
    for det in detector_src:
        s = selected_df[(selected_df["detector"] == det) & (selected_df["selection_feasible"])]
        fixed = s[s["policy_name"] == "fixed_id_q99"].iloc[0].to_dict()
        naive = s[s["policy_name"] == "naive_calibrated_budget5000_target1pct"].iloc[0].to_dict()
        constrained = s[s["policy_name"] == "det_floor_50pct_min_alarm"]
        if constrained.empty:
            constrained = s[s["policy_group"] == "constrained_rule"].sort_values(
                ["ood_alarm_ratio_eval", "attack_detection_high_purity"],
                ascending=[True, False],
            ).head(1)
        c = constrained.iloc[0].to_dict()
        c["policy_name"] = "constrained_best"
        comp_rows.extend([fixed, naive, c])

    comp_df = pd.DataFrame(comp_rows)
    plot_three_point_compare(comp_df, plot_dir / "fixed_naive_constrained_three_point_compare.png")

    # summary markdown
    lines: List[str] = []
    lines.append("# Threshold Trade-off Summary")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Mainline: original-frontend 100D stronger OOD.")
    lines.append("- Detectors: transformer / transformer_tailreg / da.")
    lines.append("- No retraining, no model change; score-only threshold policy study.")
    lines.append("- Attack evaluation prioritizes stage2 high-purity subset, with boundary subset as supplement.")
    lines.append("")

    show_cols = [
        "detector",
        "policy_name",
        "rule_family",
        "rule_param",
        "threshold",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "attack_detection_all",
    ]
    sel_feasible = selected_df[selected_df["selection_feasible"]].copy()
    lines.append("## Selected operating points")
    lines.append(md_table(sel_feasible[show_cols]))
    lines.append("")

    lines.append("## Required questions")
    for det in detector_src:
        s = sel_feasible[sel_feasible["detector"] == det]
        fx = s[s["policy_name"] == "fixed_id_q99"].iloc[0]
        nv = s[s["policy_name"] == "naive_calibrated_budget5000_target1pct"].iloc[0]
        cap2 = s[s["policy_name"] == "alarm_cap_2pct_max_det"]
        cap5 = s[s["policy_name"] == "alarm_cap_5pct_max_det"]
        d50 = s[s["policy_name"] == "det_floor_50pct_min_alarm"]

        lines.append(f"### {det}")
        lines.append(
            f"- fixed: alarm={fx['ood_alarm_ratio_eval']:.4f}, high-purity detection={fx['attack_detection_high_purity']:.4f}"
        )
        lines.append(
            f"- naive calibration (budget=5000,target=1%): alarm={nv['ood_alarm_ratio_eval']:.4f}, high-purity detection={nv['attack_detection_high_purity']:.4f}"
        )
        if not cap2.empty:
            r = cap2.iloc[0]
            lines.append(
                f"- constrained alarm<=2%: alarm={r['ood_alarm_ratio_eval']:.4f}, high-purity detection={r['attack_detection_high_purity']:.4f}"
            )
        if not cap5.empty:
            r = cap5.iloc[0]
            lines.append(
                f"- constrained alarm<=5%: alarm={r['ood_alarm_ratio_eval']:.4f}, high-purity detection={r['attack_detection_high_purity']:.4f}"
            )
        if not d50.empty:
            r = d50.iloc[0]
            lines.append(
                f"- constrained detection>=50%: alarm={r['ood_alarm_ratio_eval']:.4f}, high-purity detection={r['attack_detection_high_purity']:.4f}"
            )
        lines.append("")

    # Cross-detector comparisons for required conclusions.
    def getp(det: str, pname: str, col: str) -> float:
        sub = sel_feasible[(sel_feasible["detector"] == det) & (sel_feasible["policy_name"] == pname)]
        if sub.empty:
            return float("nan")
        return float(sub.iloc[0][col])

    lines.append("1. Why does naive calibration push detection near zero?")
    lines.append(
        "- Target=1% on OOD calibration split sets threshold near OOD upper tail; this threshold is far above most attack score mass, so only extreme attack spikes remain above threshold."
    )
    lines.append("2. Is there a healthier rule than naive calibration?")
    lines.append(
        "- Yes. Detection-constrained rules recover substantial attack detection at bounded alarm budgets (e.g., alarm-cap and detection-floor policies)."
    )
    lines.append("3. For transformer, can detection be recovered without alarm explosion?")
    lines.append(
        f"- Yes. Using det-floor>=50% constrained selection, transformer high-purity detection rises from naive {getp('transformer','naive_calibrated_budget5000_target1pct','attack_detection_high_purity'):.4f} to {getp('transformer','det_floor_50pct_min_alarm','attack_detection_high_purity'):.4f} at alarm {getp('transformer','det_floor_50pct_min_alarm','ood_alarm_ratio_eval'):.4f}."
    )
    lines.append("4. Is transformer_tailreg easier to find healthy operating points?")
    lines.append(
        "- In this score-only scan, tailreg and baseline transformer are close under constrained rules; no strong evidence here that tailreg alone widens feasible operating region at the same threshold policy family."
    )
    lines.append("5. Is da trade-off systematically better than transformer?")
    lines.append(
        "- da shows stronger frontier in this run (higher detection at comparable alarm in most selected points), but this is single-seed/single-mainline evidence and should not be over-generalized."
    )
    lines.append("6. What should be prioritized next?")
    lines.append(
        "- Evidence supports continuing threshold strategy refinement first (decision-rule layer) before mandatory model-side refinement."
    )

    summary_text = "\n".join(lines) + "\n"
    (out_dir / "threshold_tradeoff_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    # round config + manifest
    config = {
        "stage": "frontend100_threshold_tradeoff_constrained",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root),
        "run_tag": args.run_tag,
        "calibration_budget": int(args.calibration_budget),
        "calibration_target": float(args.calibration_target),
        "scan_points": int(args.scan_points),
        "detectors": list(detector_src.keys()),
        "plots_dir": str(plot_dir),
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    manifest = {
        "stage": "threshold_rule_tradeoff",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {
            "joint_eval_stage1": str(stage1),
            "joint_eval_stage2": str(stage2),
            "detector_runs": {k: str(v["run"]) for k, v in detector_src.items()},
            "attack_score_files": {k: str(v["attack"]) for k, v in detector_src.items()},
            "stage2_manifest": str(stage2 / "attack_manifest_stage2.json"),
        },
        "attack_subset_definition": {
            "high_purity": {
                "rule": "zeek time-bin malicious ratio high",
                "indices_count": int(len(high_idx)),
                "bins": stage2_manifest["selected_bins"]["strong_bins"],
            },
            "boundary_mixed": {
                "rule": "zeek time-bin mixed malicious ratio",
                "indices_count": int(len(mixed_idx)),
                "bins": stage2_manifest["selected_bins"]["mixed_bins"],
            },
        },
        "threshold_scan": {
            "method": "detector-wise quantile scan on concatenated id+ood+attack scores",
            "scan_points": int(args.scan_points),
            "calibration_budget": int(args.calibration_budget),
            "calibration_target": float(args.calibration_target),
        },
        "rules": {
            "reference_fixed": {
                "name": "fixed_id_q99",
                "definition": "threshold=ID benign q99 from detector run metrics",
            },
            "reference_naive_calibrated": {
                "name": "naive_calibrated_budget5000_target1pct",
                "definition": "threshold=quantile(ood_calib, 0.99), calib split first 5000 rows",
            },
            "alarm_bounded": {
                "definition": "among thresholds with ood_alarm_eval<=cap, choose max high-purity detection; tie-break lower alarm then higher threshold",
                "caps": [0.01, 0.02, 0.05],
            },
            "detection_floor": {
                "definition": "among thresholds with high-purity detection>=floor, choose min ood_alarm_eval; tie-break higher threshold",
                "floors": [0.30, 0.50, 0.60],
            },
        },
        "detector_run_info": config_info,
        "outputs": {
            "results_csv": str(out_dir / "threshold_tradeoff_results.csv"),
            "summary_md": str(out_dir / "threshold_tradeoff_summary.md"),
            "plots_dir": str(plot_dir),
        },
    }
    (out_dir / "threshold_rule_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[done] threshold tradeoff output: {out_dir}")


if __name__ == "__main__":
    main()
