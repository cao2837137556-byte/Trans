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
for p in [REPO_DIR, THIS_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import KitNET as kit
import frontend100_negative_recipe_rescoring as resc
import frontend100_timescale_tokenizer_v1_3 as tv3
import frontend_f2_v7_1_source_rich_label_budget_ranker as v71
import frontend_f2_v7_2_fairness_validation as v72


DEFAULT_POSITIVE_BUDGETS = "16,32,64"
DEFAULT_SAMPLE_SEEDS = "42,43,44,45,46"
TARGET_ALARM = 0.01


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected 2D matrix, got {arr.shape} from {path}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def score_kitnet_checkpoint(checkpoint: Path, x: np.ndarray, label: str, progress_every: int = 10000) -> np.ndarray:
    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(x), dtype=np.float64)
    for i, row in enumerate(x):
        scores[i] = float(model.executeAD(row.astype(np.float64)))
        if progress_every > 0 and (i + 1) % progress_every == 0:
            print(f"[score] {label}: {i + 1}/{len(x)}", flush=True)
    return scores


def maybe_load_or_score_da(
    out: Path,
    checkpoint: Path,
    id_x: np.ndarray,
    ood_x: np.ndarray,
    attack_x: np.ndarray,
    stage1_attack_scores: Path | None,
) -> Dict[str, np.ndarray]:
    cache_dir = out / "score_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    id_cache = cache_dir / "da_full_id_scores.npy"
    ood_cache = cache_dir / "da_ood_scores.npy"
    attack_cache = cache_dir / "da_attack_scores.npy"

    if id_cache.exists():
        id_scores = np.load(id_cache).astype(np.float64)
    else:
        print("[score] computing DA full ID scores from checkpoint", flush=True)
        id_scores = score_kitnet_checkpoint(checkpoint, id_x, "da id")
        np.save(id_cache, id_scores)

    if ood_cache.exists():
        ood_scores = np.load(ood_cache).astype(np.float64)
    else:
        print("[score] computing DA OOD scores from checkpoint", flush=True)
        ood_scores = score_kitnet_checkpoint(checkpoint, ood_x, "da ood")
        np.save(ood_cache, ood_scores)

    if attack_cache.exists():
        attack_scores = np.load(attack_cache).astype(np.float64)
    elif stage1_attack_scores is not None and stage1_attack_scores.exists():
        attack_scores = np.load(stage1_attack_scores).astype(np.float64)
        np.save(attack_cache, attack_scores)
    else:
        print("[score] computing DA attack scores from checkpoint", flush=True)
        attack_scores = score_kitnet_checkpoint(checkpoint, attack_x, "da attack")
        np.save(attack_cache, attack_scores)

    return {"id": id_scores, "ood": ood_scores, "attack": attack_scores}


