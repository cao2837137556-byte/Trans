"""issue27ckaa: contrastive interaction/causal representation map v1.

This is the next step after CKY/CKZ:

* CKY showed that richer interaction/causal evidence contains attack signal,
  but direct full classifiers still learn device/OOD-family shortcuts.
* CKZ showed that simply replacing the router with a neural head does not make
  the conflict signal transferable.

CKAA trains an explicit representation map over the CKY frontend:

    attack_mechanism branch  \
                              -> latent map -> 4-class head
    conflict_context branch  /

The map is trained only on legal fit roles and can use:

* four-class supervision: ID / OOD / hard-OOD / attack
* attack-vs-nonattack center contrastive margins
* source/device environment adversarial and REx-style penalties

Query/future/sealed roles are report-only.  Environment labels are training
constraints only and are never inference features.
"""

from __future__ import annotations

import argparse
import json
import math
import re
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
except Exception as exc:  # pragma: no cover
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
import issue27cks_neural_causal_selective_head_v1 as cks  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402


ISSUE = "issue27ckaa_contrastive_interaction_map_v1_2026-07-03"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"
SEED = 42
BENIGN_SAFE_Q = 0.99


@dataclass(frozen=True)
class MapCandidate:
    name: str
    hidden_dim: int
    map_dim: int
    epochs: int
    lr: float
    weight_decay: float
    dropout: float
    contrast_lambda: float
    contrast_margin: float
    adv_lambda: float
    rex_lambda: float
    worst_group_lambda: float
    description: str


@dataclass(frozen=True)
class ReviewPolicy:
    name: str
    support_review_budget: float
    description: str


CANDIDATES = [
    MapCandidate(
        name="A1_ce_map_control",
        hidden_dim=96,
        map_dim=48,
        epochs=80,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        contrast_lambda=0.0,
        contrast_margin=1.20,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="Dual-branch representation map with four-class CE only.",
    ),
    MapCandidate(
        name="A2_contrastive_map",
        hidden_dim=112,
        map_dim=56,
        epochs=90,
        lr=9e-4,
        weight_decay=1.2e-4,
        dropout=0.12,
        contrast_lambda=0.25,
        contrast_margin=1.20,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="CE plus center contrastive margin between attack and ID/OOD/hard-OOD.",
    ),
    MapCandidate(
        name="A3_contrastive_invariant_map",
        hidden_dim=128,
        map_dim=64,
        epochs=100,
        lr=8e-4,
        weight_decay=1.5e-4,
        dropout=0.15,
        contrast_lambda=0.25,
        contrast_margin=1.20,
        adv_lambda=0.04,
        rex_lambda=0.10,
        worst_group_lambda=0.03,
        description="CE plus contrastive map with GRL environment adversary and REx/worst-group pressure.",
    ),
]


POLICIES = [
    ReviewPolicy(
        name="P0_no_review_margin0",
        support_review_budget=0.0,
        description="No budgeted review: hard only when attack probability beats conflict probability.",
    ),
    ReviewPolicy(
        name="P1_support_review_1pp",
        support_review_budget=0.01,
        description="Allow at most about 1pp support attack low-margin review.",
    ),
]


def ensure_torch() -> None:
    if torch is None:
        raise RuntimeError(f"PyTorch is required for issue27ckaa; import error: {TORCH_IMPORT_ERROR}")


def set_seeds() -> None:
    np.random.seed(SEED)
    ensure_torch()
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, min(8, int(torch.get_num_threads()))))


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def candidate_by_name(name: str) -> MapCandidate:
    for candidate in CANDIDATES:
        if candidate.name == name:
            return candidate
    raise ValueError(name)


