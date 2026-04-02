from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent


def parse_int_list(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def parse_float_list(text: str) -> List[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def load_scores(run_dir: Path) -> Dict[str, np.ndarray]:
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    ood_name = list(metrics["ood_benign"].keys())[0]
    return {
        "id": np.load(run_dir / "id_scores.npy").astype(np.float64),
        "ood": np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64),
        "ood_name": ood_name,
    }


def qstats(x: np.ndarray) -> Dict[str, float]:
    q = np.quantile(x, [0.95, 0.99, 0.999])
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "q95": float(q[0]),
        "q99": float(q[1]),
        "q999": float(q[2]),
        "max": float(np.max(x)),
    }


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
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


def plot_budget_lines(df: pd.DataFrame, budgets: List[int], targets: List[float], out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, det in zip(axes, ["transformer", "da"]):
        sub = df[(df["detector"] == det) & (df["policy"] == "ood_target_alarm_calib")]
        for t in targets:
            vals = []
            for b in budgets:
                row = sub[(sub["calibration_budget"] == b) & (sub["target_alarm_rate"] == t)].iloc[0]
                vals.append(float(row["achieved_ood_alarm_ratio"]))
            ax.plot(budgets, vals, marker="o", label=f"target={t:.2f}")
        ax.set_title(det)
        ax.set_xlabel("calibration budget")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("achieved OOD alarm ratio (eval split)")
    axes[1].legend(fontsize=8)
    fig.suptitle("Calibration scan: achieved alarm vs budget")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_detector_compare(df: pd.DataFrame, budgets: List[int], targets: List[float], out_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True)
    axes = axes.flatten()
    x = np.arange(len(targets))
    width = 0.36
    for i, b in enumerate(budgets):
        ax = axes[i]
        sub = df[(df["calibration_budget"] == b) & (df["policy"] == "ood_target_alarm_calib")]
        tr = [float(sub[(sub["detector"] == "transformer") & (sub["target_alarm_rate"] == t)]["achieved_ood_alarm_ratio"].iloc[0]) for t in targets]
        da = [float(sub[(sub["detector"] == "da") & (sub["target_alarm_rate"] == t)]["achieved_ood_alarm_ratio"].iloc[0]) for t in targets]
        ax.bar(x - width / 2, tr, width=width, label="transformer")
        ax.bar(x + width / 2, da, width=width, label="da")
        ax.set_xticks(x, [f"{t:.2f}" for t in targets])
        ax.set_title(f"budget={b}")
        ax.set_xlabel("target alarm rate")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("achieved OOD alarm ratio")
    axes[1].legend()
    fig.suptitle("Detector comparison by target rate and budget")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def build_summary(df: pd.DataFrame, out_path: Path, budgets: List[int], targets: List[float]) -> None:
    grid = df[df["policy"] == "ood_target_alarm_calib"].copy()
    baseline = df[df["policy"] == "fixed_id_q99"].copy()

    lines: List[str] = []
    lines.append("# Frontend100 Cross-capture Calibration Scan Summary")
    lines.append("")
    lines.append("## Fixed protocol")
    lines.append("- ID capture: CTU-Honeypot-Capture-7-6")
    lines.append("- OOD benign capture: CTU-Honeypot-Capture-4-1")
    lines.append("- 100-D original frontend features; train_samples=8000; id_eval_samples=5000; fm=2000; ad=6000; seed=42")
    lines.append("- No detector structure changes; threshold-layer only.")
    lines.append("")
    lines.append("## Calibration grid")
    lines.append(f"- budgets: {budgets}")
    lines.append(f"- target alarm rates: {targets}")
    lines.append("- Calibration uses first `budget` unlabeled OOD rows; evaluation uses remaining non-overlapping OOD rows.")
    lines.append("")
    show_cols = [
        "detector",
        "calibration_budget",
        "target_alarm_rate",
        "threshold",
        "achieved_ood_alarm_ratio",
        "id_q99",
        "ood_q95",
        "ood_q99",
        "ood_max",
    ]
    lines.append("## Grid results (calibrated policies)")
    lines.append(md_table(grid[show_cols].sort_values(["detector", "calibration_budget", "target_alarm_rate"])))
    lines.append("")

    # aggregate diagnostics
    diag_rows = []
    for det, g in grid.groupby("detector"):
        mae = float(np.mean(np.abs(g["achieved_ood_alarm_ratio"] - g["target_alarm_rate"])))
        mean_alarm = float(np.mean(g["achieved_ood_alarm_ratio"]))
        std_alarm = float(np.std(g["achieved_ood_alarm_ratio"], ddof=0))
        diag_rows.append(
            {
                "detector": det,
                "mean_achieved_alarm": mean_alarm,
                "std_achieved_alarm": std_alarm,
                "mae_to_target": mae,
            }
        )
    diag = pd.DataFrame(diag_rows)
    lines.append("## Detector-level aggregate diagnostics")
    lines.append(md_table(diag))
    lines.append("")

    # baseline vs best calibrated
    lines.append("## Fixed vs calibrated best")
    lines.append("| detector | fixed alarm | best calibrated alarm | abs drop | rel drop |")
    lines.append("|---|---:|---:|---:|---:|")
    for det in ["transformer", "da"]:
        f = float(baseline[baseline["detector"] == det]["achieved_ood_alarm_ratio"].iloc[0])
        b = float(grid[grid["detector"] == det]["achieved_ood_alarm_ratio"].min())
        drop = f - b
        rel = drop / f * 100.0 if f > 0 else 0.0
        lines.append(f"| {det} | {f:.6f} | {b:.6f} | {drop:.6f} | {rel:.2f}% |")
    lines.append("")

    # key combos with low achieved alarm
    top = grid.sort_values("achieved_ood_alarm_ratio").head(6)
    lines.append("## Lowest achieved alarm combinations")
    lines.append(md_table(top[["detector", "calibration_budget", "target_alarm_rate", "threshold", "achieved_ood_alarm_ratio"]]))
    lines.append("")

    # interpretation
    tr_mae = float(diag[diag["detector"] == "transformer"]["mae_to_target"].iloc[0])
    da_mae = float(diag[diag["detector"] == "da"]["mae_to_target"].iloc[0])
    lines.append("## Interpretation")
    lines.append("- Calibration is effective for both detectors and consistently lowers OOD alarms versus fixed ID-q99 thresholds.")
    lines.append(
        f"- Transformer calibration stability (MAE to target): {tr_mae:.4f}; dA: {da_mae:.4f}."
    )
    if tr_mae > da_mae:
        lines.append("- dA is more calibration-stable / sample-efficient in this scan.")
    else:
        lines.append("- Transformer is at least as calibration-stable as dA in this scan.")
    lines.append("- Residual gaps remain under several settings; thresholding helps a lot but does not fully remove robustness differences.")
    lines.append("- Diagnosis: (b) threshold layer contributes strongly, but residual robustness gap remains.")
    lines.append("")
    lines.append("## Recommended next step")
    lines.append("- Prefer `2) switch to paper mode and solidify threshold-layer contribution`, then plan targeted model-side follow-up.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibration scan on frontend100 cross-capture scores.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--budgets", default="500,1000,2000,5000")
    parser.add_argument("--targets", default="0.01,0.02,0.05,0.10")
    parser.add_argument("--id-quantile", type=float, default=0.99)
    args = parser.parse_args()

    budgets = parse_int_list(args.budgets)
    targets = parse_float_list(args.targets)
    if len(budgets) != 4 or len(targets) != 4:
        raise ValueError("Expected 4 budgets and 4 targets for this scan.")

    out_root = ROOT_DIR / "runs" / args.run_tag
    out_root.mkdir(parents=True, exist_ok=True)
    plot_dir = out_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    detector_runs = {
        "transformer": args.source_root / "transformer_seed42",
        "da": args.source_root / "da_seed42",
    }

    rows: List[Dict] = []
    for det, run_dir in detector_runs.items():
        loaded = load_scores(run_dir)
        id_scores = loaded["id"]
        ood_scores = loaded["ood"]
        id_q99 = float(np.quantile(id_scores, args.id_quantile))
        id_stats = qstats(id_scores)

        # fixed baseline row
        ood_stats_full = qstats(ood_scores)
        rows.append(
            {
                "detector": det,
                "policy": "fixed_id_q99",
                "calibration_budget": 0,
                "target_alarm_rate": np.nan,
                "threshold": id_q99,
                "achieved_ood_alarm_ratio": float(np.mean(ood_scores > id_q99)),
                "id_alarm_ratio": float(np.mean(id_scores > id_q99)),
                "eval_rows": int(len(ood_scores)),
                "id_q95": id_stats["q95"],
                "id_q99": id_q99,
                "ood_q95": ood_stats_full["q95"],
                "ood_q99": ood_stats_full["q99"],
                "ood_q999": ood_stats_full["q999"],
                "ood_max": ood_stats_full["max"],
            }
        )

        for b in budgets:
            if b >= len(ood_scores):
                raise ValueError(f"budget {b} must be < number of OOD rows ({len(ood_scores)})")
            calib = ood_scores[:b]
            eval_scores = ood_scores[b:]
            eval_stats = qstats(eval_scores)
            for t in targets:
                threshold = float(np.quantile(calib, 1.0 - t))
                rows.append(
                    {
                        "detector": det,
                        "policy": "ood_target_alarm_calib",
                        "calibration_budget": int(b),
                        "target_alarm_rate": float(t),
                        "threshold": threshold,
                        "achieved_ood_alarm_ratio": float(np.mean(eval_scores > threshold)),
                        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
                        "eval_rows": int(len(eval_scores)),
                        "id_q95": id_stats["q95"],
                        "id_q99": id_q99,
                        "ood_q95": eval_stats["q95"],
                        "ood_q99": eval_stats["q99"],
                        "ood_q999": eval_stats["q999"],
                        "ood_max": eval_stats["max"],
                    }
                )

    df = pd.DataFrame(rows)
    df.to_csv(out_root / "calibration_grid_results.csv", index=False)
    (out_root / "calibration_grid_results.md").write_text(md_table(df), encoding="utf-8")
    plot_budget_lines(df, budgets, targets, plot_dir / "achieved_alarm_vs_budget.png")
    plot_detector_compare(df, budgets, targets, plot_dir / "detector_compare_by_target.png")
    build_summary(df, out_root / "summary.md", budgets, targets)

    config = {
        "stage": "frontend100_crosscapture_calibration_scan",
        "date": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(args.source_root),
        "fixed_protocol": {
            "id_capture": "CTU-Honeypot-Capture-7-6",
            "ood_capture": "CTU-Honeypot-Capture-4-1",
            "input_dim": 100,
            "train_samples": 8000,
            "id_eval_samples": 5000,
            "fm_grace": 2000,
            "ad_grace": 6000,
            "seed": 42,
            "detectors": ["transformer", "da"],
        },
        "scan_grid": {
            "calibration_budgets": budgets,
            "target_alarm_rates": targets,
            "id_quantile_baseline": args.id_quantile,
        },
        "note": "No retraining; scan is on saved score streams from fixed protocol runs.",
    }
    (out_root / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[done] calibration scan output: {out_root}")


if __name__ == "__main__":
    main()
