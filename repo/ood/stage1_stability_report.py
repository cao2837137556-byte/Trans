from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from paths import ROOT_DIR


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_seed(name: str) -> int:
    idx = name.rfind("seed")
    if idx < 0:
        return -1
    return int(name[idx + 4 :])


def summarize_runs(root: Path) -> pd.DataFrame:
    rows: List[Dict] = []
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        metrics = load_json(metrics_path)
        detector = "transformer" if run_dir.name.startswith("transformer_") else "da"
        seed = parse_seed(run_dir.name)
        id_stats = metrics["id"]["stats"]
        iot = metrics["ood_benign"]["iot23_benign"]
        cic = metrics["ood_benign"]["ciciot2023_benign"]
        rows.append(
            {
                "run_dir": str(run_dir),
                "detector": detector,
                "seed": seed,
                "id_q99": float(metrics["threshold_value"]),
                "id_mean": float(id_stats["mean"]),
                "id_std": float(id_stats["std"]),
                "id_q95": float(id_stats["q95"]),
                "id_q99_score": float(id_stats["q99"]),
                "iot_alarm_ratio": float(iot["alarm_ratio_at_id_q99_threshold"]),
                "iot_mean": float(iot["stats"]["mean"]),
                "iot_std": float(iot["stats"]["std"]),
                "iot_q95": float(iot["stats"]["q95"]),
                "iot_q99": float(iot["stats"]["q99"]),
                "cic_alarm_ratio": float(cic["alarm_ratio_at_id_q99_threshold"]),
                "cic_mean": float(cic["stats"]["mean"]),
                "cic_std": float(cic["stats"]["std"]),
                "cic_q95": float(cic["stats"]["q95"]),
                "cic_q99": float(cic["stats"]["q99"]),
            }
        )
    if not rows:
        raise RuntimeError(f"No run metrics found under {root}")
    df = pd.DataFrame(rows).sort_values(["detector", "seed"]).reset_index(drop=True)
    return df


def save_markdown_table(df: pd.DataFrame, path: Path, cols: List[str]) -> None:
    view = df[cols].copy()
    path.write_text(dataframe_to_markdown(view), encoding="utf-8")


def dataframe_to_markdown(df: pd.DataFrame) -> str:
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


def mean_var_summary(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "id_q99",
        "iot_alarm_ratio",
        "cic_alarm_ratio",
        "id_mean",
        "id_std",
        "id_q95",
        "id_q99_score",
        "iot_mean",
        "iot_std",
        "iot_q95",
        "iot_q99",
        "cic_mean",
        "cic_std",
        "cic_q95",
        "cic_q99",
    ]
    rows = []
    for det, g in df.groupby("detector"):
        for m in metrics:
            rows.append(
                {
                    "detector": det,
                    "metric": m,
                    "mean": float(g[m].mean()),
                    "var": float(g[m].var(ddof=0)),
                }
            )
    return pd.DataFrame(rows)


def plot_alarm_bars(df: pd.DataFrame, out_path: Path) -> None:
    detectors = ["transformer", "da"]
    seeds = sorted(df["seed"].unique())
    x = np.arange(len(seeds))
    width = 0.18

    plt.figure(figsize=(12, 5))
    for i, det in enumerate(detectors):
        g = df[df["detector"] == det].set_index("seed").reindex(seeds)
        plt.bar(x + (i - 1.5) * width, g["iot_alarm_ratio"], width=width, label=f"{det}-iot23")
        plt.bar(x + (i + 0.5) * width, g["cic_alarm_ratio"], width=width, label=f"{det}-ciciot")
    plt.xticks(x, [str(s) for s in seeds])
    plt.ylim(0.0, 1.05)
    plt.xlabel("seed")
    plt.ylabel("alarm ratio")
    plt.title("OOD benign alarm ratio across seeds")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def load_scores(run_dir: Path, name: str) -> np.ndarray:
    return np.load(run_dir / f"{name}_scores.npy")


