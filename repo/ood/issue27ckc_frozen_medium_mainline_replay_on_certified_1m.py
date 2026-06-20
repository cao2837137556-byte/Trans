from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation as bp


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
PROJECT_ROOT = ROOT.parent.parent

ISSUE = "issue27ckc_frozen_medium_mainline_replay_on_certified_1m_2026-06-20"
OUT = ROOT / "runs" / ISSUE
ISSUE27CF = ROOT / "runs" / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
ISSUE27CH = ROOT / "runs" / "issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17"
ISSUE27BU = ROOT / "runs" / "issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10"

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
CERT_SIDECAR = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_sidecar.csv.gz"
FEATURE_SCHEMA = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_feature_schema.json"
SUPPORT_SIDECAR = ISSUE27CF / "support_bank_sidecar.csv"
CERTIFIED_CHUNKS = ISSUE27CH / "certified_chunk_manifest.csv"
CERTIFIED_SUBSET = ISSUE27CH / "certified_attack_subset_v1.json"
MEDIUM_SELECTION = ISSUE27BU / "unified_two_head_selection_audit.csv"

SEEDS = [42, 43, 44, 45, 46]
WINDOWS = [8, 32, 128]

# issue27ar/bo medium reference:
# (2400 ID + 4 * 1500 OOD) / (4 * 128 attack support) = 16.40625.
MEDIUM_WEIGHTED_NORMAL_TO_ATTACK_RATIO = 16.40625
OOD_WEIGHT = float(ar.FROZEN_CONFIG["ood_weight"])
STRICT_SUPPORT_WEIGHT = float(ar.FROZEN_CONFIG["support_weight"])

ATTACK_EVIDENCE_SUBSPACES = ["HH", "HH_HpHp"]
BENIGN_EVIDENCE_SUBSPACES = ["HH_jit", "MI_H_HHjit", "all115"]
PROTO_BUDGET = 32

PARENT_RISK_THRESHOLD = 0.50
PARENT_STRONG_MARGIN_Q = 0.00
PARENT_WEAK_MARGIN_Q = 0.25
PARENT_ATTACK_OUTER_NORM = 1.00

TEMPORAL_ATTACK_Q = 0.99
TEMPORAL_RISK_THRESHOLD = 0.90
TEMPORAL_STRONG_ATTACK_Q = 0.75
TEMPORAL_ATTACK_DISTANCE = 1.00


@dataclass(frozen=True)
class JobSpec:
    job_index: int
    weighting: str
    seed: int
    label: str


