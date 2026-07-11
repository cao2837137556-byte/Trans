"""issue27cku: open-world neural novelty gate smoke v1.

This is the next local smoke after issue27cks/issue27ckt.

Question
--------
Can the strongest neural line stop treating an uncovered OOD family as a hard
attack without simply dumping everything into review?

The experiment keeps the same strict data boundary:

* fit:
    support_train fit, id_calib fit, ood_val fit, ood_stress fit
* threshold/envelope calibration:
    id_calib/ood_val/ood_stress select for attack score safety,
    support_val select for attack-envelope preservation
* report-only:
    same-file query, future query, sealed final OOD, sealed final attack

For leave-family stress, the held device_family is removed from both fit and
threshold/envelope calibration before evaluating that family.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
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


ISSUE = "issue27cku_open_world_neural_novelty_gate_v1_2026-07-02"
OUT = cko.ROOT / "runs" / ISSUE

DEFAULT_CANDIDATE_NAMES = {
    "N1_raw_flow_mlp_selective",
    "N3_raw_flow_aug_adv_rex_selective",
}
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"

CKU_EXTRA_CANDIDATES = [
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
        description=(
            "CKU-only stronger invariant neural head: higher domain adversarial, "
            "REx, worst-group penalty, dropout, and weight decay."
        ),
    ),
]


def all_candidates() -> list[cks.NeuralCandidate]:
    return [*cks.NEURAL_CANDIDATES, *CKU_EXTRA_CANDIDATES]


@dataclass(frozen=True)
class NoveltyPolicy:
    name: str
    support_outside_budget: float
    mode: str
    description: str


NOVELTY_POLICIES = [
    NoveltyPolicy(
        name="B0_p0_no_novelty",
        support_outside_budget=0.0,
        mode="baseline",
        description="CKS P0 decision: hard attack when attack score exceeds benign-safe threshold and attack margin is positive.",
    ),
    NoveltyPolicy(
        name="U1_attack_envelope_review_1pp",
        support_outside_budget=0.01,
        mode="review_outside_attack",
        description="Hard attack additionally requires being inside the support-calibrated attack embedding envelope; outside goes to review.",
    ),
    NoveltyPolicy(
        name="U2_attack_envelope_suppress_known_ood_1pp",
        support_outside_budget=0.01,
        mode="suppress_known_ood_else_review",
        description="Outside attack envelope is suppressed if nearest known envelope is non-attack, otherwise reviewed.",
    ),
    NoveltyPolicy(
        name="U3_nearest_attack_gate_1pp",
        support_outside_budget=0.01,
        mode="nearest_attack_gate",
        description="Hard attack requires inside attack envelope and nearest embedding envelope is attack; known non-attack nearest envelope suppresses.",
    ),
]


@dataclass
class NoveltyEnvelope:
    candidate: str
    labels: np.ndarray
    centers: np.ndarray
    scales: np.ndarray
    input_centers: np.ndarray
    input_scales: np.ndarray
    known_dist_threshold: float
    input_known_dist_threshold: float
    support_attack_dist: np.ndarray
    support_input_attack_dist: np.ndarray
    support_entropy: np.ndarray
    audit_rows: list[dict[str, Any]]

    def attack_threshold(self, support_outside_budget: float) -> float:
        if len(self.support_attack_dist) == 0:
            return float("inf")
        if support_outside_budget <= 0.0:
            return float("inf")
        q = min(1.0, max(0.0, 1.0 - float(support_outside_budget)))
        return float(np.quantile(self.support_attack_dist, q))

    def entropy_threshold(self, support_outside_budget: float) -> float:
        if len(self.support_entropy) == 0:
            return float("inf")
        q = min(1.0, max(0.0, 1.0 - float(support_outside_budget)))
        return float(np.quantile(self.support_entropy, q))

    def input_attack_threshold(self, support_outside_budget: float) -> float:
        if len(self.support_input_attack_dist) == 0:
            return float("inf")
        if support_outside_budget <= 0.0:
            return float("inf")
        q = min(1.0, max(0.0, 1.0 - float(support_outside_budget)))
        return float(np.quantile(self.support_input_attack_dist, q))


def label_name(label: int) -> str:
    return str(ckq.CLASS_NAMES.get(int(label), f"class_{label}"))


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def role_indices(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    return cks.role_indices_filtered(frame_by_role, role, phase, cap, include=include, exclude=exclude)


def embeddings(fitted: cks.FittedNeural, x: np.ndarray) -> np.ndarray:
    cks.ensure_torch()
    fitted.model.eval()
    xt = cks.torch.from_numpy(fitted.transform(x).astype(np.float32))
    with cks.torch.no_grad():
        z = fitted.model.encoder(xt).cpu().numpy()
    return np.asarray(z, dtype=np.float32)


def role_embeddings(
    fitted: cks.FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    role: str,
    idx: np.ndarray,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    z, _xz, score = role_representations(fitted, builder, role, idx)
    return z, score


def role_representations(
    fitted: cks.FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    role: str,
    idx: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    x = cks.feature_matrix(builder, fitted.candidate.feature_kind, role, idx)
    proba = fitted.predict_proba(x)
    score = cks.scores_from_proba(proba)
    z = embeddings(fitted, x)
    xz = fitted.transform(x).astype(np.float32)
    return z, xz, score


def collect_fit_embedding_set(
    fitted: cks.FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    specs = [
        ("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP),
        ("id_calib", "fit", ckh.CLASS_ID, train_cap),
        ("ood_val", "fit", ckh.CLASS_OOD, train_cap),
        ("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap),
    ]
    zs: list[np.ndarray] = []
    xzs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []
    for role, phase, label, cap in specs:
        idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
        z, xz, _score = role_representations(fitted, builder, role, idx)
        zs.append(z)
        xzs.append(xz)
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append(
            {
                "candidate": fitted.candidate.name,
                "role": role,
                "phase": phase,
                "label": label,
                "label_name": label_name(label),
                "rows": len(idx),
                "used_for": "embedding_envelope_fit",
                "exclude_field": exclude[0] if exclude else "",
                "exclude_value": exclude[1] if exclude else "",
            }
        )
    return np.vstack(zs).astype(np.float32), np.vstack(xzs).astype(np.float32), np.concatenate(ys).astype(np.int64), audit


def distance_matrix(z: np.ndarray, centers: np.ndarray, scales: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=np.float32)
    if len(z) == 0:
        return np.zeros((0, len(centers)), dtype=np.float32)
    parts = []
    for center, scale in zip(centers, scales):
        scaled = (z - center.reshape(1, -1)) / scale.reshape(1, -1)
        parts.append(np.sqrt(np.mean(np.square(scaled), axis=1)))
    return np.vstack(parts).T.astype(np.float32)


def build_envelope(
    fitted: cks.FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    exclude: tuple[str, str] | None = None,
) -> NoveltyEnvelope:
    z_fit, xz_fit, y_fit, audit_rows = collect_fit_embedding_set(fitted, builder, frame_by_role, train_cap, exclude=exclude)
    labels = np.asarray(ckq.CLASS_LABELS, dtype=np.int64)
    global_center = np.mean(z_fit, axis=0)
    global_scale = np.std(z_fit, axis=0)
    global_scale[global_scale < 1e-3] = 1.0
    input_global_center = np.mean(xz_fit, axis=0)
    input_global_scale = np.std(xz_fit, axis=0)
    input_global_scale[input_global_scale < 1e-3] = 1.0

    centers = []
    scales = []
    input_centers = []
    input_scales = []
    class_threshold_parts = []
    input_class_threshold_parts = []
    for label in labels:
        mask = y_fit == int(label)
        if int(mask.sum()) == 0:
            center = global_center
            scale = global_scale
            input_center = input_global_center
            input_scale = input_global_scale
        else:
            center = np.mean(z_fit[mask], axis=0)
            scale = np.std(z_fit[mask], axis=0)
            scale[scale < 1e-3] = float(np.median(global_scale[global_scale >= 1e-3])) if np.any(global_scale >= 1e-3) else 1.0
            input_center = np.mean(xz_fit[mask], axis=0)
            input_scale = np.std(xz_fit[mask], axis=0)
            input_scale[input_scale < 1e-3] = (
                float(np.median(input_global_scale[input_global_scale >= 1e-3])) if np.any(input_global_scale >= 1e-3) else 1.0
            )
        centers.append(center.astype(np.float32))
        scales.append(scale.astype(np.float32))
        input_centers.append(input_center.astype(np.float32))
        input_scales.append(input_scale.astype(np.float32))

    centers_arr = np.vstack(centers).astype(np.float32)
    scales_arr = np.vstack(scales).astype(np.float32)
    input_centers_arr = np.vstack(input_centers).astype(np.float32)
    input_scales_arr = np.vstack(input_scales).astype(np.float32)
    fit_dist = distance_matrix(z_fit, centers_arr, scales_arr)
    input_fit_dist = distance_matrix(xz_fit, input_centers_arr, input_scales_arr)
    for col, label in enumerate(labels):
        own = fit_dist[y_fit == int(label), col]
        input_own = input_fit_dist[y_fit == int(label), col]
        if len(own):
            class_threshold_parts.append(own)
            input_class_threshold_parts.append(input_own)
            audit_rows.append(
                {
                    "candidate": fitted.candidate.name,
                    "role": "fit_envelope",
                    "phase": "fit",
                    "label": int(label),
                    "label_name": label_name(int(label)),
                    "rows": int(len(own)),
                    "dist_mean": float(np.mean(own)),
                    "dist_q95": float(np.quantile(own, 0.95)),
                    "dist_q99": float(np.quantile(own, 0.99)),
                    "input_dist_mean": float(np.mean(input_own)),
                    "input_dist_q95": float(np.quantile(input_own, 0.95)),
                    "input_dist_q99": float(np.quantile(input_own, 0.99)),
                    "used_for": "known_envelope_threshold_fit_only",
                    "exclude_field": exclude[0] if exclude else "",
                    "exclude_value": exclude[1] if exclude else "",
                }
            )
    all_own = np.concatenate(class_threshold_parts) if class_threshold_parts else np.asarray([], dtype=np.float32)
    input_all_own = np.concatenate(input_class_threshold_parts) if input_class_threshold_parts else np.asarray([], dtype=np.float32)
    known_dist_threshold = float(np.quantile(all_own, 0.99)) if len(all_own) else float("inf")
    input_known_dist_threshold = float(np.quantile(input_all_own, 0.99)) if len(input_all_own) else float("inf")

    support_idx = role_indices(frame_by_role, "support_val", "select", eval_cap, exclude=exclude)
    if len(support_idx):
        z_support, xz_support, support_score = role_representations(fitted, builder, "support_val", support_idx)
    else:
        train_idx = role_indices(frame_by_role, "support_train", "fit", cko.FULL_CAP, exclude=exclude)
        z_support, xz_support, support_score = role_representations(fitted, builder, "support_train", train_idx)
    support_dist = distance_matrix(z_support, centers_arr, scales_arr)
    support_input_dist = distance_matrix(xz_support, input_centers_arr, input_scales_arr)
    attack_col = int(np.flatnonzero(labels == ckh.CLASS_ATTACK)[0])
    support_attack_dist = support_dist[:, attack_col] if len(support_dist) else np.asarray([], dtype=np.float32)
    support_input_attack_dist = support_input_dist[:, attack_col] if len(support_input_dist) else np.asarray([], dtype=np.float32)
    support_entropy = support_score["entropy_score"] if len(support_dist) else np.asarray([], dtype=np.float32)
    audit_rows.append(
        {
            "candidate": fitted.candidate.name,
            "role": "support_val",
            "phase": "select",
            "label": ckh.CLASS_ATTACK,
            "label_name": label_name(ckh.CLASS_ATTACK),
            "rows": int(len(support_attack_dist)),
            "dist_mean": float(np.mean(support_attack_dist)) if len(support_attack_dist) else float("nan"),
            "dist_q98": float(np.quantile(support_attack_dist, 0.98)) if len(support_attack_dist) else float("nan"),
            "dist_q99": float(np.quantile(support_attack_dist, 0.99)) if len(support_attack_dist) else float("nan"),
            "input_dist_mean": float(np.mean(support_input_attack_dist)) if len(support_input_attack_dist) else float("nan"),
            "input_dist_q98": float(np.quantile(support_input_attack_dist, 0.98)) if len(support_input_attack_dist) else float("nan"),
            "input_dist_q99": float(np.quantile(support_input_attack_dist, 0.99)) if len(support_input_attack_dist) else float("nan"),
            "entropy_q99": float(np.quantile(support_entropy, 0.99)) if len(support_entropy) else float("nan"),
            "used_for": "support_attack_envelope_threshold_select_only",
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )
    return NoveltyEnvelope(
        candidate=fitted.candidate.name,
        labels=labels,
        centers=centers_arr,
        scales=scales_arr,
        input_centers=input_centers_arr,
        input_scales=input_scales_arr,
        known_dist_threshold=known_dist_threshold,
        input_known_dist_threshold=input_known_dist_threshold,
        support_attack_dist=np.asarray(support_attack_dist, dtype=np.float32),
        support_input_attack_dist=np.asarray(support_input_attack_dist, dtype=np.float32),
        support_entropy=np.asarray(support_entropy, dtype=np.float32),
        audit_rows=audit_rows,
    )


def novelty_scores(
    fitted: cks.FittedNeural,
    envelope: NoveltyEnvelope,
    builder: ckq.FlowTemporalBuilder,
    role: str,
    idx: np.ndarray,
) -> dict[str, np.ndarray]:
    z, xz, score = role_representations(fitted, builder, role, idx)
    dists = distance_matrix(z, envelope.centers, envelope.scales)
    input_dists = distance_matrix(xz, envelope.input_centers, envelope.input_scales)
    if len(dists):
        nearest_pos = np.argmin(dists, axis=1)
        nearest_label = envelope.labels[nearest_pos]
        nearest_dist = dists[np.arange(len(dists)), nearest_pos]
        input_nearest_pos = np.argmin(input_dists, axis=1)
        input_nearest_label = envelope.labels[input_nearest_pos]
        input_nearest_dist = input_dists[np.arange(len(input_dists)), input_nearest_pos]
    else:
        nearest_label = np.asarray([], dtype=np.int64)
        nearest_dist = np.asarray([], dtype=np.float32)
        input_nearest_label = np.asarray([], dtype=np.int64)
        input_nearest_dist = np.asarray([], dtype=np.float32)
    attack_pos = int(np.flatnonzero(envelope.labels == ckh.CLASS_ATTACK)[0])
    score["attack_dist"] = dists[:, attack_pos] if len(dists) else np.asarray([], dtype=np.float32)
    score["input_attack_dist"] = input_dists[:, attack_pos] if len(input_dists) else np.asarray([], dtype=np.float32)
    score["nearest_known_dist"] = nearest_dist
    score["input_nearest_known_dist"] = input_nearest_dist
    score["nearest_known_label"] = nearest_label.astype(np.int64)
    score["input_nearest_known_label"] = input_nearest_label.astype(np.int64)
    score["nearest_is_attack"] = nearest_label.astype(np.int64) == ckh.CLASS_ATTACK
    score["input_nearest_is_attack"] = input_nearest_label.astype(np.int64) == ckh.CLASS_ATTACK
    return score


def decide(
    score: dict[str, np.ndarray],
    policy: NoveltyPolicy,
    threshold_row: dict[str, Any],
    attack_dist_threshold: float,
    known_dist_threshold: float,
) -> dict[str, np.ndarray]:
    attack_score = score["attack_score"]
    raw_alarm = attack_score > float(threshold_row["attack_threshold"])
    margin_review = raw_alarm & (score["margin_score"] <= float(threshold_row["margin_review_threshold"]))
    input_attack_dist_threshold = float(threshold_row["input_attack_dist_threshold"])
    input_known_dist_threshold = float(threshold_row["input_known_dist_threshold"])
    outside_embedding_attack = raw_alarm & (score["attack_dist"] > attack_dist_threshold)
    outside_input_attack = raw_alarm & (score["input_attack_dist"] > input_attack_dist_threshold)
    outside_attack = outside_embedding_attack | outside_input_attack
    unknown_embedding = score["nearest_known_dist"] > known_dist_threshold
    unknown_input = score["input_nearest_known_dist"] > input_known_dist_threshold
    unknown_global = raw_alarm & unknown_embedding & unknown_input
    nearest_nonattack = raw_alarm & ((~score["nearest_is_attack"]) | (~score["input_nearest_is_attack"]))

    review = margin_review.copy()
    suppress = np.zeros(len(raw_alarm), dtype=bool)

    if policy.mode == "baseline":
        pass
    elif policy.mode == "review_outside_attack":
        review = review | outside_attack
    elif policy.mode == "suppress_known_ood_else_review":
        suppress = outside_attack & nearest_nonattack & (~unknown_global) & (~margin_review)
        review = review | (outside_attack & (~suppress))
    elif policy.mode == "nearest_attack_gate":
        known_ood_like = nearest_nonattack & (~unknown_global)
        suppress = known_ood_like & (~margin_review)
        review = review | (outside_attack & (~suppress)) | (raw_alarm & (~score["nearest_is_attack"]) & unknown_global)
    else:
        raise ValueError(f"unknown novelty policy mode: {policy.mode}")

    hard = raw_alarm & (~review) & (~suppress)
    return {
        "raw_alarm": raw_alarm,
        "novelty_review": review,
        "novelty_suppress": suppress,
        "hard_alarm": hard,
        "outside_attack_envelope": outside_attack,
        "outside_embedding_attack_envelope": outside_embedding_attack,
        "outside_input_attack_envelope": outside_input_attack,
        "unknown_global_envelope": unknown_global,
        "nearest_nonattack_envelope": nearest_nonattack,
    }


def threshold_rows_for_policies(
    fitted: cks.FittedNeural,
    envelope: NoveltyEnvelope,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    exclude: tuple[str, str] | None = None,
) -> list[dict[str, Any]]:
    attack_thr = cks.attack_threshold(fitted, builder, frame_by_role, eval_cap, exclude=exclude)
    base_thr = cks.review_margin_threshold(
        fitted,
        builder,
        frame_by_role,
        attack_thr,
        eval_cap,
        cks.REVIEW_POLICIES[0],
        exclude=exclude,
    )
    rows = []
    for policy in NOVELTY_POLICIES:
        rows.append(
            {
                **base_thr,
                "policy": policy.name,
                "novelty_mode": policy.mode,
                "support_outside_budget": policy.support_outside_budget,
                "attack_dist_threshold": envelope.attack_threshold(policy.support_outside_budget),
                "input_attack_dist_threshold": envelope.input_attack_threshold(policy.support_outside_budget),
                "known_dist_threshold": envelope.known_dist_threshold,
                "input_known_dist_threshold": envelope.input_known_dist_threshold,
                "support_entropy_threshold": envelope.entropy_threshold(policy.support_outside_budget),
                "threshold_role": (
                    "attack score from id/ood select; margin P0 from support_val select; "
                    "attack envelope from support_val select; known envelope from legal fit roles"
                ),
                "exclude_field": exclude[0] if exclude else "",
                "exclude_value": exclude[1] if exclude else "",
                "policy_description": policy.description,
            }
        )
    return rows


def eval_open_role(
    fitted: cks.FittedNeural,
    envelope: NoveltyEnvelope,
    policy: NoveltyPolicy,
    threshold_row: dict[str, Any],
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    role_kind: str,
    eval_cap: int,
    split: str,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, eval_cap, include=include, exclude=exclude)
    score = novelty_scores(fitted, envelope, builder, role, idx)
    decision = decide(
        score,
        policy,
        threshold_row,
        float(threshold_row["attack_dist_threshold"]),
        float(threshold_row["known_dist_threshold"]),
    )

    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    for key, value in score.items():
        part[key] = value
    for key, value in decision.items():
        part[key] = value
    part["nearest_known_label_name"] = [label_name(int(v)) for v in score["nearest_known_label"]]

    row = {
        "feature_set": f"{fitted.candidate.name}__{policy.name}",
        "candidate": fitted.candidate.name,
        "policy": policy.name,
        "novelty_mode": policy.mode,
        "split": split,
        "held_field": include[0] if include else "",
        "held_value": include[1] if include else "",
        "feature_kind": fitted.candidate.feature_kind,
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(part),
        "attack_threshold": threshold_row["attack_threshold"],
        "margin_review_threshold": threshold_row["margin_review_threshold"],
        "attack_dist_threshold": threshold_row["attack_dist_threshold"],
        "input_attack_dist_threshold": threshold_row["input_attack_dist_threshold"],
        "known_dist_threshold": threshold_row["known_dist_threshold"],
        "input_known_dist_threshold": threshold_row["input_known_dist_threshold"],
        "raw_alarm_rate": ckg.rate(decision["raw_alarm"]),
        "review_rate": ckg.rate(decision["novelty_review"]),
        "suppress_rate": ckg.rate(decision["novelty_suppress"]),
        "hard_alarm_rate": ckg.rate(decision["hard_alarm"]),
        "outside_attack_envelope_rate": ckg.rate(decision["outside_attack_envelope"]),
        "outside_embedding_attack_envelope_rate": ckg.rate(decision["outside_embedding_attack_envelope"]),
        "outside_input_attack_envelope_rate": ckg.rate(decision["outside_input_attack_envelope"]),
        "unknown_global_envelope_rate": ckg.rate(decision["unknown_global_envelope"]),
        "nearest_nonattack_envelope_rate": ckg.rate(decision["nearest_nonattack_envelope"]),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
        "margin_score_mean": float(np.mean(score["margin_score"])) if len(part) else float("nan"),
        "entropy_score_mean": float(np.mean(score["entropy_score"])) if len(part) else float("nan"),
        "attack_dist_mean": float(np.mean(score["attack_dist"])) if len(part) else float("nan"),
        "input_attack_dist_mean": float(np.mean(score["input_attack_dist"])) if len(part) else float("nan"),
        "nearest_known_dist_mean": float(np.mean(score["nearest_known_dist"])) if len(part) else float("nan"),
        "input_nearest_known_dist_mean": float(np.mean(score["input_nearest_known_dist"])) if len(part) else float("nan"),
    }
    return row, part


def rows_for_summary(rows: list[dict[str, Any]], split: str, role: str, candidate: str, policy: str, held_value: str = "") -> dict[str, Any]:
    for row in rows:
        if (
            row.get("split") == split
            and row.get("role") == role
            and row.get("candidate") == candidate
            and row.get("policy") == policy
            and str(row.get("held_value", "")) == held_value
        ):
            return row
    return {}


def build_main_matrix(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(r["candidate"], r["policy"]) for r in role_rows if r.get("split") == "main"})
    out = []
    for candidate, policy in keys:
        def pick(role: str, metric: str) -> float:
            row = rows_for_summary(role_rows, "main", role, candidate, policy)
            return float(row.get(metric, float("nan"))) if row else float("nan")

        out.append(
            {
                "candidate": candidate,
                "policy": policy,
                "future_hard": pick("future_query", "hard_alarm_rate"),
                "future_review": pick("future_query", "review_rate"),
                "future_suppress": pick("future_query", "suppress_rate"),
                "sealed_attack_hard": pick("sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_review": pick("sealed_final_attack", "review_rate"),
                "sealed_attack_suppress": pick("sealed_final_attack", "suppress_rate"),
                "sealed_ood_hard": pick("sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_review": pick("sealed_final_ood", "review_rate"),
                "sealed_ood_suppress": pick("sealed_final_ood", "suppress_rate"),
                "ood_stress_hard": pick("ood_stress", "hard_alarm_rate"),
                "ood_stress_review": pick("ood_stress", "review_rate"),
                "ood_stress_suppress": pick("ood_stress", "suppress_rate"),
                "support_hard": pick("support_val", "hard_alarm_rate"),
                "support_review": pick("support_val", "review_rate"),
                "support_suppress": pick("support_val", "suppress_rate"),
            }
        )
    return out


def build_leave_matrix(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted(
        {
            (r["candidate"], r["policy"], str(r.get("held_value", "")), r["role"])
            for r in role_rows
            if r.get("split") == "leave_device_family" and r["role"] in {"ood_val", "ood_stress", "future_query", "sealed_final_ood", "sealed_final_attack"}
        }
    )
    return [
        {
            "candidate": candidate,
            "policy": policy,
            "held_value": held_value,
            "role": role,
            "rows": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("rows", 0),
            "raw_alarm_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("raw_alarm_rate", float("nan")),
            "hard_alarm_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("hard_alarm_rate", float("nan")),
            "review_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("review_rate", float("nan")),
            "suppress_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("suppress_rate", float("nan")),
            "outside_attack_envelope_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("outside_attack_envelope_rate", float("nan")),
            "outside_embedding_attack_envelope_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("outside_embedding_attack_envelope_rate", float("nan")),
            "outside_input_attack_envelope_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("outside_input_attack_envelope_rate", float("nan")),
            "nearest_nonattack_envelope_rate": rows_for_summary(role_rows, "leave_device_family", role, candidate, policy, held_value).get("nearest_nonattack_envelope_rate", float("nan")),
        }
        for candidate, policy, held_value, role in keys
    ]


def build_readout(main_matrix: list[dict[str, Any]], leave_matrix: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27cku open-world neural novelty gate v1",
        "",
        "## Scope",
        "",
        "Local medium smoke: CKS neural head plus embedding-envelope open-world gate.",
        "This is a dataset-internal generalization repair test, not cross-dataset proof.",
        "",
        "## Main roles",
        "",
        "| candidate | policy | future h/r/s | sealed attack h/r/s | sealed OOD h/r/s | OOD-stress h/r/s | support h/r/s |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in main_matrix:
        lines.append(
            f"| {row['candidate']} | {row['policy']} | "
            f"{cko.fmt(row['future_hard'])}/{cko.fmt(row['future_review'])}/{cko.fmt(row['future_suppress'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])}/{cko.fmt(row['sealed_attack_suppress'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])}/{cko.fmt(row['sealed_ood_suppress'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])}/{cko.fmt(row['ood_stress_suppress'])} | "
            f"{cko.fmt(row['support_hard'])}/{cko.fmt(row['support_review'])}/{cko.fmt(row['support_suppress'])} |"
        )

    lines.extend(
        [
            "",
            "## Leave-device-family stress",
            "",
            "| candidate | policy | held family | role | rows | raw | hard | review | suppress | outside any/embed/input | nearest nonattack |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in leave_matrix:
        if int(row["rows"]) == 0:
            continue
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['raw_alarm_rate'])} | {cko.fmt(row['hard_alarm_rate'])} | "
            f"{cko.fmt(row['review_rate'])} | {cko.fmt(row['suppress_rate'])} | "
            f"{cko.fmt(row['outside_attack_envelope_rate'])}/{cko.fmt(row['outside_embedding_attack_envelope_rate'])}/{cko.fmt(row['outside_input_attack_envelope_rate'])} | "
            f"{cko.fmt(row['nearest_nonattack_envelope_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## Threshold/envelope audit",
            "",
            "| candidate | split | held | policy | attack score thr | latent attack dist thr | input attack dist thr | latent known dist thr | input known dist thr |",
            "|---|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in threshold_rows:
        lines.append(
            f"| {row['candidate']} | {row.get('split', 'main')} | {row.get('held_value', '')} | {row['policy']} | "
            f"{cko.fmt(row['attack_threshold'])} | {cko.fmt(row['attack_dist_threshold'])} | "
            f"{cko.fmt(row['input_attack_dist_threshold'])} | {cko.fmt(row['known_dist_threshold'])} | "
            f"{cko.fmt(row['input_known_dist_threshold'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit uses only support_train/id_calib/ood_val/ood_stress fit phases.",
            "- Attack score threshold uses only id_calib/ood_val/ood_stress select phases.",
            "- Attack envelope threshold uses only support_val select.",
            "- Leave-family stress excludes the held device_family from fit and threshold/envelope calibration.",
            "- Query/future/sealed rows are report-only.",
            "- h/r/s = hard/review/suppress.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def fit_candidate_bundle(
    candidate: cks.NeuralCandidate,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    exclude: tuple[str, str] | None,
) -> tuple[cks.FittedNeural, NoveltyEnvelope, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fitted, train_audit, history_rows = cks.fit_neural_candidate(candidate, builder, frame_by_role, train_cap, exclude=exclude)
    envelope = build_envelope(fitted, builder, frame_by_role, train_cap, eval_cap, exclude=exclude)
    threshold_rows = threshold_rows_for_policies(fitted, envelope, builder, frame_by_role, eval_cap, exclude=exclude)
    return fitted, envelope, train_audit, history_rows, threshold_rows


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
        cap_rule="open-world neural novelty gate capped local smoke",
    )
    ckt.add_family_columns(frame_by_role)

    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    candidate_names = set(args.candidates.split(",")) if args.candidates else DEFAULT_CANDIDATE_NAMES
    candidates = [candidate for candidate in all_candidates() if candidate.name in candidate_names]
    held_values = [item.strip() for item in str(args.held_values).split(",") if item.strip()]

    role_rows: list[dict[str, Any]] = []
    part_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    envelope_rows: list[dict[str, Any]] = []
    selected_leave_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        fitted, envelope, train_audit, hist, thrs = fit_candidate_bundle(
            candidate,
            builder,
            frame_by_role,
            int(args.train_cap),
            int(args.eval_cap),
            exclude=None,
        )
        train_rows.extend({"candidate": candidate.name, "split": "main", **row} for row in train_audit)
        history_rows.extend({"candidate": candidate.name, "split": "main", **row} for row in hist)
        envelope_rows.extend({"split": "main", **row} for row in envelope.audit_rows)
        for threshold_row in thrs:
            threshold_rows.append({"split": "main", **threshold_row})
            policy = next(policy for policy in NOVELTY_POLICIES if policy.name == threshold_row["policy"])
            for role, phase, kind in cko.ROLE_EVAL:
                row, part = eval_open_role(
                    fitted,
                    envelope,
                    policy,
                    threshold_row,
                    builder,
                    frame_by_role,
                    role,
                    phase,
                    kind,
                    int(args.eval_cap),
                    split="main",
                )
                role_rows.append(row)
                if args.save_parts:
                    part["candidate"] = candidate.name
                    part["policy"] = policy.name
                    part["split"] = "main"
                    part["role"] = role
                    part_rows.extend(part.head(int(args.part_head)).to_dict("records"))

    for held_value in held_values:
        counts = {
            "ood_val": ckt.rows_for(frame_by_role, "ood_val", "select", "device_family", held_value, int(args.eval_cap)),
            "ood_stress": ckt.rows_for(frame_by_role, "ood_stress", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_ood": ckt.rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", held_value, int(args.eval_cap)),
            "future_query": ckt.rows_for(frame_by_role, "future_query", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_attack": ckt.rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", held_value, int(args.eval_cap)),
        }
        selected_leave_rows.append({"held_field": "device_family", "held_value": held_value, "total_eval_rows": sum(counts.values()), **counts})
        exclude = ("device_family", held_value)
        include = ("device_family", held_value)
        for candidate in candidates:
            fitted, envelope, train_audit, hist, thrs = fit_candidate_bundle(
                candidate,
                builder,
                frame_by_role,
                int(args.train_cap),
                int(args.eval_cap),
                exclude=exclude,
            )
            train_rows.extend({"candidate": candidate.name, "split": "leave_device_family", "held_value": held_value, **row} for row in train_audit)
            history_rows.extend({"candidate": candidate.name, "split": "leave_device_family", "held_value": held_value, **row} for row in hist)
            envelope_rows.extend({"split": "leave_device_family", "held_value": held_value, **row} for row in envelope.audit_rows)
            for threshold_row in thrs:
                threshold_rows.append({"split": "leave_device_family", "held_value": held_value, **threshold_row})
                policy = next(policy for policy in NOVELTY_POLICIES if policy.name == threshold_row["policy"])
                for role, phase, kind in cko.ROLE_EVAL:
                    row, part = eval_open_role(
                        fitted,
                        envelope,
                        policy,
                        threshold_row,
                        builder,
                        frame_by_role,
                        role,
                        phase,
                        kind,
                        int(args.eval_cap),
                        split="leave_device_family",
                        include=include,
                    )
                    role_rows.append(row)
                    if args.save_parts:
                        part["candidate"] = candidate.name
                        part["policy"] = policy.name
                        part["split"] = "leave_device_family"
                        part["held_value"] = held_value
                        part["role"] = role
                        part_rows.extend(part.head(int(args.part_head)).to_dict("records"))

    main_matrix = build_main_matrix(role_rows)
    leave_matrix = build_leave_matrix(role_rows)
    seconds = time.time() - started

    cko.write_csv(out / "main_summary_matrix.csv", main_matrix)
    cko.write_csv(out / "leave_device_family_summary_matrix.csv", leave_matrix)
    cko.write_csv(out / "role_metrics.csv", role_rows)
    cko.write_csv(out / "threshold_and_policy_audit.csv", threshold_rows)
    cko.write_csv(out / "embedding_envelope_audit.csv", envelope_rows)
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "train_history_and_env_audit.csv", history_rows)
    cko.write_csv(out / "selected_leave_groups.csv", selected_leave_rows)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    if args.save_parts:
        cko.write_csv(out / "sample_scored_rows.csv", part_rows)
    cko.write_md(out / "codex_readout.md", build_readout(main_matrix, leave_matrix, threshold_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "scope": "CKS neural head plus open-world embedding-envelope novelty gate",
            "role_cap": args.role_cap,
            "source_cap": args.source_cap,
            "train_cap": args.train_cap,
            "eval_cap": args.eval_cap,
            "candidates": [asdict(candidate) for candidate in candidates],
            "novelty_policies": [asdict(policy) for policy in NOVELTY_POLICIES],
            "held_values": held_values,
            "selected_leave_groups": selected_leave_rows,
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "attack_score_threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
                "attack_envelope_threshold_role": "support_val select",
                "known_envelope_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "leave_family_exclusion": "held device_family excluded from fit and threshold/envelope calibration",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "feature_contract": {
                "frontend": "issue27cks feature_matrix over raw115/ckq flow temporal/enhanced summaries",
                "embedding": "fitted neural encoder latent space after legal training only",
                "source_or_device_used_as_inference_feature": False,
                "device_family_used_only_for_leave_split": True,
            },
            "input_audit": input_audit,
            "role_cap_audit": role_cap_rows,
            "outputs": [
                "main_summary_matrix.csv",
                "leave_device_family_summary_matrix.csv",
                "role_metrics.csv",
                "threshold_and_policy_audit.csv",
                "embedding_envelope_audit.csv",
                "train_audit.csv",
                "train_history_and_env_audit.csv",
                "selected_leave_groups.csv",
                "flow_temporal_extraction_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=4096)
    parser.add_argument("--source-cap", type=int, default=64)
    parser.add_argument("--train-cap", type=int, default=2048)
    parser.add_argument("--eval-cap", type=int, default=4096)
    parser.add_argument("--candidates", default=",".join(sorted(DEFAULT_CANDIDATE_NAMES)))
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--save-parts", action="store_true", help="save small scored-row samples for debugging")
    parser.add_argument("--part-head", type=int, default=64)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
