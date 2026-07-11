"""issue27ckv: frontend entanglement audit v1.

This is a diagnostic, not a repair.

It asks which evidence groups make uncovered OOD families look like attack.
For a trained CKS-style neural head, the script performs legal counterfactual
feature masking:

    train excluding held device_family
    calibrate threshold excluding held device_family
    evaluate held device_family
    replace one feature group with its legal-fit mean
    measure whether held-OOD hard alarms drop and whether attack rows break

It also computes group-only affinity distances for baseline hard held-OOD rows:
whether each feature group is nearest to the attack fit centroid or to a
non-attack fit centroid.

Strict boundary:
* query/future/sealed rows are never used for fitting, centroids, masks, or
  thresholds;
* held device_family is excluded from fit and threshold selection.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27cks_neural_causal_selective_head_v1 as cks  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402


ISSUE = "issue27ckv_frontend_entanglement_audit_v1_2026-07-03"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"
DEFAULT_CANDIDATES = "N3_raw_flow_aug_adv_rex_selective"


CKV_EXTRA_CANDIDATES = [
    cks.NeuralCandidate(
        name="N4_raw_flow_aug_strong_invariant_selective",
        feature_kind="raw_flow_aug",
        hidden_dim=144,
        epochs=100,
        lr=6e-4,
        weight_decay=3e-4,
        dropout=0.25,
        adv_lambda=0.20,
        rex_lambda=0.55,
        worst_group_lambda=0.20,
        description="CKV diagnostic copy of the stronger invariant neural head from CKU.",
    ),
]


def all_candidates() -> list[cks.NeuralCandidate]:
    return [*cks.NEURAL_CANDIDATES, *CKV_EXTRA_CANDIDATES]


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def label_name(label: int) -> str:
    return str(ckq.CLASS_NAMES.get(int(label), f"class_{label}"))


def group_indices_for_feature_kind(
    feature_kind: str,
    raw_dim: int,
) -> list[dict[str, Any]]:
    flow_dim = len(ckq.FLOW_TEMPORAL_FEATURES)
    aug_dim = cks.enhanced_flow_summary_dim()
    groups: list[dict[str, Any]] = []
    raw_all = np.arange(0, raw_dim, dtype=np.int64)
    flow_all = np.asarray([], dtype=np.int64)
    aug_all = np.asarray([], dtype=np.int64)

    if feature_kind in {"raw", "raw_flow", "raw_flow_aug"}:
        groups.append(
            {
                "group": "raw115_all",
                "block": "raw115",
                "start": 0,
                "end": raw_dim,
                "indices": raw_all,
                "description": "All raw Kitsune115D features.",
            }
        )

    if feature_kind in {"raw_flow", "raw_flow_aug"}:
        flow_offset = raw_dim
        flow_all = np.arange(flow_offset, flow_offset + flow_dim, dtype=np.int64)
        token_groups = {
            "flow_current_protocol": ["cur_is_", "cur_tcp_", "cur_syn_without_ack", "cur_ack_without_syn", "cur_tcp_syn", "cur_tcp_ack", "cur_tcp_rst"],
            "flow_fanout": ["unique_dst_frac", "unique_dport_frac", "unique_src_frac", "unique_sport_frac", "dport_fanout", "dst_src_pressure"],
            "flow_rate_burst": ["count_frac", "event_rate_log", "byte_rate_log", "short_long_ratio"],
            "flow_duration_gap_size": ["duration_log", "current_gap_log", "len_mean_log", "len_std_log", "cur_log_frame_len"],
            "flow_reverse_balance": ["reverse", "balance"],
            "flow_scope_file": ["prior_file_"],
            "flow_scope_src": ["prior_src_"],
            "flow_scope_dst": ["prior_dst_"],
            "flow_scope_pair": ["prior_pair_"],
            "flow_scope_flow5": ["prior_flow5_"],
        }
        for name, tokens in token_groups.items():
            cols = [i for i, fname in enumerate(ckq.FLOW_TEMPORAL_FEATURES) if any(token in fname for token in tokens)]
            if not cols:
                continue
            idx = np.asarray([flow_offset + col for col in sorted(set(cols))], dtype=np.int64)
            groups.append(
                {
                    "group": name,
                    "block": "flow_temporal",
                    "start": int(idx.min()),
                    "end": int(idx.max()) + 1,
                    "indices": idx,
                    "description": f"Flow-temporal columns matching {tokens}.",
                }
            )
        groups.append(
            {
                "group": "flow_all",
                "block": "flow_temporal",
                "start": flow_offset,
                "end": flow_offset + flow_dim,
                "indices": flow_all,
                "description": "All ckq past-only flow-temporal columns.",
            }
        )

    if feature_kind == "raw_flow_aug":
        aug_offset = raw_dim + flow_dim
        aug_all = np.arange(aug_offset, aug_offset + aug_dim, dtype=np.int64)
        cursor = aug_offset
        for name in cks.FLOW_SUMMARY_GROUPS:
            idx = np.arange(cursor, cursor + 4, dtype=np.int64)
            groups.append(
                {
                    "group": f"aug_summary_{name}",
                    "block": "enhanced_summary",
                    "start": int(idx.min()),
                    "end": int(idx.max()) + 1,
                    "indices": idx,
                    "description": f"Enhanced summary stats for {name}.",
                }
            )
            cursor += 4
        idx = np.arange(cursor, cursor + 10, dtype=np.int64)
        groups.append(
            {
                "group": "aug_protocol_contrasts",
                "block": "enhanced_summary",
                "start": int(idx.min()),
                "end": int(idx.max()) + 1,
                "indices": idx,
                "description": "Enhanced protocol/ratio contrast channels.",
            }
        )
        groups.append(
            {
                "group": "aug_all",
                "block": "enhanced_summary",
                "start": aug_offset,
                "end": aug_offset + aug_dim,
                "indices": aug_all,
                "description": "All enhanced summary channels.",
            }
        )
    combo_specs: list[tuple[str, str, list[np.ndarray], str]] = []
    if feature_kind == "raw_flow":
        combo_specs.extend(
            [
                ("raw_plus_flow_all", "combo", [raw_all, flow_all], "Raw115 plus all flow-temporal columns."),
                ("all_features", "combo", [raw_all, flow_all], "All currently available features."),
            ]
        )
    elif feature_kind == "raw_flow_aug":
        combo_specs.extend(
            [
                ("raw_plus_flow_all", "combo", [raw_all, flow_all], "Raw115 plus all flow-temporal columns."),
                ("raw_plus_aug_all", "combo", [raw_all, aug_all], "Raw115 plus enhanced summary columns."),
                ("flow_plus_aug_all", "combo", [flow_all, aug_all], "All non-raw flow/mechanism columns."),
                ("all_features", "combo", [raw_all, flow_all, aug_all], "All raw, flow-temporal, and enhanced summary features."),
            ]
        )
    for name, block, arrays, description in combo_specs:
        idx = np.unique(np.concatenate([arr for arr in arrays if len(arr)])).astype(np.int64)
        if len(idx):
            groups.append(
                {
                    "group": name,
                    "block": block,
                    "start": int(idx.min()),
                    "end": int(idx.max()) + 1,
                    "indices": idx,
                    "description": description,
                }
            )
    return groups


def role_indices(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    return cks.role_indices_filtered(frame_by_role, role, phase, cap, include=include, exclude=exclude)


def collect_fit_features(
    fitted: cks.FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    specs = [
        ("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP),
        ("id_calib", "fit", ckh.CLASS_ID, train_cap),
        ("ood_val", "fit", ckh.CLASS_OOD, train_cap),
        ("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap),
    ]
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []
    for role, phase, label, cap in specs:
        idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
        x = cks.feature_matrix(builder, fitted.candidate.feature_kind, role, idx)
        xs.append(x)
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append(
            {
                "candidate": fitted.candidate.name,
                "role": role,
                "phase": phase,
                "label": label,
                "label_name": label_name(label),
                "rows": len(idx),
                "used_for": "fit_mean_and_affinity_centroids",
                "exclude_field": exclude[0] if exclude else "",
                "exclude_value": exclude[1] if exclude else "",
            }
        )
    return np.vstack(xs).astype(np.float32), np.concatenate(ys).astype(np.int64), audit


def predict_decision(fitted: cks.FittedNeural, x: np.ndarray, threshold_row: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    score = cks.scores_from_proba(fitted.predict_proba(x))
    raw = score["attack_score"] > float(threshold_row["attack_threshold"])
    review = raw & (score["margin_score"] <= float(threshold_row["margin_review_threshold"]))
    hard = raw & (~review)
    return score, {"raw_alarm": raw, "review": review, "hard": hard}


def eval_x(
    fitted: cks.FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    eval_cap: int,
    threshold_row: dict[str, Any],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
    mask_indices: np.ndarray | None = None,
    fit_mean: np.ndarray | None = None,
) -> tuple[dict[str, Any], np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    idx = role_indices(frame_by_role, role, phase, eval_cap, include=include, exclude=exclude)
    x = cks.feature_matrix(builder, fitted.candidate.feature_kind, role, idx)
    if mask_indices is not None and fit_mean is not None and len(mask_indices):
        x = x.copy()
        x[:, mask_indices] = fit_mean[mask_indices].reshape(1, -1)
    score, decision = predict_decision(fitted, x, threshold_row)
    row = {
        "role": role,
        "phase": phase,
        "rows": len(idx),
        "raw_alarm_rate": ckg.rate(decision["raw_alarm"]),
        "review_rate": ckg.rate(decision["review"]),
        "hard_alarm_rate": ckg.rate(decision["hard"]),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(idx) else float("nan"),
        "margin_score_mean": float(np.mean(score["margin_score"])) if len(idx) else float("nan"),
        "entropy_score_mean": float(np.mean(score["entropy_score"])) if len(idx) else float("nan"),
    }
    return row, idx, score, decision


def class_centroids(x_fit_z: np.ndarray, y_fit: np.ndarray, group_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = np.asarray(ckq.CLASS_LABELS, dtype=np.int64)
    centers = []
    scales = []
    for label in labels:
        rows = x_fit_z[y_fit == int(label)][:, group_idx]
        if len(rows):
            center = np.mean(rows, axis=0)
            scale = np.std(rows, axis=0)
        else:
            center = np.zeros(len(group_idx), dtype=np.float32)
            scale = np.ones(len(group_idx), dtype=np.float32)
        scale = np.asarray(scale, dtype=np.float32)
        scale[scale < 1e-3] = 1.0
        centers.append(np.asarray(center, dtype=np.float32))
        scales.append(scale)
    return labels, np.vstack(centers).astype(np.float32), np.vstack(scales).astype(np.float32)


def group_affinity(
    fitted: cks.FittedNeural,
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    x_eval: np.ndarray,
    eval_mask: np.ndarray,
    groups: list[dict[str, Any]],
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    if not len(x_eval) or not np.any(eval_mask):
        return []
    x_fit_z = fitted.transform(x_fit)
    x_eval_z = fitted.transform(x_eval)[eval_mask]
    rows: list[dict[str, Any]] = []
    for group in groups:
        idx = np.asarray(group["indices"], dtype=np.int64)
        if len(idx) == 0:
            continue
        labels, centers, scales = class_centroids(x_fit_z, y_fit, idx)
        part = x_eval_z[:, idx]
        dists = []
        for center, scale in zip(centers, scales):
            scaled = (part - center.reshape(1, -1)) / scale.reshape(1, -1)
            dists.append(np.sqrt(np.mean(np.square(scaled), axis=1)))
        dist = np.vstack(dists).T
        nearest_pos = np.argmin(dist, axis=1)
        nearest_labels = labels[nearest_pos]
        attack_col = int(np.flatnonzero(labels == ckh.CLASS_ATTACK)[0])
        nonattack_cols = [i for i, label in enumerate(labels) if int(label) != ckh.CLASS_ATTACK]
        attack_dist = dist[:, attack_col]
        nearest_nonattack_dist = np.min(dist[:, nonattack_cols], axis=1) if nonattack_cols else np.full(len(dist), np.nan)
        rows.append(
            {
                **meta,
                "group": group["group"],
                "block": group["block"],
                "group_dim": int(len(idx)),
                "baseline_hard_rows": int(np.sum(eval_mask)),
                "nearest_attack_rate": ckg.rate(nearest_labels == ckh.CLASS_ATTACK),
                "attack_dist_mean": float(np.mean(attack_dist)),
                "nearest_nonattack_dist_mean": float(np.mean(nearest_nonattack_dist)),
                "attack_minus_nonattack_dist_mean": float(np.mean(attack_dist - nearest_nonattack_dist)),
                "nearest_label_mode": label_name(int(pd.Series(nearest_labels).mode().iloc[0])) if len(nearest_labels) else "",
            }
        )
    return rows


def audit_candidate_held(
    candidate: cks.NeuralCandidate,
    held_value: str,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    exclude = ("device_family", held_value)
    include = ("device_family", held_value)
    fitted, train_rows, history_rows = cks.fit_neural_candidate(candidate, builder, frame_by_role, train_cap, exclude=exclude)
    attack_thr = cks.attack_threshold(fitted, builder, frame_by_role, eval_cap, exclude=exclude)
    threshold_row = cks.review_margin_threshold(
        fitted,
        builder,
        frame_by_role,
        attack_thr,
        eval_cap,
        cks.REVIEW_POLICIES[0],
        exclude=exclude,
    )
    x_fit, y_fit, fit_audit = collect_fit_features(fitted, builder, frame_by_role, train_cap, exclude=exclude)
    fit_mean = np.mean(x_fit, axis=0).astype(np.float32)
    raw_dim = int(builder.x_by_role["support_train"].shape[1])
    groups = group_indices_for_feature_kind(candidate.feature_kind, raw_dim)

    effect_rows: list[dict[str, Any]] = []
    affinity_rows: list[dict[str, Any]] = []
    target_roles = [
        ("ood_val", "select", "held_ood"),
        ("ood_stress", "select", "held_ood"),
        ("sealed_final_ood", "all", "held_ood_report"),
        ("future_query", "select", "attack_report_global"),
        ("sealed_final_attack", "all", "attack_report_global"),
    ]
    for role, phase, role_kind in target_roles:
        role_include = include if role_kind.startswith("held_ood") else None
        role_exclude = None if role_kind.startswith("held_ood") else exclude
        base, idx, base_score, base_decision = eval_x(
            fitted,
            builder,
            frame_by_role,
            role,
            phase,
            eval_cap,
            threshold_row,
            include=role_include,
            exclude=role_exclude,
        )
        base_meta = {
            "candidate": candidate.name,
            "held_field": "device_family",
            "held_value": held_value,
            "role": role,
            "phase": phase,
            "role_kind": role_kind,
            "mask_group": "baseline_none",
            "mask_block": "none",
            "group_dim": 0,
            "rows": base["rows"],
            "baseline_raw_alarm_rate": base["raw_alarm_rate"],
            "baseline_hard_alarm_rate": base["hard_alarm_rate"],
            "baseline_review_rate": base["review_rate"],
            "baseline_attack_score_mean": base["attack_score_mean"],
            "masked_raw_alarm_rate": base["raw_alarm_rate"],
            "masked_hard_alarm_rate": base["hard_alarm_rate"],
            "masked_review_rate": base["review_rate"],
            "masked_attack_score_mean": base["attack_score_mean"],
            "delta_hard_drop": 0.0,
            "delta_attack_score_drop": 0.0,
            "interpretation_hint": "baseline",
        }
        effect_rows.append(base_meta)

        x_eval = cks.feature_matrix(builder, fitted.candidate.feature_kind, role, idx)
        if role_kind.startswith("held_ood"):
            meta = {
                "candidate": candidate.name,
                "held_field": "device_family",
                "held_value": held_value,
                "role": role,
                "phase": phase,
                "role_kind": role_kind,
            }
            affinity_rows.extend(group_affinity(fitted, x_fit, y_fit, x_eval, base_decision["hard"], groups, meta))

        for group in groups:
            masked, _idx2, _score2, _decision2 = eval_x(
                fitted,
                builder,
                frame_by_role,
                role,
                phase,
                eval_cap,
                threshold_row,
                include=role_include,
                exclude=role_exclude,
                mask_indices=np.asarray(group["indices"], dtype=np.int64),
                fit_mean=fit_mean,
            )
            hard_drop = float(base["hard_alarm_rate"] - masked["hard_alarm_rate"])
            score_drop = float(base["attack_score_mean"] - masked["attack_score_mean"])
            if role_kind.startswith("held_ood") and hard_drop > 0.05:
                hint = "entangling_or_attack-like_for_held_ood"
            elif role_kind.startswith("attack") and hard_drop > 0.05:
                hint = "needed_for_attack_detection"
            elif role_kind.startswith("held_ood") and score_drop > 0.05:
                hint = "raises_held_ood_attack_score"
            else:
                hint = "small_or_no_effect"
            effect_rows.append(
                {
                    "candidate": candidate.name,
                    "held_field": "device_family",
                    "held_value": held_value,
                    "role": role,
                    "phase": phase,
                    "role_kind": role_kind,
                    "mask_group": group["group"],
                    "mask_block": group["block"],
                    "group_dim": int(len(group["indices"])),
                    "rows": base["rows"],
                    "baseline_raw_alarm_rate": base["raw_alarm_rate"],
                    "baseline_hard_alarm_rate": base["hard_alarm_rate"],
                    "baseline_review_rate": base["review_rate"],
                    "baseline_attack_score_mean": base["attack_score_mean"],
                    "masked_raw_alarm_rate": masked["raw_alarm_rate"],
                    "masked_hard_alarm_rate": masked["hard_alarm_rate"],
                    "masked_review_rate": masked["review_rate"],
                    "masked_attack_score_mean": masked["attack_score_mean"],
                    "delta_hard_drop": hard_drop,
                    "delta_attack_score_drop": score_drop,
                    "interpretation_hint": hint,
                }
            )

    group_rows = [
        {
            "candidate": candidate.name,
            "feature_kind": candidate.feature_kind,
            "group": group["group"],
            "block": group["block"],
            "group_dim": int(len(group["indices"])),
            "start": group["start"],
            "end": group["end"],
            "description": group["description"],
        }
        for group in groups
    ]
    threshold_rows = [{**threshold_row, "held_field": "device_family", "held_value": held_value}]
    return effect_rows, affinity_rows, group_rows, train_rows + fit_audit + threshold_rows, history_rows


def summarize_effects(effect_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in effect_rows if row["mask_group"] != "baseline_none"]
    out: list[dict[str, Any]] = []
    for (candidate, held, group), part in pd.DataFrame(rows).groupby(["candidate", "held_value", "mask_group"], sort=True):
        part = part.copy()
        held_ood = part[part["role_kind"].astype(str).str.startswith("held_ood")]
        attack = part[part["role_kind"].astype(str).str.startswith("attack")]
        out.append(
            {
                "candidate": candidate,
                "held_value": held,
                "mask_group": group,
                "block": str(part["mask_block"].iloc[0]) if len(part) else "",
                "group_dim": int(part["group_dim"].iloc[0]) if len(part) else 0,
                "held_ood_max_hard_drop": float(pd.to_numeric(held_ood["delta_hard_drop"], errors="coerce").max()) if len(held_ood) else float("nan"),
                "held_ood_max_score_drop": float(pd.to_numeric(held_ood["delta_attack_score_drop"], errors="coerce").max()) if len(held_ood) else float("nan"),
                "attack_max_hard_drop": float(pd.to_numeric(attack["delta_hard_drop"], errors="coerce").max()) if len(attack) else float("nan"),
                "attack_max_score_drop": float(pd.to_numeric(attack["delta_attack_score_drop"], errors="coerce").max()) if len(attack) else float("nan"),
            }
        )
    for row in out:
        h = row["held_ood_max_hard_drop"]
        a = row["attack_max_hard_drop"]
        if np.isfinite(h) and h > 0.05 and (not np.isfinite(a) or a <= 0.02):
            row["diagnosis"] = "candidate_pollution_source"
        elif np.isfinite(h) and h > 0.05 and np.isfinite(a) and a > 0.05:
            row["diagnosis"] = "shared_strong_but_dangerous_evidence"
        elif np.isfinite(row["held_ood_max_score_drop"]) and row["held_ood_max_score_drop"] > 0.05:
            row["diagnosis"] = "score_entangler_without_decision_flip"
        else:
            row["diagnosis"] = "no_clear_counterfactual_effect"
    return sorted(out, key=lambda r: (str(r["held_value"]), -float(r["held_ood_max_hard_drop"] if np.isfinite(r["held_ood_max_hard_drop"]) else -999), -float(r["held_ood_max_score_drop"] if np.isfinite(r["held_ood_max_score_drop"]) else -999)))


def build_readout(summary_rows: list[dict[str, Any]], affinity_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckv frontend entanglement audit v1",
        "",
        "## Scope",
        "",
        "Diagnostic counterfactual masking audit for OOD/attack feature entanglement.",
        "This is not a repair and not cross-dataset proof.",
        "",
        "## Counterfactual group summary",
        "",
        "| candidate | held family | group | block | held OOD hard drop | held OOD score drop | attack hard drop | diagnosis |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in summary_rows[:80]:
        lines.append(
            f"| {row['candidate']} | {row['held_value']} | {row['mask_group']} | {row['block']} | "
            f"{cko.fmt(row['held_ood_max_hard_drop'])} | {cko.fmt(row['held_ood_max_score_drop'])} | "
            f"{cko.fmt(row['attack_max_hard_drop'])} | {row['diagnosis']} |"
        )
    lines.extend(
        [
            "",
            "## Held-OOD hard affinity snapshot",
            "",
            "| candidate | held family | role | group | hard rows | nearest attack rate | attack dist | nearest nonattack dist | attack-minus-nonattack | nearest label mode |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    affinity_sorted = sorted(
        affinity_rows,
        key=lambda r: (
            str(r["held_value"]),
            str(r["role"]),
            -float(r.get("nearest_attack_rate", 0.0)),
            float(r.get("attack_minus_nonattack_dist_mean", 999.0)),
        ),
    )
    for row in affinity_sorted[:80]:
        lines.append(
            f"| {row['candidate']} | {row['held_value']} | {row['role']} | {row['group']} | {row['baseline_hard_rows']} | "
            f"{cko.fmt(row['nearest_attack_rate'])} | {cko.fmt(row['attack_dist_mean'])} | "
            f"{cko.fmt(row['nearest_nonattack_dist_mean'])} | {cko.fmt(row['attack_minus_nonattack_dist_mean'])} | "
            f"{row['nearest_label_mode']} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit, fit means, centroids, and thresholds use only legal fit/select roles.",
            "- Held device_family is excluded from fit and threshold selection.",
            "- Query/future/sealed rows are report-only and used only for counterfactual evaluation.",
            "- Positive held OOD hard drop means masking that group reduced false hard alarms.",
            "- Positive attack hard drop means masking that group damaged attack detection.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    cks.set_seeds()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(True)
    x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
        x_by_role,
        frame_by_role,
        int(args.role_cap),
        int(args.source_cap),
        cap_rule="frontend entanglement audit capped local smoke",
    )
    ckt.add_family_columns(frame_by_role)
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    candidate_names = set(item.strip() for item in str(args.candidates).split(",") if item.strip())
    candidates = [candidate for candidate in all_candidates() if candidate.name in candidate_names]
    held_values = [item.strip() for item in str(args.held_values).split(",") if item.strip()]

    effect_rows: list[dict[str, Any]] = []
    affinity_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []

    for held_value in held_values:
        counts = {
            "ood_val": ckt.rows_for(frame_by_role, "ood_val", "select", "device_family", held_value, int(args.eval_cap)),
            "ood_stress": ckt.rows_for(frame_by_role, "ood_stress", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_ood": ckt.rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", held_value, int(args.eval_cap)),
            "future_query": ckt.rows_for(frame_by_role, "future_query", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_attack": ckt.rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", held_value, int(args.eval_cap)),
        }
        selected_rows.append({"held_field": "device_family", "held_value": held_value, "total_eval_rows": sum(counts.values()), **counts})
        for candidate in candidates:
            eff, aff, grp, train, hist = audit_candidate_held(
                candidate,
                held_value,
                builder,
                frame_by_role,
                int(args.train_cap),
                int(args.eval_cap),
            )
            effect_rows.extend(eff)
            affinity_rows.extend(aff)
            group_rows.extend(grp)
            train_rows.extend({"held_value": held_value, **row} for row in train)
            history_rows.extend({"held_value": held_value, **row} for row in hist)

    summary_rows = summarize_effects(effect_rows)
    seconds = time.time() - started

    cko.write_csv(out / "counterfactual_group_effects.csv", effect_rows)
    cko.write_csv(out / "counterfactual_group_summary.csv", summary_rows)
    cko.write_csv(out / "held_ood_hard_group_affinity.csv", affinity_rows)
    cko.write_csv(out / "feature_group_registry.csv", group_rows)
    cko.write_csv(out / "selected_leave_groups.csv", selected_rows)
    cko.write_csv(out / "train_threshold_and_centroid_audit.csv", train_rows)
    cko.write_csv(out / "train_history_and_env_audit.csv", history_rows)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_md(out / "codex_readout.md", build_readout(summary_rows, affinity_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "scope": "frontend entanglement audit via legal counterfactual feature masking",
            "role_cap": args.role_cap,
            "source_cap": args.source_cap,
            "train_cap": args.train_cap,
            "eval_cap": args.eval_cap,
            "candidates": [asdict(candidate) for candidate in candidates],
            "held_values": held_values,
            "selected_leave_groups": selected_rows,
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "mask_mean_and_centroid_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "leave_family_exclusion": "held device_family excluded from fit, mask means, centroids, and thresholds",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "interpretation": {
                "counterfactual_masking": "replace one feature group by legal-fit mean before prediction",
                "held_ood_hard_drop": "false hard alarm reduction when a group is removed",
                "attack_hard_drop": "attack detection damage when a group is removed",
                "affinity": "group-only standardized distance from baseline hard held-OOD rows to legal fit class centroids",
            },
            "input_audit": input_audit,
            "role_cap_audit": role_cap_rows,
            "outputs": [
                "counterfactual_group_effects.csv",
                "counterfactual_group_summary.csv",
                "held_ood_hard_group_affinity.csv",
                "feature_group_registry.csv",
                "selected_leave_groups.csv",
                "train_threshold_and_centroid_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=1536)
    parser.add_argument("--source-cap", type=int, default=48)
    parser.add_argument("--train-cap", type=int, default=768)
    parser.add_argument("--eval-cap", type=int, default=1536)
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES)
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