def role_indices(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    return cks.role_indices_filtered(frame_by_role, role, phase, cap, include=include, exclude=exclude)


def env_to_ids(envs: list[str], max_envs: int = 32) -> tuple[np.ndarray, dict[str, int]]:
    counts = pd.Series(envs, dtype="object").value_counts()
    keep = list(counts.index[:max_envs])
    mapping = {str(key): i for i, key in enumerate(keep)}
    other_id = len(mapping)
    mapping["__OTHER__"] = other_id
    ids = np.asarray([mapping.get(str(key), other_id) for key in envs], dtype=np.int64)
    return ids, mapping


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(x, axis=0).astype(np.float32)
    std = np.std(x, axis=0).astype(np.float32)
    std[std < 1e-6] = 1.0
    return mean, std


def standardize_apply(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.nan_to_num((np.asarray(x, dtype=np.float32) - mean) / std, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def class_weights(y: np.ndarray) -> torch.Tensor:
    counts = np.bincount(np.asarray(y, dtype=np.int64), minlength=len(ckq.CLASS_LABELS)).astype(np.float64)
    weights = np.zeros(len(ckq.CLASS_LABELS), dtype=np.float32)
    total = float(np.sum(counts))
    for label in range(len(weights)):
        weights[label] = float(total / max(1.0, counts[label]))
    weights /= max(1e-12, float(np.mean(weights[weights > 0])))
    return torch.from_numpy(weights.astype(np.float32))


class GradientReverse(torch.autograd.Function):  # type: ignore[misc]
    @staticmethod
    def forward(ctx: Any, x: torch.Tensor, lambd: float) -> torch.Tensor:
        ctx.lambd = lambd
        return x.view_as(x)

    @staticmethod
    def backward(ctx: Any, grad_output: torch.Tensor) -> tuple[torch.Tensor, None]:
        return -float(ctx.lambd) * grad_output, None


class BranchEncoder(nn.Module):  # type: ignore[misc]
    def __init__(self, in_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, max(16, hidden_dim // 2)),
            nn.LayerNorm(max(16, hidden_dim // 2)),
            nn.ReLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class InteractionMapNet(nn.Module):  # type: ignore[misc]
    def __init__(self, mech_dim: int, ctx_dim: int, hidden_dim: int, map_dim: int, n_env: int, dropout: float):
        super().__init__()
        self.mech_encoder = BranchEncoder(mech_dim, hidden_dim, dropout)
        self.ctx_encoder = BranchEncoder(ctx_dim, hidden_dim, dropout)
        branch_latent = max(16, hidden_dim // 2)
        self.fusion = nn.Sequential(
            nn.Linear(branch_latent * 2, map_dim),
            nn.LayerNorm(map_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(map_dim, map_dim),
            nn.LayerNorm(map_dim),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(map_dim, len(ckq.CLASS_LABELS))
        self.domain = nn.Linear(map_dim, max(1, n_env))

    def forward(self, x_mech: torch.Tensor, x_ctx: torch.Tensor, grl_lambda: float = 0.0) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        zm = self.mech_encoder(x_mech)
        zc = self.ctx_encoder(x_ctx)
        z = self.fusion(torch.cat([zm, zc], dim=1))
        logits = self.classifier(z)
        z_rev = GradientReverse.apply(z, grl_lambda)
        domain_logits = self.domain(z_rev)
        return logits, domain_logits, z


def center_contrastive_loss(z: torch.Tensor, y: torch.Tensor, margin: float) -> torch.Tensor:
    z_norm = F.normalize(z, dim=1)
    labels = torch.unique(y)
    centers: dict[int, torch.Tensor] = {}
    pull_terms = []
    for label_t in labels:
        label = int(label_t.item())
        mask = y == label_t
        if int(mask.sum().item()) < 1:
            continue
        center = F.normalize(z_norm[mask].mean(dim=0, keepdim=True), dim=1).squeeze(0)
        centers[label] = center
        pull_terms.append(torch.sum((z_norm[mask] - center) ** 2, dim=1).mean())
    pull = torch.stack(pull_terms).mean() if pull_terms else torch.zeros((), dtype=torch.float32, device=z.device)

    push_terms = []
    attack_label = ckh.CLASS_ATTACK
    if attack_label in centers:
        attack_center = centers[attack_label]
        for label in [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD]:
            if label in centers:
                dist = torch.sum((attack_center - centers[label]) ** 2)
                push_terms.append(F.relu(float(margin) - dist))
    push = torch.stack(push_terms).mean() if push_terms else torch.zeros((), dtype=torch.float32, device=z.device)
    return pull + push


@dataclass
class FittedMap:
    candidate: MapCandidate
    mech_mean: np.ndarray
    mech_std: np.ndarray
    ctx_mean: np.ndarray
    ctx_std: np.ndarray
    model: Any
    env_mapping: dict[str, int]
    train_history: list[dict[str, Any]]

    def transform(self, x_mech: np.ndarray, x_ctx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return standardize_apply(x_mech, self.mech_mean, self.mech_std), standardize_apply(x_ctx, self.ctx_mean, self.ctx_std)

    def predict_proba_and_latent(self, x_mech: np.ndarray, x_ctx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ensure_torch()
        self.model.eval()
        xm, xc = self.transform(x_mech, x_ctx)
        tm = torch.from_numpy(xm)
        tc = torch.from_numpy(xc)
        with torch.no_grad():
            logits, _domain, z = self.model(tm, tc, 0.0)
            proba = torch.softmax(logits, dim=1).cpu().numpy()
            latent = z.cpu().numpy()
        return np.asarray(proba, dtype=np.float64), np.asarray(latent, dtype=np.float32)


def add_train_chunk(
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    label: int,
    cap: int,
    exclude: tuple[str, str] | None,
    mech_xs: list[np.ndarray],
    ctx_xs: list[np.ndarray],
    ys: list[np.ndarray],
    envs: list[str],
    audit: list[dict[str, Any]],
) -> None:
    idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
    mech_xs.append(frontend.matrix(role, idx, "attack_mechanism"))
    ctx_xs.append(frontend.matrix(role, idx, "conflict_context"))
    ys.append(np.full(len(idx), label, dtype=np.int64))
    envs.extend(cks.env_keys(frame_by_role[role].iloc[idx].reset_index(drop=True)))
    audit.append(
        {
            "role": role,
            "phase": phase,
            "rows": len(idx),
            "label": label,
            "label_name": ckq.CLASS_NAMES.get(label, str(label)),
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )


def build_train_set(
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[dict[str, Any]]]:
    mech_xs: list[np.ndarray] = []
    ctx_xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    envs: list[str] = []
    audit: list[dict[str, Any]] = []

    add_train_chunk(frontend, frame_by_role, "support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP, exclude, mech_xs, ctx_xs, ys, envs, audit)
    add_train_chunk(frontend, frame_by_role, "id_calib", "fit", ckh.CLASS_ID, train_cap, exclude, mech_xs, ctx_xs, ys, envs, audit)
    add_train_chunk(frontend, frame_by_role, "ood_val", "fit", ckh.CLASS_OOD, train_cap, exclude, mech_xs, ctx_xs, ys, envs, audit)
    add_train_chunk(frontend, frame_by_role, "ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap, exclude, mech_xs, ctx_xs, ys, envs, audit)

    return (
        np.vstack(mech_xs).astype(np.float32),
        np.vstack(ctx_xs).astype(np.float32),
        np.concatenate(ys).astype(np.int64),
        envs,
        audit,
    )


def latent_center_rows(candidate: str, split: str, held_value: str, latent: np.ndarray, y: np.ndarray, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if len(latent) == 0:
        return rows
    z = np.asarray(latent, dtype=np.float64)
    norms = np.linalg.norm(z, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1.0
    z = z / norms
    centers: dict[int, np.ndarray] = {}
    for label in sorted(set(int(v) for v in y)):
        mask = np.asarray(y) == label
        if np.sum(mask) == 0:
            continue
        center = np.mean(z[mask], axis=0)
        norm = np.linalg.norm(center)
        if norm > 1e-12:
            center = center / norm
        centers[int(label)] = center
        rows.append(
            {
                "candidate": candidate,
                "split": split,
                "held_value": held_value,
                "audit_scope": prefix,
                "metric": "class_count",
                "label_a": int(label),
                "label_a_name": ckq.CLASS_NAMES.get(int(label), str(label)),
                "label_b": "",
                "label_b_name": "",
                "value": int(np.sum(mask)),
            }
        )
    for a in sorted(centers):
        for b in sorted(centers):
            if b <= a:
                continue
            dist = float(np.sum((centers[a] - centers[b]) ** 2))
            rows.append(
                {
                    "candidate": candidate,
                    "split": split,
                    "held_value": held_value,
                    "audit_scope": prefix,
                    "metric": "normalized_center_sqdist",
                    "label_a": int(a),
                    "label_a_name": ckq.CLASS_NAMES.get(int(a), str(a)),
                    "label_b": int(b),
                    "label_b_name": ckq.CLASS_NAMES.get(int(b), str(b)),
                    "value": dist,
                }
            )
    return rows


def fit_map_candidate(
    candidate: MapCandidate,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    split: str,
    held_value: str,
    exclude: tuple[str, str] | None = None,
) -> tuple[FittedMap, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ensure_torch()
    x_mech, x_ctx, y, envs, audit = build_train_set(frontend, frame_by_role, train_cap, exclude=exclude)
    env_id, env_mapping = env_to_ids(envs)
    mech_mean, mech_std = standardize_fit(x_mech)
    ctx_mean, ctx_std = standardize_fit(x_ctx)
    xm = torch.from_numpy(standardize_apply(x_mech, mech_mean, mech_std))
    xc = torch.from_numpy(standardize_apply(x_ctx, ctx_mean, ctx_std))
    yt = torch.from_numpy(y.astype(np.int64))
    et = torch.from_numpy(env_id.astype(np.int64))
    weights = class_weights(y)

    model = InteractionMapNet(x_mech.shape[1], x_ctx.shape[1], candidate.hidden_dim, candidate.map_dim, len(env_mapping), candidate.dropout)
    opt = torch.optim.AdamW(model.parameters(), lr=candidate.lr, weight_decay=candidate.weight_decay)
    history: list[dict[str, Any]] = []
    use_domain = candidate.adv_lambda > 0.0 and len(env_mapping) > 1

    for epoch in range(1, candidate.epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        logits, domain_logits, z = model(xm, xc, candidate.adv_lambda if use_domain else 0.0)
        ce_vec = F.cross_entropy(logits, yt, weight=weights, reduction="none")
        cls_loss = ce_vec.mean()
        contrast_loss = center_contrastive_loss(z, yt, candidate.contrast_margin) if candidate.contrast_lambda > 0.0 else torch.zeros((), dtype=torch.float32)

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
            + candidate.contrast_lambda * contrast_loss
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
                    "split": split,
                    "held_value": held_value,
                    "epoch": epoch,
                    "loss": float(loss.detach().cpu().item()),
                    "cls_loss": float(cls_loss.detach().cpu().item()),
                    "contrast_loss": float(contrast_loss.detach().cpu().item()),
                    "domain_loss": float(domain_loss.detach().cpu().item()),
                    "rex_loss": float(rex_loss.detach().cpu().item()),
                    "worst_group_loss": float(worst_loss.detach().cpu().item()),
                    "train_accuracy": float((pred == yt).float().mean().cpu().item()),
                    "train_rows": int(len(y)),
                    "mech_dim": int(x_mech.shape[1]),
                    "ctx_dim": int(x_ctx.shape[1]),
                    "map_dim": int(candidate.map_dim),
                    "env_classes": int(len(env_mapping)),
                }
            )

    fitted = FittedMap(
        candidate=candidate,
        mech_mean=mech_mean,
        mech_std=mech_std,
        ctx_mean=ctx_mean,
        ctx_std=ctx_std,
        model=model,
        env_mapping=env_mapping,
        train_history=history,
    )
    _proba, latent = fitted.predict_proba_and_latent(x_mech, x_ctx)
    center_rows = latent_center_rows(candidate.name, split, held_value, latent, y, "fit_train")
    env_counts = pd.Series(envs, dtype="object").value_counts()
    env_rows = [
        {
            "candidate": candidate.name,
            "split": split,
            "held_value": held_value,
            "env_key": str(key),
            "rows": int(value),
            "mapped_id": int(env_mapping.get(str(key), env_mapping["__OTHER__"])),
            "used_for": "domain_adversary_and_rex_fit_only",
        }
        for key, value in env_counts.items()
    ]
    for row in audit:
        row["candidate"] = candidate.name
        row["split"] = split
        row["held_value"] = held_value
        row["contrast_lambda"] = candidate.contrast_lambda
        row["adv_lambda"] = candidate.adv_lambda
        row["rex_lambda"] = candidate.rex_lambda
        row["worst_group_lambda"] = candidate.worst_group_lambda
    return fitted, audit, history + env_rows, center_rows


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


def predict_scores(fitted: FittedMap, frontend: cky.InteractionCausalFrontend, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    if len(idx) == 0:
        empty = np.asarray([], dtype=np.float64)
        return {
            "attack_score": empty,
            "hard_ood_score": empty,
            "ood_score": empty,
            "id_score": empty,
            "conflict_score": empty,
            "margin_score": empty,
            "entropy_score": empty,
        }
    x_mech = frontend.matrix(role, idx, "attack_mechanism")
    x_ctx = frontend.matrix(role, idx, "conflict_context")
    proba, _latent = fitted.predict_proba_and_latent(x_mech, x_ctx)
    return scores_from_proba(proba)


def attack_threshold(
    fitted: FittedMap,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    benign_q: float,
    exclude: tuple[str, str] | None = None,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_indices(frame_by_role, role, "select", eval_cap, exclude=exclude)
        if len(idx):
            parts.append(predict_scores(fitted, frontend, role, idx)["attack_score"])
    if not parts:
        return 1.0
    return float(max(np.quantile(part, benign_q) for part in parts if len(part)))


def policy_thresholds(
    fitted: FittedMap,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    attack_thr: float,
    policy: ReviewPolicy,
    exclude: tuple[str, str] | None = None,
) -> dict[str, Any]:
    idx = role_indices(frame_by_role, "support_val", "select", eval_cap, exclude=exclude)
    score = predict_scores(fitted, frontend, "support_val", idx)
    raw = score["attack_score"] > attack_thr
    margins = score["margin_score"][raw]
    if policy.support_review_budget <= 0.0 or len(margins) == 0:
        margin_thr = 0.0
    else:
        margin_thr = max(0.0, float(np.quantile(margins, policy.support_review_budget)))
    suppress = raw & (score["margin_score"] <= 0.0)
    review = raw & (score["margin_score"] > 0.0) & (score["margin_score"] <= margin_thr)
    hard = raw & (~suppress) & (~review)
    return {
        "candidate": fitted.candidate.name,
        "policy": policy.name,
        "support_review_budget": policy.support_review_budget,
        "attack_threshold": attack_thr,
        "margin_review_threshold": margin_thr,
        "support_rows": len(idx),
        "support_raw_alarm_rate": ckg.rate(raw),
        "support_hard_rate": ckg.rate(hard),
        "support_review_rate": ckg.rate(review),
        "support_suppress_rate": ckg.rate(suppress),
        "exclude_field": exclude[0] if exclude else "",
        "exclude_value": exclude[1] if exclude else "",
    }


def decide(score: dict[str, np.ndarray], threshold_row: dict[str, Any]) -> dict[str, np.ndarray]:
    raw = score["attack_score"] > float(threshold_row["attack_threshold"])
    margin = score["margin_score"]
    suppress = raw & (margin <= 0.0)
    review = raw & (margin > 0.0) & (margin <= float(threshold_row["margin_review_threshold"]))
    hard = raw & (~suppress) & (~review)
    return {"raw_alarm": raw, "hard_alarm": hard, "review": review, "suppress": suppress}


def eval_role(
    fitted: FittedMap,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    role_kind: str,
    eval_cap: int,
    threshold_row: dict[str, Any],
    split: str,
    include: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, eval_cap, include=include)
    score = predict_scores(fitted, frontend, role, idx)
    decision = decide(score, threshold_row)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    for key, value in score.items():
        part[key] = value
    for key, value in decision.items():
        part[key] = value
    part["conflict_review"] = decision["review"]
    row = {
        "candidate": fitted.candidate.name,
        "policy": threshold_row["policy"],
        "split": split,
        "held_field": include[0] if include else "",
        "held_value": include[1] if include else "",
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(idx),
        "attack_threshold": threshold_row["attack_threshold"],
        "margin_review_threshold": threshold_row["margin_review_threshold"],
        "raw_alarm_rate": ckg.rate(decision["raw_alarm"]),
        "hard_alarm_rate": ckg.rate(decision["hard_alarm"]),
        "review_rate": ckg.rate(decision["review"]),
        "suppress_rate": ckg.rate(decision["suppress"]),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(idx) else float("nan"),
        "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(idx) else float("nan"),
        "margin_score_mean": float(np.mean(score["margin_score"])) if len(idx) else float("nan"),
        "entropy_score_mean": float(np.mean(score["entropy_score"])) if len(idx) else float("nan"),
    }
    return row, part


def eval_candidate(
    candidate: MapCandidate,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    benign_q: float,
    split: str,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    held_value = include[1] if include else ""
    fitted, train_rows, history_rows, center_rows = fit_map_candidate(candidate, frontend, frame_by_role, train_cap, split, held_value, exclude=exclude)
    attack_thr = attack_threshold(fitted, frontend, frame_by_role, eval_cap, benign_q, exclude=exclude)
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    for policy in POLICIES:
        thr = policy_thresholds(fitted, frontend, frame_by_role, eval_cap, attack_thr, policy, exclude=exclude)
        thr["split"] = split
        thr["held_field"] = include[0] if include else ""
        thr["held_value"] = held_value
        threshold_rows.append(thr)
        spec = cko.FeatureSpec(f"{candidate.name}__{policy.name}", "ckaa_representation_map", candidate.description)
        for role, phase, kind in cko.ROLE_EVAL:
            role_include = include if split == "leave_device_family" else None
            row, part = eval_role(fitted, frontend, frame_by_role, role, phase, kind, eval_cap, thr, split=split, include=role_include)
            role_rows.append(row)
            group_rows.extend(cko.group_rows(spec, role, part))
    return role_rows, threshold_rows, train_rows, history_rows, center_rows + group_rows


def pick(rows: list[dict[str, Any]], split: str, candidate: str, policy: str, role: str, metric: str, held_value: str = "") -> float:
    for row in rows:
        if (
            row["split"] == split
            and row["candidate"] == candidate
            and row["policy"] == policy
            and row["role"] == role
            and str(row.get("held_value", "")) == held_value
        ):
            return float(row.get(metric, float("nan")))
    return float("nan")


def main_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(r["candidate"], r["policy"]) for r in role_rows if r["split"] == "main"})
    out = []
    for candidate, policy in keys:
        out.append(
            {
                "candidate": candidate,
                "policy": policy,
                "future_hard": pick(role_rows, "main", candidate, policy, "future_query", "hard_alarm_rate"),
                "future_review": pick(role_rows, "main", candidate, policy, "future_query", "review_rate"),
                "future_suppress": pick(role_rows, "main", candidate, policy, "future_query", "suppress_rate"),
                "sealed_attack_hard": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_review": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "review_rate"),
                "sealed_attack_suppress": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "suppress_rate"),
                "sealed_ood_hard": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_review": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "review_rate"),
                "sealed_ood_suppress": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "suppress_rate"),
                "ood_stress_hard": pick(role_rows, "main", candidate, policy, "ood_stress", "hard_alarm_rate"),
                "ood_stress_review": pick(role_rows, "main", candidate, policy, "ood_stress", "review_rate"),
                "ood_stress_suppress": pick(role_rows, "main", candidate, policy, "ood_stress", "suppress_rate"),
            }
        )
    return out


def leave_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in role_rows:
        if row["split"] != "leave_device_family" or row["role"] not in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}:
            continue
        out.append(
            {
                "candidate": row["candidate"],
                "policy": row["policy"],
                "held_value": row.get("held_value", ""),
                "role": row["role"],
                "rows": row["rows"],
                "raw_alarm_rate": row["raw_alarm_rate"],
                "hard_alarm_rate": row["hard_alarm_rate"],
                "review_rate": row["review_rate"],
                "suppress_rate": row["suppress_rate"],
                "attack_score_mean": row["attack_score_mean"],
                "conflict_score_mean": row["conflict_score_mean"],
                "margin_score_mean": row["margin_score_mean"],
                "entropy_score_mean": row["entropy_score_mean"],
            }
        )
    return out


def build_readout(main_rows: list[dict[str, Any]], leave_rows: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckaa contrastive interaction/causal representation map v1",
        "",
        "## Scope",
        "",
        "Local smoke for CKY frontend plus explicit representation-map learning.",
        "Fit roles only train the map; query/future/sealed roles remain report-only.",
        "",
        "## Main roles",
        "",
        "| candidate | policy | future h/r/s | sealed attack h/r/s | sealed OOD h/r/s | OOD-stress h/r/s |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in main_rows:
        lines.append(
            f"| {row['candidate']} | {row['policy']} | "
            f"{cko.fmt(row['future_hard'])}/{cko.fmt(row['future_review'])}/{cko.fmt(row['future_suppress'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])}/{cko.fmt(row['sealed_attack_suppress'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])}/{cko.fmt(row['sealed_ood_suppress'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])}/{cko.fmt(row['ood_stress_suppress'])} |"
        )
    lines.extend(
        [
            "",
            "## Leave-device-family stress",
            "",
            "| candidate | policy | held family | role | rows | raw | hard | review | suppress | attack/conflict/margin mean |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in leave_rows:
        if int(row["rows"]) == 0:
            continue
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['raw_alarm_rate'])} | {cko.fmt(row['hard_alarm_rate'])} | "
            f"{cko.fmt(row['review_rate'])} | {cko.fmt(row['suppress_rate'])} | "
            f"{cko.fmt(row['attack_score_mean'])}/{cko.fmt(row['conflict_score_mean'])}/{cko.fmt(row['margin_score_mean'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold audit",
            "",
            "| candidate | split | held | policy | attack thr | margin review thr | support hard/review/suppress |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in threshold_rows:
        lines.append(
            f"| {row['candidate']} | {row['split']} | {row.get('held_value','')} | {row['policy']} | "
            f"{cko.fmt(row['attack_threshold'])} | {cko.fmt(row['margin_review_threshold'])} | "
            f"{cko.fmt(row['support_hard_rate'])}/{cko.fmt(row['support_review_rate'])}/{cko.fmt(row['support_suppress_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit uses only support_train/id_calib/ood_val/ood_stress fit phases.",
            "- Thresholds use only id_calib/ood_val/ood_stress/support_val select phases.",
            "- Leave-family stress excludes the held device_family from fit and thresholds.",
            "- Query/future/sealed rows are report-only.",
            "- h/r/s = hard/review/suppress.",
            "- This is Gotham-internal representation repair, not cross-dataset proof.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    set_seeds()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(True)
    x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
        x_by_role,
        frame_by_role,
        int(args.role_cap),
        int(args.source_cap),
        cap_rule="contrastive interaction-map capped local smoke",
    )
    ckt.add_family_columns(frame_by_role)
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    frontend = cky.InteractionCausalFrontend(builder)

    candidate_names = [item.strip() for item in str(args.candidates).split(",") if item.strip()]
    candidates = [candidate_by_name(name) for name in candidate_names]
    held_values = [item.strip() for item in str(args.held_values).split(",") if item.strip()]

    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    center_and_group_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        rows, thrs, trains, hist, centers = eval_candidate(
            candidate,
            frontend,
            frame_by_role,
            int(args.train_cap),
            int(args.eval_cap),
            float(args.benign_q),
            split="main",
        )
        role_rows.extend(rows)
        threshold_rows.extend(thrs)
        train_rows.extend(trains)
        history_rows.extend(hist)
        center_and_group_rows.extend(centers)

    for held_value in held_values:
        counts = {
            "ood_val": ckt.rows_for(frame_by_role, "ood_val", "select", "device_family", held_value, int(args.eval_cap)),
            "ood_stress": ckt.rows_for(frame_by_role, "ood_stress", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_ood": ckt.rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", held_value, int(args.eval_cap)),
            "future_query": ckt.rows_for(frame_by_role, "future_query", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_attack": ckt.rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", held_value, int(args.eval_cap)),
        }
        selected_rows.append({"held_field": "device_family", "held_value": held_value, "total_eval_rows": sum(counts.values()), **counts})
        exclude = ("device_family", held_value)
        include = ("device_family", held_value)
        for candidate in candidates:
            rows, thrs, trains, hist, centers = eval_candidate(
                candidate,
                frontend,
                frame_by_role,
                int(args.train_cap),
                int(args.eval_cap),
                float(args.benign_q),
                split="leave_device_family",
                include=include,
                exclude=exclude,
            )
            role_rows.extend(rows)
            threshold_rows.extend(thrs)
            train_rows.extend(trains)
            history_rows.extend(hist)
            center_and_group_rows.extend(centers)

    main_rows = main_summary(role_rows)
    leave_rows = leave_summary(role_rows)
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(out / "main_summary_matrix.csv", main_rows)
    cko.write_csv(out / "leave_device_family_summary_matrix.csv", leave_rows)
    cko.write_csv(out / "role_metrics.csv", role_rows)
    cko.write_csv(out / "threshold_policy_audit.csv", threshold_rows)
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "train_history_and_env_audit.csv", history_rows)
    cko.write_csv(out / "representation_and_group_audit.csv", center_and_group_rows)
    cko.write_csv(out / "evidence_feature_registry.csv", frontend.registry())
    cko.write_csv(out / "selected_leave_groups.csv", selected_rows)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "alignment_audit.csv", alignment_rows)
    cko.write_md(out / "codex_readout.md", build_readout(main_rows, leave_rows, threshold_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "scope": "contrastive interaction/causal representation map",
            "role_cap": args.role_cap,
            "source_cap": args.source_cap,
            "train_cap": args.train_cap,
            "eval_cap": args.eval_cap,
            "benign_q": args.benign_q,
            "candidates": [asdict(c) for c in candidates],
            "review_policies": [asdict(p) for p in POLICIES],
            "held_values": held_values,
            "torch_version": getattr(torch, "__version__", "missing") if torch is not None else "missing",
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "leave_family_exclusion": "held device_family excluded from fit and thresholds",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "representation_contract": {
                "frontend": "CKY interaction/causal evidence frontend",
                "latent_map_training": "legal fit roles only",
                "contrastive_margin": "attack center pushed from ID/OOD/hard-OOD centers",
                "source_or_device_used_as_inference_feature": False,
                "env_keys": "source_group|device used only for adversarial and risk penalties",
            },
            "input_audit": input_audit,
            "selected_leave_groups": selected_rows,
            "alignment_audit_rows": len(alignment_rows),
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=768)
    parser.add_argument("--source-cap", type=int, default=48)
    parser.add_argument("--train-cap", type=int, default=512)
    parser.add_argument("--eval-cap", type=int, default=768)
    parser.add_argument("--benign-q", type=float, default=BENIGN_SAFE_Q)
    parser.add_argument("--candidates", default="A1_ce_map_control,A2_contrastive_map,A3_contrastive_invariant_map")
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