JOB_SPECS = [
    *[
        JobSpec(i + 1, "medium_mass_ratio_recalibrated", seed, f"medium_ratio_seed{seed}")
        for i, seed in enumerate(SEEDS)
    ],
    *[
        JobSpec(i + 1 + len(SEEDS), "strict_frozen_weight4", seed, f"strict_weight4_seed{seed}")
        for i, seed in enumerate(SEEDS)
    ],
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_auc(positive: np.ndarray, negative: np.ndarray) -> tuple[float, float]:
    positive = np.asarray(positive, dtype=np.float64)
    negative = np.asarray(negative, dtype=np.float64)
    if not len(positive) or not len(negative):
        return float("nan"), float("nan")
    y = np.concatenate([np.ones(len(positive), dtype=np.int8), np.zeros(len(negative), dtype=np.int8)])
    score = np.concatenate([positive, negative])
    return float(roc_auc_score(y, score)), float(average_precision_score(y, score))


def rate(mask: np.ndarray | pd.Series) -> float:
    arr = np.asarray(mask)
    return float(np.mean(arr.astype(bool))) if arr.size else float("nan")


def strict_rate(scores: np.ndarray, threshold: float) -> float:
    arr = np.asarray(scores, dtype=np.float64)
    return float(np.mean(arr > float(threshold))) if arr.size else float("nan")


def qstats(values: np.ndarray | pd.Series) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if not arr.size:
        return {k: float("nan") for k in ["min", "p50", "p90", "p95", "p99", "max", "mean", "std"]}
    return {
        "min": float(np.min(arr)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
    }


def discover_attack_root() -> Path:
    if (ATTACK_ROOT / "chunks").exists() and any((ATTACK_ROOT / "chunks").glob("chunk_*_X.npy")):
        return ATTACK_ROOT
    candidates = sorted(
        (
            PROJECT_ROOT
            / "supercompute_transfer"
            / "issue27cd_exact_label_attack_slurm_20260614"
            / "pullback_results"
        ).glob("extracted_*/datasets/gotham2025/derived/kitsune115_exact_label_targeted_attack_v1"),
        reverse=True,
    )
    for candidate in candidates:
        if (candidate / "chunks").exists() and any((candidate / "chunks").glob("chunk_*_X.npy")):
            return candidate
    raise FileNotFoundError(f"Exact-label attack chunks not found under {ATTACK_ROOT} or pullback fallbacks")


def validate_inputs() -> dict[str, Any]:
    attack_root = discover_attack_root()
    required = [
        CERT_X,
        CERT_SIDECAR,
        FEATURE_SCHEMA,
        SUPPORT_SIDECAR,
        CERTIFIED_CHUNKS,
        CERTIFIED_SUBSET,
        MEDIUM_SELECTION,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(missing))
    x = np.load(CERT_X, mmap_mode="r")
    if x.shape != (1_000_000, 115):
        raise RuntimeError(f"Unexpected certified X shape: {x.shape}")
    support_rows = read_csv(SUPPORT_SIDECAR)
    if len(support_rows) != 512:
        raise RuntimeError(f"Expected frozen 512-row support bank, got {len(support_rows)}")
    if sum(r["bank_partition"] == "support_train" for r in support_rows) != 385:
        raise RuntimeError("Frozen support_train count is not 385")
    if sum(r["bank_partition"] == "support_val" for r in support_rows) != 127:
        raise RuntimeError("Frozen support_val count is not 127")
    chunks = [r for r in read_csv(CERTIFIED_CHUNKS) if r["status"] == "complete"]
    missing_chunk_files = []
    for row in chunks:
        chunk = int(row["chunk_id"])
        for suffix in ["X.npy", "sidecar.csv"]:
            path = attack_root / "chunks" / f"chunk_{chunk:05d}_{suffix}"
            if not path.exists():
                missing_chunk_files.append(str(path))
    if missing_chunk_files:
        raise FileNotFoundError("Missing certified chunk files:\n" + "\n".join(missing_chunk_files[:30]))
    selection_rows = read_csv(MEDIUM_SELECTION)
    selected = [
        r
        for r in selection_rows
        if r.get("phase_mode") == "group_disjoint_source"
        and r.get("feature_set") == "parent_oodrisk_plus_temporal"
    ]
    if len(selected) != 1:
        raise RuntimeError("Cannot uniquely locate frozen medium parent+temporal selection")
    row = selected[0]
    expected = {
        "model_kind": "histgb_shallow",
        "attack_q": "0.99",
        "risk_threshold": "0.9",
        "strong_attack_q": "0.75",
        "d_attack_thr": "1.0",
    }
    for key, value in expected.items():
        if str(row.get(key)) != value:
            raise RuntimeError(f"Frozen medium config mismatch for {key}: {row.get(key)} != {value}")
    return {
        "cert_x_shape": list(x.shape),
        "attack_root": str(attack_root),
        "support_rows": len(support_rows),
        "certified_complete_chunks": len(chunks),
        "input_hashes": {
            "feature_schema": sha256_file(FEATURE_SCHEMA),
            "support_sidecar": sha256_file(SUPPORT_SIDECAR),
            "certified_chunk_manifest": sha256_file(CERTIFIED_CHUNKS),
            "certified_subset_contract": sha256_file(CERTIFIED_SUBSET),
            "medium_selection": sha256_file(MEDIUM_SELECTION),
        },
    }


def limited_indices(indices: np.ndarray, smoke: bool, limit: int) -> np.ndarray:
    return indices[: min(len(indices), limit)] if smoke else indices


def load_benign_roles(smoke: bool) -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame]]:
    indices: dict[str, list[int]] = defaultdict(list)
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    needed = {
        "id_benign_train",
        "id_benign_calib",
        "ood_benign_val",
        "ood_benign_stress",
        "sealed_final_ood",
    }
    with gzip.open(CERT_SIDECAR, "rt", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            role = row["role"]
            if role not in needed or row["model_ready_hint"].lower() != "true":
                continue
            idx = int(row["global_row_id"])
            indices[role].append(idx)
            if role != "id_benign_train":
                records[role].append(
                    {
                        "global_id": f"cert1m:{idx}",
                        "source_group": row["csv_member"],
                        "packet_timestamp_epoch": float(row["packet_timestamp_epoch"]),
                        "recorded_index": int(row["recorded_index_within_file"]),
                        "attack_label": "benign",
                        "device": Path(row["csv_member"]).stem,
                    }
                )
    out_idx: dict[str, np.ndarray] = {}
    out_rec: dict[str, pd.DataFrame] = {}
    smoke_limits = {
        "id_benign_train": 4000,
        "id_benign_calib": 3000,
        "ood_benign_val": 3000,
        "ood_benign_stress": 3000,
        "sealed_final_ood": 3000,
    }
    for role in needed:
        arr = np.asarray(indices[role], dtype=np.int64)
        if smoke:
            arr = arr[: smoke_limits[role]]
        out_idx[role] = arr
        if role != "id_benign_train":
            out_rec[role] = pd.DataFrame(records[role]).iloc[: len(arr)].reset_index(drop=True)
    return out_idx, out_rec


def add_source_disjoint_phase(records: pd.DataFrame) -> pd.DataFrame:
    out = records.copy()
    groups = sorted(out["source_group"].astype(str).unique().tolist())
    cut = max(1, min(len(groups) - 1, len(groups) // 2)) if len(groups) > 1 else 1
    fit_groups = set(groups[:cut])
    out["phase"] = np.where(out["source_group"].astype(str).isin(fit_groups), "fit", "select")
    if not np.any(out["phase"] == "select"):
        order = out.sort_values(["packet_timestamp_epoch", "recorded_index"], kind="mergesort").index
        half = max(1, len(order) // 2)
        out["phase"] = "select"
        out.loc[order[:half], "phase"] = "fit"
    return out


def add_support_val_phase(records: pd.DataFrame) -> pd.DataFrame:
    out = records.copy()
    out["phase"] = "select"
    for _, group in out.groupby(["source_group", "attack_label"], sort=True):
        order = group.sort_values(["packet_timestamp_epoch", "recorded_index"], kind="mergesort").index.tolist()
        if len(order) >= 2:
            out.loc[order[: max(1, len(order) // 2)], "phase"] = "fit"
    return out


def load_support(attack_root: Path) -> tuple[np.ndarray, pd.DataFrame, np.ndarray, np.ndarray]:
    rows = read_csv(SUPPORT_SIDECAR)
    cache: dict[int, np.ndarray] = {}
    features = []
    records = []
    for row in rows:
        chunk = int(row["chunk_id"])
        if chunk not in cache:
            cache[chunk] = np.load(attack_root / "chunks" / f"chunk_{chunk:05d}_X.npy", mmap_mode="r")
        features.append(np.asarray(cache[chunk][int(row["row_index_within_chunk"])], dtype=np.float32))
        records.append(
            {
                "global_id": row["sample_id"],
                "source_group": row["source_file"],
                "packet_timestamp_epoch": float(row["pcap_timestamp"]),
                "recorded_index": int(row["csv_row_index"]),
                "attack_label": row["exact_attack_label"],
                "device": row["device_or_source_group"],
                "partition": row["bank_partition"],
            }
        )
    x = np.vstack(features)
    frame = pd.DataFrame(records)
    train = np.flatnonzero(frame["partition"].to_numpy() == "support_train")
    val = np.flatnonzero(frame["partition"].to_numpy() == "support_val")
    val_frame = add_support_val_phase(frame.iloc[val].reset_index(drop=True))
    frame.loc[val, "phase"] = val_frame["phase"].to_numpy()
    frame.loc[train, "phase"] = "support_train"
    return x, frame, train, val


def load_attack_role(attack_root: Path, role: str, smoke: bool, smoke_limit: int = 3000) -> tuple[np.ndarray, pd.DataFrame]:
    chunks = [
        row
        for row in read_csv(CERTIFIED_CHUNKS)
        if row["status"] == "complete" and row["role"] == role
    ]
    x_parts: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    remaining = smoke_limit if smoke else None
    for row in chunks:
        chunk = int(row["chunk_id"])
        x = np.load(attack_root / "chunks" / f"chunk_{chunk:05d}_X.npy", mmap_mode="r")
        sidecar = read_csv(attack_root / "chunks" / f"chunk_{chunk:05d}_sidecar.csv")
        if len(x) != len(sidecar) or len(x) != int(row["emitted_rows"]):
            raise RuntimeError(f"Chunk {chunk} feature/sidecar/manifest length mismatch")
        take = len(x) if remaining is None else min(len(x), remaining)
        if take <= 0:
            break
        x_parts.append(np.asarray(x[:take], dtype=np.float32))
        for i, item in enumerate(sidecar[:take]):
            records.append(
                {
                    "global_id": f"chunk{chunk}:{i}",
                    "source_group": item["csv_member"],
                    "packet_timestamp_epoch": float(item["packet_timestamp_epoch"]),
                    "recorded_index": int(item["csv_row_index"]),
                    "attack_label": item["exact_csv_label"],
                    "device": item["device"],
                    "chunk_id": chunk,
                }
            )
        if remaining is not None:
            remaining -= take
    return (
        np.concatenate(x_parts, axis=0) if x_parts else np.empty((0, 115), dtype=np.float32),
        pd.DataFrame(records),
    )


class FrozenAttackHistGB:
    def __init__(self, seed: int):
        self.seed = int(seed)
        self.model = HistGradientBoostingClassifier(
            max_depth=int(ar.FROZEN_CONFIG["max_depth"]),
            max_iter=int(ar.FROZEN_CONFIG["max_iter"]),
            learning_rate=float(ar.FROZEN_CONFIG["learning_rate"]),
            l2_regularization=float(ar.FROZEN_CONFIG["l2_regularization"]),
            random_state=self.seed,
        )
        self.score_direction = 1.0
        self.direction_check: dict[str, Any] = {}

    def fit(self, x_id: np.ndarray, x_ood: np.ndarray, x_support: np.ndarray, support_weight: float) -> None:
        x_fit = np.vstack([x_id, x_ood, x_support])
        y_fit = np.concatenate(
            [
                np.zeros(len(x_id), dtype=np.int8),
                np.zeros(len(x_ood), dtype=np.int8),
                np.ones(len(x_support), dtype=np.int8),
            ]
        )
        weights = np.concatenate(
            [
                np.ones(len(x_id), dtype=np.float64),
                np.full(len(x_ood), OOD_WEIGHT, dtype=np.float64),
                np.full(len(x_support), support_weight, dtype=np.float64),
            ]
        )
        self.model.fit(x_fit, y_fit, sample_weight=weights)
        raw_id = self.raw_score(x_id)
        raw_ood = self.raw_score(x_ood)
        raw_support = self.raw_score(x_support)
        if float(np.mean(raw_support)) < max(float(np.mean(raw_id)), float(np.mean(raw_ood))):
            self.score_direction = -1.0
        self.direction_check = {
            "raw_id_mean": float(np.mean(raw_id)),
            "raw_ood_mean": float(np.mean(raw_ood)),
            "raw_support_mean": float(np.mean(raw_support)),
            "score_direction": self.score_direction,
        }

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        return np.asarray(proba[:, classes.index(1)], dtype=np.float64)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)


def fit_shallow_histgb(x: np.ndarray, y: np.ndarray, seed: int) -> HistGradientBoostingClassifier:
    if len(np.unique(y)) != 2:
        raise RuntimeError(f"Expected binary fit labels, got {np.unique(y).tolist()}")
    model = HistGradientBoostingClassifier(
        max_iter=80,
        learning_rate=0.05,
        max_leaf_nodes=8,
        l2_regularization=0.1,
        random_state=seed,
    )
    model.fit(np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.int8))
    return model


def positive_score(model: Any, x: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    return np.asarray(proba[:, classes.index(1)], dtype=np.float64)


def build_evidence_banks(
    subspaces: dict[str, np.ndarray],
    x_id_train: np.ndarray,
    x_id_calib_fit: np.ndarray,
    x_ood_fit: np.ndarray,
    x_ood_select: np.ndarray,
    x_support_train: np.ndarray,
    x_support_val_fit: np.ndarray,
) -> tuple[dict[str, bp.ProtoBank], list[dict[str, Any]]]:
    banks: dict[str, bp.ProtoBank] = {}
    rows = []
    attack_radius = x_support_val_fit if len(x_support_val_fit) else x_support_train
    for name in ATTACK_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        bank = bp.ProtoBank(
            f"attack_{name}",
            x_support_train[:, idx],
            PROTO_BUDGET,
            {
                "core": (attack_radius[:, idx], 0.95),
                "outer": (attack_radius[:, idx], 0.99),
            },
        )
        banks[f"attack_{name}"] = bank
        rows.append(
            {
                "bank": f"attack_{name}",
                "fit_rows": bank.fit_rows,
                "core_radius": bank.radii["core"],
                "outer_radius": bank.radii["outer"],
            }
        )
    benign_fit = np.vstack([x_id_train, x_ood_fit])
    benign_radius = np.vstack([x_id_calib_fit, x_ood_select])
    for name in BENIGN_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        bank = bp.ProtoBank(
            f"benign_{name}",
            benign_fit[:, idx],
            PROTO_BUDGET,
            {"core": (benign_radius[:, idx], 0.95)},
        )
        banks[f"benign_{name}"] = bank
        rows.append(
            {
                "bank": f"benign_{name}",
                "fit_rows": bank.fit_rows,
                "core_radius": bank.radii["core"],
                "outer_radius": "",
            }
        )
    return banks, rows


def evidence_features(
    x: np.ndarray,
    attack_score: np.ndarray,
    attack_threshold: float,
    banks: dict[str, bp.ProtoBank],
    subspaces: dict[str, np.ndarray],
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    margin = np.asarray(attack_score, dtype=np.float64) - float(attack_threshold)
    cols = [margin, np.maximum(margin, 0.0)]
    attack_norms = []
    benign_norms = []
    for name in ATTACK_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        bank = banks[f"attack_{name}"]
        raw_distance = bank.raw_distance(x[:, idx])
        core = raw_distance / bank.radii["core"]
        outer = raw_distance / bank.radii["outer"]
        cols.extend([core, outer])
        attack_norms.append(outer)
    for name in BENIGN_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        core = banks[f"benign_{name}"].norm_distance(x[:, idx], "core")
        cols.append(core)
        benign_norms.append(core)
    min_attack = np.min(np.vstack(attack_norms), axis=0)
    min_benign = np.min(np.vstack(benign_norms), axis=0)
    cols.extend([min_attack, min_benign, min_benign - min_attack])
    aux = {
        "attack_margin": margin,
        "raw_alarm": margin > 0.0,
        "d_attack_outer_min": min_attack,
        "d_benign_core_min": min_benign,
        "benign_minus_attack_distance": min_benign - min_attack,
    }
    return np.column_stack(cols).astype(np.float32), aux


def fit_parent_risk(
    seed: int,
    role_features: dict[str, np.ndarray],
    role_aux: dict[str, dict[str, np.ndarray]],
) -> tuple[Any, dict[str, float], list[dict[str, Any]]]:
    parts = []
    labels = []
    audit = []
    for role, risk_label in [("id_calib", 1), ("ood_val", 1), ("support_val", 0)]:
        phase = role_features[f"{role}_phase"]
        idx = np.flatnonzero((phase == "fit") & role_aux[role]["raw_alarm"])
        source = "fit_raw_alarm_rows"
        if not len(idx):
            fit_idx = np.flatnonzero(phase == "fit")
            if not len(fit_idx):
                raise RuntimeError(f"No fit rows available for parent OOD-risk role {role}")
            margin = role_aux[role]["attack_margin"][fit_idx]
            keep = max(1, int(np.ceil(0.01 * len(fit_idx)))) if risk_label == 1 else len(fit_idx)
            idx = fit_idx[np.argsort(-margin)[:keep]]
            source = "fallback_highest_attack_margin_fit_tail"
        parts.append(role_features[role][idx])
        labels.append(np.full(len(idx), risk_label, dtype=np.int8))
        audit.append(
            {
                "role": role,
                "risk_label": risk_label,
                "fit_rows_used": len(idx),
                "row_source": source,
            }
        )
    model = fit_shallow_histgb(np.vstack(parts), np.concatenate(labels), seed)
    support_phase = role_features["support_val_phase"]
    support_margin = role_aux["support_val"]["attack_margin"][
        (support_phase == "fit") & role_aux["support_val"]["raw_alarm"]
    ]
    if not len(support_margin):
        support_margin = role_aux["support_val"]["attack_margin"][support_phase == "fit"]
    params = {
        "risk_threshold": PARENT_RISK_THRESHOLD,
        "strong_margin_floor": float(np.quantile(support_margin, PARENT_STRONG_MARGIN_Q)),
        "weak_margin_ceiling": float(np.quantile(support_margin, PARENT_WEAK_MARGIN_Q)),
        "attack_outer_norm": PARENT_ATTACK_OUTER_NORM,
    }
    return model, params, audit


def parent_masks(aux: dict[str, np.ndarray], risk: np.ndarray, params: dict[str, float]) -> dict[str, np.ndarray]:
    raw = np.asarray(aux["raw_alarm"], dtype=bool)
    strong = raw & (aux["attack_margin"] >= params["strong_margin_floor"]) & (
        aux["d_attack_outer_min"] <= params["attack_outer_norm"]
    )
    high_risk = raw & (risk >= params["risk_threshold"])
    weak = raw & (
        (aux["attack_margin"] <= params["weak_margin_ceiling"])
        | (aux["d_attack_outer_min"] > params["attack_outer_norm"])
    )
    suppress = high_risk & weak & (~strong)
    return {
        "raw_alarm": raw,
        "hard_alarm": raw & (~suppress),
        "suppress": suppress,
        "high_ood_risk": high_risk,
        "strong_attack": strong,
    }


def rolling_prior(values: pd.Series, window: int) -> pd.Series:
    return values.astype(float).shift(1).rolling(window, min_periods=1).mean().fillna(0.0)


def add_past_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    order_cols = ["packet_timestamp_epoch", "recorded_index", "global_id"]
    role_order = out.sort_values(order_cols, kind="mergesort").index
    for window in WINDOWS:
        for col in ["raw_alarm", "hard_alarm", "suppress", "high_ood_risk", "strong_attack"]:
            values = rolling_prior(out.loc[role_order, col], window)
            out.loc[role_order, f"past_role_{col}_rate_w{window}"] = values.to_numpy()
        for col in ["attack_margin", "ood_risk", "d_attack_outer_min", "d_benign_core_min"]:
            values = rolling_prior(out.loc[role_order, col], window)
            out.loc[role_order, f"past_role_{col}_mean_w{window}"] = values.to_numpy()
    for window in WINDOWS:
        for col in ["raw_alarm", "hard_alarm", "suppress", "high_ood_risk", "strong_attack"]:
            name = f"past_source_{col}_rate_w{window}"
            out[name] = 0.0
        for col in ["attack_margin", "ood_risk", "d_attack_outer_min", "d_benign_core_min"]:
            name = f"past_source_{col}_mean_w{window}"
            out[name] = 0.0
    out["past_source_raw_alarm_run_before"] = 0
    for _, group in out.groupby("source_group", sort=False):
        idx = group.sort_values(order_cols, kind="mergesort").index
        for window in WINDOWS:
            for col in ["raw_alarm", "hard_alarm", "suppress", "high_ood_risk", "strong_attack"]:
                out.loc[idx, f"past_source_{col}_rate_w{window}"] = rolling_prior(out.loc[idx, col], window).to_numpy()
            for col in ["attack_margin", "ood_risk", "d_attack_outer_min", "d_benign_core_min"]:
                out.loc[idx, f"past_source_{col}_mean_w{window}"] = rolling_prior(out.loc[idx, col], window).to_numpy()
        run = 0
        before = []
        for raw in out.loc[idx, "raw_alarm"].astype(bool):
            before.append(run)
            run = run + 1 if raw else 0
        out.loc[idx, "past_source_raw_alarm_run_before"] = before
    return out


TEMPORAL_FEATURES = [
    "attack_margin",
    "ood_risk",
    "d_attack_outer_min",
    "d_benign_core_min",
    "benign_minus_attack_distance",
    "past_role_raw_alarm_rate_w8",
    "past_role_raw_alarm_rate_w32",
    "past_role_raw_alarm_rate_w128",
    "past_source_raw_alarm_rate_w8",
    "past_source_raw_alarm_rate_w32",
    "past_source_raw_alarm_rate_w128",
    "past_source_high_ood_risk_rate_w32",
    "past_source_strong_attack_rate_w32",
    "past_source_attack_margin_mean_w32",
    "past_source_ood_risk_mean_w32",
    "past_source_d_attack_outer_min_mean_w32",
    "past_source_d_benign_core_min_mean_w32",
    "past_source_raw_alarm_run_before",
]


def build_role_frame(
    role: str,
    role_kind: str,
    x: np.ndarray,
    records: pd.DataFrame,
    attack_model: FrozenAttackHistGB,
    attack_threshold: float,
    banks: dict[str, bp.ProtoBank],
    subspaces: dict[str, np.ndarray],
    parent_model: Any,
    parent_params: dict[str, float],
) -> pd.DataFrame:
    if len(x) != len(records):
        raise RuntimeError(f"Feature/record mismatch for {role}: {len(x)} != {len(records)}")
    score = attack_model.score(x)
    evidence, aux = evidence_features(x, score, attack_threshold, banks, subspaces)
    risk = positive_score(parent_model, evidence)
    masks = parent_masks(aux, risk, parent_params)
    out = records.copy().reset_index(drop=True)
    out["role"] = role
    out["role_kind"] = role_kind
    out["attack_score"] = score
    out["attack_margin"] = aux["attack_margin"]
    out["ood_risk"] = risk
    out["d_attack_outer_min"] = aux["d_attack_outer_min"]
    out["d_benign_core_min"] = aux["d_benign_core_min"]
    out["benign_minus_attack_distance"] = aux["benign_minus_attack_distance"]
    for key, values in masks.items():
        out[key] = values
    return add_past_features(out)


def fit_temporal_heads(seed: int, frames: dict[str, pd.DataFrame]) -> tuple[Any, Any, dict[str, float], list[dict[str, Any]]]:
    fit_parts = []
    y_attack_parts = []
    y_risk_parts = []
    audit = []
    for role in ["id_calib", "ood_val", "support_val"]:
        frame = frames[role]
        fit = frame[frame["phase"] == "fit"]
        fit_parts.append(fit[TEMPORAL_FEATURES].to_numpy(dtype=np.float32))
        is_attack = role == "support_val"
        y_attack_parts.append(np.full(len(fit), int(is_attack), dtype=np.int8))
        y_risk_parts.append(np.full(len(fit), int(not is_attack), dtype=np.int8))
        audit.append({"role": role, "fit_rows": len(fit), "attack_label": int(is_attack), "ood_risk_label": int(not is_attack)})
    x_fit = np.vstack(fit_parts)
    y_attack = np.concatenate(y_attack_parts)
    y_risk = np.concatenate(y_risk_parts)
    attack_head = fit_shallow_histgb(x_fit, y_attack, seed)
    risk_head = fit_shallow_histgb(x_fit, y_risk, seed)
    id_select = frames["id_calib"][frames["id_calib"]["phase"] == "select"]
    support_fit = frames["support_val"][frames["support_val"]["phase"] == "fit"]
    id_scores = positive_score(attack_head, id_select[TEMPORAL_FEATURES].to_numpy(dtype=np.float32))
    support_scores = positive_score(attack_head, support_fit[TEMPORAL_FEATURES].to_numpy(dtype=np.float32))
    attack_threshold = float(np.quantile(id_scores, TEMPORAL_ATTACK_Q))
    strong_threshold = max(float(np.quantile(support_scores, TEMPORAL_STRONG_ATTACK_Q)), attack_threshold)
    params = {
        "attack_threshold": attack_threshold,
        "strong_attack_threshold": strong_threshold,
        "risk_threshold": TEMPORAL_RISK_THRESHOLD,
        "d_attack_thr": TEMPORAL_ATTACK_DISTANCE,
    }
    return attack_head, risk_head, params, audit


def apply_temporal_controller(frame: pd.DataFrame, attack_head: Any, risk_head: Any, params: dict[str, float]) -> pd.DataFrame:
    out = frame.copy()
    x = out[TEMPORAL_FEATURES].to_numpy(dtype=np.float32)
    attack = positive_score(attack_head, x)
    risk = positive_score(risk_head, x)
    raw = attack > params["attack_threshold"]
    strong = raw & (attack >= params["strong_attack_threshold"]) & (
        out["d_attack_outer_min"].to_numpy(dtype=np.float64) <= params["d_attack_thr"]
    )
    high_risk = raw & (risk >= params["risk_threshold"])
    suppress = high_risk & (~strong)
    out["temporal_attack_score"] = attack
    out["temporal_ood_risk"] = risk
    out["temporal_raw_alarm"] = raw
    out["temporal_strong_attack"] = strong
    out["temporal_high_ood_risk"] = high_risk
    out["temporal_suppress"] = suppress
    out["temporal_review"] = False
    out["temporal_hard_alarm"] = raw & (~suppress)
    out["temporal_unknown"] = (~raw) & (risk >= params["risk_threshold"])
    return out


def summarize_role(job: JobSpec, frame: pd.DataFrame, stage: str) -> dict[str, Any]:
    return {
        "job_index": job.job_index,
        "job_label": job.label,
        "weighting": job.weighting,
        "seed": job.seed,
        "role": str(frame["role"].iloc[0]),
        "role_kind": str(frame["role_kind"].iloc[0]),
        "stage": stage,
        "rows": len(frame),
        "parent_raw_alarm_rate": rate(frame["raw_alarm"]),
        "parent_hard_alarm_rate": rate(frame["hard_alarm"]),
        "parent_suppress_rate": rate(frame["suppress"]),
        "temporal_raw_alarm_rate": rate(frame["temporal_raw_alarm"]),
        "temporal_hard_alarm_rate": rate(frame["temporal_hard_alarm"]),
        "temporal_suppress_rate": rate(frame["temporal_suppress"]),
        "temporal_review_rate": rate(frame["temporal_review"]),
        "temporal_unknown_rate": rate(frame["temporal_unknown"]),
        "attack_score_mean": float(frame["temporal_attack_score"].mean()),
        "ood_risk_mean": float(frame["temporal_ood_risk"].mean()),
    }


def grouped_attack_metrics(job: JobSpec, frame: pd.DataFrame, support_labels: set[str], stage: str) -> list[dict[str, Any]]:
    rows = []
    for (label, device), group in frame.groupby(["attack_label", "device"], sort=True):
        rows.append(
            {
                "job_index": job.job_index,
                "job_label": job.label,
                "weighting": job.weighting,
                "seed": job.seed,
                "stage": stage,
                "role": str(group["role"].iloc[0]),
                "attack_label": label,
                "device": device,
                "support_coverage": "seen_in_support" if label in support_labels else "unseen_in_support",
                "rows": len(group),
                "parent_hard_detection": rate(group["hard_alarm"]),
                "temporal_hard_detection": rate(group["temporal_hard_alarm"]),
                "temporal_suppress_rate": rate(group["temporal_suppress"]),
                **{f"temporal_attack_{k}": v for k, v in qstats(group["temporal_attack_score"]).items()},
            }
        )
    return rows


def threshold_free_row(
    job: JobSpec,
    name: str,
    positive: pd.DataFrame,
    negative: pd.DataFrame,
    stage: str,
) -> dict[str, Any]:
    attack_auc, attack_ap = safe_auc(
        positive["temporal_attack_score"].to_numpy(),
        negative["temporal_attack_score"].to_numpy(),
    )
    hard_auc, hard_ap = safe_auc(
        positive["attack_score"].to_numpy(),
        negative["attack_score"].to_numpy(),
    )
    return {
        "job_index": job.job_index,
        "job_label": job.label,
        "weighting": job.weighting,
        "seed": job.seed,
        "comparison": name,
        "stage": stage,
        "positive_rows": len(positive),
        "negative_rows": len(negative),
        "temporal_attack_auc": attack_auc,
        "temporal_attack_ap": attack_ap,
        "parent_attack_auc": hard_auc,
        "parent_attack_ap": hard_ap,
    }


def freeze_config(
    job_dir: Path,
    job: JobSpec,
    support_weight: float,
    input_audit: dict[str, Any],
    attack_threshold: float,
    parent_params: dict[str, float],
    temporal_params: dict[str, float],
    bank_audit: list[dict[str, Any]],
    parent_fit_audit: list[dict[str, Any]],
    temporal_fit_audit: list[dict[str, Any]],
    smoke: bool,
) -> dict[str, Any]:
    payload = {
        "issue": ISSUE,
        "task": "frozen_medium_architecture_offline_role_separated_replay_not_mixed_stream_not_formal_benchmark",
        "job_spec": asdict(job),
        "smoke": smoke,
        "frontend": "Kitsune115D fixed",
        "architecture": [
            "frozen_full115_attack_scorer",
            "parent_ood_risk",
            "past_only_temporal_attack_and_ood_heads",
            "bounded_controller",
        ],
        "attack_scorer_config": ar.FROZEN_CONFIG,
        "effective_support_weight": support_weight,
        "medium_weighted_normal_to_attack_ratio_reference": MEDIUM_WEIGHTED_NORMAL_TO_ATTACK_RATIO,
        "parent_attack_threshold": attack_threshold,
        "parent_params": parent_params,
        "temporal_params": temporal_params,
        "temporal_features": TEMPORAL_FEATURES,
        "bank_audit": bank_audit,
        "parent_fit_audit": parent_fit_audit,
        "temporal_fit_audit": temporal_fit_audit,
        "fit_roles": [
            "id_benign_train",
            "derived_source_disjoint_ood_benign_val_fit",
            "support_train_385",
            "derived_fit_halves_of_id_calib_ood_val_support_val_for_parent_and_temporal_heads",
        ],
        "selection_roles": [
            "derived_select_halves_of_id_calib_ood_val_support_val",
        ],
        "read_only_after_freeze": [
            "ood_benign_stress",
            "same_file_time_forward_dev_query_exact",
            "dev_future_attack_query_exact",
        ],
        "report_only_after_freeze": [
            "sealed_final_ood",
            "sealed_final_attack_exact_realign",
        ],
        "input_audit": input_audit,
    }
    path = job_dir / "frozen_config_before_stress_query_and_final.json"
    write_json(path, payload)
    payload["frozen_config_sha256"] = sha256_file(path)
    return payload


def run_job(job_index: int, smoke: bool) -> None:
    job = next((spec for spec in JOB_SPECS if spec.job_index == job_index), None)
    if job is None:
        raise IndexError(f"job-index must be 1..{len(JOB_SPECS)}")
    suffix = "_smoke" if smoke else ""
    job_dir = OUT / f"job_{job.job_index:02d}_{job.label}{suffix}"
    job_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    input_audit = validate_inputs()
    attack_root = Path(input_audit["attack_root"])
    cert_x = np.load(CERT_X, mmap_mode="r")
    schema = json.loads(FEATURE_SCHEMA.read_text(encoding="utf-8"))
    subspaces = bp.build_subspaces(schema)

    benign_idx, benign_records = load_benign_roles(smoke)
    benign_records["id_benign_calib"] = add_source_disjoint_phase(benign_records["id_benign_calib"])
    benign_records["ood_benign_val"] = add_source_disjoint_phase(benign_records["ood_benign_val"])
    support_x, support_records, support_train_idx, support_val_idx = load_support(attack_root)
    support_val_records = support_records.iloc[support_val_idx].reset_index(drop=True)
    support_val_phase = support_val_records["phase"].to_numpy()

    id_train_idx = limited_indices(benign_idx["id_benign_train"], smoke, 4000)
    id_calib_x = np.asarray(cert_x[benign_idx["id_benign_calib"]], dtype=np.float32)
    id_calib_phase = benign_records["id_benign_calib"]["phase"].to_numpy()
    ood_val_x = np.asarray(cert_x[benign_idx["ood_benign_val"]], dtype=np.float32)
    ood_val_phase = benign_records["ood_benign_val"]["phase"].to_numpy()
    x_id_train = np.asarray(cert_x[id_train_idx], dtype=np.float32)
    x_ood_fit = ood_val_x[ood_val_phase == "fit"]
    x_ood_select = ood_val_x[ood_val_phase == "select"]
    x_support_train = support_x[support_train_idx]
    x_support_val = support_x[support_val_idx]
    x_support_val_fit = x_support_val[support_val_phase == "fit"]

    if job.weighting == "strict_frozen_weight4":
        support_weight = STRICT_SUPPORT_WEIGHT
    else:
        support_weight = float(
            (len(x_id_train) + OOD_WEIGHT * len(x_ood_fit))
            / (MEDIUM_WEIGHTED_NORMAL_TO_ATTACK_RATIO * max(1, len(x_support_train)))
        )

    attack_model = FrozenAttackHistGB(job.seed)
    attack_model.fit(x_id_train, x_ood_fit, x_support_train, support_weight)
    id_select_scores = attack_model.score(id_calib_x[id_calib_phase == "select"])
    parent_attack_threshold = float(np.quantile(id_select_scores, 0.99))

    banks, bank_audit = build_evidence_banks(
        subspaces,
        x_id_train,
        id_calib_x[id_calib_phase == "fit"],
        x_ood_fit,
        x_ood_select,
        x_support_train,
        x_support_val_fit,
    )

    pre_roles = {
        "id_calib": (
            id_calib_x,
            benign_records["id_benign_calib"].rename(columns={"phase": "phase"}).copy(),
            "benign_id",
        ),
        "ood_val": (
            ood_val_x,
            benign_records["ood_benign_val"].rename(columns={"phase": "phase"}).copy(),
            "benign_ood",
        ),
        "support_val": (
            x_support_val,
            support_val_records.copy(),
            "attack",
        ),
    }
    role_evidence: dict[str, np.ndarray] = {}
    role_aux: dict[str, dict[str, np.ndarray]] = {}
    for role, (x_role, _records, _kind) in pre_roles.items():
        score = attack_model.score(x_role)
        evidence, aux = evidence_features(x_role, score, parent_attack_threshold, banks, subspaces)
        role_evidence[role] = evidence
        role_evidence[f"{role}_phase"] = pre_roles[role][1]["phase"].to_numpy()
        role_aux[role] = aux

    parent_model, parent_params, parent_fit_audit = fit_parent_risk(job.seed, role_evidence, role_aux)
    pre_frames: dict[str, pd.DataFrame] = {}
    for role, (x_role, records, kind) in pre_roles.items():
        pre_frames[role] = build_role_frame(
            role,
            kind,
            x_role,
            records,
            attack_model,
            parent_attack_threshold,
            banks,
            subspaces,
            parent_model,
            parent_params,
        )

    temporal_attack_head, temporal_risk_head, temporal_params, temporal_fit_audit = fit_temporal_heads(
        job.seed, pre_frames
    )
    scored_pre = {
        role: apply_temporal_controller(frame, temporal_attack_head, temporal_risk_head, temporal_params)
        for role, frame in pre_frames.items()
    }

    frozen = freeze_config(
        job_dir,
        job,
        support_weight,
        input_audit,
        parent_attack_threshold,
        parent_params,
        temporal_params,
        bank_audit,
        parent_fit_audit,
        temporal_fit_audit,
        smoke,
    )

    # Read-only stress/query and sealed report-only access starts after the frozen hash exists.
    stress_x = np.asarray(cert_x[benign_idx["ood_benign_stress"]], dtype=np.float32)
    sealed_ood_x = np.asarray(cert_x[benign_idx["sealed_final_ood"]], dtype=np.float32)
    same_x, same_records = load_attack_role(attack_root, "same_file_time_forward_dev_query_exact", smoke)
    future_x, future_records = load_attack_role(attack_root, "dev_future_attack_query_exact", smoke)
    sealed_attack_x, sealed_attack_records = load_attack_role(
        attack_root, "sealed_final_attack_exact_realign", smoke
    )

    post_roles = {
        "ood_stress": (stress_x, benign_records["ood_benign_stress"], "benign_ood", "read_only"),
        "same_file_query": (same_x, same_records, "attack", "read_only"),
        "future_query": (future_x, future_records, "attack", "read_only"),
        "sealed_final_ood": (
            sealed_ood_x,
            benign_records["sealed_final_ood"],
            "benign_ood",
            "report_only",
        ),
        "sealed_final_attack": (
            sealed_attack_x,
            sealed_attack_records,
            "attack",
            "report_only",
        ),
    }
    scored_post: dict[str, pd.DataFrame] = {}
    for role, (x_role, records, kind, _stage) in post_roles.items():
        frame = build_role_frame(
            role,
            kind,
            x_role,
            records,
            attack_model,
            parent_attack_threshold,
            banks,
            subspaces,
            parent_model,
            parent_params,
        )
        scored_post[role] = apply_temporal_controller(
            frame, temporal_attack_head, temporal_risk_head, temporal_params
        )

    role_rows = []
    for role, frame in scored_pre.items():
        role_rows.append(summarize_role(job, frame[frame["phase"] == "select"], "calibration_select"))
    for role, frame in scored_post.items():
        role_rows.append(summarize_role(job, frame, post_roles[role][3]))

    support_labels = set(support_records.loc[support_train_idx, "attack_label"].astype(str))
    grouped_rows = []
    grouped_rows.extend(
        grouped_attack_metrics(
            job,
            scored_pre["support_val"][scored_pre["support_val"]["phase"] == "select"],
            support_labels,
            "calibration_select",
        )
    )
    for role in ["same_file_query", "future_query", "sealed_final_attack"]:
        grouped_rows.extend(
            grouped_attack_metrics(job, scored_post[role], support_labels, post_roles[role][3])
        )

    threshold_rows = [
        threshold_free_row(
            job,
            "support_val_select_vs_ood_val_select",
            scored_pre["support_val"][scored_pre["support_val"]["phase"] == "select"],
            scored_pre["ood_val"][scored_pre["ood_val"]["phase"] == "select"],
            "calibration_select",
        ),
        threshold_free_row(
            job,
            "dev_query_union_vs_ood_stress",
            pd.concat([scored_post["same_file_query"], scored_post["future_query"]], ignore_index=True),
            scored_post["ood_stress"],
            "read_only",
        ),
        threshold_free_row(
            job,
            "sealed_attack_vs_sealed_ood",
            scored_post["sealed_final_attack"],
            scored_post["sealed_final_ood"],
            "report_only",
        ),
    ]

    id_select_temporal = scored_pre["id_calib"].loc[
        scored_pre["id_calib"]["phase"] == "select", "temporal_attack_score"
    ].to_numpy()
    tie_rows = [
        {
            "job_index": job.job_index,
            "job_label": job.label,
            "score": "parent_attack_score",
            "threshold": parent_attack_threshold,
            "equal_mass": float(np.mean(id_select_scores == parent_attack_threshold)),
            "strict_above_mass": strict_rate(id_select_scores, parent_attack_threshold),
        },
        {
            "job_index": job.job_index,
            "job_label": job.label,
            "score": "temporal_attack_score",
            "threshold": temporal_params["attack_threshold"],
            "equal_mass": float(np.mean(id_select_temporal == temporal_params["attack_threshold"])),
            "strict_above_mass": strict_rate(id_select_temporal, temporal_params["attack_threshold"]),
        },
    ]

    write_csv(job_dir / "role_metrics.csv", role_rows)
    write_csv(job_dir / "attack_metrics_by_label_device.csv", grouped_rows)
    write_csv(job_dir / "threshold_free_metrics.csv", threshold_rows)
    write_csv(job_dir / "score_tie_audit.csv", tie_rows)
    write_csv(job_dir / "prototype_bank_audit.csv", bank_audit)
    write_csv(job_dir / "parent_risk_fit_audit.csv", parent_fit_audit)
    write_csv(job_dir / "temporal_head_fit_audit.csv", temporal_fit_audit)
    write_csv(
        job_dir / "role_access_audit.csv",
        [
            {
                "stage": "attack_scorer_fit",
                "roles": "id_benign_train|derived_ood_benign_val_fit|support_train",
                "stress_or_query_accessed": False,
                "sealed_accessed": False,
            },
            {
                "stage": "parent_and_temporal_head_fit",
                "roles": "fit_halves_of_id_calib|ood_val|support_val",
                "stress_or_query_accessed": False,
                "sealed_accessed": False,
            },
            {
                "stage": "configuration_freeze",
                "roles": "select_halves_of_id_calib|ood_val|support_val",
                "stress_or_query_accessed": False,
                "sealed_accessed": False,
            },
            {
                "stage": "read_only_replay",
                "roles": "ood_stress|same_file_query|future_query",
                "stress_or_query_accessed": True,
                "sealed_accessed": False,
            },
            {
                "stage": "report_only_replay",
                "roles": "sealed_final_ood|sealed_final_attack",
                "stress_or_query_accessed": False,
                "sealed_accessed": True,
            },
        ],
    )

    result = {
        "issue": ISSUE,
        "job_spec": asdict(job),
        "smoke": smoke,
        "support_weight": support_weight,
        "fit_rows": {
            "id_benign_train": len(x_id_train),
            "derived_ood_fit": len(x_ood_fit),
            "support_train": len(x_support_train),
            "support_val_fit": len(x_support_val_fit),
            "support_val_select": int(np.sum(support_val_phase == "select")),
        },
        "attack_direction": attack_model.direction_check,
        "parent_attack_threshold": parent_attack_threshold,
        "parent_params": parent_params,
        "temporal_params": temporal_params,
        "frozen_config_sha256": frozen["frozen_config_sha256"],
        "threshold_free": threshold_rows,
        "formal_benchmark": False,
        "mixed_stream_simulated": False,
        "online_deployment_closed_loop": False,
        "dev_query_used_for_fit_or_selection": False,
        "sealed_final_used_for_fit_or_selection": False,
        "candidate_pool_reused": False,
        "runtime_seconds": time.time() - started,
        "python": sys.version,
        "platform": platform.platform(),
    }
    write_json(job_dir / "result.json", result)
    print(json.dumps(clean(result), indent=2), flush=True)


def plan() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = validate_inputs()
    write_csv(OUT / "job_matrix.csv", [asdict(spec) for spec in JOB_SPECS])
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "purpose": "replay the frozen strongest medium architecture on certified 1M benign/OOD plus certified exact-label attacks",
            "formal_benchmark": False,
            "mixed_stream_simulated": False,
            "frontend": "Kitsune115D",
            "support_bank": "issue27cf frozen 512 rows: support_train=385 support_val=127",
            "primary_variant": "medium_mass_ratio_recalibrated",
            "control_variant": "strict_frozen_weight4",
            "seeds": SEEDS,
            "frozen_temporal_selection": {
                "model_kind": "histgb_shallow",
                "attack_q": TEMPORAL_ATTACK_Q,
                "risk_threshold": TEMPORAL_RISK_THRESHOLD,
                "strong_attack_q": TEMPORAL_STRONG_ATTACK_Q,
                "d_attack_thr": TEMPORAL_ATTACK_DISTANCE,
            },
            "role_rule": "fit/select only on derived dev halves; stress/query read-only after freeze; sealed final report-only",
            "input_audit": audit,
        },
    )
    write_md(
        OUT / "experiment_contract.md",
        [
            "# issue27ckc Frozen Medium Mainline Replay Contract",
            "",
            "This is the offline role-separated mainline replay requested by the user. It is not another raw static scorer ablation.",
            "",
            "Architecture:",
            "",
            "```text",
            "Kitsune115D",
            "-> frozen medium full-115D attack scorer",
            "-> parent OOD-risk evidence",
            "-> past-only temporal attack/OOD heads",
            "-> bounded hard/suppress/review/unknown controller",
            "```",
            "",
            "Data:",
            "",
            "- certified 1M benign/OOD asset;",
            "- issue27cf frozen 512-row support bank: 385 train, 127 validation;",
            "- issue27ch complete-only exact-label query/final attack subset;",
            "- no reuse of the remaining attack candidate pool.",
            "",
            "Access order:",
            "",
            "1. Fit attack scorer on ID train, a preregistered source-disjoint OOD-val fit half, and 385 support-train rows.",
            "2. Fit parent OOD-risk and temporal heads only on fit halves of ID-calib/OOD-val/support-val.",
            "3. Freeze and hash all models, banks, thresholds, and controller parameters.",
            "4. Replay OOD stress and certified dev queries read-only.",
            "5. Replay sealed final attack/OOD report-only.",
            "",
            "The primary variant preserves the medium weighted normal-to-attack mass ratio when moving from 128 to 385 supports and from medium to 1M ID scale. The strict weight-4 variant is retained as a frozen-weight control.",
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
    specs = JOB_SPECS[:1] if smoke else JOB_SPECS
    job_dirs = [OUT / f"job_{spec.job_index:02d}_{spec.label}{suffix}" for spec in specs]
    missing = [str(path) for path in job_dirs if not (path / "result.json").exists()]
    if missing:
        raise FileNotFoundError("Missing job results:\n" + "\n".join(missing))
    combined: dict[str, list[dict[str, Any]]] = {
        "role_metrics": [],
        "attack_metrics_by_label_device": [],
        "threshold_free_metrics": [],
        "score_tie_audit": [],
    }
    result_rows = []
    for spec, job_dir in zip(specs, job_dirs):
        result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
        result_rows.append(
            {
                **result["job_spec"],
                "smoke": result["smoke"],
                "support_weight": result["support_weight"],
                "runtime_seconds": result["runtime_seconds"],
                "frozen_config_sha256": result["frozen_config_sha256"],
            }
        )
        for name in combined:
            combined[name].extend(read_csv(job_dir / f"{name}.csv"))
    write_csv(OUT / f"aggregate_job_results{suffix}.csv", result_rows)
    for name, rows in combined.items():
        write_csv(OUT / f"aggregate_{name}{suffix}.csv", rows)

    tf = pd.DataFrame(combined["threshold_free_metrics"])
    for col in ["temporal_attack_auc", "temporal_attack_ap", "parent_attack_auc", "parent_attack_ap"]:
        tf[col] = pd.to_numeric(tf[col], errors="coerce")
    summary_rows = []
    for (weighting, comparison), group in tf.groupby(["weighting", "comparison"], sort=True):
        row = {
            "weighting": weighting,
            "comparison": comparison,
            "jobs": len(group),
        }
        for metric in ["temporal_attack_auc", "temporal_attack_ap", "parent_attack_auc", "parent_attack_ap"]:
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_min"] = float(group[metric].min())
            row[f"{metric}_max"] = float(group[metric].max())
        summary_rows.append(row)
    write_csv(OUT / f"aggregate_comparison_summary{suffix}.csv", summary_rows)
    write_md(
        OUT / f"summary{suffix}.md",
        [
            "# issue27ckc Frozen Medium Mainline Replay",
            "",
            f"- mode: `{'smoke' if smoke else 'full_hpc'}`",
            f"- completed jobs: `{len(result_rows)}`",
            "- architecture: full medium candidate route with attack scorer, parent OOD-risk, past-only temporal heads, and bounded controller.",
            "- data: certified 1M benign/OOD plus frozen 512 support and complete-only exact-label attack subset.",
            "- mixed stream: no; role-separated offline replay.",
            "- formal benchmark: no.",
            "- no winner is promoted automatically; inspect aggregate comparison, role, label/device, and tie-audit tables.",
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
