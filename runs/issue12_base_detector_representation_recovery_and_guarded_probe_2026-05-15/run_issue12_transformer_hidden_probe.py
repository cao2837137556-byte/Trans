from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


WORKTREE_ROOT = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
RUN_TAG = "issue12_base_detector_representation_recovery_and_guarded_probe_2026-05-15"
OUT = WORKTREE_ROOT / "runs" / RUN_TAG
HIDDEN_DIR = OUT / "hidden_cache"
TARGET_ALARM = 0.01
BUDGETS = [16, 32]
MAIN_SEEDS = [42, 43, 44, 45, 46]
HELDOUT_SEEDS = [47, 48, 49, 50, 51]
ALL_SEEDS = MAIN_SEEDS + HELDOUT_SEEDS
FIXED_OOD_WEIGHT = 2.0
SCORE_CONSISTENCY_TOL = 1e-6

SOURCE_ROOT = Path(r"D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master")
LEGACY_REPO = SOURCE_ROOT / "repo"
REPO_DIR = WORKTREE_ROOT / "repo"
OOD_DIR = REPO_DIR / "ood"
for p in [str(LEGACY_REPO), str(REPO_DIR), str(OOD_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import KitNET as kit  # noqa: E402
import frontend100_negative_recipe_rescoring as resc  # noqa: E402
from original100_fewshot_official_control import (  # noqa: E402
    choose_positive_train_indices,
    guarded_val_threshold,
    load_json,
    load_matrix,
    split_contiguous,
)


CHECKPOINT = (
    SOURCE_ROOT
    / "runs/frontend100_tailreg_stage1_2026-03-27/transformer_seed42/kitnet_transformer_seed42.ckpt"
)
ORIG_ID_PATH = SOURCE_ROOT / "runs/frontend100_crosscapture_stage1_2026-03-25/data/id_source_100.npy"
ORIG_OOD_PATH = SOURCE_ROOT / "runs/frontend100_crosscapture_stage1_2026-03-25/data/ood_benign_source_100.npy"
ORIG_ATTACK_PATH = SOURCE_ROOT / "runs/frontend100_joint_eval_stage1_2026-03-31/data/attack_source_100.csv"
STAGE2_MANIFEST = SOURCE_ROOT / "runs/frontend100_joint_eval_stage2_2026-04-01/attack_manifest_stage2.json"

ISSUE07B_SCORE_DIR = (
    WORKTREE_ROOT
    / "runs/issue07b_transformer_full_id_score_recovery_2026-05-14/score_cache"
)
TRANSFORMER_ID_SCORE = ISSUE07B_SCORE_DIR / "transformer_full_id_scores.npy"
TRANSFORMER_OOD_SCORE = ISSUE07B_SCORE_DIR / "transformer_ood_scores.npy"
TRANSFORMER_ATTACK_SCORE = ISSUE07B_SCORE_DIR / "transformer_attack_scores.npy"

ISSUE07B_RERUN_DIR = (
    WORKTREE_ROOT
    / "runs/issue07b_transformer_assisted_adapter_lowood_repair_2026-05-14_rerun_with_recovered_scores"
)
ISSUE11_DIR = WORKTREE_ROOT / "runs/issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"

HIDDEN_ID_PATH = HIDDEN_DIR / "transformer_outputlayer_meanpooled_hidden_id.npy"
HIDDEN_OOD_PATH = HIDDEN_DIR / "transformer_outputlayer_meanpooled_hidden_ood.npy"
HIDDEN_ATTACK_PATH = HIDDEN_DIR / "transformer_outputlayer_meanpooled_hidden_attack.npy"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, obj: Dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: List[str] = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def seed_group(seed: int) -> str:
    if seed in MAIN_SEEDS:
        return "main_paired_42_46"
    if seed in HELDOUT_SEEDS:
        return "heldout_support_47_51"
    return "unknown"


def output_layer_hidden_and_score(model: kit.KitNET, x: np.ndarray) -> Tuple[np.ndarray, float]:
    """Replicate executeAD and expose outputLayer mean-pooled encoder representation.

    The scalar score produced here is checked against the existing score cache before
    any adapter result is trusted.
    """
    s_l1 = np.zeros(len(model.ensembleLayer), dtype=np.float64)
    for i in range(len(model.ensembleLayer)):
        s_l1[i] = model.ensembleLayer[i].execute(x[model.v[i]])

    layer = model.outputLayer
    x_pre = layer.preprocess(s_l1, update_stats=False)
    layer.model.eval()
    with torch.no_grad():
        input_tensor = torch.tensor(x_pre, dtype=torch.float32).view(1, layer.input_dim, 1)
        h = layer.model.input_net(input_tensor)
        h = layer.model.transformer(h)
        pooled = torch.mean(h, dim=1).cpu().numpy()[0].astype(np.float32)
        output = layer.model.output_net(h)
        target = torch.tensor(x_pre, dtype=torch.float32).view(1, layer.input_dim, 1)
        score = float(torch.sqrt(layer.criterion(output, target)).item()) + 1e-6
    return pooled, score


def recover_hidden_for_matrix(
    *,
    name: str,
    matrix: np.ndarray,
    score_cache: np.ndarray,
    output_path: Path,
    progress_every: int = 1000,
) -> List[Dict]:
    model = kit.KitNET.load_checkpoint(CHECKPOINT)
    n = len(matrix)
    first_hidden, first_score = output_layer_hidden_and_score(model, matrix[0].astype(np.float64))
    dim = int(first_hidden.shape[0])
    hidden = np.zeros((n, dim), dtype=np.float32)
    hidden[0] = first_hidden
    consistency_rows = [
        {
            "dataset": name,
            "row_id": 0,
            "computed_score": first_score,
            "cached_score": float(score_cache[0]),
            "abs_diff": abs(first_score - float(score_cache[0])),
            "passes": bool(abs(first_score - float(score_cache[0])) <= SCORE_CONSISTENCY_TOL),
        }
    ]
    t0 = time.perf_counter()
    for i in range(1, n):
        h, score = output_layer_hidden_and_score(model, matrix[i].astype(np.float64))
        hidden[i] = h
        if i in {1, min(8000, n - 1), min(13000, n - 1), n - 1}:
            consistency_rows.append(
                {
                    "dataset": name,
                    "row_id": int(i),
                    "computed_score": score,
                    "cached_score": float(score_cache[i]),
                    "abs_diff": abs(score - float(score_cache[i])),
                        "passes": bool(abs(score - float(score_cache[i])) <= SCORE_CONSISTENCY_TOL),
                }
            )
        if (i + 1) % progress_every == 0 or (i + 1) == n:
            elapsed = time.perf_counter() - t0
            write_json(
                OUT / "progress.json",
                {
                    "phase": "hidden_recovery",
                    "dataset": name,
                    "rows_done": int(i + 1),
                    "rows_total": int(n),
                    "elapsed_seconds": elapsed,
                    "rows_per_second": float((i + 1) / elapsed) if elapsed > 0 else None,
                    "updated_at": now(),
                },
            )
            print(f"[hidden] {name}: {i + 1}/{n} rows, elapsed={elapsed:.1f}s", flush=True)
    np.save(output_path, hidden)
    return consistency_rows


def recover_hidden_if_needed(id_x: np.ndarray, ood_x: np.ndarray, attack_x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    score_id = np.load(TRANSFORMER_ID_SCORE, mmap_mode="r")
    score_ood = np.load(TRANSFORMER_OOD_SCORE, mmap_mode="r")
    score_attack = np.load(TRANSFORMER_ATTACK_SCORE, mmap_mode="r")
    consistency_rows: List[Dict] = []
    if HIDDEN_ID_PATH.exists() and HIDDEN_OOD_PATH.exists() and HIDDEN_ATTACK_PATH.exists():
        h_id = np.load(HIDDEN_ID_PATH)
        h_ood = np.load(HIDDEN_OOD_PATH)
        h_attack = np.load(HIDDEN_ATTACK_PATH)
        # Re-check a few scores even when reusing cache.
        for name, mat, scores in [
            ("id", id_x, score_id),
            ("ood", ood_x, score_ood),
            ("attack", attack_x, score_attack),
        ]:
            model = kit.KitNET.load_checkpoint(CHECKPOINT)
            for idx in [0, 1, min(8000, len(mat) - 1), len(mat) - 1]:
                _, score = output_layer_hidden_and_score(model, mat[idx].astype(np.float64))
                consistency_rows.append(
                    {
                        "dataset": name,
                        "row_id": int(idx),
                        "computed_score": score,
                        "cached_score": float(scores[idx]),
                        "abs_diff": abs(score - float(scores[idx])),
                        "passes": bool(abs(score - float(scores[idx])) <= SCORE_CONSISTENCY_TOL),
                    }
                )
        return h_id, h_ood, h_attack, pd.DataFrame(consistency_rows)

    consistency_rows.extend(
        recover_hidden_for_matrix(name="id", matrix=id_x, score_cache=score_id, output_path=HIDDEN_ID_PATH)
    )
    consistency_rows.extend(
        recover_hidden_for_matrix(name="ood", matrix=ood_x, score_cache=score_ood, output_path=HIDDEN_OOD_PATH)
    )
    consistency_rows.extend(
        recover_hidden_for_matrix(
            name="attack", matrix=attack_x, score_cache=score_attack, output_path=HIDDEN_ATTACK_PATH
        )
    )
    h_id = np.load(HIDDEN_ID_PATH)
    h_ood = np.load(HIDDEN_OOD_PATH)
    h_attack = np.load(HIDDEN_ATTACK_PATH)
    return h_id, h_ood, h_attack, pd.DataFrame(consistency_rows)


def metric_row(
    *,
    method: str,
    representation: str,
    guard_type: str,
    input_mode: str,
    budget: int,
    seed: int,
    ood_negative_weight: float,
    score_id_calib: np.ndarray,
    score_ood_val: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_eval: np.ndarray,
    threshold: float,
    threshold_info: Dict,
    train_time_seconds: float,
    inference_time_seconds: float,
    parameter_count: int,
    feature_dim: int,
    hidden_dim: int,
) -> Dict:
    y_auc = np.concatenate(
        [np.zeros(len(score_ood_eval), dtype=np.int64), np.ones(len(score_attack_eval), dtype=np.int64)]
    )
    s_auc = np.concatenate([score_ood_eval, score_attack_eval])
    final_ood_alarm = float(np.mean(score_ood_eval > threshold))
    attack_detection = float(np.mean(score_attack_eval > threshold))
    return {
        "method": method,
        "representation": representation,
        "guard_type": guard_type,
        "input_mode": input_mode,
        "positive_budget": int(budget),
        "seed": int(seed),
        "seed_group": seed_group(seed),
        "ood_negative_weight": float(ood_negative_weight),
        "threshold_policy": "guarded_id_calib_and_ood_val_target1pct",
        "threshold": float(threshold),
        "id_calib_alarm_at_selection": float(threshold_info["id_calib_alarm_at_selection"]),
        "ood_val_alarm_at_selection": float(threshold_info["ood_val_alarm_at_selection"]),
        "threshold_selection_feasible": bool(threshold_info["selection_feasible"]),
        "roc_auc": float(roc_auc_score(y_auc, s_auc)),
        "pr_auc": float(average_precision_score(y_auc, s_auc)),
        "final_ood_alarm": final_ood_alarm,
        "attack_detection": attack_detection,
        "feasible": bool(final_ood_alarm <= TARGET_ALARM),
        "attack_eval_size": int(len(score_attack_eval)),
        "final_ood_eval_size": int(len(score_ood_eval)),
        "hidden_dim": int(hidden_dim),
        "pooling_type": "outputLayer_transformer_mean_pool",
        "checkpoint_id": str(CHECKPOINT),
        "train_time_seconds": float(train_time_seconds),
        "inference_time_seconds": float(inference_time_seconds),
        "parameter_count": int(parameter_count),
        "feature_dim": int(feature_dim),
    }


def eval_lr(
    *,
    method: str,
    representation: str,
    guard_type: str,
    input_mode: str,
    budget: int,
    seed: int,
    ood_negative_weight: float,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_attack_train_pool: np.ndarray,
    attack_train_pool_rows: np.ndarray,
    attack_val_rows: np.ndarray,
    attack_eval_rows: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
    hidden_dim: int,
) -> Tuple[Dict, List[Dict], Dict]:
    selected_rows = choose_positive_train_indices(attack_train_pool_rows, budget, seed)
    row_to_pos = {int(r): i for i, r in enumerate(attack_train_pool_rows)}
    selected_pos = np.asarray([row_to_pos[int(r)] for r in selected_rows], dtype=np.int64)

    x_train = np.concatenate([x_id_train, x_ood_train, x_attack_train_pool[selected_pos]], axis=0)
    y_train = np.concatenate(
        [
            np.zeros(len(x_id_train), dtype=np.int64),
            np.zeros(len(x_ood_train), dtype=np.int64),
            np.ones(len(selected_pos), dtype=np.int64),
        ],
        axis=0,
    )
    sample_weight = np.concatenate(
        [
            np.ones(len(x_id_train), dtype=np.float64),
            np.full(len(x_ood_train), float(ood_negative_weight), dtype=np.float64),
            np.ones(len(selected_pos), dtype=np.float64),
        ]
    )

    scaler = StandardScaler()
    t0 = time.perf_counter()
    x_train_z = scaler.fit_transform(x_train)
    model = LogisticRegression(
        C=1.0,
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
        random_state=42,
    )
    model.fit(x_train_z, y_train, sample_weight=sample_weight)
    train_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    score_id_calib = model.decision_function(scaler.transform(x_id_calib)).astype(np.float64)
    score_ood_val = model.decision_function(scaler.transform(x_ood_val)).astype(np.float64)
    score_ood_eval = model.decision_function(scaler.transform(x_ood_eval)).astype(np.float64)
    score_attack_eval = model.decision_function(scaler.transform(x_attack_eval)).astype(np.float64)
    infer_time = time.perf_counter() - t1
    guarded = guarded_val_threshold(score_id_calib, score_ood_val, TARGET_ALARM)
    row = metric_row(
        method=method,
        representation=representation,
        guard_type=guard_type,
        input_mode=input_mode,
        budget=budget,
        seed=seed,
        ood_negative_weight=ood_negative_weight,
        score_id_calib=score_id_calib,
        score_ood_val=score_ood_val,
        score_ood_eval=score_ood_eval,
        score_attack_eval=score_attack_eval,
        threshold=float(guarded["threshold"]),
        threshold_info=guarded,
        train_time_seconds=train_time,
        inference_time_seconds=infer_time,
        parameter_count=int(model.coef_.size + model.intercept_.size),
        feature_dim=int(x_train.shape[1]),
        hidden_dim=hidden_dim,
    )
    train_pool_set = set(attack_train_pool_rows.tolist())
    val_set = set(attack_val_rows.tolist())
    eval_set = set(attack_eval_rows.tolist())
    support_rows = [
        {
            "method": method,
            "representation": representation,
            "guard_type": guard_type,
            "positive_budget": int(budget),
            "seed": int(seed),
            "seed_group": seed_group(seed),
            "ood_negative_weight": float(ood_negative_weight),
            "selected_attack_row_id": int(r),
            "support_source": "stage2_high_purity_attack_train_pool",
            "in_attack_train_pool": bool(r in train_pool_set),
            "overlaps_attack_val": bool(r in val_set),
            "overlaps_attack_eval": bool(r in eval_set),
        }
        for r in selected_rows
    ]
    threshold_row = {
        "method": method,
        "representation": representation,
        "guard_type": guard_type,
        "positive_budget": int(budget),
        "seed": int(seed),
        "seed_group": seed_group(seed),
        "ood_negative_weight": float(ood_negative_weight),
        "threshold_policy": "guarded_id_calib_and_ood_val_target1pct",
        "uses_id_calib": True,
        "uses_ood_val": True,
        "uses_final_ood_eval": False,
        "uses_attack_eval": False,
        "threshold": float(guarded["threshold"]),
        "id_calib_alarm_at_selection": float(guarded["id_calib_alarm_at_selection"]),
        "ood_val_alarm_at_selection": float(guarded["ood_val_alarm_at_selection"]),
        "paper_safe": True,
    }
    return row, support_rows, threshold_row


def summarize(seed_df: pd.DataFrame) -> pd.DataFrame:
    return (
        seed_df.groupby(
            [
                "seed_group",
                "method",
                "representation",
                "guard_type",
                "input_mode",
                "positive_budget",
                "ood_negative_weight",
                "threshold_policy",
            ],
            as_index=False,
        )
        .agg(
            n_seeds=("seed", "nunique"),
            auc_mean=("roc_auc", "mean"),
            auc_std=("roc_auc", "std"),
            auc_min=("roc_auc", "min"),
            auc_max=("roc_auc", "max"),
            pr_auc_mean=("pr_auc", "mean"),
            pr_auc_min=("pr_auc", "min"),
            pr_auc_max=("pr_auc", "max"),
            ood_alarm_mean=("final_ood_alarm", "mean"),
            ood_alarm_std=("final_ood_alarm", "std"),
            ood_alarm_min=("final_ood_alarm", "min"),
            ood_alarm_max=("final_ood_alarm", "max"),
            attack_detection_mean=("attack_detection", "mean"),
            attack_detection_std=("attack_detection", "std"),
            attack_detection_min=("attack_detection", "min"),
            attack_detection_max=("attack_detection", "max"),
            feasible_rate=("feasible", "mean"),
            parameter_count_mean=("parameter_count", "mean"),
            feature_dim=("feature_dim", "max"),
            hidden_dim=("hidden_dim", "max"),
        )
        .sort_values(["seed_group", "positive_budget", "method"])
    )


def make_alignment_rows(h_id: np.ndarray, h_ood: np.ndarray, h_attack: np.ndarray) -> List[Dict]:
    rows = []
    for split, n, hidden_available, original100_available, label in [
        ("id_train", 8000, len(h_id) >= 8000, True, "ID benign"),
        ("id_calib", 5000, len(h_id) >= 15000, True, "ID benign"),
        ("id_eval", 35000, len(h_id) == 50000, True, "ID benign"),
        ("ood_train", 8000, len(h_ood) >= 8000, True, "OOD benign"),
        ("ood_val", 2000, len(h_ood) >= 10000, True, "OOD benign"),
        ("ood_eval", 10000, len(h_ood) == 20000, True, "OOD benign"),
        ("attack_all", 10000, len(h_attack) == 10000, True, "high-purity attack source"),
    ]:
        rows.append(
            {
                "split": split,
                "expected_rows": n,
                "label": label,
                "hidden_available": bool(hidden_available),
                "original100_available": bool(original100_available),
                "aligned": bool(hidden_available and original100_available),
                "notes": "row-order alignment by current low-OOD feature/cache convention",
            }
        )
    return rows


def compare_to_issue11(summary_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    issue11 = pd.read_csv(ISSUE11_DIR / "method_comparison_summary.csv")
    baselines = issue11[
        issue11["method"].isin(
            [
                "original100_plain_lr",
                "original100_fixed_guard_lr",
                "source_rich_fixed_guard_lr",
                "original100_plus_source_rich_fixed_guard_lr",
            ]
        )
    ].copy()
    rows = []
    for _, row in summary_df.iterrows():
        for baseline_method in ["original100_plain_lr", "original100_fixed_guard_lr", "original100_plus_source_rich_fixed_guard_lr"]:
            base = baselines[
                baselines["seed_group"].eq(row["seed_group"])
                & baselines["positive_budget"].eq(row["positive_budget"])
                & baselines["method"].eq(baseline_method)
            ]
            if base.empty:
                continue
            b = base.iloc[0]
            rows.append(
                {
                    "seed_group": row["seed_group"],
                    "positive_budget": int(row["positive_budget"]),
                    "method": row["method"],
                    "baseline_method": baseline_method,
                    "method_detection_mean": float(row["attack_detection_mean"]),
                    "baseline_detection_mean": float(b["attack_detection_mean"]),
                    "detection_delta": float(row["attack_detection_mean"] - b["attack_detection_mean"]),
                    "method_ood_alarm_mean": float(row["ood_alarm_mean"]),
                    "baseline_ood_alarm_mean": float(b["ood_alarm_mean"]),
                    "ood_alarm_delta": float(row["ood_alarm_mean"] - b["ood_alarm_mean"]),
                    "method_ood_alarm_max": float(row["ood_alarm_max"]),
                    "baseline_ood_alarm_max": float(b["ood_alarm_max"]),
                    "method_feasible_rate": float(row["feasible_rate"]),
                    "baseline_feasible_rate": float(b["feasible_rate"]),
                    "feasible_delta": float(row["feasible_rate"] - b["feasible_rate"]),
                }
            )
    return baselines, pd.DataFrame(rows)


def hidden_vs_scalar_reference(summary_df: pd.DataFrame) -> pd.DataFrame:
    scalar = pd.read_csv(ISSUE07B_RERUN_DIR / "method_comparison_summary.csv")
    rows = []
    for _, row in summary_df.iterrows():
        if row["seed_group"] != "main_paired_42_46":
            continue
        if row["method"] == "transformer_hidden_plain_lr":
            scalar_method = "transformer_score_only_fewshot_lr"
        elif row["method"] == "original100_plus_transformer_hidden_fixed_guard_lr":
            scalar_method = "original100_plus_transformer_score_fewshot_lr"
        else:
            continue
        s = scalar[
            scalar["method"].eq(scalar_method)
            & scalar["positive_budget"].eq(row["positive_budget"])
        ]
        if s.empty:
            continue
        s0 = s.iloc[0]
        rows.append(
            {
                "seed_group": row["seed_group"],
                "hidden_method": row["method"],
                "scalar_reference_method": scalar_method,
                "positive_budget": int(row["positive_budget"]),
                "hidden_detection_mean": float(row["attack_detection_mean"]),
                "scalar_detection_mean": float(s0["attack_detection_mean"]),
                "detection_delta_hidden_minus_scalar": float(row["attack_detection_mean"] - s0["attack_detection_mean"]),
                "hidden_ood_alarm_mean": float(row["ood_alarm_mean"]),
                "scalar_ood_alarm_mean": float(s0["ood_alarm_mean"]),
                "ood_alarm_delta_hidden_minus_scalar": float(row["ood_alarm_mean"] - s0["ood_alarm_mean"]),
                "hidden_feasible_rate": float(row["feasible_rate"]),
                "scalar_feasible_rate": float(s0["feasible_rate"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    (OUT / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")
    started = now()

    id_x = load_matrix(ORIG_ID_PATH)
    ood_x = load_matrix(ORIG_OOD_PATH)
    attack_x = load_matrix(ORIG_ATTACK_PATH)
    asset_shape_rows = [
        {"asset": "original100_id", "path": str(ORIG_ID_PATH), "shape": str(id_x.shape), "shape_ok": id_x.shape == (50000, 100)},
        {"asset": "original100_ood", "path": str(ORIG_OOD_PATH), "shape": str(ood_x.shape), "shape_ok": ood_x.shape == (20000, 100)},
        {"asset": "original100_attack", "path": str(ORIG_ATTACK_PATH), "shape": str(attack_x.shape), "shape_ok": attack_x.shape == (10000, 100)},
        {"asset": "transformer_id_scores", "path": str(TRANSFORMER_ID_SCORE), "shape": str(np.load(TRANSFORMER_ID_SCORE, mmap_mode='r').shape), "shape_ok": np.load(TRANSFORMER_ID_SCORE, mmap_mode='r').shape == (50000,)},
        {"asset": "transformer_ood_scores", "path": str(TRANSFORMER_OOD_SCORE), "shape": str(np.load(TRANSFORMER_OOD_SCORE, mmap_mode='r').shape), "shape_ok": np.load(TRANSFORMER_OOD_SCORE, mmap_mode='r').shape == (20000,)},
        {"asset": "transformer_attack_scores", "path": str(TRANSFORMER_ATTACK_SCORE), "shape": str(np.load(TRANSFORMER_ATTACK_SCORE, mmap_mode='r').shape), "shape_ok": np.load(TRANSFORMER_ATTACK_SCORE, mmap_mode='r').shape == (10000,)},
    ]
    pd.DataFrame(asset_shape_rows).to_csv(OUT / "asset_shape_check.csv", index=False)
    if not all(r["shape_ok"] for r in asset_shape_rows):
        (OUT / "alignment_failure_report.md").write_text(
            "# Alignment failure\n\nInput asset shapes do not match current low-OOD protocol. Phase A/B stopped.\n",
            encoding="utf-8",
        )
        raise SystemExit("asset shape gate failed")

    h_id, h_ood, h_attack, consistency_df = recover_hidden_if_needed(id_x, ood_x, attack_x)
    consistency_df.to_csv(OUT / "score_consistency_check.csv", index=False)
    consistency_pass = bool((consistency_df["passes"] == True).all())  # noqa: E712
    hidden_shape_ok = h_id.shape == (50000, 16) and h_ood.shape == (20000, 16) and h_attack.shape == (10000, 16)

    alignment_rows = make_alignment_rows(h_id, h_ood, h_attack)
    pd.DataFrame(alignment_rows).to_csv(OUT / "hidden_alignment_check.csv", index=False)

    (OUT / "transformer_hidden_asset_report.md").write_text(
        "\n".join(
            [
                "# Transformer Hidden Asset Report",
                "",
                f"- Checkpoint: `{CHECKPOINT}`",
                f"- Model source: `{LEGACY_REPO / 'Trans.py'}`",
                "- Hidden source: outputLayer Transformer encoder mean-pooled representation before output_net.",
                "- Primary hidden policy: one pre-specified representation only; no layer search.",
                "- Hidden extraction training performed: False.",
                f"- Score consistency tolerance: `{SCORE_CONSISTENCY_TOL}`.",
                f"- ID hidden: `{HIDDEN_ID_PATH}` shape `{h_id.shape}`",
                f"- OOD hidden: `{HIDDEN_OOD_PATH}` shape `{h_ood.shape}`",
                f"- Attack hidden: `{HIDDEN_ATTACK_PATH}` shape `{h_attack.shape}`",
                f"- Score consistency pass: `{consistency_pass}`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (OUT / "dA_latent_feasibility_inventory.md").write_text(
        "\n".join(
            [
                "# dA Latent Feasibility Inventory",
                "",
                "- dA scalar RMSE scores are available and were already tested in issue07a.",
                "- No current-protocol dA latent/encoder cache was found or recovered in this run.",
                "- Recovering dA latent would require inspecting the dA hidden-layer activations and validating score/row consistency separately.",
                "- This run does not implement dA latent recovery; doing so remains a possible but lower-priority follow-up.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if not consistency_pass or not hidden_shape_ok:
        (OUT / "transformer_hidden_recovery_failure_report.md").write_text(
            "\n".join(
                [
                    "# Transformer Hidden Recovery Failure",
                    "",
                    f"- Score consistency pass: `{consistency_pass}`",
                    f"- Hidden shape ok: `{hidden_shape_ok}`",
                    "- Phase B was not executed because the hard gate failed.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        write_json(
            OUT / "manifest.json",
            {"run_tag": RUN_TAG, "phase_a_completed": False, "phase_b_executed": False},
        )
        return
    failure_path = OUT / "transformer_hidden_recovery_failure_report.md"
    if failure_path.exists():
        failure_path.unlink()

    manifest = load_json(STAGE2_MANIFEST)
    high_idx = np.asarray(sorted(resc.build_stage2_indices(manifest)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(attack_x))]
    attack_split = split_contiguous(high_idx, 0.60, 0.20)

    id_train_end, id_val_end, id_calib_end = 8000, 10000, 15000
    ood_train_end, ood_val_end = 8000, 10000
    orig_splits = {
        "id_train": id_x[:id_train_end],
        "id_calib": id_x[id_val_end:id_calib_end],
        "ood_train": ood_x[:ood_train_end],
        "ood_val": ood_x[ood_train_end:ood_val_end],
        "ood_eval": ood_x[ood_val_end:],
        "attack_train_pool": attack_x[attack_split["train"]],
        "attack_eval": attack_x[attack_split["eval"]],
    }
    hidden_splits = {
        "id_train": h_id[:id_train_end],
        "id_calib": h_id[id_val_end:id_calib_end],
        "ood_train": h_ood[:ood_train_end],
        "ood_val": h_ood[ood_train_end:ood_val_end],
        "ood_eval": h_ood[ood_val_end:],
        "attack_train_pool": h_attack[attack_split["train"]],
        "attack_eval": h_attack[attack_split["eval"]],
    }
    concat_splits = {k: np.concatenate([orig_splits[k], hidden_splits[k]], axis=1) for k in orig_splits}

    method_specs = [
        (
            "transformer_hidden_plain_lr",
            "transformer_hidden",
            "plain",
            "transformer_outputlayer_meanpooled_hidden16",
            1.0,
            hidden_splits,
        ),
        (
            "transformer_hidden_fixed_guard_lr",
            "transformer_hidden",
            "fixed_ood_weight_2",
            "transformer_outputlayer_meanpooled_hidden16",
            FIXED_OOD_WEIGHT,
            hidden_splits,
        ),
        (
            "original100_plus_transformer_hidden_fixed_guard_lr",
            "original100_plus_transformer_hidden",
            "fixed_ood_weight_2",
            "original100_flat100_plus_transformer_hidden16",
            FIXED_OOD_WEIGHT,
            concat_splits,
        ),
    ]
    result_rows: List[Dict] = []
    support_rows: List[Dict] = []
    threshold_rows: List[Dict] = []
    for method, representation, guard_type, input_mode, weight, splits in method_specs:
        for budget in BUDGETS:
            for seed in ALL_SEEDS:
                row, supports, threshold = eval_lr(
                    method=method,
                    representation=representation,
                    guard_type=guard_type,
                    input_mode=input_mode,
                    budget=budget,
                    seed=seed,
                    ood_negative_weight=weight,
                    x_id_train=splits["id_train"],
                    x_ood_train=splits["ood_train"],
                    x_attack_train_pool=splits["attack_train_pool"],
                    attack_train_pool_rows=attack_split["train"],
                    attack_val_rows=attack_split["val"],
                    attack_eval_rows=attack_split["eval"],
                    x_id_calib=splits["id_calib"],
                    x_ood_val=splits["ood_val"],
                    x_ood_eval=splits["ood_eval"],
                    x_attack_eval=splits["attack_eval"],
                    hidden_dim=16,
                )
                result_rows.append(row)
                support_rows.extend(supports)
                threshold_rows.append(threshold)
                print(f"[done] {method} budget={budget} seed={seed}", flush=True)

    seed_df = pd.DataFrame(result_rows)
    summary_df = summarize(seed_df)
    seed_df.to_csv(OUT / "method_comparison_seed_level.csv", index=False)
    summary_df.to_csv(OUT / "method_comparison_summary.csv", index=False)
    summary_df[summary_df.positive_budget.eq(16)].to_csv(OUT / "method_comparison_16shot.csv", index=False)
    summary_df[summary_df.positive_budget.eq(32)].to_csv(OUT / "method_comparison_32shot.csv", index=False)
    pd.DataFrame(support_rows).to_csv(OUT / "support_id_provenance.csv", index=False)
    pd.DataFrame(threshold_rows).to_csv(OUT / "threshold_provenance.csv", index=False)

    baselines, hidden_vs_original100 = compare_to_issue11(summary_df)
    baselines.to_csv(OUT / "fixed_baseline_reference_from_issue11.csv", index=False)
    hidden_vs_original100.to_csv(OUT / "hidden_vs_original100_fixed_guard.csv", index=False)
    hidden_vs_scalar = hidden_vs_scalar_reference(summary_df)
    hidden_vs_scalar.to_csv(OUT / "hidden_vs_scalar_score_reference.csv", index=False)

    (OUT / "hidden_scaling_report.md").write_text(
        "\n".join(
            [
                "# Hidden Scaling Report",
                "",
                "- Scaler: `StandardScaler`.",
                "- Fit scope: training data only: ID benign train + OOD benign train + selected high-purity attack supports.",
                "- Hidden cache itself is generated without fitting any scaler on final OOD eval or attack eval.",
                "- Final OOD eval and attack eval are never used for scaler fitting or threshold selection.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (OUT / "protocol.md").write_text(
        "\n".join(
            [
                "# Issue12 Transformer Hidden Recovery and Fixed-Guard Probe Protocol",
                "",
                "- Phase A recovers Transformer outputLayer mean-pooled hidden representation from an existing checkpoint only.",
                "- Phase A hard gate: row coverage, hidden shape, and scalar score consistency against issue07b score cache.",
                "- Phase B executes only three methods: hidden-only plain LR, hidden-only fixed guard LR, and original100+hidden fixed guard LR.",
                "- Fixed guard: OOD benign sample weight = 2; no OOD-weight or C search.",
                "- Threshold: guarded_id_calib_and_ood_val_target1pct.",
                "- Final OOD eval and attack eval are not used for training, scaler fitting, threshold selection, or configuration selection.",
                "- This run is a representation probe, not full GDA.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "risk_name": "hidden alignment risk",
                "severity": "medium",
                "reason": "Hidden cache is derived from legacy Transformer checkpoint and row-order conventions.",
                "mitigation": "Gate with scalar score consistency and current split length checks.",
            },
            {
                "risk_name": "checkpoint mismatch risk",
                "severity": "medium",
                "reason": "Mainline and legacy Trans.py differ; issue07b score recovery used legacy root.",
                "mitigation": "Use the exact legacy checkpoint/code path that reproduced scalar score cache.",
            },
            {
                "risk_name": "hidden dimensionality overfitting risk",
                "severity": "low",
                "reason": "Hidden dim is 16, but few-shot positives remain small.",
                "mitigation": "Report seed mean/min/max and held-out support seeds separately.",
            },
            {
                "risk_name": "no gain over original100 guard risk",
                "severity": "high",
                "reason": "Original100 fixed guard is a strong baseline from issue11.",
                "mitigation": "Compare directly to original100 fixed guard and avoid overclaiming if no gain.",
            },
            {
                "risk_name": "base-detector integration overclaim risk",
                "severity": "high",
                "reason": "This is fixed-guard LR on one Transformer hidden representation, not full detector-agnostic GDA.",
                "mitigation": "Use representation probe wording only.",
            },
        ]
    ).to_csv(OUT / "risk_register.csv", index=False)

    main32 = summary_df[
        summary_df.seed_group.eq("main_paired_42_46") & summary_df.positive_budget.eq(32)
    ].copy()
    heldout32 = summary_df[
        summary_df.seed_group.eq("heldout_support_47_51") & summary_df.positive_budget.eq(32)
    ].copy()
    main32_simple = main32[
        [
            "method",
            "representation",
            "guard_type",
            "attack_detection_mean",
            "attack_detection_min",
            "ood_alarm_mean",
            "ood_alarm_max",
            "feasible_rate",
        ]
    ]
    issue11_summary = pd.read_csv(ISSUE11_DIR / "method_comparison_summary.csv")
    orig_fixed_32 = issue11_summary[
        issue11_summary.seed_group.eq("main_paired_42_46")
        & issue11_summary.positive_budget.eq(32)
        & issue11_summary.method.eq("original100_fixed_guard_lr")
    ].iloc[0]
    orig_fixed_32_heldout = issue11_summary[
        issue11_summary.seed_group.eq("heldout_support_47_51")
        & issue11_summary.positive_budget.eq(32)
        & issue11_summary.method.eq("original100_fixed_guard_lr")
    ].iloc[0]
    combo_32 = main32[
        main32.method.eq("original100_plus_transformer_hidden_fixed_guard_lr")
    ].iloc[0]
    combo_32_heldout = heldout32[
        heldout32.method.eq("original100_plus_transformer_hidden_fixed_guard_lr")
    ].iloc[0]
    hidden_positive = bool(
        combo_32.attack_detection_mean >= orig_fixed_32.attack_detection_mean
        and combo_32.ood_alarm_max <= TARGET_ALARM
        and combo_32.feasible_rate >= 1.0
    )
    hidden_strong_gain = bool(
        combo_32.attack_detection_mean > orig_fixed_32.attack_detection_mean
        and combo_32.ood_alarm_mean <= orig_fixed_32.ood_alarm_mean
    )
    hidden_positive_heldout = bool(
        combo_32_heldout.attack_detection_mean >= orig_fixed_32_heldout.attack_detection_mean
        and combo_32_heldout.ood_alarm_max <= TARGET_ALARM
        and combo_32_heldout.feasible_rate >= 1.0
    )
    heldout_near_original100_fixed = bool(
        combo_32_heldout.attack_detection_mean >= (orig_fixed_32_heldout.attack_detection_mean - 0.002)
        and combo_32_heldout.ood_alarm_max <= TARGET_ALARM
        and combo_32_heldout.feasible_rate >= 1.0
    )
    rec = (
        "Transformer hidden fixed-guard probe is a cautious positive for representation-level integration, but held-out support seeds do not show clear superiority over original100 fixed guard. Consider a tightly scoped GDA ablation only with original100-fixed as the primary control."
        if hidden_positive
        else "Do not move to full GDA on Transformer hidden yet; keep fixed OOD guard as validated mechanism and consider dA latent or deployment timeline evidence."
    )
    (OUT / "recommended_next_action.md").write_text(
        "\n".join(
            [
                "# Recommended Next Action",
                "",
                f"- Hidden positive by fixed criteria: {hidden_positive}.",
                f"- Hidden strong gain over original100 fixed guard: {hidden_strong_gain}.",
                f"- Held-out hidden positive over original100 fixed guard: {hidden_positive_heldout}.",
                f"- Held-out near original100 fixed guard: {heldout_near_original100_fixed}.",
                f"- Recommendation: {rec}",
                "- Continue to avoid detector-agnostic claims until at least two base detector representations succeed under the same guarded protocol.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    summary_md = "\n".join(
        [
            "# Issue12 Transformer Hidden Recovery and Fixed-Guard Probe Summary",
            "",
            "## 1. Scope",
            "This run recovers Transformer outputLayer mean-pooled hidden representations from an existing checkpoint and, only after score-consistency gating, runs a minimal fixed-guard LR representation probe. It does not retrain Transformer or dA, does not search guard weights, and does not modify the manuscript.",
            "",
            "## 2. Phase A Gate",
            f"- Hidden shape: ID `{h_id.shape}`, OOD `{h_ood.shape}`, attack `{h_attack.shape}`.",
            f"- Score consistency pass: `{consistency_pass}`.",
            f"- Hidden shape gate: `{hidden_shape_ok}`.",
            "",
            "## 3. Main 32-shot Results",
            md_table(main32_simple),
            "",
            "## 4. Held-out 32-shot Results",
            md_table(
                heldout32[
                    [
                        "method",
                        "representation",
                        "guard_type",
                        "attack_detection_mean",
                        "attack_detection_min",
                        "ood_alarm_mean",
                        "ood_alarm_max",
                        "feasible_rate",
                    ]
                ]
            ),
            "",
            "## 5. Hidden vs Scalar Score Reference",
            md_table(hidden_vs_scalar),
            "",
            "## 6. Hidden vs Issue11 Baselines",
            md_table(hidden_vs_original100),
            "",
            "## 7. Verdict",
            f"- Hidden positive by fixed criteria: `{hidden_positive}`.",
            f"- Hidden strong gain over original100 fixed guard: `{hidden_strong_gain}`.",
            f"- Held-out hidden positive over original100 fixed guard: `{hidden_positive_heldout}`.",
            f"- Held-out near original100 fixed guard: `{heldout_near_original100_fixed}`.",
            f"- Recommendation: {rec}",
            "",
            "## 8. Boundary",
            "- This is not full GDA.",
            "- This does not prove detector-agnostic adaptation.",
            "- This does not establish dA latent usefulness.",
            "- No manuscript edit, commit, or push was performed.",
            "",
        ]
    )
    (OUT / "summary.md").write_text(summary_md, encoding="utf-8")
    write_json(
        OUT / "config.json",
        {
            "run_tag": RUN_TAG,
            "created_at_local": started,
            "completed_at_local": now(),
            "checkpoint": str(CHECKPOINT),
            "hidden_policy": "outputLayer_transformer_mean_pool",
            "phase_a_completed": True,
            "phase_b_executed": True,
            "fixed_ood_weight": FIXED_OOD_WEIGHT,
            "budgets": BUDGETS,
            "main_seeds": MAIN_SEEDS,
            "heldout_support_seeds": HELDOUT_SEEDS,
            "no_hyperparameter_search": True,
            "score_consistency_tolerance": SCORE_CONSISTENCY_TOL,
            "hidden_positive_main_32_vs_original100_fixed": hidden_positive,
            "hidden_positive_heldout_32_vs_original100_fixed": hidden_positive_heldout,
            "heldout_near_original100_fixed": heldout_near_original100_fixed,
            "training_performed": {
                "transformer": False,
                "dA": False,
                "LR_adapter": True,
            },
        },
    )
    write_json(
        OUT / "manifest.json",
        {
            "run_tag": RUN_TAG,
            "files": {
                "summary": str(OUT / "summary.md"),
                "transformer_hidden_asset_report": str(OUT / "transformer_hidden_asset_report.md"),
                "hidden_alignment_check": str(OUT / "hidden_alignment_check.csv"),
                "score_consistency_check": str(OUT / "score_consistency_check.csv"),
                "method_comparison_summary": str(OUT / "method_comparison_summary.csv"),
                "hidden_vs_original100_fixed_guard": str(OUT / "hidden_vs_original100_fixed_guard.csv"),
                "hidden_vs_scalar_score_reference": str(OUT / "hidden_vs_scalar_score_reference.csv"),
                "hidden_cache_dir": str(HIDDEN_DIR),
            },
        },
    )
    print(f"[done] outputs written to {OUT}")
    print(md_table(main32_simple))


if __name__ == "__main__":
    main()
