from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RUN_SEED_RE = re.compile(r"seed(\d+)")


def to_md(df: pd.DataFrame) -> str:
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


def detect_detector(run_name: str) -> Optional[str]:
    name = run_name.lower()
    if (
        "_transformer_colab" in name
        or "_transformer_local" in name
        or name.endswith("_transformer")
        or "_transformer_" in name
    ):
        return "transformer"
    if (
        "_da_colab" in name
        or "_da_local" in name
        or name.endswith("_da")
        or "_da_" in name
    ):
        return "da"
    return None


def detect_seed(run_name: str) -> Optional[int]:
    m = RUN_SEED_RE.search(run_name)
    if not m:
        return None
    return int(m.group(1))


def collect_rows(root: Path, budget: int, target_alarm_rate: float) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        detector = detect_detector(run_dir.name)
        seed = detect_seed(run_dir.name)
        if detector is None or seed is None:
            continue

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not metrics.get("ood_benign"):
            continue
        ood_name = list(metrics["ood_benign"].keys())[0]
        id_stats = metrics["id"]["stats"]
        ood_stats = metrics["ood_benign"][ood_name]["stats"]
        fixed_threshold = float(metrics["threshold_value"])
        fixed_alarm = float(metrics["ood_benign"][ood_name]["alarm_ratio_at_id_q99_threshold"])

        id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
        ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
        calib_budget = int(min(max(1, budget), len(ood_scores) - 1))
        ood_cal = ood_scores[:calib_budget]
        ood_eval = ood_scores[calib_budget:]
        calibrated_threshold = float(np.quantile(ood_cal, 1.0 - target_alarm_rate))
        calibrated_alarm = float(np.mean(ood_eval > calibrated_threshold))

        rows.append(
            {
                "run_dir": str(run_dir),
                "detector": detector,
                "seed": int(seed),
                "ood_name": ood_name,
                "id_mean": float(id_stats["mean"]),
                "id_std": float(id_stats["std"]),
                "id_q95": float(id_stats["q95"]),
                "id_q99": float(id_stats["q99"]),
                "ood_mean": float(ood_stats["mean"]),
                "ood_std": float(ood_stats["std"]),
                "ood_q95": float(ood_stats["q95"]),
                "ood_q99": float(ood_stats["q99"]),
                "fixed_threshold": fixed_threshold,
                "fixed_ood_alarm_ratio": fixed_alarm,
                "calibration_budget": int(calib_budget),
                "target_alarm_rate": float(target_alarm_rate),
                "calibrated_threshold": calibrated_threshold,
                "calibrated_ood_alarm_ratio": calibrated_alarm,
            }
        )
    if not rows:
        raise RuntimeError(f"No valid seed runs found under: {root}")
    return pd.DataFrame(rows).sort_values(["detector", "seed"]).reset_index(drop=True)


def build_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    out: List[Dict[str, object]] = []
    for det, g in df.groupby("detector"):
        out.append(
            {
                "detector": det,
                "fixed_ood_alarm_ratio_mean": float(g["fixed_ood_alarm_ratio"].mean()),
                "fixed_ood_alarm_ratio_std": float(g["fixed_ood_alarm_ratio"].std(ddof=0)),
                "calibrated_ood_alarm_ratio_mean": float(g["calibrated_ood_alarm_ratio"].mean()),
                "calibrated_ood_alarm_ratio_std": float(g["calibrated_ood_alarm_ratio"].std(ddof=0)),
                "id_q99_mean": float(g["id_q99"].mean()),
                "id_q99_std": float(g["id_q99"].std(ddof=0)),
                "ood_q99_mean": float(g["ood_q99"].mean()),
                "ood_q99_std": float(g["ood_q99"].std(ddof=0)),
            }
        )
    return pd.DataFrame(out).sort_values("detector").reset_index(drop=True)


