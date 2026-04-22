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

import frontend100_timescale_tokenizer_v1_3 as tv3
import frontend_f2_v7_source_rich_diagnostic_ranker as v7
import frontend_f2_v7_1_source_rich_label_budget_ranker as v71
import frontend_f2_v7_2_fairness_validation as v72
import frontend_f2_v7_3_da_fairness_comparison as v73


DEFAULT_POSITIVE_BUDGETS = "16,32"
DEFAULT_SAMPLE_SEEDS = "42,43,44,45,46"
TARGET_ALARM = 0.01


def load_attack_bins(manifest: Dict) -> np.ndarray:
    tsv_path = Path(manifest["source_tsv"])
    use_first_n = int(manifest.get("use_first_n", 10000))
    bin_seconds = int(manifest.get("bin_seconds", 600))
    pkt = pd.read_csv(tsv_path, sep="\t", nrows=use_first_n)
    ts = pd.to_numeric(pkt["frame.time_epoch"], errors="coerce").to_numpy(np.float64)
    if not np.isfinite(ts).all():
        raise RuntimeError(f"Non-finite timestamps found in {tsv_path}")
    ts0 = float(np.min(ts))
    return ((ts - ts0) // bin_seconds).astype(np.int64)


def rows_for_bins(row_bins: np.ndarray, bins: List[int]) -> np.ndarray:
    mask = np.isin(row_bins, np.asarray(bins, dtype=np.int64))
    return np.flatnonzero(mask).astype(np.int64)


def make_holdout_specs(manifest: Dict, row_bins: np.ndarray, min_eval_rows: int) -> List[Dict]:
    strong_bins = [int(x) for x in manifest["selected_bins"]["strong_bins"]]
    specs: List[Dict] = []

    for holdout_bin in strong_bins:
        eval_idx = rows_for_bins(row_bins, [holdout_bin])
        if len(eval_idx) < int(min_eval_rows):
            continue
        train_bins = [b for b in strong_bins if b != holdout_bin]
        train_pool = rows_for_bins(row_bins, train_bins)
        specs.append(
            {
                "holdout_type": "leave_one_attack_window_out",
                "holdout_name": f"holdout_bin_{holdout_bin}",
                "train_bins": train_bins,
                "eval_bins": [holdout_bin],
                "val_bins": [],
                "train_pool_idx": train_pool,
                "attack_val_idx": train_pool,
                "attack_eval_idx": eval_idx,
            }
        )

    chrono_defs = [
        ("chrono_early_train_late_eval", [2, 3, 4], [5], [6, 7, 8]),
        ("chrono_late_train_early_eval", [6, 7, 8], [5], [2, 3, 4]),
    ]
    available = set(strong_bins)
    for name, train_bins, val_bins, eval_bins in chrono_defs:
        train_bins = [b for b in train_bins if b in available]
        val_bins = [b for b in val_bins if b in available]
        eval_bins = [b for b in eval_bins if b in available]
        train_pool = rows_for_bins(row_bins, train_bins)
        eval_idx = rows_for_bins(row_bins, eval_bins)
        val_idx = rows_for_bins(row_bins, val_bins) if val_bins else train_pool
        if len(train_pool) == 0 or len(eval_idx) < int(min_eval_rows):
            continue
        specs.append(
            {
                "holdout_type": "chronological_cross_window",
                "holdout_name": name,
                "train_bins": train_bins,
                "eval_bins": eval_bins,
                "val_bins": val_bins,
                "train_pool_idx": train_pool,
                "attack_val_idx": val_idx if len(val_idx) else train_pool,
                "attack_eval_idx": eval_idx,
            }
        )
    return specs


def fit_logistic(x_neg_id: np.ndarray, x_neg_ood: np.ndarray, x_pos: np.ndarray, c_value: float) -> tuple[LogisticRegression, StandardScaler]:
    x_train = np.concatenate([x_neg_id, x_neg_ood, x_pos], axis=0)
    y_train = np.concatenate(
        [
            np.zeros(len(x_neg_id), dtype=np.int64),
            np.zeros(len(x_neg_ood), dtype=np.int64),
            np.ones(len(x_pos), dtype=np.int64),
        ],
        axis=0,
    )
    scaler = StandardScaler()
    x_train_z = scaler.fit_transform(x_train)
    model = LogisticRegression(
        C=float(c_value),
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
        random_state=42,
    )
    model.fit(x_train_z, y_train)
    return model, scaler


def score(model: LogisticRegression, scaler: StandardScaler, x: np.ndarray) -> np.ndarray:
    return model.decision_function(scaler.transform(x)).astype(np.float64)


def metric_rows(
    holdout_spec: Dict,
    model_label: str,
    input_mode: str,
    budget: int,
    sample_seed: int,
    selected_pos_idx: np.ndarray,
    score_id_calib: np.ndarray,
    score_id_eval: np.ndarray,
    score_ood_val: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_val: np.ndarray,
    score_attack_eval: np.ndarray,
    target_alarm: float,
) -> List[Dict]:
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
    rows: List[Dict] = []
    policies = [
        (
            "fixed_id_calib_q99",
            float(np.quantile(score_id_calib, 0.99)),
            "ID calibration q99 only; final OOD eval not used",
            {},
        ),
    ]
    guarded = v72.guarded_val_threshold(score_id_calib, score_ood_val, target_alarm)
    policies.append(
        (
            "guarded_id_calib_and_ood_val_target1pct",
            float(guarded["threshold"]),
            "ID calibration + OOD validation guard; final OOD eval not used",
            guarded,
        )
    )
    for policy_name, threshold, threshold_source, selection_info in policies:
        final_alarm = float(np.mean(score_ood_eval > threshold))
        rows.append(
            {
                "holdout_type": holdout_spec["holdout_type"],
                "holdout_name": holdout_spec["holdout_name"],
                "train_bins": ",".join(str(x) for x in holdout_spec["train_bins"]),
                "val_bins": ",".join(str(x) for x in holdout_spec["val_bins"]),
                "eval_bins": ",".join(str(x) for x in holdout_spec["eval_bins"]),
                "train_pool_count": int(len(holdout_spec["train_pool_idx"])),
                "attack_val_count": int(len(holdout_spec["attack_val_idx"])),
                "attack_eval_count": int(len(holdout_spec["attack_eval_idx"])),
                "model_label": model_label,
                "training_mode": "fewshot_target_aligned_high_purity_attack",
                "input_mode": input_mode,
                "uses_attack_labels": True,
                "positive_budget": int(budget),
                "positive_sample_seed": int(sample_seed),
                "positive_train_count": int(len(selected_pos_idx)),
                "positive_train_min_row": int(np.min(selected_pos_idx)),
                "positive_train_max_row": int(np.max(selected_pos_idx)),
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
                "id_calib_alarm_at_selection": float(selection_info.get("id_calib_alarm_at_selection", np.nan)),
                "ood_val_alarm_at_selection": float(selection_info.get("ood_val_alarm_at_selection", np.nan)),
                "threshold_selection_feasible": bool(selection_info.get("selection_feasible", True)),
            }
        )
    return rows


def summarize(results: pd.DataFrame, target_alarm: float) -> pd.DataFrame:
    grouped = (
        results.groupby(
            [
                "holdout_type",
                "holdout_name",
                "train_bins",
                "eval_bins",
                "model_label",
                "input_mode",
                "positive_budget",
                "policy_name",
            ],
            as_index=False,
        )
        .agg(
            runs=("positive_sample_seed", "nunique"),
            attack_eval_count=("attack_eval_count", "first"),
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
        .sort_values(["holdout_type", "holdout_name", "positive_budget", "policy_name", "model_label"])
    )
    grouped["all_runs_strong"] = (
        (grouped["auc_min"] >= 0.95)
        & (grouped["eval_alarm_max"] <= float(target_alarm))
        & (grouped["det_min"] >= 0.80)
    )
    return grouped


def paired_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    key = ["holdout_type", "holdout_name", "train_bins", "eval_bins", "positive_budget", "policy_name"]
    src = summary[summary["model_label"].eq("source_rich_fewshot_logistic")].copy()
    old = summary[summary["model_label"].eq("original100_fewshot_logistic")].copy()
    cols = key + [
        "auc_mean",
        "auc_min",
        "eval_alarm_mean",
        "eval_alarm_max",
        "det_mean",
        "det_min",
        "feasible_rate",
        "all_runs_strong",
    ]
    src = src[cols].rename(columns={c: f"source_rich_{c}" for c in cols if c not in key})
    old = old[cols].rename(columns={c: f"original100_{c}" for c in cols if c not in key})
    merged = src.merge(old, on=key, how="inner")
    merged["delta_det_mean_source_minus_original"] = merged["source_rich_det_mean"] - merged["original100_det_mean"]
    merged["delta_det_min_source_minus_original"] = merged["source_rich_det_min"] - merged["original100_det_min"]
    merged["delta_alarm_max_source_minus_original"] = merged["source_rich_eval_alarm_max"] - merged["original100_eval_alarm_max"]
    merged["delta_auc_mean_source_minus_original"] = merged["source_rich_auc_mean"] - merged["original100_auc_mean"]
    merged["det_mean_winner"] = np.where(
        merged["delta_det_mean_source_minus_original"] > 0,
        "source_rich",
        np.where(merged["delta_det_mean_source_minus_original"] < 0, "original100", "tie"),
    )
    return merged.sort_values(["holdout_type", "holdout_name", "positive_budget", "policy_name"])


def decision_summary(summary: pd.DataFrame, deltas: pd.DataFrame) -> Dict:
    per_model = (
        summary.groupby(["model_label", "positive_budget", "policy_name"], as_index=False)
        .agg(
            holdout_count=("holdout_name", "nunique"),
            strong_holdout_count=("all_runs_strong", "sum"),
            feasible_rate_mean=("feasible_rate", "mean"),
            det_min_global=("det_min", "min"),
            alarm_max_global=("eval_alarm_max", "max"),
            auc_min_global=("auc_min", "min"),
        )
        .sort_values(["model_label", "positive_budget", "policy_name"])
    )
    delta_focus = deltas[deltas["positive_budget"].isin([16, 32])].copy()
    win_counts = (
        delta_focus.groupby(["positive_budget", "policy_name", "det_mean_winner"], as_index=False)
        .size()
        .sort_values(["positive_budget", "policy_name", "det_mean_winner"])
    )
    return {
        "per_model": per_model,
        "win_counts": win_counts,
    }


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 v7.4 paired holdout fairness package.")
    ap.add_argument("--run-tag", default=f"frontend_f2_v7_4_paired_holdout_fairness_{today}")
    ap.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    ap.add_argument(
        "--source-rich-benign-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_crosscapture_stage1_2026-04-20" / "data",
    )
    ap.add_argument(
        "--source-rich-attack-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_attack_source_2026-04-20" / "data",
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
    ap.add_argument("--min-eval-rows", type=int, default=300)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source = args.source_root
    cross_data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1 = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2_manifest_path = source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json"
    manifest = json.loads(stage2_manifest_path.read_text(encoding="utf-8-sig"))
    row_bins = load_attack_bins(manifest)
    holdout_specs = make_holdout_specs(manifest, row_bins, args.min_eval_rows)
    if not holdout_specs:
        raise RuntimeError("No holdout specs were created.")

    src_id = v7.flatten_source_rich(
        v7.load_source_rich(args.source_rich_benign_data_dir / "id_source_expression_source_rich_v1_matrix.npy")
    )
    src_ood = v7.flatten_source_rich(
        v7.load_source_rich(args.source_rich_benign_data_dir / "ood_benign_source_expression_source_rich_v1_matrix.npy")
    )
    src_attack = v7.flatten_source_rich(
        v7.load_source_rich(args.source_rich_attack_data_dir / "attack_source_expression_source_rich_v1_matrix.npy")
    )
    orig_id = v73.load_matrix(cross_data / "id_source_100.npy")
    orig_ood = v73.load_matrix(cross_data / "ood_benign_source_100.npy")
    orig_attack = v73.load_matrix(stage1 / "data" / "attack_source_100.csv")

    n_attack = min(len(src_attack), len(orig_attack), len(row_bins))
    src_attack = src_attack[:n_attack]
    orig_attack = orig_attack[:n_attack]
    row_bins = row_bins[:n_attack]
    budgets = v71.parse_positive_budgets(args.positive_budgets, max(len(s["train_pool_idx"]) for s in holdout_specs))
    sample_seeds = v72.parse_int_list(args.sample_seeds)

    id_train_end = int(args.id_train_rows)
    id_val_end = id_train_end + int(args.id_val_rows)
    id_calib_end = id_val_end + int(args.id_calibration_rows)
    ood_train_end = int(args.ood_train_rows)
    ood_val_end = ood_train_end + int(args.ood_val_rows)
    datasets = {
        "source_rich_fewshot_logistic": {
            "input_mode": "source_rich_v1_flat260",
            "id_train": src_id[:id_train_end],
            "id_calib": src_id[id_val_end:id_calib_end],
            "id_eval": src_id[id_calib_end:],
            "ood_train": src_ood[:ood_train_end],
            "ood_val": src_ood[ood_train_end:ood_val_end],
            "ood_eval": src_ood[ood_val_end:],
            "attack": src_attack,
        },
        "original100_fewshot_logistic": {
            "input_mode": "original_frontend_flat100",
            "id_train": orig_id[:id_train_end],
            "id_calib": orig_id[id_val_end:id_calib_end],
            "id_eval": orig_id[id_calib_end:],
            "ood_train": orig_ood[:ood_train_end],
            "ood_val": orig_ood[ood_train_end:ood_val_end],
            "ood_eval": orig_ood[ood_val_end:],
            "attack": orig_attack,
        },
    }

    rows: List[Dict] = []
    holdout_table_rows = []
    for spec in holdout_specs:
        holdout_table_rows.append(
            {
                "holdout_type": spec["holdout_type"],
                "holdout_name": spec["holdout_name"],
                "train_bins": ",".join(str(x) for x in spec["train_bins"]),
                "eval_bins": ",".join(str(x) for x in spec["eval_bins"]),
                "train_pool_count": int(len(spec["train_pool_idx"])),
                "attack_eval_count": int(len(spec["attack_eval_idx"])),
            }
        )
        for budget in budgets:
            for sample_seed in sample_seeds:
                selected_pos_idx = v71.choose_positive_train_indices(spec["train_pool_idx"], budget, sample_seed)
                for model_label, data in datasets.items():
                    model, scaler = fit_logistic(
                        data["id_train"],
                        data["ood_train"],
                        data["attack"][selected_pos_idx],
                        c_value=float(args.C),
                    )
                    rows.extend(
                        metric_rows(
                            holdout_spec=spec,
                            model_label=model_label,
                            input_mode=data["input_mode"],
                            budget=budget,
                            sample_seed=sample_seed,
                            selected_pos_idx=selected_pos_idx,
                            score_id_calib=score(model, scaler, data["id_calib"]),
                            score_id_eval=score(model, scaler, data["id_eval"]),
                            score_ood_val=score(model, scaler, data["ood_val"]),
                            score_ood_eval=score(model, scaler, data["ood_eval"]),
                            score_attack_val=score(model, scaler, data["attack"][spec["attack_val_idx"]]),
                            score_attack_eval=score(model, scaler, data["attack"][spec["attack_eval_idx"]]),
                            target_alarm=float(args.calibration_target),
                        )
                    )
                print(
                    f"[holdout={spec['holdout_name']} budget={budget} seed={sample_seed}] done",
                    flush=True,
                )

    results = pd.DataFrame(rows)
    summary = summarize(results, float(args.calibration_target))
    deltas = paired_deltas(summary)
    decision = decision_summary(summary, deltas)
    holdout_table = pd.DataFrame(holdout_table_rows)

    results.to_csv(out / "frontend_f2_v7_4_paired_holdout_results.csv", index=False)
    results.to_csv(out / "results.csv", index=False)
    summary.to_csv(out / "frontend_f2_v7_4_paired_holdout_summary.csv", index=False)
    deltas.to_csv(out / "frontend_f2_v7_4_paired_holdout_deltas.csv", index=False)
    holdout_table.to_csv(out / "frontend_f2_v7_4_holdout_specs.csv", index=False)
    decision["per_model"].to_csv(out / "frontend_f2_v7_4_decision_per_model.csv", index=False)
    decision["win_counts"].to_csv(out / "frontend_f2_v7_4_decision_win_counts.csv", index=False)

    config = {
        "stage": "frontend_f2_v7_4_paired_holdout_fairness",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "positive_budgets": budgets,
        "positive_sample_seeds": sample_seeds,
        "threshold_policies": ["fixed_id_calib_q99", "guarded_id_calib_and_ood_val_target1pct"],
        "final_ood_eval_threshold_leakage": False,
        "models": {
            "source_rich_fewshot_logistic": "source_rich_v1 [20,13] flattened to 260",
            "original100_fewshot_logistic": "original frontend flat100",
        },
        "stage2_manifest": str(stage2_manifest_path),
        "holdout_specs": holdout_table.to_dict("records"),
        "outputs": {
            "results": str(out / "frontend_f2_v7_4_paired_holdout_results.csv"),
            "summary": str(out / "frontend_f2_v7_4_paired_holdout_summary.csv"),
            "deltas": str(out / "frontend_f2_v7_4_paired_holdout_deltas.csv"),
            "summary_md": str(out / "summary.md"),
        },
    }
    (out / "frontend_f2_v7_4_paired_holdout_metadata.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    per_model_md = tv3.md_table(decision["per_model"])
    win_counts_md = tv3.md_table(decision["win_counts"])
    holdouts_md = tv3.md_table(holdout_table)
    focus = summary[
        (summary["positive_budget"].isin([16, 32]))
        & (summary["policy_name"].eq("fixed_id_calib_q99"))
    ].copy()
    focus_md = tv3.md_table(focus)
    delta_focus = deltas[
        (deltas["positive_budget"].isin([16, 32]))
        & (deltas["policy_name"].eq("fixed_id_calib_q99"))
    ].copy()
    delta_focus_md = tv3.md_table(delta_focus)

    source16 = decision["per_model"][
        (decision["per_model"]["model_label"].eq("source_rich_fewshot_logistic"))
        & (decision["per_model"]["positive_budget"].eq(16))
        & (decision["per_model"]["policy_name"].eq("fixed_id_calib_q99"))
    ]
    orig16 = decision["per_model"][
        (decision["per_model"]["model_label"].eq("original100_fewshot_logistic"))
        & (decision["per_model"]["positive_budget"].eq(16))
        & (decision["per_model"]["policy_name"].eq("fixed_id_calib_q99"))
    ]
    source_line = ""
    if len(source16):
        r = source16.iloc[0]
        source_line = (
            f"- Source-rich 16-shot fixed-q99: strong holdouts {int(r['strong_holdout_count'])}/{int(r['holdout_count'])}, "
            f"global det_min={float(r['det_min_global']):.4f}, alarm_max={float(r['alarm_max_global']):.4f}."
        )
    orig_line = ""
    if len(orig16):
        r = orig16.iloc[0]
        orig_line = (
            f"- Original100 16-shot fixed-q99: strong holdouts {int(r['strong_holdout_count'])}/{int(r['holdout_count'])}, "
            f"global det_min={float(r['det_min_global']):.4f}, alarm_max={float(r['alarm_max_global']):.4f}."
        )
    note = "\n".join(
        [
            "# Frontend-F2 v7.4 Paired Holdout Fairness Package",
            "",
            "- Purpose: decide whether few-shot target-aligned strength survives stricter attack-window holdouts, and whether source_rich adds performance over original100.",
            "- Compared models: `source_rich_fewshot_logistic` vs `original100_fewshot_logistic`.",
            "- Same negative train split, same positive budgets, same positive sample seeds, same threshold rules, same final OOD eval.",
            "- Final OOD eval is never used for threshold selection.",
            source_line,
            orig_line,
            "",
            "## Holdout Specs",
            holdouts_md,
            "",
            "## Decision Per Model",
            per_model_md,
            "",
            "## Winner Counts",
            win_counts_md,
            "",
            "## Fixed-Q99 Focus",
            focus_md,
            "",
            "## Fixed-Q99 Paired Deltas",
            delta_focus_md,
            "",
            "## Interpretation Boundary",
            "- If both representations remain strong, the robust claim is few-shot target alignment, not source_rich-only performance.",
            "- Source-rich earns a performance claim only where paired deltas consistently favor it under the same holdout/budget/seed/policy.",
            "- Otherwise source_rich should be positioned as auditable/diagnosable representation, with original100 as a strong performance control.",
        ]
    ) + "\n"
    (out / "summary.md").write_text(note, encoding="utf-8")
    print(f"[done] frontend-f2 v7.4 paired holdout output: {out}", flush=True)
    print(per_model_md, flush=True)


if __name__ == "__main__":
    main()
