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

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit


def score_stats(x: np.ndarray) -> Dict[str, float]:
    q = np.quantile(x, [0.95, 0.99])
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "q95": float(q[0]),
        "q99": float(q[1]),
    }


def score_attack(model: kit.KitNET, x: np.ndarray) -> np.ndarray:
    scores = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        if i > 0 and i % 2000 == 0:
            print(f"  attack scoring progress: {i}/{len(x)}")
        scores[i] = model.process(x[i])
    return scores


def compute_auc(y_true: np.ndarray, y_score: np.ndarray) -> Dict[str, float] | None:
    if y_true is None or len(np.unique(y_true)) < 2:
        return None
    try:
        from sklearn.metrics import average_precision_score, roc_auc_score
    except Exception:
        return None
    return {
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc": float(average_precision_score(y_true, y_score)),
    }


def to_md_table(df: pd.DataFrame) -> str:
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


def plot_tradeoff(df: pd.DataFrame, out_path: Path) -> None:
    plt.figure(figsize=(7.8, 5.0))
    color_map = {
        "transformer": "#1f77b4",
        "transformer_tailreg": "#ff7f0e",
        "da": "#2ca02c",
    }
    marker_map = {
        "fixed_id_q99": "o",
        "calibrated_budget5000_target1pct": "s",
    }

    for _, row in df.iterrows():
        x = float(row["ood_benign_alarm_ratio"])
        y = float(row["attack_detection_rate"])
        det = str(row["detector"])
        policy = str(row["threshold_policy"])
        plt.scatter(
            x,
            y,
            c=color_map.get(det, "#444444"),
            marker=marker_map.get(policy, "o"),
            s=80,
            alpha=0.9,
        )
        label = f"{det}-{policy.replace('calibrated_budget5000_target1pct', 'cal')}"
        plt.text(x + 0.003, y + 0.003, label, fontsize=8)

    plt.xlabel("OOD benign alarm ratio (lower is better)")
    plt.ylabel("Attack detection rate (higher is better)")
    plt.title("Joint trade-off on frontend100 stronger OOD mainline")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Joint benign-FP and attack-detection evaluation on frontend100 mainline.")
    parser.add_argument("--run-tag", default=f"frontend100_joint_eval_stage1_{today}")
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--target-alarm-rate", type=float, default=0.01)
    args = parser.parse_args()

    out_dir = ROOT_DIR / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    data_dir = out_dir / "data"
    attack_csv = data_dir / "attack_source_100.csv"
    if not attack_csv.exists():
        raise FileNotFoundError(f"Missing attack source csv: {attack_csv}")
    attack_x = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)
    if attack_x.ndim != 2 or attack_x.shape[1] != 100:
        raise RuntimeError(f"Expected 100-D attack input, got shape={attack_x.shape}")

    detectors = {
        "transformer": {
            "score_run": ROOT_DIR / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "transformer_seed42",
            "checkpoint": ROOT_DIR / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "transformer_seed42" / "kitnet_transformer_seed42.ckpt",
        },
        "transformer_tailreg": {
            "score_run": ROOT_DIR / "runs" / "frontend100_tailreg_hparam_scan_2026-03-28" / "tailreg_l0.2_k1.0_seed42",
            "checkpoint": ROOT_DIR / "runs" / "frontend100_tailreg_hparam_scan_2026-03-28" / "tailreg_l0.2_k1.0_seed42" / "kitnet_transformer_tailreg_seed42.ckpt",
        },
        "da": {
            "score_run": ROOT_DIR / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "da_seed42",
            "checkpoint": ROOT_DIR / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "da_seed42" / "kitnet_da_seed42.ckpt",
        },
    }

    rows: List[Dict] = []
    details: Dict[str, Dict] = {}

    for det, info in detectors.items():
        print(f"[detector] {det}")
        score_run = info["score_run"]
        metrics = json.loads((score_run / "metrics.json").read_text(encoding="utf-8"))
        benign_name = list(metrics["ood_benign"].keys())[0]

        id_scores = np.load(score_run / "id_scores.npy").astype(np.float64)
        ood_scores = np.load(score_run / f"{benign_name}_scores.npy").astype(np.float64)

        model = kit.KitNET.load_checkpoint(info["checkpoint"])
        attack_scores = score_attack(model, attack_x)
        np.save(out_dir / f"{det}_attack_scores.npy", attack_scores)

        id_stat = score_stats(id_scores)
        ood_stat = score_stats(ood_scores)
        attack_stat = score_stats(attack_scores)

        thr_fixed = float(np.quantile(id_scores, 0.99))
        fixed_alarm = float(np.mean(ood_scores > thr_fixed))
        fixed_det = float(np.mean(attack_scores > thr_fixed))

        b = int(args.calibration_budget)
        if b >= len(ood_scores):
            raise ValueError(f"calibration_budget={b} must be < len(ood_scores)={len(ood_scores)}")
        ood_calib = ood_scores[:b]
        ood_eval = ood_scores[b:]
        thr_cal = float(np.quantile(ood_calib, 1.0 - args.target_alarm_rate))
        cal_alarm = float(np.mean(ood_eval > thr_cal))
        cal_det = float(np.mean(attack_scores > thr_cal))

        y_eval = np.concatenate(
            [
                np.zeros(len(ood_eval), dtype=np.int64),
                np.ones(len(attack_scores), dtype=np.int64),
            ]
        )
        s_eval = np.concatenate([ood_eval, attack_scores])
        auc = compute_auc(y_eval, s_eval)

        rows.append(
            {
                "detector": det,
                "threshold_policy": "fixed_id_q99",
                "threshold_value": thr_fixed,
                "ood_benign_alarm_ratio": fixed_alarm,
                "attack_detection_rate": fixed_det,
                "id_mean": id_stat["mean"],
                "id_std": id_stat["std"],
                "id_q95": id_stat["q95"],
                "id_q99": id_stat["q99"],
                "ood_mean": ood_stat["mean"],
                "ood_std": ood_stat["std"],
                "ood_q95": ood_stat["q95"],
                "ood_q99": ood_stat["q99"],
                "attack_mean": attack_stat["mean"],
                "attack_std": attack_stat["std"],
                "attack_q95": attack_stat["q95"],
                "attack_q99": attack_stat["q99"],
                "roc_auc_ood_eval_vs_attack": np.nan if auc is None else auc["roc_auc"],
                "pr_auc_ood_eval_vs_attack": np.nan if auc is None else auc["pr_auc"],
            }
        )
        rows.append(
            {
                "detector": det,
                "threshold_policy": "calibrated_budget5000_target1pct",
                "threshold_value": thr_cal,
                "ood_benign_alarm_ratio": cal_alarm,
                "attack_detection_rate": cal_det,
                "id_mean": id_stat["mean"],
                "id_std": id_stat["std"],
                "id_q95": id_stat["q95"],
                "id_q99": id_stat["q99"],
                "ood_mean": ood_stat["mean"],
                "ood_std": ood_stat["std"],
                "ood_q95": ood_stat["q95"],
                "ood_q99": ood_stat["q99"],
                "attack_mean": attack_stat["mean"],
                "attack_std": attack_stat["std"],
                "attack_q95": attack_stat["q95"],
                "attack_q99": attack_stat["q99"],
                "roc_auc_ood_eval_vs_attack": np.nan if auc is None else auc["roc_auc"],
                "pr_auc_ood_eval_vs_attack": np.nan if auc is None else auc["pr_auc"],
            }
        )

        details[det] = {
            "source_score_run": str(score_run),
            "source_checkpoint": str(info["checkpoint"]),
            "ood_benign_dataset_name": benign_name,
            "attack_rows": int(len(attack_scores)),
            "calibration_budget": int(b),
            "calibration_eval_rows": int(len(ood_eval)),
        }

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "joint_eval_results.csv", index=False)
    (out_dir / "joint_eval_results.md").write_text(to_md_table(df), encoding="utf-8")
    plot_tradeoff(df, plot_dir / "benign_alarm_vs_attack_detection.png")

    # summary
    lines: List[str] = []
    lines.append("# Frontend100 Joint Eval Stage1 Summary")
    lines.append("")
    lines.append("## Protocol")
    lines.append("- ID benign capture: CTU-Honeypot-Capture-7-6")
    lines.append("- OOD benign capture: CTU-Honeypot-Capture-4-1")
    lines.append("- Attack capture: CTU-IoT-Malware-Capture-34-1 (capture-level proxy labels)")
    lines.append("- Input: original-frontend 100-D")
    lines.append("- train_samples=8000, id_eval_samples=5000, fm=2000, ad=6000")
    lines.append("- Calibration: budget=5000, target=1%, non-overlap OOD eval split")
    lines.append("")
    lines.append("## Joint results (OOD benign alarm vs attack detection)")
    show = df[
        [
            "detector",
            "threshold_policy",
            "threshold_value",
            "ood_benign_alarm_ratio",
            "attack_detection_rate",
            "roc_auc_ood_eval_vs_attack",
            "pr_auc_ood_eval_vs_attack",
        ]
    ]
    lines.append(to_md_table(show))
    lines.append("")

    lines.append("## Quick interpretation")
    for det in ["transformer", "transformer_tailreg", "da"]:
        sub = df[df["detector"] == det].reset_index(drop=True)
        fixed_alarm = float(sub[sub["threshold_policy"] == "fixed_id_q99"]["ood_benign_alarm_ratio"].iloc[0])
        fixed_det = float(sub[sub["threshold_policy"] == "fixed_id_q99"]["attack_detection_rate"].iloc[0])
        cal_alarm = float(sub[sub["threshold_policy"] == "calibrated_budget5000_target1pct"]["ood_benign_alarm_ratio"].iloc[0])
        cal_det = float(sub[sub["threshold_policy"] == "calibrated_budget5000_target1pct"]["attack_detection_rate"].iloc[0])
        lines.append(
            f"- {det}: alarm {fixed_alarm:.4f}->{cal_alarm:.4f}, attack detection {fixed_det:.4f}->{cal_det:.4f}"
        )

    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    config = {
        "stage": "frontend100_joint_eval_stage1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "protocol": {
            "id_capture": "CTU-Honeypot-Capture-7-6",
            "ood_benign_capture": "CTU-Honeypot-Capture-4-1",
            "attack_capture": "CTU-IoT-Malware-Capture-34-1",
            "input_dim": 100,
            "train_samples": 8000,
            "id_eval_samples": 5000,
            "fm_grace": 2000,
            "ad_grace": 6000,
            "seed": 42,
        },
        "calibration": {
            "budget": int(args.calibration_budget),
            "target_alarm_rate": float(args.target_alarm_rate),
            "non_overlap_eval": True,
        },
        "detectors": details,
        "attack_source_csv": str(attack_csv),
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[done] joint eval output: {out_dir}")


if __name__ == "__main__":
    main()
