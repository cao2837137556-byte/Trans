"""issue27cks: neural causal/selective head smoke v1.

Goal
----
This is a local medium-smoke route for the next real method line:

    stronger strictly-aligned frontend + neural selective head
    + source/device-style de-emphasis via domain adversarial/REx penalties.

It deliberately keeps the data boundary conservative:

* fit roles only:
    support_train fit, id_calib fit, ood_val fit, ood_stress fit
* threshold roles only:
    id_calib select, ood_val select, ood_stress select, support_val select
* same_file/future/sealed rows remain report-only.

The enhanced frontend is derived from the same ckq FlowTemporalBuilder matrices
used for raw115/flow-temporal alignment.  It never reorders rows independently:
for every role/index, raw115, flow-temporal, and enhanced summaries are built
from the same role frame positions.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception as exc:  # pragma: no cover - explicit runtime dependency check
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    TORCH_IMPORT_ERROR = repr(exc)
else:
    TORCH_IMPORT_ERROR = ""

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402


ISSUE = "issue27cks_neural_causal_selective_head_v1_2026-07-01"
OUT = cko.ROOT / "runs" / ISSUE

MEDIUM_ROLE_CAP = 4096
MEDIUM_SOURCE_CAP = 64
MEDIUM_TRAIN_CAP = 2048
MEDIUM_EVAL_CAP = 4096
MICRO_TRAIN_CAP = 384
MICRO_EVAL_CAP = 768
SEED = ckh.SEED


@dataclass(frozen=True)
class NeuralCandidate:
    name: str
    feature_kind: str
    hidden_dim: int
    epochs: int
    lr: float
    weight_decay: float
    dropout: float
    adv_lambda: float
    rex_lambda: float
    worst_group_lambda: float
    description: str


@dataclass(frozen=True)
class ReviewPolicy:
    name: str
    support_review_budget: float
    description: str


NEURAL_CANDIDATES = [
    NeuralCandidate(
        name="N0_raw115_mlp_selective",
        feature_kind="raw",
        hidden_dim=96,
        epochs=60,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="Raw115 only, small neural four-class head plus selective decision policy.",
    ),
    NeuralCandidate(
        name="N1_raw_flow_mlp_selective",
        feature_kind="raw_flow",
        hidden_dim=128,
        epochs=70,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="Raw115 + ckq flow-temporal features, direct neural head.",
    ),
    NeuralCandidate(
        name="N2_raw_flow_aug_mlp_selective",
        feature_kind="raw_flow_aug",
        hidden_dim=160,
        epochs=80,
        lr=8e-4,
        weight_decay=1e-4,
        dropout=0.12,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="Raw115 + flow-temporal + aligned mechanism summaries, direct neural head.",
    ),
    NeuralCandidate(
        name="N3_raw_flow_aug_adv_rex_selective",
        feature_kind="raw_flow_aug",
        hidden_dim=160,
        epochs=90,
        lr=8e-4,
        weight_decay=1.5e-4,
        dropout=0.15,
        adv_lambda=0.05,
        rex_lambda=0.15,
        worst_group_lambda=0.05,
        description=(
            "Raw115 + enhanced flow frontend with domain-adversarial and "
            "risk-variance penalties across source/device environments."
        ),
    ),
]


REVIEW_POLICIES = [
    ReviewPolicy(
        name="P0_conflict_only",
        support_review_budget=0.0,
        description="Review only when non-attack class probability exceeds attack probability.",
    ),
    ReviewPolicy(
        name="P1_support_margin_1pp",
        support_review_budget=0.01,
        description="Allow at most about 1pp low-margin support attack review, then apply to all roles.",
    ),
    ReviewPolicy(
        name="P2_support_margin_2pp",
        support_review_budget=0.02,
        description="Allow at most about 2pp low-margin support attack review, then apply to all roles.",
    ),
]


def ensure_torch() -> None:
    if torch is None:
        raise RuntimeError(f"PyTorch is required for issue27cks neural smoke; import error: {TORCH_IMPORT_ERROR}")


def set_seeds() -> None:
    np.random.seed(SEED)
    ensure_torch()
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, min(8, int(torch.get_num_threads()))))


def flow_col_indices(tokens: list[str]) -> list[int]:
    out: list[int] = []
    for i, name in enumerate(ckq.FLOW_TEMPORAL_FEATURES):
        if any(token in name for token in tokens):
            out.append(i)
    return out


FLOW_SUMMARY_GROUPS = {
    "current_protocol": flow_col_indices(["cur_is_", "cur_tcp_", "cur_syn_without_ack", "cur_ack_without_syn"]),
    "fanout": flow_col_indices(["unique_dst_frac", "unique_dport_frac", "unique_src_frac", "unique_sport_frac"]),
    "rates": flow_col_indices(["count_frac", "event_rate_log", "byte_rate_log", "short_long_ratio"]),
    "duration_gap_size": flow_col_indices(["duration_log", "current_gap_log", "len_mean_log", "len_std_log", "cur_log_frame_len"]),
    "reverse_balance": flow_col_indices(["reverse", "balance"]),
}


def get_flow_col(flow: np.ndarray, name: str) -> np.ndarray:
    try:
        idx = ckq.FLOW_TEMPORAL_FEATURES.index(name)
    except ValueError:
        return np.zeros(len(flow), dtype=np.float32)
    return flow[:, idx].astype(np.float32)


def enhanced_flow_summary(flow: np.ndarray) -> np.ndarray:
    """Aligned mechanism summaries derived from the already-aligned ckq flow matrix.

    The neural net still receives the full flow-temporal matrix.  These summaries
    add explicit mechanism channels: fanout pressure, rate/burst pressure,
    reverse-flow imbalance, and protocol-state contrasts.
    """

    flow = np.asarray(flow, dtype=np.float32)
    if len(flow) == 0:
        return np.zeros((0, enhanced_flow_summary_dim()), dtype=np.float32)

    blocks: list[np.ndarray] = []
    for _group_name, cols in FLOW_SUMMARY_GROUPS.items():
        if not cols:
            stats = np.zeros((len(flow), 4), dtype=np.float32)
        else:
            vals = np.nan_to_num(flow[:, cols], nan=0.0, posinf=0.0, neginf=0.0)
            stats = np.column_stack(
                [
                    np.mean(vals, axis=1),
                    np.max(vals, axis=1),
                    np.std(vals, axis=1),
                    np.linalg.norm(vals, axis=1) / math.sqrt(max(1, vals.shape[1])),
                ]
            ).astype(np.float32)
        blocks.append(stats)

    cur_tcp = get_flow_col(flow, "cur_is_tcp")
    cur_udp = get_flow_col(flow, "cur_is_udp")
    cur_syn = get_flow_col(flow, "cur_tcp_syn")
    cur_ack = get_flow_col(flow, "cur_tcp_ack")
    cur_rst = get_flow_col(flow, "cur_tcp_rst")
    src_count_ratio = get_flow_col(flow, "src_count_short_long_ratio_w8_128")
    src_dport_ratio = get_flow_col(flow, "src_dport_fanout_short_long_ratio_w8_128")
    dst_pressure_ratio = get_flow_col(flow, "dst_src_pressure_short_long_ratio_w8_128")
    pair_count_ratio = get_flow_col(flow, "pair_count_short_long_ratio_w8_128")
    flow5_count_ratio = get_flow_col(flow, "flow5_count_short_long_ratio_w8_128")
    protocol_contrasts = np.column_stack(
        [
            cur_tcp - cur_udp,
            cur_syn - cur_ack,
            cur_rst - cur_syn,
            src_count_ratio,
            src_dport_ratio,
            dst_pressure_ratio,
            pair_count_ratio,
            flow5_count_ratio,
            src_count_ratio * np.maximum(0.0, src_dport_ratio),
            np.maximum(src_dport_ratio, dst_pressure_ratio),
        ]
    ).astype(np.float32)
    blocks.append(protocol_contrasts)
    return np.nan_to_num(np.hstack(blocks).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def enhanced_flow_summary_dim() -> int:
    return len(FLOW_SUMMARY_GROUPS) * 4 + 10


def feature_matrix(builder: ckq.FlowTemporalBuilder, feature_kind: str, role: str, idx: np.ndarray) -> np.ndarray:
    raw = np.asarray(builder.matrix(ckq.RAW_BLOCK, role, idx), dtype=np.float32)
    if feature_kind == "raw":
        return raw
    flow = np.asarray(builder.matrix(ckq.FLOW_BLOCK, role, idx), dtype=np.float32)
    if feature_kind == "raw_flow":
        return np.hstack([raw, flow]).astype(np.float32)
    if feature_kind == "raw_flow_aug":
        return np.hstack([raw, flow, enhanced_flow_summary(flow)]).astype(np.float32)
    raise ValueError(f"unknown feature kind {feature_kind}")


def env_keys(frame_part: pd.DataFrame) -> list[str]:
    source = frame_part.get("source_group", pd.Series(["unknown"] * len(frame_part))).astype(str).fillna("unknown")
    device = frame_part.get("device", pd.Series(["unknown"] * len(frame_part))).astype(str).fillna("unknown")
    return [f"{s}|{d}" for s, d in zip(source, device)]


def role_indices_filtered(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    frame = frame_by_role[role]
    idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].astype(str).to_numpy() == phase)
    if include is not None and include[0] in frame:
        field, value = include
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() == str(value)]
    if exclude is not None and exclude[0] in frame:
        field, value = exclude
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() != str(value)]
    return cko.deterministic_cap(idx, cap)


def build_train_set(
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    feature_kind: str,
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], list[dict[str, Any]]]:
    chunks: list[dict[str, Any]] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = role_indices_filtered(frame_by_role, role, phase, cap, exclude=exclude)
        chunks.append({"role": role, "phase": phase, "label": label, "idx": idx})
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append(
            {
                "role": role,
                "phase": phase,
                "label": label,
                "label_name": ckq.CLASS_NAMES[label],
                "rows": len(idx),
                "exclude_field": exclude[0] if exclude else "",
                "exclude_value": exclude[1] if exclude else "",
            }
        )

    add("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    y = np.concatenate(ys)
    xs: list[np.ndarray] = []
    envs: list[str] = []
    for chunk in chunks:
        role = str(chunk["role"])
        idx = np.asarray(chunk["idx"], dtype=np.int64)
        xs.append(feature_matrix(builder, feature_kind, role, idx))
        envs.extend(env_keys(frame_by_role[role].iloc[idx].reset_index(drop=True)))
    x = np.vstack(xs).astype(np.float32)
    for row in audit:
        row["feature_kind"] = feature_kind
        row["candidate_scope"] = "neural_fit_set"
    return x, np.asarray(y, dtype=np.int64), envs, audit


def env_to_ids(envs: list[str], max_envs: int = 32) -> tuple[np.ndarray, dict[str, int]]:
    counts = pd.Series(envs, dtype="object").value_counts()
    keep = list(counts.index[:max_envs])
    mapping = {key: i for i, key in enumerate(keep)}
    other_id = len(mapping)
    mapping["__OTHER__"] = other_id
    ids = np.asarray([mapping.get(key, other_id) for key in envs], dtype=np.int64)
    return ids, mapping


class GradientReverse(torch.autograd.Function):  # type: ignore[misc]
    @staticmethod
    def forward(ctx: Any, x: torch.Tensor, lambd: float) -> torch.Tensor:
        ctx.lambd = lambd
        return x.view_as(x)

    @staticmethod
    def backward(ctx: Any, grad_output: torch.Tensor) -> tuple[torch.Tensor, None]:
        return -float(ctx.lambd) * grad_output, None


class NeuralCausalHead(nn.Module):  # type: ignore[misc]
    def __init__(self, in_dim: int, hidden_dim: int, n_env: int, dropout: float):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ReLU(),
        )
        latent = hidden_dim // 2
        self.classifier = nn.Linear(latent, len(ckq.CLASS_LABELS))
        self.domain = nn.Linear(latent, max(1, n_env))

    def forward(self, x: torch.Tensor, grl_lambda: float = 0.0) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.encoder(x)
        logits = self.classifier(z)
        z_rev = GradientReverse.apply(z, grl_lambda)
        domain_logits = self.domain(z_rev)
        return logits, domain_logits


@dataclass
class FittedNeural:
    candidate: NeuralCandidate
    mean: np.ndarray
    std: np.ndarray
    model: Any
    env_mapping: dict[str, int]
    train_history: list[dict[str, Any]]

    def transform(self, x: np.ndarray) -> np.ndarray:
        return np.nan_to_num((np.asarray(x, dtype=np.float32) - self.mean) / self.std, nan=0.0, posinf=0.0, neginf=0.0)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        ensure_torch()
        self.model.eval()
        xt = torch.from_numpy(self.transform(x).astype(np.float32))
        with torch.no_grad():
            logits, _ = self.model(xt, 0.0)
            proba = torch.softmax(logits, dim=1).cpu().numpy()
        return np.asarray(proba, dtype=np.float64)


def class_weights(y: np.ndarray) -> torch.Tensor:
    counts = np.bincount(y, minlength=len(ckq.CLASS_LABELS)).astype(np.float64)
    weights = np.zeros(len(ckq.CLASS_LABELS), dtype=np.float32)
    total = float(np.sum(counts))
    for label in range(len(weights)):
        weights[label] = float(total / max(1.0, counts[label]))
    weights /= max(1e-12, float(np.mean(weights[weights > 0])))
    return torch.from_numpy(weights.astype(np.float32))


def fit_neural_candidate(
    candidate: NeuralCandidate,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[FittedNeural, list[dict[str, Any]], list[dict[str, Any]]]:
    ensure_torch()
    x, y, envs, audit = build_train_set(builder, frame_by_role, candidate.feature_kind, train_cap, exclude=exclude)
    env_id, env_mapping = env_to_ids(envs)
    mean = np.mean(x, axis=0).astype(np.float32)
    std = np.std(x, axis=0).astype(np.float32)
    std[std < 1e-6] = 1.0
    xz = np.nan_to_num((x - mean) / std, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    xt = torch.from_numpy(xz)
    yt = torch.from_numpy(y.astype(np.int64))
    et = torch.from_numpy(env_id.astype(np.int64))
    weights = class_weights(y)
    model = NeuralCausalHead(x.shape[1], candidate.hidden_dim, len(env_mapping), candidate.dropout)
    opt = torch.optim.AdamW(model.parameters(), lr=candidate.lr, weight_decay=candidate.weight_decay)

    history: list[dict[str, Any]] = []
    n_env = len(env_mapping)
    use_domain = candidate.adv_lambda > 0.0 and n_env > 1
    for epoch in range(1, candidate.epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        logits, domain_logits = model(xt, candidate.adv_lambda if use_domain else 0.0)
        ce_vec = F.cross_entropy(logits, yt, weight=weights, reduction="none")
        cls_loss = ce_vec.mean()

        env_risks = []
        for env_value in torch.unique(et):
            mask = et == env_value
            if int(mask.sum().item()) >= 4:
                env_risks.append(ce_vec[mask].mean())
        if len(env_risks) >= 2:
            risks = torch.stack(env_risks)
            rex_loss = torch.var(risks, unbiased=False)
            worst_loss = torch.max(risks)
        else:
            rex_loss = torch.zeros((), dtype=torch.float32)
            worst_loss = torch.zeros((), dtype=torch.float32)

        if use_domain:
            domain_loss = F.cross_entropy(domain_logits, et)
        else:
            domain_loss = torch.zeros((), dtype=torch.float32)

        loss = (
            cls_loss
            + candidate.adv_lambda * domain_loss
            + candidate.rex_lambda * rex_loss
            + candidate.worst_group_lambda * worst_loss
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()

        if epoch == 1 or epoch == candidate.epochs or epoch % 10 == 0:
            pred = torch.argmax(logits.detach(), dim=1)
            history.append(
                {
                    "candidate": candidate.name,
                    "epoch": epoch,
                    "loss": float(loss.detach().cpu().item()),
                    "cls_loss": float(cls_loss.detach().cpu().item()),
                    "domain_loss": float(domain_loss.detach().cpu().item()),
                    "rex_loss": float(rex_loss.detach().cpu().item()),
                    "worst_group_loss": float(worst_loss.detach().cpu().item()),
                    "train_accuracy": float((pred == yt).float().mean().cpu().item()),
                    "train_rows": int(len(y)),
                    "feature_dim": int(x.shape[1]),
                    "env_classes": int(n_env),
                }
            )

    fitted = FittedNeural(
        candidate=candidate,
        mean=mean,
        std=std,
        model=model,
        env_mapping=env_mapping,
        train_history=history,
    )
    env_counts = pd.Series(envs, dtype="object").value_counts()
    env_rows = [
        {
            "candidate": candidate.name,
            "env_key": str(key),
            "rows": int(value),
            "mapped_id": int(env_mapping.get(str(key), env_mapping["__OTHER__"])),
            "used_for": "domain_adversary_and_rex_fit_only",
        }
        for key, value in env_counts.items()
    ]
    env_rows.append(
        {
            "candidate": candidate.name,
            "env_key": "__OTHER__",
            "rows": int(sum(value for key, value in env_counts.items() if str(key) not in env_mapping)),
            "mapped_id": int(env_mapping["__OTHER__"]),
            "used_for": "domain_adversary_and_rex_fit_only",
        }
    )
    return fitted, audit, history + env_rows


def scores_from_proba(proba: np.ndarray) -> dict[str, np.ndarray]:
    attack = proba[:, ckh.CLASS_ATTACK]
    hard_ood = proba[:, ckh.CLASS_HARD_OOD]
    ood = proba[:, ckh.CLASS_OOD]
    identity = proba[:, ckh.CLASS_ID]
    conflict = np.maximum.reduce([identity, ood, hard_ood])
    p = np.clip(proba, 1e-12, 1.0)
    entropy = -np.sum(p * np.log(p), axis=1)
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "ood_score": ood,
        "id_score": identity,
        "conflict_score": conflict,
        "margin_score": attack - conflict,
        "entropy_score": entropy,
    }


def predict_scores(fitted: FittedNeural, builder: ckq.FlowTemporalBuilder, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    x = feature_matrix(builder, fitted.candidate.feature_kind, role, idx)
    return scores_from_proba(fitted.predict_proba(x))


def attack_threshold(
    fitted: FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    exclude: tuple[str, str] | None = None,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_indices_filtered(frame_by_role, role, "select", eval_cap, exclude=exclude)
        if not len(idx):
            continue
        parts.append(predict_scores(fitted, builder, role, idx)["attack_score"])
    return float(max(np.quantile(part, cko.BENIGN_SAFE_Q) for part in parts if len(part)))


def review_margin_threshold(
    fitted: FittedNeural,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    attack_thr: float,
    eval_cap: int,
    policy: ReviewPolicy,
    exclude: tuple[str, str] | None = None,
) -> dict[str, Any]:
    idx = role_indices_filtered(frame_by_role, "support_val", "select", eval_cap, exclude=exclude)
    score = predict_scores(fitted, builder, "support_val", idx)
    raw_alarm = score["attack_score"] > attack_thr
    margins = score["margin_score"][raw_alarm]
    if policy.support_review_budget <= 0.0 or len(margins) == 0:
        margin_thr = 0.0
    else:
        margin_thr = float(np.quantile(margins, min(1.0, max(0.0, policy.support_review_budget))))
        margin_thr = max(0.0, margin_thr)
    review = raw_alarm & (score["margin_score"] <= margin_thr)
    hard = raw_alarm & (~review)
    return {
        "candidate": fitted.candidate.name,
        "policy": policy.name,
        "support_review_budget": policy.support_review_budget,
        "attack_threshold": attack_thr,
        "margin_review_threshold": margin_thr,
        "support_rows": len(idx),
        "support_raw_alarm_rate": ckg.rate(raw_alarm),
        "support_policy_review_rate": ckg.rate(review),
        "support_policy_hard_rate": ckg.rate(hard),
        "threshold_role": "support_val select only",
        "exclude_field": exclude[0] if exclude else "",
        "exclude_value": exclude[1] if exclude else "",
    }


def eval_role(
    fitted: FittedNeural,
    policy: ReviewPolicy,
    threshold_row: dict[str, Any],
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    role_kind: str,
    eval_cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices_filtered(frame_by_role, role, phase, eval_cap, include=include, exclude=exclude)
    score = predict_scores(fitted, builder, role, idx)
    raw_alarm = score["attack_score"] > float(threshold_row["attack_threshold"])
    review = raw_alarm & (score["margin_score"] <= float(threshold_row["margin_review_threshold"]))
    hard = raw_alarm & (~review)

    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    for key, value in score.items():
        part[key] = value
    part["raw_alarm"] = raw_alarm
    part["conflict_review"] = review
    part["hard_alarm"] = hard
    row = {
        "feature_set": f"{fitted.candidate.name}__{policy.name}",
        "candidate": fitted.candidate.name,
        "policy": policy.name,
        "feature_kind": fitted.candidate.feature_kind,
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(part),
        "attack_threshold": threshold_row["attack_threshold"],
        "margin_review_threshold": threshold_row["margin_review_threshold"],
        "raw_alarm_rate": ckg.rate(raw_alarm),
        "conflict_review_rate": ckg.rate(review),
        "hard_alarm_rate": ckg.rate(hard),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
        "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(part) else float("nan"),
        "margin_score_mean": float(np.mean(score["margin_score"])) if len(part) else float("nan"),
        "entropy_score_mean": float(np.mean(score["entropy_score"])) if len(part) else float("nan"),
    }
    return row, part


def feature_dim_for_kind(builder: ckq.FlowTemporalBuilder, feature_kind: str, frame_by_role: dict[str, pd.DataFrame]) -> int:
    for role, frame in frame_by_role.items():
        if len(frame):
            idx = np.asarray([0], dtype=np.int64)
            return int(feature_matrix(builder, feature_kind, role, idx).shape[1])
    return 0


def build_readout(matrix: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float, smoke: bool) -> list[str]:
    lines = [
        "# issue27cks neural causal/selective head smoke v1",
        "",
        "## Scope",
        "",
        "Local medium-smoke for stronger aligned frontend + neural selective head.",
        "This is dataset-internal robustness repair, not cross-dataset proof.",
        f"Mode: `{'smoke' if smoke else 'full'}`.",
        "",
        "## Main matrix",
        "",
        "| candidate | future hard | same-file hard | sealed attack hard/review | sealed OOD hard/review | sealed OOD group hard max | OOD-stress hard/review |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['feature_set']} | {cko.fmt(row['future_hard'])} | {cko.fmt(row['same_file_hard'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])} | "
            f"{cko.fmt(row['sealed_ood_group_hard_max'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold policies",
            "",
            "| candidate | policy | attack threshold | margin review threshold | support hard | support review |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in threshold_rows:
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {cko.fmt(row['attack_threshold'])} | "
            f"{cko.fmt(row['margin_review_threshold'])} | {cko.fmt(row['support_policy_hard_rate'])} | "
            f"{cko.fmt(row['support_policy_review_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Training uses only support_train/id_calib/ood_val/ood_stress fit phases.",
            "- Attack threshold uses id_calib/ood_val/ood_stress select phases.",
            "- Review margin threshold uses support_val select only.",
            "- Query/future/sealed rows are report-only.",
            "- source_group/device are used only as environment keys for adversarial/REx losses, not inference features.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    set_seeds()
    OUT.mkdir(parents=True, exist_ok=True)

    role_cap_requested = args.role_cap is not None
    smoke = bool(args.smoke or args.micro_smoke or role_cap_requested)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke)
    role_cap_rows: list[dict[str, Any]] = []
    if args.micro_smoke or role_cap_requested:
        per_phase_cap = int(args.micro_role_cap if args.micro_smoke else args.role_cap)
        per_source_cap = int(args.micro_source_cap if args.micro_smoke else args.source_cap)
        cap_rule = (
            "earliest recorded_index rows per phase/source for local-context micro-smoke only"
            if args.micro_smoke
            else "earliest recorded_index rows per phase/source for complete-past capped neural smoke"
        )
        x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            per_phase_cap,
            per_source_cap,
            cap_rule=cap_rule,
        )

    train_cap = int(args.train_cap if args.train_cap is not None else (MICRO_TRAIN_CAP if args.micro_smoke else MEDIUM_TRAIN_CAP))
    eval_cap = int(args.eval_cap if args.eval_cap is not None else (MICRO_EVAL_CAP if args.micro_smoke else MEDIUM_EVAL_CAP))
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=smoke, local_context_only=args.micro_smoke)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    candidates = NEURAL_CANDIDATES
    if args.fast:
        candidates = [NEURAL_CANDIDATES[0], NEURAL_CANDIDATES[2], NEURAL_CANDIDATES[3]]

    role_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    train_history_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        fitted, audit, history = fit_neural_candidate(candidate, builder, frame_by_role, train_cap)
        train_rows.extend({"candidate": candidate.name, **row} for row in audit)
        train_history_rows.extend(history)
        candidate_rows.append(
            {
                **asdict(candidate),
                "feature_dim": feature_dim_for_kind(builder, candidate.feature_kind, frame_by_role),
                "flow_temporal_dim": len(ckq.FLOW_TEMPORAL_FEATURES),
                "enhanced_summary_dim": enhanced_flow_summary_dim(),
            }
        )
        attack_thr = attack_threshold(fitted, builder, frame_by_role, eval_cap)
        for policy in REVIEW_POLICIES:
            thr = review_margin_threshold(fitted, builder, frame_by_role, attack_thr, eval_cap, policy)
            threshold_rows.append(thr)
            spec = cko.FeatureSpec(
                f"{candidate.name}__{policy.name}",
                candidate.feature_kind,
                f"{candidate.description} / {policy.description}",
            )
            for role, phase, kind in cko.ROLE_EVAL:
                row, part = eval_role(fitted, policy, thr, builder, frame_by_role, role, phase, kind, eval_cap)
                role_rows.append(row)
                group_rows.extend(cko.group_rows(spec, role, part))

    matrix = cko.aggregate(role_rows, group_rows)
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(OUT / "candidate_matrix.csv", candidate_rows)
    cko.write_csv(OUT / "train_audit.csv", train_rows)
    cko.write_csv(OUT / "train_history_and_env_audit.csv", train_history_rows)
    cko.write_csv(OUT / "threshold_policy_audit.csv", threshold_rows)
    cko.write_csv(OUT / "role_metrics.csv", role_rows)
    cko.write_csv(OUT / "group_metrics_by_source_device.csv", group_rows)
    cko.write_csv(OUT / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(OUT / "alignment_audit.csv", alignment_rows)
    cko.write_csv(OUT / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    cko.write_md(OUT / "codex_readout.md", build_readout(matrix, threshold_rows, seconds, smoke))
    cko.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "aligned enhanced frontend plus neural selective causal-style head smoke",
            "smoke": smoke,
            "micro_smoke": args.micro_smoke,
            "fast": args.fast,
            "train_cap": train_cap,
            "eval_cap": eval_cap,
            "medium_role_cap_default": MEDIUM_ROLE_CAP,
            "medium_source_cap_default": MEDIUM_SOURCE_CAP,
            "torch_version": getattr(torch, "__version__", "missing") if torch is not None else "missing",
            "feature_contract": {
                "raw115": "loaded by cko.load_role_inputs",
                "flow_temporal": "ckq past-only FlowTemporalBuilder, same role/index rows as raw115",
                "enhanced_summary": "derived from the same aligned flow-temporal matrix; not independently indexed",
                "env_keys": "source_group|device used only for domain-adversarial/REx training losses",
                "processed_label_used_as_feature": False,
                "source_or_device_used_as_inference_feature": False,
            },
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "attack_threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
                "review_threshold_role": "support_val select only",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "candidates": [asdict(c) for c in candidates],
            "review_policies": [asdict(p) for p in REVIEW_POLICIES],
            "input_audit": input_audit,
            "role_cap_audit": role_cap_rows,
            "alignment_audit": {
                "sample_per_role": cko.ALIGNMENT_AUDIT_SAMPLE_PER_ROLE,
                "rows": len(alignment_rows),
                "purpose": "report-only raw115-to-flow-temporal row pairing evidence",
            },
            "outputs": [
                "candidate_summary_matrix.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "train_audit.csv",
                "train_history_and_env_audit.csv",
                "threshold_policy_audit.csv",
                "flow_temporal_extraction_audit.csv",
                "alignment_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds, "smoke": smoke}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--micro-smoke", action="store_true", help="tiny code-path check with capped role rows")
    parser.add_argument("--micro-role-cap", type=int, default=512)
    parser.add_argument("--micro-source-cap", type=int, default=48)
    parser.add_argument("--role-cap", type=int, default=MEDIUM_ROLE_CAP, help="cap rows per role phase for local medium smoke")
    parser.add_argument("--source-cap", type=int, default=MEDIUM_SOURCE_CAP, help="cap rows per source within each role phase")
    parser.add_argument("--train-cap", type=int, default=None)
    parser.add_argument("--eval-cap", type=int, default=None)
    parser.add_argument("--fast", action="store_true", help="skip one direct raw+flow candidate for quicker local diagnosis")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
