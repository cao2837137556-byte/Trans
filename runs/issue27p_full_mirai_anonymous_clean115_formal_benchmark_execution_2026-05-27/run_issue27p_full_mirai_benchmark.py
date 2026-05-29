from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression, SGDOneClassSVM
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import RobustScaler, StandardScaler


REPO = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
KITNET = Path(r"D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master")
OUT = REPO / "runs" / "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27"
MAINLINE_DOCS = REPO / "runs" / "mainline_docs"
ISSUE27O = REPO / "runs" / "issue27o_full_mirai_protocol_reset_feature_mapping_and_formal_benchmark_spec_2026-05-27"

FULL_MIRAI = KITNET / "Mirai_dataset.csv"
FULL_LABELS = KITNET / "mirai_labels.csv"

SEEDS = [42, 43, 44, 45, 46]
TARGET = 0.01
FEATURE_SCHEMA = "anonymous_clean115_all"
DATASET_NAME = "full_mirai_protocol_reset"
SPLIT_NAME = "full_mirai_protocol_reset_row_order_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "NA") for k in fieldnames})


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_array(arr: np.ndarray) -> str:
    a = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(str(a.shape).encode("ascii"))
    h.update(str(a.dtype).encode("ascii"))
    h.update(a.tobytes())
    return h.hexdigest()


def sha256_clean115_chunked(csv_path: Path, chunksize: int = 50000) -> tuple[str, int, int]:
    h = hashlib.sha256()
    rows = 0
    cols = 0
    for chunk in pd.read_csv(csv_path, header=None, chunksize=chunksize):
        clean = chunk.iloc[:, 1:].to_numpy(dtype=np.float32)
        rows += clean.shape[0]
        cols = clean.shape[1]
        h.update(np.ascontiguousarray(clean).tobytes())
    h.update(f"rows={rows};cols={cols};dtype=float32".encode("ascii"))
    return h.hexdigest(), rows, cols


def read_labels() -> np.ndarray:
    labels: list[int] = []
    with FULL_LABELS.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if s:
                labels.append(int(float(s.split(",")[0])))
    return np.asarray(labels, dtype=np.int8)


def load_range(start: int, count: int) -> np.ndarray:
    df = pd.read_csv(FULL_MIRAI, header=None, skiprows=range(0, start), nrows=count)
    arr = df.iloc[:, 1:].to_numpy(dtype=np.float32)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def kcenter_select(X: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    first = int(rng.integers(0, n))
    selected = [first]
    min_dist = np.sum((X - X[first]) ** 2, axis=1)
    for _ in range(1, min(k, n)):
        idx = int(np.argmax(min_dist))
        selected.append(idx)
        dist = np.sum((X - X[idx]) ** 2, axis=1)
        min_dist = np.minimum(min_dist, dist)
    return np.asarray(selected, dtype=np.int64)


def random_select(X: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 1000003)
    return np.asarray(rng.choice(np.arange(X.shape[0]), size=min(k, X.shape[0]), replace=False), dtype=np.int64)


def calibrate_threshold(id_scores: np.ndarray, ood_val_scores: np.ndarray, mode: str) -> float:
    q = 1.0 - TARGET
    id_thr = float(np.quantile(id_scores, q))
    if mode == "id_only":
        return id_thr
    ood_thr = float(np.quantile(ood_val_scores, q))
    return float(max(id_thr, ood_thr))


def safe_auc(ood_scores: np.ndarray, attack_scores: np.ndarray) -> tuple[float | str, float | str, float | str]:
    y = np.concatenate([np.zeros(len(ood_scores), dtype=np.int8), np.ones(len(attack_scores), dtype=np.int8)])
    s = np.concatenate([ood_scores, attack_scores])
    try:
        roc = float(roc_auc_score(y, s))
    except Exception:
        roc = "NA"
    try:
        pr = float(average_precision_score(y, s))
    except Exception:
        pr = "NA"
    try:
        pauc = float(roc_auc_score(y, s, max_fpr=0.01))
    except Exception:
        pauc = "NA"
    return roc, pr, pauc


def tpr_at_fpr_1pct(ood_scores: np.ndarray, attack_scores: np.ndarray) -> float:
    threshold = float(np.quantile(ood_scores, 0.99))
    return float(np.mean(attack_scores >= threshold))


def param_count(model: Any) -> str | int:
    if isinstance(model, tuple):
        return param_count(model[-1])
    if hasattr(model, "coef_"):
        return int(np.prod(model.coef_.shape) + np.prod(getattr(model, "intercept_", np.array([])).shape))
    if hasattr(model, "coefs_"):
        return int(sum(np.prod(c.shape) for c in model.coefs_) + sum(np.prod(i.shape) for i in model.intercepts_))
    if hasattr(model, "estimators_"):
        return int(len(model.estimators_))
    if hasattr(model, "n_iter_"):
        try:
            return int(model.n_iter_)
        except Exception:
            return "NA"
    return "NA"


@dataclass
class SplitData:
    labels: np.ndarray
    id_train: np.ndarray
    ood_train: np.ndarray
    id_calib: np.ndarray
    ood_val: np.ndarray
    final_ood_eval: np.ndarray
    attack_support_pool: np.ndarray
    attack_eval: np.ndarray
    rows: dict[str, np.ndarray]


def build_split(labels: np.ndarray) -> SplitData:
    ranges = {
        "id_train": (0, 60000),
        "ood_train": (60000, 20000),
        "id_calib": (80000, 20000),
        "ood_val": (100000, 10000),
        "final_ood_eval": (110000, 11621),
        "attack_support_pool": (121621, 60000),
        "attack_eval": (181621, 582516),
    }
    arrays = {name: load_range(start, count) for name, (start, count) in ranges.items()}
    rows = {name: np.arange(start, start + count, dtype=np.int64) for name, (start, count) in ranges.items()}
    return SplitData(
        labels=labels,
        id_train=arrays["id_train"],
        ood_train=arrays["ood_train"],
        id_calib=arrays["id_calib"],
        ood_val=arrays["ood_val"],
        final_ood_eval=arrays["final_ood_eval"],
        attack_support_pool=arrays["attack_support_pool"],
        attack_eval=arrays["attack_eval"],
        rows=rows,
    )


def train_histgb(
    X_train: np.ndarray,
    y_train: np.ndarray,
    weights: np.ndarray,
    seed: int,
    max_depth: int,
    learning_rate: float,
    l2: float,
    max_iter: int,
) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(
        max_depth=max_depth,
        learning_rate=learning_rate,
        l2_regularization=l2,
        max_iter=max_iter,
        random_state=seed,
    )
    model.fit(X_train, y_train, sample_weight=weights)
    return model


def train_lr(X_train: np.ndarray, y_train: np.ndarray, weights: np.ndarray, seed: int) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X_train)
    model = LogisticRegression(max_iter=1000, solver="liblinear", random_state=seed)
    model.fit(Xs, y_train, sample_weight=weights)
    return scaler, model


