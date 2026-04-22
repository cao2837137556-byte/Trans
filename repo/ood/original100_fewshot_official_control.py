from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

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

import KitNET as kit
import frontend100_negative_recipe_rescoring as resc


DEFAULT_POSITIVE_BUDGETS = "16,32"
DEFAULT_SAMPLE_SEEDS = "42,43,44,45,46"
TARGET_ALARM = 0.01


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
        raise RuntimeError(f"Expected 2D matrix, got {arr.shape} from {path}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


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


def parse_positive_budgets(spec: str, max_count: int) -> List[int]:
    budgets: List[int] = []
    for raw in spec.split(","):
        token = raw.strip().lower()
        if not token:
            continue
        if token in {"all", "full", "full-positive", "full_positive"}:
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


def split_contiguous(indices: Iterable[int], train_frac: float = 0.60, val_frac: float = 0.20) -> Dict[str, np.ndarray]:
    idx = np.asarray(sorted(int(i) for i in indices), dtype=np.int64)
    n = len(idx)
    n_train = int(np.floor(n * train_frac))
    n_val = int(np.floor(n * val_frac))
    if n_train <= 0 or n_val <= 0 or n - n_train - n_val <= 0:
        raise RuntimeError(f"Not enough indices for contiguous split: n={n}")
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


def score_kitnet_checkpoint(checkpoint: Path, x: np.ndarray, label: str, progress_every: int = 10000) -> np.ndarray:
    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(x), dtype=np.float64)
    for i, row in enumerate(x):
        scores[i] = float(model.executeAD(row.astype(np.float64)))
        if progress_every > 0 and (i + 1) % progress_every == 0:
            print(f"[score] {label}: {i + 1}/{len(x)}", flush=True)
    return scores


def _maybe_copy_cache(src_dir: Path | None, src_name: str, dst: Path) -> None:
    if dst.exists() or src_dir is None:
        return
    src = src_dir / src_name
    if src.exists():
        shutil.copy2(src, dst)