def plot_detector_boxplot(root: Path, df: pd.DataFrame, out_path: Path) -> None:
    eps = 1e-12
    boxes = []
    labels = []
    for det in ["transformer", "da"]:
        run_dirs = [Path(p) for p in df[df["detector"] == det]["run_dir"].tolist()]
        id_all = np.concatenate([load_scores(r, "id") for r in run_dirs])
        iot_all = np.concatenate([load_scores(r, "iot23_benign") for r in run_dirs])
        cic_all = np.concatenate([load_scores(r, "ciciot2023_benign") for r in run_dirs])
        boxes.extend([np.log10(id_all + eps), np.log10(iot_all + eps), np.log10(cic_all + eps)])
        labels.extend([f"{det}-ID", f"{det}-IoT23B", f"{det}-CICB"])

    plt.figure(figsize=(12, 5))
    plt.boxplot(boxes, tick_labels=labels, showfliers=False)
    plt.ylabel("log10(score)")
    plt.title("Transformer vs dA: ID/OOD benign score distributions")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def build_summary_markdown(df: pd.DataFrame, agg: pd.DataFrame, out_path: Path) -> None:
    lines: List[str] = []
    lines.append("# Stage1 OOD Stability Summary")
    lines.append("")
    lines.append("## Per-seed core results")
    cols = [
        "detector",
        "seed",
        "id_q99",
        "iot_alarm_ratio",
        "cic_alarm_ratio",
        "id_mean",
        "id_std",
        "id_q95",
        "id_q99_score",
        "iot_mean",
        "iot_std",
        "iot_q95",
        "iot_q99",
        "cic_mean",
        "cic_std",
        "cic_q95",
        "cic_q99",
    ]
    lines.append(dataframe_to_markdown(df[cols]))
    lines.append("")
    lines.append("## Mean +- variance by detector")
    lines.append(dataframe_to_markdown(agg))
    lines.append("")

    def mv(det: str, metric: str) -> str:
        row = agg[(agg["detector"] == det) & (agg["metric"] == metric)].iloc[0]
        return f"{row['mean']:.6f} +- {row['var']:.6f}"

    lines.append("## Quick read")
    lines.append(f"- Transformer IoT23 benign alarm ratio (mean+-var): {mv('transformer', 'iot_alarm_ratio')}")
    lines.append(f"- Transformer CIC benign alarm ratio (mean+-var): {mv('transformer', 'cic_alarm_ratio')}")
    lines.append(f"- dA IoT23 benign alarm ratio (mean+-var): {mv('da', 'iot_alarm_ratio')}")
    lines.append(f"- dA CIC benign alarm ratio (mean+-var): {mv('da', 'cic_alarm_ratio')}")
    lines.append(f"- Transformer ID q99 (mean+-var): {mv('transformer', 'id_q99')}")
    lines.append(f"- dA ID q99 (mean+-var): {mv('da', 'id_q99')}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate stage1 stability runs.")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR / "runs" / "ood_probe_stage1_stability_2026-03-21",
    )
    args = parser.parse_args()

    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    df = summarize_runs(root)
    agg = mean_var_summary(df)

    per_seed_csv = root / "per_seed_results.csv"
    agg_csv = root / "aggregate_mean_var.csv"
    per_seed_md = root / "per_seed_results.md"
    agg_md = root / "aggregate_mean_var.md"
    summary_md = root / "summary.md"

    df.to_csv(per_seed_csv, index=False)
    agg.to_csv(agg_csv, index=False)
    save_markdown_table(
        df,
        per_seed_md,
        [
            "detector",
            "seed",
            "id_q99",
            "iot_alarm_ratio",
            "cic_alarm_ratio",
            "id_mean",
            "id_std",
            "id_q95",
            "id_q99_score",
            "iot_mean",
            "iot_std",
            "iot_q95",
            "iot_q99",
            "cic_mean",
            "cic_std",
            "cic_q95",
            "cic_q99",
        ],
    )
    save_markdown_table(agg, agg_md, ["detector", "metric", "mean", "var"])

    plot_alarm_bars(df, root / "alarm_ratio_by_seed.png")
    plot_detector_boxplot(root, df, root / "detector_score_boxplot.png")
    build_summary_markdown(df, agg, summary_md)
    print(f"[done] summary at {summary_md}")


if __name__ == "__main__":
    main()