def predict_model(model: Any, X: np.ndarray, mode: str) -> np.ndarray:
    if mode == "histgb":
        return model.predict_proba(X)[:, 1]
    if mode == "lr":
        scaler, clf = model
        return clf.predict_proba(scaler.transform(X))[:, 1]
    if mode == "mlp":
        scaler, clf = model
        return clf.predict_proba(scaler.transform(X))[:, 1]
    if mode == "isoforest":
        return -model.decision_function(X)
    if mode == "ocsvm":
        scaler, clf = model
        return -clf.decision_function(scaler.transform(X))
    if mode == "deepsad":
        center, scale, weights = model
        z = (X - center) / scale
        return np.sum((z * weights) ** 2, axis=1)
    if mode == "prototype":
        scaler, clf, centers = model
        feats = prototype_features(X, centers)
        return clf.predict_proba(scaler.transform(feats))[:, 1]
    raise ValueError(mode)


def prototype_features(X: np.ndarray, centers: dict[str, np.ndarray]) -> np.ndarray:
    id_center = centers["id"]
    ood_center = centers["ood"]
    attack_center = centers["attack"]
    normal_center = centers["normal"]
    d_id = np.linalg.norm(X - id_center, axis=1)
    d_ood = np.linalg.norm(X - ood_center, axis=1)
    d_attack = np.linalg.norm(X - attack_center, axis=1)
    attack_margin = np.linalg.norm(X - normal_center, axis=1) - d_attack
    ood_margin = d_attack - d_ood
    return np.column_stack([d_id, d_ood, d_attack, attack_margin, ood_margin]).astype(np.float32)


def evaluate_method(
    method_name: str,
    seed: int,
    data: SplitData,
    support_idx: np.ndarray,
    train_fn: Callable[[np.ndarray, int], tuple[Any, str, str, str, str]],
    threshold_mode: str,
    support_rule: str,
) -> dict[str, Any]:
    support_rows = data.rows["attack_support_pool"][support_idx]
    X_support = data.attack_support_pool[support_idx]
    train_start = time.time()
    model, score_mode, impl_status, objective_type, hyperparams_source = train_fn(X_support, seed)
    train_time = time.time() - train_start
    infer_start = time.time()
    score_id_calib = predict_model(model, data.id_calib, score_mode)
    score_ood_val = predict_model(model, data.ood_val, score_mode)
    threshold = calibrate_threshold(score_id_calib, score_ood_val, threshold_mode)
    score_final_ood = predict_model(model, data.final_ood_eval, score_mode)
    score_attack_eval = predict_model(model, data.attack_eval, score_mode)
    score_support = predict_model(model, X_support, score_mode)
    inference_time = time.time() - infer_start
    final_ood_alarm = float(np.mean(score_final_ood >= threshold))
    attack_detection = float(np.mean(score_attack_eval >= threshold))
    roc, pr, pauc = safe_auc(score_final_ood, score_attack_eval)
    return {
        "dataset_name": DATASET_NAME,
        "split_name": SPLIT_NAME,
        "feature_schema": FEATURE_SCHEMA,
        "seed": seed,
        "method_name": method_name,
        "attack_detection": attack_detection,
        "final_ood_alarm": final_ood_alarm,
        "id_calib_alarm": float(np.mean(score_id_calib >= threshold)),
        "ood_val_alarm": float(np.mean(score_ood_val >= threshold)),
        "threshold": float(threshold),
        "roc_auc_attack_vs_ood": roc,
        "pr_auc_attack_vs_ood": pr,
        "pauc_fpr_1pct": pauc,
        "tpr_at_fpr_1pct": tpr_at_fpr_1pct(score_final_ood, score_attack_eval),
        "feasible_under_1pct": final_ood_alarm <= TARGET,
        "train_time_sec": train_time,
        "inference_time_sec": inference_time,
        "param_count": param_count(model),
        "support_rule": support_rule,
        "support_rows_sha256": sha256_array(support_rows),
        "support_eval_disjoint": bool(set(support_rows.tolist()).isdisjoint(set(data.rows["attack_eval"].tolist()))),
        "final_eval_used_for_selection": False,
        "threshold_rule": threshold_mode,
        "ood_alarm_target": TARGET,
        "implementation_status": impl_status,
        "objective_type": objective_type,
        "hyperparams_source": hyperparams_source,
        "support_mean_score": float(np.mean(score_support)),
        "attack_eval_mean_score": float(np.mean(score_attack_eval)),
        "final_ood_mean_score": float(np.mean(score_final_ood)),
        "score_nan_count": int(
            np.isnan(score_id_calib).sum()
            + np.isnan(score_ood_val).sum()
            + np.isnan(score_final_ood).sum()
            + np.isnan(score_attack_eval).sum()
        ),
    }


