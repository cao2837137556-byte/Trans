from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import pickle
import platform
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
PROJECT_ROOT = ROOT.parent.parent

ISSUE = "issue27ckb_offline_static_capability_snapshot_on_frozen_exact_label_roles_2026-06-18"
OUT = ROOT / "runs" / ISSUE
ISSUE27CF = ROOT / "runs" / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
ISSUE27CH = ROOT / "runs" / "issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17"

CERT_ROOT = Path(
    os.environ.get(
        "GOTHAM_CERT_ROOT",
        str(PROJECT_ROOT / "datasets" / "gotham2025" / "derived" / "kitsune115_larger_sanity_1m_certified_v1"),
    )
)
ATTACK_ROOT = Path(
    os.environ.get(
        "GOTHAM_ATTACK_ROOT",
        str(PROJECT_ROOT / "datasets" / "gotham2025" / "derived" / "kitsune115_exact_label_targeted_attack_v1"),
    )
)

CERT_X = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_X.npy"
CERT_SPLIT = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_split_manifest.csv.gz"
FEATURE_SCHEMA = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_feature_schema.json"
ATTACK_CHUNKS = ATTACK_ROOT / "chunks"
SUPPORT_SIDECAR = ISSUE27CF / "support_bank_sidecar.csv"
CERTIFIED_CHUNKS = ISSUE27CH / "certified_chunk_manifest.csv"
CERTIFIED_SUBSET = ISSUE27CH / "certified_attack_subset_v1.json"

ROLE_ORDER = [
    "id_benign_train",
    "support_train",
    "id_benign_calib",
    "support_val",
    "ood_benign_val",
    "freeze_model_and_thresholds",
    "ood_benign_stress",
    "same_file_time_forward_dev_query_exact",
    "dev_future_attack_query_exact",
    "sealed_final_attack_exact_realign",
    "sealed_final_ood",
]

TRAIN_ROLES = {"id_benign_train", "support_train"}
CALIBRATION_ROLES = {"id_benign_calib", "support_val", "ood_benign_val"}
READ_ONLY_ROLES = {
    "ood_benign_stress",
    "same_file_time_forward_dev_query_exact",
    "dev_future_attack_query_exact",
}
REPORT_ONLY_ROLES = {"sealed_final_attack_exact_realign", "sealed_final_ood"}

THRESHOLD_RULES = ("id_q99", "ood_guarded_q99", "support_val_recall90")
CLIP_ABS = 50.0
EPS = 1e-8


@dataclass(frozen=True)
class JobSpec:
    job_index: int
    model_family: str
    seed: int
    support_weight: float
    label: str


JOB_SPECS = [
    JobSpec(1, "histgb", 42, 64.0, "histgb_support64_seed42"),
    JobSpec(2, "histgb", 43, 64.0, "histgb_support64_seed43"),
    JobSpec(3, "histgb", 44, 64.0, "histgb_support64_seed44"),
    JobSpec(4, "histgb", 42, 256.0, "histgb_support256_seed42"),
    JobSpec(5, "histgb", 43, 256.0, "histgb_support256_seed43"),
    JobSpec(6, "histgb", 44, 256.0, "histgb_support256_seed44"),
    JobSpec(7, "logreg", 42, -1.0, "logreg_balanced"),
]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    view = np.ascontiguousarray(array).view(np.uint8)
    return hashlib.sha256(view).hexdigest()


def qstats(scores: np.ndarray) -> dict[str, float]:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.size == 0:
        return {key: float("nan") for key in ("min", "p01", "p10", "p50", "p90", "p99", "max", "mean", "std")}
    return {
        "min": float(np.min(scores)),
        "p01": float(np.quantile(scores, 0.01)),
        "p10": float(np.quantile(scores, 0.10)),
        "p50": float(np.quantile(scores, 0.50)),
        "p90": float(np.quantile(scores, 0.90)),
        "p99": float(np.quantile(scores, 0.99)),
        "max": float(np.max(scores)),
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
    }