def maybe_load_or_score_da(
    out: Path,
    checkpoint: Path,
    id_x: np.ndarray,
    ood_x: np.ndarray,
    attack_x: np.ndarray,
    stage1_attack_scores: Path | None,
    cache_source_dir: Path | None,
) -> Dict[str, np.ndarray]:
    cache_dir = out / "score_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    id_cache = cache_dir / "da_full_id_scores.npy"
    ood_cache = cache_dir / "da_ood_scores.npy"
    attack_cache = cache_dir / "da_attack_scores.npy"

    _maybe_copy_cache(cache_source_dir, id_cache.name, id_cache)
    _maybe_copy_cache(cache_source_dir, ood_cache.name, ood_cache)
    _maybe_copy_cache(cache_source_dir, attack_cache.name, attack_cache)

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

    expected = {"id": len(id_x), "ood": len(ood_x), "attack": len(attack_x)}
    actual = {"id": len(id_scores), "ood": len(ood_scores), "attack": len(attack_scores)}
    if actual != expected:
        raise RuntimeError(f"DA score length mismatch: expected={expected}, actual={actual}")
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

    guarded = guarded_val_threshold(score_id_calib, score_ood_val, target_alarm)
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
    summary = (
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
            auc_max=("roc_auc_attack_high_vs_ood_eval", "max"),
            eval_alarm_mean=("ood_alarm_ratio_eval", "mean"),
            eval_alarm_min=("ood_alarm_ratio_eval", "min"),
            eval_alarm_max=("ood_alarm_ratio_eval", "max"),
            det_mean=("attack_detection_high_purity", "mean"),
            det_min=("attack_detection_high_purity", "min"),
            det_max=("attack_detection_high_purity", "max"),
            feasible_rate=("selection_feasible", "mean"),
        )
        .sort_values(["model_label", "positive_budget", "policy_name"])
    )
    return summary


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
            "train_negative": [0, id_train_end],
            "val_unused_by_threshold": [id_train_end, id_val_end],
            "calibration_threshold_only": [id_val_end, id_calib_end],
            "eval_final_only": [id_calib_end, id_rows],
        },
        "ood": {
            "train_negative": [0, ood_train_end],
            "val_threshold_only": [ood_train_end, ood_val_end],
            "eval_final_only": [ood_val_end, ood_rows],
        },
        "attack_high": {
            "total_high": int(len(high_idx)),
            "train_pool_count": int(len(attack_split["train"])),
            "val_diagnostics_only_count": int(len(attack_split["val"])),
            "eval_final_count": int(len(attack_split["eval"])),
            "train_first_last": [int(attack_split["train"][0]), int(attack_split["train"][-1])],
            "val_first_last": [int(attack_split["val"][0]), int(attack_split["val"][-1])],
            "eval_first_last": [int(attack_split["eval"][0]), int(attack_split["eval"][-1])],
        },
    }


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(
        description="Mainline official original100 few-shot target-aligned logistic control package."
    )
    ap.add_argument("--run-tag", default=f"original100_fewshot_official_control_{today}")
    ap.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
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
    ap.add_argument("--da-cache-source-dir", type=Path, default=None)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    command = "python " + " ".join(sys.argv)
    (out / "command.txt").write_text(command + "\n", encoding="utf-8")

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
    attack_split = split_contiguous(high_idx, args.attack_train_frac, args.attack_val_frac)

    budgets = parse_positive_budgets(args.positive_budgets, len(attack_split["train"]))
    sample_seeds = parse_int_list(args.sample_seeds)

    id_train_end = int(args.id_train_rows)
    id_val_end = id_train_end + int(args.id_val_rows)
    id_calib_end = id_val_end + int(args.id_calibration_rows)
    ood_train_end = int(args.ood_train_rows)
    ood_val_end = ood_train_end + int(args.ood_val_rows)
    if id_calib_end >= len(id_x):
        raise RuntimeError(f"ID split leaves no eval rows: id_calib_end={id_calib_end}, rows={len(id_x)}")
    if ood_val_end >= len(ood_x):
        raise RuntimeError(f"OOD split leaves no eval rows: ood_val_end={ood_val_end}, rows={len(ood_x)}")

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

    id_train_x = id_x[:id_train_end]
    ood_train_x = ood_x[:ood_train_end]
    id_calib_x = id_x[id_val_end:id_calib_end]
    id_eval_x = id_x[id_calib_end:]
    ood_val_x = ood_x[ood_train_end:ood_val_end]
    ood_eval_x = ood_x[ood_val_end:]
    attack_val_x = attack_x[attack_split["val"]]
    attack_eval_x = attack_x[attack_split["eval"]]

    rows: List[Dict] = []
    selected_positive_rows: List[Dict] = []
    for budget in budgets:
        for sample_seed in sample_seeds:
            selected_pos_idx = choose_positive_train_indices(attack_split["train"], budget, sample_seed)
            selected_positive_rows.append(
                {
                    "positive_budget": int(budget),
                    "positive_sample_seed": int(sample_seed),
                    "positive_train_count": int(len(selected_pos_idx)),
                    "positive_train_first_row": int(selected_pos_idx[0]),
                    "positive_train_last_row": int(selected_pos_idx[-1]),
                }
            )
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
        cache_source_dir=args.da_cache_source_dir,
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
    focus = summary[
        summary["model_label"].eq("da_unsupervised_score_seed42")
        | (
            summary["model_label"].eq("original100_fewshot_logistic")
            & summary["positive_budget"].isin([16, 32])
        )
    ].copy()

    results_path = out / "original100_fewshot_official_control_results.csv"
    summary_path = out / "original100_fewshot_official_control_summary.csv"
    focus_path = out / "original100_fewshot_official_control_focus.csv"
    selected_positive_path = out / "selected_positive_samples.csv"
    results.to_csv(results_path, index=False)
    results.to_csv(out / "results.csv", index=False)
    summary.to_csv(summary_path, index=False)
    focus.to_csv(focus_path, index=False)
    pd.DataFrame(selected_positive_rows).to_csv(selected_positive_path, index=False)

    diagnostics = {
        "matrix_shapes": {
            "id": list(id_x.shape),
            "ood_benign": list(ood_x.shape),
            "attack": list(attack_x.shape),
        },
        "nonfinite_after_load": {
            "id": int(np.size(id_x) - np.isfinite(id_x).sum()),
            "ood_benign": int(np.size(ood_x) - np.isfinite(ood_x).sum()),
            "attack": int(np.size(attack_x) - np.isfinite(attack_x).sum()),
        },
        "label_definition": {
            "negative_train": "ID benign train rows + OOD benign train rows",
            "positive_train": "seeded few-shot samples from stage2 high-purity attack train split",
            "da_reference": "unsupervised ID-only dA; no attack labels",
        },
        "fairness": {
            "final_ood_eval_used_for_threshold_selection": False,
            "positive_sampling_multi_seed": True,
            "threshold_policies": ["fixed_id_calib_q99", "guarded_id_calib_and_ood_val_target1pct"],
        },
        "split_info": split_info,
    }
    write_json(out / "diagnostics.json", diagnostics)

    config = {
        "stage": "original100_fewshot_official_control",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "command": command,
        "source_root": str(source),
        "input_mode": "original_frontend_flat100",
        "protocol_source": "frontend-f2 v7.2/v7.3 few-shot target-aligned protocol, ported to original100 representation",
        "task_type": "few-shot supervised target-aligned detector; not unsupervised anomaly scoring",
        "model": {
            "type": "LogisticRegression",
            "penalty": "l2",
            "solver": "liblinear",
            "class_weight": "balanced",
            "C": float(args.C),
            "max_iter": 2000,
            "score": "decision_function",
        },
        "positive_budgets": budgets,
        "positive_sample_seeds": sample_seeds,
        "calibration_target": float(args.calibration_target),
        "da_checkpoint": str(da_checkpoint),
        "da_cache_source_dir": None if args.da_cache_source_dir is None else str(args.da_cache_source_dir),
        "stage2_manifest": str(stage2 / "attack_manifest_stage2.json"),
        "split_info": split_info,
        "outputs": {
            "results": str(results_path),
            "summary": str(summary_path),
            "focus": str(focus_path),
            "diagnostics": str(out / "diagnostics.json"),
            "selected_positive_samples": str(selected_positive_path),
            "summary_md": str(out / "summary.md"),
        },
    }
    write_json(out / "config.json", config)
    write_json(out / "run_spec.json", config)
    write_json(out / "official_control_manifest.json", config)

    note = "\n".join(
        [
            "# Original100 Few-Shot Official Control",
            "",
            "- Purpose: establish the mainline official control group by porting the frontend-f2 v7.2/v7.3 few-shot target-aligned protocol to the original100 representation.",
            "- Task type: few-shot supervised target-aligned detector, not unsupervised anomaly scoring.",
            "- Logistic control: L2 LogisticRegression, balanced class weights, C=1.0.",
            "- Labels: negatives = ID benign + OOD benign; positives = stage2 high-purity attack.",
            "- Fairness: final OOD eval is never used for threshold selection; positive sampling runs multiple seeds.",
            "- Operating points: `fixed_id_calib_q99` and `guarded_id_calib_and_ood_val_target1pct`.",
            "- Boundary: `original100_fewshot_logistic` is the official control; `da_unsupervised_score_seed42` is only a reference baseline.",
            "",
            "## Focus Summary",
            md_table(focus),
            "",
            "## Full Summary",
            md_table(summary),
        ]
    ) + "\n"
    (out / "summary.md").write_text(note, encoding="utf-8")
    (out / "stdout.log").write_text("[done] original100 few-shot official control package generated\n", encoding="utf-8")
    (out / "stderr.log").write_text("", encoding="utf-8")

    print(f"[done] original100 few-shot official control output: {out}", flush=True)
    print(md_table(focus), flush=True)


if __name__ == "__main__":
    main()
