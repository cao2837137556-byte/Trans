"""issue27ckah: family-aware invariant neural router v1.

This is the first "restart from the objective" smoke:

    low OOD hard false alarm
    high attack hard detection
    bounded review
    less source/device shortcut

It is intentionally smaller than the full CKAH idea.  The question is not yet
"can we publish the final system?" but:

* H0: with the same CKAG mechanism frontend, does a global attack head still
  bury attack families?
* H1: does a family/mechanism-aware attack head recover family coverage?
* H2: does adding source/device adversarial + REx pressure reduce shortcut
  dependence without killing attack detection?

Data contract:

* Fit: support_train/id_calib/ood_val/ood_stress fit only.
* Threshold: id_calib/ood_val/ood_stress/support_val select only.
* same_file/future/sealed roles are report-only.
* source/device are training environment labels only, never inference inputs.
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
import issue27ckac_frontend_feature_utility_audit_v1 as ckac  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27cks_neural_causal_selective_head_v1 as cks  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27ckz_neural_interaction_causal_router_v1 as ckz  # noqa: E402
import issue27ckag_attack_evidence_coverage_frontend_v1 as ckag  # noqa: E402


ISSUE = "issue27ckah_family_invariant_router_v1_2026-07-06"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"
SEED = 42

FAMILY_NAMES = ["icmp", "tcp_scan_flood", "udp_gre_flood", "transfer", "c2", "other_attack"]


@dataclass(frozen=True)
class CkahCandidate:
    name: str
    family_mode: bool
    hidden_dim: int
    epochs: int
    lr: float
    weight_decay: float
    dropout: float
    adv_lambda: float
    rex_lambda: float
    worst_group_lambda: float
    description: str
    raw_attack_top: int = 0
    raw_context_top: int = 0


@dataclass(frozen=True)
class ReviewPolicy:
    name: str
    support_review_budget: float
    description: str


CANDIDATES = [
    CkahCandidate(
        name="H0_global_mechanism_router",
        family_mode=False,
        hidden_dim=64,
        epochs=45,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="Global attack-vs-benign mechanism head using CKAG attack evidence.",
    ),
    CkahCandidate(
        name="H1_family_mechanism_router",
        family_mode=True,
        hidden_dim=80,
        epochs=55,
        lr=1e-3,
        weight_decay=1e-4,
        dropout=0.10,
        adv_lambda=0.0,
        rex_lambda=0.0,
        worst_group_lambda=0.0,
        description="Family/mechanism-aware attack heads; attack score is max over family heads.",
    ),
    CkahCandidate(
        name="H2_family_adv_rex_router",
        family_mode=True,
        hidden_dim=80,
        epochs=65,
        lr=8e-4,
        weight_decay=1.5e-4,
        dropout=0.15,
        adv_lambda=0.06,
        rex_lambda=0.12,
        worst_group_lambda=0.04,
        description="H1 plus source/device adversarial and REx/worst-environment pressure.",
    ),
    CkahCandidate(
        name="H3_family_plus_selected_raw_context",
        family_mode=True,
        hidden_dim=96,
        epochs=65,
        lr=8e-4,
        weight_decay=1.5e-4,
        dropout=0.15,
        adv_lambda=0.04,
        rex_lambda=0.08,
        worst_group_lambda=0.04,
        description="H1 plus legally selected raw115 context/conflict features; raw115 cannot directly create hard attack evidence.",
        raw_attack_top=0,
        raw_context_top=16,
    ),
    CkahCandidate(
        name="H4_family_plus_weak_raw_attack_adv",
        family_mode=True,
        hidden_dim=96,
        epochs=70,
        lr=7e-4,
        weight_decay=2e-4,
        dropout=0.18,
        adv_lambda=0.08,
        rex_lambda=0.12,
        worst_group_lambda=0.06,
        description="H3 plus a tiny audited raw115 weak-attack branch under adversarial/REx pressure.",
        raw_attack_top=8,
        raw_context_top=16,
    ),
]


POLICIES = [
    ReviewPolicy(
        name="P0_no_review",
        support_review_budget=0.0,
        description="No budgeted low-margin review; hard attack requires attack score above benign threshold and margin over conflict.",
    ),
    ReviewPolicy(
        name="P1_support_review_1pp",
        support_review_budget=0.01,
        description="Allow about 1pp support low-margin review.",
    ),
]


def ensure_torch() -> None:
    if torch is None:
        raise RuntimeError(f"PyTorch is required for CKAH; import error: {TORCH_IMPORT_ERROR}")


def set_seeds() -> None:
    np.random.seed(SEED)
    ensure_torch()
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, min(8, int(torch.get_num_threads()))))


def slug(text: Any, limit: int = 90) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:limit] or "empty"


def attack_family(label: Any) -> str:
    text = str(label).lower()
    if "icmp" in text:
        return "icmp"
    if "tcp" in text or "scan" in text:
        return "tcp_scan_flood"
    if "udp" in text or "gre" in text:
        return "udp_gre_flood"
    if "file" in text or "download" in text or "tool transfer" in text or "ingress" in text:
        return "transfer"
    if "c&c" in text or "c2" in text or "communication" in text:
        return "c2"
    return "other_attack"


def candidate_by_name(name: str) -> CkahCandidate:
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


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(x, axis=0).astype(np.float32)
    std = np.std(x, axis=0).astype(np.float32)
    std[std < 1e-6] = 1.0
    return mean, std


def standardize_apply(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.nan_to_num((np.asarray(x, dtype=np.float32) - mean) / std, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def env_to_ids(envs: list[str], max_envs: int = 32) -> tuple[np.ndarray, dict[str, int]]:
    counts = pd.Series(envs, dtype="object").value_counts()
    keep = list(counts.index[:max_envs])
    mapping = {str(key): i for i, key in enumerate(keep)}
    mapping["__OTHER__"] = len(mapping)
    ids = np.asarray([mapping.get(str(key), mapping["__OTHER__"]) for key in envs], dtype=np.int64)
    return ids, mapping


class CkahFrontend:
    """CKAG frontend plus audited raw115 sub-branches.

    CKAG attack features remain the default hard-attack evidence.  raw115 is
    selected only from legal fit/select roles and is candidate-gated:

    * raw_context_top: raw115 context/conflict evidence for the context branch.
    * raw_attack_top: tiny experimental raw115 weak-attack evidence for H4.

    This keeps H0/H1/H2 comparable and prevents raw115 from silently becoming a
    free hard-attack shortcut in every candidate.
    """

    def __init__(
        self,
        frontend: ckag.AttackEvidenceCoverageFrontend,
        x_by_role: dict[str, np.ndarray],
        frame_by_role: dict[str, pd.DataFrame],
        raw_role_cap: int,
        raw_min_group_rows: int = 12,
    ):
        self.frontend = frontend
        self.x_by_role = x_by_role
        reg = frontend.registry()
        self.registry_rows = list(reg)
        self.attack_cols = [int(row["feature_index"]) for row in reg if str(row["feature_group"]).startswith("attack_")]
        self.ctx_cols = [int(row["feature_index"]) for row in reg if not str(row["feature_group"]).startswith("attack_")]
        if not self.attack_cols:
            raise RuntimeError("CKAH frontend has no attack_* features")
        if not self.ctx_cols:
            raise RuntimeError("CKAH frontend has no context features")

        self.raw_feature_names = ckac.raw_feature_names()
        self.raw_feature_rows, self.raw_usage_rows = self._score_raw_features(frame_by_role, raw_role_cap, raw_min_group_rows)
        self.raw_attack_cols = self._select_raw_attack_cols()
        self.raw_context_cols = self._select_raw_context_cols()

    def _raw_matrix(self, role: str, idx: np.ndarray, cols: list[int]) -> np.ndarray:
        if not cols:
            return np.empty((len(idx), 0), dtype=np.float32)
        return np.asarray(self.x_by_role[role][idx][:, cols], dtype=np.float32)

    def _score_raw_features(
        self,
        frame_by_role: dict[str, pd.DataFrame],
        raw_role_cap: int,
        raw_min_group_rows: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        names = list(self.raw_feature_names)
        groups = [ckac.raw_family(name) for name in names]
        raw_space = ckac.FeatureSpace(
            name="raw115",
            feature_names=names,
            feature_groups=groups,
            matrix_fn=lambda role, idx: np.asarray(self.x_by_role[role][idx], dtype=np.float32),
            description="raw115 audited inside CKAH using only legal fit/select roles",
        )
        rows, audit = ckac.score_feature_space(raw_space, frame_by_role, int(raw_role_cap), int(raw_min_group_rows))
        for row in rows:
            shortcut = ckac.finite(row.get("max_shortcut_strength_fit"), 0.0)
            legal = ckac.finite(row.get("legal_selection_score"), -999.0)
            attack_strength = ckac.finite(row.get("strength_attack_vs_oodish_select"), 0.0)
            rec = str(row.get("recommendation", ""))
            if rec == "candidate_conflict_context":
                row["ckah_raw_branch"] = "context_candidate"
            elif legal >= 0.10 and shortcut <= 0.70 and attack_strength >= 0.20:
                row["ckah_raw_branch"] = "weak_attack_candidate_experimental"
            else:
                row["ckah_raw_branch"] = "not_selected_by_ckah"
            if (
                row["ckah_raw_branch"] == "context_candidate"
                and legal >= 0.08
                and shortcut <= 0.80
                and attack_strength >= 0.35
            ):
                row["ckah_raw_attack_probe_eligible"] = True
            else:
                row["ckah_raw_attack_probe_eligible"] = False
            row["ckah_selection_boundary"] = "support/id/ood fit plus support/id/ood select only; no query/final/sealed"
        return rows, audit

    def _select_raw_attack_cols(self, top_n: int = 16) -> list[int]:
        df = pd.DataFrame(self.raw_feature_rows)
        if df.empty:
            return []
        part = df[df["ckah_raw_branch"] == "weak_attack_candidate_experimental"].copy()
        if part.empty:
            # Conservative fallback for H4 only: these are still high-risk raw115
            # features, usually classified as context because shortcut is visible.
            # We allow a tiny probe branch under adversarial/REx pressure so the
            # experiment can answer whether selected raw115 helps attack coverage
            # without silently promoting it as clean hard-attack evidence.
            part = df[df["ckah_raw_attack_probe_eligible"].astype(bool)].copy()
        if part.empty:
            return []
        part["_score"] = pd.to_numeric(part["legal_selection_score"], errors="coerce").fillna(-999.0)
        part["_strength"] = pd.to_numeric(part["strength_attack_vs_oodish_select"], errors="coerce").fillna(0.0)
        part = part.sort_values(["_score", "_strength"], ascending=False).head(int(top_n))
        return [int(v) for v in part["feature_index"].tolist()]

    def _select_raw_context_cols(self, top_n: int = 32) -> list[int]:
        df = pd.DataFrame(self.raw_feature_rows)
        if df.empty:
            return []
        part = df[df["ckah_raw_branch"] == "context_candidate"].copy()
        if part.empty:
            return []
        part["_shortcut"] = pd.to_numeric(part["max_shortcut_strength_fit"], errors="coerce").fillna(0.0)
        part["_id_ood"] = pd.to_numeric(part["strength_id_vs_oodish_fit"], errors="coerce").fillna(0.0)
        part["_legal"] = pd.to_numeric(part["legal_selection_score"], errors="coerce").fillna(-999.0)
        part = part.sort_values(["_shortcut", "_id_ood", "_legal"], ascending=False).head(int(top_n))
        return [int(v) for v in part["feature_index"].tolist()]

    def matrix(self, role: str, idx: np.ndarray, block: str, candidate: CkahCandidate | None = None) -> np.ndarray:
        full = self.frontend.matrix(role, idx)
        if block == "attack":
            parts = [np.asarray(full[:, self.attack_cols], dtype=np.float32)]
            if candidate is not None and int(candidate.raw_attack_top) > 0:
                parts.append(self._raw_matrix(role, idx, self.raw_attack_cols[: int(candidate.raw_attack_top)]))
            return np.hstack(parts).astype(np.float32)
        if block == "context":
            parts = [np.asarray(full[:, self.ctx_cols], dtype=np.float32)]
            if candidate is not None and int(candidate.raw_context_top) > 0:
                parts.append(self._raw_matrix(role, idx, self.raw_context_cols[: int(candidate.raw_context_top)]))
            return np.hstack(parts).astype(np.float32)
        if block == "full":
            return np.asarray(full, dtype=np.float32)
        raise ValueError(block)

    def registry(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self.registry_rows:
            row2 = dict(row)
            row2["ckah_branch"] = "attack" if int(row2["feature_index"]) in set(self.attack_cols) else "context"
            rows.append(row2)
        raw_attack_set = set(self.raw_attack_cols)
        raw_context_set = set(self.raw_context_cols)
        for row in self.raw_feature_rows:
            idx = int(row["feature_index"])
            if idx not in raw_attack_set and idx not in raw_context_set:
                continue
            row2 = dict(row)
            row2["feature_space"] = "raw115"
            row2["ckah_branch"] = (
                "raw_attack_experimental" if idx in raw_attack_set else "raw_context"
            )
            rows.append(row2)
        return rows


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
        latent = max(16, hidden_dim // 2)
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, latent),
            nn.LayerNorm(latent),
            nn.ReLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class FamilyInvariantRouter(nn.Module):  # type: ignore[misc]
    def __init__(self, attack_dim: int, ctx_dim: int, hidden_dim: int, n_family: int, n_env: int, dropout: float):
        super().__init__()
        self.attack_encoder = BranchEncoder(attack_dim, hidden_dim, dropout)
        self.ctx_encoder = BranchEncoder(ctx_dim, hidden_dim, dropout)
        latent = max(16, hidden_dim // 2)
        self.family_heads = nn.Linear(latent, n_family)
        self.conflict_head = nn.Linear(latent, 1)
        self.domain_head = nn.Linear(latent, max(1, n_env))

    def attack_forward(self, x: torch.Tensor, grl_lambda: float = 0.0) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        z = self.attack_encoder(x)
        family_logits = self.family_heads(z)
        z_rev = GradientReverse.apply(z, grl_lambda)
        domain_logits = self.domain_head(z_rev)
        return family_logits, domain_logits, z

    def conflict_forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.ctx_encoder(x)
        return self.conflict_head(z).squeeze(-1)


@dataclass
class FittedCkah:
    candidate: CkahCandidate
    family_names: list[str]
    attack_mean: np.ndarray
    attack_std: np.ndarray
    ctx_mean: np.ndarray
    ctx_std: np.ndarray
    model: Any
    env_mapping: dict[str, int]
    train_history: list[dict[str, Any]]

    def family_scores(self, x_attack: np.ndarray) -> np.ndarray:
        ensure_torch()
        self.model.eval()
        xt = torch.from_numpy(standardize_apply(x_attack, self.attack_mean, self.attack_std))
        with torch.no_grad():
            logits, _domain, _z = self.model.attack_forward(xt, 0.0)
            return torch.sigmoid(logits).cpu().numpy().astype(np.float64)

    def conflict_score(self, x_ctx: np.ndarray) -> np.ndarray:
        ensure_torch()
        self.model.eval()
        xt = torch.from_numpy(standardize_apply(x_ctx, self.ctx_mean, self.ctx_std))
        with torch.no_grad():
            logits = self.model.conflict_forward(xt)
            return torch.sigmoid(logits).cpu().numpy().astype(np.float64)


def add_attack_chunk(
    candidate: CkahCandidate,
    frontend: CkahFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    is_attack: bool,
    family_names: list[str],
    exclude: tuple[str, str] | None,
    xs: list[np.ndarray],
    ys: list[np.ndarray],
    envs: list[str],
    audit: list[dict[str, Any]],
) -> np.ndarray:
    idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
    xs.append(frontend.matrix(role, idx, "attack", candidate))
    target = np.zeros((len(idx), len(family_names)), dtype=np.float32)
    if is_attack and len(idx):
        labels = frame_by_role[role].iloc[idx].reset_index(drop=True).get("attack_label", pd.Series(["unknown"] * len(idx))).astype(str)
        for i, label in enumerate(labels):
            family = attack_family(label)
            if len(family_names) == 1:
                target[i, 0] = 1.0
            elif family in family_names:
                target[i, family_names.index(family)] = 1.0
            else:
                target[i, family_names.index("other_attack")] = 1.0
    ys.append(target)
    envs.extend(cks.env_keys(frame_by_role[role].iloc[idx].reset_index(drop=True)))
    audit.append(
        {
            "role": role,
            "phase": phase,
            "rows": int(len(idx)),
            "head": "family_attack_heads",
            "target": "attack_family_onehot" if is_attack else "all_family_zero",
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )
    return idx


def add_context_chunk(
    candidate: CkahCandidate,
    frontend: CkahFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    label: int,
    exclude: tuple[str, str] | None,
    xs: list[np.ndarray],
    ys: list[np.ndarray],
    audit: list[dict[str, Any]],
) -> np.ndarray:
    idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
    xs.append(frontend.matrix(role, idx, "context", candidate))
    ys.append(np.full(len(idx), int(label), dtype=np.float32))
    audit.append(
        {
            "role": role,
            "phase": phase,
            "rows": int(len(idx)),
            "head": "context_conflict_head",
            "target": label,
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )
    return idx


def build_train_set(
    candidate: CkahCandidate,
    frontend: CkahFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], np.ndarray, np.ndarray, list[dict[str, Any]], list[str]]:
    family_names = ["attack_any"] if not candidate.family_mode else list(FAMILY_NAMES)
    attack_xs: list[np.ndarray] = []
    attack_ys: list[np.ndarray] = []
    attack_envs: list[str] = []
    ctx_xs: list[np.ndarray] = []
    ctx_ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    support_idx = add_attack_chunk(candidate, frontend, frame_by_role, "support_train", "fit", cko.FULL_CAP, True, family_names, exclude, attack_xs, attack_ys, attack_envs, audit)
    id_idx = add_attack_chunk(candidate, frontend, frame_by_role, "id_calib", "fit", train_cap, False, family_names, exclude, attack_xs, attack_ys, attack_envs, audit)
    ood_idx = add_attack_chunk(candidate, frontend, frame_by_role, "ood_val", "fit", train_cap, False, family_names, exclude, attack_xs, attack_ys, attack_envs, audit)
    hard_idx = add_attack_chunk(candidate, frontend, frame_by_role, "ood_stress", "fit", train_cap, False, family_names, exclude, attack_xs, attack_ys, attack_envs, audit)

    add_context_chunk(candidate, frontend, frame_by_role, "support_train", "fit", cko.FULL_CAP, 0, exclude, ctx_xs, ctx_ys, audit)
    add_context_chunk(candidate, frontend, frame_by_role, "id_calib", "fit", train_cap, 1, exclude, ctx_xs, ctx_ys, audit)
    add_context_chunk(candidate, frontend, frame_by_role, "ood_val", "fit", train_cap, 1, exclude, ctx_xs, ctx_ys, audit)
    add_context_chunk(candidate, frontend, frame_by_role, "ood_stress", "fit", train_cap, 1, exclude, ctx_xs, ctx_ys, audit)

    audit.append(
        {
            "role": "feature_contract",
            "phase": "audit",
            "rows": int(len(support_idx) + len(id_idx) + len(ood_idx) + len(hard_idx)),
            "head": "candidate_specific_feature_dims",
            "target": "",
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
            "attack_feature_dim": int(sum(x.shape[1] for x in attack_xs[:1])),
            "context_feature_dim": int(sum(x.shape[1] for x in ctx_xs[:1])),
            "raw_attack_top": int(candidate.raw_attack_top),
            "raw_context_top": int(candidate.raw_context_top),
        }
    )

    return (
        np.vstack(attack_xs).astype(np.float32),
        np.vstack(attack_ys).astype(np.float32),
        attack_envs,
        np.vstack(ctx_xs).astype(np.float32),
        np.concatenate(ctx_ys).astype(np.float32),
        audit,
        family_names,
    )


def bce_family_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    pos = target.sum(dim=0)
    neg = target.shape[0] - pos
    pos_weight = torch.clamp(neg / torch.clamp(pos, min=1.0), min=1.0, max=20.0)
    return F.binary_cross_entropy_with_logits(logits, target, pos_weight=pos_weight, reduction="mean")


def sample_weights_binary(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.int64)
    counts = np.bincount(y, minlength=2).astype(np.float64)
    total = float(np.sum(counts))
    weights = np.zeros(2, dtype=np.float32)
    for label in range(2):
        weights[label] = float(total / max(1.0, counts[label]))
    weights /= max(1e-12, float(np.mean(weights[weights > 0])))
    return weights[y].astype(np.float32)


def fit_candidate(
    candidate: CkahCandidate,
    frontend: CkahFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[FittedCkah, list[dict[str, Any]], list[dict[str, Any]]]:
    ensure_torch()
    x_attack, y_family, attack_envs, x_ctx, y_ctx, audit, family_names = build_train_set(candidate, frontend, frame_by_role, train_cap, exclude=exclude)
    y_global = (np.sum(y_family, axis=1) > 0).astype(np.float32)
    env_id, env_mapping = env_to_ids(attack_envs)
    attack_mean, attack_std = standardize_fit(x_attack)
    ctx_mean, ctx_std = standardize_fit(x_ctx)

    xa = torch.from_numpy(standardize_apply(x_attack, attack_mean, attack_std))
    yf = torch.from_numpy(y_family.astype(np.float32))
    yg = torch.from_numpy(y_global.astype(np.float32))
    ea = torch.from_numpy(env_id.astype(np.int64))
    xc = torch.from_numpy(standardize_apply(x_ctx, ctx_mean, ctx_std))
    yc = torch.from_numpy(y_ctx.astype(np.float32))
    wc = torch.from_numpy(sample_weights_binary(y_ctx.astype(np.int64)))

    model = FamilyInvariantRouter(x_attack.shape[1], x_ctx.shape[1], candidate.hidden_dim, len(family_names), len(env_mapping), candidate.dropout)
    opt = torch.optim.AdamW(model.parameters(), lr=candidate.lr, weight_decay=candidate.weight_decay)
    history: list[dict[str, Any]] = []
    use_domain = candidate.adv_lambda > 0.0 and len(env_mapping) > 1
    for epoch in range(1, candidate.epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        family_logits, domain_logits, _z = model.attack_forward(xa, candidate.adv_lambda if use_domain else 0.0)
        conflict_logits = model.conflict_forward(xc)
        global_logits = torch.logsumexp(family_logits, dim=1)
        family_loss = bce_family_loss(family_logits, yf)
        global_vec = F.binary_cross_entropy_with_logits(global_logits, yg, reduction="none")
        global_loss = global_vec.mean()
        conflict_loss = F.binary_cross_entropy_with_logits(conflict_logits, yc, weight=wc, reduction="mean")

        env_risks = []
        for env_value in torch.unique(ea):
            mask = ea == env_value
            if int(mask.sum().item()) >= 4:
                env_risks.append(global_vec[mask].mean())
        if len(env_risks) >= 2:
            risks = torch.stack(env_risks)
            rex_loss = torch.var(risks, unbiased=False)
            worst_loss = torch.max(risks)
        else:
            rex_loss = torch.zeros((), dtype=torch.float32)
            worst_loss = torch.zeros((), dtype=torch.float32)
        domain_loss = F.cross_entropy(domain_logits, ea) if use_domain else torch.zeros((), dtype=torch.float32)
        loss = family_loss + 0.50 * global_loss + conflict_loss + candidate.adv_lambda * domain_loss + candidate.rex_lambda * rex_loss + candidate.worst_group_lambda * worst_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()
        if epoch == 1 or epoch == candidate.epochs or epoch % 10 == 0:
            with torch.no_grad():
                fam_prob = torch.sigmoid(family_logits)
                attack_pred = (torch.max(fam_prob, dim=1).values > 0.5).float()
                conflict_pred = (torch.sigmoid(conflict_logits) > 0.5).float()
            history.append(
                {
                    "candidate": candidate.name,
                    "epoch": int(epoch),
                    "loss": float(loss.detach().cpu().item()),
                    "family_loss": float(family_loss.detach().cpu().item()),
                    "global_loss": float(global_loss.detach().cpu().item()),
                    "conflict_loss": float(conflict_loss.detach().cpu().item()),
                    "domain_loss": float(domain_loss.detach().cpu().item()),
                    "rex_loss": float(rex_loss.detach().cpu().item()),
                    "worst_group_loss": float(worst_loss.detach().cpu().item()),
                    "attack_train_accuracy": float((attack_pred == yg).float().mean().cpu().item()),
                    "conflict_train_accuracy": float((conflict_pred == yc).float().mean().cpu().item()),
                    "attack_rows": int(len(y_global)),
                    "context_rows": int(len(y_ctx)),
                    "attack_dim": int(x_attack.shape[1]),
                    "context_dim": int(x_ctx.shape[1]),
                    "family_heads": int(len(family_names)),
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
    for row in audit:
        row["candidate"] = candidate.name
        row["family_mode"] = bool(candidate.family_mode)
        row["adv_lambda"] = float(candidate.adv_lambda)
        row["rex_lambda"] = float(candidate.rex_lambda)
        row["worst_group_lambda"] = float(candidate.worst_group_lambda)
    fitted = FittedCkah(
        candidate=candidate,
        family_names=family_names,
        attack_mean=attack_mean,
        attack_std=attack_std,
        ctx_mean=ctx_mean,
        ctx_std=ctx_std,
        model=model,
        env_mapping=env_mapping,
        train_history=history,
    )
    return fitted, audit, history + env_rows


def predict_scores(fitted: FittedCkah, frontend: CkahFrontend, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    if len(idx) == 0:
        empty = np.asarray([], dtype=np.float64)
        return {"attack_score": empty, "conflict_score": empty, "margin_score": empty}
    fam = fitted.family_scores(frontend.matrix(role, idx, "attack", fitted.candidate))
    conflict = fitted.conflict_score(frontend.matrix(role, idx, "context", fitted.candidate))
    attack = np.max(fam, axis=1)
    out: dict[str, np.ndarray] = {
        "attack_score": attack.astype(np.float64),
        "conflict_score": conflict.astype(np.float64),
        "margin_score": (attack - conflict).astype(np.float64),
    }
    for j, name in enumerate(fitted.family_names):
        out[f"family_score_{name}"] = fam[:, j].astype(np.float64)
    return out


def attack_threshold(
    fitted: FittedCkah,
    frontend: CkahFrontend,
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


def policy_threshold(
    fitted: FittedCkah,
    frontend: CkahFrontend,
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
    margin_thr = 0.0 if policy.support_review_budget <= 0.0 or len(margins) == 0 else max(0.0, float(np.quantile(margins, policy.support_review_budget)))
    suppress = raw & (score["margin_score"] <= 0.0)
    review = raw & (score["margin_score"] > 0.0) & (score["margin_score"] <= margin_thr)
    hard = raw & (~suppress) & (~review)
    return {
        "candidate": fitted.candidate.name,
        "policy": policy.name,
        "support_review_budget": float(policy.support_review_budget),
        "attack_threshold": float(attack_thr),
        "margin_review_threshold": float(margin_thr),
        "support_rows": int(len(idx)),
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
    fitted: FittedCkah,
    frontend: CkahFrontend,
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
        "rows": int(len(idx)),
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
    for name in fitted.family_names:
        key = f"family_score_{name}"
        row[f"{key}_mean"] = float(np.mean(score[key])) if key in score and len(idx) else float("nan")
    return row, part


def eval_candidate(
    candidate: CkahCandidate,
    frontend: CkahFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    benign_q: float,
    policies: list[ReviewPolicy],
    split: str,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[pd.DataFrame]]:
    fitted, train_rows, history_rows = fit_candidate(candidate, frontend, frame_by_role, train_cap, exclude=exclude)
    attack_thr = attack_threshold(fitted, frontend, frame_by_role, eval_cap, benign_q, exclude=exclude)
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    parts: list[pd.DataFrame] = []
    for policy in policies:
        thr = policy_threshold(fitted, frontend, frame_by_role, eval_cap, attack_thr, policy, exclude=exclude)
        thr["split"] = split
        thr["held_field"] = include[0] if include else ""
        thr["held_value"] = include[1] if include else ""
        threshold_rows.append(thr)
        for role, phase, kind in cko.ROLE_EVAL:
            role_include = include if split == "leave_device_family" else None
            row, part = eval_role(fitted, frontend, frame_by_role, role, phase, kind, eval_cap, thr, split=split, include=role_include)
            role_rows.append(row)
            part["candidate"] = candidate.name
            part["policy"] = policy.name
            part["split"] = split
            part["role"] = role
            part["phase_eval"] = phase
            part["role_kind"] = kind
            part["held_value"] = include[1] if include else ""
            parts.append(part)
    return role_rows, threshold_rows, train_rows, history_rows, parts


def rate(values: Any) -> float:
    arr = np.asarray(values, dtype=bool)
    return float(np.mean(arr)) if len(arr) else float("nan")


def attack_family_summary(parts: list[pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not parts:
        return rows
    df = pd.concat(parts, ignore_index=True)
    attack_roles = {"support_val", "same_file_query", "future_query", "sealed_final_attack"}
    df = df[df["role"].isin(attack_roles)].copy()
    if df.empty or "attack_label" not in df:
        return rows
    df["attack_family"] = df["attack_label"].map(attack_family)
    for (candidate, policy, split, held, role, label, fam), part in df.groupby(
        ["candidate", "policy", "split", "held_value", "role", "attack_label", "attack_family"], dropna=False, sort=True
    ):
        rows.append(
            {
                "candidate": candidate,
                "policy": policy,
                "split": split,
                "held_value": held,
                "role": role,
                "attack_label": label,
                "attack_family": fam,
                "rows": int(len(part)),
                "raw_alarm_rate": rate(part["raw_alarm"]),
                "hard_alarm_rate": rate(part["hard_alarm"]),
                "review_rate": rate(part["review"]),
                "suppress_rate": rate(part["suppress"]),
                "attack_score_mean": float(pd.to_numeric(part["attack_score"], errors="coerce").mean()),
                "conflict_score_mean": float(pd.to_numeric(part["conflict_score"], errors="coerce").mean()),
                "margin_score_mean": float(pd.to_numeric(part["margin_score"], errors="coerce").mean()),
            }
        )
    return rows


def pick(rows: list[dict[str, Any]], split: str, candidate: str, policy: str, role: str, metric: str, held_value: str = "") -> float:
    for row in rows:
        if row["split"] == split and row["candidate"] == candidate and row["policy"] == policy and row["role"] == role and str(row.get("held_value", "")) == held_value:
            return float(row.get(metric, float("nan")))
    return float("nan")


def main_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(r["candidate"], r["policy"]) for r in role_rows if r["split"] == "main"})
    out: list[dict[str, Any]] = []
    for candidate, policy in keys:
        out.append(
            {
                "candidate": candidate,
                "policy": policy,
                "support_hard": pick(role_rows, "main", candidate, policy, "support_val", "hard_alarm_rate"),
                "same_file_hard": pick(role_rows, "main", candidate, policy, "same_file_query", "hard_alarm_rate"),
                "same_file_review": pick(role_rows, "main", candidate, policy, "same_file_query", "review_rate"),
                "future_hard": pick(role_rows, "main", candidate, policy, "future_query", "hard_alarm_rate"),
                "future_review": pick(role_rows, "main", candidate, policy, "future_query", "review_rate"),
                "sealed_attack_hard": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_review": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "review_rate"),
                "sealed_ood_hard": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_review": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "review_rate"),
                "ood_stress_hard": pick(role_rows, "main", candidate, policy, "ood_stress", "hard_alarm_rate"),
                "ood_stress_review": pick(role_rows, "main", candidate, policy, "ood_stress", "review_rate"),
            }
        )
    return out


def leave_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
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
        for row in role_rows
        if row["split"] == "leave_device_family" and row["role"] in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack", "same_file_query"}
    ]


def build_readout(main_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], leave_rows: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckah family-aware invariant neural router v1",
        "",
        "## Scope",
        "",
        "Minimal CKAH-v1 smoke: H0 global mechanism head, H1 family-aware mechanism heads, H2 family-aware + adversarial/REx shortcut pressure.",
        "",
        "## Main roles",
        "",
        "| candidate | policy | support | same-file h/r | future h/r | sealed attack h/r | sealed OOD h/r | OOD-stress h/r |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in main_rows:
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {cko.fmt(row['support_hard'])} | "
            f"{cko.fmt(row['same_file_hard'])}/{cko.fmt(row['same_file_review'])} | "
            f"{cko.fmt(row['future_hard'])}/{cko.fmt(row['future_review'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Per attack-family report-only snapshot",
            "",
            "| candidate | policy | role | label | family | rows | hard | review | attack/conflict/margin |",
            "|---|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in family_rows:
        if row["split"] != "main" or row["role"] not in {"same_file_query", "future_query", "sealed_final_attack", "support_val"}:
            continue
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {row['role']} | {row['attack_label']} | {row['attack_family']} | "
            f"{row['rows']} | {cko.fmt(row['hard_alarm_rate'])} | {cko.fmt(row['review_rate'])} | "
            f"{cko.fmt(row['attack_score_mean'])}/{cko.fmt(row['conflict_score_mean'])}/{cko.fmt(row['margin_score_mean'])} |"
        )
        if len(lines) > 80:
            break
    if leave_rows:
        lines.extend(
            [
                "",
                "## Leave-device-family stress",
                "",
                "| candidate | policy | held | role | rows | hard | review | attack/conflict/margin |",
                "|---|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in leave_rows:
            if int(row["rows"]) == 0:
                continue
            lines.append(
                f"| {row['candidate']} | {row['policy']} | {row['held_value']} | {row['role']} | {row['rows']} | "
                f"{cko.fmt(row['hard_alarm_rate'])} | {cko.fmt(row['review_rate'])} | "
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
            "- Query/future/sealed rows are report-only.",
            "- source/device are used only as training environment constraints, not inference features.",
            "- This is a local smoke, not a final benchmark or cross-dataset proof.",
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
    role_cap_rows: list[dict[str, Any]] = []
    if int(args.source_cap) > 0:
        x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            int(args.role_cap),
            int(args.source_cap),
            cap_rule="ckah family-invariant capped local smoke",
        )
    ckt.add_family_columns(frame_by_role)
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    ckag_front = ckag.AttackEvidenceCoverageFrontend(builder)
    _ = ckag_front.matrix("support_train", np.asarray([0], dtype=np.int64))
    frontend = CkahFrontend(ckag_front, x_by_role, frame_by_role, int(args.role_cap), int(args.raw_min_group_rows))

    candidates = [candidate_by_name(item.strip()) for item in str(args.candidates).split(",") if item.strip()]
    held_values = [item.strip() for item in str(args.held_values).split(",") if item.strip()]
    policies = [p for p in POLICIES if p.name in {item.strip() for item in str(args.policies).split(",") if item.strip()}]

    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    part_frames: list[pd.DataFrame] = []
    selected_leave_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        rows, thrs, trains, hist, parts = eval_candidate(
            candidate,
            frontend,
            frame_by_role,
            int(args.train_cap),
            int(args.eval_cap),
            float(args.benign_q),
            policies,
            split="main",
        )
        role_rows.extend(rows)
        threshold_rows.extend(thrs)
        train_rows.extend(trains)
        history_rows.extend(hist)
        part_frames.extend(parts)

    if bool(args.run_leave):
        for held_value in held_values:
            counts = {
                "ood_val": ckt.rows_for(frame_by_role, "ood_val", "select", "device_family", held_value, int(args.eval_cap)),
                "ood_stress": ckt.rows_for(frame_by_role, "ood_stress", "select", "device_family", held_value, int(args.eval_cap)),
                "sealed_final_ood": ckt.rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", held_value, int(args.eval_cap)),
                "same_file_query": ckt.rows_for(frame_by_role, "same_file_query", "select", "device_family", held_value, int(args.eval_cap)),
                "future_query": ckt.rows_for(frame_by_role, "future_query", "select", "device_family", held_value, int(args.eval_cap)),
                "sealed_final_attack": ckt.rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", held_value, int(args.eval_cap)),
            }
            selected_leave_rows.append({"held_field": "device_family", "held_value": held_value, "total_eval_rows": sum(counts.values()), **counts})
            for candidate in candidates:
                rows, thrs, trains, hist, parts = eval_candidate(
                    candidate,
                    frontend,
                    frame_by_role,
                    int(args.train_cap),
                    int(args.eval_cap),
                    float(args.benign_q),
                    policies,
                    split="leave_device_family",
                    include=("device_family", held_value),
                    exclude=("device_family", held_value),
                )
                role_rows.extend(rows)
                threshold_rows.extend(thrs)
                train_rows.extend({"held_value": held_value, **row} for row in trains)
                history_rows.extend({"held_value": held_value, **row} for row in hist)
                part_frames.extend(parts)

    main_rows = main_summary(role_rows)
    family_rows = attack_family_summary(part_frames)
    leave_rows = leave_summary(role_rows)
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(out / "main_summary_matrix.csv", main_rows)
    cko.write_csv(out / "attack_family_summary.csv", family_rows)
    cko.write_csv(out / "leave_device_family_summary_matrix.csv", leave_rows)
    cko.write_csv(out / "role_metrics.csv", role_rows)
    cko.write_csv(out / "threshold_policy_audit.csv", threshold_rows)
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "train_history_and_env_audit.csv", history_rows)
    cko.write_csv(out / "frontend_registry.csv", frontend.registry())
    cko.write_csv(out / "raw_feature_selection_audit.csv", frontend.raw_feature_rows)
    cko.write_csv(out / "raw_feature_role_usage_audit.csv", frontend.raw_usage_rows)
    cko.write_csv(out / "selected_leave_groups.csv", selected_leave_rows)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "alignment_audit.csv", alignment_rows)
    cko.write_md(out / "codex_readout.md", build_readout(main_rows, family_rows, leave_rows, threshold_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "role_cap": int(args.role_cap),
            "source_cap": int(args.source_cap),
            "train_cap": int(args.train_cap),
            "eval_cap": int(args.eval_cap),
            "benign_q": float(args.benign_q),
            "candidates": [asdict(c) for c in candidates],
            "policies": [asdict(p) for p in policies],
            "run_leave": bool(args.run_leave),
            "held_values": held_values,
            "torch_version": getattr(torch, "__version__", "missing") if torch is not None else "missing",
            "family_names": FAMILY_NAMES,
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "query_future_sealed_used_for_training_or_thresholding": False,
                "source_device_inference_features": False,
            },
            "frontend_contract": {
                "frontend": "CKAG coverage-expanded mechanism frontend",
                "attack_branch": "candidate-gated CKAG attack_* plus optional audited raw115 weak attack features",
                "context_branch": "CKAG conflict/context plus optional audited raw115 context features",
                "raw115_direct_attack": "only H4 experimental raw_attack_top; H0-H3 keep raw115 out of hard attack evidence",
                "raw_feature_selection": "computed inside this run from legal fit/select roles only",
                "raw_attack_cols": frontend.raw_attack_cols,
                "raw_context_cols": frontend.raw_context_cols,
            },
            "input_audit": input_audit,
            "alignment_rows": len(alignment_rows),
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=512)
    parser.add_argument("--source-cap", type=int, default=0)
    parser.add_argument("--train-cap", type=int, default=384)
    parser.add_argument("--eval-cap", type=int, default=512)
    parser.add_argument("--benign-q", type=float, default=0.99)
    parser.add_argument("--raw-min-group-rows", type=int, default=12)
    parser.add_argument("--candidates", default="H0_global_mechanism_router,H1_family_mechanism_router,H2_family_adv_rex_router,H3_family_plus_selected_raw_context,H4_family_plus_weak_raw_attack_adv")
    parser.add_argument("--policies", default="P0_no_review")
    parser.add_argument("--run-leave", action="store_true")
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
