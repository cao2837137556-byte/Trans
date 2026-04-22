from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc
import frontend100_timescale_tokenizer_v1_3 as tv3
import frontend_f2_v7_source_rich_diagnostic_ranker as v7
import frontend_f2_v7_1_source_rich_label_budget_ranker as v71


DEFAULT_POSITIVE_BUDGETS = "16,32,64"
DEFAULT_SAMPLE_SEEDS = "42,43,44,45,46"
TARGET_ALARM = 0.01


def parse_int_list(spec: str) -> List[int]:
    values: List[int] = []
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        value = int(token)
        if value not in values:
            values.append(value)
    if not values:
        raise ValueError(f"No integers parsed from {spec!r}")
    return values


def threshold_for_alarm(scores: np.ndarray, target_alarm: float, n_candidates: int = 4000) -> float:
    scores = np.asarray(scores, dtype=np.float64)
    q_levels = np.linspace(0.0, 1.0, int(n_candidates) + 1)[1:]
    candidates = np.unique(np.quantile(scores, q_levels))
    for thr in sorted(candidates):
        if float(np.mean(scores > thr)) <= float(target_alarm):
            return float(thr)
    return float(np.max(scores))


def guarded_val_threshold(
    score_id_calib: np.ndarray,
    score_ood_val: np.ndarray,
    target_alarm: float,
    n_candidates: int = 4000,
) -> Dict:
    pool = np.concatenate([score_id_calib, score_ood_val]).astype(np.float64)
    q_levels = np.linspace(0.0, 1.0, int(n_candidates) + 1)[1:]
    candidates = np.unique(np.quantile(pool, q_levels))
    for thr in sorted(candidates):
        id_alarm = float(np.mean(score_id_calib > thr))
        ood_val_alarm = float(np.mean(score_ood_val > thr))
        if id_alarm <= float(target_alarm) and ood_val_alarm <= float(target_alarm):
            return {
                "threshold": float(thr),
                "id_calib_alarm_at_selection": id_alarm,
                "ood_val_alarm_at_selection": ood_val_alarm,
                "selection_feasible": True,
            }
    thr = float(np.max(pool))
    return {
        "threshold": thr,
        "id_calib_alarm_at_selection": float(np.mean(score_id_calib > thr)),
        "ood_val_alarm_at_selection": float(np.mean(score_ood_val > thr)),
        "selection_feasible": False,
    }


def split_info_dict(
    id_train_end: int,
    id_val_end: int,
    id_calib_end: int,
    id_rows: int,
    ood_train_end: int,
    ood_val_end: int,
    ood_rows: int,
    high_idx: np.ndarray,
    attack_split: Dict[str, np.ndarray],
) -> Dict:
    return {
        "id": {
            "train": [0, id_train_end],
            "val": [id_train_end, id_val_end],
            "calibration": [id_val_end, id_calib_end],
            "eval_unused_by_threshold": [id_calib_end, id_rows],
        },
        "ood": {
            "train": [0, ood_train_end],
            "val_threshold_only": [ood_train_end, ood_val_end],
            "eval_final_only": [ood_val_end, ood_rows],
        },
        "attack_high": {
            "total_high": int(len(high_idx)),
            "train_pool_count": int(len(attack_split["train"])),
            "val_threshold_diagnostics_count": int(len(attack_split["val"])),
            "eval_final_count": int(len(attack_split["eval"])),
            "train_first_last": [int(attack_split["train"][0]), int(attack_split["train"][-1])],
            "val_first_last": [int(attack_split["val"][0]), int(attack_split["val"][-1])],
            "eval_first_last": [int(attack_split["eval"][0]), int(attack_split["eval"][-1])],
        },
    }


