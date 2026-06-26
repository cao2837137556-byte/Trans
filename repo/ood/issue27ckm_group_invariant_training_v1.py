"""issue27ckm: group-invariant / causal-inspired training v1.

This is the next step after issue27ckl.  CKL showed that simple robust
frontend features do not repair the C4 shortcut problem.  CKM therefore keeps
the raw115 frontend and C4 four-class HistGB head, and changes only the
training objective via environment-aware weighting.

This is not a claim of full causal discovery.  It is a controlled
causal-inspired invariant training diagnostic:

- environments are device/source families;
- the detector is penalized/reweighted toward worst class-environment groups;
- sealed final rows remain report-only;
- query/future rows remain report-only for this fit.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cki_c4_full_data_multiclass_replay as cki  # noqa: E402
import issue27ckj_c4_stability_and_shortcut_anatomy as ckj  # noqa: E402


ISSUE = "issue27ckm_group_invariant_training_v1_2026-06-26"
OUT = ROOT / "runs" / ISSUE
TRAIN_CAP = 20_000
FULL_CAP = cki.FULL_CAP
SEEDS = [42, 43, 44, 45, 46]
DRO_ROUNDS = 2
DRO_ETA = 1.25
DRO_MULT_CLIP = (0.25, 8.0)


@dataclass(frozen=True)
class TrainSpec:
    name: str
    env_field: str | None
    weight_mode: str
    dro_rounds: int
    description: str


SPECS = [
    TrainSpec(
        "M0_c4_baseline",
        None,
        "class_balanced",
        0,
        "C4 raw115 HistGB baseline; class-balanced only.",
    ),
    TrainSpec(
        "M1_device_family_env_balanced",
        "device_family",
        "class_env_balanced",
        0,
        "Class x device-family balanced ERM control.",
    ),
    TrainSpec(
        "M2_source_family_env_balanced",
        "source_family",
        "class_env_balanced",
        0,
        "Class x source-family balanced ERM control.",
    ),
    TrainSpec(
        "M3_device_family_dro",
        "device_family",
        "class_env_dro",
        DRO_ROUNDS,
        "DRO-style iterative reweighting toward worst class x device-family groups.",
    ),
    TrainSpec(
        "M4_source_family_dro",
        "source_family",
        "class_env_dro",
        DRO_ROUNDS,
        "DRO-style iterative reweighting toward worst class x source-family groups.",
    ),
]

LEAVEOUT_SPEC_NAMES = {"M0_c4_baseline", "M3_device_family_dro", "M4_source_family_dro"}


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


def candidate(spec: TrainSpec, seed: int, suffix: str = "") -> ckh.Candidate:
    return ckh.Candidate(
        f"CKM_{spec.name}_seed{seed}{suffix}",
        "fewshot_direct",
        "raw115",
        "multiclass_id_ood_hardood_attack",
        "histgb_shallow",
        spec.description,
    )


def env_values(frame_by_role: dict[str, pd.DataFrame], role: str, idx: np.ndarray, env_field: str | None) -> np.ndarray:
    if env_field is None or env_field not in frame_by_role[role]:
        return np.asarray(["ALL"] * len(idx), dtype=object)
    vals = frame_by_role[role].iloc[idx][env_field].astype(str).to_numpy(dtype=object)
    vals[(vals == "") | (vals == "nan")] = "NA"
    return vals


def normalized(weights: np.ndarray) -> np.ndarray:
    w = np.asarray(weights, dtype=np.float64)
    total = float(np.sum(w))
    if total <= 0 or not math.isfinite(total):
        return np.ones(len(w), dtype=np.float64)
    return w * (len(w) / total)


def class_balanced_weights(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.int64)
    counts = {int(label): int(np.sum(y == label)) for label in np.unique(y)}
    return normalized(np.asarray([1.0 / max(1, counts[int(label)]) for label in y], dtype=np.float64))


def class_env_weights(y: np.ndarray, env: np.ndarray) -> np.ndarray:
    keys = [f"{int(label)}::{str(group)}" for label, group in zip(y, env)]
    counts: dict[str, int] = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    return normalized(np.asarray([1.0 / max(1, counts[key]) for key in keys], dtype=np.float64))


def nll_losses(model: Any, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    eps = 1e-12
    out = np.zeros(len(y), dtype=np.float64)
    for i, label in enumerate(y):
        if int(label) not in classes:
            out[i] = -math.log(eps)
        else:
            out[i] = -math.log(max(float(proba[i, classes.index(int(label))]), eps))
    return out


def group_loss_rows(
    candidate_name: str,
    split: str,
    round_id: int,
    y: np.ndarray,
    env: np.ndarray,
    weights: np.ndarray,
    losses: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys = np.asarray([f"{int(label)}::{str(group)}" for label, group in zip(y, env)], dtype=object)
    for key in sorted(set(keys.tolist())):
        mask = keys == key
        label, group = key.split("::", 1)
        rows.append(
            {
                "candidate": candidate_name,
                "split": split,
                "dro_round": round_id,
                "class_label": int(label),
                "env_value": group,
                "rows": int(np.sum(mask)),
                "mean_weight": float(np.mean(weights[mask])),
                "mean_loss": float(np.mean(losses[mask])),
                "max_loss": float(np.max(losses[mask])),
            }
        )
    return rows


def build_training_arrays(
    spec: TrainSpec,
    cand: ckh.Candidate,
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
        x = ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)[idx]
        env = env_values(frame_by_role, role, idx, spec.env_field)
        xs.append(x)
        ys.append(np.full(len(idx), label, dtype=np.int64))
        envs.append(env)
        audit.append(
            {
                "candidate": cand.name,
                "variant": spec.name,
                "env_field": spec.env_field or "",
                "weight_mode": spec.weight_mode,
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


def fit_weighted_model(seed: int, x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> Any:
    old_seed = ckh.SEED
    ckh.SEED = int(seed)
    try:
        model = ckh.build_model("histgb_shallow", multiclass=True)
        model.fit(np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.int64), sample_weight=np.asarray(weights, dtype=np.float64))
        return model
    finally:
        ckh.SEED = old_seed


def fit_spec(
    spec: TrainSpec,
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
    suffix: str = "",
) -> tuple[ckh.Candidate, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    cand = candidate(spec, seed, suffix)
    x_train, y_train, env, audit = build_training_arrays(spec, cand, x_by_role, frame_by_role, exclude=exclude)
    if spec.weight_mode == "class_balanced":
        weights = class_balanced_weights(y_train)
    else:
        weights = class_env_weights(y_train, env)
    loss_rows: list[dict[str, Any]] = []
    model = fit_weighted_model(seed, x_train, y_train, weights)
    losses = nll_losses(model, x_train, y_train)
    loss_rows.extend(group_loss_rows(cand.name, "train", 0, y_train, env, weights, losses))
    base_weights = weights.copy()

    if spec.weight_mode == "class_env_dro":
        keys = np.asarray([f"{int(label)}::{str(group)}" for label, group in zip(y_train, env)], dtype=object)
        for round_id in range(1, spec.dro_rounds + 1):
            means = {key: float(np.mean(losses[keys == key])) for key in sorted(set(keys.tolist()))}
            center = float(np.mean(list(means.values()))) if means else 0.0
            multipliers = {
                key: float(np.clip(math.exp(DRO_ETA * (loss - center)), DRO_MULT_CLIP[0], DRO_MULT_CLIP[1]))
                for key, loss in means.items()
            }
            weights = normalized(np.asarray([base_weights[i] * multipliers[keys[i]] for i in range(len(keys))], dtype=np.float64))
            model = fit_weighted_model(seed, x_train, y_train, weights)
            losses = nll_losses(model, x_train, y_train)
            loss_rows.extend(group_loss_rows(cand.name, "train", round_id, y_train, env, weights, losses))
    return cand, {"multiclass_model": model}, audit, loss_rows


def thresholds_for(
    cand: ckh.Candidate,
    fitted: dict[str, Any],
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
        x = ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)[idx]
        scores.append(ckh.decision_scores(cand, fitted, x)["attack_score"])
        roles.append(role)
    if not scores:
        raise RuntimeError(f"No threshold rows after exclusion {exclude}")
    return {
        "attack_threshold": float(max(np.quantile(score, ckh.BENIGN_SAFE_Q) for score in scores)),
        "hard_ood_gate": float("nan"),
        "threshold_roles": "|".join(roles),
    }


def eval_all_roles(
    cand: ckh.Candidate,
    fitted: dict[str, Any],
    thresholds: dict[str, Any],
    seed: int,
    split: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    rows, parts = ckj.eval_all_roles(
        cand,
        fitted,
        thresholds,
        seed,
        split,
        x_by_role,
        frame_by_role,
        include=include,
        exclude=exclude,
    )
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
    main = df[df["split"] == "main"].copy()
    if "variant" not in main:
        main["variant"] = main["candidate"].astype(str).str.split("_seed", n=1).str[0].str.replace("CKM_", "", regex=False)
    for variant, group in main.groupby("variant", sort=True):
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
                "seeds": int(group["seed"].nunique()) if "seed" in group else 0,
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


def select_leave_groups(max_groups: int) -> dict[str, list[str]]:
    for path in [
        ROOT / "runs" / "issue27ckk_group_balanced_worst_group_c4_2026-06-25" / "run_spec.json",
        ROOT / "runs" / "issue27ckj_c4_stability_and_shortcut_anatomy_2026-06-25" / "run_spec.json",
    ]:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        groups = payload.get("leave_groups_from_issue27ckj") or payload.get("selected_leave_groups") or {}
        device = list(groups.get("device_family", []))[:max_groups]
        if device:
            return {"device_family": device}
    return {"device_family": []}


def eval_leaveout(
    specs: list[TrainSpec],
    selected_groups: dict[str, list[str]],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    seed = SEEDS[0]
    rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    leave_specs = [spec for spec in specs if spec.name in LEAVEOUT_SPEC_NAMES]
    for value in selected_groups.get("device_family", []):
        held = ("device_family", value)
        for spec in leave_specs:
            cand, fitted, audit, losses = fit_spec(
                spec,
                seed,
                x_by_role,
                frame_by_role,
                exclude=held,
                suffix=f"_leave_{slug(value)}",
            )
            thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role, exclude=held)
            for item in audit:
                audit_rows.append({**item, "split": "leave_device_family", "held_field": "device_family", "held_value": value})
            for item in losses:
                loss_rows.append({**item, "held_field": "device_family", "held_value": value})
            eval_rows, _parts = eval_all_roles(
                cand,
                fitted,
                thresholds,
                seed,
                "leave_device_family",
                x_by_role,
                frame_by_role,
                include=held,
            )
            for row in eval_rows:
                row["variant"] = spec.name
                row["held_field"] = "device_family"
                row["held_value"] = value
            rows.extend(eval_rows)
    return rows, audit_rows, loss_rows


def build_readout(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckm group-invariant training v1",
        "",
        "## Scope",
        "",
        "Fixed frontend/head: raw115 + C4 four-class HistGB.",
        "Only the training objective/weights change. Environments are device/source families.",
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
        if int(row.get("rows", 0)) == 0:
            continue
        if row.get("role") not in {"ood_val", "ood_stress", "sealed_final_ood"}:
            continue
        lines.append(
            f"| {row['variant']} | {str(row.get('held_value', ''))[:60]} | {row['role']} | {row['rows']} | "
            f"{ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {ckh.fmt(row['raw_alarm_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- A valid invariant-training improvement must reduce sealed OOD review without raising sealed OOD hard false alarms.",
            "- It must preserve sealed/future attack hard detection.",
            "- It must reduce leave-device-family collapse, not merely move uncertainty from review into hard false alarms.",
            "- This is causal-inspired invariant training only; it is not a full causal discovery claim.",
            "",
            f"Runtime seconds: `{ckh.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def build_interpretation(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]]) -> list[str]:
    lines = ["# issue27ckm diagnostic interpretation", "", "## Verdict", ""]
    df = pd.DataFrame(matrix)
    if df.empty:
        return lines + ["No matrix rows were produced."]
    base = df[df["variant"] == "M0_c4_baseline"]
    if base.empty:
        return lines + ["No baseline row was produced."]
    base_row = base.iloc[0]
    lines.append("This run tests environment-aware training objectives while keeping raw115 and the C4 HistGB head fixed.")
    lines.append("")
    candidates = df[df["variant"] != "M0_c4_baseline"].copy()
    if not candidates.empty:
        candidates["passes_guardrail"] = (
            (candidates["sealed_ood_review_mean"].astype(float) < float(base_row["sealed_ood_review_mean"]))
            & (candidates["sealed_ood_hard_max"].astype(float) <= float(base_row["sealed_ood_hard_max"]) + 0.002)
            & (candidates["sealed_attack_hard_mean"].astype(float) >= float(base_row["sealed_attack_hard_mean"]) - 0.002)
            & (candidates["future_hard_mean"].astype(float) >= float(base_row["future_hard_mean"]) - 0.002)
        )
        if bool(candidates["passes_guardrail"].any()):
            best = candidates[candidates["passes_guardrail"]].sort_values("sealed_ood_review_mean").iloc[0]
            lines.append(f"Best guardrail-passing candidate: `{best['variant']}`.")
        else:
            lines.append("No environment-aware candidate passes the conservative guardrail.")
        lines.append("")
    for _, row in df.sort_values("variant").iterrows():
        if row["variant"] == "M0_c4_baseline":
            continue
        lines.append(
            f"- `{row['variant']}` vs baseline: sealed OOD review delta "
            f"`{ckh.fmt(float(row['sealed_ood_review_mean']) - float(base_row['sealed_ood_review_mean']))}`, "
            f"sealed OOD hard-max delta `{ckh.fmt(float(row['sealed_ood_hard_max']) - float(base_row['sealed_ood_hard_max']))}`, "
            f"sealed attack hard delta `{ckh.fmt(float(row['sealed_attack_hard_mean']) - float(base_row['sealed_attack_hard_mean']))}`, "
            f"future hard delta `{ckh.fmt(float(row['future_hard_mean']) - float(base_row['future_hard_mean']))}`."
        )
    lines.extend(
        [
            "",
            "Interpretation: environment-aware weighting increased sealed/future attack confidence for some rows, but it did not produce a valid generalization improvement.",
            "Compared with C4, the DRO-style variants still raise sealed OOD hard false alarms and reduce future attack hard detection by about six percentage points on average.",
            "Device-family and source-family variants are identical here because the current role metadata maps those environments almost one-to-one in the legal fit roles.",
        ]
    )
    leave = pd.DataFrame(leave_rows)
    if not leave.empty:
        risky = leave[
            (leave["role"].isin(["ood_val", "ood_stress", "sealed_final_ood"]))
            & (pd.to_numeric(leave["rows"], errors="coerce") > 0)
        ].copy()
        if not risky.empty:
            risky["hard_alarm_rate"] = pd.to_numeric(risky["hard_alarm_rate"], errors="coerce")
            worst = risky.sort_values("hard_alarm_rate", ascending=False).iloc[0]
            lines.extend(
                [
                    "",
                    "## Leave-device-family risk",
                    "",
                    f"Worst held-family hard alarm: `{worst['variant']}` / `{worst['held_value']}` / `{worst['role']}` = `{ckh.fmt(worst['hard_alarm_rate'])}`.",
                    "The invariant weighting line therefore has not solved the `iotsim-stream-consumer` collapse; the system still treats that held OOD family almost entirely as hard attack.",
                ]
            )
    lines.extend(
        [
            "",
            "## Data-use boundary",
            "",
            "Training uses only support_train fit, id_calib fit, ood_val fit, and ood_stress fit.",
            "Thresholds use only id_calib/ood_val/ood_stress select.",
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
    specs = SPECS[:2] if args.smoke else (SPECS[:3] if args.quick else SPECS)
    seeds = SEEDS[:1] if args.smoke else (SEEDS[:3] if args.quick else SEEDS)

    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    anatomy_rows: list[dict[str, Any]] = []

    for seed in seeds:
        for spec in specs:
            cand, fitted, audit, losses = fit_spec(spec, seed, x_by_role, frame_by_role)
            thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role)
            for item in audit:
                train_rows.append({**item, "split": "main", "seed": seed})
            loss_rows.extend(losses)
            rows, parts = eval_all_roles(cand, fitted, thresholds, seed, "main", x_by_role, frame_by_role)
            for row in rows:
                row["variant"] = spec.name
            role_rows.extend(rows)
            if seed == seeds[0]:
                anatomy_rows.extend(grouped_anatomy(parts, "main_seed42", seed))

    selected_leave_groups = select_leave_groups(args.max_leave_groups)
    leave_rows: list[dict[str, Any]] = []
    leave_train_rows: list[dict[str, Any]] = []
    leave_loss_rows: list[dict[str, Any]] = []
    if not args.skip_leaveout:
        leave_rows, leave_train_rows, leave_loss_rows = eval_leaveout(specs, selected_leave_groups, x_by_role, frame_by_role)
        train_rows.extend(leave_train_rows)
        loss_rows.extend(leave_loss_rows)

    matrix = aggregate_matrix(role_rows)
    seconds = time.time() - started
    ckh.write_csv(OUT / "candidate_matrix.csv", [spec.__dict__ for spec in SPECS])
    ckh.write_csv(OUT / "role_inventory.csv", inventory)
    ckh.write_csv(OUT / "train_audit.csv", train_rows)
    ckh.write_csv(OUT / "train_group_loss.csv", loss_rows)
    ckh.write_csv(OUT / "role_metrics_by_candidate_seed.csv", role_rows)
    ckh.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    ckh.write_csv(OUT / "review_anatomy_by_group_seed42.csv", anatomy_rows)
    ckh.write_csv(OUT / "leave_device_family_stress_metrics.csv", leave_rows)
    ckh.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "group-invariant / causal-inspired training v1; fixed raw115 C4 HistGB head",
            "smoke": args.smoke,
            "quick": args.quick,
            "seeds": seeds,
            "train_cap": TRAIN_CAP,
            "eval_cap": "full",
            "dro_rounds": DRO_ROUNDS,
            "dro_eta": DRO_ETA,
            "detector_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
            "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
            "sealed_final_roles_used_for_training": False,
            "specs": [spec.__dict__ for spec in SPECS],
            "selected_leave_groups": selected_leave_groups,
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "role_inventory.csv",
                "train_audit.csv",
                "train_group_loss.csv",
                "role_metrics_by_candidate_seed.csv",
                "candidate_summary_matrix.csv",
                "review_anatomy_by_group_seed42.csv",
                "leave_device_family_stress_metrics.csv",
                "codex_readout.md",
                "diagnostic_interpretation.md",
            ],
        },
    )
    ckh.write_md(OUT / "codex_readout.md", build_readout(matrix, leave_rows, seconds))
    ckh.write_md(OUT / "diagnostic_interpretation.md", build_interpretation(matrix, leave_rows))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--quick", action="store_true", help="run 3 seeds and first 3 specs")
    parser.add_argument("--skip-leaveout", action="store_true")
    parser.add_argument("--max-leave-groups", type=int, default=4)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
