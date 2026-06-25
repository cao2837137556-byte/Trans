from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier


OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckc_frozen_medium_mainline_replay_on_certified_1m as ckc  # noqa: E402


ISSUE = "issue27ckf_hard_ood_calibrated_worst_group_veto_2026-06-25"
OUT = ROOT / "runs" / ISSUE

HARD_OOD_FIT_CAP = 12000
VETO_RISK_THRESHOLD = 0.50
ATTACK_PROTECT_D_ATTACK = 1.00
ATTACK_PROTECT_SUPPORT_BENIGN_Q = 0.10


@dataclass(frozen=True)
class Candidate:
    name: str
    stack: str
    decision: str
    risk_threshold: float
    protect_attack: bool
    description: str
    protect_benign_q: float = ATTACK_PROTECT_SUPPORT_BENIGN_Q


CANDIDATES = [
    Candidate(
        "C0_baseline_issue27ckc",
        "baseline",
        "issue27ckc_temporal",
        ckc.TEMPORAL_RISK_THRESHOLD,
        False,
        "Exact issue27ckc decision; no hard-OOD calibration.",
    ),
    Candidate(
        "V1_hard_ood_risk_existing_controller",
        "hard_ood_calibrated",
        "issue27ckc_temporal",
        ckc.TEMPORAL_RISK_THRESHOLD,
        False,
        "Hard-OOD calibrated risk head, but original strong-attack bypass/controller.",
    ),
    Candidate(
        "V2_hard_ood_conservative_veto",
        "hard_ood_calibrated",
        "risk_veto",
        VETO_RISK_THRESHOLD,
        False,
        "Hard-OOD calibrated risk head with direct risk veto; diagnostic upper bound on OOD suppression.",
    ),
    Candidate(
        "V3_hard_ood_attack_preserving_veto",
        "hard_ood_calibrated",
        "risk_veto",
        VETO_RISK_THRESHOLD,
        True,
        "Hard-OOD calibrated risk veto, but preserves strong support-like attack evidence.",
    ),
    Candidate(
        "V4_baseline_attack_hard_ood_risk_veto",
        "hybrid_baseline_attack_hard_ood_risk",
        "hybrid_risk_veto",
        VETO_RISK_THRESHOLD,
        True,
        "Keep baseline attack scores/temporal attack head, use hard-OOD calibrated risk only as a veto signal.",
    ),
    Candidate(
        "V5_baseline_attack_strict_hard_ood_veto",
        "hybrid_baseline_attack_hard_ood_risk",
        "hybrid_risk_veto",
        VETO_RISK_THRESHOLD,
        True,
        "Hybrid veto with stricter attack protection: support-like attacks must also clear support median benign-separation.",
        0.50,
    ),
]


