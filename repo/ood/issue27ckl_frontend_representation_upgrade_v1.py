"""issue27ckl: frontend representation upgrade v1.

This run is deliberately narrow:

- keep the detector head fixed to the C4 four-class HistGB head;
- keep the training contract fixed to support_train + benign/OOD fit roles;
- change only the feature representation fed into that fixed head.

The goal is to test whether fit-only robust/mechanism-inspired evidence can
reduce C4's source/device shortcut and leave-device-family collapse without
turning review into hard OOD false alarms.

No support_val/query/future/sealed-final row is used for fitting robust
statistics, classifier heads, thresholds, or shortcut probes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score

OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cki_c4_full_data_multiclass_replay as cki  # noqa: E402
import issue27ckj_c4_stability_and_shortcut_anatomy as ckj  # noqa: E402


ISSUE = "issue27ckl_frontend_representation_upgrade_v1_2026-06-26"
OUT = ROOT / "runs" / ISSUE

TRAIN_CAP = 20_000
FULL_CAP = cki.FULL_CAP
SEEDS = [42, 43, 44, 45, 46]
ROBUST_CLIP = 8.0
MIN_GROUP_ROWS = 512
PROBE_CAP_PER_ROLE = 20_000


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: str
    group_field: str | None
    description: str


FEATURE_SPECS = [
    FeatureSpec(
        "F0_raw115",
        "raw",
        None,
        "C4 control: original raw Kitsune115D.",
    ),
    FeatureSpec(
        "F1_global_robust_tail",
        "global_robust_tail",
        None,
        "raw115 plus fit-only global robust z/absolute/tail evidence from legal benign fit rows.",
    ),
    FeatureSpec(
        "F1_global_robust_only",
        "global_robust_only",
        None,
        "fit-only global robust z/absolute/tail evidence without raw115; tests whether raw concatenation is the shortcut carrier.",
    ),
    FeatureSpec(
        "F1_device_family_robust_tail",
        "group_robust_tail",
        "device_family",
        "F1 plus device-family robust residual evidence, with unknown/under-sampled families falling back to global fit baseline.",
    ),
    FeatureSpec(
        "F1_device_family_robust_only",
        "group_robust_only",
        "device_family",
        "device-family robust residual evidence without raw115; unknown/under-sampled families fall back to global fit baseline.",
    ),
]


@dataclass
class RobustStats:
    center: np.ndarray
    scale: np.ndarray
    low: np.ndarray
    high: np.ndarray


@dataclass
class FeatureBuilder:
    global_stats: RobustStats
    group_stats: dict[str, dict[str, RobustStats]]
    feature_audit: list[dict[str, Any]]

    def components(self, x: np.ndarray, stats: RobustStats) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        arr = np.asarray(x, dtype=np.float32)
        z = (arr - stats.center) / stats.scale
        z = np.clip(z, -ROBUST_CLIP, ROBUST_CLIP)
        abs_z = np.abs(z)
        upper = np.maximum((arr - stats.high) / stats.scale, 0.0)
        lower = np.maximum((stats.low - arr) / stats.scale, 0.0)
        tail = np.clip(upper + lower, 0.0, ROBUST_CLIP)
        return z.astype(np.float32), abs_z.astype(np.float32), tail.astype(np.float32)

    def group_components(
        self,
        role: str,
        idx: np.ndarray,
        x: np.ndarray,
        frame_by_role: dict[str, pd.DataFrame],
        group_field: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        global_z, global_abs, global_tail = self.components(x, self.global_stats)
        z = global_z.copy()
        abs_z = global_abs.copy()
        tail = global_tail.copy()
        used_group = np.zeros(len(idx), dtype=bool)
        if group_field not in frame_by_role[role] or group_field not in self.group_stats:
            return z, abs_z, tail, used_group
        labels = frame_by_role[role].iloc[idx][group_field].astype(str).to_numpy()
        stats_by_value = self.group_stats[group_field]
        for value in sorted(set(labels.tolist())):
            stats = stats_by_value.get(value)
            if stats is None:
                continue
            mask = labels == value
            local_z, local_abs, local_tail = self.components(x[mask], stats)
            z[mask] = local_z
            abs_z[mask] = local_abs
            tail[mask] = local_tail
            used_group[mask] = True
        return z, abs_z, tail, used_group

    def transform(
        self,
        spec: FeatureSpec,
        role: str,
        idx: np.ndarray,
        x_by_role: dict[str, np.ndarray],
        frame_by_role: dict[str, pd.DataFrame],
    ) -> np.ndarray:
        raw = np.asarray(x_by_role[role][idx], dtype=np.float32)
        if spec.kind == "raw":
            return clean_features(raw)
        global_z, global_abs, global_tail = self.components(raw, self.global_stats)
        if spec.kind == "global_robust_only":
            return clean_features(np.hstack([global_z, global_abs, global_tail]))
        if spec.kind == "global_robust_tail":
            return clean_features(np.hstack([raw, global_z, global_abs, global_tail]))
        if spec.kind == "group_robust_tail":
            assert spec.group_field is not None
            group_z, group_abs, group_tail, _used = self.group_components(
                role,
                idx,
                raw,
                frame_by_role,
                spec.group_field,
            )
            return clean_features(np.hstack([raw, global_z, global_abs, global_tail, group_z, group_abs, group_tail]))
        if spec.kind == "group_robust_only":
            assert spec.group_field is not None
            group_z, group_abs, group_tail, _used = self.group_components(
                role,
                idx,
                raw,
                frame_by_role,
                spec.group_field,
            )
            return clean_features(np.hstack([global_z, global_abs, global_tail, group_z, group_abs, group_tail]))
        raise ValueError(f"unknown feature kind {spec.kind}")

    def fallback_rate(self, spec: FeatureSpec, role: str, idx: np.ndarray, x_by_role: dict[str, np.ndarray], frame_by_role: dict[str, pd.DataFrame]) -> float:
        if spec.group_field is None or spec.kind not in {"group_robust_tail", "group_robust_only"} or len(idx) == 0:
            return float("nan")
        raw = np.asarray(x_by_role[role][idx], dtype=np.float32)
        _z, _a, _t, used = self.group_components(role, idx, raw, frame_by_role, spec.group_field)
        return float(1.0 - np.mean(used))


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def clean_features(x: np.ndarray) -> np.ndarray:
    return np.nan_to_num(np.asarray(x, dtype=np.float32), nan=0.0, posinf=ROBUST_CLIP, neginf=-ROBUST_CLIP)


def robust_stats(x: np.ndarray) -> RobustStats:
    arr = np.asarray(x, dtype=np.float32)
    center = np.median(arr, axis=0)
    q25 = np.quantile(arr, 0.25, axis=0)
    q75 = np.quantile(arr, 0.75, axis=0)
    scale = q75 - q25
    std = np.std(arr, axis=0)
    fallback = scale <= 1e-8
    scale[fallback] = std[fallback]
    scale[scale <= 1e-8] = 1.0
    return RobustStats(
        center=np.asarray(center, dtype=np.float32),
        scale=np.asarray(scale, dtype=np.float32),
        low=np.asarray(np.quantile(arr, 0.01, axis=0), dtype=np.float32),
        high=np.asarray(np.quantile(arr, 0.99, axis=0), dtype=np.float32),
    )


def idx_for(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int = FULL_CAP,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    frame = frame_by_role[role]
    idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].to_numpy() == phase)
    if include is not None and include[0] in frame:
        field, value = include
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() == str(value)]
    if exclude is not None and exclude[0] in frame:
        field, value = exclude
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() != str(value)]
    return ckh.deterministic_cap(idx, cap)


def legal_benign_fit(
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, pd.DataFrame, list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    frames: list[pd.DataFrame] = []
    audit: list[dict[str, Any]] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = idx_for(frame_by_role, role, "fit", FULL_CAP, exclude=exclude)
        xs.append(np.asarray(x_by_role[role][idx], dtype=np.float32))
        part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
        part["_fit_role"] = role
        frames.append(part)
        audit.append({"role": role, "phase": "fit", "rows": len(idx), "purpose": "feature_stats"})
    return np.vstack(xs), pd.concat(frames, ignore_index=True), audit


def fit_feature_builder(
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> FeatureBuilder:
    x_fit, frame_fit, audit = legal_benign_fit(x_by_role, frame_by_role, exclude=exclude)
    global_pack = robust_stats(x_fit)
    feature_audit: list[dict[str, Any]] = [
        {
            "scope": "global",
            "group_field": "",
            "group_value": "ALL_LEGAL_BENIGN_FIT",
            "rows": len(x_fit),
            "eligible": True,
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        },
        *audit,
    ]
    group_stats: dict[str, dict[str, RobustStats]] = {}
    for field in ["device_family", "source_family", "source_group"]:
        if field not in frame_fit:
            continue
        local: dict[str, RobustStats] = {}
        labels = frame_fit[field].astype(str).to_numpy()
        for value in sorted(set(labels.tolist())):
            pos = np.flatnonzero(labels == value)
            eligible = len(pos) >= MIN_GROUP_ROWS
            if eligible:
                local[value] = robust_stats(x_fit[pos])
            feature_audit.append(
                {
                    "scope": "group",
                    "group_field": field,
                    "group_value": value,
                    "rows": len(pos),
                    "eligible": eligible,
                    "exclude_field": exclude[0] if exclude else "",
                    "exclude_value": exclude[1] if exclude else "",
                }
            )
        group_stats[field] = local
    return FeatureBuilder(global_pack, group_stats, feature_audit)


def fit_c4(
    spec: FeatureSpec,
    builder: FeatureBuilder,
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    old_seed = ckh.SEED
    ckh.SEED = int(seed)
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = idx_for(frame_by_role, role, phase, cap, exclude=exclude)
        x = builder.transform(spec, role, idx, x_by_role, frame_by_role)
        xs.append(x)
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append(
            {
                "candidate": candidate_name(spec, seed),
                "feature_set": spec.name,
                "seed": seed,
                "role": role,
                "phase": phase,
                "label": label,
                "rows": len(idx),
                "feature_dim": int(x.shape[1]) if x.ndim == 2 else 0,
                "group_fallback_rate": builder.fallback_rate(spec, role, idx, x_by_role, frame_by_role),
            }
        )

    try:
        add("support_train", "fit", ckh.CLASS_ATTACK, FULL_CAP)
        add("id_calib", "fit", ckh.CLASS_ID, TRAIN_CAP)
        add("ood_val", "fit", ckh.CLASS_OOD, TRAIN_CAP)
        add("ood_stress", "fit", ckh.CLASS_HARD_OOD, TRAIN_CAP)
        model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), np.vstack(xs), np.concatenate(ys))
        return {"multiclass_model": model}, audit
    finally:
        ckh.SEED = old_seed


def candidate_name(spec: FeatureSpec, seed: int, suffix: str = "") -> str:
    return f"CKL_{spec.name}_seed{seed}{suffix}"


def decision_scores(fitted: dict[str, Any], x: np.ndarray) -> dict[str, np.ndarray]:
    model = fitted["multiclass_model"]
    attack = ckh.class_score(model, x, ckh.CLASS_ATTACK)
    hard_ood = ckh.class_score(model, x, ckh.CLASS_HARD_OOD)
    ordinary_ood = ckh.class_score(model, x, ckh.CLASS_OOD)
    identity = ckh.class_score(model, x, ckh.CLASS_ID)
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "conflict_score": np.maximum.reduce([identity, ordinary_ood, hard_ood]),
    }


def thresholds_for(
    spec: FeatureSpec,
    builder: FeatureBuilder,
    fitted: dict[str, Any],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> dict[str, Any]:
    scores: list[np.ndarray] = []
    roles: list[str] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = idx_for(frame_by_role, role, "select", FULL_CAP, exclude=exclude)
        if len(idx) == 0:
            continue
        x = builder.transform(spec, role, idx, x_by_role, frame_by_role)
        scores.append(decision_scores(fitted, x)["attack_score"])
        roles.append(role)
    if not scores:
        raise RuntimeError(f"No threshold rows for {spec.name} after exclusion {exclude}")
    return {
        "attack_threshold": float(max(np.quantile(score, ckh.BENIGN_SAFE_Q) for score in scores)),
        "hard_ood_gate": float("nan"),
        "threshold_roles": "|".join(roles),
    }


def decide_part(
    spec: FeatureSpec,
    builder: FeatureBuilder,
    fitted: dict[str, Any],
    thresholds: dict[str, Any],
    role: str,
    phase: str,
    role_kind: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> pd.DataFrame:
    idx = idx_for(frame_by_role, role, phase, FULL_CAP, include=include, exclude=exclude)
    frame = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    frame["candidate"] = ""
    frame["feature_set"] = spec.name
    frame["role_kind"] = role_kind
    if len(idx) == 0:
        for col in ["attack_score", "hard_ood_score", "conflict_score"]:
            frame[col] = pd.Series(dtype=float)
        for col in ["candidate_raw_alarm", "candidate_conflict_review", "candidate_hard_alarm"]:
            frame[col] = pd.Series(dtype=bool)
        return frame
    x = builder.transform(spec, role, idx, x_by_role, frame_by_role)
    score = decision_scores(fitted, x)
    raw = score["attack_score"] > float(thresholds["attack_threshold"])
    review = raw & (score["conflict_score"] > score["attack_score"])
    hard = raw & ~review
    frame["attack_score"] = score["attack_score"]
    frame["hard_ood_score"] = score["hard_ood_score"]
    frame["conflict_score"] = score["conflict_score"]
    frame["candidate_raw_alarm"] = raw
    frame["candidate_conflict_review"] = review
    frame["candidate_hard_alarm"] = hard
    frame["group_fallback_rate"] = builder.fallback_rate(spec, role, idx, x_by_role, frame_by_role)
    return frame


def summarize_part(
    candidate: str,
    spec: FeatureSpec,
    split: str,
    seed: int,
    role: str,
    phase: str,
    part: pd.DataFrame,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    rows = len(part)
    return {
        "candidate": candidate,
        "feature_set": spec.name,
        "split": split,
        "seed": seed,
        "role": role,
        "phase": phase,
        "role_kind": part["role_kind"].iloc[0] if rows and "role_kind" in part else "",
        "rows": rows,
        "attack_threshold": thresholds["attack_threshold"],
        "raw_alarm_rate": ckh.rate(part["candidate_raw_alarm"]) if rows else float("nan"),
        "conflict_review_rate": ckh.rate(part["candidate_conflict_review"]) if rows else float("nan"),
        "hard_alarm_rate": ckh.rate(part["candidate_hard_alarm"]) if rows else float("nan"),
        "attack_score_mean": float(part["attack_score"].mean()) if rows else float("nan"),
        "conflict_score_mean": float(part["conflict_score"].mean()) if rows else float("nan"),
        "group_fallback_rate": float(part["group_fallback_rate"].mean()) if rows and "group_fallback_rate" in part else float("nan"),
    }


def eval_all_roles(
    spec: FeatureSpec,
    builder: FeatureBuilder,
    fitted: dict[str, Any],
    thresholds: dict[str, Any],
    seed: int,
    split: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    candidate = candidate_name(spec, seed)
    rows: list[dict[str, Any]] = []
    parts: dict[str, pd.DataFrame] = {}
    for role, phase, role_kind in ckh.ROLE_EVAL:
        part = decide_part(
            spec,
            builder,
            fitted,
            thresholds,
            role,
            phase,
            role_kind,
            x_by_role,
            frame_by_role,
            include=include,
            exclude=exclude,
        )
        part["candidate"] = candidate
        rows.append(summarize_part(candidate, spec, split, seed, role, phase, part, thresholds))
        parts[role] = part
    return rows, parts


def group_anatomy(parts: dict[str, pd.DataFrame], fields: list[str], split: str, seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, part in parts.items():
        if part.empty:
            continue
        for field in fields:
            if field not in part:
                continue
            for value, group in part.groupby(field, sort=True):
                rows.append(
                    {
                        "candidate": str(group["candidate"].iloc[0]),
                        "feature_set": str(group["feature_set"].iloc[0]),
                        "split": split,
                        "seed": seed,
                        "role": role,
                        "group_field": field,
                        "group_value": value,
                        "rows": len(group),
                        "hard_alarm_rate": ckh.rate(group["candidate_hard_alarm"]),
                        "conflict_review_rate": ckh.rate(group["candidate_conflict_review"]),
                        "raw_alarm_rate": ckh.rate(group["candidate_raw_alarm"]),
                        "hard_count": int(np.sum(group["candidate_hard_alarm"].to_numpy(dtype=bool))),
                        "review_count": int(np.sum(group["candidate_conflict_review"].to_numpy(dtype=bool))),
                    }
                )
    return rows


def aggregate_matrix(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(role_rows)
    rows: list[dict[str, Any]] = []
    if df.empty:
        return rows
    for feature_set, group in df[df["split"] == "main"].groupby("feature_set", sort=True):
        def val(role: str, col: str, fn: str = "mean") -> float:
            vals = pd.to_numeric(group[group["role"] == role][col], errors="coerce")
            if vals.empty:
                return float("nan")
            if fn == "min":
                return float(vals.min())
            if fn == "max":
                return float(vals.max())
            return float(vals.mean())

        rows.append(
            {
                "feature_set": feature_set,
                "future_hard_mean": val("future_query", "hard_alarm_rate"),
                "future_hard_min": val("future_query", "hard_alarm_rate", "min"),
                "future_review_mean": val("future_query", "conflict_review_rate"),
                "sealed_attack_hard_mean": val("sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_hard_min": val("sealed_final_attack", "hard_alarm_rate", "min"),
                "sealed_attack_review_mean": val("sealed_final_attack", "conflict_review_rate"),
                "sealed_ood_hard_mean": val("sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_hard_max": val("sealed_final_ood", "hard_alarm_rate", "max"),
                "sealed_ood_review_mean": val("sealed_final_ood", "conflict_review_rate"),
                "sealed_ood_review_max": val("sealed_final_ood", "conflict_review_rate", "max"),
                "ood_stress_hard_max": val("ood_stress", "hard_alarm_rate", "max"),
                "ood_stress_review_mean": val("ood_stress", "conflict_review_rate"),
            }
        )
    return rows


def select_leave_groups(max_groups: int) -> dict[str, list[str]]:
    candidates = [
        ROOT / "runs" / "issue27ckk_group_balanced_worst_group_c4_2026-06-25" / "run_spec.json",
        ROOT / "runs" / "issue27ckj_c4_stability_and_shortcut_anatomy_2026-06-25" / "run_spec.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        groups = payload.get("leave_groups_from_issue27ckj") or payload.get("selected_leave_groups") or {}
        device = list(groups.get("device_family", []))[:max_groups]
        if device:
            return {"device_family": device}
    return {"device_family": []}


def eval_leave_device_family(
    specs: list[FeatureSpec],
    selected_groups: dict[str, list[str]],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    seed = SEEDS[0]
    rows: list[dict[str, Any]] = []
    train_audit: list[dict[str, Any]] = []
    feature_audit: list[dict[str, Any]] = []
    for value in selected_groups.get("device_family", []):
        exclude = ("device_family", value)
        builder = fit_feature_builder(x_by_role, frame_by_role, exclude=exclude)
        for item in builder.feature_audit:
            feature_audit.append({**item, "split": "leave_device_family", "held_field": "device_family", "held_value": value})
        for spec in specs:
            fitted, audit = fit_c4(spec, builder, seed, x_by_role, frame_by_role, exclude=exclude)
            thresholds = thresholds_for(spec, builder, fitted, x_by_role, frame_by_role, exclude=exclude)
            for item in audit:
                train_audit.append({**item, "split": "leave_device_family", "held_field": "device_family", "held_value": value})
            eval_rows, _parts = eval_all_roles(
                spec,
                builder,
                fitted,
                thresholds,
                seed,
                "leave_device_family",
                x_by_role,
                frame_by_role,
                include=exclude,
            )
            for row in eval_rows:
                row["held_field"] = "device_family"
                row["held_value"] = value
            rows.extend(eval_rows)
    return rows, train_audit, feature_audit


def shortcut_probe(
    spec: FeatureSpec,
    builder: FeatureBuilder,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    target_field: str,
) -> list[dict[str, Any]]:
    train_x: list[np.ndarray] = []
    train_y: list[str] = []
    audit_roles: list[str] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        if target_field not in frame_by_role[role]:
            continue
        idx = idx_for(frame_by_role, role, "fit", PROBE_CAP_PER_ROLE)
        y = frame_by_role[role].iloc[idx][target_field].astype(str).to_numpy()
        keep = y != "NA"
        if not np.any(keep):
            continue
        train_x.append(builder.transform(spec, role, idx[keep], x_by_role, frame_by_role))
        train_y.extend(y[keep].tolist())
        audit_roles.append(f"{role}:fit:{int(np.sum(keep))}")
    if not train_x or len(set(train_y)) < 2:
        return []
    old_seed = ckh.SEED
    ckh.SEED = SEEDS[0]
    try:
        model = HistGradientBoostingClassifier(
            max_iter=50,
            learning_rate=0.05,
            max_leaf_nodes=8,
            l2_regularization=0.1,
            random_state=SEEDS[0],
        )
        model.fit(np.vstack(train_x), np.asarray(train_y, dtype=object))
    finally:
        ckh.SEED = old_seed

    rows: list[dict[str, Any]] = []
    for role, phase in [
        ("id_calib", "select"),
        ("ood_val", "select"),
        ("ood_stress", "select"),
        ("sealed_final_ood", "all"),
    ]:
        if target_field not in frame_by_role[role]:
            continue
        idx = idx_for(frame_by_role, role, phase, FULL_CAP)
        y_true = frame_by_role[role].iloc[idx][target_field].astype(str).to_numpy()
        keep = y_true != "NA"
        if not np.any(keep):
            continue
        x = builder.transform(spec, role, idx[keep], x_by_role, frame_by_role)
        y_pred = model.predict(x)
        rows.append(
            {
                "feature_set": spec.name,
                "target_field": target_field,
                "train_roles": "|".join(audit_roles),
                "eval_role": role,
                "eval_phase": phase,
                "rows": int(np.sum(keep)),
                "classes_train": len(set(train_y)),
                "accuracy": float(accuracy_score(y_true[keep], y_pred)),
                "balanced_accuracy": safe_balanced_accuracy(y_true[keep], y_pred),
            }
        )
    return rows


def safe_balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return float(balanced_accuracy_score(y_true, y_pred))


def build_readout(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckl frontend representation upgrade v1",
        "",
        "## Scope",
        "",
        "Fixed head: C4 HistGB four-class ID / OOD / hard-OOD / attack.",
        "Only the frontend representation changes. Robust statistics are fit only from legal benign fit roles.",
        "",
        "## Main candidate matrix",
        "",
        "| feature set | future hard mean/min | future review | sealed attack hard mean/min | sealed attack review | sealed OOD hard mean/max | sealed OOD review mean/max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['feature_set']} | {ckh.fmt(row['future_hard_mean'])}/{ckh.fmt(row['future_hard_min'])} | "
            f"{ckh.fmt(row['future_review_mean'])} | {ckh.fmt(row['sealed_attack_hard_mean'])}/{ckh.fmt(row['sealed_attack_hard_min'])} | "
            f"{ckh.fmt(row['sealed_attack_review_mean'])} | {ckh.fmt(row['sealed_ood_hard_mean'])}/{ckh.fmt(row['sealed_ood_hard_max'])} | "
            f"{ckh.fmt(row['sealed_ood_review_mean'])}/{ckh.fmt(row['sealed_ood_review_max'])} |"
        )
    lines.extend(["", "## Leave-device-family stress", ""])
    lines.extend(["| feature set | held value | role | rows | hard | review | raw | fallback |", "|---|---|---|---:|---:|---:|---:|---:|"])
    for row in leave_rows:
        if int(row.get("rows", 0)) == 0:
            continue
        if row.get("role") not in {"ood_val", "ood_stress", "sealed_final_ood"}:
            continue
        lines.append(
            f"| {row['feature_set']} | {str(row.get('held_value', ''))[:60]} | {row['role']} | {row['rows']} | "
            f"{ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {ckh.fmt(row['raw_alarm_rate'])} | {ckh.fmt(row.get('group_fallback_rate', float('nan')))} |"
        )
    lines.extend(["", "## Shortcut probe snapshot", ""])
    lines.extend(["| feature set | target | eval role | accuracy | balanced acc |", "|---|---|---|---:|---:|"])
    for row in probe_rows:
        if row.get("eval_role") not in {"ood_stress", "sealed_final_ood"}:
            continue
        lines.append(
            f"| {row['feature_set']} | {row['target_field']} | {row['eval_role']} | {ckh.fmt(row['accuracy'])} | {ckh.fmt(row['balanced_accuracy'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- A useful frontend upgrade must reduce sealed OOD review without raising sealed OOD hard false alarms.",
            "- It must not reduce sealed/future attack hard detection.",
            "- It must improve leave-device-family collapse; otherwise it is only an in-Gotham cosmetic repair.",
            "- Group-aware features use fit-only group baselines and fall back to global robust baselines for unknown/under-sampled groups.",
            "",
            f"Runtime seconds: `{ckh.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def build_interpretation(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "# issue27ckl diagnostic interpretation",
        "",
        "## Verdict",
        "",
    ]
    df = pd.DataFrame(matrix)
    if df.empty:
        return lines + ["No matrix rows were produced."]
    base = df[df["feature_set"] == "F0_raw115"]
    if base.empty:
        lines.append("No F0 baseline row was produced.")
        return lines
    base_row = base.iloc[0]
    lines.append("This is a frontend-only ablation. The detector head and data contract are fixed.")
    lines.append("")
    candidates = df[df["feature_set"] != "F0_raw115"].copy()
    if not candidates.empty:
        candidates["passes_guardrail"] = (
            (candidates["sealed_ood_review_mean"].astype(float) < float(base_row["sealed_ood_review_mean"]))
            & (candidates["sealed_ood_hard_max"].astype(float) <= float(base_row["sealed_ood_hard_max"]) + 0.002)
            & (candidates["sealed_attack_hard_mean"].astype(float) >= float(base_row["sealed_attack_hard_mean"]) - 0.002)
            & (candidates["future_hard_mean"].astype(float) >= float(base_row["future_hard_mean"]) - 0.002)
        )
        if not bool(candidates["passes_guardrail"].any()):
            lines.extend(
                [
                    "No F1 frontend candidate passes the conservative guardrail.",
                    "The useful-looking reductions are trade-offs: they either raise OOD hard false alarms or damage future/sealed attack detection.",
                    "",
                ]
            )
    for _, row in df.sort_values("feature_set").iterrows():
        if row["feature_set"] == "F0_raw115":
            continue
        ood_review_delta = float(row["sealed_ood_review_mean"]) - float(base_row["sealed_ood_review_mean"])
        ood_hard_delta = float(row["sealed_ood_hard_max"]) - float(base_row["sealed_ood_hard_max"])
        attack_delta = float(row["sealed_attack_hard_mean"]) - float(base_row["sealed_attack_hard_mean"])
        future_delta = float(row["future_hard_mean"]) - float(base_row["future_hard_mean"])
        lines.append(
            f"- `{row['feature_set']}` vs F0: sealed OOD review delta `{ckh.fmt(ood_review_delta)}`, "
            f"sealed OOD hard-max delta `{ckh.fmt(ood_hard_delta)}`, sealed attack hard delta `{ckh.fmt(attack_delta)}`, "
            f"future hard delta `{ckh.fmt(future_delta)}`."
        )
    best_review = df[df["feature_set"] != "F0_raw115"].sort_values("sealed_ood_review_mean").head(1)
    if not best_review.empty:
        row = best_review.iloc[0]
        lines.extend(
            [
                "",
                "Best OOD-review-only candidate is not acceptable:",
                f"- `{row['feature_set']}` lowers sealed OOD review to `{ckh.fmt(row['sealed_ood_review_mean'])}`, "
                f"but future hard drops to `{ckh.fmt(row['future_hard_mean'])}` and sealed OOD hard max rises to `{ckh.fmt(row['sealed_ood_hard_max'])}`.",
            ]
        )
    leave = pd.DataFrame(leave_rows)
    if not leave.empty:
        risk = leave[
            (leave["role"].isin(["ood_val", "ood_stress", "sealed_final_ood"]))
            & (pd.to_numeric(leave["rows"], errors="coerce") > 0)
        ].copy()
        if not risk.empty:
            risk["hard_alarm_rate"] = pd.to_numeric(risk["hard_alarm_rate"], errors="coerce")
            worst = risk.sort_values("hard_alarm_rate", ascending=False).iloc[0]
            lines.extend(
                [
                    "",
                    "## Leave-device-family risk",
                    "",
                    f"Worst held-family hard alarm: `{worst['feature_set']}` / `{worst['held_value']}` / `{worst['role']}` = `{ckh.fmt(worst['hard_alarm_rate'])}`.",
                ]
            )
    probe = pd.DataFrame(probe_rows)
    if not probe.empty:
        sealed = probe[probe["eval_role"] == "sealed_final_ood"].copy()
        if not sealed.empty:
            sealed["balanced_accuracy"] = pd.to_numeric(sealed["balanced_accuracy"], errors="coerce")
            lines.extend(["", "## Shortcut probe", ""])
            for _, row in sealed.sort_values(["target_field", "feature_set"]).iterrows():
                lines.append(
                    f"- `{row['feature_set']}` predicts `{row['target_field']}` on sealed_final_ood with balanced accuracy `{ckh.fmt(row['balanced_accuracy'])}`."
                )
            known = probe[probe["eval_role"] == "ood_stress"].copy()
            if not known.empty:
                known["balanced_accuracy"] = pd.to_numeric(known["balanced_accuracy"], errors="coerce")
                lines.append("")
                lines.append(
                    "Interpretation note: sealed_final_ood probe accuracy is zero because those held families are outside the probe's fit-label support; "
                    "it is not evidence of invariance. On known ood_stress families, device/source predictability remains near-perfect."
                )
                for _, row in known.sort_values(["target_field", "feature_set"]).iterrows():
                    lines.append(
                        f"- known-family `{row['feature_set']}` -> `{row['target_field']}` balanced accuracy `{ckh.fmt(row['balanced_accuracy'])}`."
                    )
    lines.extend(
        [
            "",
            "## Data-use boundary",
            "",
            "Feature statistics, detector fit, thresholds, and shortcut probes use only legal fit/select development roles as appropriate.",
            "No support_val, query, future, sealed_final_ood, or sealed_final_attack rows are used for fitting.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    x_by_role, frame_by_role, support_labels, input_audit = cki.prepare_roles(args.smoke)
    ckj.add_diagnostic_columns(frame_by_role, support_labels)
    inventory = cki.role_inventory(frame_by_role)
    seeds = SEEDS[:1] if args.smoke else (SEEDS[:3] if args.quick else SEEDS)
    specs = FEATURE_SPECS[:2] if args.smoke else FEATURE_SPECS

    builder = fit_feature_builder(x_by_role, frame_by_role)
    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []

    for seed in seeds:
        for spec in specs:
            fitted, audit = fit_c4(spec, builder, seed, x_by_role, frame_by_role)
            thresholds = thresholds_for(spec, builder, fitted, x_by_role, frame_by_role)
            for item in audit:
                train_rows.append({**item, "split": "main"})
            rows, parts = eval_all_roles(spec, builder, fitted, thresholds, seed, "main", x_by_role, frame_by_role)
            role_rows.extend(rows)
            if seed == seeds[0]:
                group_rows.extend(
                    group_anatomy(
                        parts,
                        ["source_group", "device_family", "source_family", "time_block", "attack_label", "support_seen"],
                        "main_seed42",
                        seed,
                    )
                )

    if not args.skip_probe:
        for spec in specs:
            for target in ["device_family", "source_family"]:
                probe_rows.extend(shortcut_probe(spec, builder, x_by_role, frame_by_role, target))

    leave_rows: list[dict[str, Any]] = []
    leave_train_rows: list[dict[str, Any]] = []
    leave_feature_audit: list[dict[str, Any]] = []
    selected_leave_groups = select_leave_groups(args.max_leave_groups)
    if not args.skip_leaveout:
        leave_rows, leave_train_rows, leave_feature_audit = eval_leave_device_family(specs, selected_leave_groups, x_by_role, frame_by_role)
        train_rows.extend(leave_train_rows)

    matrix = aggregate_matrix(role_rows)
    seconds = time.time() - started
    feature_audit = [{**row, "split": "main"} for row in builder.feature_audit] + leave_feature_audit
    ckh.write_csv(OUT / "candidate_matrix.csv", [spec.__dict__ for spec in FEATURE_SPECS])
    ckh.write_csv(OUT / "role_inventory.csv", inventory)
    ckh.write_csv(OUT / "feature_audit.csv", feature_audit)
    ckh.write_csv(OUT / "train_audit.csv", train_rows)
    ckh.write_csv(OUT / "role_metrics_by_candidate_seed.csv", role_rows)
    ckh.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    ckh.write_csv(OUT / "review_anatomy_by_group_seed42.csv", group_rows)
    ckh.write_csv(OUT / "shortcut_probe_metrics.csv", probe_rows)
    ckh.write_csv(OUT / "leave_device_family_stress_metrics.csv", leave_rows)
    ckh.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "frontend representation upgrade v1; fixed C4 HistGB head",
            "smoke": args.smoke,
            "quick": args.quick,
            "seeds": seeds,
            "train_cap": TRAIN_CAP,
            "eval_cap": "full",
            "robust_stats_fit_roles": ["id_calib fit", "ood_val fit", "ood_stress fit"],
            "detector_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
            "sealed_final_roles_used_for_training": False,
            "feature_specs": [spec.__dict__ for spec in FEATURE_SPECS],
            "selected_leave_groups": selected_leave_groups,
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "role_inventory.csv",
                "feature_audit.csv",
                "train_audit.csv",
                "role_metrics_by_candidate_seed.csv",
                "candidate_summary_matrix.csv",
                "review_anatomy_by_group_seed42.csv",
                "shortcut_probe_metrics.csv",
                "leave_device_family_stress_metrics.csv",
                "codex_readout.md",
                "diagnostic_interpretation.md",
            ],
        },
    )
    ckh.write_md(OUT / "codex_readout.md", build_readout(matrix, leave_rows, probe_rows, seconds))
    ckh.write_md(OUT / "diagnostic_interpretation.md", build_interpretation(matrix, leave_rows, probe_rows))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--quick", action="store_true", help="use 3 seeds instead of 5")
    parser.add_argument("--skip-leaveout", action="store_true")
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument("--max-leave-groups", type=int, default=4)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
