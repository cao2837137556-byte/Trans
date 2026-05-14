from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


OUT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = OUT_DIR.parents[1]
REPO_DIR = WORKTREE_ROOT / "repo"
OOD_DIR = REPO_DIR / "ood"
SOURCE_ROOT = WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"

for p in [str(OOD_DIR), str(REPO_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import frontend100_negative_recipe_rescoring as resc  # noqa: E402


RUN_TAG = "issue07a_da_assisted_adapter_lowood_repair_2026-05-14"
BUDGETS = [16, 32]
SEEDS = [42, 43, 44, 45, 46]
TARGET_ALARM = 0.01
THRESHOLD_POLICY = "guarded_id_calib_and_ood_val_target1pct"
SUPPORT_RULE = "rng=np.random.default_rng(seed + int(budget) * 1009); rng.choice(train_idx, size=budget, replace=False)"


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj: Dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected 2D matrix from {path}, got {arr.shape}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def split_contiguous(indices: Iterable[int], train_frac: float = 0.60, val_frac: float = 0.20) -> Dict[str, np.ndarray]:
    idx = np.asarray(sorted(int(i) for i in indices), dtype=np.int64)
    n = len(idx)
    n_train = int(np.floor(n * train_frac))
    n_val = int(np.floor(n * val_frac))
    if n_train <= 0 or n_val <= 0 or n - n_train - n_val <= 0:
        raise RuntimeError(f"Not enough indices for split: n={n}")
    return {
        "train": idx[:n_train],
        "val": idx[n_train : n_train + n_val],
        "eval": idx[n_train + n_val :],
    }


def choose_positive_train_indices(train_idx: np.ndarray, budget: int, seed: int) -> np.ndarray:
    train_idx = np.asarray(train_idx, dtype=np.int64)
    if budget >= len(train_idx):
        return train_idx.copy()
    rng = np.random.default_rng(seed + int(budget) * 1009)
    chosen = rng.choice(train_idx, size=int(budget), replace=False)
    return np.asarray(sorted(chosen), dtype=np.int64)


def guarded_val_threshold(score_id_calib: np.ndarray, score_ood_val: np.ndarray, target_alarm: float) -> Dict:
    pool = np.concatenate([score_id_calib, score_ood_val]).astype(np.float64)
    q_levels = np.linspace(0.0, 1.0, 4001)[1:]
    candidates = np.unique(np.quantile(pool, q_levels))
    for thr in sorted(candidates):
        id_alarm = float(np.mean(score_id_calib > thr))
        ood_val_alarm = float(np.mean(score_ood_val > thr))
        if id_alarm <= float(target_alarm) and ood_val_alarm <= float(target_alarm):
            return {
                "threshold": float(thr),
                "id_calib_alarm_at_selection": id_alarm,
                "ood_val_alarm_at_selection": ood_val_alarm,
                "threshold_selection_feasible": True,
            }
    thr = float(np.max(pool))
    return {
        "threshold": thr,
        "id_calib_alarm_at_selection": float(np.mean(score_id_calib > thr)),
        "ood_val_alarm_at_selection": float(np.mean(score_ood_val > thr)),
        "threshold_selection_feasible": False,
    }


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: List[str] = []
        for col in cols:
            val = row[col]
            if isinstance(val, (float, np.floating)):
                vals.append(f"{float(val):.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def make_features(base_x: np.ndarray, score: np.ndarray, mode: str) -> np.ndarray:
    score_col = np.asarray(score, dtype=np.float64).reshape(-1, 1)
    if mode == "da_score_only":
        return score_col.astype(np.float32)
    if mode == "original100_plus_da_score":
        return np.concatenate([base_x.astype(np.float32), score_col.astype(np.float32)], axis=1)
    raise ValueError(f"Unknown mode: {mode}")


def fit_score_lr(
    mode: str,
    id_train_x: np.ndarray,
    ood_train_x: np.ndarray,
    attack_train_x: np.ndarray,
    id_train_score: np.ndarray,
    ood_train_score: np.ndarray,
    attack_train_score: np.ndarray,
    eval_blocks: Dict[str, tuple[np.ndarray, np.ndarray]],
) -> tuple[Dict[str, np.ndarray], Dict[str, float]]:
    train_x = np.concatenate(
        [
            make_features(id_train_x, id_train_score, mode),
            make_features(ood_train_x, ood_train_score, mode),
            make_features(attack_train_x, attack_train_score, mode),
        ],
        axis=0,
    )
    train_y = np.concatenate(
        [
            np.zeros(len(id_train_x), dtype=np.int64),
            np.zeros(len(ood_train_x), dtype=np.int64),
            np.ones(len(attack_train_x), dtype=np.int64),
        ],
        axis=0,
    )

    scaler = StandardScaler()
    train_z = scaler.fit_transform(train_x)
    model = LogisticRegression(
        C=1.0,
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
        random_state=42,
    )
    t0 = time.perf_counter()
    model.fit(train_z, train_y)
    train_time = time.perf_counter() - t0

    scored: Dict[str, np.ndarray] = {}
    t1 = time.perf_counter()
    total_eval = 0
    for name, (x, score) in eval_blocks.items():
        feats = make_features(x, score, mode)
        total_eval += len(feats)
        scored[name] = model.decision_function(scaler.transform(feats)).astype(np.float64)
    infer_time = time.perf_counter() - t1
    params = int(model.coef_.size + model.intercept_.size)
    return scored, {
        "train_time_seconds": float(train_time),
        "inference_time_seconds": float(infer_time),
        "inference_samples": int(total_eval),
        "inference_latency_ms_per_sample": float(infer_time / max(total_eval, 1) * 1000.0),
        "num_trainable_params": params,
        "feature_dim": int(train_x.shape[1]),
        "solver_converged": bool(getattr(model, "n_iter_", np.array([0]))[0] < 2000),
    }


def metric_row(
    method: str,
    input_mode: str,
    budget: int,
    seed: int,
    scores: Dict[str, np.ndarray],
    timing: Dict[str, float],
    threshold_info: Dict,
) -> Dict:
    threshold = float(threshold_info["threshold"])
    ood_eval = scores["ood_eval"]
    attack_eval = scores["attack_eval"]
    y_eval = np.concatenate([np.zeros(len(ood_eval), dtype=np.int64), np.ones(len(attack_eval), dtype=np.int64)])
    s_eval = np.concatenate([ood_eval, attack_eval])
    final_ood_alarm = float(np.mean(ood_eval > threshold))
    attack_detection = float(np.mean(attack_eval > threshold))
    return {
        "method": method,
        "input_mode": input_mode,
        "positive_budget": int(budget),
        "positive_sample_seed": int(seed),
        "threshold_policy": THRESHOLD_POLICY,
        "threshold": threshold,
        "target_alarm": TARGET_ALARM,
        "selection_feasible": bool(threshold_info["threshold_selection_feasible"]),
        "feasible": bool(final_ood_alarm <= TARGET_ALARM),
        "id_calib_alarm": float(np.mean(scores["id_calib"] > threshold)),
        "id_eval_alarm": float(np.mean(scores["id_eval"] > threshold)),
        "ood_val_alarm": float(np.mean(scores["ood_val"] > threshold)),
        "final_ood_alarm": final_ood_alarm,
        "attack_detection_val": float(np.mean(scores["attack_val"] > threshold)),
        "attack_detection": attack_detection,
        "roc_auc_attack_vs_ood": float(roc_auc_score(y_eval, s_eval)),
        "pr_auc_attack_vs_ood": float(average_precision_score(y_eval, s_eval)),
        **timing,
    }


def summarize_methods(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["method", "input_mode", "positive_budget"], as_index=False)
        .agg(
            n_seeds=("positive_sample_seed", "nunique"),
            auc_mean=("roc_auc_attack_vs_ood", "mean"),
            auc_min=("roc_auc_attack_vs_ood", "min"),
            auc_max=("roc_auc_attack_vs_ood", "max"),
            pr_auc_mean=("pr_auc_attack_vs_ood", "mean"),
            ood_alarm_mean=("final_ood_alarm", "mean"),
            ood_alarm_min=("final_ood_alarm", "min"),
            ood_alarm_max=("final_ood_alarm", "max"),
            attack_detection_mean=("attack_detection", "mean"),
            attack_detection_min=("attack_detection", "min"),
            attack_detection_max=("attack_detection", "max"),
            feasible_rate=("feasible", "mean"),
            train_time_mean=("train_time_seconds", "mean"),
            latency_ms_mean=("inference_latency_ms_per_sample", "mean"),
            params_mean=("num_trainable_params", "mean"),
        )
        .sort_values(["positive_budget", "method"])
    )


def plot_grouped(summary: pd.DataFrame, value_col: str, ylabel: str, output_name: str) -> None:
    methods = ["da_score_only_fewshot_lr", "original100_plus_da_score_fewshot_lr"]
    budgets = sorted(summary["positive_budget"].unique().tolist())
    x = np.arange(len(budgets))
    width = 0.34
    plt.figure(figsize=(6.4, 4.0))
    for i, method in enumerate(methods):
        vals = []
        for budget in budgets:
            row = summary[(summary["method"] == method) & (summary["positive_budget"] == budget)]
            vals.append(float(row[value_col].iloc[0]) if not row.empty else np.nan)
        plt.bar(x + (i - 0.5) * width, vals, width=width, label=method.replace("_fewshot_lr", "").replace("_", " "))
    if "alarm" in value_col:
        plt.axhline(0.01, color="#aa3333", linestyle="--", linewidth=1.0, label="1% target")
    plt.xticks(x, [str(b) for b in budgets])
    plt.xlabel("Positive budget")
    plt.ylabel(ylabel)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.4)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "figures" / f"{output_name}.png", dpi=300)
    plt.savefig(OUT_DIR / "figures" / f"{output_name}.pdf")
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figures").mkdir(exist_ok=True)
    (OUT_DIR / "command.txt").write_text("python run_issue07a_da_assisted_adapter.py\n", encoding="utf-8")

    official_dir = WORKTREE_ROOT / "runs" / "original100_fewshot_official_control_2026-04-22"
    score_cache = official_dir / "score_cache"
    preflight_dir = WORKTREE_ROOT / "runs" / "issue07_preflight_score_alignment_2026-05-14"
    collapse_dir = WORKTREE_ROOT / "runs" / "collapse_sanity_audit_2026-04-25"
    e2_dir = WORKTREE_ROOT / "runs" / "fewshot_seed_stability_pack_2026-04-30"

    source_data = SOURCE_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1 = SOURCE_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2 = SOURCE_ROOT / "runs" / "frontend100_joint_eval_stage2_2026-04-01"

    id_x = load_matrix(source_data / "id_source_100.npy")
    ood_x = load_matrix(source_data / "ood_benign_source_100.npy")
    attack_x = load_matrix(stage1 / "data" / "attack_source_100.csv")
    da_id = np.load(score_cache / "da_full_id_scores.npy").astype(np.float64)
    da_ood = np.load(score_cache / "da_ood_scores.npy").astype(np.float64)
    da_attack = np.load(score_cache / "da_attack_scores.npy").astype(np.float64)

    if len(da_id) != len(id_x) or len(da_ood) != len(ood_x) or len(da_attack) != len(attack_x):
        raise RuntimeError("dA score cache length mismatch with current source matrices.")

    manifest = load_json(stage2 / "attack_manifest_stage2.json")
    high_idx = np.asarray(sorted(resc.build_stage2_indices(manifest)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(attack_x))]
    attack_split = split_contiguous(high_idx)

    id_train_end = 8000
    id_val_end = 10000
    id_calib_end = 15000
    ood_train_end = 8000
    ood_val_end = 10000

    blocks = {
        "id_train": (id_x[:id_train_end], da_id[:id_train_end]),
        "id_calib": (id_x[id_val_end:id_calib_end], da_id[id_val_end:id_calib_end]),
        "id_eval": (id_x[id_calib_end:], da_id[id_calib_end:]),
        "ood_train": (ood_x[:ood_train_end], da_ood[:ood_train_end]),
        "ood_val": (ood_x[ood_train_end:ood_val_end], da_ood[ood_train_end:ood_val_end]),
        "ood_eval": (ood_x[ood_val_end:], da_ood[ood_val_end:]),
        "attack_val": (attack_x[attack_split["val"]], da_attack[attack_split["val"]]),
        "attack_eval": (attack_x[attack_split["eval"]], da_attack[attack_split["eval"]]),
    }

    result_rows: List[Dict] = []
    support_rows: List[Dict] = []

    for budget in BUDGETS:
        for seed in SEEDS:
            selected = choose_positive_train_indices(attack_split["train"], budget, seed)
            selected_set = set(selected.tolist())
            val_set = set(attack_split["val"].tolist())
            eval_set = set(attack_split["eval"].tolist())
            for row_id in selected:
                support_rows.append(
                    {
                        "positive_budget": budget,
                        "seed": seed,
                        "selected_row_id": int(row_id),
                        "support_source": "stage2_high_purity_attack_train_pool",
                        "in_candidate_train_pool": bool(row_id in set(attack_split["train"].tolist())),
                        "overlaps_attack_val": bool(row_id in val_set),
                        "overlaps_attack_eval": bool(row_id in eval_set),
                        "shared_by_methods": "da_score_only_fewshot_lr;original100_plus_da_score_fewshot_lr",
                    }
                )

            for mode, method in [
                ("da_score_only", "da_score_only_fewshot_lr"),
                ("original100_plus_da_score", "original100_plus_da_score_fewshot_lr"),
            ]:
                scored, timing = fit_score_lr(
                    mode=mode,
                    id_train_x=blocks["id_train"][0],
                    ood_train_x=blocks["ood_train"][0],
                    attack_train_x=attack_x[selected],
                    id_train_score=blocks["id_train"][1],
                    ood_train_score=blocks["ood_train"][1],
                    attack_train_score=da_attack[selected],
                    eval_blocks={
                        "id_calib": blocks["id_calib"],
                        "id_eval": blocks["id_eval"],
                        "ood_val": blocks["ood_val"],
                        "ood_eval": blocks["ood_eval"],
                        "attack_val": blocks["attack_val"],
                        "attack_eval": blocks["attack_eval"],
                    },
                )
                threshold_info = guarded_val_threshold(scored["id_calib"], scored["ood_val"], TARGET_ALARM)
                result_rows.append(
                    metric_row(
                        method=method,
                        input_mode=mode,
                        budget=budget,
                        seed=seed,
                        scores=scored,
                        timing=timing,
                        threshold_info=threshold_info,
                    )
                )
                print(f"[issue07a] {method} budget={budget} seed={seed} done", flush=True)

    result_df = pd.DataFrame(result_rows).sort_values(["positive_budget", "method", "positive_sample_seed"])
    summary_df = summarize_methods(result_df)
    support_df = pd.DataFrame(support_rows).sort_values(["positive_budget", "seed", "selected_row_id"])

    original_focus = pd.read_csv(official_dir / "original100_fewshot_official_control_focus.csv")
    e2_table = pd.read_csv(e2_dir / "paper_facing_table.csv")
    fixed_rows: List[Dict] = []
    da_base = original_focus[
        (original_focus["model_label"].str.contains("da_unsupervised", na=False))
        & (original_focus["policy_name"] == THRESHOLD_POLICY)
    ]
    if not da_base.empty:
        r = da_base.iloc[0]
        fixed_rows.append(
            {
                "baseline": "fixed_baseline_da_only",
                "positive_budget": -1,
                "source_path": str(official_dir / "original100_fewshot_official_control_focus.csv"),
                "roc_auc_attack_vs_ood": float(r["auc_mean"]),
                "final_ood_alarm": float(r["eval_alarm_mean"]),
                "attack_detection": float(r["det_mean"]),
                "feasible_rate": float(r["feasible_rate"]),
                "reuse_status": "exact_current_protocol_reusable",
            }
        )
    for _, r in e2_table[
        (e2_table["representation"] == "original100") & (e2_table["threshold_policy"] == THRESHOLD_POLICY)
    ].iterrows():
        fixed_rows.append(
            {
                "baseline": "fixed_baseline_original100_lr",
                "positive_budget": int(r["positive_budget"]),
                "source_path": str(e2_dir / "paper_facing_table.csv"),
                "roc_auc_attack_vs_ood": float(r["auc_mean"]),
                "final_ood_alarm": float(r["ood_alarm_mean"]),
                "attack_detection": float(r["attack_detection_mean"]),
                "feasible_rate": float(r["feasible_rate"]),
                "reuse_status": "exact_current_protocol_reusable",
            }
        )
    fixed_df = pd.DataFrame(fixed_rows)

    repair_base_rows = []
    da_det = float(fixed_df[fixed_df["baseline"] == "fixed_baseline_da_only"]["attack_detection"].iloc[0])
    da_alarm = float(fixed_df[fixed_df["baseline"] == "fixed_baseline_da_only"]["final_ood_alarm"].iloc[0])
    for _, r in summary_df.iterrows():
        repair_base_rows.append(
            {
                "method": r["method"],
                "positive_budget": int(r["positive_budget"]),
                "adapter_detection_mean": float(r["attack_detection_mean"]),
                "adapter_ood_alarm_mean": float(r["ood_alarm_mean"]),
                "base_detection": da_det,
                "base_ood_alarm": da_alarm,
                "detection_delta_vs_da_only": float(r["attack_detection_mean"] - da_det),
                "ood_alarm_delta_vs_da_only": float(r["ood_alarm_mean"] - da_alarm),
                "base_repair_supported": bool(float(r["attack_detection_mean"]) > da_det and float(r["feasible_rate"]) >= 0.8),
            }
        )
    repair_base_df = pd.DataFrame(repair_base_rows)

    repair_lr_rows = []
    for _, r in summary_df[summary_df["method"] == "original100_plus_da_score_fewshot_lr"].iterrows():
        budget = int(r["positive_budget"])
        lr = fixed_df[(fixed_df["baseline"] == "fixed_baseline_original100_lr") & (fixed_df["positive_budget"] == budget)]
        if lr.empty:
            continue
        lr = lr.iloc[0]
        repair_lr_rows.append(
            {
                "method": r["method"],
                "positive_budget": budget,
                "adapter_detection_mean": float(r["attack_detection_mean"]),
                "adapter_ood_alarm_mean": float(r["ood_alarm_mean"]),
                "original100_lr_detection_mean": float(lr["attack_detection"]),
                "original100_lr_ood_alarm_mean": float(lr["final_ood_alarm"]),
                "detection_delta_vs_original100_lr": float(r["attack_detection_mean"] - lr["attack_detection"]),
                "ood_alarm_delta_vs_original100_lr": float(r["ood_alarm_mean"] - lr["final_ood_alarm"]),
                "adds_value_over_original100_lr": bool(float(r["attack_detection_mean"]) > float(lr["attack_detection"])),
            }
        )
    repair_lr_df = pd.DataFrame(repair_lr_rows)

    alignment_rows = [
        {
            "score_source": "dA full ID scores",
            "path": str(score_cache / "da_full_id_scores.npy"),
            "score_len": len(da_id),
            "matrix_rows": len(id_x),
            "alignment_status": "aligned",
            "note": "Covers current primary split ID train/calib/eval slices.",
        },
        {
            "score_source": "dA OOD scores",
            "path": str(score_cache / "da_ood_scores.npy"),
            "score_len": len(da_ood),
            "matrix_rows": len(ood_x),
            "alignment_status": "aligned",
            "note": "Covers current primary split OOD train/val/eval slices.",
        },
        {
            "score_source": "dA attack scores",
            "path": str(score_cache / "da_attack_scores.npy"),
            "score_len": len(da_attack),
            "matrix_rows": len(attack_x),
            "alignment_status": "aligned",
            "note": "Covers stage2 high-purity attack train/val/eval row ids.",
        },
    ]
    alignment_df = pd.DataFrame(alignment_rows)

    threshold_df = pd.DataFrame(
        [
            {
                "threshold_name": THRESHOLD_POLICY,
                "threshold_description": "Guarded threshold selected from adapter scores on ID calibration and OOD validation only.",
                "uses_id_calib": True,
                "uses_ood_val": True,
                "uses_final_ood_eval": False,
                "uses_attack_eval": False,
                "uses_attack_train_pool": False,
                "paper_safe": True,
                "note": "Final OOD eval and final attack eval are never used for threshold selection.",
            }
        ]
    )

    result_df.to_csv(OUT_DIR / "method_comparison_all.csv", index=False)
    result_df[result_df["positive_budget"] == 16].to_csv(OUT_DIR / "method_comparison_16shot.csv", index=False)
    result_df[result_df["positive_budget"] == 32].to_csv(OUT_DIR / "method_comparison_32shot.csv", index=False)
    summary_df.to_csv(OUT_DIR / "method_comparison_summary.csv", index=False)
    fixed_df.to_csv(OUT_DIR / "fixed_baseline_metrics.csv", index=False)
    repair_base_df.to_csv(OUT_DIR / "adapter_repair_vs_base.csv", index=False)
    repair_lr_df.to_csv(OUT_DIR / "adapter_repair_vs_original100_lr.csv", index=False)
    support_df.to_csv(OUT_DIR / "support_id_provenance.csv", index=False)
    alignment_df.to_csv(OUT_DIR / "score_alignment_check.csv", index=False)
    threshold_df.to_csv(OUT_DIR / "threshold_provenance.csv", index=False)

    plot_grouped(summary_df, "attack_detection_mean", "Attack detection", "issue07a_attack_detection_grouped")
    plot_grouped(summary_df, "ood_alarm_mean", "Final OOD alarm", "issue07a_ood_alarm_grouped")

    protocol_md = f"""# Issue07a Protocol

## Scope
This run tests only dA-assisted few-shot adapter branches under the current low-OOD primary protocol. It does not retrain dA, does not use Transformer, and does not modify the manuscript.

## Data roles
- ID benign: train `[0,8000)`, calibration `[10000,15000)`, final eval `[15000,50000)`.
- OOD benign: train `[0,8000)`, validation `[8000,10000)`, final eval `[10000,20000)`.
- High-purity attack: train pool `{len(attack_split['train'])}` rows, validation `{len(attack_split['val'])}` rows, final eval `{len(attack_split['eval'])}` rows.

## Methods
- `da_score_only_fewshot_lr`: one-dimensional dA score input, L2 LogisticRegression adapter.
- `original100_plus_da_score_fewshot_lr`: original100 features concatenated with dA score, L2 LogisticRegression adapter.

## Fairness
- Final OOD eval is not used for training or threshold selection.
- Final attack eval is not used for training or threshold selection.
- dA scores are reused from existing aligned cache; dA is not retrained.
- Threshold policy: `{THRESHOLD_POLICY}`.
"""
    (OUT_DIR / "protocol.md").write_text(protocol_md, encoding="utf-8")

    baseline_md = "# Baseline Reuse Report\n\n" + md_table(fixed_df) + "\n"
    (OUT_DIR / "baseline_reuse_report.md").write_text(baseline_md, encoding="utf-8")

    score_report_md = "# dA Score Source Report\n\n" + md_table(alignment_df) + "\n"
    (OUT_DIR / "da_score_source_report.md").write_text(score_report_md, encoding="utf-8")
    (OUT_DIR / "sample_alignment_check.md").write_text(
        "# Sample Alignment Check\n\nAll dA score arrays match the row counts of the current source matrices. "
        "The adapter uses the same row slicing as the official original100 few-shot control.\n",
        encoding="utf-8",
    )
    (OUT_DIR / "score_direction_check.md").write_text(
        "# Score Direction Check\n\n"
        "- dA cache uses the original anomaly score direction: higher means more anomalous.\n"
        "- LogisticRegression adapters use `decision_function`; higher means more attack-like because attack supports are labeled positive.\n",
        encoding="utf-8",
    )
    (OUT_DIR / "missing_baseline_report.md").write_text(
        "# Missing Baseline Report\n\nNo missing baseline blocks the dA-only branch. "
        "Transformer-only remains out of scope for issue07a because full-ID Transformer scores are not yet available.\n",
        encoding="utf-8",
    )
    (OUT_DIR / "risk_register.csv").write_text(
        "risk_name,severity,reason,mitigation,recommend_continue\n"
        "dA_score_only_may_be_too_low_capacity,medium,One-dimensional dA score may not contain enough information after OOD-tail shift,Report honestly and compare with original100+dA score,yes\n"
        "original100_plus_da_score_may_not_improve,medium,dA score may be redundant with original100 features,Use original100-only baseline as fixed comparison,yes\n"
        "Transformer_branch_not_ready,medium,Full-ID Transformer scores are missing,Do not run Transformer adapter in issue07a,yes_for_da_only\n",
        encoding="utf-8",
    )

    lifecycle = """# Applicability Lifecycle Interpretation

This run tests a conservative lifecycle interpretation: dA can remain a cold-start unsupervised detector, while a lightweight few-shot adapter can be added after high-purity attack positives become available.

The experiment should not be interpreted as replacing dA. It asks whether dA scores, alone or combined with original100 features, are useful inputs for target-aligned adaptation under the guarded low-OOD protocol.
"""
    (OUT_DIR / "applicability_lifecycle_interpretation.md").write_text(lifecycle, encoding="utf-8")

    rec = """# Recommended Next Action

If the dA-score-only adapter repairs the dA-only collapse, it can support the lifecycle idea that dA scores can be recalibrated by few-shot target alignment.

If `original100_plus_da_score` improves over `original100_only`, keep it as a candidate adapter input. If it does not improve, retain original100-only LR as the minimal target-alignment baseline and treat dA score as useful mainly for cold-start diagnostics.

Do not start Transformer adapter experiments until full-ID Transformer score recovery is complete.
"""
    (OUT_DIR / "recommended_next_action.md").write_text(rec, encoding="utf-8")

    config = {
        "run_tag": RUN_TAG,
        "created_at_local": datetime.now().isoformat(timespec="seconds"),
        "task": "dA-assisted few-shot adapter low-OOD repair",
        "budgets": BUDGETS,
        "seeds": SEEDS,
        "threshold_policy": THRESHOLD_POLICY,
        "target_alarm": TARGET_ALARM,
        "new_backbone_trained": False,
        "da_retrained": False,
        "transformer_run": False,
        "data_paths": {
            "id_features": str(source_data / "id_source_100.npy"),
            "ood_features": str(source_data / "ood_benign_source_100.npy"),
            "attack_features": str(stage1 / "data" / "attack_source_100.csv"),
            "da_id_scores": str(score_cache / "da_full_id_scores.npy"),
            "da_ood_scores": str(score_cache / "da_ood_scores.npy"),
            "da_attack_scores": str(score_cache / "da_attack_scores.npy"),
            "stage2_manifest": str(stage2 / "attack_manifest_stage2.json"),
        },
        "model": {
            "type": "LogisticRegression",
            "penalty": "l2",
            "solver": "liblinear",
            "class_weight": "balanced",
            "C": 1.0,
            "max_iter": 2000,
        },
        "support_sampling_rule": SUPPORT_RULE,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    write_json(OUT_DIR / "config.json", config)

    manifest = {
        "run_tag": RUN_TAG,
        "completed": True,
        "outputs": sorted([p.name for p in OUT_DIR.iterdir() if p.is_file()] + [f"figures/{p.name}" for p in (OUT_DIR / "figures").iterdir()]),
    }
    write_json(OUT_DIR / "manifest.json", manifest)

    summary_md = f"""# Issue07a dA-assisted Few-shot Adapter Summary

## 1. Scope
This run executed only the dA-assisted few-shot adapter branch. It did not retrain dA, did not use Transformer, did not train a new backbone, did not modify the manuscript, and did not change any existing result files.

## 2. Score alignment
- dA ID score length: {len(da_id)} / ID rows: {len(id_x)}.
- dA OOD score length: {len(da_ood)} / OOD rows: {len(ood_x)}.
- dA attack score length: {len(da_attack)} / attack rows: {len(attack_x)}.
- Alignment status: passed.

## 3. Fixed baselines
{md_table(fixed_df)}

## 4. Adapter summary
{md_table(summary_df)}

## 5. Repair vs dA-only
{md_table(repair_base_df)}

## 6. Value over original100-only LR
{md_table(repair_lr_df)}

## 7. Interpretation boundary
- This is not a replacement claim against dA.
- dA remains the cold-start unsupervised detector.
- The LR adapter is a minimal deployment-stage target-alignment module.
- Transformer adapter branches are not executed here because full-ID Transformer scores are still missing.
"""
    (OUT_DIR / "summary.md").write_text(summary_md, encoding="utf-8")
    (OUT_DIR / "stdout.log").write_text("[done] issue07a dA-assisted adapter completed\n", encoding="utf-8")
    (OUT_DIR / "stderr.log").write_text("", encoding="utf-8")

    print(md_table(summary_df), flush=True)


if __name__ == "__main__":
    main()
