"""issue27ckab: pseudo-held episodic representation-map training v1.

This is a strict follow-up to CKAA.

CKAA showed that the interaction/causal representation map can recover useful
main-split attack signal, but leave-device-family stress is still unstable.  The
goal here is not to tune thresholds or move errors into review.  The goal is to
make the latent map train under simulated "unseen device family" pressure using
only legal fit roles.

Data-use contract:

* fit only: support_train / id_calib / ood_val / ood_stress, phase=fit
* threshold only: id_calib / ood_val / ood_stress / support_val, phase=select
* report only: query/future/sealed roles
* pseudo-held episodes are built only inside the legal fit set

Implementation note:

This file deliberately reuses CKAA's frontend/evaluation/audit machinery and
patches only the training routine.  That keeps the comparison against CKAA
clean and avoids a new result format.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckaa_contrastive_interaction_map_v1 as ckaa  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27cks_neural_causal_selective_head_v1 as cks  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402


ISSUE = "issue27ckab_pseudoheld_episode_map_v1_2026-07-03"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = ckaa.DEFAULT_HELD_VALUES
SEED = ckaa.SEED
BENIGN_SAFE_Q = ckaa.BENIGN_SAFE_Q

torch = ckaa.torch
nn = ckaa.nn
F = ckaa.F


@dataclass(frozen=True)
class EpisodeSpec:
    """Additional legal-fit-only pseudo-held episode pressure."""

    name: str
    enabled: bool
    group_field: str
    min_group_rows: int
    episode_lambda: float
    episode_rex_lambda: float
    episode_worst_lambda: float
    prototype_lambda: float
    logit_margin: float
    prototype_margin: float
    description: str


def _clone_candidate(base: ckaa.MapCandidate, *, name: str, description: str, epochs: int | None = None) -> ckaa.MapCandidate:
    return ckaa.MapCandidate(
        name=name,
        hidden_dim=base.hidden_dim,
        map_dim=base.map_dim,
        epochs=base.epochs if epochs is None else epochs,
        lr=base.lr,
        weight_decay=base.weight_decay,
        dropout=base.dropout,
        contrast_lambda=base.contrast_lambda,
        contrast_margin=base.contrast_margin,
        adv_lambda=base.adv_lambda,
        rex_lambda=base.rex_lambda,
        worst_group_lambda=base.worst_group_lambda,
        description=description,
    )


def _stronger_candidate(base: ckaa.MapCandidate, *, name: str, description: str) -> ckaa.MapCandidate:
    return ckaa.MapCandidate(
        name=name,
        hidden_dim=max(base.hidden_dim, 144),
        map_dim=max(base.map_dim, 72),
        epochs=120,
        lr=7e-4,
        weight_decay=1.8e-4,
        dropout=0.16,
        contrast_lambda=0.30,
        contrast_margin=1.25,
        adv_lambda=0.05,
        rex_lambda=0.12,
        worst_group_lambda=0.04,
        description=description,
    )


_A3 = ckaa.candidate_by_name("A3_contrastive_invariant_map")

CANDIDATES = [
    _clone_candidate(
        _A3,
        name="B0_a3_replay_fast",
        description="Fast local diagnostic A3 replay control; no pseudo-held episode loss.",
        epochs=35,
    ),
    _clone_candidate(
        _A3,
        name="B1_pseudoheld_episode_map_fast",
        description="Fast local diagnostic A3 plus legal-fit pseudo-held device-family episode pressure.",
        epochs=45,
    ),
    _clone_candidate(
        _A3,
        name="B0_a3_replay_control",
        description="A3 replay control inside CKAB; no pseudo-held episode loss.",
        epochs=90,
    ),
    _clone_candidate(
        _A3,
        name="B1_pseudoheld_episode_map",
        description="A3 plus legal-fit pseudo-held device-family episode CE/REx/worst/prototype pressure.",
        epochs=105,
    ),
    _stronger_candidate(
        _A3,
        name="B2_pseudoheld_episode_map_stronger",
        description="Stronger pseudo-held episode map with slightly larger latent capacity and stronger invariance.",
    ),
]

EPISODE_SPECS: dict[str, EpisodeSpec] = {
    "B0_a3_replay_fast": EpisodeSpec(
        name="E0_disabled_fast",
        enabled=False,
        group_field="device_family",
        min_group_rows=8,
        episode_lambda=0.0,
        episode_rex_lambda=0.0,
        episode_worst_lambda=0.0,
        prototype_lambda=0.0,
        logit_margin=0.20,
        prototype_margin=1.10,
        description="Fast no-episode pressure diagnostic; not a final candidate.",
    ),
    "B1_pseudoheld_episode_map_fast": EpisodeSpec(
        name="E1_device_family_episode_fast",
        enabled=True,
        group_field="device_family",
        min_group_rows=8,
        episode_lambda=0.20,
        episode_rex_lambda=0.12,
        episode_worst_lambda=0.04,
        prototype_lambda=0.08,
        logit_margin=0.25,
        prototype_margin=1.15,
        description="Fast leave-one-device-family legal-fit episode diagnostic; not a final candidate.",
    ),
    "B0_a3_replay_control": EpisodeSpec(
        name="E0_disabled",
        enabled=False,
        group_field="device_family",
        min_group_rows=8,
        episode_lambda=0.0,
        episode_rex_lambda=0.0,
        episode_worst_lambda=0.0,
        prototype_lambda=0.0,
        logit_margin=0.20,
        prototype_margin=1.10,
        description="No episode pressure; CKAA A3 replay control.",
    ),
    "B1_pseudoheld_episode_map": EpisodeSpec(
        name="E1_device_family_episode",
        enabled=True,
        group_field="device_family",
        min_group_rows=8,
        episode_lambda=0.20,
        episode_rex_lambda=0.12,
        episode_worst_lambda=0.04,
        prototype_lambda=0.08,
        logit_margin=0.25,
        prototype_margin=1.15,
        description="Leave-one-device-family legal-fit episode risk plus prototype-transfer pressure.",
    ),
    "B2_pseudoheld_episode_map_stronger": EpisodeSpec(
        name="E2_device_family_episode_stronger",
        enabled=True,
        group_field="device_family",
        min_group_rows=8,
        episode_lambda=0.30,
        episode_rex_lambda=0.16,
        episode_worst_lambda=0.06,
        prototype_lambda=0.12,
        logit_margin=0.30,
        prototype_margin=1.20,
        description="Stronger leave-one-device-family episode pressure; use after B1 smoke passes.",
    ),
}


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def _series_or_default(df: pd.DataFrame, column: str, default: str) -> list[str]:
    if column in df.columns:
        return [str(v) if pd.notna(v) and str(v) else default for v in df[column].tolist()]
    return [default for _ in range(len(df))]


def _factorize(values: list[str]) -> tuple[np.ndarray, dict[str, int]]:
    uniq = sorted(set(str(v) for v in values))
    mapping = {value: i for i, value in enumerate(uniq)}
    ids = np.asarray([mapping[str(v)] for v in values], dtype=np.int64)
    return ids, mapping


def _add_train_chunk_with_meta(
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
    families: list[str],
    roles: list[str],
    audit: list[dict[str, Any]],
) -> None:
    idx = ckaa.role_indices(frame_by_role, role, phase, cap, exclude=exclude)
    mech_xs.append(frontend.matrix(role, idx, "attack_mechanism"))
    ctx_xs.append(frontend.matrix(role, idx, "conflict_context"))
    ys.append(np.full(len(idx), label, dtype=np.int64))
    sub = frame_by_role[role].iloc[idx].reset_index(drop=True)
    envs.extend(cks.env_keys(sub))
    families.extend(_series_or_default(sub, "device_family", "unknown_device_family"))
    roles.extend([role for _ in range(len(idx))])
    audit.append(
        {
            "role": role,
            "phase": phase,
            "rows": len(idx),
            "label": label,
            "label_name": ckq.CLASS_NAMES.get(label, str(label)),
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
            "meta_group_field": "device_family",
        }
    )


def build_train_set_with_meta(
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str], list[str], list[dict[str, Any]]]:
    mech_xs: list[np.ndarray] = []
    ctx_xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    envs: list[str] = []
    families: list[str] = []
    roles: list[str] = []
    audit: list[dict[str, Any]] = []

    _add_train_chunk_with_meta(frontend, frame_by_role, "support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP, exclude, mech_xs, ctx_xs, ys, envs, families, roles, audit)
    _add_train_chunk_with_meta(frontend, frame_by_role, "id_calib", "fit", ckh.CLASS_ID, train_cap, exclude, mech_xs, ctx_xs, ys, envs, families, roles, audit)
    _add_train_chunk_with_meta(frontend, frame_by_role, "ood_val", "fit", ckh.CLASS_OOD, train_cap, exclude, mech_xs, ctx_xs, ys, envs, families, roles, audit)
    _add_train_chunk_with_meta(frontend, frame_by_role, "ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap, exclude, mech_xs, ctx_xs, ys, envs, families, roles, audit)

    return (
        np.vstack(mech_xs).astype(np.float32),
        np.vstack(ctx_xs).astype(np.float32),
        np.concatenate(ys).astype(np.int64),
        envs,
        families,
        roles,
        audit,
    )


def _prototype_episode_loss(
    z: Any,
    y: Any,
    group_ids: Any,
    group_value: Any,
    spec: EpisodeSpec,
) -> Any:
    z_norm = F.normalize(z, dim=1)
    held = group_ids == group_value
    base = ~held
    if int(held.sum().item()) < spec.min_group_rows or int(base.sum().item()) < spec.min_group_rows:
        return torch.zeros((), dtype=torch.float32, device=z.device)

    centers: dict[int, Any] = {}
    for label in torch.unique(y[base]):
        label_int = int(label.item())
        mask = base & (y == label)
        if int(mask.sum().item()) >= 1:
            centers[label_int] = F.normalize(z_norm[mask].mean(dim=0, keepdim=True), dim=1).squeeze(0)

    pull_terms = []
    push_terms = []
    attack_label = ckh.CLASS_ATTACK
    nonattack_labels = [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD]
    for label in torch.unique(y[held]):
        label_int = int(label.item())
        held_mask = held & (y == label)
        if label_int in centers:
            pull_terms.append(torch.sum((z_norm[held_mask] - centers[label_int]) ** 2, dim=1).mean())
        if label_int == attack_label:
            for other in nonattack_labels:
                if other in centers:
                    d = torch.sum((z_norm[held_mask] - centers[other].view(1, -1)) ** 2, dim=1)
                    push_terms.append(F.relu(float(spec.prototype_margin) - d).mean())
        elif attack_label in centers:
            d = torch.sum((z_norm[held_mask] - centers[attack_label].view(1, -1)) ** 2, dim=1)
            push_terms.append(F.relu(float(spec.prototype_margin) - d).mean())

    if not pull_terms and not push_terms:
        return torch.zeros((), dtype=torch.float32, device=z.device)
    pull = torch.stack(pull_terms).mean() if pull_terms else torch.zeros((), dtype=torch.float32, device=z.device)
    push = torch.stack(push_terms).mean() if push_terms else torch.zeros((), dtype=torch.float32, device=z.device)
    return pull + push


def pseudoheld_episode_losses(
    logits: Any,
    z: Any,
    y: Any,
    group_ids: Any,
    ce_vec: Any,
    spec: EpisodeSpec,
) -> tuple[Any, Any, Any, Any, int]:
    if not spec.enabled:
        zero = torch.zeros((), dtype=torch.float32, device=logits.device)
        return zero, zero, zero, zero, 0

    attack_logit = logits[:, ckh.CLASS_ATTACK]
    nonattack = torch.logsumexp(logits[:, [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD]], dim=1)
    attack_mask = y == ckh.CLASS_ATTACK
    margin_vec = torch.where(
        attack_mask,
        F.relu(float(spec.logit_margin) - (attack_logit - nonattack)),
        F.relu(float(spec.logit_margin) - (nonattack - attack_logit)),
    )
    sample_risk = ce_vec + margin_vec

    risks = []
    proto_terms = []
    for group_value in torch.unique(group_ids):
        mask = group_ids == group_value
        if int(mask.sum().item()) < spec.min_group_rows:
            continue
        risks.append(sample_risk[mask].mean())
        proto_terms.append(_prototype_episode_loss(z, y, group_ids, group_value, spec))

    if not risks:
        zero = torch.zeros((), dtype=torch.float32, device=logits.device)
        return zero, zero, zero, zero, 0

    risk_t = torch.stack(risks)
    episode_mean = risk_t.mean()
    episode_rex = torch.var(risk_t, unbiased=False) if len(risks) >= 2 else torch.zeros((), dtype=torch.float32, device=logits.device)
    episode_worst = torch.max(risk_t)
    prototype = torch.stack(proto_terms).mean() if proto_terms else torch.zeros((), dtype=torch.float32, device=logits.device)
    return episode_mean, episode_rex, episode_worst, prototype, len(risks)


def fit_map_candidate(
    candidate: ckaa.MapCandidate,
    frontend: cky.InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    split: str,
    held_value: str,
    exclude: tuple[str, str] | None = None,
) -> tuple[ckaa.FittedMap, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ckaa.ensure_torch()
    spec = EPISODE_SPECS[candidate.name]
    x_mech, x_ctx, y, envs, families, roles, audit = build_train_set_with_meta(frontend, frame_by_role, train_cap, exclude=exclude)
    env_id, env_mapping = ckaa.env_to_ids(envs)
    family_id, family_mapping = _factorize(families)

    mech_mean, mech_std = ckaa.standardize_fit(x_mech)
    ctx_mean, ctx_std = ckaa.standardize_fit(x_ctx)
    xm = torch.from_numpy(ckaa.standardize_apply(x_mech, mech_mean, mech_std))
    xc = torch.from_numpy(ckaa.standardize_apply(x_ctx, ctx_mean, ctx_std))
    yt = torch.from_numpy(y.astype(np.int64))
    et = torch.from_numpy(env_id.astype(np.int64))
    gt = torch.from_numpy(family_id.astype(np.int64))
    weights = ckaa.class_weights(y)

    model = ckaa.InteractionMapNet(x_mech.shape[1], x_ctx.shape[1], candidate.hidden_dim, candidate.map_dim, len(env_mapping), candidate.dropout)
    opt = torch.optim.AdamW(model.parameters(), lr=candidate.lr, weight_decay=candidate.weight_decay)
    history: list[dict[str, Any]] = []
    use_domain = candidate.adv_lambda > 0.0 and len(env_mapping) > 1

    for epoch in range(1, candidate.epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        logits, domain_logits, z = model(xm, xc, candidate.adv_lambda if use_domain else 0.0)
        ce_vec = F.cross_entropy(logits, yt, weight=weights, reduction="none")
        cls_loss = ce_vec.mean()
        contrast_loss = ckaa.center_contrastive_loss(z, yt, candidate.contrast_margin) if candidate.contrast_lambda > 0.0 else torch.zeros((), dtype=torch.float32)

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

        domain_loss = F.cross_entropy(domain_logits, et) if use_domain else torch.zeros((), dtype=torch.float32)
        epi_mean, epi_rex, epi_worst, epi_proto, episode_count = pseudoheld_episode_losses(logits, z, yt, gt, ce_vec, spec)

        loss = (
            cls_loss
            + candidate.contrast_lambda * contrast_loss
            + candidate.adv_lambda * domain_loss
            + candidate.rex_lambda * rex_loss
            + candidate.worst_group_lambda * worst_loss
            + spec.episode_lambda * epi_mean
            + spec.episode_rex_lambda * epi_rex
            + spec.episode_worst_lambda * epi_worst
            + spec.prototype_lambda * epi_proto
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()

        if epoch == 1 or epoch == candidate.epochs or epoch % 10 == 0:
            pred = torch.argmax(logits.detach(), dim=1)
            history.append(
                {
                    "candidate": candidate.name,
                    "episode_spec": spec.name,
                    "split": split,
                    "held_value": held_value,
                    "epoch": epoch,
                    "loss": float(loss.detach().cpu().item()),
                    "cls_loss": float(cls_loss.detach().cpu().item()),
                    "contrast_loss": float(contrast_loss.detach().cpu().item()),
                    "domain_loss": float(domain_loss.detach().cpu().item()),
                    "rex_loss": float(rex_loss.detach().cpu().item()),
                    "worst_group_loss": float(worst_loss.detach().cpu().item()),
                    "episode_mean_loss": float(epi_mean.detach().cpu().item()),
                    "episode_rex_loss": float(epi_rex.detach().cpu().item()),
                    "episode_worst_loss": float(epi_worst.detach().cpu().item()),
                    "episode_prototype_loss": float(epi_proto.detach().cpu().item()),
                    "episode_groups": int(episode_count),
                    "train_accuracy": float((pred == yt).float().mean().cpu().item()),
                    "train_rows": int(len(y)),
                    "mech_dim": int(x_mech.shape[1]),
                    "ctx_dim": int(x_ctx.shape[1]),
                    "map_dim": int(candidate.map_dim),
                    "env_classes": int(len(env_mapping)),
                    "family_classes": int(len(family_mapping)),
                }
            )

    fitted = ckaa.FittedMap(
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
    center_rows = ckaa.latent_center_rows(candidate.name, split, held_value, latent, y, "fit_train")

    family_counts = pd.Series(families, dtype="object").value_counts()
    family_rows = [
        {
            "candidate": candidate.name,
            "split": split,
            "held_value": held_value,
            "env_key": str(key),
            "rows": int(value),
            "mapped_id": int(family_mapping.get(str(key), -1)),
            "used_for": "pseudoheld_episode_fit_only",
            "episode_spec": spec.name,
        }
        for key, value in family_counts.items()
    ]
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
            "episode_spec": spec.name,
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
        row["episode_spec"] = spec.name
        row["episode_group_field"] = spec.group_field
        row["episode_lambda"] = spec.episode_lambda
        row["episode_rex_lambda"] = spec.episode_rex_lambda
        row["episode_worst_lambda"] = spec.episode_worst_lambda
        row["episode_prototype_lambda"] = spec.prototype_lambda
    return fitted, audit, history + family_rows + env_rows, center_rows


_ORIGINAL_BUILD_READOUT = ckaa.build_readout


def build_readout(main_rows: list[dict[str, Any]], leave_rows: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = _ORIGINAL_BUILD_READOUT(main_rows, leave_rows, threshold_rows, seconds)
    if lines:
        lines[0] = "# issue27ckab pseudo-held episodic representation map v1"
    insert_at = 2 if len(lines) > 2 else len(lines)
    lines[insert_at:insert_at] = [
        "",
        "## CKAB addition",
        "",
        "- B0 is an A3 replay control under the same code path.",
        "- B1/B2 add legal-fit-only pseudo-held device-family episode pressure.",
        "- The episode loss uses only fit labels and never uses query/future/sealed rows.",
    ]
    return lines


def configure_ckaa_patch() -> None:
    ckaa.ISSUE = ISSUE
    ckaa.OUT = OUT
    ckaa.CANDIDATES = CANDIDATES
    ckaa.fit_map_candidate = fit_map_candidate
    ckaa.build_readout = build_readout


def run(args: argparse.Namespace) -> None:
    configure_ckaa_patch()
    ckaa.run(args)
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    spec_path = out / "run_spec.json"
    if spec_path.exists():
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["issue"] = ISSUE
        spec["scope"] = "pseudo-held episodic interaction/causal representation map"
        spec["episode_specs"] = {name: asdict(value) for name, value in EPISODE_SPECS.items()}
        spec["data_use_boundary"]["pseudoheld_episode_roles"] = ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"]
        spec["representation_contract"]["pseudoheld_episode_training"] = "leave-one-device-family pressure constructed only within legal fit roles"
        cko.write_json(spec_path, spec)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=768)
    parser.add_argument("--source-cap", type=int, default=48)
    parser.add_argument("--train-cap", type=int, default=512)
    parser.add_argument("--eval-cap", type=int, default=768)
    parser.add_argument("--benign-q", type=float, default=BENIGN_SAFE_Q)
    parser.add_argument("--candidates", default="B0_a3_replay_control,B1_pseudoheld_episode_map")
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