def metric_row(
    policy_name: str,
    threshold: float,
    score_id_calib: np.ndarray,
    score_id_eval: np.ndarray,
    score_ood_val: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_val: np.ndarray,
    score_attack_eval: np.ndarray,
    auc_eval: float,
    auc_val: float,
    budget: int,
    sample_seed: int,
    selected_pos_idx: np.ndarray,
    c_value: float,
    target_alarm: float,
    threshold_source: str,
    selection_info: Dict | None = None,
) -> Dict:
    selection_info = selection_info or {}
    return {
        "object_label": "v7_2_source_rich_fairness_validation",
        "detector_family": "frontend_f2_v7_2_fairness_validation",
        "score_label": "logistic_decision_function",
        "token_profile": "flat_source_rich_260",
        "source_mode": "source_rich_v1_frozen",
        "input_tensor": "source_rich_v1[20x13]_flat260",
        "model": "LogisticRegression_L2_balanced",
        "C": float(c_value),
        "positive_budget": int(budget),
        "positive_train_count": int(len(selected_pos_idx)),
        "positive_sample_seed": int(sample_seed),
        "positive_train_first_row": int(selected_pos_idx[0]),
        "positive_train_last_row": int(selected_pos_idx[-1]),
        "policy_name": policy_name,
        "threshold_source": threshold_source,
        "threshold": float(threshold),
        "target_alarm": float(target_alarm),
        "selection_feasible": bool(float(np.mean(score_ood_eval > threshold)) <= float(target_alarm)),
        "id_calib_alarm": float(np.mean(score_id_calib > threshold)),
        "id_eval_alarm": float(np.mean(score_id_eval > threshold)) if len(score_id_eval) else float("nan"),
        "ood_val_alarm": float(np.mean(score_ood_val > threshold)),
        "ood_alarm_ratio_eval": float(np.mean(score_ood_eval > threshold)),
        "attack_detection_val": float(np.mean(score_attack_val > threshold)),
        "attack_detection_high_purity": float(np.mean(score_attack_eval > threshold)),
        "roc_auc_attack_high_vs_ood_val": float(auc_val),
        "roc_auc_attack_high_vs_ood_eval": float(auc_eval),
        "id_calib_alarm_at_selection": float(selection_info.get("id_calib_alarm_at_selection", np.nan)),
        "ood_val_alarm_at_selection": float(selection_info.get("ood_val_alarm_at_selection", np.nan)),
        "threshold_selection_feasible": bool(selection_info.get("selection_feasible", True)),
    }