ROLE_STAGES = {
    "id_calib": "calibration_select",
    "ood_val": "calibration_select",
    "support_val": "calibration_select",
    "ood_stress": "hard_ood_dev",
    "same_file_query": "read_only",
    "future_query": "read_only",
    "sealed_final_ood": "report_only",
    "sealed_final_attack": "report_only",
}


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
        writer.writerows({key: clean(row.get(key, "")) for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
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


def parse_job_indices(raw: str) -> list[int]:
    out = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not out:
        raise ValueError("No jobs selected")
    return out


def fmt(value: Any, digits: int = 4) -> str:
    try:
        val = float(value)
    except Exception:
        return "nan"
    if not math.isfinite(val):
        return "nan"
    return f"{val:.{digits}f}"


def rate(values: Any) -> float:
    arr = np.asarray(values, dtype=bool)
    return float(np.mean(arr)) if arr.size else float("nan")


def qstats(values: Any) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {key: float("nan") for key in ["min", "p50", "p90", "p95", "p99", "max", "mean"]}
    return {
        "min": float(np.min(arr)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
    }


def support_weight_for(job: ckc.JobSpec, n_id: int, n_ood_fit: int, n_support_train: int) -> float:
    if job.weighting == "strict_frozen_weight4":
        return ckc.STRICT_SUPPORT_WEIGHT
    return float(
        (n_id + ckc.OOD_WEIGHT * n_ood_fit)
        / (ckc.MEDIUM_WEIGHTED_NORMAL_TO_ATTACK_RATIO * max(1, n_support_train))
    )


def deterministic_even_sample(idx: np.ndarray, cap: int) -> np.ndarray:
    idx = np.asarray(idx, dtype=np.int64)
    if len(idx) <= cap:
        return idx
    keep = np.linspace(0, len(idx) - 1, num=cap, dtype=np.int64)
    return idx[keep]


def fit_shallow_histgb_weighted(x: np.ndarray, y: np.ndarray, seed: int) -> HistGradientBoostingClassifier:
    y = np.asarray(y, dtype=np.int8)
    if len(np.unique(y)) != 2:
        raise RuntimeError(f"Expected binary labels, got {np.unique(y).tolist()}")
    counts = {label: int(np.sum(y == label)) for label in np.unique(y)}
    weights = np.asarray([1.0 / max(1, counts[int(label)]) for label in y], dtype=np.float64)
    weights *= len(weights) / float(np.sum(weights))
    model = HistGradientBoostingClassifier(
        max_iter=80,
        learning_rate=0.05,
        max_leaf_nodes=8,
        l2_regularization=0.1,
        random_state=seed,
    )
    model.fit(np.asarray(x, dtype=np.float32), y, sample_weight=weights)
    return model


def add_hard_ood_phase(records: pd.DataFrame) -> pd.DataFrame:
    out = records.copy().reset_index(drop=True)
    groups = sorted(out["source_group"].astype(str).unique().tolist())
    if len(groups) > 1:
        cut = max(1, min(len(groups) - 1, len(groups) // 2))
        fit_groups = set(groups[:cut])
        out["phase"] = np.where(out["source_group"].astype(str).isin(fit_groups), "fit", "select")
        out["phase_rule"] = "source_group_disjoint"
        return out
    order = out.sort_values(["packet_timestamp_epoch", "recorded_index"], kind="mergesort").index
    split = max(1, len(order) // 2)
    out["phase"] = "select"
    out.loc[order[:split], "phase"] = "fit"
    out["phase_rule"] = "time_half_fallback"
    return out


def select_fit_alarm_rows(
    role: str,
    phase: np.ndarray,
    aux: dict[str, np.ndarray],
    risk_label: int,
    cap: int | None,
) -> tuple[np.ndarray, str]:
    idx = np.flatnonzero((phase == "fit") & aux["raw_alarm"])
    source = "fit_raw_alarm_rows"
    if not len(idx):
        fit_idx = np.flatnonzero(phase == "fit")
        if not len(fit_idx):
            raise RuntimeError(f"No fit rows for {role}")
        margin = aux["attack_margin"][fit_idx]
        keep = max(1, int(np.ceil(0.01 * len(fit_idx)))) if risk_label == 1 else len(fit_idx)
        idx = fit_idx[np.argsort(-margin)[:keep]]
        source = "fallback_highest_attack_margin_fit_tail"
    if cap is not None and len(idx) > cap:
        margin = aux["attack_margin"][idx]
        order = idx[np.argsort(margin)]
        idx = deterministic_even_sample(order, cap)
        source = f"{source}_even_margin_cap{cap}"
    return idx, source


def fit_parent_risk_with_optional_hard_ood(
    seed: int,
    role_features: dict[str, np.ndarray],
    role_aux: dict[str, dict[str, np.ndarray]],
    include_hard_ood: bool,
) -> tuple[Any, dict[str, float], list[dict[str, Any]]]:
    parts = []
    labels = []
    audit = []
    roles = [("id_calib", 1, None), ("ood_val", 1, None)]
    if include_hard_ood:
        roles.append(("ood_stress", 1, HARD_OOD_FIT_CAP))
    roles.append(("support_val", 0, None))
    for role, risk_label, cap in roles:
        phase = role_features[f"{role}_phase"]
        idx, source = select_fit_alarm_rows(role, phase, role_aux[role], risk_label, cap)
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
    model = fit_shallow_histgb_weighted(np.vstack(parts), np.concatenate(labels), seed)
    support_phase = role_features["support_val_phase"]
    support_margin = role_aux["support_val"]["attack_margin"][
        (support_phase == "fit") & role_aux["support_val"]["raw_alarm"]
    ]
    if not len(support_margin):
        support_margin = role_aux["support_val"]["attack_margin"][support_phase == "fit"]
    params = {
        "risk_threshold": ckc.PARENT_RISK_THRESHOLD,
        "strong_margin_floor": float(np.quantile(support_margin, ckc.PARENT_STRONG_MARGIN_Q)),
        "weak_margin_ceiling": float(np.quantile(support_margin, ckc.PARENT_WEAK_MARGIN_Q)),
        "attack_outer_norm": ckc.PARENT_ATTACK_OUTER_NORM,
    }
    return model, params, audit


def fit_temporal_risk_with_hard_ood(seed: int, frames: dict[str, pd.DataFrame]) -> tuple[Any, list[dict[str, Any]]]:
    parts = []
    labels = []
    audit = []
    roles = [("id_calib", 1, None), ("ood_val", 1, None), ("ood_stress", 1, HARD_OOD_FIT_CAP), ("support_val", 0, None)]
    for role, risk_label, cap in roles:
        fit = frames[role][frames[role]["phase"] == "fit"].copy()
        if cap is not None and len(fit) > cap:
            fit = fit.sort_values(["attack_margin", "packet_timestamp_epoch", "recorded_index"], kind="mergesort")
            fit = fit.iloc[deterministic_even_sample(np.arange(len(fit)), cap)].copy()
        parts.append(fit[ckc.TEMPORAL_FEATURES].to_numpy(dtype=np.float32))
        labels.append(np.full(len(fit), risk_label, dtype=np.int8))
        audit.append({"role": role, "risk_label": risk_label, "fit_rows": len(fit)})
    return fit_shallow_histgb_weighted(np.vstack(parts), np.concatenate(labels), seed), audit


def add_job_cols(frame: pd.DataFrame, job: ckc.JobSpec) -> pd.DataFrame:
    out = frame.copy()
    out.insert(0, "seed", job.seed)
    out.insert(0, "weighting", job.weighting)
    out.insert(0, "job_label", job.label)
    out.insert(0, "job_index", job.job_index)
    out["row_index_in_role"] = np.arange(len(out), dtype=np.int64)
    return out


def build_role_frame_with_temporal(
    role: str,
    role_kind: str,
    x: np.ndarray,
    records: pd.DataFrame,
    stack: dict[str, Any],
    job: ckc.JobSpec,
) -> pd.DataFrame:
    frame = ckc.build_role_frame(
        role,
        role_kind,
        x,
        records,
        stack["attack_model"],
        stack["parent_attack_threshold"],
        stack["banks"],
        stack["subspaces"],
        stack["parent_model"],
        stack["parent_params"],
    )
    temporal = ckc.apply_temporal_controller(
        frame,
        stack["temporal_attack_head"],
        stack["temporal_risk_head"],
        stack["temporal_params"],
    )
    return add_job_cols(temporal, job)


def build_stack(
    job: ckc.JobSpec,
    cert_x: np.ndarray,
    benign_idx: dict[str, np.ndarray],
    benign_records: dict[str, pd.DataFrame],
    support_x: np.ndarray,
    support_records: pd.DataFrame,
    support_train_idx: np.ndarray,
    support_val_idx: np.ndarray,
    subspaces: dict[str, np.ndarray],
    attack_root: Path,
    hard_ood_records: pd.DataFrame,
    hard_ood_x: np.ndarray,
    smoke: bool,
    include_hard_ood_risk: bool,
) -> dict[str, Any]:
    support_val_records = support_records.iloc[support_val_idx].reset_index(drop=True)
    support_val_phase = support_val_records["phase"].to_numpy()

    id_train_idx = ckc.limited_indices(benign_idx["id_benign_train"], smoke, 4000)
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

    support_weight = support_weight_for(job, len(x_id_train), len(x_ood_fit), len(x_support_train))
    attack_model = ckc.FrozenAttackHistGB(job.seed)
    attack_model.fit(x_id_train, x_ood_fit, x_support_train, support_weight)
    id_select_scores = attack_model.score(id_calib_x[id_calib_phase == "select"])
    parent_attack_threshold = float(np.quantile(id_select_scores, 0.99))

    banks, bank_audit = ckc.build_evidence_banks(
        subspaces,
        x_id_train,
        id_calib_x[id_calib_phase == "fit"],
        x_ood_fit,
        x_ood_select,
        x_support_train,
        x_support_val_fit,
    )

    pre_roles: dict[str, tuple[np.ndarray, pd.DataFrame, str]] = {
        "id_calib": (id_calib_x, benign_records["id_benign_calib"].copy(), "benign_id"),
        "ood_val": (ood_val_x, benign_records["ood_benign_val"].copy(), "benign_ood"),
        "support_val": (x_support_val, support_val_records.copy(), "attack"),
        "ood_stress": (hard_ood_x, hard_ood_records.copy(), "benign_ood"),
    }
    role_evidence: dict[str, np.ndarray] = {}
    role_aux: dict[str, dict[str, np.ndarray]] = {}
    parent_fit_roles = ["id_calib", "ood_val", "support_val"] + (["ood_stress"] if include_hard_ood_risk else [])
    for role in parent_fit_roles:
        x_role, records, _kind = pre_roles[role]
        score = attack_model.score(x_role)
        evidence, aux = ckc.evidence_features(x_role, score, parent_attack_threshold, banks, subspaces)
        role_evidence[role] = evidence
        role_evidence[f"{role}_phase"] = records["phase"].to_numpy()
        role_aux[role] = aux

    parent_model, parent_params, parent_fit_audit = fit_parent_risk_with_optional_hard_ood(
        job.seed,
        role_evidence,
        role_aux,
        include_hard_ood_risk,
    )

    stack_core = {
        "attack_model": attack_model,
        "parent_attack_threshold": parent_attack_threshold,
        "banks": banks,
        "bank_audit": bank_audit,
        "subspaces": subspaces,
        "parent_model": parent_model,
        "parent_params": parent_params,
    }

    pre_frames: dict[str, pd.DataFrame] = {}
    for role, (x_role, records, kind) in pre_roles.items():
        pre_frames[role] = ckc.build_role_frame(
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

    temporal_attack_head, baseline_temporal_risk_head, temporal_params, temporal_fit_audit = ckc.fit_temporal_heads(
        job.seed,
        {role: pre_frames[role] for role in ["id_calib", "ood_val", "support_val"]},
    )
    temporal_risk_audit: list[dict[str, Any]]
    if include_hard_ood_risk:
        temporal_risk_head, temporal_risk_audit = fit_temporal_risk_with_hard_ood(job.seed, pre_frames)
    else:
        temporal_risk_head = baseline_temporal_risk_head
        temporal_risk_audit = [
            {"role": row["role"], "risk_label": row["ood_risk_label"], "fit_rows": row["fit_rows"]}
            for row in temporal_fit_audit
        ]

    stack = {
        **stack_core,
        "support_weight": support_weight,
        "parent_fit_audit": parent_fit_audit,
        "temporal_fit_audit": temporal_fit_audit,
        "temporal_risk_audit": temporal_risk_audit,
        "temporal_attack_head": temporal_attack_head,
        "temporal_risk_head": temporal_risk_head,
        "temporal_params": temporal_params,
    }

    role_inputs = {
        "id_calib": (id_calib_x, benign_records["id_benign_calib"].copy(), "benign_id"),
        "ood_val": (ood_val_x, benign_records["ood_benign_val"].copy(), "benign_ood"),
        "support_val": (x_support_val, support_val_records.copy(), "attack"),
        "ood_stress": (hard_ood_x, hard_ood_records.copy(), "benign_ood"),
    }
    same_x, same_records = ckc.load_attack_role(attack_root, "same_file_time_forward_dev_query_exact", smoke)
    future_x, future_records = ckc.load_attack_role(attack_root, "dev_future_attack_query_exact", smoke)
    sealed_attack_x, sealed_attack_records = ckc.load_attack_role(
        attack_root,
        "sealed_final_attack_exact_realign",
        smoke,
    )
    sealed_ood_x = np.asarray(cert_x[benign_idx["sealed_final_ood"]], dtype=np.float32)
    role_inputs.update(
        {
            "same_file_query": (same_x, same_records, "attack"),
            "future_query": (future_x, future_records, "attack"),
            "sealed_final_ood": (sealed_ood_x, benign_records["sealed_final_ood"].copy(), "benign_ood"),
            "sealed_final_attack": (sealed_attack_x, sealed_attack_records, "attack"),
        }
    )
    scored_frames = {
        role: build_role_frame_with_temporal(role, kind, x_role, records, stack, job)
        for role, (x_role, records, kind) in role_inputs.items()
    }

    support_fit = scored_frames["support_val"][scored_frames["support_val"]["phase"] == "fit"]
    support_benign_values = support_fit["d_benign_core_min"].to_numpy(dtype=np.float64)
    support_benign_floors = {
        "0.10": float(np.quantile(support_benign_values, 0.10)),
        "0.25": float(np.quantile(support_benign_values, 0.25)),
        "0.50": float(np.quantile(support_benign_values, 0.50)),
        "0.75": float(np.quantile(support_benign_values, 0.75)),
    }
    support_benign_floor = support_benign_floors[f"{ATTACK_PROTECT_SUPPORT_BENIGN_Q:.2f}"]

    return {
        **stack,
        "stack_name": "hard_ood_calibrated" if include_hard_ood_risk else "baseline",
        "frames": scored_frames,
        "support_benign_floor": support_benign_floor,
        "support_benign_floors": support_benign_floors,
        "hard_ood_phase_rule": str(hard_ood_records.get("phase_rule", pd.Series([""])).iloc[0]),
    }


def apply_candidate_decision(frame: pd.DataFrame, candidate: Candidate, support_benign_floor: float) -> pd.DataFrame:
    out = frame.copy()
    if candidate.decision == "issue27ckc_temporal":
        out["candidate_raw_alarm"] = out["temporal_raw_alarm"].astype(bool)
        out["candidate_risk_score"] = out["temporal_ood_risk"].astype(float)
        out["candidate_high_risk"] = out["temporal_high_ood_risk"].astype(bool)
        out["candidate_attack_protected"] = out["temporal_strong_attack"].astype(bool)
        out["candidate_veto"] = out["temporal_suppress"].astype(bool)
        out["candidate_hard_alarm"] = out["temporal_hard_alarm"].astype(bool)
        out["candidate_review"] = out["temporal_review"].astype(bool) | out["candidate_veto"].astype(bool)
        out["candidate_unknown"] = out["temporal_unknown"].astype(bool)
        return out

    raw = out["temporal_raw_alarm"].to_numpy(dtype=bool)
    risk = out["temporal_ood_risk"].to_numpy(dtype=np.float64)
    attack = out["temporal_attack_score"].to_numpy(dtype=np.float64)
    d_attack = out["d_attack_outer_min"].to_numpy(dtype=np.float64)
    d_benign = out["d_benign_core_min"].to_numpy(dtype=np.float64)
    high_risk = raw & (risk >= candidate.risk_threshold)
    protected = (
        raw
        & out["temporal_strong_attack"].to_numpy(dtype=bool)
        & (d_attack <= ATTACK_PROTECT_D_ATTACK)
        & (d_benign >= support_benign_floor)
        if candidate.protect_attack
        else np.zeros(len(out), dtype=bool)
    )
    veto = high_risk & (~protected)
    out["candidate_raw_alarm"] = raw
    out["candidate_risk_score"] = risk
    out["candidate_high_risk"] = high_risk
    out["candidate_attack_protected"] = protected
    out["candidate_veto"] = veto
    out["candidate_hard_alarm"] = raw & (~veto)
    out["candidate_review"] = veto
    out["candidate_unknown"] = (~raw) & (risk >= candidate.risk_threshold)
    return out


def apply_hybrid_candidate_decision(
    baseline_frame: pd.DataFrame,
    hard_risk_frame: pd.DataFrame,
    candidate: Candidate,
    support_benign_floor: float,
) -> pd.DataFrame:
    if len(baseline_frame) != len(hard_risk_frame):
        raise RuntimeError(f"Hybrid frame length mismatch for {baseline_frame['role'].iloc[0]}")
    out = baseline_frame.copy()
    raw = out["temporal_raw_alarm"].to_numpy(dtype=bool)
    risk = hard_risk_frame["temporal_ood_risk"].to_numpy(dtype=np.float64)
    d_attack = out["d_attack_outer_min"].to_numpy(dtype=np.float64)
    d_benign = out["d_benign_core_min"].to_numpy(dtype=np.float64)
    protected = (
        raw
        & out["temporal_strong_attack"].to_numpy(dtype=bool)
        & (d_attack <= ATTACK_PROTECT_D_ATTACK)
        & (d_benign >= support_benign_floor)
    )
    high_risk = raw & (risk >= candidate.risk_threshold)
    veto = high_risk & (~protected)
    out["candidate_raw_alarm"] = raw
    out["candidate_risk_score"] = risk
    out["candidate_high_risk"] = high_risk
    out["candidate_attack_protected"] = protected
    out["candidate_veto"] = veto
    out["candidate_hard_alarm"] = raw & (~veto)
    out["candidate_review"] = veto
    out["candidate_unknown"] = (~raw) & (risk >= candidate.risk_threshold)
    out["hybrid_uses_baseline_attack"] = True
    return out


def summarize_role(candidate: Candidate, frame: pd.DataFrame, phase: str | None, stage: str) -> dict[str, Any]:
    part = frame if phase is None else frame[frame["phase"] == phase]
    if len(part) == 0:
        return {}
    row: dict[str, Any] = {
        "candidate": candidate.name,
        "decision": candidate.decision,
        "stack": candidate.stack,
        "risk_threshold": candidate.risk_threshold,
        "protect_attack": candidate.protect_attack,
        "protect_benign_q": candidate.protect_benign_q,
        "job_index": int(part["job_index"].iloc[0]),
        "job_label": str(part["job_label"].iloc[0]),
        "weighting": str(part["weighting"].iloc[0]),
        "seed": int(part["seed"].iloc[0]),
        "role": str(part["role"].iloc[0]),
        "role_kind": str(part["role_kind"].iloc[0]),
        "phase": phase or "",
        "stage": stage,
        "rows": len(part),
        "candidate_hard_alarm_rate": rate(part["candidate_hard_alarm"]),
        "candidate_veto_rate": rate(part["candidate_veto"]),
        "candidate_review_rate": rate(part["candidate_review"]),
        "candidate_unknown_rate": rate(part["candidate_unknown"]),
        "candidate_high_risk_rate": rate(part["candidate_high_risk"]),
        "candidate_attack_protected_rate": rate(part["candidate_attack_protected"]),
        "temporal_hard_alarm_rate": rate(part["temporal_hard_alarm"]),
        "parent_hard_alarm_rate": rate(part["hard_alarm"]),
        "raw_alarm_rate": rate(part["temporal_raw_alarm"]),
    }
    for col in [
        "temporal_attack_score",
        "temporal_ood_risk",
        "candidate_risk_score",
        "attack_score",
        "ood_risk",
        "d_attack_outer_min",
        "d_benign_core_min",
    ]:
        stats = qstats(part[col])
        row[f"{col}_mean"] = stats["mean"]
        row[f"{col}_p50"] = stats["p50"]
        row[f"{col}_p95"] = stats["p95"]
    return row


def summarize_groups(candidate: Candidate, frame: pd.DataFrame, phase: str | None, group_cols: list[str]) -> list[dict[str, Any]]:
    part = frame if phase is None else frame[frame["phase"] == phase]
    if len(part) == 0:
        return []
    rows = []
    for key, group in part.groupby(group_cols, sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        row: dict[str, Any] = {
            "candidate": candidate.name,
            "job_index": int(group["job_index"].iloc[0]),
            "weighting": str(group["weighting"].iloc[0]),
            "role": str(group["role"].iloc[0]),
            "role_kind": str(group["role_kind"].iloc[0]),
            "phase": phase or "",
            "rows": len(group),
            "candidate_hard_alarm_rate": rate(group["candidate_hard_alarm"]),
            "candidate_veto_rate": rate(group["candidate_veto"]),
            "candidate_review_rate": rate(group["candidate_review"]),
            "candidate_high_risk_rate": rate(group["candidate_high_risk"]),
            "temporal_attack_score_mean": float(group["temporal_attack_score"].mean()),
            "temporal_ood_risk_mean": float(group["temporal_ood_risk"].mean()),
        }
        for col, value in zip(group_cols, key):
            row[col] = value
        rows.append(row)
    return rows


def aggregate_group(rows: list[dict[str, Any]], role: str, candidate: str, weighting: str, phase: str = "") -> dict[str, float]:
    vals = [
        float(row["candidate_hard_alarm_rate"])
        for row in rows
        if row["role"] == role and row["candidate"] == candidate and row["weighting"] == weighting and str(row.get("phase", "")) == phase
    ]
    if not vals:
        return {"max": float("nan"), "p95": float("nan")}
    return {"max": float(np.max(vals)), "p95": float(np.quantile(vals, 0.95))}


def weighted_role(rows: list[dict[str, Any]], role: str, candidate: str, weighting: str, phase: str = "") -> float:
    selected = [
        row
        for row in rows
        if row["role"] == role and row["candidate"] == candidate and row["weighting"] == weighting and str(row.get("phase", "")) == phase
    ]
    if not selected:
        return float("nan")
    denom = sum(float(row["rows"]) for row in selected)
    return sum(float(row["rows"]) * float(row["candidate_hard_alarm_rate"]) for row in selected) / max(1.0, denom)


def build_candidate_summary(role_rows: list[dict[str, Any]], group_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for candidate in sorted({row["candidate"] for row in role_rows}):
        for weighting in sorted({row["weighting"] for row in role_rows if row["candidate"] == candidate}):
            def get(role: str, phase: str = "") -> float:
                matches = [
                    row
                    for row in role_rows
                    if row["candidate"] == candidate and row["weighting"] == weighting and row["role"] == role and str(row.get("phase", "")) == phase
                ]
                return float(np.mean([float(row["candidate_hard_alarm_rate"]) for row in matches])) if matches else float("nan")

            stress_group = aggregate_group(group_rows, "ood_stress", candidate, weighting, "select")
            sealed_group = aggregate_group(group_rows, "sealed_final_ood", candidate, weighting, "")
            out.append(
                {
                    "candidate": candidate,
                    "weighting": weighting,
                    "ood_stress_select_hard": get("ood_stress", "select"),
                    "ood_stress_select_group_max": stress_group["max"],
                    "ood_stress_select_group_p95": stress_group["p95"],
                    "sealed_final_ood_hard": get("sealed_final_ood", ""),
                    "sealed_final_ood_group_max": sealed_group["max"],
                    "sealed_final_ood_group_p95": sealed_group["p95"],
                    "support_val_select_hard": get("support_val", "select"),
                    "same_file_query_hard": get("same_file_query", ""),
                    "future_query_hard": get("future_query", ""),
                    "sealed_final_attack_hard": get("sealed_final_attack", ""),
                }
            )
    return out


def support_coverage_rows(candidate: Candidate, frame: pd.DataFrame, support_labels: set[str]) -> list[dict[str, Any]]:
    if "attack_label" not in frame:
        return []
    rows = []
    for (coverage, role), group in frame.assign(
        support_coverage=np.where(frame["attack_label"].astype(str).isin(support_labels), "seen_in_support", "unseen_in_support")
    ).groupby(["support_coverage", "role"], sort=True):
        rows.append(
            {
                "candidate": candidate.name,
                "job_index": int(group["job_index"].iloc[0]),
                "weighting": str(group["weighting"].iloc[0]),
                "role": role,
                "support_coverage": coverage,
                "rows": len(group),
                "candidate_hard_alarm_rate": rate(group["candidate_hard_alarm"]),
                "candidate_veto_rate": rate(group["candidate_veto"]),
                "candidate_review_rate": rate(group["candidate_review"]),
            }
        )
    return rows


def collect_candidate_outputs(
    candidate: Candidate,
    frames: dict[str, pd.DataFrame],
    support_benign_floor: float,
    support_labels: set[str],
    role_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    hard_risk_frames: dict[str, pd.DataFrame] | None = None,
) -> None:
    for role, frame in frames.items():
        if candidate.stack == "hybrid_baseline_attack_hard_ood_risk":
            if hard_risk_frames is None:
                raise RuntimeError("Hybrid candidate requires hard-risk frames")
            decided = apply_hybrid_candidate_decision(frame, hard_risk_frames[role], candidate, support_benign_floor)
        else:
            decided = apply_candidate_decision(frame, candidate, support_benign_floor)
        if role == "ood_stress":
            for phase in ["fit", "select"]:
                row = summarize_role(candidate, decided, phase, f"{ROLE_STAGES[role]}_{phase}")
                if row:
                    role_rows.append(row)
                group_rows.extend(summarize_groups(candidate, decided, phase, ["source_group", "device"]))
        elif role in {"id_calib", "ood_val", "support_val"}:
            row = summarize_role(candidate, decided, "select", ROLE_STAGES[role])
            if row:
                role_rows.append(row)
            group_rows.extend(summarize_groups(candidate, decided, "select", ["source_group", "device"]))
        else:
            row = summarize_role(candidate, decided, None, ROLE_STAGES[role])
            if row:
                role_rows.append(row)
            group_rows.extend(summarize_groups(candidate, decided, None, ["source_group", "device"]))
        if role in {"support_val", "same_file_query", "future_query", "sealed_final_attack"}:
            part = decided[decided["phase"] == "select"] if role == "support_val" else decided
            coverage_rows.extend(support_coverage_rows(candidate, part, support_labels))


def floor_for_candidate(candidate: Candidate, stack: dict[str, Any]) -> float:
    key = f"{candidate.protect_benign_q:.2f}"
    return float(stack["support_benign_floors"].get(key, stack["support_benign_floor"]))


def build_readout(summary_rows: list[dict[str, Any]], role_rows: list[dict[str, Any]], fit_audit_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckf hard-OOD calibrated worst-group veto",
        "",
        "## Scope",
        "",
        "This is a stop-bleeding diagnostic, not the final paper method. It tests whether legal hard-OOD calibration can make the current Kitsune115D/evidence space separate hard benign OOD from attack without using sealed final roles for fitting or selection.",
        "",
        "## Candidate summary",
        "",
        "| candidate | weighting | ood_stress select | ood_stress group max | sealed_final_ood | sealed group max | support_val | same_file | future | sealed_attack |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['candidate']} | {row['weighting']} | {fmt(row['ood_stress_select_hard'])} | {fmt(row['ood_stress_select_group_max'])} | {fmt(row['sealed_final_ood_hard'])} | {fmt(row['sealed_final_ood_group_max'])} | {fmt(row['support_val_select_hard'])} | {fmt(row['same_file_query_hard'])} | {fmt(row['future_query_hard'])} | {fmt(row['sealed_final_attack_hard'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrail",
            "",
            "- If only `ood_stress_select` improves but `sealed_final_ood` does not, this is just a local OOD patch.",
            "- If OOD improves but support-covered attack collapses, the veto is not attack-preserving.",
            "- If both hard OOD and attack retention improve, the line is worth a full 10-seed replay and later group-robust/invariant-evidence upgrade.",
            "- Even a successful stop-bleeding result is not enough for the final paper claim; smarter heads and causal-inspired invariant evidence remain required follow-up work.",
            "",
            "## Hard-OOD fit audit",
            "",
            "| job | stack | role | risk label | rows used | source |",
            "|---:|---|---|---:|---:|---|",
        ]
    )
    for row in fit_audit_rows:
        if row.get("audit_kind") == "parent_risk":
            lines.append(
                f"| {row['job_index']} | {row['stack']} | {row['role']} | {row['risk_label']} | {row['fit_rows_used']} | {row['row_source']} |"
            )
    lines.extend(["", f"Runtime seconds: `{fmt(seconds, 1)}`."])
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", default="1,6", help="comma-separated issue27ckc jobs; default medium seed42 and strict seed42")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    input_audit = ckc.validate_inputs()
    attack_root = Path(input_audit["attack_root"])
    cert_x = np.load(ckc.CERT_X, mmap_mode="r")
    schema = json.loads(ckc.FEATURE_SCHEMA.read_text(encoding="utf-8"))
    subspaces = ckc.bp.build_subspaces(schema)

    benign_idx, benign_records = ckc.load_benign_roles(args.smoke)
    benign_records["id_benign_calib"] = ckc.add_source_disjoint_phase(benign_records["id_benign_calib"])
    benign_records["ood_benign_val"] = ckc.add_source_disjoint_phase(benign_records["ood_benign_val"])
    hard_ood_x = np.asarray(cert_x[benign_idx["ood_benign_stress"]], dtype=np.float32)
    hard_ood_records = add_hard_ood_phase(benign_records["ood_benign_stress"])
    support_x, support_records, support_train_idx, support_val_idx = ckc.load_support(attack_root)
    support_labels = set(support_records.loc[support_train_idx, "attack_label"].astype(str))

    job_indices = parse_job_indices(args.jobs)
    jobs = []
    for job_index in job_indices:
        job = next((spec for spec in ckc.JOB_SPECS if spec.job_index == job_index), None)
        if job is None:
            raise SystemExit(f"Unknown issue27ckc job index: {job_index}")
        jobs.append(job)

    role_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    fit_audit_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    for job in jobs:
        baseline_stack = build_stack(
            job,
            cert_x,
            benign_idx,
            benign_records,
            support_x,
            support_records,
            support_train_idx,
            support_val_idx,
            subspaces,
            attack_root,
            hard_ood_records,
            hard_ood_x,
            args.smoke,
            False,
        )
        hard_stack = build_stack(
            job,
            cert_x,
            benign_idx,
            benign_records,
            support_x,
            support_records,
            support_train_idx,
            support_val_idx,
            subspaces,
            attack_root,
            hard_ood_records,
            hard_ood_x,
            args.smoke,
            True,
        )
        for stack in [baseline_stack, hard_stack]:
            for row in stack["parent_fit_audit"]:
                fit_audit_rows.append(
                    {
                        "job_index": job.job_index,
                        "weighting": job.weighting,
                        "stack": stack["stack_name"],
                        "audit_kind": "parent_risk",
                        **row,
                    }
                )
            for row in stack["temporal_risk_audit"]:
                fit_audit_rows.append(
                    {
                        "job_index": job.job_index,
                        "weighting": job.weighting,
                        "stack": stack["stack_name"],
                        "audit_kind": "temporal_risk",
                        **row,
                    }
                )
            run_rows.append(
                {
                    "job_index": job.job_index,
                    "weighting": job.weighting,
                    "stack": stack["stack_name"],
                    "support_weight": stack["support_weight"],
                    "parent_attack_threshold": stack["parent_attack_threshold"],
                    "temporal_attack_threshold": stack["temporal_params"]["attack_threshold"],
                    "temporal_strong_attack_threshold": stack["temporal_params"]["strong_attack_threshold"],
                    "support_benign_floor": stack["support_benign_floor"],
                    "support_benign_floor_q10": stack["support_benign_floors"]["0.10"],
                    "support_benign_floor_q25": stack["support_benign_floors"]["0.25"],
                    "support_benign_floor_q50": stack["support_benign_floors"]["0.50"],
                    "support_benign_floor_q75": stack["support_benign_floors"]["0.75"],
                    "hard_ood_phase_rule": stack["hard_ood_phase_rule"],
                }
            )
        for candidate in CANDIDATES:
            if candidate.stack == "baseline":
                collect_candidate_outputs(
                    candidate,
                    baseline_stack["frames"],
                    floor_for_candidate(candidate, baseline_stack),
                    support_labels,
                    role_rows,
                    group_rows,
                    coverage_rows,
                )
            elif candidate.stack == "hard_ood_calibrated":
                collect_candidate_outputs(
                    candidate,
                    hard_stack["frames"],
                    floor_for_candidate(candidate, hard_stack),
                    support_labels,
                    role_rows,
                    group_rows,
                    coverage_rows,
                )
            elif candidate.stack == "hybrid_baseline_attack_hard_ood_risk":
                collect_candidate_outputs(
                    candidate,
                    baseline_stack["frames"],
                    floor_for_candidate(candidate, baseline_stack),
                    support_labels,
                    role_rows,
                    group_rows,
                    coverage_rows,
                    hard_risk_frames=hard_stack["frames"],
                )

    summary_rows = build_candidate_summary(role_rows, group_rows)
    seconds = time.time() - started

    write_csv(OUT / "candidate_matrix.csv", [candidate.__dict__ for candidate in CANDIDATES])
    write_csv(OUT / "role_metrics.csv", role_rows)
    write_csv(OUT / "group_metrics_by_source_device.csv", group_rows)
    write_csv(OUT / "support_coverage_metrics.csv", coverage_rows)
    write_csv(OUT / "fit_audit.csv", fit_audit_rows)
    write_csv(OUT / "run_jobs.csv", run_rows)
    write_csv(OUT / "selected_candidate_summary.csv", summary_rows)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "stop-bleeding diagnostic; not final method",
            "smoke": args.smoke,
            "jobs": [job.__dict__ for job in jobs],
            "hard_ood_fit_cap": HARD_OOD_FIT_CAP,
            "veto_risk_threshold": VETO_RISK_THRESHOLD,
            "attack_protect_support_benign_q": ATTACK_PROTECT_SUPPORT_BENIGN_Q,
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "support_coverage_metrics.csv",
                "fit_audit.csv",
                "run_jobs.csv",
                "selected_candidate_summary.csv",
                "summary.md",
                "codex_readout.md",
            ],
            "future_required_work": [
                "smarter temporal/contextual heads",
                "source/time/device-disjoint group-robust validation",
                "causal-inspired invariant evidence diagnostics",
                "second-dataset transfer validation",
            ],
        },
    )
    readout = build_readout(summary_rows, role_rows, fit_audit_rows, seconds)
    write_md(OUT / "summary.md", readout)
    write_md(OUT / "codex_readout.md", readout)
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


if __name__ == "__main__":
    main()