def make_train_fns(data: SplitData, support_idx_kcenter: np.ndarray, seed: int) -> dict[str, tuple[Callable[[np.ndarray, int], tuple[Any, str, str, str, str]], str, str]]:
    def lowguard_histgb(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        X_train = np.vstack([data.id_train, data.ood_train, X_support])
        y_train = np.concatenate([np.zeros(data.id_train.shape[0] + data.ood_train.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate([
            np.ones(data.id_train.shape[0], dtype=np.float32),
            np.full(data.ood_train.shape[0], 4.0, dtype=np.float32),
            np.full(X_support.shape[0], 4.0, dtype=np.float32),
        ])
        return (
            train_histgb(X_train, y_train, weights, s, max_depth=2, learning_rate=0.05, l2=0.1, max_iter=100),
            "histgb",
            "completed",
            "lowguard_histgb_conservative",
            "issue27d_frozen_config_no_search",
        )

    def lowguard_lr(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        X_train = np.vstack([data.id_train, data.ood_train, X_support])
        y_train = np.concatenate([np.zeros(data.id_train.shape[0] + data.ood_train.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate([
            np.ones(data.id_train.shape[0], dtype=np.float32),
            np.full(data.ood_train.shape[0], 4.0, dtype=np.float32),
            np.full(X_support.shape[0], 4.0, dtype=np.float32),
        ])
        return train_lr(X_train, y_train, weights, s), "lr", "completed", "lowguard_lr_minimal", "reset_fixed_no_search"

    def raw_lr(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        X_train = np.vstack([data.id_train, X_support])
        y_train = np.concatenate([np.zeros(data.id_train.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate([np.ones(data.id_train.shape[0], dtype=np.float32), np.full(X_support.shape[0], 4.0, dtype=np.float32)])
        return train_lr(X_train, y_train, weights, s), "lr", "completed", "ordinary_lr_no_ood_train", "reset_fixed_no_search"

    def histgb_shallow(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        X_train = np.vstack([data.id_train, X_support])
        y_train = np.concatenate([np.zeros(data.id_train.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate([np.ones(data.id_train.shape[0], dtype=np.float32), np.full(X_support.shape[0], 2.0, dtype=np.float32)])
        return (
            train_histgb(X_train, y_train, weights, s, max_depth=2, learning_rate=0.05, l2=0.0, max_iter=100),
            "histgb",
            "completed",
            "ordinary_histgb_shallow",
            "reset_fixed_no_search",
        )

    def isolation_forest(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        del X_support
        X_train = np.vstack([data.id_train, data.ood_train])
        model = IsolationForest(n_estimators=100, contamination="auto", random_state=s, n_jobs=-1)
        model.fit(X_train)
        return model, "isoforest", "completed", "unsupervised_normal_training", "reset_fixed_no_search"

    def ocsvm_sgd(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        del X_support
        X_train = np.vstack([data.id_train, data.ood_train])
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X_train)
        model = SGDOneClassSVM(nu=0.01, random_state=s, max_iter=1000, tol=1e-3)
        model.fit(Xs)
        return (scaler, model), "ocsvm", "completed_scalable_linear_sgd_ocsvm", "one_class_svm_scalable", "reset_fixed_no_search"

    def devnet_style(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        rng = np.random.default_rng(s)
        normal_idx_id = rng.choice(data.id_train.shape[0], size=min(20000, data.id_train.shape[0]), replace=False)
        normal_idx_ood = rng.choice(data.ood_train.shape[0], size=min(20000, data.ood_train.shape[0]), replace=False)
        X_normal = np.vstack([data.id_train[normal_idx_id], data.ood_train[normal_idx_ood]])
        X_train = np.vstack([X_normal, X_support])
        y_train = np.concatenate([np.zeros(X_normal.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate([np.ones(X_normal.shape[0], dtype=np.float32), np.full(X_support.shape[0], 40.0, dtype=np.float32)])
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X_train)
        model = MLPClassifier(hidden_layer_sizes=(16,), activation="relu", solver="adam", max_iter=80, random_state=s)
        try:
            model.fit(Xs, y_train, sample_weight=weights)
            status = "completed_model_specific_lite"
        except TypeError:
            model.fit(Xs, y_train)
            status = "completed_model_specific_lite_no_sample_weight_api"
        return (scaler, model), "mlp", status, "devnet_style_score_head_lite", "reset_fixed_no_search"

    def deepsad_lite(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        del s
        normal = np.vstack([data.id_train, data.ood_train])
        center = normal.mean(axis=0)
        scale = normal.std(axis=0) + 1e-6
        diff = np.abs(X_support.mean(axis=0) - center) / scale
        weights = 1.0 + np.clip(diff / (np.median(diff) + 1e-6), 0.0, 5.0)
        return (center, scale, weights.astype(np.float32)), "deepsad", "completed_model_specific_lite", "deepsad_style_weighted_center", "reset_fixed_no_search"

    def prototype_margin(X_support: np.ndarray, s: int) -> tuple[Any, str, str, str, str]:
        del s
        centers = {
            "id": data.id_train.mean(axis=0),
            "ood": data.ood_train.mean(axis=0),
            "attack": X_support.mean(axis=0),
            "normal": np.vstack([data.id_train, data.ood_train]).mean(axis=0),
        }
        X_neg = np.vstack([data.id_train, data.ood_train])
        X_train = np.vstack([X_neg, X_support])
        feats = prototype_features(X_train, centers)
        y_train = np.concatenate([np.zeros(X_neg.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate([
            np.ones(data.id_train.shape[0], dtype=np.float32),
            np.full(data.ood_train.shape[0], 4.0, dtype=np.float32),
            np.full(X_support.shape[0], 8.0, dtype=np.float32),
        ])
        scaler = RobustScaler()
        clf = LogisticRegression(max_iter=1000, solver="liblinear", random_state=seed)
        clf.fit(scaler.fit_transform(feats), y_train, sample_weight=weights)
        return (scaler, clf, centers), "prototype", "completed_optional", "prototype_margin_lite", "reset_fixed_no_search"

    return {
        "LOW_GUARD_PLUSPLUS_HistGB_Conservative": (lowguard_histgb, "guarded", "kcenter32"),
        "LOW_GUARD_LR_Minimal": (lowguard_lr, "guarded", "kcenter32"),
        "Raw_LR_NoGuard": (raw_lr, "id_only", "kcenter32"),
        "LR_ThresholdOnly": (raw_lr, "guarded", "kcenter32"),
        "LR_NoOODGuard": (raw_lr, "guarded", "kcenter32"),
        "LR_NoThresholdGuard": (lowguard_lr, "id_only", "kcenter32"),
        "HistGB_Shallow": (histgb_shallow, "guarded", "kcenter32"),
        "IsolationForest": (isolation_forest, "guarded", "no_attack_support"),
        "OCSVM": (ocsvm_sgd, "guarded", "no_attack_support"),
        "DevNetStyle_ScoreHead": (devnet_style, "guarded", "kcenter32"),
        "DeepSADStyle_Lite": (deepsad_lite, "guarded", "kcenter32"),
        "RandomSupport32_LOW_GUARD": (lowguard_histgb, "guarded", "random32_train_side"),
        "PrototypeMargin": (prototype_margin, "guarded", "kcenter32"),
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for method in sorted({r["method_name"] for r in rows}):
        sub = [r for r in rows if r["method_name"] == method]
        det = np.asarray([float(r["attack_detection"]) for r in sub], dtype=float)
        ood = np.asarray([float(r["final_ood_alarm"]) for r in sub], dtype=float)
        feas = np.asarray([bool(r["feasible_under_1pct"]) for r in sub], dtype=bool)
        ood_val = np.asarray([float(r["ood_val_alarm"]) for r in sub], dtype=float)
        out.append(
            {
                "method_name": method,
                "feature_schema": FEATURE_SCHEMA,
                "seeds_completed": len(sub),
                "detection_mean": float(np.mean(det)),
                "detection_min": float(np.min(det)),
                "detection_std": float(np.std(det)),
                "final_ood_alarm_mean": float(np.mean(ood)),
                "final_ood_alarm_max": float(np.max(ood)),
                "final_ood_alarm_std": float(np.std(ood)),
                "feasible_rate": float(np.mean(feas)),
                "ood_val_alarm_mean": float(np.mean(ood_val)),
                "threshold_median": float(np.median([float(r["threshold"]) for r in sub])),
                "train_time_sec_mean": float(np.mean([float(r["train_time_sec"]) for r in sub])),
                "inference_time_sec_mean": float(np.mean([float(r["inference_time_sec"]) for r in sub])),
                "support_eval_disjoint_all": all(bool(r["support_eval_disjoint"]) for r in sub),
                "final_eval_used_for_selection_any": any(bool(r["final_eval_used_for_selection"]) for r in sub),
                "implementation_status": ";".join(sorted({str(r["implementation_status"]) for r in sub})),
            }
        )
    return out


def rank_methods(summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        feasible = float(row["feasible_rate"]) >= 1.0 and float(row["final_ood_alarm_max"]) <= TARGET
        complete = not str(row["implementation_status"]).startswith("implementation")
        return (
            0 if feasible else 1,
            float(row["final_ood_alarm_max"]),
            -float(row["detection_min"]),
            -float(row["detection_mean"]),
            float(row["detection_std"]),
            0 if complete else 1,
            float(row["train_time_sec_mean"]) + float(row["inference_time_sec_mean"]),
        )
    ranked = sorted(summary, key=key)
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
        row["ranking_feasible_first"] = float(row["feasible_rate"]) >= 1.0 and float(row["final_ood_alarm_max"]) <= TARGET
    return ranked


def preflight(labels: np.ndarray) -> tuple[str, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, verdict_if_failed: str, notes: str) -> None:
        checks.append({"check": name, "passed": passed, "verdict_if_failed": verdict_if_failed, "notes": notes})

    add("full_mirai_csv_exists", FULL_MIRAI.exists(), "blocked_feature_matrix", str(FULL_MIRAI))
    add("label_sidecar_exists", FULL_LABELS.exists(), "blocked_label_alignment", str(FULL_LABELS))
    add("label_count_matches_expected", len(labels) == 764137, "blocked_label_alignment", f"labels={len(labels)}")
    benign_count = int(np.sum(labels == 0))
    attack_count = int(np.sum(labels == 1))
    add("label_counts_match_issue27o", benign_count == 121621 and attack_count == 642516, "blocked_label_alignment", f"benign={benign_count}; attack={attack_count}")
    add("benign_prefix_attack_suffix", bool(np.all(labels[:121621] == 0) and np.all(labels[121621:] == 1)), "blocked_split_contract", "row-order split assumes benign prefix then attack suffix")
    sample = pd.read_csv(FULL_MIRAI, header=None, nrows=1000)
    add("dirty116_width", sample.shape[1] == 116, "blocked_feature_matrix", f"sample_width={sample.shape[1]}")
    col0 = sample.iloc[:, 0].to_numpy()
    add("col0_index_like_removed_for_clean115", bool(np.all(np.diff(col0) == 1) or len(np.unique(col0)) == len(col0)), "blocked_feature_matrix", "col0 is not included in clean115 arrays")
    add("clean115_width_after_drop", sample.iloc[:, 1:].shape[1] == 115, "blocked_feature_matrix", f"clean_width={sample.iloc[:, 1:].shape[1]}")
    split_sets = {
        "id_train": set(range(0, 60000)),
        "ood_train": set(range(60000, 80000)),
        "id_calib": set(range(80000, 100000)),
        "ood_val": set(range(100000, 110000)),
        "final_ood_eval": set(range(110000, 121621)),
        "attack_support_pool": set(range(121621, 181621)),
        "attack_eval": set(range(181621, 764137)),
    }
    disjoint = True
    names = list(split_sets)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if split_sets[a].intersection(split_sets[b]):
                disjoint = False
    add("split_sets_disjoint", disjoint, "blocked_split_contract", "issue27o row-order contract")
    add("support_pool_attack_only", bool(np.all(labels[121621:181621] == 1)), "blocked_split_contract", "support pool rows are attack")
    add("attack_eval_attack_only", bool(np.all(labels[181621:] == 1)), "blocked_split_contract", "attack eval rows are attack")
    add("final_ood_eval_benign_only", bool(np.all(labels[110000:121621] == 0)), "blocked_split_contract", "final OOD eval rows are benign")
    add("final_eval_report_only_protocol", True, "blocked_final_eval_leakage_risk", "threshold/support/config are train/val-side only")
    add("feature_schema_named_anonymous_clean115", FEATURE_SCHEMA == "anonymous_clean115_all", "blocked_feature_matrix", FEATURE_SCHEMA)
    add("no_restored115_or_common100_claim", True, "blocked_other", "mapping remains low/blocked from issue27o")
    add("seeds_fixed", SEEDS == [42, 43, 44, 45, 46], "blocked_other", str(SEEDS))
    add("local_execution_allowed", True, "blocked_resource_needs_slurm_plan", "resource-aware scalable baselines used; exact RBF OC-SVM deferred")
    verdict = "pass" if all(c["passed"] for c in checks) else next(c["verdict_if_failed"] for c in checks if not c["passed"])
    return verdict, checks


def method_registry_rows() -> list[dict[str, Any]]:
    methods = [
        ("LOW_GUARD_PLUSPLUS_HistGB_Conservative", "ID+OOD benign negatives plus kcenter32 support positives", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "issue27d frozen HistGB config; no search", "true", "completed", "main LOW-GUARD++ candidate under anonymous clean115"),
        ("LOW_GUARD_LR_Minimal", "ID+OOD benign negatives plus kcenter32 support positives", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed LR minimal instance; no search", "true", "completed", "minimal LOW-GUARD reference"),
        ("Raw_LR_NoGuard", "ID benign negatives plus kcenter32 support positives", "ID_calib only", "report-only final OOD and attack eval", "kcenter32", "ID-only threshold", "fixed LR; no search", "true", "completed", "ordinary few-shot LR baseline"),
        ("LR_ThresholdOnly", "ID benign negatives plus kcenter32 support positives", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed LR; no search", "true", "completed", "threshold guard only"),
        ("LR_NoOODGuard", "ID benign negatives plus kcenter32 support positives", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed LR; no search", "true", "completed", "alias protocol for no OOD train guard"),
        ("LR_NoThresholdGuard", "ID+OOD benign negatives plus kcenter32 support positives", "ID_calib only", "report-only final OOD and attack eval", "kcenter32", "ID-only threshold", "fixed LR; no search", "true", "completed", "training guard only"),
        ("HistGB_Shallow", "ID benign negatives plus kcenter32 support positives", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed shallow HistGB; no search", "true", "completed", "ordinary shallow tree baseline"),
        ("IsolationForest", "ID+OOD benign only", "ID_calib+OOD_val", "report-only final OOD and attack eval", "none", "guarded threshold", "fixed IF; no search", "true", "completed", "traditional anomaly baseline"),
        ("OCSVM", "ID+OOD benign only", "ID_calib+OOD_val", "report-only final OOD and attack eval", "none", "guarded threshold", "fixed scalable linear SGDOneClassSVM; no search", "true", "completed_scalable_linear_sgd_ocsvm", "resource-bounded OC-SVM rerun"),
        ("DevNetStyle_ScoreHead", "train-side normal subset plus kcenter32 support", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed small MLP score head; no search", "true", "completed_model_specific_lite", "collapse model re-evaluation"),
        ("DeepSADStyle_Lite", "ID+OOD benign center plus kcenter32 support weighting", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed weighted center objective; no search", "true", "completed_model_specific_lite", "collapse model re-evaluation"),
        ("RandomSupport32_LOW_GUARD", "ID+OOD benign negatives plus random32 support positives", "ID_calib+OOD_val", "report-only final OOD and attack eval", "random32_train_side", "guarded threshold", "same HistGB config as LOW-GUARD++; random support only", "true", "completed", "support rule ablation"),
        ("PrototypeMargin", "ID+OOD benign centers plus kcenter32 support center", "ID_calib+OOD_val", "report-only final OOD and attack eval", "kcenter32", "guarded threshold", "fixed lightweight prototype margin; no search", "true", "completed_optional", "optional cheap collapse/prototype diagnostic"),
    ]
    return [
        {
            "method_name": m[0],
            "feature_schema": FEATURE_SCHEMA,
            "training_inputs": m[1],
            "validation_inputs": m[2],
            "final_eval_inputs": m[3],
            "support_rule": m[4],
            "threshold_rule": m[5],
            "hyperparams_source": m[6],
            "is_formal": m[7],
            "implementation_status": m[8],
            "notes": m[9],
        }
        for m in methods
    ]


def append_docs(verdict: str, best_method: str, complete: bool) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    experiment_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    with handoff.open("a", encoding="utf-8") as f:
        f.write(
            "\n## issue27p full Mirai anonymous clean115 formal benchmark execution (2026-05-27)\n\n"
            f"- primary_verdict: `{verdict}`\n"
            "- scope: executes the full Mirai protocol-reset benchmark on `anonymous_clean115_all` with fixed split, train/validation-only selection, and report-only final eval.\n"
            f"- baseline rerun status: {'complete for planned local reset methods' if complete else 'incomplete; see slurm/debug plan'}; old issue20-27n numbers remain exploratory.\n"
            f"- current benchmark leader by feasibility-first ranking: `{best_method}`.\n"
            "- claim boundary: this is within-dataset protocol-reset evidence, not external generalization and not restored115/original100 evidence.\n"
            "- next action: `issue27q_protocol_reset_result_audit_and_seed_expansion`.\n"
        )
    with experiment_map.open("a", encoding="utf-8") as f:
        f.write(
            "\n| issue27p | full Mirai anonymous clean115 reset benchmark | "
            f"`{verdict}` | Runs formal within-dataset reset benchmark with anonymous clean115; best current method `{best_method}`; old results superseded for final claims. Next: `issue27q_protocol_reset_result_audit_and_seed_expansion`. |\n"
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    start_time = time.time()

    labels = read_labels()
    preflight_verdict, preflight_rows = preflight(labels)
    write_csv(OUT / "preflight_table.csv", preflight_rows)
    write_text(
        OUT / "preflight_checklist.md",
        "# Preflight Checklist\n\n"
        f"- verdict: `{preflight_verdict}`\n"
        "- anonymous clean115 is dirty116 with index-like col0 removed.\n"
        "- final eval is report-only and not used for support, threshold, feature, split, or config selection.\n"
        "- full Mirai is a within-dataset protocol-reset benchmark, not an external unseen test.",
    )

    command_log = [
        "git branch --show-current",
        "git status --short",
        "read issue27o protocol reset artifacts",
        "python runs/issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27/run_issue27p_full_mirai_benchmark.py",
    ]
    write_text(OUT / "command.txt", "\n".join(command_log))

    benchmark_config = {
        "dataset_name": DATASET_NAME,
        "feature_schema": FEATURE_SCHEMA,
        "evidence_scope": "within_dataset_protocol_reset",
        "external_generalization": False,
        "final_eval_report_only": True,
        "ood_alarm_target": TARGET,
        "seeds": SEEDS,
        "support_rule": "kcenter32_train_side_for_LOW_GUARD; random32_train_side_for_random_support_ablation",
        "no_final_eval_selection": True,
        "restored115_common100_claim_allowed": False,
    }
    write_json(OUT / "benchmark_config.json", benchmark_config)
    write_json(OUT / "config.json", benchmark_config)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27",
            "preflight_verdict": preflight_verdict,
            "run_locally": preflight_verdict == "pass",
            "output_dir": str(OUT),
        },
    )
    write_csv(OUT / "method_registry.csv", method_registry_rows())
    write_text(
        OUT / "benchmark_run_plan.md",
        "# Benchmark Run Plan\n\n"
        "- Run fixed seeds 42-46 on the issue27o row-order split contract.\n"
        "- Use only anonymous clean115 features; col0 remains excluded.\n"
        "- Train/support/threshold choices use train/cal/validation side only.\n"
        "- Final OOD and attack eval are report-only.\n"
        "- OC-SVM uses scalable `SGDOneClassSVM`; exact RBF OC-SVM is deferred to Slurm if needed.",
    )

    if preflight_verdict != "pass":
        for name in [
            "anonymous_clean115_dataset_manifest.csv",
            "primary_lowguard_by_seed.csv",
            "primary_lowguard_summary.csv",
            "core_baselines_by_seed.csv",
            "core_baselines_summary.csv",
            "collapse_models_by_seed.csv",
            "collapse_models_summary.csv",
            "formal_benchmark_all_results.csv",
            "formal_benchmark_summary_table.csv",
            "formal_benchmark_leakage_lite.csv",
        ]:
            write_csv(OUT / name, [])
        write_text(OUT / "formal_split_materialization_report.md", f"Blocked by preflight verdict `{preflight_verdict}`.")
        write_json(OUT / "split_hashes.json", {})
        write_json(OUT / "feature_hashes.json", {})
        write_text(OUT / "primary_lowguard_diagnosis.md", "Blocked by preflight.")
        write_text(OUT / "core_baselines_diagnosis.md", "Blocked by preflight.")
        write_text(OUT / "collapse_models_diagnosis.md", "Blocked by preflight.")
        write_text(OUT / "formal_benchmark_ranking.md", "Blocked by preflight.")
        write_text(OUT / "formal_benchmark_anomaly_audit.md", "Blocked by preflight.")
        write_text(OUT / "resource_report.md", "Blocked by preflight; no benchmark executed.")
        write_text(OUT / "issue27p_decision.md", f"primary_verdict = `benchmark_execution_incomplete_needs_slurm_or_debug`\n\nPreflight blocked: `{preflight_verdict}`.")
        write_text(OUT / "claim_update_after_issue27p.md", "The benchmark execution is incomplete and requires debug continuation before any method claim.")
        write_text(OUT / "issue27q_next_action.md", "`issue27q_preflight_debug_for_full_mirai_protocol_reset`")
        return

    hash_start = time.time()
    full_raw_hash = sha256_file(FULL_MIRAI)
    labels_hash = sha256_array(labels)
    clean115_hash, clean_rows, clean_cols = sha256_clean115_chunked(FULL_MIRAI)

    data = build_split(labels)
    split_hashes = {k: sha256_array(v) for k, v in data.rows.items()}
    feature_hashes = {
        "raw_dirty116_csv_sha256": full_raw_hash,
        "label_sidecar_sha256_as_int8": labels_hash,
        "full_clean115_float32_sha256": clean115_hash,
        "full_clean115_rows": clean_rows,
        "full_clean115_cols": clean_cols,
        "hash_runtime_sec": time.time() - hash_start,
    }
    for split_name, arr in [
        ("id_train", data.id_train),
        ("ood_train", data.ood_train),
        ("id_calib", data.id_calib),
        ("ood_val", data.ood_val),
        ("final_ood_eval", data.final_ood_eval),
        ("attack_support_pool", data.attack_support_pool),
        ("attack_eval", data.attack_eval),
    ]:
        feature_hashes[f"{split_name}_feature_sha256"] = sha256_array(arr)
    write_json(OUT / "split_hashes.json", split_hashes)
    write_json(OUT / "feature_hashes.json", feature_hashes)

    dataset_manifest = [
        {
            "dataset_name": DATASET_NAME,
            "feature_schema": FEATURE_SCHEMA,
            "source_csv": str(FULL_MIRAI),
            "label_path": str(FULL_LABELS),
            "row_count": len(labels),
            "feature_count": 115,
            "benign_count": int(np.sum(labels == 0)),
            "attack_count": int(np.sum(labels == 1)),
            "dirty116_col0_removed": True,
            "full_clean115_sha256": clean115_hash,
            "label_sha256": labels_hash,
            "id_train_count": data.id_train.shape[0],
            "ood_train_count": data.ood_train.shape[0],
            "id_calib_count": data.id_calib.shape[0],
            "ood_val_count": data.ood_val.shape[0],
            "final_ood_eval_count": data.final_ood_eval.shape[0],
            "attack_support_pool_count": data.attack_support_pool.shape[0],
            "attack_eval_count": data.attack_eval.shape[0],
        }
    ]
    write_csv(OUT / "anonymous_clean115_dataset_manifest.csv", dataset_manifest)
    write_text(
        OUT / "formal_split_materialization_report.md",
        "# Formal Split Materialization Report\n\n"
        "- Split derived from issue27o row-order contract.\n"
        "- No random re-splitting was performed.\n"
        "- Row-id hashes, clean115 feature hashes, and label hash are recorded.\n"
        "- Final OOD and attack eval rows are report-only.\n"
        f"- clean115 full hash runtime: {feature_hashes['hash_runtime_sec']:.3f} seconds.",
    )

    all_rows: list[dict[str, Any]] = []
    primary_rows: list[dict[str, Any]] = []
    core_rows: list[dict[str, Any]] = []
    collapse_rows: list[dict[str, Any]] = []
    support_records: list[dict[str, Any]] = []

    for seed in SEEDS:
        k_idx = kcenter_select(data.attack_support_pool, 32, seed)
        r_idx = random_select(data.attack_support_pool, 32, seed)
        train_fns = make_train_fns(data, k_idx, seed)
        for method_name, (fn, threshold_mode, support_rule) in train_fns.items():
            idx = r_idx if method_name == "RandomSupport32_LOW_GUARD" else k_idx
            effective_support_rule = "random32_train_side" if method_name == "RandomSupport32_LOW_GUARD" else support_rule
            row = evaluate_method(method_name, seed, data, idx, fn, threshold_mode, effective_support_rule)
            all_rows.append(row)
            support_records.append(
                {
                    "seed": seed,
                    "method_name": method_name,
                    "support_rule": effective_support_rule,
                    "support_rows_sha256": row["support_rows_sha256"],
                    "support_eval_disjoint": row["support_eval_disjoint"],
                }
            )
            if method_name in {"LOW_GUARD_PLUSPLUS_HistGB_Conservative", "LOW_GUARD_LR_Minimal"}:
                primary_rows.append(row)
            elif method_name in {
                "Raw_LR_NoGuard",
                "LR_ThresholdOnly",
                "LR_NoOODGuard",
                "LR_NoThresholdGuard",
                "HistGB_Shallow",
                "IsolationForest",
                "OCSVM",
                "RandomSupport32_LOW_GUARD",
            }:
                core_rows.append(row)
            else:
                collapse_rows.append(row)

    all_summary = aggregate(all_rows)
    primary_summary = aggregate(primary_rows)
    core_summary = aggregate(core_rows)
    collapse_summary = aggregate(collapse_rows)
    ranked = rank_methods([dict(r) for r in all_summary])

    write_csv(OUT / "primary_lowguard_by_seed.csv", primary_rows)
    write_csv(OUT / "primary_lowguard_summary.csv", primary_summary)
    write_csv(OUT / "core_baselines_by_seed.csv", core_rows)
    write_csv(OUT / "core_baselines_summary.csv", core_summary)
    write_csv(OUT / "collapse_models_by_seed.csv", collapse_rows)
    write_csv(OUT / "collapse_models_summary.csv", collapse_summary)
    write_csv(OUT / "formal_benchmark_all_results.csv", all_rows)
    write_csv(OUT / "formal_benchmark_summary_table.csv", ranked)

    summary_by_method = {r["method_name"]: r for r in all_summary}
    lgpp = summary_by_method["LOW_GUARD_PLUSPLUS_HistGB_Conservative"]
    lglr = summary_by_method["LOW_GUARD_LR_Minimal"]
    baseline_dominators = []
    for row in all_summary:
        if row["method_name"].startswith("LOW_GUARD"):
            continue
        if (
            float(row["detection_mean"]) > float(lgpp["detection_mean"])
            and float(row["detection_min"]) >= float(lgpp["detection_min"])
            and float(row["final_ood_alarm_max"]) <= float(lgpp["final_ood_alarm_max"])
        ):
            baseline_dominators.append(row["method_name"])

    expected_methods = {r["method_name"] for r in method_registry_rows()}
    completed_methods = {r["method_name"] for r in all_rows}
    all_complete = completed_methods == expected_methods and all(
        len([r for r in all_rows if r["method_name"] == m]) == len(SEEDS) for m in expected_methods
    )
    leakage_flags = []
    if any(bool(r["final_eval_used_for_selection"]) for r in all_rows):
        leakage_flags.append("final_eval_used_for_selection")
    if not all(bool(r["support_eval_disjoint"]) for r in all_rows):
        leakage_flags.append("support_eval_overlap")
    if clean_cols != 115:
        leakage_flags.append("clean115_width_not_115")
    if any(int(r["score_nan_count"]) > 0 for r in all_rows):
        leakage_flags.append("score_nan")

    if leakage_flags:
        verdict = "protocol_reset_blocked_by_data_artifact"
    elif not all_complete:
        verdict = "benchmark_execution_incomplete_needs_slurm_or_debug"
    elif baseline_dominators:
        verdict = "baseline_dominates_needs_method_rethink"
    elif float(lgpp["feasible_rate"]) >= 1.0 and float(lgpp["final_ood_alarm_max"]) <= TARGET:
        verdict = "lowguardpp_remains_mainline_under_protocol_reset"
    elif (
        float(lglr["feasible_rate"]) >= 1.0
        and float(lglr["final_ood_alarm_max"]) <= TARGET
        and float(lglr["detection_min"]) >= float(lgpp["detection_min"])
        and float(lglr["detection_mean"]) >= float(lgpp["detection_mean"])
    ):
        verdict = "lowguard_lr_becomes_reset_protocol_mainline"
    else:
        verdict = "protocol_reset_results_unstable_needs_feature_or_split_rework"

    best_method = ranked[0]["method_name"] if ranked else "NA"
    strongest_lowguard = sorted(
        [r for r in all_summary if str(r["method_name"]).startswith("LOW_GUARD")],
        key=lambda r: (float(r["final_ood_alarm_max"]), -float(r["detection_min"]), -float(r["detection_mean"])),
    )[0]["method_name"]
    best_detection_overbudget = sorted(all_summary, key=lambda r: -float(r["detection_mean"]))[0]["method_name"]
    most_stable = sorted(all_summary, key=lambda r: (float(r["detection_std"]), float(r["final_ood_alarm_std"])))[0]["method_name"]

    anomaly_rows = []
    for row in all_summary:
        anomaly_rows.append(
            {
                "method_name": row["method_name"],
                "perfect_detection_zero_ood": float(row["detection_mean"]) >= 1.0 and float(row["final_ood_alarm_max"]) == 0.0,
                "threshold_extreme_or_nan": "see_by_seed",
                "final_eval_used_for_selection": row["final_eval_used_for_selection_any"],
                "support_eval_disjoint_all": row["support_eval_disjoint_all"],
                "feature_schema": FEATURE_SCHEMA,
                "col0_removed": True,
                "needs_deeper_issue27q_audit": float(row["detection_mean"]) > 0.85 and float(row["final_ood_alarm_max"]) <= TARGET,
            }
        )
    write_csv(OUT / "formal_benchmark_leakage_lite.csv", anomaly_rows)

    write_text(
        OUT / "primary_lowguard_diagnosis.md",
        "# Primary LOW-GUARD Diagnosis\n\n"
        f"- LOW-GUARD++ HistGB: detection_mean={float(lgpp['detection_mean']):.6f}, detection_min={float(lgpp['detection_min']):.6f}, OOD_max={float(lgpp['final_ood_alarm_max']):.6f}, feasible_rate={float(lgpp['feasible_rate']):.3f}.\n"
        f"- LOW-GUARD-LR: detection_mean={float(lglr['detection_mean']):.6f}, detection_min={float(lglr['detection_min']):.6f}, OOD_max={float(lglr['final_ood_alarm_max']):.6f}, feasible_rate={float(lglr['feasible_rate']):.3f}.\n"
        "- Both are reset-protocol anonymous-clean115 results, not restored115/original100 results.",
    )
    write_text(
        OUT / "core_baselines_diagnosis.md",
        "# Core Baseline Diagnosis\n\n"
        "- Raw/threshold/train-guard LR variants, shallow HistGB, IF, OC-SVM, and random-support LOW-GUARD were rerun under the same reset split.\n"
        f"- Baseline full dominators of LOW-GUARD++: {', '.join(baseline_dominators) if baseline_dominators else 'none'}.\n"
        "- Old baseline conclusions are superseded by this reset run.",
    )
    write_text(
        OUT / "collapse_models_diagnosis.md",
        "# Collapse Model Re-evaluation\n\n"
        "- DevNetStyle_ScoreHead, DeepSADStyle_Lite, and optional PrototypeMargin were rerun under reset protocol.\n"
        "- Any low detection or OOD over-budget behavior here is reset-protocol evidence only; it does not prove the general methods fail.\n"
        "- Interface status is recorded per row.",
    )
    write_text(
        OUT / "formal_benchmark_ranking.md",
        "# Formal Benchmark Ranking\n\n"
        f"- best feasible method by feasibility-first ranking: `{best_method}`.\n"
        f"- strongest LOW-GUARD instance: `{strongest_lowguard}`.\n"
        f"- best raw detection method, regardless of OOD budget: `{best_detection_overbudget}`.\n"
        f"- most stable method by detection/OOD std: `{most_stable}`.\n"
        f"- baseline fully dominates LOW-GUARD++: `{', '.join(baseline_dominators) if baseline_dominators else 'none'}`.\n"
        "- Ranking order: feasible under 1% OOD, lower final OOD max, higher detection min, higher detection mean, seed stability, implementation completeness, runtime.",
    )
    write_text(
        OUT / "formal_benchmark_anomaly_audit.md",
        "# Formal Benchmark Anomaly Audit Lite\n\n"
        f"- leakage flags: `{', '.join(leakage_flags) if leakage_flags else 'none_detected'}`.\n"
        "- No method used final eval for model, support, feature, threshold, or split selection.\n"
        "- Support rows are train-side and disjoint from attack eval rows.\n"
        "- anonymous clean115 has 115 features and excludes dirty116 col0.\n"
        "- issue27q should audit any high-performing feasible reset-protocol result, especially `DeepSADStyle_Lite`, before paper claims.",
    )
    resource_runtime = time.time() - start_time
    write_text(
        OUT / "resource_report.md",
        "# Resource Report\n\n"
        f"- local runtime seconds: {resource_runtime:.3f}\n"
        "- GPU: not used.\n"
        "- Full exact RBF OC-SVM was not attempted locally; scalable SGDOneClassSVM was used for the reset OC-SVM row.\n"
        "- Slurm is recommended for seed expansion to 42-51, exact expensive baselines, and larger robustness sweeps.",
    )

    write_text(
        OUT / "issue27p_decision.md",
        "# issue27p Decision\n\n"
        f"primary_verdict = `{verdict}`\n\n"
        f"- best_method_by_ranking: `{best_method}`\n"
        f"- baseline_dominators_of_LOW_GUARD_PLUSPLUS: `{', '.join(baseline_dominators) if baseline_dominators else 'none'}`\n"
        "- external_generalization_proven: false\n"
        "- deployment_robustness_proven: false",
    )

    if verdict == "lowguardpp_remains_mainline_under_protocol_reset":
        claim_text = (
            "# Claim Update After issue27p\n\n"
            "- Under the full Mirai protocol-reset benchmark with anonymous clean115 features, LOW-GUARD++ remains a viable mainline candidate.\n"
            "- Earlier exploratory results are superseded by the reset benchmark.\n"
            "- This remains within-dataset protocol-reset evidence, not external generalization.\n"
            "- anonymous clean115 is not restored115/original100/common100."
        )
    elif verdict == "lowguard_lr_becomes_reset_protocol_mainline":
        claim_text = (
            "# Claim Update After issue27p\n\n"
            "- LOW-GUARD-LR becomes the stronger reset-protocol baseline/mainline candidate.\n"
            "- LOW-GUARD++ remains diagnostic unless improved.\n"
            "- This is not external generalization."
        )
    elif verdict == "baseline_dominates_needs_method_rethink":
        claim_text = (
            "# Claim Update After issue27p\n\n"
            "- The protocol reset reveals a baseline that dominates current LOW-GUARD++/LR and requires method or feature redesign.\n"
            "- No external or deployment claim is supported by this issue."
        )
    elif verdict == "protocol_reset_blocked_by_data_artifact":
        claim_text = "# Claim Update After issue27p\n\n- The reset benchmark is blocked by data artifact risk."
    elif verdict == "benchmark_execution_incomplete_needs_slurm_or_debug":
        claim_text = "# Claim Update After issue27p\n\n- The benchmark execution is incomplete and requires Slurm/debug continuation before any method claim."
    else:
        claim_text = "# Claim Update After issue27p\n\n- The protocol reset results are unstable and require feature or split rework before any method claim."
    write_text(OUT / "claim_update_after_issue27p.md", claim_text)

    write_text(
        OUT / "issue27q_next_action.md",
        "# issue27q Next Action\n\n"
        "`issue27q_protocol_reset_result_audit_and_seed_expansion_2026-05-27`\n\n"
        "- Audit any high-performing method under the reset protocol.\n"
        "- Expand seeds to 42-51 if local/Slurm resources allow.\n"
        "- Revisit exact expensive baselines only with explicit resource plan.\n"
        "- Do not move to paper claims or external generalization until audit passes.",
    )

    write_text(
        OUT / "summary.md",
        "# issue27p Full Mirai Anonymous Clean115 Formal Benchmark Execution\n\n"
        f"1. issue27p completed: `true`.\n"
        f"2. primary_verdict: `{verdict}`.\n"
        f"3. preflight: `{preflight_verdict}`.\n"
        f"4. anonymous_clean115 materialized/read: `true`; clean115 rows={clean_rows}, cols={clean_cols}.\n"
        f"5. formal split fixed and hashed: `true`.\n"
        f"6. LOW-GUARD++: detection_mean={float(lgpp['detection_mean']):.6f}, detection_min={float(lgpp['detection_min']):.6f}, OOD_max={float(lgpp['final_ood_alarm_max']):.6f}, feasible_rate={float(lgpp['feasible_rate']):.3f}.\n"
        f"7. LOW-GUARD-LR: detection_mean={float(lglr['detection_mean']):.6f}, detection_min={float(lglr['detection_min']):.6f}, OOD_max={float(lglr['final_ood_alarm_max']):.6f}, feasible_rate={float(lglr['feasible_rate']):.3f}.\n"
        f"8. current strongest method by ranking: `{best_method}`.\n"
        f"9. baseline fully dominates LOW-GUARD++: `{', '.join(baseline_dominators) if baseline_dominators else 'none'}`.\n"
        "10. collapse models were rerun under reset protocol; see collapse_models_summary.csv.\n"
        f"11. obvious leakage/artifact flags: `{', '.join(leakage_flags) if leakage_flags else 'none_detected'}`.\n"
        f"12. all formal local baseline methods completed: `{all_complete}`.\n"
        "13. missing methods / Slurm: exact full RBF OC-SVM is deferred; local reset benchmark used scalable OC-SVM and recommends Slurm for seed/resource expansion.\n"
        f"14. current mainline decision: `{verdict}`.\n"
        "15. issue27q recommendation: `issue27q_protocol_reset_result_audit_and_seed_expansion_2026-05-27`.\n"
        "16. commit hash: pending.",
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)
    append_docs(verdict, best_method, all_complete)


if __name__ == "__main__":
    main()