def summarize_results(results: pd.DataFrame, target_alarm: float) -> pd.DataFrame:
    grouped = (
        results.groupby(["positive_budget", "policy_name"], as_index=False)
        .agg(
            runs=("positive_sample_seed", "nunique"),
            auc_mean=("roc_auc_attack_high_vs_ood_eval", "mean"),
            auc_min=("roc_auc_attack_high_vs_ood_eval", "min"),
            auc_std=("roc_auc_attack_high_vs_ood_eval", "std"),
            eval_alarm_mean=("ood_alarm_ratio_eval", "mean"),
            eval_alarm_max=("ood_alarm_ratio_eval", "max"),
            eval_alarm_std=("ood_alarm_ratio_eval", "std"),
            det_mean=("attack_detection_high_purity", "mean"),
            det_min=("attack_detection_high_purity", "min"),
            det_std=("attack_detection_high_purity", "std"),
            feasible_rate=("selection_feasible", "mean"),
        )
        .sort_values(["positive_budget", "policy_name"])
    )
    grouped["all_runs_strong"] = (
        (grouped["auc_min"] >= 0.95)
        & (grouped["eval_alarm_max"] <= float(target_alarm))
        & (grouped["det_min"] >= 0.80)
    )
    return grouped


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 v7.2 fairness validation for source_rich few-shot ranker.")
    ap.add_argument("--run-tag", default=f"frontend_f2_v7_2_fairness_validation_{today}")
    ap.add_argument(
        "--benign-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_crosscapture_stage1_2026-04-20" / "data",
    )
    ap.add_argument(
        "--attack-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_attack_source_2026-04-20" / "data",
    )
    ap.add_argument(
        "--stage2-manifest",
        type=Path,
        default=WORKTREE_ROOT.parents[1]
        / "KitNET-py-master"
        / "KitNET-py-master"
        / "runs"
        / "frontend100_joint_eval_stage2_2026-04-01"
        / "attack_manifest_stage2.json",
    )
    ap.add_argument("--positive-budgets", default=DEFAULT_POSITIVE_BUDGETS)
    ap.add_argument("--sample-seeds", default=DEFAULT_SAMPLE_SEEDS)
    ap.add_argument("--id-train-rows", type=int, default=8000)
    ap.add_argument("--id-val-rows", type=int, default=2000)
    ap.add_argument("--id-calibration-rows", type=int, default=5000)
    ap.add_argument("--ood-train-rows", type=int, default=8000)
    ap.add_argument("--ood-val-rows", type=int, default=2000)
    ap.add_argument("--attack-train-frac", type=float, default=0.60)
    ap.add_argument("--attack-val-frac", type=float, default=0.20)
    ap.add_argument("--calibration-target", type=float, default=TARGET_ALARM)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--C", type=float, default=1.0)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    id_matrix = v7.load_source_rich(args.benign_data_dir / "id_source_expression_source_rich_v1_matrix.npy")
    ood_matrix = v7.load_source_rich(args.benign_data_dir / "ood_benign_source_expression_source_rich_v1_matrix.npy")
    attack_matrix = v7.load_source_rich(args.attack_data_dir / "attack_source_expression_source_rich_v1_matrix.npy")
    id_x = v7.flatten_source_rich(id_matrix)
    ood_x = v7.flatten_source_rich(ood_matrix)
    attack_x = v7.flatten_source_rich(attack_matrix)

    id_train_end = int(args.id_train_rows)
    id_val_end = id_train_end + int(args.id_val_rows)
    id_calib_end = id_val_end + int(args.id_calibration_rows)
    ood_train_end = int(args.ood_train_rows)
    ood_val_end = ood_train_end + int(args.ood_val_rows)
    if id_calib_end >= len(id_x):
        raise RuntimeError(f"ID split leaves no eval rows: calibration_end={id_calib_end}, rows={len(id_x)}")
    if ood_val_end >= len(ood_x):
        raise RuntimeError(f"OOD split leaves no eval rows: val_end={ood_val_end}, rows={len(ood_x)}")

    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    high_idx = np.asarray(sorted(resc.build_stage2_indices(stage2)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(attack_x))]
    attack_split = v7.split_contiguous(high_idx, args.attack_train_frac, args.attack_val_frac)
    budgets = v71.parse_positive_budgets(args.positive_budgets, len(attack_split["train"]))
    sample_seeds = parse_int_list(args.sample_seeds)

    id_train_x = id_x[:id_train_end]
    ood_train_x = ood_x[:ood_train_end]
    id_calib_x = id_x[id_val_end:id_calib_end]
    id_eval_x = id_x[id_calib_end:]
    ood_val_x = ood_x[ood_train_end:ood_val_end]
    ood_eval_x = ood_x[ood_val_end:]
    attack_val_x = attack_x[attack_split["val"]]
    attack_eval_x = attack_x[attack_split["eval"]]

    results_rows: List[Dict] = []
    importance_frames: List[pd.DataFrame] = []

    for budget in budgets:
        for sample_seed in sample_seeds:
            selected_pos_idx = v71.choose_positive_train_indices(attack_split["train"], budget, sample_seed)
            x_train = np.concatenate([id_train_x, ood_train_x, attack_x[selected_pos_idx]], axis=0)
            y_train = np.concatenate(
                [
                    np.zeros(len(id_train_x), dtype=np.int64),
                    np.zeros(len(ood_train_x), dtype=np.int64),
                    np.ones(len(selected_pos_idx), dtype=np.int64),
                ],
                axis=0,
            )

            scaler = StandardScaler()
            x_train_z = scaler.fit_transform(x_train)
            model = LogisticRegression(
                C=float(args.C),
                penalty="l2",
                solver="liblinear",
                class_weight="balanced",
                max_iter=2000,
                random_state=int(args.seed),
            )
            model.fit(x_train_z, y_train)

            score_id_calib = v7.score_model(model, scaler, id_calib_x)
            score_id_eval = v7.score_model(model, scaler, id_eval_x)
            score_ood_val = v7.score_model(model, scaler, ood_val_x)
            score_ood_eval = v7.score_model(model, scaler, ood_eval_x)
            score_attack_val = v7.score_model(model, scaler, attack_val_x)
            score_attack_eval = v7.score_model(model, scaler, attack_eval_x)

            auc_eval = float(
                roc_auc_score(
                    np.concatenate(
                        [
                            np.zeros(len(score_ood_eval), dtype=np.int64),
                            np.ones(len(score_attack_eval), dtype=np.int64),
                        ]
                    ),
                    np.concatenate([score_ood_eval, score_attack_eval]),
                )
            )
            auc_val = float(
                roc_auc_score(
                    np.concatenate(
                        [
                            np.zeros(len(score_ood_val), dtype=np.int64),
                            np.ones(len(score_attack_val), dtype=np.int64),
                        ]
                    ),
                    np.concatenate([score_ood_val, score_attack_val]),
                )
            )

            id_q99 = float(np.quantile(score_id_calib, 0.99))
            results_rows.append(
                metric_row(
                    policy_name="fixed_id_calib_q99",
                    threshold=id_q99,
                    score_id_calib=score_id_calib,
                    score_id_eval=score_id_eval,
                    score_ood_val=score_ood_val,
                    score_ood_eval=score_ood_eval,
                    score_attack_val=score_attack_val,
                    score_attack_eval=score_attack_eval,
                    auc_eval=auc_eval,
                    auc_val=auc_val,
                    budget=budget,
                    sample_seed=sample_seed,
                    selected_pos_idx=selected_pos_idx,
                    c_value=float(args.C),
                    target_alarm=float(args.calibration_target),
                    threshold_source="ID calibration q99 only; final OOD eval not used",
                )
            )

            guarded = guarded_val_threshold(score_id_calib, score_ood_val, float(args.calibration_target))
            results_rows.append(
                metric_row(
                    policy_name="guarded_id_calib_and_ood_val_target1pct",
                    threshold=float(guarded["threshold"]),
                    score_id_calib=score_id_calib,
                    score_id_eval=score_id_eval,
                    score_ood_val=score_ood_val,
                    score_ood_eval=score_ood_eval,
                    score_attack_val=score_attack_val,
                    score_attack_eval=score_attack_eval,
                    auc_eval=auc_eval,
                    auc_val=auc_val,
                    budget=budget,
                    sample_seed=sample_seed,
                    selected_pos_idx=selected_pos_idx,
                    c_value=float(args.C),
                    target_alarm=float(args.calibration_target),
                    threshold_source="ID calibration + OOD validation guard; final OOD eval not used",
                    selection_info=guarded,
                )
            )

            importance = v7.build_feature_importance(model.coef_.reshape(-1))
            importance.insert(0, "positive_sample_seed", int(sample_seed))
            importance.insert(0, "positive_budget", int(budget))
            importance_frames.append(importance)

            fixed_row = results_rows[-2]
            guarded_row = results_rows[-1]
            print(
                f"[budget={budget} seed={sample_seed}] auc={auc_eval:.4f} "
                f"id_q99_alarm={fixed_row['ood_alarm_ratio_eval']:.4f} id_q99_det={fixed_row['attack_detection_high_purity']:.4f} "
                f"guard_alarm={guarded_row['ood_alarm_ratio_eval']:.4f} guard_det={guarded_row['attack_detection_high_purity']:.4f}",
                flush=True,
            )

    results = pd.DataFrame(results_rows)
    summary = summarize_results(results, float(args.calibration_target))
    feature_importance = pd.concat(importance_frames, ignore_index=True)
    top_features = (
        feature_importance.groupby(["positive_budget", "positive_sample_seed"], as_index=False)
        .head(10)
        .loc[:, ["positive_budget", "positive_sample_seed", "family", "scale", "channel", "coef", "abs_coef"]]
    )

    results.to_csv(out / "frontend_f2_v7_2_fairness_results.csv", index=False)
    results.to_csv(out / "results.csv", index=False)
    summary.to_csv(out / "frontend_f2_v7_2_fairness_summary.csv", index=False)
    feature_importance.to_csv(out / "frontend_f2_v7_2_fairness_feature_importance.csv", index=False)
    top_features.to_csv(out / "frontend_f2_v7_2_fairness_top_features.csv", index=False)

    anchor_df = v7.load_anchor_rows()
    if len(anchor_df):
        anchor_df.to_csv(out / "frontend_f2_v7_2_anchor_comparison.csv", index=False)

    split_info = split_info_dict(
        id_train_end=id_train_end,
        id_val_end=id_val_end,
        id_calib_end=id_calib_end,
        id_rows=len(id_x),
        ood_train_end=ood_train_end,
        ood_val_end=ood_val_end,
        ood_rows=len(ood_x),
        high_idx=high_idx,
        attack_split=attack_split,
    )
    strong = summary[summary["all_runs_strong"]]
    min_strong_budget = int(strong["positive_budget"].min()) if len(strong) else None
    config = {
        "stage": "frontend_f2_v7_2_fairness_validation",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": int(args.seed),
        "positive_budgets": budgets,
        "positive_sample_seeds": sample_seeds,
        "threshold_policies": [
            "fixed_id_calib_q99",
            "guarded_id_calib_and_ood_val_target1pct",
        ],
        "final_ood_eval_threshold_leakage": False,
        "benign_data_dir": str(args.benign_data_dir),
        "attack_data_dir": str(args.attack_data_dir),
        "stage2_manifest": str(args.stage2_manifest),
        "split_info": split_info,
        "model": {
            "type": "LogisticRegression",
            "penalty": "l2",
            "solver": "liblinear",
            "class_weight": "balanced",
            "C": float(args.C),
        },
        "min_budget_all_sample_seeds_strong": min_strong_budget,
        "outputs": {
            "results": str(out / "frontend_f2_v7_2_fairness_results.csv"),
            "summary": str(out / "frontend_f2_v7_2_fairness_summary.csv"),
            "feature_importance": str(out / "frontend_f2_v7_2_fairness_feature_importance.csv"),
            "top_features": str(out / "frontend_f2_v7_2_fairness_top_features.csv"),
            "summary_md": str(out / "summary.md"),
        },
    }
    (out / "frontend_f2_v7_2_fairness_metadata.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    strong_line = (
        f"- Minimum budget where all sample seeds meet AUC>=0.95, final OOD alarm<=1%, det>=0.80: `{min_strong_budget}`."
        if min_strong_budget is not None
        else "- No budget met the all-seed strong criterion."
    )
    anchor_md = tv3.md_table(anchor_df) if len(anchor_df) else "(anchor files not found)"
    summary_md = tv3.md_table(summary)
    top_md = tv3.md_table(top_features.groupby("positive_budget", as_index=False).head(12))
    note = "\n".join(
        [
            "# Frontend-F2 v7.2 Fairness Validation",
            "",
            "- Input: frozen `source_rich_v1 [20,13]`, flattened to 260 dimensions.",
            "- Model: L2 LogisticRegression with balanced class weights.",
            "- Negative labels: ID benign train + OOD benign train.",
            "- Positive labels: high-purity attack train split only.",
            "- Final OOD eval is never used for threshold selection.",
            "- Threshold policies:",
            "  - `fixed_id_calib_q99`: threshold from ID calibration q99 only.",
            "  - `guarded_id_calib_and_ood_val_target1pct`: threshold selected using ID calibration + OOD validation only.",
            f"- Positive budgets: `{budgets}`.",
            f"- Positive sample seeds: `{sample_seeds}`.",
            strong_line,
            "",
            "## Aggregate Results",
            summary_md,
            "",
            "## Anchor Comparison",
            anchor_md,
            "",
            "## Top Features Snapshot",
            top_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(note, encoding="utf-8")

    print(f"[done] frontend-f2 v7.2 fairness output: {out}", flush=True)
    print(
        f"[summary] min_budget_all_seeds_strong={min_strong_budget} "
        f"budgets={budgets} sample_seeds={sample_seeds}",
        flush=True,
    )


if __name__ == "__main__":
    main()
