"""issue27ckap: C1 invariant/prototype/selective gate local smoke.

This is a small-but-deep backend smoke for the specific failure exposed by
issue27ckao:

    held OOD device families are still mapped into the attack region.

The script fixes the frontend to C1 CICFlow-style evidence and tests a narrow
backend ladder under the same strict leave-device-family protocol:

    H1: C1 + MLP CE control
    H2: H1 + supervised contrastive/prototype gate
    H3: H2 + REx worst-family risk penalty
    H4: H3 + budgeted selective review gate

H0 C1+HistGB is intentionally not refit here; issue27ckao is the paired
baseline.  This script focuses on whether a neural/prototype backend can pull
held OOD families away from the hard attack region without hiding everything
inside review.

Data-use boundary:
* fit uses support_train/id_calib/ood_val/ood_stress fit only, excluding held
  device_family;
* threshold/select uses id_calib/ood_val/ood_stress/support_val select only,
  excluding held device_family;
* eval includes only the held device_family;
* query/future/sealed roles are report-only.
"""

from __future__ import annotations

import argparse
import json
import math
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


ISSUE = "issue27ckap_c1_ips_prototype_selective_smoke_v1_2026-07-09"
OUT_BASE = cko.ROOT / "runs" / ISSUE
SEED = 27
DEVICE = torch.device("cpu")


LABEL_NAMES = {
    ckh.CLASS_ID: "id",
    ckh.CLASS_OOD: "ood",
    ckh.CLASS_HARD_OOD: "hard_ood",
    ckh.CLASS_ATTACK: "attack",
}


@dataclass(frozen=True)
class NeuralRoute:
    name: str
    use_supcon: bool
    use_rex: bool
    use_proto_gate: bool
    use_budgeted_review: bool
    description: str


ROUTES = [
    NeuralRoute(
        "H1_c1_mlp_ce",
        use_supcon=False,
        use_rex=False,
        use_proto_gate=False,
        use_budgeted_review=False,
        description="C1 + small MLP CE control.",
    ),
    NeuralRoute(
        "H2_c1_supcon_proto",
        use_supcon=True,
        use_rex=False,
        use_proto_gate=True,
        use_budgeted_review=False,
        description="C1 + SupCon embedding + prototype attack gate.",
    ),
    NeuralRoute(
        "H3_c1_supcon_rex_proto",
        use_supcon=True,
        use_rex=True,
        use_proto_gate=True,
        use_budgeted_review=False,
        description="H2 + REx variance penalty over source/device environments.",
    ),
    NeuralRoute(
        "H4_c1_supcon_rex_proto_selective_budget",
        use_supcon=True,
        use_rex=True,
        use_proto_gate=True,
        use_budgeted_review=True,
        description="H3 + budgeted review for high attack score but prototype conflict.",
    ),
]


class EncoderHead(nn.Module):
    def __init__(self, in_dim: int, emb_dim: int = 32, hidden: int = 128, classes: int = 4):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(hidden, emb_dim),
        )
        self.classifier = nn.Linear(emb_dim, classes)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.encoder(x)
        z = F.normalize(z, dim=1)
        logits = self.classifier(z)
        return z, logits


