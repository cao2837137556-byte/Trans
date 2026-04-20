from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
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


def choose_detection_floor(df: pd.DataFrame, det_floor: float) -> pd.Series | None:
    cand = df[df["attack_detection"] >= det_floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(["ood_alarm_ratio", "threshold"], ascending=[True, False])
    return cand.iloc[0]


def eval_threshold(
    threshold: float,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio": float(np.mean(ood_scores > threshold)),
        "attack_detection": float(np.mean(attack_scores > threshold)),
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="BoT-IoT second-environment local smoke.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--train-csv", type=Path, required=True)
    parser.add_argument("--test-csv", type=Path, required=True)
    parser.add_argument("--label-col", default="attack")
    parser.add_argument("--normal-label", default="0")
    parser.add_argument("--max-attack-eval", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(args.train_csv, low_memory=False)
    test_df = pd.read_csv(args.test_csv, low_memory=False)
    if args.label_col not in train_df.columns or args.label_col not in test_df.columns:
        raise RuntimeError(f"Missing label column: {args.label_col}")

    train_label = train_df[args.label_col].astype(str)
    test_label = test_df[args.label_col].astype(str)
    train_is_benign = train_label == str(args.normal_label)
    test_is_benign = test_label == str(args.normal_label)

    numeric_cols = [
        c
        for c in train_df.columns
        if c != args.label_col
        and pd.api.types.is_numeric_dtype(train_df[c])
        and c in test_df.columns
    ]
    if not numeric_cols:
        raise RuntimeError("No shared numeric feature columns available.")

    id_df = train_df.loc[train_is_benign, numeric_cols].copy()
    ood_df = test_df.loc[test_is_benign, numeric_cols].copy()
    attack_df = test_df.loc[~test_is_benign, numeric_cols].copy()

    # Keep smoke bounded while preserving class composition.
    if len(attack_df) > args.max_attack_eval:
        idx = rng.choice(len(attack_df), size=args.max_attack_eval, replace=False)
        attack_df = attack_df.iloc[idx].copy()

    id_x = id_df.to_numpy(dtype=np.float64)
    ood_x = ood_df.to_numpy(dtype=np.float64)
    attack_x = attack_df.to_numpy(dtype=np.float64)

    if len(id_x) < 100:
        raise RuntimeError(f"ID benign samples too small for smoke: {len(id_x)}")
    if len(ood_x) < 50:
        raise RuntimeError(f"OOD benign samples too small for smoke: {len(ood_x)}")
    if len(attack_x) < 100:
        raise RuntimeError(f"Attack samples too small for smoke: {len(attack_x)}")

    models = {
        "isolation_forest": make_pipeline(
            StandardScaler(),
            IsolationForest(n_estimators=300, contamination=0.01, random_state=args.seed, n_jobs=-1),
        ),
        "oneclass_svm": make_pipeline(StandardScaler(), OneClassSVM(kernel="rbf", gamma="scale", nu=0.01)),
    }

    result_rows: List[Dict[str, object]] = []
    scan_rows: List[Dict[str, object]] = []
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

        fixed = eval_threshold(float(np.quantile(id_scores, 0.99)), id_scores=id_scores, ood_scores=ood_scores, attack_scores=attack_scores)
        result_rows.append(
            {
                "model": model_name,
                "policy_name": "fixed_id_q99",
                "roc_auc_attack_vs_ood": auc,
                **fixed,
            }
        )

        calib_n = min(500, len(ood_scores))
        naive_thr = float(np.quantile(ood_scores[:calib_n], 0.99))
        naive = eval_threshold(naive_thr, id_scores=id_scores, ood_scores=ood_scores, attack_scores=attack_scores)
        result_rows.append(
            {
                "model": model_name,
                "policy_name": "naive_calibrated_budget500_target1pct",
                "roc_auc_attack_vs_ood": auc,
                **naive,
            }
        )

        all_scores = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
        thr_grid = np.unique(np.quantile(all_scores, np.linspace(0.0, 1.0, 512)))
        for thr in thr_grid:
            row = eval_threshold(float(thr), id_scores=id_scores, ood_scores=ood_scores, attack_scores=attack_scores)
            row["model"] = model_name
            scan_rows.append(row)
        scan_df = pd.DataFrame([r for r in scan_rows if r["model"] == model_name])
        det50 = choose_detection_floor(scan_df, det_floor=0.50)
        if det50 is not None:
            result_rows.append(
                {
                    "model": model_name,
                    "policy_name": "det_floor_50pct_min_alarm",
                    "roc_auc_attack_vs_ood": auc,
                    **det50.to_dict(),
                }
            )

    result_df = pd.DataFrame(result_rows)
    scan_df = pd.DataFrame(scan_rows)
    split_df = pd.DataFrame(
        [
            {"split": "id_benign_train", "n_samples": int(len(id_x)), "n_features": int(id_x.shape[1])},
            {"split": "ood_benign_test", "n_samples": int(len(ood_x)), "n_features": int(ood_x.shape[1])},
            {"split": "attack_test", "n_samples": int(len(attack_x)), "n_features": int(attack_x.shape[1])},
        ]
    )

    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(id_x, columns=numeric_cols).to_csv(data_dir / "id_benign_numeric.csv", index=False)
    pd.DataFrame(ood_x, columns=numeric_cols).to_csv(data_dir / "ood_benign_numeric.csv", index=False)
    pd.DataFrame(attack_x, columns=numeric_cols).to_csv(data_dir / "attack_numeric.csv", index=False)

    split_df.to_csv(run_dir / "split_summary.csv", index=False)
    result_df.to_csv(run_dir / "smoke_results.csv", index=False)
    scan_df.to_csv(run_dir / "smoke_scan.csv", index=False)
    (run_dir / "feature_columns.txt").write_text("\n".join(numeric_cols) + "\n", encoding="utf-8")

    config = {
        "run_tag": args.run_tag,
        "train_csv": str(args.train_csv),
        "test_csv": str(args.test_csv),
        "label_col": args.label_col,
        "normal_label": args.normal_label,
        "max_attack_eval": int(args.max_attack_eval),
        "seed": int(args.seed),
    }
    run_spec = {
        "stage": "second_environment_botiot_smoke",
        "goal": "Build a minimal BoT-IoT second-environment split and run quick unsupervised smoke baselines.",
        "fixed_policies": [
            "fixed_id_q99",
            "naive_calibrated_budget500_target1pct",
            "det_floor_50pct_min_alarm",
        ],
    }
    write_text(run_dir / "config.json", json.dumps(clean(config), indent=2) + "\n")
    write_text(run_dir / "run_spec.json", json.dumps(clean(run_spec), indent=2) + "\n")
    write_text(run_dir / "command.txt", " ".join(sys.argv) + "\n")

    summary_lines = [
        "# BoT-IoT Second Environment Smoke Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Train CSV: `{args.train_csv}`",
        f"- Test CSV: `{args.test_csv}`",
        f"- Label column: `{args.label_col}` (`normal={args.normal_label}`)",
        f"- Numeric feature count used: `{len(numeric_cols)}`",
        "",
        "## Split Summary",
    ]
    for _, row in split_df.iterrows():
        summary_lines.append(f"- `{row['split']}`: {int(row['n_samples'])} samples, {int(row['n_features'])} features")
    summary_lines += ["", "## Smoke Results"]
    for _, row in result_df.sort_values(["model", "policy_name"]).iterrows():
        summary_lines.append(
            f"- `{row['model']}` / `{row['policy_name']}`: "
            f"ood_alarm={float(row['ood_alarm_ratio']):.6f}, "
            f"attack_det={float(row['attack_detection']):.6f}, "
            f"id_alarm={float(row['id_alarm_ratio']):.6f}, "
            f"auc={float(row['roc_auc_attack_vs_ood']):.6f}"
        )
    summary_lines += [
        "",
        "## Note",
        "- This is a local smoke node for second-environment readiness, not a formal multi-seed model comparison.",
    ]
    write_text(run_dir / "summary.md", "\n".join(summary_lines) + "\n")

    payload = {
        "run_dir": str(run_dir),
        "id_n": int(len(id_x)),
        "ood_n": int(len(ood_x)),
        "attack_n": int(len(attack_x)),
        "feature_n": int(len(numeric_cols)),
    }
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
