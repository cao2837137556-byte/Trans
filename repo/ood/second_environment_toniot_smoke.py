from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    return obj


def eval_threshold(threshold: float, id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio": float(np.mean(ood_scores > threshold)),
        "attack_detection": float(np.mean(attack_scores > threshold)),
    }


def choose_detection_floor(df: pd.DataFrame, det_floor: float) -> pd.Series | None:
    cand = df[df["attack_detection"] >= det_floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(["ood_alarm_ratio", "threshold"], ascending=[True, False])
    return cand.iloc[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="TON-IoT local smoke for second-environment fallback.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--csv-path", type=Path, required=True)
    parser.add_argument("--label-col", default="label")
    parser.add_argument("--normal-label", default="0")
    parser.add_argument("--id-benign-n", type=int, default=30000)
    parser.add_argument("--ood-benign-n", type=int, default=20000)
    parser.add_argument("--attack-n", type=int, default=100000)
    parser.add_argument("--naive-budget", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.csv_path, low_memory=False)
    if args.label_col not in df.columns:
        raise RuntimeError(f"Missing label column: {args.label_col}")

    label = df[args.label_col].astype(str)
    benign_all = df[label == str(args.normal_label)].copy()
    attack_all = df[label != str(args.normal_label)].copy()
    if len(benign_all) < args.id_benign_n + args.ood_benign_n:
        raise RuntimeError(
            f"Insufficient benign samples: need {args.id_benign_n + args.ood_benign_n}, got {len(benign_all)}"
        )
    if len(attack_all) < args.attack_n:
        raise RuntimeError(f"Insufficient attack samples: need {args.attack_n}, got {len(attack_all)}")

    # Keep deterministic temporal split on benign stream.
    id_df = benign_all.iloc[: args.id_benign_n].copy()
    ood_df = benign_all.iloc[args.id_benign_n : args.id_benign_n + args.ood_benign_n].copy()
    attack_idx = rng.choice(len(attack_all), size=args.attack_n, replace=False)
    attack_df = attack_all.iloc[attack_idx].copy()

    numeric_cols = [
        c
        for c in df.columns
        if c != args.label_col and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not numeric_cols:
        raise RuntimeError("No numeric columns available for smoke.")

    id_x = id_df[numeric_cols].to_numpy(dtype=np.float64)
    ood_x = ood_df[numeric_cols].to_numpy(dtype=np.float64)
    attack_x = attack_df[numeric_cols].to_numpy(dtype=np.float64)

    models = {
        "isolation_forest": make_pipeline(
            StandardScaler(),
            IsolationForest(n_estimators=300, contamination=0.01, random_state=args.seed, n_jobs=-1),
        ),
        "oneclass_svm": make_pipeline(StandardScaler(), OneClassSVM(kernel="rbf", gamma="scale", nu=0.01)),
    }

    results: List[Dict[str, object]] = []
    scans: List[Dict[str, object]] = []
    for model_name, model in models.items():
        model.fit(id_x)
        id_scores = -model.decision_function(id_x)
        ood_scores = -model.decision_function(ood_x)
        attack_scores = -model.decision_function(attack_x)

        auc = float(
            roc_auc_score(
                np.concatenate([np.zeros(len(ood_scores), dtype=np.int64), np.ones(len(attack_scores), dtype=np.int64)]),
                np.concatenate([ood_scores, attack_scores]),
            )
        )

        fixed = eval_threshold(float(np.quantile(id_scores, 0.99)), id_scores, ood_scores, attack_scores)
        results.append({"model": model_name, "policy_name": "fixed_id_q99", "roc_auc_attack_vs_ood": auc, **fixed})

        budget = min(args.naive_budget, len(ood_scores))
        naive_thr = float(np.quantile(ood_scores[:budget], 0.99))
        naive = eval_threshold(naive_thr, id_scores, ood_scores, attack_scores)
        results.append(
            {
                "model": model_name,
                "policy_name": f"naive_calibrated_budget{budget}_target1pct",
                "roc_auc_attack_vs_ood": auc,
                **naive,
            }
        )

        all_scores = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
        grid = np.unique(np.quantile(all_scores, np.linspace(0.0, 1.0, 512)))
        model_scan = []
        for thr in grid:
            row = eval_threshold(float(thr), id_scores, ood_scores, attack_scores)
            row["model"] = model_name
            model_scan.append(row)
            scans.append(row)
        det50 = choose_detection_floor(pd.DataFrame(model_scan), 0.50)
        if det50 is not None:
            results.append(
                {
                    "model": model_name,
                    "policy_name": "det_floor_50pct_min_alarm",
                    "roc_auc_attack_vs_ood": auc,
                    **det50.to_dict(),
                }
            )

    split_df = pd.DataFrame(
        [
            {"split": "id_benign", "n_samples": int(len(id_x)), "n_features": int(id_x.shape[1])},
            {"split": "ood_benign", "n_samples": int(len(ood_x)), "n_features": int(ood_x.shape[1])},
            {"split": "attack", "n_samples": int(len(attack_x)), "n_features": int(attack_x.shape[1])},
        ]
    )
    result_df = pd.DataFrame(results)
    scan_df = pd.DataFrame(scans)

    split_df.to_csv(run_dir / "split_summary.csv", index=False)
    result_df.to_csv(run_dir / "smoke_results.csv", index=False)
    scan_df.to_csv(run_dir / "smoke_scan.csv", index=False)
    (run_dir / "feature_columns.txt").write_text("\n".join(numeric_cols) + "\n", encoding="utf-8")

    config = {
        "run_tag": args.run_tag,
        "csv_path": str(args.csv_path),
        "label_col": args.label_col,
        "normal_label": args.normal_label,
        "id_benign_n": int(args.id_benign_n),
        "ood_benign_n": int(args.ood_benign_n),
        "attack_n": int(args.attack_n),
        "naive_budget": int(args.naive_budget),
        "seed": int(args.seed),
    }
    run_spec = {
        "stage": "second_environment_toniot_smoke",
        "goal": "TON-IoT fallback local smoke under fixed mainline policy family.",
        "policies": ["fixed_id_q99", f"naive_calibrated_budget{min(args.naive_budget, len(ood_x))}_target1pct", "det_floor_50pct_min_alarm"],
    }
    (run_dir / "config.json").write_text(json.dumps(clean(config), indent=2) + "\n", encoding="utf-8")
    (run_dir / "run_spec.json").write_text(json.dumps(clean(run_spec), indent=2) + "\n", encoding="utf-8")
    (run_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    lines = [
        "# TON-IoT Second Environment Smoke Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- CSV: `{args.csv_path}`",
        f"- Label column: `{args.label_col}` (`normal={args.normal_label}`)",
        f"- Numeric feature count: `{len(numeric_cols)}`",
        "",
        "## Split",
    ]
    for _, row in split_df.iterrows():
        lines.append(f"- `{row['split']}`: {int(row['n_samples'])} samples, {int(row['n_features'])} features")
    lines.append("")
    lines.append("## Results")
    for _, row in result_df.sort_values(["model", "policy_name"]).iterrows():
        lines.append(
            f"- `{row['model']}` / `{row['policy_name']}`: "
            f"ood_alarm={float(row['ood_alarm_ratio']):.6f}, "
            f"attack_det={float(row['attack_detection']):.6f}, "
            f"id_alarm={float(row['id_alarm_ratio']):.6f}, "
            f"auc={float(row['roc_auc_attack_vs_ood']):.6f}"
        )
    lines.append("")
    lines.append("## Note")
    lines.append("- This is a local smoke node for TON-IoT fallback readiness, not a formal multi-seed comparison.")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "id_n": int(len(id_x)),
                "ood_n": int(len(ood_x)),
                "attack_n": int(len(attack_x)),
                "feature_n": int(len(numeric_cols)),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