def make_metric_row(
    model_label: str,
    training_mode: str,
    input_mode: str,
    uses_attack_labels: bool,
    positive_budget: int | None,
    positive_sample_seed: int | None,
    policy_name: str,
    threshold: float,
    threshold_source: str,
    score_id_calib: np.ndarray,
    score_id_eval: np.ndarray,
    score_ood_val: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_val: np.ndarray,
    score_attack_eval: np.ndarray,
    target_alarm: float,
    threshold_selection_info: Dict | None = None,
) -> Dict:
    threshold_selection_info = threshold_selection_info or {}
    auc_eval = float(
        roc_auc_score(
            np.concatenate([np.zeros(len(score_ood_eval), dtype=np.int64), np.ones(len(score_attack_eval), dtype=np.int64)]),
            np.concatenate([score_ood_eval, score_attack_eval]),
        )
    )
    auc_val = float(
        roc_auc_score(
            np.concatenate([np.zeros(len(score_ood_val), dtype=np.int64), np.ones(len(score_attack_val), dtype=np.int64)]),
            np.concatenate([score_ood_val, score_attack_val]),
        )
    )
    final_alarm = float(np.mean(score_ood_eval > threshold))
    return {
        "model_label": model_label,
        "training_mode": training_mode,
        "input_mode": input_mode,
        "uses_attack_labels": bool(uses_attack_labels),
        "positive_budget": -1 if positive_budget is None else int(positive_budget),
        "positive_sample_seed": -1 if positive_sample_seed is None else int(positive_sample_seed),
        "policy_name": policy_name,
        "threshold_source": threshold_source,
        "threshold": float(threshold),
        "target_alarm": float(target_alarm),
        "selection_feasible": bool(final_alarm <= float(target_alarm)),
        "id_calib_alarm": float(np.mean(score_id_calib > threshold)),
        "id_eval_alarm": float(np.mean(score_id_eval > threshold)) if len(score_id_eval) else float("nan"),
        "ood_val_alarm": float(np.mean(score_ood_val > threshold)),
        "ood_alarm_ratio_eval": final_alarm,
        "attack_detection_val": float(np.mean(score_attack_val > threshold)),
        "attack_detection_high_purity": float(np.mean(score_attack_eval > threshold)),
        "roc_auc_attack_high_vs_ood_val": auc_val,
        "roc_auc_attack_high_vs_ood_eval": auc_eval,
        "id_calib_alarm_at_selection": float(threshold_selection_info.get("id_calib_alarm_at_selection", np.nan)),
        "ood_val_alarm_at_selection": float(threshold_selection_info.get("ood_val_alarm_at_selection", np.nan)),
        "threshold_selection_feasible": bool(threshold_selection_info.get("selection_feasible", True)),
    }


def add_threshold_policy_rows(
    rows: List[Dict],
    model_label: str,
    training_mode: str,
    input_mode: str,
    uses_attack_labels: bool,
    positive_budget: int | None,
    positive_sample_seed: int | None,
    score_id_calib: np.ndarray,
    score_id_eval: np.ndarray,
    score_ood_val: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_val: np.ndarray,
    score_attack_eval: np.ndarray,
    target_alarm: float,
) -> None:
    id_q99 = float(np.quantile(score_id_calib, 0.99))
    rows.append(
        make_metric_row(
            model_label=model_label,
            training_mode=training_mode,
            input_mode=input_mode,
            uses_attack_labels=uses_attack_labels,
            positive_budget=positive_budget,
            positive_sample_seed=positive_sample_seed,
            policy_name="fixed_id_calib_q99",
            threshold=id_q99,
            threshold_source="ID calibration q99 only; final OOD eval not used",
            score_id_calib=score_id_calib,
            score_id_eval=score_id_eval,
            score_ood_val=score_ood_val,
            score_ood_eval=score_ood_eval,
            score_attack_val=score_attack_val,
            score_attack_eval=score_attack_eval,
            target_alarm=target_alarm,
        )
    )

    guarded = v72.guarded_val_threshold(score_id_calib, score_ood_val, target_alarm)
    rows.append(
        make_metric_row(
            model_label=model_label,
            training_mode=training_mode,
            input_mode=input_mode,
            uses_attack_labels=uses_attack_labels,
            positive_budget=positive_budget,
            positive_sample_seed=positive_sample_seed,
            policy_name="guarded_id_calib_and_ood_val_target1pct",
            threshold=float(guarded["threshold"]),
            threshold_source="ID calibration + OOD validation guard; final OOD eval not used",
            score_id_calib=score_id_calib,
            score_id_eval=score_id_eval,
            score_ood_val=score_ood_val,
            score_ood_eval=score_ood_eval,
            score_attack_val=score_attack_val,
            score_attack_eval=score_attack_eval,
            target_alarm=target_alarm,
            threshold_selection_info=guarded,
        )
    )


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    return (
        results.groupby(
            [
                "model_label",
                "training_mode",
                "input_mode",
                "uses_attack_labels",
                "positive_budget",
                "policy_name",
            ],
            as_index=False,
        )
        .agg(
            runs=("positive_sample_seed", "nunique"),
            auc_mean=("roc_auc_attack_high_vs_ood_eval", "mean"),
            auc_min=("roc_auc_attack_high_vs_ood_eval", "min"),
            eval_alarm_mean=("ood_alarm_ratio_eval", "mean"),
            eval_alarm_max=("ood_alarm_ratio_eval", "max"),
            det_mean=("attack_detection_high_purity", "mean"),
            det_min=("attack_detection_high_purity", "min"),
            feasible_rate=("selection_feasible", "mean"),
        )
        .sort_values(["model_label", "positive_budget", "policy_name"])
    )