def rate(scores: np.ndarray, threshold: float) -> float:
    scores = np.asarray(scores, dtype=np.float64)
    return float(np.mean(scores >= float(threshold))) if scores.size else float("nan")


def safe_auc(positive: np.ndarray, negative: np.ndarray) -> tuple[float, float]:
    positive = np.asarray(positive, dtype=np.float64)
    negative = np.asarray(negative, dtype=np.float64)
    if not len(positive) or not len(negative):
        return float("nan"), float("nan")
    y = np.concatenate([np.ones(len(positive), dtype=np.int8), np.zeros(len(negative), dtype=np.int8)])
    scores = np.concatenate([positive, negative])
    return float(roc_auc_score(y, scores)), float(average_precision_score(y, scores))


def role_indices() -> dict[str, np.ndarray]:
    roles: dict[str, list[int]] = defaultdict(list)
    with gzip.open(CERT_SPLIT, "rt", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            roles[row["role"]].append(int(row["global_row_id"]))
    return {role: np.asarray(indices, dtype=np.int64) for role, indices in roles.items()}


def limited_indices(indices: np.ndarray, smoke: bool, limit: int) -> np.ndarray:
    return indices[: min(len(indices), limit)] if smoke else indices


def fit_scaler(x_id: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    center = np.median(x_id, axis=0)
    q25 = np.quantile(x_id, 0.25, axis=0)
    q75 = np.quantile(x_id, 0.75, axis=0)
    scale = q75 - q25
    std = np.std(x_id, axis=0)
    use_std = scale <= EPS
    scale[use_std] = std[use_std]
    scale[scale <= EPS] = 1.0
    return center.astype(np.float64), scale.astype(np.float64)


def transform(x: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    z = (np.asarray(x, dtype=np.float64) - center) / scale
    return np.clip(z, -CLIP_ABS, CLIP_ABS).astype(np.float32)


def discover_attack_root() -> Path:
    if ATTACK_CHUNKS.exists() and any(ATTACK_CHUNKS.glob("chunk_*_X.npy")):
        return ATTACK_ROOT
    candidates = sorted(
        (PROJECT_ROOT / "supercompute_transfer" / "issue27cd_exact_label_attack_slurm_20260614" / "pullback_results").glob(
            "extracted_*/datasets/gotham2025/derived/kitsune115_exact_label_targeted_attack_v1"
        ),
        reverse=True,
    )
    for candidate in candidates:
        if (candidate / "chunks").exists():
            return candidate
    raise FileNotFoundError(f"Attack chunks not found under {ATTACK_ROOT} or pullback fallbacks")


def validate_inputs() -> dict[str, Any]:
    attack_root = discover_attack_root()
    required = [CERT_X, CERT_SPLIT, FEATURE_SCHEMA, SUPPORT_SIDECAR, CERTIFIED_CHUNKS, CERTIFIED_SUBSET]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(missing))
    chunks = read_csv(CERTIFIED_CHUNKS)
    missing_chunks = [
        int(row["chunk_id"])
        for row in chunks
        if not (attack_root / "chunks" / f"chunk_{int(row['chunk_id']):05d}_X.npy").exists()
    ]
    if missing_chunks:
        raise FileNotFoundError(f"Missing certified attack chunks: {missing_chunks[:20]}")
    x = np.load(CERT_X, mmap_mode="r")
    if x.shape != (1_000_000, 115):
        raise RuntimeError(f"Unexpected certified X shape: {x.shape}")
    support_rows = read_csv(SUPPORT_SIDECAR)
    if len(support_rows) != 512:
        raise RuntimeError(f"Expected 512 frozen support rows, got {len(support_rows)}")
    return {
        "attack_root": str(attack_root),
        "cert_x_shape": list(x.shape),
        "support_rows": len(support_rows),
        "certified_chunks": len(chunks),
        "input_hashes": {
            "feature_schema": sha256_file(FEATURE_SCHEMA),
            "support_sidecar": sha256_file(SUPPORT_SIDECAR),
            "certified_chunk_manifest": sha256_file(CERTIFIED_CHUNKS),
            "certified_subset_contract": sha256_file(CERTIFIED_SUBSET),
        },
    }


def load_support(attack_root: Path, smoke: bool) -> tuple[list[dict[str, str]], np.ndarray, np.ndarray, np.ndarray]:
    rows = read_csv(SUPPORT_SIDECAR)
    cache: dict[int, np.ndarray] = {}
    features = []
    for row in rows:
        chunk_id = int(row["chunk_id"])
        if chunk_id not in cache:
            cache[chunk_id] = np.load(attack_root / "chunks" / f"chunk_{chunk_id:05d}_X.npy", mmap_mode="r")
        features.append(np.asarray(cache[chunk_id][int(row["row_index_within_chunk"])], dtype=np.float32))
    x = np.vstack(features)
    train_mask = np.asarray([row["bank_partition"] == "support_train" for row in rows], dtype=bool)
    val_mask = np.asarray([row["bank_partition"] == "support_val" for row in rows], dtype=bool)
    # The frozen bank is small enough to keep intact even in smoke mode.
    # Truncating it would silently remove exact labels and invalidate seen/unseen audits.
    train_ids = np.where(train_mask)[0]
    val_ids = np.where(val_mask)[0]
    return rows, x, train_ids, val_ids


def make_model(spec: JobSpec, n_id: int, n_support: int) -> tuple[Any, float]:
    if spec.model_family == "histgb":
        model = HistGradientBoostingClassifier(
            max_depth=6,
            max_iter=220,
            learning_rate=0.05,
            l2_regularization=1.0,
            min_samples_leaf=20,
            early_stopping=True,
            validation_fraction=0.10,
            n_iter_no_change=20,
            random_state=spec.seed,
        )
        return model, spec.support_weight
    if spec.model_family == "logreg":
        model = LogisticRegression(
            C=1.0,
            max_iter=600,
            solver="lbfgs",
            random_state=spec.seed,
        )
        return model, float(n_id / max(1, n_support))
    raise ValueError(spec.model_family)


def positive_scores(model: Any, x: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(x)
    classes = list(model.classes_)
    if 1 not in classes:
        raise RuntimeError(f"Attack class missing from model classes: {classes}")
    return np.asarray(proba[:, classes.index(1)], dtype=np.float64)


def score_in_batches(model: Any, x: np.ndarray, center: np.ndarray, scale: np.ndarray, batch: int = 50_000) -> np.ndarray:
    scores = np.empty(len(x), dtype=np.float64)
    for start in range(0, len(x), batch):
        stop = min(len(x), start + batch)
        scores[start:stop] = positive_scores(model, transform(np.asarray(x[start:stop]), center, scale))
    return scores


def thresholds_from_calibration(
    id_scores: np.ndarray,
    support_scores: np.ndarray,
    ood_scores: np.ndarray,
) -> dict[str, float]:
    id_q99 = float(np.quantile(id_scores, 0.99))
    ood_q99 = float(np.quantile(ood_scores, 0.99))
    support_recall90 = float(np.quantile(support_scores, 0.10))
    return {
        "id_q99": id_q99,
        "ood_guarded_q99": max(id_q99, ood_q99),
        "support_val_recall90": support_recall90,
    }


def load_attack_role_scores(
    model: Any,
    center: np.ndarray,
    scale: np.ndarray,
    attack_root: Path,
    role: str,
    smoke: bool,
    smoke_limit: int = 3000,
) -> tuple[np.ndarray, list[dict[str, str]]]:
    rows = [row for row in read_csv(CERTIFIED_CHUNKS) if row["role"] == role and row["status"] == "complete"]
    scores: list[np.ndarray] = []
    metadata: list[dict[str, str]] = []
    remaining = smoke_limit if smoke else None
    for row in rows:
        raw = np.load(attack_root / "chunks" / f"chunk_{int(row['chunk_id']):05d}_X.npy", mmap_mode="r")
        if len(raw) != int(row["emitted_rows"]):
            raise RuntimeError(f"Chunk length mismatch for chunk {row['chunk_id']}")
        take = len(raw) if remaining is None else min(len(raw), remaining)
        if take <= 0:
            break
        chunk_scores = score_in_batches(model, raw[:take], center, scale)
        scores.append(chunk_scores)
        metadata.extend(
            {
                "role": role,
                "attack_label": row["attack_label"],
                "device": row["device"],
                "phase": row["phase"],
                "chunk_id": row["chunk_id"],
            }
            for _ in range(take)
        )
        if remaining is not None:
            remaining -= take
    return (np.concatenate(scores) if scores else np.asarray([], dtype=np.float64)), metadata


def distribution_row(spec: JobSpec, role: str, scores: np.ndarray, stage: str) -> dict[str, Any]:
    return {
        "job_index": spec.job_index,
        "model_label": spec.label,
        "model_family": spec.model_family,
        "seed": spec.seed,
        "role": role,
        "stage": stage,
        "rows": int(len(scores)),
        **qstats(scores),
    }


def threshold_rows(
    spec: JobSpec,
    role: str,
    scores: np.ndarray,
    thresholds: dict[str, float],
    stage: str,
    metric_kind: str,
) -> list[dict[str, Any]]:
    return [
        {
            "job_index": spec.job_index,
            "model_label": spec.label,
            "model_family": spec.model_family,
            "seed": spec.seed,
            "role": role,
            "stage": stage,
            "metric_kind": metric_kind,
            "threshold_rule": rule,
            "threshold": threshold,
            "rate": rate(scores, threshold),
            "rows": int(len(scores)),
        }
        for rule, threshold in thresholds.items()
    ]


def grouped_attack_rows(
    spec: JobSpec,
    scores: np.ndarray,
    metadata: list[dict[str, str]],
    thresholds: dict[str, float],
    support_labels: set[str],
    stage: str,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for score, meta in zip(scores, metadata):
        seen = "seen_in_support" if meta["attack_label"] in support_labels else "unseen_in_support"
        groups[(meta["role"], meta["attack_label"], meta["device"], seen)].append(float(score))
    rows = []
    for (role, label, device, seen), values in sorted(groups.items()):
        arr = np.asarray(values, dtype=np.float64)
        for rule, threshold in thresholds.items():
            rows.append(
                {
                    "job_index": spec.job_index,
                    "model_label": spec.label,
                    "model_family": spec.model_family,
                    "seed": spec.seed,
                    "stage": stage,
                    "role": role,
                    "attack_label": label,
                    "device": device,
                    "support_coverage": seen,
                    "threshold_rule": rule,
                    "threshold": threshold,
                    "detection_rate": rate(arr, threshold),
                    "rows": int(len(arr)),
                    **qstats(arr),
                }
            )
    return rows


def freeze_config(
    job_dir: Path,
    spec: JobSpec,
    support_weight: float,
    center: np.ndarray,
    scale: np.ndarray,
    thresholds: dict[str, float],
    input_audit: dict[str, Any],
    smoke: bool,
) -> dict[str, Any]:
    payload = {
        "issue": ISSUE,
        "task": "diagnostic_offline_capability_not_online_deployment_not_formal_benchmark",
        "job_spec": asdict(spec),
        "effective_support_weight": support_weight,
        "transform": "id_benign_train_median_iqr_std_fallback_clip_abs_50",
        "transform_center_sha256": sha256_array(center),
        "transform_scale_sha256": sha256_array(scale),
        "thresholds": thresholds,
        "threshold_sources": {
            "id_q99": "id_benign_calib",
            "ood_guarded_q99": "max(id_benign_calib_q99, ood_benign_val_q99)",
            "support_val_recall90": "support_val_q10",
        },
        "roles_accessed_before_freeze": [
            "id_benign_train",
            "support_train",
            "id_benign_calib",
            "support_val",
            "ood_benign_val",
        ],
        "roles_forbidden_before_freeze": sorted(READ_ONLY_ROLES | REPORT_ONLY_ROLES),
        "support_candidate_reuse": False,
        "selected_support_bank_changed": False,
        "smoke": smoke,
        "input_audit": input_audit,
    }
    write_json(job_dir / "frozen_config_before_stress_and_final.json", payload)
    payload["frozen_config_sha256"] = sha256_file(job_dir / "frozen_config_before_stress_and_final.json")
    return payload


def run_job(job_index: int, smoke: bool) -> None:
    spec = next((item for item in JOB_SPECS if item.job_index == job_index), None)
    if spec is None:
        raise IndexError(f"job_index must be 1..{len(JOB_SPECS)}")
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "_smoke" if smoke else ""
    job_dir = OUT / f"job_{job_index:02d}_{spec.label}{suffix}"
    job_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    input_audit = validate_inputs()
    attack_root = Path(input_audit["attack_root"])
    cert_x = np.load(CERT_X, mmap_mode="r")
    roles = role_indices()
    required_benign = {"id_benign_train", "id_benign_calib", "ood_benign_val", "ood_benign_stress", "sealed_final_ood"}
    if not required_benign.issubset(roles):
        raise RuntimeError(f"Missing certified benign roles: {required_benign - set(roles)}")

    id_train_idx = limited_indices(roles["id_benign_train"], smoke, 4000)
    id_calib_idx = limited_indices(roles["id_benign_calib"], smoke, 2000)
    ood_val_idx = limited_indices(roles["ood_benign_val"], smoke, 2000)
    x_id_train_raw = np.asarray(cert_x[id_train_idx], dtype=np.float32)
    center, scale = fit_scaler(x_id_train_raw)

    support_rows, support_x_raw, support_train_ids, support_val_ids = load_support(attack_root, smoke)
    support_labels = {support_rows[i]["exact_attack_label"] for i in support_train_ids}
    x_id_train = transform(x_id_train_raw, center, scale)
    x_support_train = transform(support_x_raw[support_train_ids], center, scale)
    x_support_val = transform(support_x_raw[support_val_ids], center, scale)

    model, support_weight = make_model(spec, len(x_id_train), len(x_support_train))
    x_fit = np.vstack([x_id_train, x_support_train])
    y_fit = np.concatenate(
        [np.zeros(len(x_id_train), dtype=np.int8), np.ones(len(x_support_train), dtype=np.int8)]
    )
    sample_weight = np.concatenate(
        [np.ones(len(x_id_train), dtype=np.float64), np.full(len(x_support_train), support_weight, dtype=np.float64)]
    )
    fit_started = time.time()
    model.fit(x_fit, y_fit, sample_weight=sample_weight)
    fit_seconds = time.time() - fit_started

    id_calib_scores = score_in_batches(model, cert_x[id_calib_idx], center, scale)
    support_val_scores = positive_scores(model, x_support_val)
    ood_val_scores = score_in_batches(model, cert_x[ood_val_idx], center, scale)
    thresholds = thresholds_from_calibration(id_calib_scores, support_val_scores, ood_val_scores)

    frozen = freeze_config(job_dir, spec, support_weight, center, scale, thresholds, input_audit, smoke)
    with (job_dir / "model.pkl").open("wb") as f:
        pickle.dump(
            {
                "model": model,
                "center": center,
                "scale": scale,
                "frozen_config": frozen,
            },
            f,
            protocol=4,
        )

    distribution_rows = [
        distribution_row(spec, "id_benign_calib", id_calib_scores, "calibration"),
        distribution_row(spec, "support_val", support_val_scores, "calibration"),
        distribution_row(spec, "ood_benign_val", ood_val_scores, "calibration"),
    ]
    metric_rows = []
    metric_rows.extend(threshold_rows(spec, "id_benign_calib", id_calib_scores, thresholds, "calibration", "false_alarm_rate"))
    metric_rows.extend(threshold_rows(spec, "support_val", support_val_scores, thresholds, "calibration", "detection_rate"))
    metric_rows.extend(threshold_rows(spec, "ood_benign_val", ood_val_scores, thresholds, "calibration", "false_alarm_rate"))

    # Frozen read-only stress begins here. Nothing below may alter model, transform, or thresholds.
    ood_stress_idx = limited_indices(roles["ood_benign_stress"], smoke, 3000)
    ood_stress_scores = score_in_batches(model, cert_x[ood_stress_idx], center, scale)
    same_scores, same_meta = load_attack_role_scores(
        model, center, scale, attack_root, "same_file_time_forward_dev_query_exact", smoke
    )
    future_scores, future_meta = load_attack_role_scores(
        model, center, scale, attack_root, "dev_future_attack_query_exact", smoke
    )
    distribution_rows.extend(
        [
            distribution_row(spec, "ood_benign_stress", ood_stress_scores, "read_only_stress"),
            distribution_row(spec, "same_file_time_forward_dev_query_exact", same_scores, "read_only_stress"),
            distribution_row(spec, "dev_future_attack_query_exact", future_scores, "read_only_stress"),
        ]
    )
    metric_rows.extend(threshold_rows(spec, "ood_benign_stress", ood_stress_scores, thresholds, "read_only_stress", "false_alarm_rate"))
    metric_rows.extend(threshold_rows(spec, "same_file_time_forward_dev_query_exact", same_scores, thresholds, "read_only_stress", "detection_rate"))
    metric_rows.extend(threshold_rows(spec, "dev_future_attack_query_exact", future_scores, thresholds, "read_only_stress", "detection_rate"))

    attack_group_rows = grouped_attack_rows(
        spec, same_scores, same_meta, thresholds, support_labels, "read_only_stress"
    )
    attack_group_rows.extend(
        grouped_attack_rows(spec, future_scores, future_meta, thresholds, support_labels, "read_only_stress")
    )

    # Sealed final replay occurs once, after the configuration hash has been written.
    sealed_attack_scores, sealed_attack_meta = load_attack_role_scores(
        model, center, scale, attack_root, "sealed_final_attack_exact_realign", smoke
    )
    sealed_ood_idx = limited_indices(roles["sealed_final_ood"], smoke, 3000)
    sealed_ood_scores = score_in_batches(model, cert_x[sealed_ood_idx], center, scale)
    distribution_rows.extend(
        [
            distribution_row(spec, "sealed_final_attack_exact_realign", sealed_attack_scores, "report_only"),
            distribution_row(spec, "sealed_final_ood", sealed_ood_scores, "report_only"),
        ]
    )
    metric_rows.extend(threshold_rows(spec, "sealed_final_attack_exact_realign", sealed_attack_scores, thresholds, "report_only", "detection_rate"))
    metric_rows.extend(threshold_rows(spec, "sealed_final_ood", sealed_ood_scores, thresholds, "report_only", "false_alarm_rate"))
    attack_group_rows.extend(
        grouped_attack_rows(spec, sealed_attack_scores, sealed_attack_meta, thresholds, support_labels, "report_only")
    )

    dev_positive = np.concatenate([same_scores, future_scores])
    dev_auc, dev_ap = safe_auc(dev_positive, ood_stress_scores)
    final_auc, final_ap = safe_auc(sealed_attack_scores, sealed_ood_scores)

    write_csv(job_dir / "score_distributions.csv", distribution_rows)
    write_csv(job_dir / "threshold_role_metrics.csv", metric_rows)
    write_csv(job_dir / "attack_metrics_by_label_device.csv", attack_group_rows)
    write_csv(
        job_dir / "role_access_audit.csv",
        [
            {
                "stage": "fit",
                "allowed_roles": "|".join(sorted(TRAIN_ROLES)),
                "accessed_roles": "id_benign_train|support_train",
                "forbidden_roles_accessed": False,
            },
            {
                "stage": "calibration",
                "allowed_roles": "|".join(sorted(CALIBRATION_ROLES)),
                "accessed_roles": "id_benign_calib|support_val|ood_benign_val",
                "forbidden_roles_accessed": False,
            },
            {
                "stage": "read_only_stress",
                "allowed_roles": "|".join(sorted(READ_ONLY_ROLES)),
                "accessed_roles": "|".join(sorted(READ_ONLY_ROLES)),
                "forbidden_roles_accessed": False,
            },
            {
                "stage": "report_only",
                "allowed_roles": "|".join(sorted(REPORT_ONLY_ROLES)),
                "accessed_roles": "|".join(sorted(REPORT_ONLY_ROLES)),
                "forbidden_roles_accessed": False,
            },
        ],
    )

    result = {
        "issue": ISSUE,
        "job_spec": asdict(spec),
        "smoke": smoke,
        "effective_support_weight": support_weight,
        "fit_rows": {
            "id_benign_train": int(len(x_id_train)),
            "support_train": int(len(x_support_train)),
            "support_val": int(len(x_support_val)),
        },
        "support_labels": sorted(support_labels),
        "thresholds": thresholds,
        "dev_read_only_auc": dev_auc,
        "dev_read_only_average_precision": dev_ap,
        "sealed_final_auc_report_only": final_auc,
        "sealed_final_average_precision_report_only": final_ap,
        "fit_seconds": fit_seconds,
        "total_seconds": time.time() - started,
        "frozen_config_sha256": frozen["frozen_config_sha256"],
        "python": sys.version,
        "platform": platform.platform(),
        "formal_benchmark": False,
        "online_deployment_simulated": False,
        "candidate_pool_reused": False,
        "final_used_for_selection": False,
    }
    write_json(job_dir / "result.json", result)
    print(json.dumps(result, indent=2), flush=True)


def plan() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_audit = validate_inputs()
    write_csv(OUT / "job_matrix.csv", [asdict(spec) for spec in JOB_SPECS])
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "stage": "diagnostic_offline_capability_snapshot",
            "formal_benchmark": False,
            "online_deployment_simulated": False,
            "frontend": "Gotham PCAP-derived Kitsune115D",
            "support_bank": "issue27cf frozen 512 rows; support_train 385; support_val 127",
            "candidate_pool_reuse": False,
            "models": [asdict(spec) for spec in JOB_SPECS],
            "threshold_rules": list(THRESHOLD_RULES),
            "role_order": ROLE_ORDER,
            "report_only_selection": False,
            "input_audit": input_audit,
        },
    )
    write_md(
        OUT / "role_contract.md",
        [
            "# issue27ckb Offline Static Capability Role Contract",
            "",
            "This issue is an offline diagnostic capability snapshot. It is not an online deployment simulation and not a formal benchmark.",
            "",
            "## Fixed Role Order",
            "",
            "1. `id_benign_train`: fit the deterministic robust transform and benign class.",
            "2. frozen `support_train`: fit the attack class.",
            "3. `id_benign_calib`, frozen `support_val`, and `ood_benign_val`: compute three preregistered thresholds.",
            "4. Write and hash the frozen model/transform/threshold configuration.",
            "5. `ood_benign_stress` and certified dev query roles: read-only stress.",
            "6. sealed final attack/OOD: one report-only replay after freeze.",
            "",
            "## Forbidden",
            "",
            "- no use of the remaining 69,492 candidate pool;",
            "- no support reselection;",
            "- no threshold or model changes after reading stress/query/final roles;",
            "- no controller tuning, online update, or formal benchmark claim;",
            "- no claim that static offline performance establishes deployability.",
        ],
    )
    write_md(
        OUT / "command.txt",
        [
            f"python repo/ood/{Path(__file__).name} --mode plan",
            f"python repo/ood/{Path(__file__).name} --mode run-job --job-index $SLURM_ARRAY_TASK_ID",
            f"python repo/ood/{Path(__file__).name} --mode aggregate",
        ],
    )
    print(json.dumps({"status": "plan_ready", "jobs": len(JOB_SPECS), "out": str(OUT)}, indent=2))


def aggregate(smoke: bool) -> None:
    suffix = "_smoke" if smoke else ""
    job_dirs = [OUT / f"job_{spec.job_index:02d}_{spec.label}{suffix}" for spec in JOB_SPECS]
    missing = [str(path) for path in job_dirs if not (path / "result.json").exists()]
    if missing:
        raise FileNotFoundError("Missing job results:\n" + "\n".join(missing))

    result_rows = []
    metric_rows = []
    label_rows = []
    distribution_rows = []
    for spec, job_dir in zip(JOB_SPECS, job_dirs):
        result_rows.append(json.loads((job_dir / "result.json").read_text(encoding="utf-8")))
        metric_rows.extend(read_csv(job_dir / "threshold_role_metrics.csv"))
        label_rows.extend(read_csv(job_dir / "attack_metrics_by_label_device.csv"))
        distribution_rows.extend(read_csv(job_dir / "score_distributions.csv"))

    flat_results = []
    for result in result_rows:
        spec = result["job_spec"]
        flat_results.append(
            {
                **spec,
                "smoke": result["smoke"],
                "effective_support_weight": result["effective_support_weight"],
                "dev_read_only_auc": result["dev_read_only_auc"],
                "dev_read_only_average_precision": result["dev_read_only_average_precision"],
                "sealed_final_auc_report_only": result["sealed_final_auc_report_only"],
                "sealed_final_average_precision_report_only": result["sealed_final_average_precision_report_only"],
                "fit_seconds": result["fit_seconds"],
                "total_seconds": result["total_seconds"],
                "frozen_config_sha256": result["frozen_config_sha256"],
            }
        )
    write_csv(OUT / f"aggregate_job_results{suffix}.csv", flat_results)
    write_csv(OUT / f"aggregate_threshold_role_metrics{suffix}.csv", metric_rows)
    write_csv(OUT / f"aggregate_attack_metrics_by_label_device{suffix}.csv", label_rows)
    write_csv(OUT / f"aggregate_score_distributions{suffix}.csv", distribution_rows)

    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in metric_rows:
        grouped[(row["model_label"].rsplit("_seed", 1)[0], row["threshold_rule"], row["role"])].append(float(row["rate"]))
    summary_rows = []
    for (family, threshold_rule, role), values in sorted(grouped.items()):
        arr = np.asarray(values, dtype=np.float64)
        summary_rows.append(
            {
                "model_group": family,
                "threshold_rule": threshold_rule,
                "role": role,
                "mean_rate": float(np.mean(arr)),
                "min_rate": float(np.min(arr)),
                "max_rate": float(np.max(arr)),
                "std_rate": float(np.std(arr)),
                "jobs": len(arr),
            }
        )
    write_csv(OUT / f"aggregate_role_summary{suffix}.csv", summary_rows)
    write_md(
        OUT / f"summary{suffix}.md",
        [
            "# issue27ckb Offline Static Capability Snapshot",
            "",
            f"- mode: `{'smoke' if smoke else 'full_hpc'}`",
            f"- completed jobs: `{len(result_rows)}`",
            "- purpose: inspect static offline model capacity on the frozen exact-label support/data contract.",
            "- formal benchmark: no",
            "- online deployment simulation: no",
            "- candidate-pool reuse: no",
            "- final/report-only data used for selection: no",
            "",
            "No winning model is promoted automatically. Compare the aggregate tables, especially:",
            "",
            "- support validation versus certified future-query gap;",
            "- seen versus unseen exact attack labels;",
            "- OOD-val versus OOD-stress false-alarm inflation;",
            "- dev versus sealed-final replay stability.",
        ],
    )
    print(json.dumps({"status": "aggregate_complete", "jobs": len(result_rows), "smoke": smoke}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan", "run-job", "aggregate"], required=True)
    parser.add_argument("--job-index", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.mode == "plan":
        plan()
    elif args.mode == "run-job":
        job_index = args.job_index or int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
        if job_index <= 0:
            raise SystemExit("Missing --job-index or SLURM_ARRAY_TASK_ID")
        run_job(job_index, args.smoke)
    else:
        aggregate(args.smoke)


if __name__ == "__main__":
    main()