def set_seeds(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = np.mean(x, axis=0, keepdims=True)
    sig = np.std(x, axis=0, keepdims=True)
    sig = np.where(sig < 1e-6, 1.0, sig)
    return mu.astype(np.float32), sig.astype(np.float32)


def standardize_apply(x: np.ndarray, mu: np.ndarray, sig: np.ndarray) -> np.ndarray:
    return np.nan_to_num((np.asarray(x, dtype=np.float32) - mu) / sig, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def supcon_loss(z: torch.Tensor, y: torch.Tensor, temperature: float = 0.2) -> torch.Tensor:
    if len(z) <= 1:
        return z.new_tensor(0.0)
    sim = torch.matmul(z, z.T) / temperature
    logits_mask = torch.ones_like(sim, dtype=torch.bool)
    logits_mask.fill_diagonal_(False)
    same = (y[:, None] == y[None, :]) & logits_mask
    # Stable log-softmax over non-self examples.
    sim_masked = sim.masked_fill(~logits_mask, -1e9)
    log_prob = sim_masked - torch.logsumexp(sim_masked, dim=1, keepdim=True)
    pos_count = same.sum(dim=1)
    valid = pos_count > 0
    if not torch.any(valid):
        return z.new_tensor(0.0)
    mean_log_prob_pos = (log_prob * same.float()).sum(dim=1)[valid] / pos_count[valid].float()
    return -mean_log_prob_pos.mean()


def env_keys(frame_part: pd.DataFrame) -> list[str]:
    source = frame_part.get("source_family", pd.Series(["unknown"] * len(frame_part))).astype(str).fillna("unknown")
    device = frame_part.get("device_family", pd.Series(["unknown"] * len(frame_part))).astype(str).fillna("unknown")
    return [f"{s}|{d}" for s, d in zip(source, device)]


def rex_penalty(loss_vec: torch.Tensor, env_batch: np.ndarray, min_group: int = 4) -> torch.Tensor:
    vals: list[torch.Tensor] = []
    for env in sorted(set(env_batch.tolist())):
        mask_np = env_batch == env
        if int(mask_np.sum()) >= min_group:
            mask = torch.as_tensor(mask_np, dtype=torch.bool, device=loss_vec.device)
            vals.append(loss_vec[mask].mean())
    if len(vals) <= 1:
        return loss_vec.new_tensor(0.0)
    stacked = torch.stack(vals)
    return torch.var(stacked, unbiased=False)


def c1_candidate() -> ckai.Candidate:
    for candidate in ckai.CANDIDATES:
        if candidate.name == "C1_cicflow_style_only_histgb":
            return candidate
    raise RuntimeError("C1 candidate not found")


def build_c1_train_set(
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    train_cap: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    candidate = c1_candidate()
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    envs: list[str] = []
    audit: list[dict[str, Any]] = []
    exclude = ("device_family", held_value)

    def add(role: str, phase: str, label: int, cap: int) -> None:
        before = len(ckao.role_indices_filtered(frame_by_role, role, phase, cap))
        idx = ckao.role_indices_filtered(frame_by_role, role, phase, cap, exclude=exclude)
        mat = frontend.matrix(candidate, role, idx)
        part = frame_by_role[role].iloc[idx].reset_index(drop=True)
        xs.append(mat)
        ys.append(np.full(len(idx), int(label), dtype=np.int64))
        envs.extend(env_keys(part))
        audit.append(
            {
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
    env = np.asarray(envs, dtype=object)
    return x, y, env, audit


def class_weights(y: np.ndarray) -> torch.Tensor:
    labels = np.arange(4, dtype=np.int64)
    counts = np.asarray([max(1, int(np.sum(y == label))) for label in labels], dtype=np.float32)
    w = 1.0 / counts
    w = w * (len(labels) / max(1e-6, float(np.sum(w))))
    return torch.as_tensor(w, dtype=torch.float32, device=DEVICE)


def train_route(
    route: NeuralRoute,
    x: np.ndarray,
    y: np.ndarray,
    env: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    supcon_weight: float,
    rex_weight: float,
) -> tuple[EncoderHead, list[dict[str, Any]]]:
    set_seeds()
    mu, sig = standardize_fit(x)
    xs = standardize_apply(x, mu, sig)
    model = EncoderHead(xs.shape[1]).to(DEVICE)
    model.mu = torch.as_tensor(mu, dtype=torch.float32, device=DEVICE)  # type: ignore[attr-defined]
    model.sig = torch.as_tensor(sig, dtype=torch.float32, device=DEVICE)  # type: ignore[attr-defined]
    opt = torch.optim.AdamW(model.parameters(), lr=float(lr), weight_decay=1e-4)
    weights = class_weights(y)
    n = len(y)
    indices = np.arange(n)
    history: list[dict[str, Any]] = []
    best_state = None
    best_loss = float("inf")
    patience = 8
    stale = 0

    for epoch in range(int(epochs)):
        rng = np.random.default_rng(SEED + epoch)
        rng.shuffle(indices)
        losses: list[float] = []
        ce_losses: list[float] = []
        sup_losses: list[float] = []
        rex_losses: list[float] = []
        for start in range(0, n, int(batch_size)):
            idx = indices[start : start + int(batch_size)]
            xb = torch.as_tensor(xs[idx], dtype=torch.float32, device=DEVICE)
            yb = torch.as_tensor(y[idx], dtype=torch.long, device=DEVICE)
            zb, logits = model(xb)
            ce_vec = F.cross_entropy(logits, yb, weight=weights, reduction="none")
            ce = ce_vec.mean()
            sup = supcon_loss(zb, yb) if route.use_supcon else ce.new_tensor(0.0)
            rex = rex_penalty(ce_vec, env[idx]) if route.use_rex else ce.new_tensor(0.0)
            loss = ce + float(supcon_weight) * sup + float(rex_weight) * rex
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
            ce_losses.append(float(ce.detach().cpu()))
            sup_losses.append(float(sup.detach().cpu()))
            rex_losses.append(float(rex.detach().cpu()))
        epoch_loss = float(np.mean(losses)) if losses else float("nan")
        history.append(
            {
                "route": route.name,
                "epoch": epoch,
                "loss": epoch_loss,
                "ce": float(np.mean(ce_losses)) if ce_losses else float("nan"),
                "supcon": float(np.mean(sup_losses)) if sup_losses else 0.0,
                "rex": float(np.mean(rex_losses)) if rex_losses else 0.0,
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
    return model, history


@torch.no_grad()
def embed_logits(model: EncoderHead, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = model.mu.detach().cpu().numpy()  # type: ignore[attr-defined]
    sig = model.sig.detach().cpu().numpy()  # type: ignore[attr-defined]
    xs = standardize_apply(x, mu, sig)
    z, logits = model(torch.as_tensor(xs, dtype=torch.float32, device=DEVICE))
    proba = F.softmax(logits, dim=1)
    return z.detach().cpu().numpy().astype(np.float32), proba.detach().cpu().numpy().astype(np.float64)


def compute_prototypes(model: EncoderHead, x: np.ndarray, y: np.ndarray) -> dict[int, np.ndarray]:
    z, _ = embed_logits(model, x)
    protos: dict[int, np.ndarray] = {}
    for label in sorted(set(y.tolist())):
        part = z[y == label]
        if len(part):
            p = np.mean(part, axis=0)
            norm = np.linalg.norm(p)
            if norm > 1e-12:
                p = p / norm
            protos[int(label)] = p.astype(np.float32)
    return protos


def proto_scores(z: np.ndarray, protos: dict[int, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    attack_proto = protos.get(ckh.CLASS_ATTACK)
    if attack_proto is None:
        return (
            np.full(len(z), np.inf, dtype=np.float64),
            np.full(len(z), np.inf, dtype=np.float64),
            np.full(len(z), -np.inf, dtype=np.float64),
        )
    d_attack = np.sum((z - attack_proto[None, :]) ** 2, axis=1).astype(np.float64)
    non_attack_dist = []
    for label, proto in protos.items():
        if int(label) != ckh.CLASS_ATTACK:
            non_attack_dist.append(np.sum((z - proto[None, :]) ** 2, axis=1))
    if non_attack_dist:
        d_nonattack = np.min(np.vstack(non_attack_dist), axis=0).astype(np.float64)
    else:
        d_nonattack = np.full(len(z), np.inf, dtype=np.float64)
    # Higher margin means more attack-like than non-attack-like.
    margin = d_nonattack - d_attack
    return d_attack, d_nonattack, margin.astype(np.float64)


def select_indices(
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


def route_features(frontend: ckai.ExternalFlowFrontend, role: str, idx: np.ndarray) -> np.ndarray:
    return frontend.matrix(c1_candidate(), role, idx)


def calibrate_thresholds(
    route: NeuralRoute,
    model: EncoderHead,
    protos: dict[int, np.ndarray],
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    eval_cap: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    benign_attack_scores: list[np.ndarray] = []
    benign_proto_margins: list[np.ndarray] = []
    review_scores: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = select_indices(frame_by_role, role, "select", held_value, eval_cap, include_held=False)
        if len(idx):
            x = route_features(frontend, role, idx)
            z, p = embed_logits(model, x)
            _da, _dn, margin = proto_scores(z, protos)
            attack = p[:, ckh.CLASS_ATTACK]
            benign_attack_scores.append(attack)
            benign_proto_margins.append(margin)
            review_scores.append(attack - margin)
            rows.append(
                {
                    "held_value": held_value,
                    "route": route.name,
                    "calib_role": role,
                    "rows": int(len(idx)),
                    "attack_q99": float(np.quantile(attack, 0.99)),
                    "proto_margin_q99": float(np.quantile(margin, 0.99)),
                    "review_score_q99": float(np.quantile(attack - margin, 0.99)),
                }
            )
        else:
            rows.append({"held_value": held_value, "route": route.name, "calib_role": role, "rows": 0})
    if not benign_attack_scores:
        raise RuntimeError(f"No non-held benign/OOD calibration rows for {held_value}")
    attack_thr = float(max(np.quantile(v, 0.99) for v in benign_attack_scores if len(v)))
    proto_thr = float(max(np.quantile(v, 0.99) for v in benign_proto_margins if len(v)))
    review_thr = float(max(np.quantile(v, 0.99) for v in review_scores if len(v)))

    # Attack support select is legal for threshold support, still excluding held.
    sidx = select_indices(frame_by_role, "support_val", "select", held_value, eval_cap, include_held=False)
    support_attack_q05 = float("nan")
    support_proto_q05 = float("nan")
    if len(sidx):
        sx = route_features(frontend, "support_val", sidx)
        sz, sp = embed_logits(model, sx)
        _da, _dn, sm = proto_scores(sz, protos)
        support_attack_q05 = float(np.quantile(sp[:, ckh.CLASS_ATTACK], 0.05))
        support_proto_q05 = float(np.quantile(sm, 0.05))
        # Do not let prototype gate murder support if support evidence is scarce.
        if math.isfinite(support_proto_q05):
            proto_thr = min(proto_thr, support_proto_q05)
    rows.append(
        {
            "held_value": held_value,
            "route": route.name,
            "calib_role": "support_val",
            "rows": int(len(sidx)),
            "support_attack_q05": support_attack_q05,
            "support_proto_margin_q05": support_proto_q05,
            "attack_threshold": attack_thr,
            "proto_margin_threshold": proto_thr,
            "review_score_threshold": review_thr,
        }
    )
    return {
        "attack_threshold": attack_thr,
        "proto_margin_threshold": proto_thr,
        "review_score_threshold": review_thr,
    }, rows


def evaluate_route_role(
    route: NeuralRoute,
    model: EncoderHead,
    protos: dict[int, np.ndarray],
    thresholds: dict[str, float],
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    role: str,
    phase: str,
    kind: str,
    eval_cap: int,
) -> dict[str, Any]:
    idx = select_indices(frame_by_role, role, phase, held_value, eval_cap, include_held=True)
    desired = "high" if "attack" in kind else "low"
    if len(idx) == 0:
        return {
            "route": route.name,
            "held_value": held_value,
            "role": role,
            "phase": phase,
            "role_kind": kind,
            "rows": 0,
            "hard_alarm_rate": float("nan"),
            "raw_alarm_rate": float("nan"),
            "review_rate": float("nan"),
            "desired_hard_direction": desired,
            "error_rate_for_role": float("nan"),
        }
    x = route_features(frontend, role, idx)
    z, p = embed_logits(model, x)
    _da, _dn, margin = proto_scores(z, protos)
    attack = p[:, ckh.CLASS_ATTACK]
    raw_alarm = attack > float(thresholds["attack_threshold"])
    if route.use_proto_gate:
        proto_ok = margin > float(thresholds["proto_margin_threshold"])
        hard = raw_alarm & proto_ok
        conflict = raw_alarm & ~proto_ok
    else:
        hard = raw_alarm
        conflict = np.zeros_like(raw_alarm, dtype=bool)
    if route.use_budgeted_review:
        review_score = attack - margin
        review = conflict & (review_score > float(thresholds["review_score_threshold"]))
    else:
        review = conflict
    hard_rate = ckg.rate(hard)
    review_rate = ckg.rate(review)
    raw_rate = ckg.rate(raw_alarm)
    err = 1.0 - hard_rate if desired == "high" else hard_rate
    return {
        "route": route.name,
        "held_value": held_value,
        "role": role,
        "phase": phase,
        "role_kind": kind,
        "rows": int(len(idx)),
        "attack_threshold": float(thresholds["attack_threshold"]),
        "proto_margin_threshold": float(thresholds["proto_margin_threshold"]),
        "review_score_threshold": float(thresholds["review_score_threshold"]),
        "hard_alarm_rate": hard_rate,
        "raw_alarm_rate": raw_rate,
        "review_rate": review_rate,
        "desired_hard_direction": desired,
        "error_rate_for_role": float(err),
        "attack_score_mean": float(np.mean(attack)),
        "proto_margin_mean": float(np.mean(margin)),
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    df = pd.DataFrame(rows)
    if df.empty:
        return out
    df = df[pd.to_numeric(df["rows"], errors="coerce").fillna(0).astype(int) > 0].copy()
    for route, part in df.groupby("route", sort=True):
        item: dict[str, Any] = {"route": route}
        for family in ["iotsim-stream-consumer", "iotsim-hydraulic-system", "iotsim-ip-camera-street", "domotic-monitor", "combined-cycle"]:
            fam = part[part["held_value"].astype(str) == family]
            if not fam.empty:
                item[f"{family}_weighted_error"] = float(
                    np.average(
                        pd.to_numeric(fam["error_rate_for_role"], errors="coerce").fillna(0.0),
                        weights=pd.to_numeric(fam["rows"], errors="coerce").fillna(0.0),
                    )
                )
                item[f"{family}_review"] = float(
                    np.average(
                        pd.to_numeric(fam["review_rate"], errors="coerce").fillna(0.0),
                        weights=pd.to_numeric(fam["rows"], errors="coerce").fillna(0.0),
                    )
                )
        ood = part[part["desired_hard_direction"] == "low"]
        atk = part[part["desired_hard_direction"] == "high"]
        for name, sub in [("held_ood", ood), ("held_attack", atk)]:
            if not sub.empty:
                weights = pd.to_numeric(sub["rows"], errors="coerce").fillna(0.0)
                item[f"{name}_weighted_error"] = float(np.average(pd.to_numeric(sub["error_rate_for_role"], errors="coerce").fillna(0.0), weights=weights))
                item[f"{name}_weighted_review"] = float(np.average(pd.to_numeric(sub["review_rate"], errors="coerce").fillna(0.0), weights=weights))
        out.append(item)
    return out


def build_readout(selected: list[dict[str, Any]], rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        f"# {ISSUE}",
        "",
        "## Selected held families",
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
            "| route | held family | role | rows | hard | raw | review | desired | error |",
            "|---|---|---|---:|---:|---:|---:|---|---:|",
        ]
    )
    focus = {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}
    for row in rows:
        if row["role"] not in focus or int(row["rows"]) <= 0:
            continue
        lines.append(
            f"| {row['route']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['hard_alarm_rate'])} | {cko.fmt(row['raw_alarm_rate'])} | {cko.fmt(row['review_rate'])} | "
            f"{row['desired_hard_direction']} | {cko.fmt(row['error_rate_for_role'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fixed frontend: C1 CICFlow-style evidence from issue27ckai.",
            "- Fit/select exclude held device_family.",
            "- Eval includes only held device_family.",
            "- Prototype/review thresholds use non-held legal select roles only.",
            "- Query/future/sealed roles are report-only.",
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
    preflight_rows = ckao.build_preflight_audit(frame_by_role, selected, int(args.train_cap), int(args.eval_cap))
    preflight_pass = all(
        bool(row.get("pass_no_held_leakage", True)) and bool(row.get("pass_eval_only_held", True))
        for row in preflight_rows
    )
    if not preflight_pass:
        raise RuntimeError("strict leave preflight failed")
    cache = ckai.ExternalFlowFeatureCache(cko.GOTHAM_ZIP)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)
    route_names = {v.strip() for v in str(args.routes).split(",") if v.strip()}
    routes = [r for r in ROUTES if r.name in route_names]
    if not routes:
        raise RuntimeError("no routes selected")

    metric_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    for held in selected:
        held_value = str(held["held_value"])
        x_train, y_train, env_train, base_audit = build_c1_train_set(
            frontend,
            frame_by_role,
            held_value,
            int(args.train_cap),
        )
        for route in routes:
            model, hist = train_route(
                route,
                x_train,
                y_train,
                env_train,
                int(args.epochs),
                int(args.batch_size),
                float(args.lr),
                float(args.supcon_weight),
                float(args.rex_weight),
            )
            protos = compute_prototypes(model, x_train, y_train)
            thresholds, thr_rows = calibrate_thresholds(
                route,
                model,
                protos,
                frontend,
                frame_by_role,
                held_value,
                int(args.eval_cap),
            )
            for row in base_audit:
                train_rows.append({**row, "route": route.name, "train_rows_total": int(len(y_train))})
            for row in hist:
                history_rows.append({**row, "held_value": held_value})
            threshold_rows.extend(thr_rows)
            for role, phase, kind in cko.ROLE_EVAL:
                metric_rows.append(
                    evaluate_route_role(
                        route,
                        model,
                        protos,
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
    cko.write_csv(out / "route_summary.csv", aggregate_rows(metric_rows))
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
            "routes": [r.__dict__ for r in routes],
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "supcon_weight": float(args.supcon_weight),
            "rex_weight": float(args.rex_weight),
            "selected_leave_groups": selected,
            "preflight_pass": bool(preflight_pass),
            "data_use_boundary": {
                "frontend": "C1_cicflow_style_only",
                "fit_roles_exclude_held": True,
                "select_roles_exclude_held": True,
                "eval_roles_include_only_held": True,
                "query_future_sealed_used_for_training_or_thresholding": False,
                "source_device_as_inference_features": False,
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds, "routes": [r.name for r in routes]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--max-recorded-index", type=int, default=300000)
    parser.add_argument("--train-cap", type=int, default=3000)
    parser.add_argument("--eval-cap", type=int, default=4000)
    parser.add_argument("--max-leave-groups", type=int, default=5)
    parser.add_argument("--min-eval-rows", type=int, default=128)
    parser.add_argument("--held-values", default="")
    parser.add_argument("--routes", default="H1_c1_mlp_ce,H2_c1_supcon_proto,H3_c1_supcon_rex_proto,H4_c1_supcon_rex_proto_selective_budget")
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--supcon-weight", type=float, default=0.1)
    parser.add_argument("--rex-weight", type=float, default=0.25)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