def load_v72_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    out = pd.DataFrame(
        {
            "model_label": "source_rich_v7_2_fewshot_logistic",
            "training_mode": "fewshot_target_aligned_high_purity_attack",
            "input_mode": "source_rich_v1_flat260",
            "uses_attack_labels": True,
            "positive_budget": df["positive_budget"].astype(int),
            "positive_sample_seed": df["positive_sample_seed"].astype(int),
            "policy_name": df["policy_name"],
            "threshold_source": df["threshold_source"],
            "threshold": df["threshold"],
            "target_alarm": df["target_alarm"],
            "selection_feasible": df["selection_feasible"],
            "id_calib_alarm": df["id_calib_alarm"],
            "id_eval_alarm": df["id_eval_alarm"],
            "ood_val_alarm": df["ood_val_alarm"],
            "ood_alarm_ratio_eval": df["ood_alarm_ratio_eval"],
            "attack_detection_val": df["attack_detection_val"],
            "attack_detection_high_purity": df["attack_detection_high_purity"],
            "roc_auc_attack_high_vs_ood_val": df["roc_auc_attack_high_vs_ood_val"],
            "roc_auc_attack_high_vs_ood_eval": df["roc_auc_attack_high_vs_ood_eval"],
            "id_calib_alarm_at_selection": df["id_calib_alarm_at_selection"],
            "ood_val_alarm_at_selection": df["ood_val_alarm_at_selection"],
            "threshold_selection_feasible": df["threshold_selection_feasible"],
        }
    )
    return out


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 v7.3 DA and original100 fairness comparison.")
    ap.add_argument("--run-tag", default=f"frontend_f2_v7_3_da_fairness_comparison_{today}")
    ap.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    ap.add_argument(
        "--v72-results",
        type=Path,
        default=WORKTREE_ROOT
        / "runs"
        / "frontend_f2_v7_2_fairness_validation_2026-04-22"
        / "frontend_f2_v7_2_fairness_results.csv",
    )
    ap.add_argument("--positive-budgets", default=DEFAULT_POSITIVE_BUDGETS)
    ap.add_argument("--sample-seeds", default=DEFAULT_SAMPLE_SEEDS)
    ap.add_argument("--calibration-target", type=float, default=TARGET_ALARM)
    ap.add_argument("--C", type=float, default=1.0)
    ap.add_argument("--id-train-rows", type=int, default=8000)
    ap.add_argument("--id-val-rows", type=int, default=2000)
    ap.add_argument("--id-calibration-rows", type=int, default=5000)
    ap.add_argument("--ood-train-rows", type=int, default=8000)
    ap.add_argument("--ood-val-rows", type=int, default=2000)
    ap.add_argument("--attack-train-frac", type=float, default=0.60)
    ap.add_argument("--attack-val-frac", type=float, default=0.20)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source = args.source_root
    cross_data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1 = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2 = source / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    da_checkpoint = source / "runs" / "frontend100_tailreg_stage1_2026-03-27" / "da_seed42" / "kitnet_da_seed42.ckpt"

    id_x = load_matrix(cross_data / "id_source_100.npy")
    ood_x = load_matrix(cross_data / "ood_benign_source_100.npy")
    attack_x = load_matrix(stage1 / "data" / "attack_source_100.csv")
    manifest = load_json(stage2 / "attack_manifest_stage2.json")
    high_idx = np.asarray(sorted(resc.build_stage2_indices(manifest)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(attack_x))]
    attack_split = v72.v7.split_contiguous(high_idx, args.attack_train_frac, args.attack_val_frac)

    budgets = v71.parse_positive_budgets(args.positive_budgets, len(attack_split["train"]))
    sample_seeds = v72.parse_int_list(args.sample_seeds)

    id_train_end = int(args.id_train_rows)
    id_val_end = id_train_end + int(args.id_val_rows)
    id_calib_end = id_val_end + int(args.id_calibration_rows)
    ood_train_end = int(args.ood_train_rows)
    ood_val_end = ood_train_end + int(args.ood_val_rows)
    if id_calib_end >= len(id_x):
        raise RuntimeError(f"ID split leaves no eval rows: {id_calib_end=} rows={len(id_x)}")
    if ood_val_end >= len(ood_x):
        raise RuntimeError(f"OOD split leaves no eval rows: {ood_val_end=} rows={len(ood_x)}")

    rows: List[Dict] = []

    if args.v72_results.exists():
        rows.extend(load_v72_results(args.v72_results).to_dict("records"))

    id_train_x = id_x[:id_train_end]
    ood_train_x = ood_x[:ood_train_end]
    id_calib_x = id_x[id_val_end:id_calib_end]
    id_eval_x = id_x[id_calib_end:]
    ood_val_x = ood_x[ood_train_end:ood_val_end]
    ood_eval_x = ood_x[ood_val_end:]
    attack_val_x = attack_x[attack_split["val"]]
    attack_eval_x = attack_x[attack_split["eval"]]

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
                random_state=42,
            )
            model.fit(x_train_z, y_train)
            add_threshold_policy_rows(
                rows=rows,
                model_label="original100_fewshot_logistic",
                training_mode="fewshot_target_aligned_high_purity_attack",
                input_mode="original_frontend_flat100",
                uses_attack_labels=True,
                positive_budget=budget,
                positive_sample_seed=sample_seed,
                score_id_calib=model.decision_function(scaler.transform(id_calib_x)).astype(np.float64),
                score_id_eval=model.decision_function(scaler.transform(id_eval_x)).astype(np.float64),
                score_ood_val=model.decision_function(scaler.transform(ood_val_x)).astype(np.float64),
                score_ood_eval=model.decision_function(scaler.transform(ood_eval_x)).astype(np.float64),
                score_attack_val=model.decision_function(scaler.transform(attack_val_x)).astype(np.float64),
                score_attack_eval=model.decision_function(scaler.transform(attack_eval_x)).astype(np.float64),
                target_alarm=float(args.calibration_target),
            )
            print(f"[original100] budget={budget} seed={sample_seed} done", flush=True)

    da_scores = maybe_load_or_score_da(
        out=out,
        checkpoint=da_checkpoint,
        id_x=id_x,
        ood_x=ood_x,
        attack_x=attack_x,
        stage1_attack_scores=stage1 / "da_attack_scores.npy",
    )
    add_threshold_policy_rows(
        rows=rows,
        model_label="da_unsupervised_score_seed42",
        training_mode="unsupervised_id_only_original_KitNET_dA",
        input_mode="original_frontend_flat100",
        uses_attack_labels=False,
        positive_budget=None,
        positive_sample_seed=None,
        score_id_calib=da_scores["id"][id_val_end:id_calib_end],
        score_id_eval=da_scores["id"][id_calib_end:],
        score_ood_val=da_scores["ood"][ood_train_end:ood_val_end],
        score_ood_eval=da_scores["ood"][ood_val_end:],
        score_attack_val=da_scores["attack"][attack_split["val"]],
        score_attack_eval=da_scores["attack"][attack_split["eval"]],
        target_alarm=float(args.calibration_target),
    )

    results = pd.DataFrame(rows)
    summary = summarize(results)
    results.to_csv(out / "frontend_f2_v7_3_da_fairness_comparison_results.csv", index=False)
    results.to_csv(out / "results.csv", index=False)
    summary.to_csv(out / "frontend_f2_v7_3_da_fairness_comparison_summary.csv", index=False)

    comparison_focus = summary[
        (
            summary["policy_name"].eq("fixed_id_calib_q99")
            & (
                summary["model_label"].eq("da_unsupervised_score_seed42")
                | (
                    summary["model_label"].isin(
                        ["source_rich_v7_2_fewshot_logistic", "original100_fewshot_logistic"]
                    )
                    & summary["positive_budget"].eq(16)
                )
            )
        )
        | (
            summary["policy_name"].eq("guarded_id_calib_and_ood_val_target1pct")
            & (
                summary["model_label"].eq("da_unsupervised_score_seed42")
                | (
                    summary["model_label"].isin(
                        ["source_rich_v7_2_fewshot_logistic", "original100_fewshot_logistic"]
                    )
                    & summary["positive_budget"].eq(16)
                )
            )
        )
    ].copy()
    comparison_focus.to_csv(out / "frontend_f2_v7_3_focus_comparison.csv", index=False)

    split_info = v72.split_info_dict(
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
    config = {
        "stage": "frontend_f2_v7_3_da_fairness_comparison",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source),
        "v72_results": str(args.v72_results),
        "positive_budgets": budgets,
        "positive_sample_seeds": sample_seeds,
        "threshold_policies": ["fixed_id_calib_q99", "guarded_id_calib_and_ood_val_target1pct"],
        "final_ood_eval_threshold_leakage": False,
        "da_checkpoint": str(da_checkpoint),
        "split_info": split_info,
        "outputs": {
            "results": str(out / "frontend_f2_v7_3_da_fairness_comparison_results.csv"),
            "summary": str(out / "frontend_f2_v7_3_da_fairness_comparison_summary.csv"),
            "focus_comparison": str(out / "frontend_f2_v7_3_focus_comparison.csv"),
            "summary_md": str(out / "summary.md"),
        },
    }
    (out / "frontend_f2_v7_3_da_fairness_comparison_metadata.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    focus_md = tv3.md_table(comparison_focus)
    full_md = tv3.md_table(summary)
    note = "\n".join(
        [
            "# Frontend-F2 v7.3 DA Fairness Comparison",
            "",
            "- Purpose: compare v7.2 source-rich few-shot ranker against DA and an original-100D few-shot control under the same final splits.",
            "- Final OOD eval is never used for threshold selection.",
            "- DA is unsupervised ID-only and uses original frontend flat100; it does not use attack labels.",
            "- Few-shot controls use the same high-purity attack positive budgets/seeds as v7.2.",
            "- Threshold policies: `fixed_id_calib_q99` and `guarded_id_calib_and_ood_val_target1pct`.",
            "",
            "## Focus Comparison",
            focus_md,
            "",
            "## Full Aggregate",
            full_md,
            "",
            "## Interpretation Boundary",
            "- `source_rich_v7_2_fewshot_logistic` and `original100_fewshot_logistic` are few-shot supervised/target-aligned detectors.",
            "- `da_unsupervised_score_seed42` is an unsupervised DA reference; it is not in the same label-information setting.",
            "- The fair label-budget question is source-rich few-shot vs original100 few-shot.",
            "- The deployment-style reference question is source-rich few-shot vs unsupervised DA at the same final OOD/attack split.",
        ]
    ) + "\n"
    (out / "summary.md").write_text(note, encoding="utf-8")
    print(f"[done] frontend-f2 v7.3 DA fairness comparison output: {out}", flush=True)
    print(tv3.md_table(comparison_focus), flush=True)


if __name__ == "__main__":
    main()
