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


ID_CALIB_POLICY = "id_budget_calibrated_target1pct"
DEFAULT_POSITIVE_BUDGETS = "16,32,64,128,256,512,1024,2048,all"


def parse_positive_budgets(spec: str, max_count: int) -> List[int]:
    budgets: List[int] = []
    for raw in spec.split(","):
        token = raw.strip().lower()
        if not token:
            continue
        if token == "all":
            budget = int(max_count)
        else:
            budget = int(token)
            if budget <= 0:
                raise ValueError(f"positive budget must be > 0, got {budget}")
            budget = min(budget, int(max_count))
        if budget not in budgets:
            budgets.append(budget)
    if not budgets:
        raise ValueError("No positive budgets were parsed.")
    return budgets


def make_combined_summary(df: pd.DataFrame, calib_policy: str) -> pd.DataFrame:
    key = [
        "positive_budget",
        "positive_train_count",
        "object_label",
        "detector_family",
        "token_profile",
        "score_label",
    ]
    fixed = df[df["policy_name"].eq("fixed_id_q99")].copy()
    calib = df[df["policy_name"].eq(calib_policy)].copy()
    fixed = fixed[
        key + ["ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]
    ].rename(columns={"ood_alarm_ratio_eval": "fixed_alarm", "attack_detection_high_purity": "fixed_det"})
    calib = calib[key + ["ood_alarm_ratio_eval", "attack_detection_high_purity", "selection_feasible"]].rename(
        columns={"ood_alarm_ratio_eval": "calibrated_alarm", "attack_detection_high_purity": "calibrated_det"}
    )
    combined = fixed.merge(calib, on=key, how="left")
    order = key + [
        "fixed_alarm",
        "fixed_det",
        "calibrated_alarm",
        "calibrated_det",
        "selection_feasible",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    return combined[[c for c in order if c in combined.columns]].sort_values("positive_budget")


def choose_positive_train_indices(train_idx: np.ndarray, budget: int, seed: int) -> np.ndarray:
    train_idx = np.asarray(train_idx, dtype=np.int64)
    if budget >= len(train_idx):
        return train_idx.copy()
    rng = np.random.default_rng(seed + int(budget) * 1009)
    chosen = rng.choice(train_idx, size=int(budget), replace=False)
    return np.asarray(sorted(chosen), dtype=np.int64)


def add_score_rows(
    rows: List[Dict],
    score_id_calib: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_eval: np.ndarray,
    fixed_threshold: float,
    calib_result: dict,
    auc: float,
    val_auc: float,
    seed: int,
    c_value: float,
    budget: int,
    selected_pos_idx: np.ndarray,
) -> None:
    object_label = "v7_1_source_rich_label_budget_logistic"
    detector_family = "frontend_f2_v7_1_source_rich_label_budget_ranker"
    score_label = "logistic_decision_function"
    extra = {
        "token_profile": "flat_source_rich_260",
        "source_mode": "source_rich_v1_frozen",
        "input_tensor": "source_rich_v1[20x13]_flat260",
        "model": "LogisticRegression_L2_balanced",
        "C": float(c_value),
        "positive_budget": int(budget),
        "positive_train_count": int(len(selected_pos_idx)),
        "positive_budget_mode": "seeded_without_replacement_from_attack_train_split",
        "positive_train_first_row": int(selected_pos_idx[0]),
        "positive_train_last_row": int(selected_pos_idx[-1]),
        "validation_auc_threeway": float(val_auc),
    }
    v7.add_score_rows(
        rows=rows,
        object_label=object_label,
        detector_family=detector_family,
        score_label=score_label,
        score_id_calib=score_id_calib,
        score_ood_eval=score_ood_eval,
        score_attack_eval=score_attack_eval,
        fixed_threshold=fixed_threshold,
        calib_result=calib_result,
        auc=auc,
        seed=seed,
        extra=extra,
    )


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(
        description="Frontend-F2 v7.1 label-budget sweep for frozen source_rich_v1 diagnostic ranker."
    )
    ap.add_argument("--run-tag", default=f"frontend_f2_v7_1_source_rich_label_budget_{today}")
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
    ap.add_argument("--id-train-rows", type=int, default=8000)
    ap.add_argument("--id-val-rows", type=int, default=2000)
    ap.add_argument("--id-calibration-rows", type=int, default=5000)
    ap.add_argument("--ood-train-rows", type=int, default=8000)
    ap.add_argument("--ood-val-rows", type=int, default=2000)
    ap.add_argument("--attack-train-frac", type=float, default=0.60)
    ap.add_argument("--attack-val-frac", type=float, default=0.20)
    ap.add_argument("--calibration-target", type=float, default=0.01)
    ap.add_argument("--calibration-budget", type=int, default=5000)
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
    if id_calib_end > len(id_x):
        raise RuntimeError(f"ID split exceeds rows: need {id_calib_end}, have {len(id_x)}")
    if ood_val_end >= len(ood_x):
        raise RuntimeError(f"OOD split leaves no eval rows: val_end={ood_val_end}, rows={len(ood_x)}")

    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    high_idx = np.asarray(sorted(resc.build_stage2_indices(stage2)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(attack_x))]
    attack_split = v7.split_contiguous(high_idx, args.attack_train_frac, args.attack_val_frac)
    budgets = parse_positive_budgets(args.positive_budgets, len(attack_split["train"]))

    id_train_x = id_x[:id_train_end]
    ood_train_x = ood_x[:ood_train_end]
    id_val_x = id_x[id_train_end:id_val_end]
    ood_val_x = ood_x[ood_train_end:ood_val_end]
    id_calib_idx = np.arange(id_val_end, id_calib_end, dtype=np.int64)
    ood_eval_idx = np.arange(ood_val_end, len(ood_x), dtype=np.int64)
    attack_eval_idx = attack_split["eval"]

    results_rows: List[Dict] = []
    row_score_frames: List[pd.DataFrame] = []
    importance_frames: List[pd.DataFrame] = []

    for budget in budgets:
        selected_pos_idx = choose_positive_train_indices(attack_split["train"], budget, int(args.seed))
        x_train = np.concatenate([id_train_x, ood_train_x, attack_x[selected_pos_idx]], axis=0)
        y_train = np.concatenate(
            [
                np.zeros(len(id_train_x), dtype=np.int64),
                np.zeros(len(ood_train_x), dtype=np.int64),
                np.ones(len(selected_pos_idx), dtype=np.int64),
            ],
            axis=0,
        )
        x_val = np.concatenate([id_val_x, ood_val_x, attack_x[attack_split["val"]]], axis=0)
        y_val = np.concatenate(
            [
                np.zeros(len(id_val_x), dtype=np.int64),
                np.zeros(len(ood_val_x), dtype=np.int64),
                np.ones(len(attack_split["val"]), dtype=np.int64),
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

        score_id_calib = v7.score_model(model, scaler, id_x[id_calib_idx])
        score_ood_eval = v7.score_model(model, scaler, ood_x[ood_eval_idx])
        score_attack_eval = v7.score_model(model, scaler, attack_x[attack_eval_idx])
        score_val = v7.score_model(model, scaler, x_val)
        auc = float(
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
        val_auc = float(roc_auc_score(y_val, score_val)) if len(np.unique(y_val)) == 2 else float("nan")
        fixed_threshold = float(np.quantile(score_id_calib, 0.99))
        calib_result = v7.id_budget_calibrate(
            score_id_eval=score_id_calib,
            score_ood_eval=score_ood_eval,
            score_attack_high=score_attack_eval,
            budget=int(args.calibration_budget),
            target_alarm=float(args.calibration_target),
            seed=int(args.seed),
        )
        add_score_rows(
            rows=results_rows,
            score_id_calib=score_id_calib,
            score_ood_eval=score_ood_eval,
            score_attack_eval=score_attack_eval,
            fixed_threshold=fixed_threshold,
            calib_result=calib_result,
            auc=auc,
            val_auc=val_auc,
            seed=int(args.seed),
            c_value=float(args.C),
            budget=int(budget),
            selected_pos_idx=selected_pos_idx,
        )

        row_scores = v7.build_row_scores(
            score_id_calib=score_id_calib,
            score_ood_eval=score_ood_eval,
            score_attack_eval=score_attack_eval,
            id_calib_idx=id_calib_idx,
            ood_eval_idx=ood_eval_idx,
            attack_eval_idx=attack_eval_idx,
        )
        row_scores.insert(0, "positive_budget", int(budget))
        row_score_frames.append(row_scores)

        importance = v7.build_feature_importance(model.coef_.reshape(-1))
        importance.insert(0, "positive_budget", int(budget))
        importance_frames.append(importance)

        print(
            f"[budget={budget}] auc={auc:.4f} alarm={calib_result['calibrated_ood_alarm']:.4f} "
            f"det={calib_result['calibrated_det']:.4f} feasible={calib_result['feasible']}",
            flush=True,
        )

    results = pd.DataFrame(results_rows)
    combined = make_combined_summary(results, ID_CALIB_POLICY)
    feature_importance = pd.concat(importance_frames, ignore_index=True)
    row_scores = pd.concat(row_score_frames, ignore_index=True)

    results.to_csv(out / "frontend_f2_v7_1_label_budget_results.csv", index=False)
    results.to_csv(out / "results.csv", index=False)
    combined.to_csv(out / "frontend_f2_v7_1_label_budget_combined.csv", index=False)
    combined.to_csv(out / "frontend_f2_v7_1_label_budget_summary.csv", index=False)
    feature_importance.to_csv(out / "frontend_f2_v7_1_label_budget_feature_importance.csv", index=False)
    row_scores.to_csv(out / "frontend_f2_v7_1_label_budget_row_scores.csv", index=False)

    anchor_df = v7.load_anchor_rows()
    if len(anchor_df):
        anchor_df.to_csv(out / "frontend_f2_v7_1_anchor_comparison.csv", index=False)

    best = combined.sort_values(
        ["selection_feasible", "calibrated_det", "roc_auc_attack_high_vs_ood_eval"],
        ascending=[False, False, False],
    ).iloc[0]
    min_strong = combined[
        (combined["roc_auc_attack_high_vs_ood_eval"] >= 0.95)
        & (combined["calibrated_alarm"] <= float(args.calibration_target))
        & (combined["calibrated_det"] >= 0.80)
    ]
    min_strong_budget = int(min_strong["positive_budget"].min()) if len(min_strong) else None

    split_info = {
        "id": {
            "train": [0, id_train_end],
            "val": [id_train_end, id_val_end],
            "calibration": [id_val_end, id_calib_end],
        },
        "ood": {
            "train": [0, ood_train_end],
            "val": [ood_train_end, ood_val_end],
            "eval": [ood_val_end, len(ood_x)],
        },
        "attack_high": {
            "total_high": int(len(high_idx)),
            "train_count": int(len(attack_split["train"])),
            "val_count": int(len(attack_split["val"])),
            "eval_count": int(len(attack_split["eval"])),
            "train_first_last": [int(attack_split["train"][0]), int(attack_split["train"][-1])],
            "val_first_last": [int(attack_split["val"][0]), int(attack_split["val"][-1])],
            "eval_first_last": [int(attack_split["eval"][0]), int(attack_split["eval"][-1])],
        },
    }
    config = {
        "stage": "frontend_f2_v7_1_source_rich_label_budget_ranker",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": int(args.seed),
        "benign_data_dir": str(args.benign_data_dir),
        "attack_data_dir": str(args.attack_data_dir),
        "stage2_manifest": str(args.stage2_manifest),
        "positive_budgets": budgets,
        "positive_budget_mode": "seeded_without_replacement_from_attack_train_split",
        "model": {
            "type": "LogisticRegression",
            "penalty": "l2",
            "solver": "liblinear",
            "class_weight": "balanced",
            "C": float(args.C),
        },
        "split_info": split_info,
        "best_budget": {
            "positive_budget": int(best["positive_budget"]),
            "auc": float(best["roc_auc_attack_high_vs_ood_eval"]),
            "calibrated_alarm": float(best["calibrated_alarm"]),
            "calibrated_det": float(best["calibrated_det"]),
            "selection_feasible": bool(best["selection_feasible"]),
        },
        "min_budget_meeting_auc95_alarm1pct_det80pct": min_strong_budget,
        "outputs": {
            "results": str(out / "frontend_f2_v7_1_label_budget_results.csv"),
            "combined": str(out / "frontend_f2_v7_1_label_budget_combined.csv"),
            "row_scores": str(out / "frontend_f2_v7_1_label_budget_row_scores.csv"),
            "feature_importance": str(out / "frontend_f2_v7_1_label_budget_feature_importance.csv"),
            "summary": str(out / "summary.md"),
        },
    }
    (out / "frontend_f2_v7_1_label_budget_metadata.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    anchor_md = tv3.md_table(anchor_df) if len(anchor_df) else "(anchor files not found)"
    combined_md = tv3.md_table(combined)
    top_by_budget = (
        feature_importance.groupby("positive_budget", as_index=False)
        .head(10)
        .loc[:, ["positive_budget", "family", "scale", "channel", "coef", "abs_coef"]]
    )
    top_features_md = tv3.md_table(top_by_budget)
    min_budget_line = (
        f"- Minimum budget meeting AUC>=0.95, alarm<={args.calibration_target:.2f}, det>=0.80: `{min_strong_budget}`."
        if min_strong_budget is not None
        else "- No budget met AUC>=0.95, alarm<=target, det>=0.80."
    )
    summary = "\n".join(
        [
            "# Frontend-F2 v7.1 Source-Rich Label-Budget Ranker",
            "",
            "- Input: frozen `source_rich_v1 [20,13]`, flattened to 260 dimensions.",
            "- Model: L2 LogisticRegression with balanced class weights.",
            "- Negative labels: ID benign + OOD benign train splits.",
            "- Positive labels: seeded subsets of stage2 high-purity attack train split.",
            "- Eval is unchanged across budgets: OOD eval split vs held-out high-purity attack eval split.",
            f"- Calibration: ID-calibration budget={args.calibration_budget}, target OOD alarm <= {args.calibration_target:.2f}.",
            min_budget_line,
            "",
            "## Label-Budget Results",
            combined_md,
            "",
            "## Anchor Comparison",
            anchor_md,
            "",
            "## Top Coefficients By Budget",
            top_features_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")

    print(f"[done] frontend-f2 v7.1 label-budget output: {out}", flush=True)
    print(
        f"[best] budget={int(best['positive_budget'])} auc={float(best['roc_auc_attack_high_vs_ood_eval']):.4f} "
        f"alarm={float(best['calibrated_alarm']):.4f} det={float(best['calibrated_det']):.4f} "
        f"feasible={bool(best['selection_feasible'])}",
        flush=True,
    )


if __name__ == "__main__":
    main()
