from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


REPO = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
KITNET = Path(r"D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master")
OUT = REPO / "runs" / "issue27q_P0P1_deepsad_lite_audit_and_seed_expansion_2026-05-27"
MAINLINE_DOCS = REPO / "runs" / "mainline_docs"
ISSUE27P = REPO / "runs" / "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27"
ISSUE27Q_PLAN = REPO / "runs" / "issue27q_plan_protocol_reset_result_audit_lowguardpp_failure_and_deepsad_candidate_strategy_2026-05-27"

FULL_MIRAI = KITNET / "Mirai_dataset.csv"
FULL_LABELS = KITNET / "mirai_labels.csv"
FEATURE_SCHEMA = "anonymous_clean115_all"
DATASET_NAME = "full_mirai_protocol_reset"
SPLIT_NAME = "full_mirai_protocol_reset_row_order_v1"
TARGET = 0.01
REPLAY_SEEDS = [42, 43, 44, 45, 46]
EXPANSION_SEEDS = list(range(42, 52))


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


def sha256_array(arr: np.ndarray) -> str:
    a = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(str(a.shape).encode("ascii"))
    h.update(str(a.dtype).encode("ascii"))
    h.update(a.tobytes())
    return h.hexdigest()


def read_labels() -> np.ndarray:
    vals = []
    with FULL_LABELS.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if s:
                vals.append(int(float(s.split(",")[0])))
    return np.asarray(vals, dtype=np.int8)


def load_range(start: int, count: int) -> np.ndarray:
    df = pd.read_csv(FULL_MIRAI, header=None, skiprows=range(0, start), nrows=count)
    arr = df.iloc[:, 1:].to_numpy(dtype=np.float32)
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


