from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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


def build_models(seed: int) -> Dict[str, object]:
    return {
        "isolation_forest": make_pipeline(
            StandardScaler(),
            IsolationForest(n_estimators=300, contamination=0.01, random_state=seed, n_jobs=-1),
        ),
        "oneclass_svm": make_pipeline(StandardScaler(), OneClassSVM(kernel="rbf", gamma="scale", nu=0.01)),
    }


def orientation_auc(ood_scores: np.ndarray, attack_scores: np.ndarray, score_sign: int) -> float:
    y = np.concatenate([np.zeros(len(ood_scores), dtype=np.int64), np.ones(len(attack_scores), dtype=np.int64)])
    s = score_sign * np.concatenate([ood_scores, attack_scores]).astype(np.float64)
    return float(roc_auc_score(y, s))


def choose_orientation(ood_scores: np.ndarray, attack_scores: np.ndarray) -> Tuple[int, float, float]:
    auc_plus = orientation_auc(ood_scores, attack_scores, score_sign=1)
    auc_minus = orientation_auc(ood_scores, attack_scores, score_sign=-1)
    if auc_plus >= auc_minus:
        return 1, auc_plus, auc_minus
    return -1, auc_minus, auc_plus


def summarize_scores(name: str, id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray) -> Dict[str, float]:
    return {
        "model": name,
        "id_q50": float(np.quantile(id_scores, 0.5)),
        "id_q99": float(np.quantile(id_scores, 0.99)),
        "ood_q50": float(np.quantile(ood_scores, 0.5)),
        "ood_q99": float(np.quantile(ood_scores, 0.99)),
        "attack_q50": float(np.quantile(attack_scores, 0.5)),
        "attack_q99": float(np.quantile(attack_scores, 0.99)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TON-IoT formal precheck with score polarity gate.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--csv-path", type=Path, required=True)
    parser.add_argument("--label-col", default="label")
    parser.add_argument("--normal-label", default="0")
    parser.add_argument("--id-benign-n", type=int, default=30000)
    parser.add_argument("--ood-benign-n", type=int, default=20000)
    parser.add_argument("--attack-n", type=int, default=100000)
    parser.add_argument("--naive-budget", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-acceptable-auc", type=float, default=0.60)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.csv_path, low_memory=False)
    if args.label_col not in df.columns:
        raise RuntimeError(f"Missing label column: {args.label_col}")

    labels = df[args.label_col].astype(str)
    benign_idx_all = np.flatnonzero(labels.to_numpy() == str(args.normal_label))
    attack_idx_all = np.flatnonzero(labels.to_numpy() != str(args.normal_label))
    if len(benign_idx_all) < args.id_benign_n + args.ood_benign_n:
        raise RuntimeError(
            f"Insufficient benign rows: need {args.id_benign_n + args.ood_benign_n}, got {len(benign_idx_all)}"
        )
    if len(attack_idx_all) < args.attack_n:
        raise RuntimeError(f"Insufficient attack rows: need {args.attack_n}, got {len(attack_idx_all)}")

    id_idx = benign_idx_all[: args.id_benign_n]
    ood_idx = benign_idx_all[args.id_benign_n : args.id_benign_n + args.ood_benign_n]
    attack_idx = rng.choice(attack_idx_all, size=args.attack_n, replace=False)

    numeric_cols = [c for c in df.columns if c != args.label_col and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        raise RuntimeError("No numeric columns available.")

    x = df[numeric_cols].to_numpy(dtype=np.float64)
    id_x = x[id_idx]
    ood_x = x[ood_idx]
    attack_x = x[attack_idx]

    orientation_rows: List[Dict[str, object]] = []
    policy_rows: List[Dict[str, object]] = []
    dist_rows: List[Dict[str, object]] = []

    for model_name, model in build_models(seed=args.seed).items():
        model.fit(id_x)
        raw_id = model.decision_function(id_x).astype(np.float64)
        raw_ood = model.decision_function(ood_x).astype(np.float64)
        raw_attack = model.decision_function(attack_x).astype(np.float64)

        chosen_sign, chosen_auc, other_auc = choose_orientation(raw_ood, raw_attack)
        chosen_name = "raw_decision" if chosen_sign == 1 else "neg_raw_decision"
        orientation_rows.append(
            {
                "model": model_name,
                "chosen_score": chosen_name,
                "chosen_sign": int(chosen_sign),
                "auc_chosen": float(chosen_auc),
                "auc_other_orientation": float(other_auc),
                "improvement_over_other": float(chosen_auc - other_auc),
            }
        )

        id_scores = chosen_sign * raw_id
        ood_scores = chosen_sign * raw_ood
        attack_scores = chosen_sign * raw_attack
        dist_rows.append(summarize_scores(model_name, id_scores, ood_scores, attack_scores))

        fixed = eval_threshold(float(np.quantile(id_scores, 0.99)), id_scores, ood_scores, attack_scores)
        policy_rows.append(
            {"model": model_name, "policy_name": "fixed_id_q99", "score_orientation": chosen_name, "roc_auc_attack_vs_ood": chosen_auc, **fixed}
        )

        budget = min(args.naive_budget, len(ood_scores))
        naive_thr = float(np.quantile(ood_scores[:budget], 0.99))
        naive = eval_threshold(naive_thr, id_scores, ood_scores, attack_scores)
        policy_rows.append(
            {
                "model": model_name,
                "policy_name": f"naive_calibrated_budget{budget}_target1pct",
                "score_orientation": chosen_name,
                "roc_auc_attack_vs_ood": chosen_auc,
                **naive,
            }
        )

        grid = np.unique(np.quantile(np.concatenate([id_scores, ood_scores, attack_scores]), np.linspace(0.0, 1.0, 512)))
        scan = []
        for thr in grid:
            row = eval_threshold(float(thr), id_scores, ood_scores, attack_scores)
            row["threshold"] = float(thr)
            scan.append(row)
        det50 = choose_detection_floor(pd.DataFrame(scan), det_floor=0.50)
        if det50 is not None:
            policy_rows.append(
                {
                    "model": model_name,
                    "policy_name": "det_floor_50pct_min_alarm",
                    "score_orientation": chosen_name,
                    "roc_auc_attack_vs_ood": chosen_auc,
                    **det50.to_dict(),
                }
            )

    orientation_df = pd.DataFrame(orientation_rows)
    policy_df = pd.DataFrame(policy_rows)
    dist_df = pd.DataFrame(dist_rows)

    orientation_df.to_csv(run_dir / "polarity_check.csv", index=False)
    policy_df.to_csv(run_dir / "precheck_policy_results.csv", index=False)
    dist_df.to_csv(run_dir / "score_distribution_stats.csv", index=False)
    (run_dir / "feature_columns.txt").write_text("\n".join(numeric_cols) + "\n", encoding="utf-8")

    split_manifest = {
        "csv_path": str(args.csv_path),
        "label_col": args.label_col,
        "normal_label": str(args.normal_label),
        "seed": int(args.seed),
        "id_benign_n": int(args.id_benign_n),
        "ood_benign_n": int(args.ood_benign_n),
        "attack_n": int(args.attack_n),
        "id_indices": [int(v) for v in id_idx],
        "ood_indices": [int(v) for v in ood_idx],
        "attack_indices": [int(v) for v in attack_idx],
    }
    (run_dir / "split_manifest.json").write_text(json.dumps(clean(split_manifest), indent=2) + "\n", encoding="utf-8")

    min_auc = float(orientation_df["auc_chosen"].min()) if len(orientation_df) else 0.0
    if min_auc < float(args.min_acceptable_auc):
        verdict = "warning_polarity_checked_but_signal_weak"
        reason = f"After orientation correction, at least one model still has AUC below {args.min_acceptable_auc:.2f}."
    else:
        verdict = "polarity_checked_ready_for_formal_object_runs"
        reason = "Orientation and split manifest are fixed; baseline signal passes minimum AUC gate."

    config = {
        "run_tag": args.run_tag,
        "csv_path": str(args.csv_path),
        "label_col": args.label_col,
        "normal_label": str(args.normal_label),
        "id_benign_n": int(args.id_benign_n),
        "ood_benign_n": int(args.ood_benign_n),
        "attack_n": int(args.attack_n),
        "naive_budget": int(args.naive_budget),
        "seed": int(args.seed),
        "min_acceptable_auc": float(args.min_acceptable_auc),
    }
    run_spec = {
        "stage": "second_environment_toniot_precheck",
        "goal": "Freeze split manifest and verify score polarity before formal second-environment object runs.",
    }
    (run_dir / "config.json").write_text(json.dumps(clean(config), indent=2) + "\n", encoding="utf-8")
    (run_dir / "run_spec.json").write_text(json.dumps(clean(run_spec), indent=2) + "\n", encoding="utf-8")
    (run_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    lines = [
        "# TON-IoT Formal Precheck Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Verdict: `{verdict}`",
        f"- Reason: {reason}",
        f"- CSV: `{args.csv_path}`",
        f"- Split: ID={len(id_idx)}, OOD={len(ood_idx)}, attack={len(attack_idx)}",
        f"- Numeric feature count: `{len(numeric_cols)}`",
        "",
        "## Polarity",
    ]
    for _, row in orientation_df.sort_values("model").iterrows():
        lines.append(
            f"- `{row['model']}`: chosen `{row['chosen_score']}`, auc={float(row['auc_chosen']):.6f}, "
            f"other={float(row['auc_other_orientation']):.6f}, delta={float(row['improvement_over_other']):.6f}"
        )
    lines += [
        "",
        "## Next",
        "- Use `split_manifest.json` as the fixed source split for formal object runs.",
        "- Run `dA`, `current strongest candidate`, and `FT` line under the same policy family on this split.",
    ]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict}, ensure_ascii=True))


if __name__ == "__main__":
    main()
