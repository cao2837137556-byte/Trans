"""issue27ckn: deep invariant mechanism learning v1.

This is the first non-shallow method experiment after CKL/CKM.

Scope:
- keep strict role separation;
- compare C4 raw115 HistGB with a small raw115 neural encoder;
- add a domain-adversarial variant that tries to keep attack/OOD information
  while suppressing device/source-family information in the learned embedding.

This is causal-inspired invariant representation learning, not a full causal
discovery claim.  No support_val/query/future/sealed-final row is used for
training the detector, scaler, adversary, threshold, or representation probe.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cki_c4_full_data_multiclass_replay as cki  # noqa: E402
import issue27ckj_c4_stability_and_shortcut_anatomy as ckj  # noqa: E402


ISSUE = "issue27ckn_deep_invariant_mechanism_learning_v1_2026-06-26"
OUT = ROOT / "runs" / ISSUE

TRAIN_CAP = 20_000
FULL_CAP = cki.FULL_CAP
SEEDS = [42, 43, 44]
EPOCHS = 24
SMOKE_EPOCHS = 4
BATCH_SIZE = 1024
LR = 1e-3
WEIGHT_DECAY = 1e-4
DEVICE = torch.device("cpu")
PROBE_CAP_PER_ROLE = 20_000


@dataclass(frozen=True)
class ModelSpec:
    name: str
    kind: str
    env_field: str | None
    adv_lambda: float
    description: str


SPECS = [
    ModelSpec("C0_c4_histgb", "histgb", None, 0.0, "C4 raw115 HistGB control."),
    ModelSpec("N1_mlp_erm", "neural", None, 0.0, "raw115 -> small encoder -> four-class head."),
    ModelSpec(
        "N2_dann_device_family",
        "neural",
        "device_family",
        0.20,
        "small encoder with gradient-reversal adversary on device_family.",
    ),
    ModelSpec(
        "N3_dann_source_family",
        "neural",
        "source_family",
        0.20,
        "small encoder with gradient-reversal adversary on source_family.",
    ),
]

LEAVEOUT_SPEC_NAMES = {"C0_c4_histgb", "N1_mlp_erm", "N2_dann_device_family"}


class GradReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx: Any, x: torch.Tensor, lambd: float) -> torch.Tensor:
        ctx.lambd = float(lambd)
        return x.view_as(x)

    @staticmethod
    def backward(ctx: Any, grad_output: torch.Tensor) -> tuple[torch.Tensor, None]:
        return -ctx.lambd * grad_output, None


def grl(x: torch.Tensor, lambd: float) -> torch.Tensor:
    return GradReverse.apply(x, lambd)


class InvariantNet(nn.Module):
    def __init__(self, input_dim: int, num_classes: int, num_envs: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 96),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(96, 48),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(48, num_classes)
        self.adversary = nn.Sequential(
            nn.Linear(48, 48),
            nn.ReLU(),
            nn.Linear(48, max(1, num_envs)),
        )

    def forward(self, x: torch.Tensor, adv_lambda: float = 0.0) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        z = self.encoder(x)
        class_logits = self.classifier(z)
        env_logits = self.adversary(grl(z, adv_lambda))
        return class_logits, env_logits, z


@dataclass
class Scaler:
    mean: np.ndarray
    scale: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        out = (np.asarray(x, dtype=np.float32) - self.mean) / self.scale
        return np.nan_to_num(out, nan=0.0, posinf=8.0, neginf=-8.0).astype(np.float32)


@dataclass
class Fitted:
    spec: ModelSpec
    seed: int
    model: Any
    scaler: Scaler | None
    env_to_id: dict[str, int]
    id_to_env: dict[int, str]
    training_history: list[dict[str, Any]]


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def idx_for(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int = FULL_CAP,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    frame = frame_by_role[role]
    idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].to_numpy() == phase)
    if include is not None and include[0] in frame:
        field, value = include
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() == str(value)]
    if exclude is not None and exclude[0] in frame:
        field, value = exclude
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() != str(value)]
    return ckh.deterministic_cap(idx, cap)


def env_values(frame_by_role: dict[str, pd.DataFrame], role: str, idx: np.ndarray, env_field: str | None) -> np.ndarray:
    if env_field is None or env_field not in frame_by_role[role]:
        return np.asarray(["ALL"] * len(idx), dtype=object)
    vals = frame_by_role[role].iloc[idx][env_field].astype(str).to_numpy(dtype=object)
    vals[(vals == "") | (vals == "nan")] = "NA"
    return vals


def candidate_name(spec: ModelSpec, seed: int, suffix: str = "") -> str:
    return f"CKN_{spec.name}_seed{seed}{suffix}"


def build_training_arrays(
    spec: ModelSpec,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    envs: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = idx_for(frame_by_role, role, phase, cap, exclude=exclude)
        x = np.asarray(x_by_role[role][idx], dtype=np.float32)
        env = env_values(frame_by_role, role, idx, spec.env_field)
        xs.append(x)
        ys.append(np.full(len(idx), int(label), dtype=np.int64))
        envs.append(env)
        audit.append(
            {
                "variant": spec.name,
                "env_field": spec.env_field or "",
                "role": role,
                "phase": phase,
                "label": label,
                "rows": len(idx),
                "unique_envs": int(len(set(env.tolist()))) if len(env) else 0,
            }
        )

    add("support_train", "fit", ckh.CLASS_ATTACK, FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, TRAIN_CAP)
    add("ood_val", "fit", ckh.CLASS_OOD, TRAIN_CAP)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, TRAIN_CAP)
    return np.vstack(xs), np.concatenate(ys), np.concatenate(envs), audit


def fit_scaler(x: np.ndarray) -> Scaler:
    mean = np.mean(x, axis=0).astype(np.float32)
    scale = np.std(x, axis=0).astype(np.float32)
    scale[scale <= 1e-6] = 1.0
    return Scaler(mean=mean, scale=scale)


def class_weights(y: np.ndarray) -> torch.Tensor:
    counts = np.bincount(y.astype(np.int64), minlength=4).astype(np.float64)
    counts[counts <= 0] = 1.0
    weights = 1.0 / counts
    weights *= len(weights) / np.sum(weights)
    return torch.tensor(weights, dtype=torch.float32, device=DEVICE)


def env_weights(env_id: np.ndarray, num_envs: int) -> torch.Tensor:
    counts = np.bincount(env_id.astype(np.int64), minlength=max(1, num_envs)).astype(np.float64)
    counts[counts <= 0] = 1.0
    weights = 1.0 / counts
    weights *= len(weights) / np.sum(weights)
    return torch.tensor(weights, dtype=torch.float32, device=DEVICE)


def fit_histgb(spec: ModelSpec, seed: int, x_train: np.ndarray, y_train: np.ndarray) -> Any:
    old_seed = ckh.SEED
    ckh.SEED = int(seed)
    try:
        model = ckh.build_model("histgb_shallow", multiclass=True)
        counts = {label: int(np.sum(y_train == label)) for label in np.unique(y_train)}
        weights = np.asarray([1.0 / max(1, counts[int(label)]) for label in y_train], dtype=np.float64)
        weights *= len(weights) / max(1e-12, float(np.sum(weights)))
        model.fit(np.asarray(x_train, dtype=np.float32), y_train, sample_weight=weights)
        return model
    finally:
        ckh.SEED = old_seed


def fit_neural(
    spec: ModelSpec,
    seed: int,
    x_train_raw: np.ndarray,
    y_train: np.ndarray,
    env: np.ndarray,
    epochs: int,
) -> tuple[InvariantNet, Scaler, dict[str, int], dict[int, str], list[dict[str, Any]]]:
    torch.manual_seed(int(seed))
    np.random.seed(int(seed))
    scaler = fit_scaler(x_train_raw)
    x_train = scaler.transform(x_train_raw)
    env_labels = sorted(set(env.astype(str).tolist()))
    env_to_id = {label: i for i, label in enumerate(env_labels)}
    id_to_env = {i: label for label, i in env_to_id.items()}
    env_id = np.asarray([env_to_id[str(label)] for label in env], dtype=np.int64)

    ds = TensorDataset(
        torch.tensor(x_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long),
        torch.tensor(env_id, dtype=torch.long),
    )
    # The attack support class is intentionally few-shot.  For a neural head,
    # class-weighted loss alone can still leave the rare attack minibatches too
    # sparse, so we use class-balanced sampling as the legal analogue of the
    # sample_weight contract used by the HistGB control.  This does not add any
    # report/query/final rows to fitting; it only changes how the allowed fit
    # rows are replayed during SGD.
    cls_counts = np.bincount(np.asarray(y_train, dtype=np.int64), minlength=4)
    cls_counts = np.maximum(cls_counts, 1)
    sample_weights = np.asarray([1.0 / cls_counts[int(label)] for label in y_train], dtype=np.float64)
    sample_weights *= len(sample_weights) / max(1e-12, float(sample_weights.sum()))
    sampler = WeightedRandomSampler(
        weights=torch.tensor(sample_weights, dtype=torch.double),
        num_samples=len(sample_weights),
        replacement=True,
    )
    loader = DataLoader(ds, batch_size=BATCH_SIZE, sampler=sampler, drop_last=False)
    model = InvariantNet(input_dim=x_train.shape[1], num_classes=4, num_envs=len(env_to_id)).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    main_loss_fn = nn.CrossEntropyLoss(weight=class_weights(y_train))
    env_loss_fn = nn.CrossEntropyLoss(weight=env_weights(env_id, len(env_to_id)))
    history: list[dict[str, Any]] = []

    for epoch in range(1, epochs + 1):
        model.train()
        total = 0
        main_sum = 0.0
        env_sum = 0.0
        correct = 0
        env_correct = 0
        for xb, yb, eb in loader:
            xb = xb.to(DEVICE)
            yb = yb.to(DEVICE)
            eb = eb.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            logits, env_logits, _z = model(xb, spec.adv_lambda)
            main_loss = main_loss_fn(logits, yb)
            if spec.env_field is not None and spec.adv_lambda > 0:
                env_loss = env_loss_fn(env_logits, eb)
                loss = main_loss + env_loss
            else:
                env_loss = torch.zeros((), dtype=torch.float32, device=DEVICE)
                loss = main_loss
            loss.backward()
            opt.step()
            n = len(xb)
            total += n
            main_sum += float(main_loss.detach().cpu()) * n
            env_sum += float(env_loss.detach().cpu()) * n
            correct += int((logits.argmax(dim=1) == yb).sum().detach().cpu())
            env_correct += int((env_logits.argmax(dim=1) == eb).sum().detach().cpu())
        history.append(
            {
                "epoch": epoch,
                "main_loss": main_sum / max(1, total),
                "env_loss": env_sum / max(1, total),
                "train_acc": correct / max(1, total),
                "env_acc": env_correct / max(1, total),
            }
        )
    return model, scaler, env_to_id, id_to_env, history


def fit_spec(
    spec: ModelSpec,
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    epochs: int,
    exclude: tuple[str, str] | None = None,
    suffix: str = "",
) -> tuple[str, Fitted, list[dict[str, Any]], list[dict[str, Any]]]:
    x_train, y_train, env, audit = build_training_arrays(spec, x_by_role, frame_by_role, exclude=exclude)
    name = candidate_name(spec, seed, suffix)
    if spec.kind == "histgb":
        model = fit_histgb(spec, seed, x_train, y_train)
        fitted = Fitted(spec, seed, model, None, {"ALL": 0}, {0: "ALL"}, [])
    else:
        model, scaler, env_to_id, id_to_env, history = fit_neural(spec, seed, x_train, y_train, env, epochs)
        fitted = Fitted(spec, seed, model, scaler, env_to_id, id_to_env, history)
    train_rows = [{**row, "candidate": name, "seed": seed, "kind": spec.kind, "adv_lambda": spec.adv_lambda} for row in audit]
    hist_rows = [{**row, "candidate": name, "seed": seed, "variant": spec.name} for row in fitted.training_history]
    return name, fitted, train_rows, hist_rows


def features_for(fitted: Fitted, role: str, idx: np.ndarray, x_by_role: dict[str, np.ndarray]) -> np.ndarray:
    raw = np.asarray(x_by_role[role][idx], dtype=np.float32)
    if fitted.scaler is None:
        return raw
    return fitted.scaler.transform(raw)


def neural_scores(fitted: Fitted, x: np.ndarray, batch_size: int = 8192) -> tuple[dict[str, np.ndarray], np.ndarray]:
    assert isinstance(fitted.model, InvariantNet)
    fitted.model.eval()
    probs: list[np.ndarray] = []
    zs: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x), batch_size):
            xb = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=DEVICE)
            logits, _env_logits, z = fitted.model(xb, 0.0)
            probs.append(torch.softmax(logits, dim=1).cpu().numpy())
            zs.append(z.cpu().numpy())
    proba = np.vstack(probs) if probs else np.zeros((0, 4), dtype=np.float32)
    z_all = np.vstack(zs) if zs else np.zeros((0, 48), dtype=np.float32)
    identity = proba[:, ckh.CLASS_ID]
    ordinary_ood = proba[:, ckh.CLASS_OOD]
    hard_ood = proba[:, ckh.CLASS_HARD_OOD]
    attack = proba[:, ckh.CLASS_ATTACK]
    return {
        "attack_score": attack.astype(np.float64),
        "hard_ood_score": hard_ood.astype(np.float64),
        "conflict_score": np.maximum.reduce([identity, ordinary_ood, hard_ood]).astype(np.float64),
    }, z_all


def decision_scores(fitted: Fitted, role: str, idx: np.ndarray, x_by_role: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    x = features_for(fitted, role, idx, x_by_role)
    if fitted.spec.kind == "histgb":
        cand = ckh.Candidate("tmp", "fewshot_direct", "raw115", "multiclass_id_ood_hardood_attack", "histgb_shallow", "")
        score = ckh.decision_scores(cand, {"multiclass_model": fitted.model}, x)
        return score, x
    return neural_scores(fitted, x)


def thresholds_for(
    fitted: Fitted,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> dict[str, Any]:
    scores: list[np.ndarray] = []
    roles: list[str] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = idx_for(frame_by_role, role, "select", FULL_CAP, exclude=exclude)
        if len(idx) == 0:
            continue
        score, _z = decision_scores(fitted, role, idx, x_by_role)
        scores.append(score["attack_score"])
        roles.append(role)
    if not scores:
        raise RuntimeError(f"No threshold rows for {fitted.spec.name} after exclusion {exclude}")
    return {
        "attack_threshold": float(max(np.quantile(score, ckh.BENIGN_SAFE_Q) for score in scores)),
        "hard_ood_gate": float("nan"),
        "threshold_roles": "|".join(roles),
    }


def decide_part(
    name: str,
    fitted: Fitted,
    thresholds: dict[str, Any],
    role: str,
    phase: str,
    role_kind: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> pd.DataFrame:
    idx = idx_for(frame_by_role, role, phase, FULL_CAP, include=include, exclude=exclude)
    frame = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    frame["candidate"] = name
    frame["variant"] = fitted.spec.name
    frame["role_kind"] = role_kind
    if len(idx) == 0:
        for col in ["attack_score", "hard_ood_score", "conflict_score"]:
            frame[col] = pd.Series(dtype=float)
        for col in ["candidate_raw_alarm", "candidate_conflict_review", "candidate_hard_alarm"]:
            frame[col] = pd.Series(dtype=bool)
        return frame
    score, _z = decision_scores(fitted, role, idx, x_by_role)
    raw = score["attack_score"] > float(thresholds["attack_threshold"])
    review = raw & (score["conflict_score"] > score["attack_score"])
    hard = raw & ~review
    frame["attack_score"] = score["attack_score"]
    frame["hard_ood_score"] = score["hard_ood_score"]
    frame["conflict_score"] = score["conflict_score"]
    frame["candidate_raw_alarm"] = raw
    frame["candidate_conflict_review"] = review
    frame["candidate_hard_alarm"] = hard
    return frame


def summarize_part(
    name: str,
    fitted: Fitted,
    split: str,
    seed: int,
    role: str,
    phase: str,
    part: pd.DataFrame,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    rows = len(part)
    return {
        "candidate": name,
        "variant": fitted.spec.name,
        "kind": fitted.spec.kind,
        "env_field": fitted.spec.env_field or "",
        "adv_lambda": fitted.spec.adv_lambda,
        "split": split,
        "seed": seed,
        "role": role,
        "phase": phase,
        "rows": rows,
        "attack_threshold": thresholds["attack_threshold"],
        "raw_alarm_rate": ckh.rate(part["candidate_raw_alarm"]) if rows else float("nan"),
        "conflict_review_rate": ckh.rate(part["candidate_conflict_review"]) if rows else float("nan"),
        "hard_alarm_rate": ckh.rate(part["candidate_hard_alarm"]) if rows else float("nan"),
        "review_count": int(np.sum(part["candidate_conflict_review"].to_numpy(dtype=bool))) if rows else 0,
        "hard_count": int(np.sum(part["candidate_hard_alarm"].to_numpy(dtype=bool))) if rows else 0,
        "attack_score_mean": float(part["attack_score"].mean()) if rows else float("nan"),
        "conflict_score_mean": float(part["conflict_score"].mean()) if rows else float("nan"),
    }


def eval_all_roles(
    name: str,
    fitted: Fitted,
    thresholds: dict[str, Any],
    seed: int,
    split: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    parts: dict[str, pd.DataFrame] = {}
    for role, phase, role_kind in ckh.ROLE_EVAL:
        part = decide_part(name, fitted, thresholds, role, phase, role_kind, x_by_role, frame_by_role, include=include, exclude=exclude)
        rows.append(summarize_part(name, fitted, split, seed, role, phase, part, thresholds))
        parts[role] = part
    return rows, parts


def grouped_anatomy(parts: dict[str, pd.DataFrame], split: str, seed: int) -> list[dict[str, Any]]:
    return ckj.grouped_anatomy(
        parts,
        ["source_group", "source_family", "device_family", "time_block", "attack_label", "attack_family", "support_seen"],
        split,
        seed,
    )


def aggregate_matrix(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(role_rows)
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for variant, group in df[df["split"] == "main"].groupby("variant", sort=True):
        def val(role: str, col: str, fn: str = "mean") -> float:
            vals = pd.to_numeric(group[group["role"] == role][col], errors="coerce")
            if vals.empty:
                return float("nan")
            if fn == "min":
                return float(vals.min())
            if fn == "max":
                return float(vals.max())
            return float(vals.mean())

        rows.append(
            {
                "variant": variant,
                "seeds": int(group["seed"].nunique()),
                "future_hard_mean": val("future_query", "hard_alarm_rate"),
                "future_hard_min": val("future_query", "hard_alarm_rate", "min"),
                "future_review_mean": val("future_query", "conflict_review_rate"),
                "sealed_attack_hard_mean": val("sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_hard_min": val("sealed_final_attack", "hard_alarm_rate", "min"),
                "sealed_attack_review_mean": val("sealed_final_attack", "conflict_review_rate"),
                "sealed_ood_hard_mean": val("sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_hard_max": val("sealed_final_ood", "hard_alarm_rate", "max"),
                "sealed_ood_review_mean": val("sealed_final_ood", "conflict_review_rate"),
                "sealed_ood_review_max": val("sealed_final_ood", "conflict_review_rate", "max"),
                "ood_stress_hard_max": val("ood_stress", "hard_alarm_rate", "max"),
                "ood_stress_review_mean": val("ood_stress", "conflict_review_rate"),
            }
        )
    return rows


def safe_bal_acc(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return float(balanced_accuracy_score(y_true, y_pred))


def embedding_for_role(
    fitted: Fitted,
    role: str,
    phase: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    cap: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    idx = idx_for(frame_by_role, role, phase, cap)
    if fitted.spec.kind == "histgb":
        z = np.asarray(x_by_role[role][idx], dtype=np.float32)
    else:
        x = features_for(fitted, role, idx, x_by_role)
        _score, z = neural_scores(fitted, x)
    return z, frame_by_role[role].iloc[idx].copy().reset_index(drop=True)


def probe_embedding(
    variant: str,
    fitted: Fitted,
    target_field: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    xs: list[np.ndarray] = []
    ys: list[str] = []
    roles_used: list[str] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        if target_field not in frame_by_role[role]:
            continue
        z, frame = embedding_for_role(fitted, role, "fit", x_by_role, frame_by_role, PROBE_CAP_PER_ROLE)
        y = frame[target_field].astype(str).to_numpy()
        keep = y != "NA"
        if np.any(keep):
            xs.append(z[keep])
            ys.extend(y[keep].tolist())
            roles_used.append(f"{role}:fit:{int(np.sum(keep))}")
    if not xs or len(set(ys)) < 2:
        return []
    model = HistGradientBoostingClassifier(
        max_iter=50,
        learning_rate=0.05,
        max_leaf_nodes=8,
        l2_regularization=0.1,
        random_state=fitted.seed,
    )
    train_labels = sorted(set(ys))
    model.fit(np.vstack(xs), np.asarray(ys, dtype=object))
    rows: list[dict[str, Any]] = []
    for role, phase in [("ood_stress", "select"), ("sealed_final_ood", "all")]:
        if target_field not in frame_by_role[role]:
            continue
        z, frame = embedding_for_role(fitted, role, phase, x_by_role, frame_by_role, FULL_CAP)
        y_true = frame[target_field].astype(str).to_numpy()
        keep = y_true != "NA"
        if not np.any(keep):
            continue
        y_eval = y_true[keep]
        y_pred = model.predict(z[keep])
        known = np.isin(y_eval, train_labels)
        known_rows = int(np.sum(known))
        unknown_rows = int(len(y_eval) - known_rows)
        if known_rows:
            known_acc = float(accuracy_score(y_eval[known], y_pred[known]))
            known_bal = safe_bal_acc(y_eval[known], y_pred[known])
        else:
            known_acc = float("nan")
            known_bal = float("nan")
        rows.append(
            {
                "variant": variant,
                "target_field": target_field,
                "train_roles": "|".join(roles_used),
                "eval_role": role,
                "eval_phase": phase,
                "rows": int(len(y_eval)),
                "known_label_rows": known_rows,
                "unknown_label_rows": unknown_rows,
                "known_label_rate": float(known_rows / max(1, len(y_eval))),
                "accuracy": float(accuracy_score(y_eval, y_pred)),
                "balanced_accuracy": safe_bal_acc(y_eval, y_pred),
                "known_accuracy": known_acc,
                "known_balanced_accuracy": known_bal,
            }
        )
    return rows


def select_leave_groups(max_groups: int) -> dict[str, list[str]]:
    for path in [
        ROOT / "runs" / "issue27ckm_group_invariant_training_v1_2026-06-26" / "run_spec.json",
        ROOT / "runs" / "issue27ckk_group_balanced_worst_group_c4_2026-06-25" / "run_spec.json",
        ROOT / "runs" / "issue27ckj_c4_stability_and_shortcut_anatomy_2026-06-25" / "run_spec.json",
    ]:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        groups = payload.get("selected_leave_groups") or payload.get("leave_groups_from_issue27ckj") or {}
        device = list(groups.get("device_family", []))[:max_groups]
        if device:
            return {"device_family": device}
    return {"device_family": []}


def eval_leaveout(
    specs: list[ModelSpec],
    groups: dict[str, list[str]],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    epochs: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    seed = SEEDS[0]
    rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    leave_specs = [spec for spec in specs if spec.name in {"C0_c4_histgb", "N1_mlp_erm", "N2_dann_device_family"}]
    for value in groups.get("device_family", []):
        held = ("device_family", value)
        for spec in leave_specs:
            name, fitted, audit, hist = fit_spec(spec, seed, x_by_role, frame_by_role, epochs, exclude=held, suffix=f"_leave_{slug(value)}")
            thresholds = thresholds_for(fitted, x_by_role, frame_by_role, exclude=held)
            for item in audit:
                train_rows.append({**item, "split": "leave_device_family", "held_field": "device_family", "held_value": value})
            for item in hist:
                history_rows.append({**item, "split": "leave_device_family", "held_field": "device_family", "held_value": value})
            eval_rows, _parts = eval_all_roles(name, fitted, thresholds, seed, "leave_device_family", x_by_role, frame_by_role, include=held)
            for row in eval_rows:
                row["held_field"] = "device_family"
                row["held_value"] = value
            rows.extend(eval_rows)
    return rows, train_rows, history_rows


def build_readout(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckn deep invariant mechanism learning v1",
        "",
        "## Scope",
        "",
        "Causal-inspired invariant representation diagnostic. C0 is C4 raw115 HistGB; N1/N2/N3 are small neural encoders.",
        "No report-only role is used for detector/scaler/adversary/probe/threshold fitting.",
        "",
        "## Main matrix",
        "",
        "| variant | future hard mean/min | future review | sealed attack hard mean/min | sealed attack review | sealed OOD hard mean/max | sealed OOD review mean/max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['variant']} | {ckh.fmt(row['future_hard_mean'])}/{ckh.fmt(row['future_hard_min'])} | "
            f"{ckh.fmt(row['future_review_mean'])} | {ckh.fmt(row['sealed_attack_hard_mean'])}/{ckh.fmt(row['sealed_attack_hard_min'])} | "
            f"{ckh.fmt(row['sealed_attack_review_mean'])} | {ckh.fmt(row['sealed_ood_hard_mean'])}/{ckh.fmt(row['sealed_ood_hard_max'])} | "
            f"{ckh.fmt(row['sealed_ood_review_mean'])}/{ckh.fmt(row['sealed_ood_review_max'])} |"
        )
    lines.extend(["", "## Leave-device-family stress", ""])
    lines.extend(["| variant | held value | role | rows | hard | review | raw |", "|---|---|---|---:|---:|---:|---:|"])
    for row in leave_rows:
        if int(row.get("rows", 0)) == 0 or row.get("role") not in {"ood_val", "ood_stress", "sealed_final_ood"}:
            continue
        lines.append(
            f"| {row['variant']} | {str(row.get('held_value', ''))[:60]} | {row['role']} | {row['rows']} | "
            f"{ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {ckh.fmt(row['raw_alarm_rate'])} |"
        )
    lines.extend(["", "## Representation shortcut probe", ""])
    lines.extend(
        [
            "| variant | target | eval role | known label rate | known-label balanced acc | all-label balanced acc |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for row in probe_rows:
        if row.get("eval_role") not in {"ood_stress", "sealed_final_ood"}:
            continue
        lines.append(
            f"| {row['variant']} | {row['target_field']} | {row['eval_role']} | "
            f"{ckh.fmt(row.get('known_label_rate'))} | {ckh.fmt(row.get('known_balanced_accuracy'))} | "
            f"{ckh.fmt(row.get('balanced_accuracy'))} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- A valid deep invariant improvement must reduce sealed OOD review/hard without sacrificing sealed/future attack hard detection.",
            "- It must reduce leave-device-family collapse.",
            "- Lower domain-probe accuracy is useful only if detection guardrails also pass.",
            "- This is causal-inspired invariant representation learning, not a full causal discovery claim.",
            "",
            f"Runtime seconds: `{ckh.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def build_interpretation(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]]) -> list[str]:
    lines = ["# issue27ckn diagnostic interpretation", "", "## Verdict", ""]
    df = pd.DataFrame(matrix)
    if df.empty:
        return lines + ["No matrix rows were produced."]
    base = df[df["variant"] == "C0_c4_histgb"]
    if base.empty:
        return lines + ["No C0 baseline row was produced."]
    base_row = base.iloc[0]
    candidates = df[df["variant"] != "C0_c4_histgb"].copy()
    lines.append("This run is the first deep representation test after shallow feature/reweighting failures.")
    lines.append("")
    if not candidates.empty:
        candidates["passes_guardrail"] = (
            (candidates["sealed_ood_review_mean"].astype(float) < float(base_row["sealed_ood_review_mean"]))
            & (candidates["sealed_ood_hard_max"].astype(float) <= float(base_row["sealed_ood_hard_max"]) + 0.002)
            & (candidates["sealed_attack_hard_mean"].astype(float) >= float(base_row["sealed_attack_hard_mean"]) - 0.005)
            & (candidates["future_hard_mean"].astype(float) >= float(base_row["future_hard_mean"]) - 0.005)
        )
        if bool(candidates["passes_guardrail"].any()):
            best = candidates[candidates["passes_guardrail"]].sort_values("sealed_ood_review_mean").iloc[0]
            lines.append(f"Best guardrail-passing candidate: `{best['variant']}`.")
        else:
            lines.append("No neural invariant candidate passes the conservative detection guardrail.")
    lines.append("")
    for _, row in df.sort_values("variant").iterrows():
        if row["variant"] == "C0_c4_histgb":
            continue
        lines.append(
            f"- `{row['variant']}` vs C0: sealed OOD review delta "
            f"`{ckh.fmt(float(row['sealed_ood_review_mean']) - float(base_row['sealed_ood_review_mean']))}`, "
            f"sealed OOD hard-max delta `{ckh.fmt(float(row['sealed_ood_hard_max']) - float(base_row['sealed_ood_hard_max']))}`, "
            f"sealed attack hard delta `{ckh.fmt(float(row['sealed_attack_hard_mean']) - float(base_row['sealed_attack_hard_mean']))}`, "
            f"future hard delta `{ckh.fmt(float(row['future_hard_mean']) - float(base_row['future_hard_mean']))}`."
        )
    leave = pd.DataFrame(leave_rows)
    if not leave.empty:
        risky = leave[(leave["role"].isin(["ood_val", "ood_stress", "sealed_final_ood"])) & (pd.to_numeric(leave["rows"], errors="coerce") > 0)].copy()
        if not risky.empty:
            risky["hard_alarm_rate"] = pd.to_numeric(risky["hard_alarm_rate"], errors="coerce")
            worst = risky.sort_values("hard_alarm_rate", ascending=False).iloc[0]
            lines.extend(["", "## Leave-device-family risk", ""])
            lines.append(
                f"Worst held-family hard alarm: `{worst['variant']}` / `{worst['held_value']}` / `{worst['role']}` = `{ckh.fmt(worst['hard_alarm_rate'])}`."
            )
    probe = pd.DataFrame(probe_rows)
    if not probe.empty:
        lines.extend(["", "## Probe interpretation", ""])
        for _, row in probe[probe["eval_role"] == "ood_stress"].sort_values(["target_field", "variant"]).iterrows():
            lines.append(
                f"- known-family `{row['variant']}` -> `{row['target_field']}` probe known-label balanced accuracy "
                f"`{ckh.fmt(row.get('known_balanced_accuracy'))}` with known-label rate `{ckh.fmt(row.get('known_label_rate'))}`."
            )
        sealed_unknown = probe[probe["eval_role"] == "sealed_final_ood"].copy()
        if not sealed_unknown.empty:
            worst_known = sealed_unknown["known_label_rate"].astype(float).max()
            lines.append(
                f"- sealed_final_ood probe rows are mostly/fully outside the probe training label vocabulary "
                f"(max known-label rate `{ckh.fmt(worst_known)}`), so all-label probe accuracy there is not treated as shortcut removal evidence."
            )
    lines.extend(
        [
            "",
            "## Data-use boundary",
            "",
            "Training uses only support_train fit, id_calib fit, ood_val fit, and ood_stress fit.",
            "Thresholds use only id_calib/ood_val/ood_stress select.",
            "Representation probes are trained only on legal benign fit roles.",
            "support_val, same_file_query, future_query, sealed_final_ood, and sealed_final_attack are report-only.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    x_by_role, frame_by_role, support_labels, input_audit = cki.prepare_roles(args.smoke)
    ckj.add_diagnostic_columns(frame_by_role, support_labels)
    inventory = cki.role_inventory(frame_by_role)
    specs = SPECS[:2] if args.smoke else SPECS
    seeds = SEEDS[:1] if args.smoke else (SEEDS[:2] if args.quick else SEEDS)
    epochs = SMOKE_EPOCHS if args.smoke else (10 if args.quick else EPOCHS)

    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    anatomy_rows: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []

    fitted_seed42: dict[str, Fitted] = {}
    for seed in seeds:
        for spec in specs:
            name, fitted, audit, hist = fit_spec(spec, seed, x_by_role, frame_by_role, epochs)
            thresholds = thresholds_for(fitted, x_by_role, frame_by_role)
            for item in audit:
                train_rows.append({**item, "candidate": name, "seed": seed, "split": "main"})
            history_rows.extend([{**row, "split": "main"} for row in hist])
            rows, parts = eval_all_roles(name, fitted, thresholds, seed, "main", x_by_role, frame_by_role)
            role_rows.extend(rows)
            if seed == seeds[0]:
                fitted_seed42[spec.name] = fitted
                anatomy_rows.extend(grouped_anatomy(parts, "main_seed42", seed))

    if not args.skip_probe:
        for variant, fitted in fitted_seed42.items():
            for target in ["device_family", "source_family"]:
                probe_rows.extend(probe_embedding(variant, fitted, target, x_by_role, frame_by_role))

    selected_leave_groups = select_leave_groups(args.max_leave_groups)
    leave_rows: list[dict[str, Any]] = []
    leave_train: list[dict[str, Any]] = []
    leave_hist: list[dict[str, Any]] = []
    if not args.skip_leaveout:
        leave_rows, leave_train, leave_hist = eval_leaveout(specs, selected_leave_groups, x_by_role, frame_by_role, epochs)
        train_rows.extend(leave_train)
        history_rows.extend(leave_hist)

    matrix = aggregate_matrix(role_rows)
    seconds = time.time() - started
    ckh.write_csv(OUT / "candidate_matrix.csv", [spec.__dict__ for spec in SPECS])
    ckh.write_csv(OUT / "role_inventory.csv", inventory)
    ckh.write_csv(OUT / "train_audit.csv", train_rows)
    ckh.write_csv(OUT / "training_history.csv", history_rows)
    ckh.write_csv(OUT / "role_metrics_by_candidate_seed.csv", role_rows)
    ckh.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    ckh.write_csv(OUT / "review_anatomy_by_group_seed42.csv", anatomy_rows)
    ckh.write_csv(OUT / "representation_probe_metrics.csv", probe_rows)
    ckh.write_csv(OUT / "leave_device_family_stress_metrics.csv", leave_rows)
    ckh.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "deep invariant mechanism learning v1; raw115 encoder with optional domain adversary",
            "smoke": args.smoke,
            "quick": args.quick,
            "seeds": seeds,
            "epochs": epochs,
            "train_cap": TRAIN_CAP,
            "eval_cap": "full",
            "detector_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
            "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
            "probe_fit_roles": ["id_calib fit", "ood_val fit", "ood_stress fit"],
            "sealed_final_roles_used_for_training": False,
            "specs": [spec.__dict__ for spec in SPECS],
            "selected_leave_groups": selected_leave_groups,
            "input_audit": input_audit,
            "torch": {"version": torch.__version__, "device": str(DEVICE)},
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "role_inventory.csv",
                "train_audit.csv",
                "training_history.csv",
                "role_metrics_by_candidate_seed.csv",
                "candidate_summary_matrix.csv",
                "review_anatomy_by_group_seed42.csv",
                "representation_probe_metrics.csv",
                "leave_device_family_stress_metrics.csv",
                "codex_readout.md",
                "diagnostic_interpretation.md",
            ],
        },
    )
    ckh.write_md(OUT / "codex_readout.md", build_readout(matrix, leave_rows, probe_rows, seconds))
    ckh.write_md(OUT / "diagnostic_interpretation.md", build_interpretation(matrix, leave_rows, probe_rows))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--skip-leaveout", action="store_true")
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument("--max-leave-groups", type=int, default=4)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