def kcenter_select(X: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    first = int(rng.integers(0, X.shape[0]))
    selected = [first]
    min_dist = np.sum((X - X[first]) ** 2, axis=1)
    for _ in range(1, min(k, X.shape[0])):
        idx = int(np.argmax(min_dist))
        selected.append(idx)
        min_dist = np.minimum(min_dist, np.sum((X - X[idx]) ** 2, axis=1))
    return np.asarray(selected, dtype=np.int64)


def calibrate(id_scores: np.ndarray, ood_val_scores: np.ndarray) -> float:
    return float(max(np.quantile(id_scores, 1.0 - TARGET), np.quantile(ood_val_scores, 1.0 - TARGET)))


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

    @property
    def normal_train(self) -> np.ndarray:
        return np.vstack([self.id_train, self.ood_train])


def load_split(labels: np.ndarray) -> SplitData:
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


def fit_deepsad_lite(normal_train: np.ndarray, support: np.ndarray, mode: str = "formal") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    center = normal_train.mean(axis=0)
    scale = normal_train.std(axis=0) + 1e-6
    if mode == "support_removed":
        weights = np.ones_like(center, dtype=np.float32)
    else:
        diff = np.abs(support.mean(axis=0) - center) / scale
        denom = float(np.median(diff) + 1e-6)
        weights = (1.0 + np.clip(diff / denom, 0.0, 5.0)).astype(np.float32)
    return center.astype(np.float32), scale.astype(np.float32), weights


def score_deepsad(X: np.ndarray, model: tuple[np.ndarray, np.ndarray, np.ndarray]) -> np.ndarray:
    center, scale, weights = model
    z = (X - center) / scale
    return np.sum((z * weights) ** 2, axis=1)


def eval_model(data: SplitData, model: tuple[np.ndarray, np.ndarray, np.ndarray], support: np.ndarray) -> dict[str, Any]:
    s_id = score_deepsad(data.id_calib, model)
    s_val = score_deepsad(data.ood_val, model)
    threshold = calibrate(s_id, s_val)
    s_ood = score_deepsad(data.final_ood_eval, model)
    s_attack = score_deepsad(data.attack_eval, model)
    s_support = score_deepsad(support, model)
    return {
        "threshold": float(threshold),
        "attack_detection": float(np.mean(s_attack >= threshold)),
        "final_ood_alarm": float(np.mean(s_ood >= threshold)),
        "id_calib_alarm": float(np.mean(s_id >= threshold)),
        "ood_val_alarm": float(np.mean(s_val >= threshold)),
        "support_mean_score": float(np.mean(s_support)),
        "attack_mean_score": float(np.mean(s_attack)),
        "final_ood_mean_score": float(np.mean(s_ood)),
        "min_attack_score": float(np.min(s_attack)),
        "max_final_ood_score": float(np.max(s_ood)),
        "attack_margin_vs_threshold": float(np.min(s_attack) - threshold),
        "ood_margin_vs_threshold": float(threshold - np.max(s_ood)),
        "scores": {
            "id_calib": s_id,
            "ood_val": s_val,
            "final_ood": s_ood,
            "attack": s_attack,
        },
    }


def row_voids(arr: np.ndarray) -> np.ndarray:
    contiguous = np.ascontiguousarray(arr)
    return contiguous.view(np.dtype((np.void, contiguous.dtype.itemsize * contiguous.shape[1]))).ravel()


def summarize_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    out = []
    for val in sorted({r[key] for r in rows}):
        sub = [r for r in rows if r[key] == val]
        det = np.asarray([float(r["attack_detection"]) for r in sub])
        ood = np.asarray([float(r["final_ood_alarm"]) for r in sub])
        out.append(
            {
                key: val,
                "n": len(sub),
                "detection_mean": float(np.mean(det)),
                "detection_min": float(np.min(det)),
                "detection_std": float(np.std(det)),
                "final_ood_alarm_mean": float(np.mean(ood)),
                "final_ood_alarm_max": float(np.max(ood)),
                "final_ood_alarm_std": float(np.std(ood)),
                "feasible_rate": float(np.mean(ood <= TARGET)),
            }
        )
    return out


def feature_stats(data: SplitData, formal_scores: np.ndarray) -> tuple[list[dict[str, Any]], list[int]]:
    benign_parts = [data.id_train, data.ood_train, data.id_calib, data.ood_val, data.final_ood_eval]
    attack_parts = [data.attack_support_pool, data.attack_eval]
    benign = np.vstack(benign_parts)
    attack = np.vstack(attack_parts)
    rows_benign = np.concatenate([data.rows["id_train"], data.rows["ood_train"], data.rows["id_calib"], data.rows["ood_val"], data.rows["final_ood_eval"]])
    rows_attack = np.concatenate([data.rows["attack_support_pool"], data.rows["attack_eval"]])
    all_rows = np.concatenate([rows_benign, rows_attack]).astype(np.float64)

    global_mean = (benign.sum(axis=0) + attack.sum(axis=0)) / (benign.shape[0] + attack.shape[0])
    global_var = ((benign.astype(np.float64) - global_mean) ** 2).sum(axis=0) + ((attack.astype(np.float64) - global_mean) ** 2).sum(axis=0)
    global_std = np.sqrt(global_var / (benign.shape[0] + attack.shape[0] - 1)) + 1e-12

    label = np.concatenate([np.zeros(benign.shape[0]), np.ones(attack.shape[0])])
    label_std = label.std() + 1e-12
    row_std = all_rows.std() + 1e-12
    rows_all_centered = all_rows - all_rows.mean()

    rows = []
    for j in range(benign.shape[1]):
        xb = benign[:, j].astype(np.float64)
        xa = attack[:, j].astype(np.float64)
        x_all = np.concatenate([xb, xa])
        x_centered = x_all - x_all.mean()
        corr_label = float(np.mean(x_centered * (label - label.mean())) / ((x_all.std() + 1e-12) * label_std))
        corr_row = float(np.mean(x_centered * rows_all_centered) / ((x_all.std() + 1e-12) * row_std))
        pooled = global_std[j]
        cohen_d = float((xa.mean() - xb.mean()) / pooled)
        rows.append(
            {
                "feature_index": j,
                "benign_mean": float(xb.mean()),
                "attack_mean": float(xa.mean()),
                "cohen_d_attack_vs_benign": cohen_d,
                "abs_cohen_d": abs(cohen_d),
                "corr_with_label": corr_label,
                "abs_corr_with_label": abs(corr_label),
                "corr_with_row_order": corr_row,
                "abs_corr_with_row_order": abs(corr_row),
                "constant_rate_proxy": float(max(np.mean(x_all == np.min(x_all)), np.mean(x_all == np.max(x_all)))),
                "is_index_like_risk": bool(abs(corr_row) > 0.999),
            }
        )

    top = sorted(rows, key=lambda r: (r["abs_corr_with_label"], r["abs_cohen_d"]), reverse=True)[:10]
    for r in top:
        j = int(r["feature_index"])
        x = np.concatenate([benign[:, j], attack[:, j]])
        try:
            auc = float(roc_auc_score(label, x))
            r["single_feature_auc"] = max(auc, 1 - auc)
        except Exception:
            r["single_feature_auc"] = "NA"
    score_row_corr = float(np.corrcoef(data.rows["attack_eval"].astype(float), formal_scores)[0, 1])
    for r in rows:
        j = int(r["feature_index"])
        try:
            r["formal_attack_score_corr"] = float(np.corrcoef(data.attack_eval[:, j], formal_scores)[0, 1])
        except Exception:
            r["formal_attack_score_corr"] = "NA"
        r["formal_attack_score_row_corr"] = score_row_corr
        r["near_perfect_single_column_separator"] = bool(
            (r.get("single_feature_auc") != "NA" and float(r.get("single_feature_auc", 0.0)) > 0.995)
            or r["abs_corr_with_label"] > 0.995
        )
    suspicious = [int(r["feature_index"]) for r in sorted(rows, key=lambda r: r["abs_corr_with_label"], reverse=True)[:5]]
    return rows, suspicious


def drop_columns(data: SplitData, cols: list[int]) -> SplitData:
    keep = [i for i in range(data.id_train.shape[1]) if i not in set(cols)]
    return SplitData(
        labels=data.labels,
        id_train=data.id_train[:, keep],
        ood_train=data.ood_train[:, keep],
        id_calib=data.id_calib[:, keep],
        ood_val=data.ood_val[:, keep],
        final_ood_eval=data.final_ood_eval[:, keep],
        attack_support_pool=data.attack_support_pool[:, keep],
        attack_eval=data.attack_eval[:, keep],
        rows=data.rows,
    )


def rank_normalize_array(arr: np.ndarray, sorted_ref: list[np.ndarray]) -> np.ndarray:
    out = np.empty_like(arr, dtype=np.float32)
    n = len(sorted_ref[0])
    for j, ref in enumerate(sorted_ref):
        out[:, j] = np.searchsorted(ref, arr[:, j], side="right") / max(n, 1)
    return out


def rank_normalized_data(data: SplitData) -> SplitData:
    normal = data.normal_train
    sorted_ref = [np.sort(normal[:, j]) for j in range(normal.shape[1])]
    return SplitData(
        labels=data.labels,
        id_train=rank_normalize_array(data.id_train, sorted_ref),
        ood_train=rank_normalize_array(data.ood_train, sorted_ref),
        id_calib=rank_normalize_array(data.id_calib, sorted_ref),
        ood_val=rank_normalize_array(data.ood_val, sorted_ref),
        final_ood_eval=rank_normalize_array(data.final_ood_eval, sorted_ref),
        attack_support_pool=rank_normalize_array(data.attack_support_pool, sorted_ref),
        attack_eval=rank_normalize_array(data.attack_eval, sorted_ref),
        rows=data.rows,
    )


def run_formal(data: SplitData, seeds: list[int], label: str) -> tuple[list[dict[str, Any]], dict[int, dict[str, np.ndarray]]]:
    rows = []
    score_cache: dict[int, dict[str, np.ndarray]] = {}
    normal = data.normal_train
    for seed in seeds:
        idx = kcenter_select(data.attack_support_pool, 32, seed)
        support = data.attack_support_pool[idx]
        model = fit_deepsad_lite(normal, support, mode="formal")
        ev = eval_model(data, model, support)
        score_cache[seed] = ev.pop("scores")
        support_rows = data.rows["attack_support_pool"][idx]
        rows.append(
            {
                "seed": seed,
                "run_label": label,
                "support_rows_sha256": sha256_array(support_rows),
                "support_eval_disjoint": bool(set(support_rows.tolist()).isdisjoint(set(data.rows["attack_eval"].tolist()))),
                "final_eval_used_for_selection": False,
                "score_direction_higher_is_more_anomalous": True,
                **ev,
            }
        )
    return rows, score_cache


def run_control(data: SplitData, seeds: list[int], control_name: str) -> list[dict[str, Any]]:
    rows = []
    normal = data.normal_train
    combined_train = np.vstack([data.id_train, data.ood_train, data.attack_support_pool])
    for seed in seeds:
        rng = np.random.default_rng(seed + 300000)
        if control_name == "support_removed":
            support_idx = kcenter_select(data.attack_support_pool, 32, seed)
            support = data.attack_support_pool[support_idx]
            model = fit_deepsad_lite(normal, support, mode="support_removed")
            support_rows = data.rows["attack_support_pool"][support_idx]
            support_source = "attack_support_pool_weights_removed"
        elif control_name == "ood_benign_support":
            support_idx = kcenter_select(data.ood_train, 32, seed)
            support = data.ood_train[support_idx]
            model = fit_deepsad_lite(normal, support, mode="formal")
            support_rows = data.rows["ood_train"][support_idx]
            support_source = "ood_train_benign"
        elif control_name == "label_permutation_pseudo_support":
            pseudo_idx = rng.choice(np.arange(combined_train.shape[0]), size=32, replace=False)
            support = combined_train[pseudo_idx]
            model = fit_deepsad_lite(normal, support, mode="formal")
            row_pool = np.concatenate([data.rows["id_train"], data.rows["ood_train"], data.rows["attack_support_pool"]])
            support_rows = row_pool[pseudo_idx]
            support_source = "permuted_train_pool_pseudo_positive"
        elif control_name == "random_gaussian_features":
            # Optional sanity: replace all features with seed-fixed Gaussian noise with matching shapes.
            def rnd(shape: tuple[int, int]) -> np.ndarray:
                return rng.normal(size=shape).astype(np.float32)

            gdata = SplitData(
                labels=data.labels,
                id_train=rnd(data.id_train.shape),
                ood_train=rnd(data.ood_train.shape),
                id_calib=rnd(data.id_calib.shape),
                ood_val=rnd(data.ood_val.shape),
                final_ood_eval=rnd(data.final_ood_eval.shape),
                attack_support_pool=rnd(data.attack_support_pool.shape),
                attack_eval=rnd(data.attack_eval.shape),
                rows=data.rows,
            )
            support_idx = kcenter_select(gdata.attack_support_pool, 32, seed)
            support = gdata.attack_support_pool[support_idx]
            model = fit_deepsad_lite(gdata.normal_train, support, mode="formal")
            ev = eval_model(gdata, model, support)
            ev.pop("scores")
            rows.append(
                {
                    "seed": seed,
                    "control_name": control_name,
                    "support_source": "random_gaussian_noise",
                    "support_eval_disjoint": True,
                    "final_eval_used_for_selection": False,
                    **ev,
                }
            )
            continue
        else:
            raise ValueError(control_name)
        ev = eval_model(data, model, support)
        ev.pop("scores")
        rows.append(
            {
                "seed": seed,
                "control_name": control_name,
                "support_source": support_source,
                "support_rows_sha256": sha256_array(support_rows),
                "support_eval_disjoint": bool(set(support_rows.tolist()).isdisjoint(set(data.rows["attack_eval"].tolist()))),
                "final_eval_used_for_selection": False,
                **ev,
            }
        )
    return rows


def segment_report(scores: dict[str, np.ndarray], threshold: float) -> list[dict[str, Any]]:
    rows = []
    attack_scores = scores["attack"]
    n = len(attack_scores)
    for i, idx in enumerate(np.array_split(np.arange(n), 10)):
        rows.append(
            {
                "segment_type": "attack_eval_row_decile",
                "segment_id": i,
                "row_start": int(181621 + idx[0]),
                "row_end": int(181621 + idx[-1]),
                "count": int(len(idx)),
                "detection_or_alarm": float(np.mean(attack_scores[idx] >= threshold)),
                "score_mean": float(np.mean(attack_scores[idx])),
                "score_median": float(np.median(attack_scores[idx])),
            }
        )
    ood_scores = scores["final_ood"]
    for i, idx in enumerate(np.array_split(np.arange(len(ood_scores)), 5)):
        rows.append(
            {
                "segment_type": "final_ood_row_quintile",
                "segment_id": i,
                "row_start": int(110000 + idx[0]),
                "row_end": int(110000 + idx[-1]),
                "count": int(len(idx)),
                "detection_or_alarm": float(np.mean(ood_scores[idx] >= threshold)),
                "score_mean": float(np.mean(ood_scores[idx])),
                "score_median": float(np.median(ood_scores[idx])),
            }
        )
    qs = np.quantile(attack_scores, np.linspace(0, 1, 11))
    for i in range(10):
        mask = (attack_scores >= qs[i]) & (attack_scores <= qs[i + 1])
        rows.append(
            {
                "segment_type": "attack_score_decile",
                "segment_id": i,
                "row_start": "NA",
                "row_end": "NA",
                "count": int(np.sum(mask)),
                "detection_or_alarm": float(np.mean(attack_scores[mask] >= threshold)) if np.any(mask) else "NA",
                "score_mean": float(np.mean(attack_scores[mask])) if np.any(mask) else "NA",
                "score_median": float(np.median(attack_scores[mask])) if np.any(mask) else "NA",
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    start = time.time()

    labels = read_labels()
    data = load_split(labels)
    issue27p_rows = pd.read_csv(ISSUE27P / "formal_benchmark_all_results.csv")
    issue27p_ds = issue27p_rows[issue27p_rows["method_name"] == "DeepSADStyle_Lite"].copy()

    formal_rows, score_cache = run_formal(data, REPLAY_SEEDS, "issue27p_replay")
    replay_rows = []
    replay_ok = True
    for row in formal_rows:
        old = issue27p_ds[issue27p_ds["seed"] == row["seed"]].iloc[0].to_dict()
        det_diff = abs(float(row["attack_detection"]) - float(old["attack_detection"]))
        ood_diff = abs(float(row["final_ood_alarm"]) - float(old["final_ood_alarm"]))
        threshold_diff = abs(float(row["threshold"]) - float(old["threshold"]))
        ok = det_diff < 1e-12 and ood_diff < 1e-12 and threshold_diff < 1e-6
        replay_ok = replay_ok and ok
        replay_rows.append(
            {
                "seed": row["seed"],
                "issue27p_attack_detection": old["attack_detection"],
                "replay_attack_detection": row["attack_detection"],
                "attack_detection_abs_diff": det_diff,
                "issue27p_final_ood_alarm": old["final_ood_alarm"],
                "replay_final_ood_alarm": row["final_ood_alarm"],
                "final_ood_alarm_abs_diff": ood_diff,
                "issue27p_threshold": old["threshold"],
                "replay_threshold": row["threshold"],
                "threshold_abs_diff": threshold_diff,
                "replay_matches_issue27p": ok,
                "score_direction_higher_is_more_anomalous": True,
                "final_eval_used_for_selection": False,
            }
        )
    write_csv(OUT / "deepsad_lite_replay_table.csv", replay_rows)

    # Data separation and leakage assertions.
    split_sets = {k: set(v.tolist()) for k, v in data.rows.items()}
    separation_rows = []
    for a in split_sets:
        for b in split_sets:
            if a < b:
                overlap = len(split_sets[a].intersection(split_sets[b]))
                separation_rows.append(
                    {
                        "assertion": f"{a}_vs_{b}_row_disjoint",
                        "passed": overlap == 0,
                        "overlap_count": overlap,
                        "notes": "row-id disjointness",
                    }
                )
    attack_eval_voids = row_voids(data.attack_eval)
    attack_eval_hash_set = set(attack_eval_voids.tolist())
    feature_dup_count = 0
    for seed in EXPANSION_SEEDS:
        idx = kcenter_select(data.attack_support_pool, 32, seed)
        support_voids = row_voids(data.attack_support_pool[idx])
        feature_dup_count += sum(v in attack_eval_hash_set for v in support_voids.tolist())
    separation_rows.extend(
        [
            {
                "assertion": "dirty116_col0_removed",
                "passed": data.id_train.shape[1] == 115,
                "overlap_count": 0,
                "notes": f"feature_count={data.id_train.shape[1]}",
            },
            {
                "assertion": "label_sidecar_not_in_feature_matrix",
                "passed": data.id_train.shape[1] == 115 and np.all(labels[:121621] == 0) and np.all(labels[121621:] == 1),
                "overlap_count": 0,
                "notes": "labels loaded separately and never appended to features",
            },
            {
                "assertion": "support_feature_duplicate_with_attack_eval",
                "passed": feature_dup_count == 0,
                "overlap_count": feature_dup_count,
                "notes": "exact float32 row-byte duplicate check for support seeds 42..51",
            },
            {
                "assertion": "threshold_uses_validation_only",
                "passed": replay_ok,
                "overlap_count": 0,
                "notes": "threshold replay matches issue27p from ID_calib+OOD_val",
            },
        ]
    )
    separation_ok = all(bool(r["passed"]) for r in separation_rows)
    write_csv(OUT / "deepsad_lite_data_separation_assertions.csv", separation_rows)

    if not replay_ok:
        verdict = "deepsad_lite_result_invalid_needs_implementation_fix"
    elif not separation_ok:
        verdict = "deepsad_lite_result_blocked_by_leakage_or_overlap"
    else:
        controls = []
        for control in [
            "label_permutation_pseudo_support",
            "support_removed",
            "ood_benign_support",
            "random_gaussian_features",
        ]:
            controls.extend(run_control(data, REPLAY_SEEDS, control))
        write_csv(OUT / "deepsad_lite_negative_controls_by_seed.csv", controls)
        control_summary = summarize_by(controls, "control_name")
        write_csv(OUT / "deepsad_lite_negative_controls_summary.csv", control_summary)

        # Feature artifact audit uses formal seed 42 scores for score correlations.
        seed42_scores = score_cache[42]["attack"]
        feature_rows, suspicious_cols = feature_stats(data, seed42_scores)
        write_csv(OUT / "deepsad_lite_feature_artifact_audit.csv", sorted(feature_rows, key=lambda r: r["abs_corr_with_label"], reverse=True))

        # Quick replay for top-column removal and rank-normalized data.
        artifact_replay = []
        variants: list[tuple[str, SplitData]] = [
            ("remove_top1_suspicious", drop_columns(data, suspicious_cols[:1])),
            ("remove_top3_suspicious", drop_columns(data, suspicious_cols[:3])),
            ("remove_top5_suspicious", drop_columns(data, suspicious_cols[:5])),
        ]
        # Rank normalization is comparatively expensive but important because it tests whether scale dominates the center distance.
        variants.append(("rank_normalize_all_features_train_reference", rank_normalized_data(data)))
        for name, vdata in variants:
            rows, _ = run_formal(vdata, REPLAY_SEEDS, name)
            for r in rows:
                r["variant"] = name
                r.pop("scores", None)
                artifact_replay.append(r)
        write_csv(OUT / "deepsad_lite_feature_artifact_replay.csv", artifact_replay)
        artifact_summary = summarize_by(artifact_replay, "variant")

        # Seed expansion formal run.
        expansion_rows, expansion_scores = run_formal(data, EXPANSION_SEEDS, "seed_expansion_42_51")
        write_csv(OUT / "deepsad_lite_seed_expansion_by_seed.csv", expansion_rows)
        expansion_summary = summarize_by(expansion_rows, "run_label")
        write_csv(OUT / "deepsad_lite_seed_expansion_summary.csv", expansion_summary)

        # Stratification with seed 42 and summary of row-order weakness.
        seed42_threshold = next(r["threshold"] for r in expansion_rows if r["seed"] == 42)
        strat_rows = segment_report(expansion_scores[42], float(seed42_threshold))
        write_csv(OUT / "deepsad_lite_stratified_diagnosis.csv", strat_rows)

        formal_det = [float(r["attack_detection"]) for r in expansion_rows]
        formal_ood = [float(r["final_ood_alarm"]) for r in expansion_rows]
        seed_stable = min(formal_det) > 0.85 and max(formal_ood) <= TARGET and np.std(formal_det) < 1e-3
        controls_by_name = {r["control_name"]: r for r in control_summary}
        support_removed_strong = float(controls_by_name["support_removed"]["detection_mean"]) > 0.8 and float(controls_by_name["support_removed"]["final_ood_alarm_max"]) <= TARGET
        ood_support_strong = float(controls_by_name["ood_benign_support"]["detection_mean"]) > 0.8 and float(controls_by_name["ood_benign_support"]["final_ood_alarm_max"]) <= TARGET
        pseudo_support_strong = float(controls_by_name["label_permutation_pseudo_support"]["detection_mean"]) > 0.8 and float(controls_by_name["label_permutation_pseudo_support"]["final_ood_alarm_max"]) <= TARGET
        random_gaussian_collapsed = float(controls_by_name["random_gaussian_features"]["detection_mean"]) < 0.1
        near_perfect_cols = [r for r in feature_rows if r["near_perfect_single_column_separator"]]
        rank_norm_summary = [r for r in artifact_summary if r["variant"] == "rank_normalize_all_features_train_reference"][0]
        top_drop_summary = [r for r in artifact_summary if r["variant"] == "remove_top5_suspicious"][0]
        feature_artifact = len(near_perfect_cols) > 0 or float(top_drop_summary["detection_mean"]) < 0.5
        negative_controls_ok = random_gaussian_collapsed and not (support_removed_strong and ood_support_strong and pseudo_support_strong)

        if not negative_controls_ok:
            verdict = "deepsad_lite_result_suspicious_needs_artifact_debug"
        elif feature_artifact:
            verdict = "deepsad_lite_result_feature_artifact_risk"
        elif not seed_stable:
            verdict = "deepsad_lite_candidate_unstable_under_seed_expansion"
        else:
            verdict = "deepsad_lite_candidate_passes_p0p1_audit"

        worst_attack_segment = min([r for r in strat_rows if r["segment_type"] == "attack_eval_row_decile"], key=lambda r: float(r["detection_or_alarm"]))
        worst_ood_segment = max([r for r in strat_rows if r["segment_type"] == "final_ood_row_quintile"], key=lambda r: float(r["detection_or_alarm"]))

        write_text(
            OUT / "deepsad_lite_negative_controls_report.md",
            f"""
# DeepSADStyle_Lite Negative Controls

- label_permutation_pseudo_support detection_mean: `{controls_by_name['label_permutation_pseudo_support']['detection_mean']}`.
- support_removed detection_mean: `{controls_by_name['support_removed']['detection_mean']}`.
- ood_benign_support detection_mean: `{controls_by_name['ood_benign_support']['detection_mean']}`.
- random_gaussian_features detection_mean: `{controls_by_name['random_gaussian_features']['detection_mean']}`.

Interpretation:

The random Gaussian feature control collapses if its detection is near the OOD target, which checks that the scoring code is not label-driven.
If support removal or benign pseudo-support remains strong, the candidate is not yet proven to be few-shot support-driven; it may be a strong
normal-center detector under this split. That is a claim-boundary risk, not an automatic implementation failure.
""",
        )
        write_text(
            OUT / "deepsad_lite_feature_artifact_report.md",
            f"""
# DeepSADStyle_Lite Feature Artifact Audit

- suspicious columns by label/row-order proxy: `{suspicious_cols}`.
- near-perfect single-column separators: `{len(near_perfect_cols)}`.
- remove_top5 suspicious replay detection_mean: `{top_drop_summary['detection_mean']}`.
- rank-normalize all features replay detection_mean: `{rank_norm_summary['detection_mean']}`.

This is an anonymous clean115 audit. Column semantics are still unknown, so any strong single-column or row-order dependence requires issue27r
feature provenance rather than a main-text claim.
""",
        )
        write_text(
            OUT / "deepsad_lite_seed_expansion_report.md",
            f"""
# DeepSADStyle_Lite Seed Expansion Report

- seeds: `42..51`.
- detection_mean: `{expansion_summary[0]['detection_mean']}`.
- detection_min: `{expansion_summary[0]['detection_min']}`.
- detection_std: `{expansion_summary[0]['detection_std']}`.
- final_ood_alarm_max: `{expansion_summary[0]['final_ood_alarm_max']}`.
- feasible_rate: `{expansion_summary[0]['feasible_rate']}`.
- seed-invariant behavior persists: `{seed_stable}`.

No config, threshold target, feature, support, or split selection used final eval.
""",
        )
        write_text(
            OUT / "deepsad_lite_stratified_report.md",
            f"""
# DeepSADStyle_Lite Stratified Diagnosis

- worst attack row-order decile: `{worst_attack_segment['segment_id']}` with detection `{worst_attack_segment['detection_or_alarm']}`.
- worst final OOD row-order quintile: `{worst_ood_segment['segment_id']}` with alarm `{worst_ood_segment['detection_or_alarm']}`.

No attack-family labels are available in the anonymous clean115 split, so row-order and score segments are the available stratification.
Temporal or second-dataset validation remains unproven.
""",
        )
    if replay_ok:
        write_text(
            OUT / "deepsad_lite_implementation_replay.md",
            """
# DeepSADStyle_Lite Implementation Replay

DeepSADStyle_Lite is a weighted-center distance method:

- normal center and scale are estimated from ID_train + OOD_train.
- attack support is used only to form feature weights from support mean distance to the normal center.
- score is weighted squared distance to the normal center.
- higher score means more anomalous.
- threshold is max(99th percentile ID_calib score, 99th percentile OOD_val score).
- final OOD eval and attack eval are report-only.

This is not full Deep SAD. It is a DeepSAD-style Lite / weighted-center objective.
Replay of seeds 42..46 matches issue27p.
""",
        )
    else:
        write_text(
            OUT / "deepsad_lite_implementation_replay.md",
            "# DeepSADStyle_Lite Implementation Replay\n\nReplay failed; stop before interpreting performance.",
        )

    write_text(
        OUT / "deepsad_lite_data_separation_report.md",
        f"""
# DeepSADStyle_Lite Data Separation Report

- row split disjointness: `{all(r['passed'] for r in separation_rows if 'row_disjoint' in r['assertion'])}`.
- support/eval exact feature duplicate count: `{next(r['overlap_count'] for r in separation_rows if r['assertion'] == 'support_feature_duplicate_with_attack_eval')}`.
- dirty116 col0 removed: `{data.id_train.shape[1] == 115}`.
- label sidecar is loaded separately and not appended to features.
- threshold replay uses validation-only scores and matches issue27p: `{replay_ok}`.
""",
    )

    if not replay_ok or not separation_ok:
        # Emit required files with blocked content.
        for name in [
            "deepsad_lite_negative_controls_by_seed.csv",
            "deepsad_lite_negative_controls_summary.csv",
            "deepsad_lite_feature_artifact_audit.csv",
            "deepsad_lite_seed_expansion_by_seed.csv",
            "deepsad_lite_seed_expansion_summary.csv",
            "deepsad_lite_stratified_diagnosis.csv",
        ]:
            write_csv(OUT / name, [])
        for name in [
            "deepsad_lite_negative_controls_report.md",
            "deepsad_lite_feature_artifact_report.md",
            "deepsad_lite_seed_expansion_report.md",
            "deepsad_lite_stratified_report.md",
        ]:
            write_text(OUT / name, "Blocked by replay or data separation failure.")
        formal_continue = False
        support_disjoint = separation_ok
        final_report_only = replay_ok
        controls_collapse = "blocked"
        feature_risk_text = "blocked"
        seed_text = "blocked"
        strat_text = "blocked"
    else:
        formal_continue = verdict == "deepsad_lite_candidate_passes_p0p1_audit"
        support_disjoint = separation_ok
        final_report_only = True
        controls_collapse = str(negative_controls_ok)
        feature_risk_text = "near_perfect_cols=" + str(len(near_perfect_cols))
        seed_text = str(seed_stable)
        strat_text = f"worst_attack_decile={worst_attack_segment['segment_id']}"

    write_text(
        OUT / "issue27q_P0P1_decision.md",
        f"""
# issue27q P0P1 Decision

primary_verdict = `{verdict}`

- replay_matches_issue27p: `{replay_ok}`
- data_separation_passed: `{separation_ok}`
- negative_controls_passed: `{controls_collapse}`
- feature_artifact_status: `{feature_risk_text}`
- seed_expansion_stable: `{seed_text}`

DeepSADStyle_Lite is still bounded to the full Mirai anonymous_clean115 within-dataset protocol reset. It is not exact Deep SAD and is not an external-generalization result.
""",
    )
    write_text(
        OUT / "claim_update_after_issue27q_P0P1.md",
        f"""
# Claim Update After issue27q P0P1

Allowed:

- DeepSADStyle_Lite has undergone P0/P1 replay, data separation, negative control, feature artifact, seed expansion, and stratified audits.
- The result remains bounded to anonymous clean115 and the full Mirai within-dataset protocol reset.

Not allowed:

- DeepSADStyle_Lite is the final main method.
- DeepSADStyle_Lite is exact Deep SAD.
- External generalization, temporal generalization, or deployment robustness is proven.
- LOW-GUARD++ is abandoned.

Current verdict: `{verdict}`.
""",
    )
    next_action = (
        "issue27r_deepsad_lite_artifact_debug_and_feature_provenance"
        if verdict in {"deepsad_lite_result_suspicious_needs_artifact_debug", "deepsad_lite_result_feature_artifact_risk"}
        else "issue27q_P2_lowguardpp_failure_diagnosis"
    )
    write_text(
        OUT / "issue27q_next_action_after_P0P1.md",
        f"""
# Next Action After issue27q P0P1

Recommended next issue: `{next_action}`.

If the candidate remains suspicious, debug support dependence and anonymous-feature provenance before any mainline claim. If it passes, proceed to LOW-GUARD++ failure diagnosis without abandoning LOW-GUARD++.
""",
    )

    write_text(
        OUT / "summary.md",
        f"""
# issue27q P0P1 DeepSADStyle_Lite Audit Summary

1. issue27q_P0P1 completed: `true`.
2. primary_verdict: `{verdict}`.
3. issue27p DeepSADStyle_Lite replay reproduced: `{replay_ok}`.
4. score direction correct: `true` (higher weighted-center distance is more anomalous).
5. threshold replay correct: `{replay_ok}`.
6. final eval report-only: `{final_report_only}`.
7. support and attack eval disjoint: `{support_disjoint}`.
8. negative controls behaved as expected: `{controls_collapse}`.
9. label-like / index-like / row-order artifact: `{feature_risk_text}`.
10. seeds 42..51 stable: `{seed_text}`.
11. attack/OOD stratification exposed weakness: `{strat_text}`.
12. DeepSADStyle_Lite can continue as mainline candidate: `{formal_continue}`.
13. can proceed to LOW-GUARD++ failure diagnosis: `{formal_continue}`.
14. Slurm needed: `not for P0 controls; recommended for broader follow-up`.
15. next recommendation: `{next_action}`.
16. commit hash: pending.
""",
    )

    write_text(
        OUT / "command.txt",
        "\n".join(
            [
                "git branch --show-current",
                "git status --short",
                "read issue27p and issue27q_plan artifacts",
                "python runs/issue27q_P0P1_deepsad_lite_audit_and_seed_expansion_2026-05-27/run_issue27q_p0p1_deepsad_audit.py",
            ]
        ),
    )
    write_json(
        OUT / "config.json",
        {
            "dataset": "full_mirai_protocol_reset",
            "feature_schema": FEATURE_SCHEMA,
            "method": "DeepSADStyle_Lite_weighted_center_not_exact_deep_sad",
            "seeds_replay": REPLAY_SEEDS,
            "seeds_expansion": EXPANSION_SEEDS,
            "threshold_target": TARGET,
            "final_eval_report_only": True,
            "no_lowguardpp_repair": True,
            "no_universality_matrix": True,
        },
    )
    write_json(
        OUT / "run_spec.json",
        {
            "issue": "issue27q_P0P1_deepsad_lite_audit_and_seed_expansion_2026-05-27",
            "outputs": [
                "summary.md",
                "deepsad_lite_implementation_replay.md",
                "deepsad_lite_data_separation_assertions.csv",
                "deepsad_lite_negative_controls_summary.csv",
                "deepsad_lite_feature_artifact_audit.csv",
                "deepsad_lite_seed_expansion_summary.csv",
                "deepsad_lite_stratified_diagnosis.csv",
            ],
            "runtime_sec": time.time() - start,
        },
    )

    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    with handoff.open("a", encoding="utf-8") as f:
        f.write(
            "\n## issue27q P0P1 DeepSAD-lite audit and seed expansion (2026-05-27)\n\n"
            f"- primary_verdict: `{verdict}`\n"
            "- scope: audits DeepSADStyle_Lite replay, score direction, split separation, negative controls, feature artifacts, seed expansion, and stratified behavior.\n"
            "- claim boundary: DeepSADStyle_Lite remains a weighted-center lite candidate under anonymous clean115, not exact Deep SAD and not external generalization.\n"
            f"- next action: `{next_action}`.\n"
        )
    exp_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    with exp_map.open("a", encoding="utf-8") as f:
        f.write(
            "\n| issue27q_P0P1 | DeepSAD-lite replay/audit/seed expansion | "
            f"`{verdict}` | P0/P1 audit for the issue27p leader; checks replay, leakage, negative controls, feature artifact risk, and seed 42-51 stability. Next: `{next_action}`. |\n"
        )

    manifest = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest.append({"file": path.name, "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)


if __name__ == "__main__":
    main()