def plot_by_seed(df: pd.DataFrame, y_col: str, title: str, out_path: Path) -> None:
    seeds = sorted(df["seed"].unique())
    x = np.arange(len(seeds))
    width = 0.36
    plt.figure(figsize=(8, 4.6))
    for det, shift in [("transformer", -width / 2), ("da", width / 2)]:
        g = df[df["detector"] == det].set_index("seed").reindex(seeds)
        plt.bar(x + shift, g[y_col], width=width, label=det)
    plt.xticks(x, [str(s) for s in seeds])
    plt.xlabel("seed")
    plt.ylabel("OOD alarm ratio")
    plt.title(title)
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_mean_compare(agg: pd.DataFrame, out_path: Path) -> None:
    order = ["transformer", "da"]
    sub = agg.set_index("detector").reindex(order)
    x = np.arange(len(order))
    width = 0.36
    plt.figure(figsize=(7.4, 4.4))
    plt.bar(x - width / 2, sub["fixed_ood_alarm_ratio_mean"], width=width, label="fixed")
    plt.bar(x + width / 2, sub["calibrated_ood_alarm_ratio_mean"], width=width, label="calibrated")
    plt.xticks(x, order)
    plt.ylabel("mean OOD alarm ratio")
    plt.title("Fixed vs calibrated mean alarm ratio")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def write_summary(root: Path, per_seed: pd.DataFrame, agg: pd.DataFrame) -> None:
    a = agg.set_index("detector")
    tf_fixed = float(a.loc["transformer", "fixed_ood_alarm_ratio_mean"])
    da_fixed = float(a.loc["da", "fixed_ood_alarm_ratio_mean"])
    tf_cal = float(a.loc["transformer", "calibrated_ood_alarm_ratio_mean"])
    da_cal = float(a.loc["da", "calibrated_ood_alarm_ratio_mean"])
    cal_gap = tf_cal - da_cal

    lines: List[str] = []
    lines.append(f"# Frontend100 Cross-capture Calibration Stability Summary ({root.name})")
    lines.append("")
    lines.append("## Core claim check")
    lines.append(
        "- Fixed threshold (ID q99) amplifies OOD false alarms; calibrated threshold "
        "(budget=5000, target=1%) shrinks transformer-da alarm gap."
    )
    lines.append("")
    lines.append("## Aggregate key numbers")
    lines.append(
        f"- transformer fixed/calibrated mean alarm: {tf_fixed:.6f} / {tf_cal:.6f}"
    )
    lines.append(
        f"- da fixed/calibrated mean alarm: {da_fixed:.6f} / {da_cal:.6f}"
    )
    lines.append(f"- calibrated gap mean (transformer - da): {cal_gap:.6f}")
    lines.append("")
    lines.append("## Output files")
    lines.append("- per_seed_results.csv / per_seed_results.md")
    lines.append("- aggregate_mean_var.csv / aggregate_mean_var.md")
    lines.append("- plots/fixed_alarm_ratio_by_seed.png")
    lines.append("- plots/calibrated_alarm_ratio_by_seed.png")
    lines.append("- plots/fixed_vs_calibrated_mean.png")
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate frontend100 cross-capture calibration stability runs.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--target-alarm-rate", type=float, default=0.01)
    args = parser.parse_args()

    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    plot_dir = root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    per_seed = collect_rows(root, budget=args.calibration_budget, target_alarm_rate=args.target_alarm_rate)
    agg = build_aggregate(per_seed)

    per_seed.to_csv(root / "per_seed_results.csv", index=False)
    agg.to_csv(root / "aggregate_mean_var.csv", index=False)
    (root / "per_seed_results.md").write_text(to_md(per_seed), encoding="utf-8")
    (root / "aggregate_mean_var.md").write_text(to_md(agg), encoding="utf-8")

    plot_by_seed(
        per_seed,
        y_col="fixed_ood_alarm_ratio",
        title="Fixed threshold OOD alarm ratio by seed",
        out_path=plot_dir / "fixed_alarm_ratio_by_seed.png",
    )
    plot_by_seed(
        per_seed,
        y_col="calibrated_ood_alarm_ratio",
        title="Calibrated OOD alarm ratio by seed",
        out_path=plot_dir / "calibrated_alarm_ratio_by_seed.png",
    )
    plot_mean_compare(agg, plot_dir / "fixed_vs_calibrated_mean.png")

    info = {
        "root": str(root),
        "calibration_budget": args.calibration_budget,
        "target_alarm_rate": args.target_alarm_rate,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (root / "config.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    write_summary(root, per_seed, agg)
    print(f"[done] outputs written to: {root}")


if __name__ == "__main__":
    main()
