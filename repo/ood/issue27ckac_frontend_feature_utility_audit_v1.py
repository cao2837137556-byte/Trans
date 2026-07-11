"""issue27ckac: frontend feature utility/shortcut audit v1.

This is a diagnostic step before building another detector.

Question:

    Can we keep only useful raw115 dimensions and combine them with the useful
    parts of our own frontend, instead of blindly using all raw115 features?

This script scores each feature under strict data boundaries:

* legal fit metrics:
    support_train/id_calib/ood_val/ood_stress, phase=fit
* legal select validation:
    support_val/id_calib/ood_val/ood_stress, phase=select
* report-only stress:
    held device-family OOD/attack rows are diagnosed but are not used for the
    legal recommendation score.

By default this runs a fast raw115-only audit.  `--include-interaction` adds the
CKY interaction/causal frontend blocks, which is heavier because it has to build
flow-temporal evidence from the raw Gotham zip.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402


ISSUE = "issue27ckac_frontend_feature_utility_audit_v1_2026-07-05"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"
RAW_SCHEMA_PATH = (
    cko.ckc.PROJECT_ROOT
    / "datasets"
    / "gotham2025"
    / "derived"
    / "kitsune115_larger_sanity_1m_certified_v1"
    / "gotham_kitsune115_1m_certified_train_state_then_eval_online_feature_schema.json"
)


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def finite(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def fmt(value: Any, digits: int = 4) -> str:
    value_f = finite(value)
    if math.isnan(value_f):
        return "nan"
    return f"{value_f:.{digits}f}"


def raw_feature_names() -> list[str]:
    try:
        schema = json.loads(RAW_SCHEMA_PATH.read_text(encoding="utf-8"))
        names = list(schema.get("feature_names", []))
        if len(names) == 115:
            return [str(v) for v in names]
    except Exception:
        pass
    return [f"raw115_{i:03d}" for i in range(115)]


def raw_family(name: str) -> str:
    if name.startswith("MI_dir_"):
        return "raw_MI_dir"
    if name.startswith("HH_jit"):
        return "raw_HH_jit"
    if name.startswith("HH_"):
        return "raw_HH"
    if name.startswith("HpHp_"):
        return "raw_HpHp"
    if name.startswith("H_"):
        return "raw_H"
    return "raw_other"


def raw_stat_kind(name: str) -> str:
    for suffix in ["weight", "mean", "std", "magnitude", "radius", "covariance"]:
        if name.endswith(f"_{suffix}") or f"_{suffix}_" in name:
            return suffix
    return "other"


def role_indices(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    frame = frame_by_role[role]
    mask = np.ones(len(frame), dtype=bool)
    if phase != "all" and "phase" in frame:
        mask &= frame["phase"].astype(str).to_numpy() == phase
    if include is not None:
        field, value = include
        if field not in frame:
            return np.asarray([], dtype=np.int64)
        mask &= frame[field].astype(str).to_numpy() == str(value)
    if exclude is not None:
        field, value = exclude
        if field in frame:
            mask &= frame[field].astype(str).to_numpy() != str(value)
    return cko.deterministic_cap(np.flatnonzero(mask).astype(np.int64), int(cap))


def auc_binary(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if len(pos) < 2 or len(neg) < 2:
        return float("nan")
    values = np.concatenate([pos, neg])
    ranks = pd.Series(values).rank(method="average").to_numpy(dtype=np.float64)
    n_pos = len(pos)
    n_neg = len(neg)
    rank_sum_pos = float(np.sum(ranks[:n_pos]))
    return float((rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / max(1.0, n_pos * n_neg))


def strength(auc: float) -> float:
    auc = finite(auc)
    if math.isnan(auc):
        return float("nan")
    return float(abs(auc - 0.5) * 2.0)


def signed_effect(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if len(pos) < 2 or len(neg) < 2:
        return float("nan")
    pooled = np.concatenate([pos, neg])
    std = float(np.std(pooled))
    if std < 1e-12:
        return 0.0
    return float((np.mean(pos) - np.mean(neg)) / std)


def max_one_vs_rest_strength(values: np.ndarray, groups: list[str], min_rows: int) -> tuple[float, str, int]:
    values = np.asarray(values, dtype=np.float64)
    groups_arr = np.asarray([str(g) for g in groups], dtype=object)
    best = 0.0
    best_group = ""
    best_rows = 0
    for group in sorted(set(groups_arr.tolist())):
        if not group or group == "NA" or group == "nan":
            continue
        mask = groups_arr == group
        if int(np.sum(mask)) < min_rows or int(np.sum(~mask)) < min_rows:
            continue
        auc = auc_binary(values[mask], values[~mask])
        s = strength(auc)
        if math.isfinite(s) and s > best:
            best = float(s)
            best_group = str(group)
            best_rows = int(np.sum(mask))
    return best, best_group, best_rows


def frame_groups(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    source = frame["source_group"].astype(str).tolist() if "source_group" in frame else ["NA"] * len(frame)
    device = frame["device_family"].astype(str).tolist() if "device_family" in frame else ["NA"] * len(frame)
    return source, device


class FeatureSpace:
    def __init__(
        self,
        name: str,
        feature_names: list[str],
        feature_groups: list[str],
        matrix_fn: Callable[[str, np.ndarray], np.ndarray],
        description: str,
    ) -> None:
        self.name = name
        self.feature_names = feature_names
        self.feature_groups = feature_groups
        self.matrix = matrix_fn
        self.description = description


def collect_labeled(
    space: FeatureSpace,
    frame_by_role: dict[str, pd.DataFrame],
    specs: list[tuple[str, str, int, str]],
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> dict[str, Any]:
    xs: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    role_names: list[str] = []
    phase_names: list[str] = []
    frames: list[pd.DataFrame] = []
    audit: list[dict[str, Any]] = []
    for role, phase, label, label_name in specs:
        if role not in frame_by_role:
            continue
        idx = role_indices(frame_by_role, role, phase, cap, include=include, exclude=exclude)
        if len(idx) == 0:
            audit.append({"role": role, "phase": phase, "label": label, "label_name": label_name, "rows": 0})
            continue
        x = space.matrix(role, idx)
        xs.append(np.asarray(x, dtype=np.float32))
        labels.append(np.full(len(idx), int(label), dtype=np.int64))
        role_names.extend([role] * len(idx))
        phase_names.extend([phase] * len(idx))
        frames.append(frame_by_role[role].iloc[idx].reset_index(drop=True))
        audit.append({"role": role, "phase": phase, "label": label, "label_name": label_name, "rows": int(len(idx))})
    if xs:
        frame = pd.concat(frames, ignore_index=True)
        source, device = frame_groups(frame)
        return {
            "x": np.vstack(xs).astype(np.float32),
            "y": np.concatenate(labels).astype(np.int64),
            "role": role_names,
            "phase": phase_names,
            "source_group": source,
            "device_family": device,
            "audit": audit,
        }
    return {
        "x": np.empty((0, len(space.feature_names)), dtype=np.float32),
        "y": np.empty((0,), dtype=np.int64),
        "role": [],
        "phase": [],
        "source_group": [],
        "device_family": [],
        "audit": audit,
    }


def label_mask(y: np.ndarray, labels: set[int]) -> np.ndarray:
    return np.asarray([int(v) in labels for v in y], dtype=bool)


def score_feature_space(
    space: FeatureSpace,
    frame_by_role: dict[str, pd.DataFrame],
    role_cap: int,
    min_group_rows: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fit_specs = [
        ("support_train", "fit", ckh.CLASS_ATTACK, "attack"),
        ("id_calib", "fit", ckh.CLASS_ID, "id"),
        ("ood_val", "fit", ckh.CLASS_OOD, "ood"),
        ("ood_stress", "fit", ckh.CLASS_HARD_OOD, "hard_ood"),
    ]
    select_specs = [
        ("support_val", "select", ckh.CLASS_ATTACK, "attack"),
        ("id_calib", "select", ckh.CLASS_ID, "id"),
        ("ood_val", "select", ckh.CLASS_OOD, "ood"),
        ("ood_stress", "select", ckh.CLASS_HARD_OOD, "hard_ood"),
    ]
    fit = collect_labeled(space, frame_by_role, fit_specs, role_cap)
    select = collect_labeled(space, frame_by_role, select_specs, role_cap)
    audit = [
        {"feature_space": space.name, "split": "fit", **row} for row in fit["audit"]
    ] + [
        {"feature_space": space.name, "split": "select", **row} for row in select["audit"]
    ]

    rows: list[dict[str, Any]] = []
    x_fit = fit["x"]
    y_fit = fit["y"]
    x_sel = select["x"]
    y_sel = select["y"]
    for j, name in enumerate(space.feature_names):
        group = space.feature_groups[j] if j < len(space.feature_groups) else "unknown"
        fit_attack = x_fit[y_fit == ckh.CLASS_ATTACK, j]
        fit_id = x_fit[y_fit == ckh.CLASS_ID, j]
        fit_ood = x_fit[y_fit == ckh.CLASS_OOD, j]
        fit_hard = x_fit[y_fit == ckh.CLASS_HARD_OOD, j]
        fit_non = x_fit[y_fit != ckh.CLASS_ATTACK, j]

        sel_attack = x_sel[y_sel == ckh.CLASS_ATTACK, j]
        sel_non = x_sel[y_sel != ckh.CLASS_ATTACK, j]
        sel_oodish = x_sel[label_mask(y_sel, {ckh.CLASS_OOD, ckh.CLASS_HARD_OOD}), j]

        auc_attack_non = auc_binary(fit_attack, fit_non)
        auc_attack_id = auc_binary(fit_attack, fit_id)
        auc_attack_ood = auc_binary(fit_attack, np.concatenate([fit_ood, fit_hard]) if len(fit_ood) + len(fit_hard) else np.asarray([]))
        auc_attack_hard = auc_binary(fit_attack, fit_hard)
        auc_id_ood = auc_binary(fit_id, np.concatenate([fit_ood, fit_hard]) if len(fit_ood) + len(fit_hard) else np.asarray([]))
        auc_sel_attack_non = auc_binary(sel_attack, sel_non)
        auc_sel_attack_ood = auc_binary(sel_attack, sel_oodish)

        s_attack_non = strength(auc_attack_non)
        s_attack_id = strength(auc_attack_id)
        s_attack_ood = strength(auc_attack_ood)
        s_attack_hard = strength(auc_attack_hard)
        s_id_ood = strength(auc_id_ood)
        s_sel_non = strength(auc_sel_attack_non)
        s_sel_ood = strength(auc_sel_attack_ood)
        source_s, source_group, source_rows = max_one_vs_rest_strength(x_fit[:, j], fit["source_group"], min_group_rows)
        device_s, device_group, device_rows = max_one_vs_rest_strength(x_fit[:, j], fit["device_family"], min_group_rows)
        shortcut_s = max(source_s, device_s)

        fit_attack_score = 0.45 * finite(s_attack_ood, 0.0) + 0.35 * finite(s_attack_hard, 0.0) + 0.20 * finite(s_attack_id, 0.0)
        select_attack_score = 0.60 * finite(s_sel_ood, 0.0) + 0.40 * finite(s_sel_non, 0.0)
        legal_score = fit_attack_score * 0.65 + select_attack_score * 0.35
        legal_score -= 0.35 * shortcut_s
        legal_score -= 0.15 * finite(s_id_ood, 0.0)
        legal_score = float(legal_score)

        if legal_score >= 0.30 and shortcut_s <= 0.45 and finite(s_sel_ood, 0.0) >= 0.20:
            recommendation = "candidate_attack_evidence"
        elif shortcut_s >= 0.55 or finite(s_id_ood, 0.0) >= 0.45:
            recommendation = "candidate_conflict_context"
        elif legal_score >= 0.18 and shortcut_s <= 0.65:
            recommendation = "weak_attack_evidence_needs_group_check"
        else:
            recommendation = "demote_or_discard"

        rows.append(
            {
                "feature_space": space.name,
                "feature_index": j,
                "feature_name": name,
                "feature_group": group,
                "raw_family": raw_family(name) if space.name == "raw115" else "",
                "raw_stat_kind": raw_stat_kind(name) if space.name == "raw115" else "",
                "n_fit_attack": int(len(fit_attack)),
                "n_fit_nonattack": int(len(fit_non)),
                "auc_attack_vs_nonattack_fit": auc_attack_non,
                "strength_attack_vs_nonattack_fit": s_attack_non,
                "auc_attack_vs_id_fit": auc_attack_id,
                "strength_attack_vs_id_fit": s_attack_id,
                "auc_attack_vs_oodish_fit": auc_attack_ood,
                "strength_attack_vs_oodish_fit": s_attack_ood,
                "auc_attack_vs_hard_ood_fit": auc_attack_hard,
                "strength_attack_vs_hard_ood_fit": s_attack_hard,
                "effect_attack_vs_oodish_fit": signed_effect(fit_attack, np.concatenate([fit_ood, fit_hard]) if len(fit_ood) + len(fit_hard) else np.asarray([])),
                "strength_id_vs_oodish_fit": s_id_ood,
                "strength_attack_vs_nonattack_select": s_sel_non,
                "strength_attack_vs_oodish_select": s_sel_ood,
                "source_shortcut_strength_fit": source_s,
                "source_shortcut_group": source_group,
                "source_shortcut_rows": source_rows,
                "device_shortcut_strength_fit": device_s,
                "device_shortcut_group": device_group,
                "device_shortcut_rows": device_rows,
                "max_shortcut_strength_fit": shortcut_s,
                "legal_selection_score": legal_score,
                "recommendation": recommendation,
            }
        )
    return rows, audit


def group_summary(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not feature_rows:
        return []
    df = pd.DataFrame(feature_rows)
    rows: list[dict[str, Any]] = []
    for (space, group), part in df.groupby(["feature_space", "feature_group"], dropna=False):
        scores = pd.to_numeric(part["legal_selection_score"], errors="coerce")
        shortcuts = pd.to_numeric(part["max_shortcut_strength_fit"], errors="coerce")
        attack_strength = pd.to_numeric(part["strength_attack_vs_oodish_fit"], errors="coerce")
        rec_counts = part["recommendation"].value_counts().to_dict()
        rows.append(
            {
                "feature_space": space,
                "feature_group": group,
                "feature_count": int(len(part)),
                "mean_legal_selection_score": float(scores.mean()) if len(scores) else float("nan"),
                "max_legal_selection_score": float(scores.max()) if len(scores) else float("nan"),
                "mean_attack_oodish_strength_fit": float(attack_strength.mean()) if len(attack_strength) else float("nan"),
                "max_shortcut_strength_fit": float(shortcuts.max()) if len(shortcuts) else float("nan"),
                "candidate_attack_evidence_count": int(rec_counts.get("candidate_attack_evidence", 0)),
                "weak_attack_evidence_count": int(rec_counts.get("weak_attack_evidence_needs_group_check", 0)),
                "conflict_context_count": int(rec_counts.get("candidate_conflict_context", 0)),
                "demote_or_discard_count": int(rec_counts.get("demote_or_discard", 0)),
            }
        )
    return sorted(rows, key=lambda r: finite(r["max_legal_selection_score"], -999.0), reverse=True)


def held_stress_rows(
    spaces: list[FeatureSpace],
    frame_by_role: dict[str, pd.DataFrame],
    feature_rows: list[dict[str, Any]],
    held_values: list[str],
    role_cap: int,
    top_k: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    top_features = (
        pd.DataFrame(feature_rows)
        .sort_values("legal_selection_score", ascending=False)
        .groupby("feature_space", as_index=False)
        .head(top_k)
    )
    top_by_space: dict[str, set[int]] = {}
    for _idx, row in top_features.iterrows():
        top_by_space.setdefault(str(row["feature_space"]), set()).add(int(row["feature_index"]))

    fit_specs = [
        ("support_train", "fit", ckh.CLASS_ATTACK, "attack"),
        ("id_calib", "fit", ckh.CLASS_ID, "id"),
        ("ood_val", "fit", ckh.CLASS_OOD, "ood"),
        ("ood_stress", "fit", ckh.CLASS_HARD_OOD, "hard_ood"),
    ]
    for space in spaces:
        selected = sorted(top_by_space.get(space.name, set()))
        if not selected:
            continue
        fit = collect_labeled(space, frame_by_role, fit_specs, role_cap)
        x_fit = fit["x"]
        y_fit = fit["y"]
        mean = np.mean(x_fit, axis=0)
        std = np.std(x_fit, axis=0)
        std[std < 1e-6] = 1.0
        z_fit = (x_fit - mean) / std
        class_means = {}
        for label in [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD, ckh.CLASS_ATTACK]:
            mask = y_fit == label
            if int(np.sum(mask)):
                class_means[label] = np.mean(z_fit[mask], axis=0)
        for held in held_values:
            for role, phase, role_kind in [
                ("ood_val", "select", "held_ood"),
                ("ood_stress", "select", "held_hard_ood"),
                ("sealed_final_ood", "all", "held_sealed_ood_report"),
                ("future_query", "select", "held_future_attack_report"),
                ("sealed_final_attack", "all", "held_sealed_attack_report"),
            ]:
                if role not in frame_by_role:
                    continue
                idx = role_indices(frame_by_role, role, phase, role_cap, include=("device_family", held))
                if len(idx) == 0:
                    continue
                z_eval = (space.matrix(role, idx) - mean) / std
                held_mean = np.mean(z_eval, axis=0)
                for j in selected:
                    attack_dist = abs(float(held_mean[j] - class_means.get(ckh.CLASS_ATTACK, np.zeros_like(mean))[j]))
                    nonattack_dists = [
                        abs(float(held_mean[j] - class_means[label][j]))
                        for label in [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD]
                        if label in class_means
                    ]
                    nearest_nonattack = min(nonattack_dists) if nonattack_dists else float("nan")
                    rows.append(
                        {
                            "feature_space": space.name,
                            "feature_index": j,
                            "feature_name": space.feature_names[j],
                            "feature_group": space.feature_groups[j],
                            "held_value": held,
                            "role": role,
                            "phase": phase,
                            "role_kind": role_kind,
                            "rows": int(len(idx)),
                            "held_mean_z": float(held_mean[j]),
                            "distance_to_attack_fit_mean_z": attack_dist,
                            "distance_to_nearest_nonattack_fit_mean_z": nearest_nonattack,
                            "attack_affinity_positive_means_closer_to_attack": float(nearest_nonattack - attack_dist) if math.isfinite(nearest_nonattack) else float("nan"),
                            "used_for_legal_selection": False,
                        }
                    )
    return rows


def recommended_manifest(feature_rows: list[dict[str, Any]], max_attack_features: int, max_conflict_features: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    df = pd.DataFrame(feature_rows)
    if df.empty:
        return rows
    attack = df[df["recommendation"].isin(["candidate_attack_evidence", "weak_attack_evidence_needs_group_check"])].copy()
    attack = attack.sort_values(["legal_selection_score", "strength_attack_vs_oodish_select"], ascending=False).head(max_attack_features)
    conflict = df[df["recommendation"] == "candidate_conflict_context"].copy()
    conflict = conflict.sort_values(["max_shortcut_strength_fit", "strength_id_vs_oodish_fit"], ascending=False).head(max_conflict_features)
    for purpose, part in [("attack_evidence_candidate", attack), ("conflict_context_candidate", conflict)]:
        for rank, (_idx, row) in enumerate(part.iterrows(), start=1):
            rows.append(
                {
                    "rank": rank,
                    "purpose": purpose,
                    "feature_space": row["feature_space"],
                    "feature_index": int(row["feature_index"]),
                    "feature_name": row["feature_name"],
                    "feature_group": row["feature_group"],
                    "legal_selection_score": row["legal_selection_score"],
                    "max_shortcut_strength_fit": row["max_shortcut_strength_fit"],
                    "recommendation": row["recommendation"],
                    "selection_boundary": "legal_fit_select_only; report_only_stress_not_used",
                }
            )
    return rows


def build_interaction_spaces(
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    smoke: bool,
) -> tuple[list[FeatureSpace], list[dict[str, Any]], list[dict[str, Any]]]:
    import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
    import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402

    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=smoke, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    frontend = cky.InteractionCausalFrontend(builder)
    _ = frontend.matrix("support_train", np.asarray([0], dtype=np.int64), "full")
    reg = frontend.registry()
    spaces: list[FeatureSpace] = []
    for block in ["attack_mechanism", "conflict_context"]:
        names = [str(r["feature_name"]) for r in reg if str(r["evidence_group"]) == block]
        groups = [block] * len(names)
        spaces.append(
            FeatureSpace(
                name=f"cky_{block}",
                feature_names=names,
                feature_groups=groups,
                matrix_fn=lambda role, idx, b=block: frontend.matrix(role, idx, b),
                description=f"CKY {block} block",
            )
        )
    return spaces, cache.audit_rows, reg


def build_readout(
    out: Path,
    feature_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
    stress_rows: list[dict[str, Any]],
    seconds: float,
) -> list[str]:
    df = pd.DataFrame(feature_rows)
    man = pd.DataFrame(manifest_rows)
    stress = pd.DataFrame(stress_rows)
    lines = [
        "# issue27ckac frontend feature utility audit v1",
        "",
        "## Scope",
        "",
        "Diagnostic for selecting useful raw115/self-frontend evidence before training another detector.",
        "Recommendations are based on legal fit/select metrics only; held-family stress is report-only.",
        "",
        "## Top attack-evidence candidates",
        "",
        "| rank | feature_space | feature | score | shortcut | recommendation |",
        "|---:|---|---|---:|---:|---|",
    ]
    if not man.empty:
        attack = man[man["purpose"] == "attack_evidence_candidate"].head(12)
        for _idx, row in attack.iterrows():
            lines.append(
                f"| {int(row['rank'])} | {row['feature_space']} | {row['feature_name']} | "
                f"{fmt(row['legal_selection_score'])} | {fmt(row['max_shortcut_strength_fit'])} | {row['recommendation']} |"
            )
    lines.extend(
        [
            "",
            "## Strongest shortcut/conflict candidates",
            "",
            "| rank | feature_space | feature | score | shortcut | recommendation |",
            "|---:|---|---|---:|---:|---|",
        ]
    )
    if not man.empty:
        conflict = man[man["purpose"] == "conflict_context_candidate"].head(12)
        for _idx, row in conflict.iterrows():
            lines.append(
                f"| {int(row['rank'])} | {row['feature_space']} | {row['feature_name']} | "
                f"{fmt(row['legal_selection_score'])} | {fmt(row['max_shortcut_strength_fit'])} | {row['recommendation']} |"
            )
    lines.extend(
        [
            "",
            "## Group summary",
            "",
            "| feature_space | group | count | max score | mean score | attack candidates | conflict candidates | max shortcut |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in group_rows[:16]:
        lines.append(
            f"| {row['feature_space']} | {row['feature_group']} | {row['feature_count']} | "
            f"{fmt(row['max_legal_selection_score'])} | {fmt(row['mean_legal_selection_score'])} | "
            f"{row['candidate_attack_evidence_count']} | {row['conflict_context_count']} | {fmt(row['max_shortcut_strength_fit'])} |"
        )
    if not stress.empty:
        stress2 = stress.sort_values("attack_affinity_positive_means_closer_to_attack", ascending=False).head(12)
        lines.extend(
            [
                "",
                "## Report-only held-family attack-affinity warnings",
                "",
                "| held | role | feature_space | feature | affinity | rows |",
                "|---|---|---|---|---:|---:|",
            ]
        )
        for _idx, row in stress2.iterrows():
            lines.append(
                f"| {row['held_value']} | {row['role']} | {row['feature_space']} | {row['feature_name']} | "
                f"{fmt(row['attack_affinity_positive_means_closer_to_attack'])} | {int(row['rows'])} |"
            )
    counts = df["recommendation"].value_counts().to_dict() if not df.empty else {}
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Legal recommendation uses only support_train/id_calib/ood_val/ood_stress fit and support_val/id_calib/ood_val/ood_stress select.",
            "- Query/future/sealed and held-family stress rows are report-only diagnostics, not feature-selection labels.",
            "- This is a frontend-selection audit, not a detector result.",
            f"- recommendation counts: {json.dumps({str(k): int(v) for k, v in counts.items()}, ensure_ascii=False)}",
            f"- output: `{out}`",
            f"- runtime seconds: {fmt(seconds, 1)}",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(bool(args.smoke))
    ckt.add_family_columns(frame_by_role)
    raw_names = raw_feature_names()
    raw_space = FeatureSpace(
        name="raw115",
        feature_names=raw_names,
        feature_groups=[raw_family(n) for n in raw_names],
        matrix_fn=lambda role, idx: np.asarray(x_by_role[role][idx], dtype=np.float32),
        description="Raw Kitsune115D dimensions, audited one by one.",
    )
    spaces = [raw_space]
    flow_audit_rows: list[dict[str, Any]] = []
    frontend_registry: list[dict[str, Any]] = []
    if bool(args.include_interaction):
        extra_spaces, flow_audit_rows, frontend_registry = build_interaction_spaces(x_by_role, frame_by_role, bool(args.smoke))
        spaces.extend(extra_spaces)

    feature_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for space in spaces:
        rows, audit = score_feature_space(space, frame_by_role, int(args.role_cap), int(args.min_group_rows))
        feature_rows.extend(rows)
        audit_rows.extend(audit)

    group_rows = group_summary(feature_rows)
    manifest_rows = recommended_manifest(feature_rows, int(args.max_attack_features), int(args.max_conflict_features))
    held_values = [v.strip() for v in str(args.held_values).split(",") if v.strip()]
    stress_rows = held_stress_rows(spaces, frame_by_role, feature_rows, held_values, int(args.role_cap), int(args.stress_top_k))
    seconds = time.time() - started

    cko.write_csv(out / "feature_scores.csv", feature_rows)
    cko.write_csv(out / "feature_group_scores.csv", group_rows)
    cko.write_csv(out / "recommended_frontend_manifest.csv", manifest_rows)
    cko.write_csv(out / "held_family_feature_stress_report_only.csv", stress_rows)
    cko.write_csv(out / "role_usage_audit.csv", audit_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", flow_audit_rows)
    cko.write_csv(out / "frontend_registry.csv", frontend_registry)
    cko.write_md(out / "codex_readout.md", build_readout(out, feature_rows, group_rows, manifest_rows, stress_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "smoke": bool(args.smoke),
            "role_cap": int(args.role_cap),
            "include_interaction": bool(args.include_interaction),
            "held_values": held_values,
            "data_use_boundary": {
                "legal_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "legal_select_validation_roles": ["support_val select", "id_calib select", "ood_val select", "ood_stress select"],
                "report_only_stress_roles": ["ood_val select held family", "ood_stress select held family", "sealed/future report roles held family"],
                "report_only_used_for_legal_selection": False,
            },
            "recommendation_formula": {
                "positive_terms": ["attack-vs-OOD strength on fit", "attack-vs-hard-OOD strength on fit", "attack-vs-ID strength on fit", "attack validation on select"],
                "penalties": ["source/device shortcut one-vs-rest strength", "ID-vs-OOD benign split strength"],
            },
            "input_audit": input_audit,
            "raw_schema_path": str(RAW_SCHEMA_PATH),
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", default=True)
    parser.add_argument("--role-cap", type=int, default=768)
    parser.add_argument("--min-group-rows", type=int, default=12)
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--include-interaction", action="store_true")
    parser.add_argument("--max-attack-features", type=int, default=32)
    parser.add_argument("--max-conflict-features", type=int, default=32)
    parser.add_argument("--stress-top-k", type=int, default=24)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
