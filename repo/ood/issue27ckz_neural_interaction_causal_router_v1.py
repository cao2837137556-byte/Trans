"""issue27ckz: neural interaction/causal evidence router v1.

This experiment follows the issue27cky diagnosis:

* full direct classifiers can recover attack on the main split but learn
  device/source/OOD-family shortcuts under leave-family stress;
* strict evidence routing protects OOD but loses too much attack recall.

CKZ keeps the evidence contract, but replaces the tree router with a neural
two-branch router:

    attack mechanism branch -> attack score
    context/conflict branch -> OOD-vs-attack conflict score

The attack branch can be trained with source/device environment adversarial
and REx-style penalties.  Environment labels are used only as training
constraints, never as inference features.
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
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27cks_neural_causal_selective_head_v1 as cks  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402


ISSUE = "issue27ckz_neural_interaction_causal_router_v1_2026-07-03"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"
SEED = 42
BENIGN_SAFE_Q = 0.99


@dataclass(frozen=True)
class NeuralRouterCandidate:
    name: str
    hidden_dim: int
    epochs: int
    lr: float
    weight_decay: float
    dropout: float
    adv_lambda: float
    rex_lambda: float
    worst_group_lambda: float
    conflict_include_id: bool
    description: str


@dataclass(frozen=True)
class ReviewPolicy:
    name: str
    support_review_budget: float
    description: str


NEURAL_CANDIDATES = [
    NeuralRouterCandidate(
        name="Z1_neural_mech_context_router",
        hidden_dim=64,
        epochs=70,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        conflict_include_id=False,
        description="Two-branch neural router with no environment-invariance penalty.",
    ),
    NeuralRouterCandidate(
        name="Z2_neural_mech_context_adv_rex_router",
        hidden_dim=96,
        epochs=85,
        lr=8e-4,
        weight_decay=1.5e-4,
        dropout=0.15,
        adv_lambda=0.06,
        rex_lambda=0.12,
        worst_group_lambda=0.04,
        conflict_include_id=False,
        description="Two-branch neural router with GRL domain adversary plus REx/worst-group pressure.",
    ),
    NeuralRouterCandidate(
        name="Z3_neural_mech_allbenign_conflict_router",
        hidden_dim=64,
        epochs=70,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        conflict_include_id=True,
        description=(
            "Two-branch router where conflict context learns support-vs-all-benign "
            "instead of support-vs-OOD-only; tests whether conflict generalizes better."
        ),
    ),
]


REVIEW_POLICIES = [
    ReviewPolicy(
        name="P0_no_review_margin0",
        support_review_budget=0.0,
        description="No budgeted review: hard only when attack score beats conflict score.",
    ),
    ReviewPolicy(
        name="P1_support_review_1pp",
        support_review_budget=0.01,
        description="Allow at most about 1pp support low-margin review.",
    ),
]


def ensure_torch() -> None:
    if torch is None:
        raise RuntimeError(f"PyTorch is required for issue27ckz; import error: {TORCH_IMPORT_ERROR}")


def set_seeds() -> None:
    np.random.seed(SEED)
    ensure_torch()
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, min(8, int(torch.get_num_threads()))))


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def candidate_by_name(name: str) -> NeuralRouterCandidate:
    for candidate in NEURAL_CANDIDATES:
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


def sample_weights(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.int64)
    counts = np.bincount(y, minlength=2).astype(np.float64)
    total = float(np.sum(counts))
    weights = np.zeros(2, dtype=np.float32)
    for label in range(2):
        weights[label] = float(total / max(1.0, counts[label]))
    weights /= max(1e-12, float(np.mean(weights[weights > 0])))
    return weights[y].astype(np.float32)


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(x, axis=0).astype(np.float32)
    std = np.std(x, axis=0).astype(np.float32)
    std[std < 1e-6] = 1.0
    return mean, std


def standardize_apply(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.nan_to_num((np.asarray(x, dtype=np.float32) - mean) / std, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


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


class DualBranchRouter(nn.Module):  # type: ignore[misc]
    def __init__(self, mech_dim: int, ctx_dim: int, hidden_dim: int, n_env: int, dropout: float):
        super().__init__()
        self.mech_encoder = BranchEncoder(mech_dim, hidden_dim, dropout)
        self.ctx_encoder = BranchEncoder(ctx_dim, hidden_dim, dropout)
        latent = max(16, hidden_dim // 2)
        self.attack_head = nn.Linear(latent, 1)
        self.conflict_head = nn.Linear(latent, 1)
        self.domain_head = nn.Linear(latent, max(1, n_env))

    def attack_forward(self, x_mech: torch.Tensor, grl_lambda: float = 0.0) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.mech_encoder(x_mech)
        attack_logit = self.attack_head(z).squeeze(-1)
        z_rev = GradientReverse.apply(z, grl_lambda)
        domain_logits = self.domain_head(z_rev)
        return attack_logit, domain_logits

    def conflict_forward(self, x_ctx: torch.Tensor) -> torch.Tensor:
        z = self.ctx_encoder(x_ctx)
        return self.conflict_head(z).squeeze(-1)


@dataclass
class FittedRouter:
    candidate: NeuralRouterCandidate
    mech_mean: np.ndarray
    mech_std: np.ndarray
    ctx_mean: np.ndarray
    ctx_std: np.ndarray
    model: Any
    env_mapping: dict[str, int]
    train_history: list[dict[str, Any]]

    def attack_score(self, x_mech: np.ndarray) -> np.ndarray:
        ensure_torch()
        self.model.eval()
        xt = torch.from_numpy(standardize_apply(x_mech, self.mech_mean, self.mech_std))
        with torch.no_grad():
            logits, _domain = self.model.attack_forward(xt, 0.0)
            return torch.sigmoid(logits).cpu().numpy().astype(np.float64)

    def conflict_score(self, x_ctx: np.ndarray) -> np.ndarray:
        ensure_torch()
        self.model.eval()
        xt = torch.from_numpy(standardize_apply(x_ctx, self.ctx_mean, self.ctx_std))
        with torch.no_grad():
            logits = self.model.conflict_forward(xt)
            return torch.sigmoid(logits).cpu().numpy().astype(np.float64)


def add_training_chunk(
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    label: int,
    block: str,
    exclude: tuple[str, str] | None,
    xs: list[np.ndarray],
    ys: list[np.ndarray],
    envs: list[str],
    audit: list[dict[str, Any]],
    head: str,
) -> np.ndarray:
    idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
    xs.append(frontend.matrix(role, idx, block))
    ys.append(np.full(len(idx), label, dtype=np.int64))
    envs.extend(cks.env_keys(frame_by_role[role].iloc[idx].reset_index(drop=True)))
    audit.append(
        {
            "role": role,
            "phase": phase,
            "rows": len(idx),
            "label": label,
            "block": block,
            "head": head,
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )
    return idx


def build_router_train_set(
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    conflict_include_id: bool,
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], np.ndarray, np.ndarray, list[str], list[dict[str, Any]]]:
    attack_xs: list[np.ndarray] = []
    attack_ys: list[np.ndarray] = []
    attack_envs: list[str] = []
    conflict_xs: list[np.ndarray] = []
    conflict_ys: list[np.ndarray] = []
    conflict_envs: list[str] = []
    audit: list[dict[str, Any]] = []

    support_idx = add_training_chunk(
        frontend, frame_by_role, "support_train", "fit", cko.FULL_CAP, 1, "attack_mechanism", exclude, attack_xs, attack_ys, attack_envs, audit, "attack_score"
    )
    id_idx = add_training_chunk(frontend, frame_by_role, "id_calib", "fit", train_cap, 0, "attack_mechanism", exclude, attack_xs, attack_ys, attack_envs, audit, "attack_score")
    ood_idx = add_training_chunk(frontend, frame_by_role, "ood_val", "fit", train_cap, 0, "attack_mechanism", exclude, attack_xs, attack_ys, attack_envs, audit, "attack_score")
    hard_ood_idx = add_training_chunk(frontend, frame_by_role, "ood_stress", "fit", train_cap, 0, "attack_mechanism", exclude, attack_xs, attack_ys, attack_envs, audit, "attack_score")

    # OOD-vs-attack conflict head.  ID benign is intentionally excluded from
    # this head so it does not dilute the specific OOD/attack separation signal.
    conflict_xs.append(frontend.matrix("support_train", support_idx, "conflict_context"))
    conflict_ys.append(np.zeros(len(support_idx), dtype=np.int64))
    conflict_envs.extend(cks.env_keys(frame_by_role["support_train"].iloc[support_idx].reset_index(drop=True)))
    if conflict_include_id:
        conflict_xs.append(frontend.matrix("id_calib", id_idx, "conflict_context"))
        conflict_ys.append(np.ones(len(id_idx), dtype=np.int64))
        conflict_envs.extend(cks.env_keys(frame_by_role["id_calib"].iloc[id_idx].reset_index(drop=True)))
    conflict_xs.append(frontend.matrix("ood_val", ood_idx, "conflict_context"))
    conflict_ys.append(np.ones(len(ood_idx), dtype=np.int64))
    conflict_envs.extend(cks.env_keys(frame_by_role["ood_val"].iloc[ood_idx].reset_index(drop=True)))
    conflict_xs.append(frontend.matrix("ood_stress", hard_ood_idx, "conflict_context"))
    conflict_ys.append(np.ones(len(hard_ood_idx), dtype=np.int64))
    conflict_envs.extend(cks.env_keys(frame_by_role["ood_stress"].iloc[hard_ood_idx].reset_index(drop=True)))
    audit.append(
        {
            "role": "support_train+id_calib+ood_val+ood_stress" if conflict_include_id else "support_train+ood_val+ood_stress",
            "phase": "fit",
            "rows": int(len(support_idx) + (len(id_idx) if conflict_include_id else 0) + len(ood_idx) + len(hard_ood_idx)),
            "label": "support=0,id+ood=1" if conflict_include_id else "support=0,ood=1",
            "block": "conflict_context",
            "head": "ood_vs_attack_conflict_score",
            "conflict_include_id": conflict_include_id,
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )

    return (
        np.vstack(attack_xs).astype(np.float32),
        np.concatenate(attack_ys).astype(np.int64),
        attack_envs,
        np.vstack(conflict_xs).astype(np.float32),
        np.concatenate(conflict_ys).astype(np.int64),
        conflict_envs,
        audit,
    )


def fit_neural_router(
    candidate: NeuralRouterCandidate,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[FittedRouter, list[dict[str, Any]], list[dict[str, Any]]]:
    ensure_torch()
    (
        x_attack,
        y_attack,
        attack_envs,
        x_conflict,
        y_conflict,
        conflict_envs,
        audit,
    ) = build_router_train_set(
        frontend,
        frame_by_role,
        train_cap,
        conflict_include_id=candidate.conflict_include_id,
        exclude=exclude,
    )

    env_id, env_mapping = env_to_ids(attack_envs)
    mech_mean, mech_std = standardize_fit(x_attack)
    ctx_mean, ctx_std = standardize_fit(x_conflict)
    xa = torch.from_numpy(standardize_apply(x_attack, mech_mean, mech_std))
    ya = torch.from_numpy(y_attack.astype(np.float32))
    wa = torch.from_numpy(sample_weights(y_attack))
    ea = torch.from_numpy(env_id.astype(np.int64))
    xc = torch.from_numpy(standardize_apply(x_conflict, ctx_mean, ctx_std))
    yc = torch.from_numpy(y_conflict.astype(np.float32))
    wc = torch.from_numpy(sample_weights(y_conflict))

    model = DualBranchRouter(x_attack.shape[1], x_conflict.shape[1], candidate.hidden_dim, len(env_mapping), candidate.dropout)
    opt = torch.optim.AdamW(model.parameters(), lr=candidate.lr, weight_decay=candidate.weight_decay)

    history: list[dict[str, Any]] = []
    use_domain = candidate.adv_lambda > 0.0 and len(env_mapping) > 1
    for epoch in range(1, candidate.epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        attack_logits, domain_logits = model.attack_forward(xa, candidate.adv_lambda if use_domain else 0.0)
        conflict_logits = model.conflict_forward(xc)
        attack_ce_vec = F.binary_cross_entropy_with_logits(attack_logits, ya, weight=wa, reduction="none")
        attack_loss = attack_ce_vec.mean()
        conflict_loss = F.binary_cross_entropy_with_logits(conflict_logits, yc, weight=wc, reduction="mean")

        env_risks = []
        for env_value in torch.unique(ea):
            mask = ea == env_value
            if int(mask.sum().item()) >= 4:
                env_risks.append(attack_ce_vec[mask].mean())
        if len(env_risks) >= 2:
            risks = torch.stack(env_risks)
            rex_loss = torch.var(risks, unbiased=False)
            worst_loss = torch.max(risks)
        else:
            rex_loss = torch.zeros((), dtype=torch.float32)
            worst_loss = torch.zeros((), dtype=torch.float32)

        if use_domain:
            domain_loss = F.cross_entropy(domain_logits, ea)
        else:
            domain_loss = torch.zeros((), dtype=torch.float32)

        loss = (
            attack_loss
            + conflict_loss
            + candidate.adv_lambda * domain_loss
            + candidate.rex_lambda * rex_loss
            + candidate.worst_group_lambda * worst_loss
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()

        if epoch == 1 or epoch == candidate.epochs or epoch % 10 == 0:
            with torch.no_grad():
                attack_pred = (torch.sigmoid(attack_logits) > 0.5).float()
                conflict_pred = (torch.sigmoid(conflict_logits) > 0.5).float()
            history.append(
                {
                    "candidate": candidate.name,
                    "epoch": epoch,
                    "loss": float(loss.detach().cpu().item()),
                    "attack_loss": float(attack_loss.detach().cpu().item()),
                    "conflict_loss": float(conflict_loss.detach().cpu().item()),
                    "domain_loss": float(domain_loss.detach().cpu().item()),
                    "rex_loss": float(rex_loss.detach().cpu().item()),
                    "worst_group_loss": float(worst_loss.detach().cpu().item()),
                    "attack_train_accuracy": float((attack_pred == ya).float().mean().cpu().item()),
                    "conflict_train_accuracy": float((conflict_pred == yc).float().mean().cpu().item()),
                    "attack_train_rows": int(len(y_attack)),
                    "conflict_train_rows": int(len(y_conflict)),
                    "mech_dim": int(x_attack.shape[1]),
                    "ctx_dim": int(x_conflict.shape[1]),
                    "env_classes": int(len(env_mapping)),
                    "exclude_field": exclude[0] if exclude else "",
                    "exclude_value": exclude[1] if exclude else "",
                }
            )

    env_counts = pd.Series(attack_envs, dtype="object").value_counts()
    env_rows = [
        {
            "candidate": candidate.name,
            "env_key": str(key),
            "rows": int(value),
            "mapped_id": int(env_mapping.get(str(key), env_mapping["__OTHER__"])),
            "used_for": "attack_branch_domain_adversary_and_rex_fit_only",
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
        for key, value in env_counts.items()
    ]
    fitted = FittedRouter(
        candidate=candidate,
        mech_mean=mech_mean,
        mech_std=mech_std,
        ctx_mean=ctx_mean,
        ctx_std=ctx_std,
        model=model,
        env_mapping=env_mapping,
        train_history=history,
    )
    for row in audit:
        row["candidate"] = candidate.name
        row["architecture"] = "neural_two_branch_router"
        row["adv_lambda"] = candidate.adv_lambda
        row["rex_lambda"] = candidate.rex_lambda
        row["worst_group_lambda"] = candidate.worst_group_lambda
    return fitted, audit, history + env_rows


def predict_scores(fitted: FittedRouter, frontend: cky.InteractionCausalFrontend, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    if len(idx) == 0:
        empty = np.asarray([], dtype=np.float64)
        return {
            "attack_score": empty,
            "conflict_score": empty,
            "margin_score": empty,
        }
    attack_x = frontend.matrix(role, idx, "attack_mechanism")
    ctx_x = frontend.matrix(role, idx, "conflict_context")
    attack = fitted.attack_score(attack_x)
    conflict = fitted.conflict_score(ctx_x)
    return {
        "attack_score": attack,
        "conflict_score": conflict,
        "margin_score": attack - conflict,
    }


def attack_threshold(
    fitted: FittedRouter,
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
    fitted: FittedRouter,
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
    fitted: FittedRouter,
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
    }
    return row, part


def eval_candidate(
    candidate: NeuralRouterCandidate,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    benign_q: float,
    split: str,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fitted, train_rows, history_rows = fit_neural_router(candidate, frontend, frame_by_role, train_cap, exclude=exclude)
    attack_thr = attack_threshold(fitted, frontend, frame_by_role, eval_cap, benign_q, exclude=exclude)
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    for policy in REVIEW_POLICIES:
        thr = policy_thresholds(fitted, frontend, frame_by_role, eval_cap, attack_thr, policy, exclude=exclude)
        thr["split"] = split
        thr["held_field"] = include[0] if include else ""
        thr["held_value"] = include[1] if include else ""
        threshold_rows.append(thr)
        for role, phase, kind in cko.ROLE_EVAL:
            role_include = include if split == "leave_device_family" else None
            row, _part = eval_role(
                fitted,
                frontend,
                frame_by_role,
                role,
                phase,
                kind,
                eval_cap,
                thr,
                split=split,
                include=role_include,
            )
            role_rows.append(row)
    return role_rows, threshold_rows, train_rows, history_rows


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
            }
        )
    return out


def build_readout(main_rows: list[dict[str, Any]], leave_rows: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckz neural interaction/causal evidence router v1",
        "",
        "## Scope",
        "",
        "Local smoke for CKY evidence frontend plus neural two-branch router.",
        "Attack score uses only attack_mechanism features; conflict score uses conflict_context features.",
        "Environment labels are training constraints only, not inference features.",
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
            "- This is still Gotham-internal smoke, not cross-dataset proof.",
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
        cap_rule="neural interaction-causal router capped local smoke",
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
    selected_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        rows, thrs, trains, hist = eval_candidate(
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
            rows, thrs, trains, hist = eval_candidate(
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
            train_rows.extend({"held_value": held_value, **row} for row in trains)
            history_rows.extend({"held_value": held_value, **row} for row in hist)

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
            "scope": "neural two-branch interaction/causal evidence router",
            "role_cap": args.role_cap,
            "source_cap": args.source_cap,
            "train_cap": args.train_cap,
            "eval_cap": args.eval_cap,
            "benign_q": args.benign_q,
            "candidates": [asdict(c) for c in candidates],
            "review_policies": [asdict(p) for p in REVIEW_POLICIES],
            "held_values": held_values,
            "torch_version": getattr(torch, "__version__", "missing") if torch is not None else "missing",
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "leave_family_exclusion": "held device_family excluded from fit and thresholds",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "frontend_contract": {
                "attack_score_features": "attack_mechanism only",
                "conflict_score_features": "conflict_context only",
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
    parser.add_argument("--candidates", default="Z1_neural_mech_context_router,Z2_neural_mech_context_adv_rex_router")
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
