"""issue27ckar: pseudo-held OOD episode gate local smoke.

This route is a targeted follow-up after three Level-2 canaries:

* CKAO: C1 CICFlow-style frontend helps some held families, but the two old
  held OOD failures (stream-consumer / hydraulic-system) remain attack-like.
* CKAP: a plain MLP + class prototype/SupCon/REx did not pull those held OOD
  families out of the attack region.
* CKAQ: a strict attack-support distance gate either did not help, or turned
  the problem into review / attack rejection.

The new hypothesis is narrower:

    Train the backend to rehearse "unseen OOD family" pressure inside the
    legal fit split, instead of hoping a normal class head learns it.

Boundary
--------
For each true held device_family:

* support_train / id_calib / ood_val / ood_stress fit rows exclude the true
  held family;
* id_calib / ood_val / ood_stress / support_val select rows exclude the true
  held family for thresholds;
* evaluation rows include only the true held family;
* future/query/sealed rows are report-only;
* source/device/family fields are used only for grouping, audits, and
  pseudo-held training episodes, never as inference features.

Routes
------
P0_C1_ce_margin:
    C1 frontend + MLP CE + probability-margin decision. Control.
P1_C1_episode_margin:
    P0 + worst OOD-family attack penalty on legal non-held fit rows.
P2_M1_episode_margin:
    P1 with all external blocks (graph + Zeek + NetFlow + CICFlow) to add
    OOD/context evidence. This tests whether the missing signal is frontend
    context, not only backend.
P3_M1_episode_selective:
    Same score as P2, but reports the would-be review burden for raw-attack
    / margin-conflict samples. This is a diagnostic; high review is not a win.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckar_pseudoheld_ood_episode_gate_v1_2026-07-09"
OUT_BASE = cko.ROOT / "runs" / ISSUE
SEED = 27
DEVICE = torch.device("cpu")

NON_ATTACK = [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD]

LABEL_NAMES = {
    ckh.CLASS_ID: "id",
    ckh.CLASS_OOD: "ood",
    ckh.CLASS_HARD_OOD: "hard_ood",
    ckh.CLASS_ATTACK: "attack",
}


@dataclass(frozen=True)
class Route:
    name: str
    candidate_name: str
    episode_loss: bool
    selective: bool
    description: str


ROUTES = [
    Route(
        "P0_C1_ce_margin",
        "C1_cicflow_style_only_histgb",
        episode_loss=False,
        selective=False,
        description="C1 frontend + MLP CE + probability-margin decision control.",
    ),
    Route(
        "P1_C1_episode_margin",
        "C1_cicflow_style_only_histgb",
        episode_loss=True,
        selective=False,
        description="C1 + worst OOD-family attack penalty on legal non-held fit rows.",
    ),
    Route(
        "P2_M1_episode_margin",
        "M1_all_external_blocks_histgb",
        episode_loss=True,
        selective=False,
        description="All external blocks + pseudo-held OOD family penalty.",
    ),
    Route(
        "P3_M1_episode_selective",
        "M1_all_external_blocks_histgb",
        episode_loss=True,
        selective=True,
        description="P2 diagnostic with raw-attack/margin-conflict review accounting.",
    ),
    Route(
        "P4_REL_episode_margin",
        "__RELATIVE_DELTA_EXTERNAL__",
        episode_loss=True,
        selective=False,
        description="Relative frontend: current semantics + w16-w128 deltas/absolute deltas/short-long ratios.",
    ),
    Route(
        "P5_REL_episode_selective",
        "__RELATIVE_DELTA_EXTERNAL__",
        episode_loss=True,
        selective=True,
        description="P4 diagnostic with raw-attack/margin-conflict review accounting.",
    ),
]

RELATIVE_CANDIDATE = "__RELATIVE_DELTA_EXTERNAL__"


class TinyEpisodeHead(nn.Module):
    def __init__(self, in_dim: int, hidden: int = 128, emb_dim: int = 48, classes: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.LayerNorm(hidden),
            nn.ReLU(),
            nn.Dropout(0.08),
            nn.Linear(hidden, emb_dim),
            nn.LayerNorm(emb_dim),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(emb_dim, classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.net(x))


def set_seeds(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))


def candidate_by_name(name: str) -> ckai.Candidate:
    for candidate in ckai.CANDIDATES:
        if candidate.name == name:
            return candidate
    raise RuntimeError(f"candidate not found: {name}")


def relative_delta_matrix(frontend: ckai.ExternalFlowFrontend, role: str, idx: np.ndarray) -> np.ndarray:
    """Build a compact context-relative frontend from CKAI external features.

    We keep current per-flow protocol semantics, the explicitly engineered
    short/long ratios, and add w16-w128 signed/absolute deltas for matching
    window statistics.  The intent is to reduce absolute device-style shortcut
    and emphasize "changed relative to recent context" evidence.
    """
    ext = frontend.external_matrix(role, idx)
    names = list(ckai.FEATURE_NAMES)
    name_to_i = {name: i for i, name in enumerate(names)}

    keep: list[np.ndarray] = []
    # Current protocol/flag/port semantics.
    cur_cols = [i for i, name in enumerate(names) if name.startswith("cur_")]
    if cur_cols:
        keep.append(ext[:, cur_cols])
    # Explicit short-long ratios already generated by CKAI.
    ratio_cols = [i for i, name in enumerate(names) if "short_long_ratio" in name]
    if ratio_cols:
        keep.append(ext[:, ratio_cols])

    deltas: list[np.ndarray] = []
    for name, i16 in name_to_i.items():
        if "_w16_" not in name and not name.endswith("_w16"):
            continue
        name128 = name.replace("_w16_", "_w128_")
        if name128 == name:
            name128 = name.removesuffix("_w16") + "_w128"
        if name128 not in name_to_i:
            continue
        diff = ext[:, [i16]] - ext[:, [name_to_i[name128]]]
        deltas.append(diff)
        deltas.append(np.abs(diff))
    if deltas:
        keep.append(np.hstack(deltas))
    if not keep:
        raise RuntimeError("relative_delta_matrix found no usable features")
    return np.nan_to_num(np.hstack(keep), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = np.mean(x, axis=0, keepdims=True)
    sig = np.std(x, axis=0, keepdims=True)
    sig = np.where(sig < 1e-6, 1.0, sig)
    return mu.astype(np.float32), sig.astype(np.float32)


def standardize_apply(x: np.ndarray, mu: np.ndarray, sig: np.ndarray) -> np.ndarray:
    return np.nan_to_num((np.asarray(x, dtype=np.float32) - mu) / sig, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def class_weights(y: np.ndarray) -> torch.Tensor:
    counts = np.asarray([max(1, int(np.sum(y == label))) for label in range(4)], dtype=np.float32)
    weights = 1.0 / counts
    weights = weights * (len(weights) / max(1e-6, float(np.sum(weights))))
    return torch.as_tensor(weights, dtype=torch.float32, device=DEVICE)


def family_keys(frame_part: pd.DataFrame) -> np.ndarray:
    source = frame_part.get("source_family", pd.Series(["unknown"] * len(frame_part))).astype(str).fillna("unknown")
    device = frame_part.get("device_family", pd.Series(["unknown"] * len(frame_part))).astype(str).fillna("unknown")
    return np.asarray([f"{s}|{d}" for s, d in zip(source, device)], dtype=object)


def select_idx(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    held_value: str,
    cap: int,
    include_held: bool,
) -> np.ndarray:
    if include_held:
        return ckao.role_indices_filtered(frame_by_role, role, phase, cap, include=("device_family", held_value))
    return ckao.role_indices_filtered(frame_by_role, role, phase, cap, exclude=("device_family", held_value))


def build_train_set(
    route: Route,
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    train_cap: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    candidate_name = route.candidate_name
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    fams: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        before = len(ckao.role_indices_filtered(frame_by_role, role, phase, cap))
        idx = select_idx(frame_by_role, role, phase, held_value, cap, include_held=False)
        mat = route_matrix(route, frontend, role, idx)
        part = frame_by_role[role].iloc[idx].reset_index(drop=True)
        xs.append(mat)
        ys.append(np.full(len(idx), int(label), dtype=np.int64))
        fams.append(family_keys(part))
        audit.append(
            {
                "route": route.name,
                "candidate": candidate_name,
                "held_value": held_value,
                "role": role,
                "phase": phase,
                "label": int(label),
                "label_name": LABEL_NAMES[int(label)],
                "rows_before_exclude": int(before),
                "rows_after_exclude": int(len(idx)),
                "held_rows_removed": int(before - len(idx)),
                "feature_dim": int(mat.shape[1]) if mat.ndim == 2 else 0,
            }
        )

    add("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)

    x = np.vstack(xs).astype(np.float32)
    y = np.concatenate(ys).astype(np.int64)
    fam = np.concatenate(fams).astype(object)
    return x, y, fam, audit


def episode_ood_loss(logits: torch.Tensor, y: torch.Tensor, fam_batch: np.ndarray, min_group: int = 3) -> torch.Tensor:
    """Worst pseudo-held OOD-family attack-confidence penalty.

    This is deliberately not a threshold trick.  It says: among legal non-held
    fit OOD groups seen in the batch, the worst group's attack probability must
    be low.  That rehearses the exact deployment failure: a new OOD family
    should not become high-confidence attack just because it is not a familiar
    benign family.
    """
    proba = F.softmax(logits, dim=1)
    attack_p = proba[:, ckh.CLASS_ATTACK]
    nonattack_p, _ = proba[:, NON_ATTACK].max(dim=1)
    is_ood = (y == ckh.CLASS_OOD) | (y == ckh.CLASS_HARD_OOD)
    vals: list[torch.Tensor] = []
    fam_arr = np.asarray(fam_batch, dtype=object)
    for fam in sorted(set(fam_arr.tolist())):
        mask_np = (fam_arr == fam)
        mask_np = mask_np & is_ood.detach().cpu().numpy()
        if int(mask_np.sum()) >= int(min_group):
            mask = torch.as_tensor(mask_np, dtype=torch.bool, device=logits.device)
            # Penalize both high absolute attack confidence and positive
            # attack-vs-nonattack margin for this pseudo-held OOD group.
            vals.append(attack_p[mask].mean() + F.relu(attack_p[mask] - nonattack_p[mask] + 0.10).mean())
    if not vals:
        return logits.new_tensor(0.0)
    return torch.stack(vals).max()


def margin_loss(logits: torch.Tensor, y: torch.Tensor, margin: float = 0.12) -> torch.Tensor:
    proba = F.softmax(logits, dim=1)
    attack = proba[:, ckh.CLASS_ATTACK]
    nonattack, _ = proba[:, NON_ATTACK].max(dim=1)
    score = attack - nonattack
    is_attack = y == ckh.CLASS_ATTACK
    pos = F.relu(float(margin) - score[is_attack]) if torch.any(is_attack) else logits.new_zeros(0)
    neg = F.relu(float(margin) + score[~is_attack]) if torch.any(~is_attack) else logits.new_zeros(0)
    parts = []
    if len(pos):
        parts.append(pos.mean())
    if len(neg):
        parts.append(neg.mean())
    if not parts:
        return logits.new_tensor(0.0)
    return torch.stack(parts).mean()


def train_route(
    route: Route,
    x: np.ndarray,
    y: np.ndarray,
    fam: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    episode_weight: float,
    margin_weight: float,
) -> tuple[TinyEpisodeHead, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    set_seeds()
    mu, sig = standardize_fit(x)
    xs = standardize_apply(x, mu, sig)
    model = TinyEpisodeHead(xs.shape[1]).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=float(lr), weight_decay=2e-4)
    weights = class_weights(y)
    indices = np.arange(len(y))
    history: list[dict[str, Any]] = []
    best_state = None
    best_loss = float("inf")
    stale = 0
    patience = 7

    for epoch in range(int(epochs)):
        rng = np.random.default_rng(SEED + epoch)
        rng.shuffle(indices)
        losses: list[float] = []
        ce_losses: list[float] = []
        margin_losses: list[float] = []
        episode_losses: list[float] = []
        for start in range(0, len(indices), int(batch_size)):
            idx = indices[start : start + int(batch_size)]
            xb = torch.as_tensor(xs[idx], dtype=torch.float32, device=DEVICE)
            yb = torch.as_tensor(y[idx], dtype=torch.long, device=DEVICE)
            logits = model(xb)
            ce = F.cross_entropy(logits, yb, weight=weights)
            m = margin_loss(logits, yb)
            ep = episode_ood_loss(logits, yb, fam[idx]) if route.episode_loss else logits.new_tensor(0.0)
            loss = ce + float(margin_weight) * m + float(episode_weight) * ep
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
            ce_losses.append(float(ce.detach().cpu()))
            margin_losses.append(float(m.detach().cpu()))
            episode_losses.append(float(ep.detach().cpu()))
        epoch_loss = float(np.mean(losses)) if losses else float("nan")
        history.append(
            {
                "route": route.name,
                "epoch": int(epoch),
                "loss": epoch_loss,
                "ce": float(np.mean(ce_losses)) if ce_losses else float("nan"),
                "margin": float(np.mean(margin_losses)) if margin_losses else float("nan"),
                "episode_ood": float(np.mean(episode_losses)) if episode_losses else 0.0,
            }
        )
        if epoch_loss + 1e-5 < best_loss:
            best_loss = epoch_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model, mu, sig, history


@torch.no_grad()
def predict_proba(model: TinyEpisodeHead, x: np.ndarray, mu: np.ndarray, sig: np.ndarray) -> np.ndarray:
    xs = standardize_apply(x, mu, sig)
    logits = model(torch.as_tensor(xs, dtype=torch.float32, device=DEVICE))
    return F.softmax(logits, dim=1).detach().cpu().numpy().astype(np.float64)


def route_matrix(route: Route, frontend: ckai.ExternalFlowFrontend, role: str, idx: np.ndarray) -> np.ndarray:
    if route.candidate_name == RELATIVE_CANDIDATE:
        return relative_delta_matrix(frontend, role, idx)
    return frontend.matrix(candidate_by_name(route.candidate_name), role, idx)


def score_from_proba(proba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    attack = proba[:, ckh.CLASS_ATTACK]
    nonattack = np.max(proba[:, NON_ATTACK], axis=1)
    margin = attack - nonattack
    return attack.astype(np.float64), margin.astype(np.float64)


def calibrate(
    route: Route,
    model: TinyEpisodeHead,
    mu: np.ndarray,
    sig: np.ndarray,
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    eval_cap: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    attack_parts: list[np.ndarray] = []
    margin_parts: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = select_idx(frame_by_role, role, "select", held_value, eval_cap, include_held=False)
        if len(idx):
            proba = predict_proba(model, route_matrix(route, frontend, role, idx), mu, sig)
            attack, margin = score_from_proba(proba)
            attack_parts.append(attack)
            margin_parts.append(margin)
            rows.append(
                {
                    "route": route.name,
                    "held_value": held_value,
                    "calib_role": role,
                    "rows": int(len(idx)),
                    "attack_q99": float(np.quantile(attack, 0.99)),
                    "margin_q99": float(np.quantile(margin, 0.99)),
                }
            )
        else:
            rows.append({"route": route.name, "held_value": held_value, "calib_role": role, "rows": 0})
    if not attack_parts or not margin_parts:
        raise RuntimeError(f"No legal non-held select rows for calibration: {held_value}")
    attack_thr = float(max(np.quantile(v, 0.99) for v in attack_parts if len(v)))
    margin_thr = float(max(np.quantile(v, 0.99) for v in margin_parts if len(v)))

    # Legal support select can only loosen an overly strict attack margin.
    sidx = select_idx(frame_by_role, "support_val", "select", held_value, eval_cap, include_held=False)
    support_margin_q05 = float("nan")
    support_attack_q05 = float("nan")
    if len(sidx):
        proba = predict_proba(model, route_matrix(route, frontend, "support_val", sidx), mu, sig)
        attack, margin = score_from_proba(proba)
        support_attack_q05 = float(np.quantile(attack, 0.05))
        support_margin_q05 = float(np.quantile(margin, 0.05))
        margin_thr = min(margin_thr, support_margin_q05)
    rows.append(
        {
            "route": route.name,
            "held_value": held_value,
            "calib_role": "support_val",
            "rows": int(len(sidx)),
            "support_attack_q05": support_attack_q05,
            "support_margin_q05": support_margin_q05,
            "attack_threshold": attack_thr,
            "decision_margin_threshold": margin_thr,
        }
    )
    return {"attack_threshold": attack_thr, "decision_margin_threshold": margin_thr}, rows


def evaluate_role(
    route: Route,
    model: TinyEpisodeHead,
    mu: np.ndarray,
    sig: np.ndarray,
    thresholds: dict[str, float],
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    role: str,
    phase: str,
    kind: str,
    eval_cap: int,
) -> dict[str, Any]:
    idx = select_idx(frame_by_role, role, phase, held_value, eval_cap, include_held=True)
    desired = "high" if "attack" in kind else "low"
    if len(idx) == 0:
        return {
            "route": route.name,
            "candidate": route.candidate_name,
            "held_value": held_value,
            "role": role,
            "phase": phase,
            "role_kind": kind,
            "rows": 0,
            "desired_hard_direction": desired,
        }
    proba = predict_proba(model, route_matrix(route, frontend, role, idx), mu, sig)
    attack, margin = score_from_proba(proba)
    raw = attack > float(thresholds["attack_threshold"])
    hard = raw & (margin > float(thresholds["decision_margin_threshold"]))
    review = raw & ~hard if route.selective else np.zeros_like(raw, dtype=bool)
    hard_rate = ckg.rate(hard)
    err = 1.0 - hard_rate if desired == "high" else hard_rate
    return {
        "route": route.name,
        "candidate": route.candidate_name,
        "held_value": held_value,
        "role": role,
        "phase": phase,
        "role_kind": kind,
        "rows": int(len(idx)),
        "attack_threshold": float(thresholds["attack_threshold"]),
        "decision_margin_threshold": float(thresholds["decision_margin_threshold"]),
        "raw_alarm_rate": ckg.rate(raw),
        "hard_alarm_rate": hard_rate,
        "review_rate": ckg.rate(review),
        "desired_hard_direction": desired,
        "error_rate_for_role": float(err),
        "attack_score_mean": float(np.mean(attack)),
        "decision_margin_mean": float(np.mean(margin)),
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    df = df[pd.to_numeric(df["rows"], errors="coerce").fillna(0).astype(int) > 0].copy()
    out: list[dict[str, Any]] = []
    for route, part in df.groupby("route", sort=True):
        item: dict[str, Any] = {"route": route}
        for family in [
            "iotsim-stream-consumer",
            "iotsim-hydraulic-system",
            "iotsim-ip-camera-street",
            "domotic-monitor",
            "combined-cycle",
        ]:
            sub = part[part["held_value"].astype(str) == family]
            if sub.empty:
                continue
            weights = pd.to_numeric(sub["rows"], errors="coerce").fillna(0.0)
            item[f"{family}_error"] = float(np.average(pd.to_numeric(sub["error_rate_for_role"], errors="coerce").fillna(0.0), weights=weights))
            item[f"{family}_hard"] = float(np.average(pd.to_numeric(sub["hard_alarm_rate"], errors="coerce").fillna(0.0), weights=weights))
            item[f"{family}_review"] = float(np.average(pd.to_numeric(sub["review_rate"], errors="coerce").fillna(0.0), weights=weights))
        ood = part[part["desired_hard_direction"] == "low"]
        attack = part[part["desired_hard_direction"] == "high"]
        for name, sub in [("held_ood", ood), ("held_attack", attack)]:
            if sub.empty:
                continue
            weights = pd.to_numeric(sub["rows"], errors="coerce").fillna(0.0)
            item[f"{name}_weighted_error"] = float(np.average(pd.to_numeric(sub["error_rate_for_role"], errors="coerce").fillna(0.0), weights=weights))
            item[f"{name}_weighted_review"] = float(np.average(pd.to_numeric(sub["review_rate"], errors="coerce").fillna(0.0), weights=weights))
        out.append(item)
    return out


def build_readout(selected: list[dict[str, Any]], metric_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        f"# {ISSUE}",
        "",
        "## Selected held device families",
        "",
        "| held family | total | OOD | attack | ood_val | ood_stress | sealed OOD | future | sealed attack |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in selected:
        lines.append(
            f"| {row['held_value']} | {row['total_eval_rows']} | {row['ood_eval_rows']} | {row['attack_eval_rows']} | "
            f"{row['ood_val']} | {row['ood_stress']} | {row['sealed_final_ood']} | {row['future_query']} | {row['sealed_final_attack']} |"
        )
    lines.extend(
        [
            "",
            "## Held-family metrics",
            "",
            "| route | frontend | held family | role | rows | hard | raw | review | desired | error |",
            "|---|---|---|---|---:|---:|---:|---:|---|---:|",
        ]
    )
    focus = {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}
    for row in metric_rows:
        if row.get("role") not in focus or int(row.get("rows", 0)) <= 0:
            continue
        lines.append(
            f"| {row['route']} | {row['candidate']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['hard_alarm_rate'])} | {cko.fmt(row['raw_alarm_rate'])} | {cko.fmt(row['review_rate'])} | "
            f"{row['desired_hard_direction']} | {cko.fmt(row['error_rate_for_role'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- True held device_family is excluded from all fit and threshold/select rows.",
            "- Pseudo-held episode loss uses only legal non-held fit OOD groups.",
            "- Future/query/sealed rows are report-only.",
            "- Source/device/family are grouping variables, not inference features.",
            "- Review is diagnostic only; high review is not counted as success.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    set_seeds()
    out = OUT_BASE if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)

    smoke_input = not bool(args.full)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke_input)
    x_by_role, frame_by_role, cap_rows = ckai.filter_roles_by_recorded_index(
        x_by_role,
        frame_by_role,
        int(args.max_recorded_index),
    )
    ckao.add_family_columns(frame_by_role)
    selected = ckao.select_leave_groups(
        frame_by_role,
        int(args.eval_cap),
        int(args.max_leave_groups),
        int(args.min_eval_rows),
        str(args.held_values),
    )
    if not selected:
        raise RuntimeError("no held groups selected")
    preflight_rows = ckao.build_preflight_audit(frame_by_role, selected, int(args.train_cap), int(args.eval_cap))
    preflight_pass = all(
        bool(row.get("pass_no_held_leakage", True)) and bool(row.get("pass_eval_only_held", True))
        for row in preflight_rows
    )
    if not preflight_pass:
        raise RuntimeError("strict leave preflight failed")

    route_names = {v.strip() for v in str(args.routes).split(",") if v.strip()}
    routes = [r for r in ROUTES if r.name in route_names]
    if not routes:
        raise RuntimeError("no routes selected")

    cache = ckai.ExternalFlowFeatureCache(cko.GOTHAM_ZIP)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)

    metric_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    for held in selected:
        held_value = str(held["held_value"])
        for route in routes:
            x_train, y_train, fam_train, audit = build_train_set(route, frontend, frame_by_role, held_value, int(args.train_cap))
            model, mu, sig, history = train_route(
                route,
                x_train,
                y_train,
                fam_train,
                int(args.epochs),
                int(args.batch_size),
                float(args.lr),
                float(args.episode_weight),
                float(args.margin_weight),
            )
            thresholds, thr_rows = calibrate(
                route,
                model,
                mu,
                sig,
                frontend,
                frame_by_role,
                held_value,
                int(args.eval_cap),
            )
            for row in audit:
                train_rows.append({**row, "train_rows_total": int(len(y_train)), "train_classes": "|".join(map(str, sorted(np.unique(y_train).tolist())))})
            for row in history:
                history_rows.append({**row, "held_value": held_value})
            threshold_rows.extend(thr_rows)
            for role, phase, kind in cko.ROLE_EVAL:
                metric_rows.append(
                    evaluate_role(
                        route,
                        model,
                        mu,
                        sig,
                        thresholds,
                        frontend,
                        frame_by_role,
                        held_value,
                        role,
                        phase,
                        kind,
                        int(args.eval_cap),
                    )
                )

    seconds = time.time() - started
    cko.write_csv(out / "selected_leave_groups.csv", selected)
    cko.write_csv(out / "strict_leave_preflight_audit.csv", preflight_rows)
    cko.write_csv(out / "role_cap_audit.csv", cap_rows)
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "train_history.csv", history_rows)
    cko.write_csv(out / "threshold_audit.csv", threshold_rows)
    cko.write_csv(out / "leave_role_metrics.csv", metric_rows)
    cko.write_csv(out / "route_summary.csv", aggregate(metric_rows))
    cko.write_csv(out / "external_extraction_audit.csv", cache.audit_rows)
    cko.write_md(out / "codex_readout.md", build_readout(selected, metric_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "full": bool(args.full),
            "smoke_input": bool(smoke_input),
            "max_recorded_index": int(args.max_recorded_index),
            "train_cap": int(args.train_cap),
            "eval_cap": int(args.eval_cap),
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "lr": float(args.lr),
            "episode_weight": float(args.episode_weight),
            "margin_weight": float(args.margin_weight),
            "routes": [r.__dict__ for r in routes],
            "selected_leave_groups": selected,
            "preflight_pass": bool(preflight_pass),
            "data_use_boundary": {
                "true_fit_select_exclude_held_device_family": True,
                "eval_include_only_held_device_family": True,
                "pseudoheld_episode_uses_only_legal_nonheld_fit_rows": True,
                "query_future_sealed_used_for_training_or_thresholding": False,
                "source_device_family_as_inference_features": False,
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "out": str(out),
                "seconds": seconds,
                "routes": [r.name for r in routes],
                "held_groups": [r["held_value"] for r in selected],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--max-recorded-index", type=int, default=300000)
    parser.add_argument("--train-cap", type=int, default=3000)
    parser.add_argument("--eval-cap", type=int, default=4000)
    parser.add_argument("--max-leave-groups", type=int, default=5)
    parser.add_argument("--min-eval-rows", type=int, default=128)
    parser.add_argument("--held-values", default="")
    parser.add_argument("--routes", default="P0_C1_ce_margin,P1_C1_episode_margin,P2_M1_episode_margin,P3_M1_episode_selective")
    parser.add_argument("--epochs", type=int, default=28)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--episode-weight", type=float, default=0.8)
    parser.add_argument("--margin-weight", type=float, default=0.35)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
