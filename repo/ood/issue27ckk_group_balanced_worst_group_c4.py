"""issue27ckk: group-balanced / worst-group C4 repair.

This is the first repair after issue27ckj.  It keeps the detector family fixed
to the C4 raw115 four-class head and changes only legal training views and
sample weights.

Legal fit data only:

- support_train attack positives
- id_calib fit
- ood_val fit
- ood_stress fit

No support_val select, query select, future query, or sealed final rows are used
for model fitting.  The optional fit-tail mining candidate mines hard benign
rows only from those legal fit roles.
"""

from __future__ import annotations

import argparse
import json
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


ISSUE = "issue27ckk_group_balanced_worst_group_c4_2026-06-25"
OUT = ROOT / "runs" / ISSUE
TRAIN_CAP = 20_000
FULL_CAP = cki.FULL_CAP
SEEDS = [42, 43, 44, 45, 46]


@dataclass(frozen=True)
class RepairSpec:
    name: str
    sampler: str
    weight_mode: str
    description: str


SPECS = [
    RepairSpec(
        "baseline_cap20000",
        "baseline",
        "class_balanced",
        "issue27cki C4-cap20000 reproduction.",
    ),
    RepairSpec(
        "source_balanced",
        "source_group",
        "class_balanced",
        "Equalize legal fit sampling across source_group inside each benign/OOD role.",
    ),
    RepairSpec(
        "device_time_balanced",
        "device_family_time_block",
        "class_balanced",
        "Equalize legal fit sampling across device_family x time_block inside each benign/OOD role.",
    ),
    RepairSpec(
        "source_balanced_group_weighted",
        "source_group",
        "class_and_group_balanced",
        "Source-balanced sampling plus inverse source-group sample weighting.",
    ),
    RepairSpec(
        "fit_tail_source_balanced",
        "source_group_plus_fit_tail",
        "class_and_group_balanced",
        "Source-balanced legal fit view plus hard benign fit-tail mining; no select/report rows.",
    ),
]
LEAVEOUT_SPEC_NAMES = {
    "baseline_cap20000",
    "source_balanced_group_weighted",
    "fit_tail_source_balanced",
}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    pd.DataFrame(rows, columns=fields).to_csv(path, index=False)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def role_fit_indices(frame_by_role: dict[str, pd.DataFrame], role: str, exclude: tuple[str, str] | None = None) -> np.ndarray:
    frame = frame_by_role[role]
    idx = np.flatnonzero(frame["phase"].to_numpy() == "fit")
    if exclude is not None and exclude[0] in frame:
        field, value = exclude
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() != str(value)]
    return idx.astype(np.int64)


def deterministic_even(indices: np.ndarray, cap: int) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) <= cap:
        return indices
    keep = np.linspace(0, len(indices) - 1, num=cap, dtype=np.int64)
    return indices[keep]


def group_key(frame: pd.DataFrame, indices: np.ndarray, cols: list[str]) -> pd.Series:
    indices = np.asarray(indices, dtype=np.int64)
    if not cols:
        return pd.Series(["all"] * len(indices), index=indices)
    present = [col for col in cols if col in frame]
    if not present:
        return pd.Series(["all"] * len(indices), index=indices)
    values = frame.iloc[indices][present].astype(str).to_numpy(dtype=object)
    joined = ["||".join(str(item) for item in row) for row in values]
    return pd.Series(joined, index=indices)


def group_balanced_indices(frame: pd.DataFrame, indices: np.ndarray, cap: int, cols: list[str]) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) <= cap or len(indices) == 0:
        return indices
    keys = group_key(frame, indices, cols)
    groups = [(str(key), np.asarray(vals.index, dtype=np.int64)) for key, vals in keys.groupby(keys, sort=True)]
    if not groups:
        return deterministic_even(indices, cap)
    base = max(1, cap // len(groups))
    chosen: list[np.ndarray] = []
    used: set[int] = set()
    for _key, vals in groups:
        part = deterministic_even(vals, min(len(vals), base))
        chosen.append(part)
        used.update(int(x) for x in part)
    merged = np.concatenate(chosen) if chosen else np.empty(0, dtype=np.int64)
    if len(merged) < cap:
        remaining = np.asarray([idx for idx in indices if int(idx) not in used], dtype=np.int64)
        add = deterministic_even(remaining, min(len(remaining), cap - len(merged)))
        merged = np.concatenate([merged, add])
    if len(merged) > cap:
        merged = deterministic_even(merged, cap)
    return np.asarray(sorted(set(int(x) for x in merged)), dtype=np.int64)


def sampler_cols(name: str) -> list[str]:
    if name == "source_group":
        return ["source_group"]
    if name == "device_family_time_block":
        return ["device_family", "time_block"]
    return []


def sample_role_indices(
    spec: RepairSpec,
    role: str,
    frame_by_role: dict[str, pd.DataFrame],
    cap: int,
    exclude: tuple[str, str] | None,
    fit_tail_scores: dict[str, np.ndarray] | None,
) -> np.ndarray:
    frame = frame_by_role[role]
    idx = role_fit_indices(frame_by_role, role, exclude=exclude)
    if role == "support_train":
        return idx
    if len(idx) <= cap:
        return idx
    if spec.sampler == "baseline":
        return deterministic_even(idx, cap)
    if spec.sampler in {"source_group", "device_family_time_block"}:
        return group_balanced_indices(frame, idx, cap, sampler_cols(spec.sampler))
    if spec.sampler == "source_group_plus_fit_tail":
        base_cap = int(round(cap * 0.70))
        tail_cap = cap - base_cap
        base = group_balanced_indices(frame, idx, base_cap, ["source_group"])
        used = set(int(x) for x in base)
        scores = fit_tail_scores.get(role) if fit_tail_scores else None
        if scores is None:
            return group_balanced_indices(frame, idx, cap, ["source_group"])
        remaining = np.asarray([i for i in idx if int(i) not in used], dtype=np.int64)
        if len(remaining):
            order = remaining[np.argsort(-scores[remaining])]
            tail = deterministic_even(order[: min(len(order), tail_cap * 4)], min(len(order), tail_cap))
        else:
            tail = np.empty(0, dtype=np.int64)
        merged = np.concatenate([base, tail])
        if len(merged) < cap:
            leftover = np.asarray([i for i in idx if int(i) not in set(int(x) for x in merged)], dtype=np.int64)
            merged = np.concatenate([merged, deterministic_even(leftover, min(len(leftover), cap - len(merged)))])
        return np.asarray(sorted(set(int(x) for x in merged)), dtype=np.int64)
    raise ValueError(f"unknown sampler {spec.sampler}")


def candidate_name(spec: RepairSpec, seed: int, suffix: str = "") -> str:
    return f"C4_{spec.name}_seed{seed}{suffix}"


def make_candidate(spec: RepairSpec, seed: int, suffix: str = "") -> ckh.Candidate:
    return ckh.Candidate(
        candidate_name(spec, seed, suffix),
        "fewshot_direct",
        "raw115",
        "multiclass_id_ood_hardood_attack",
        "histgb_shallow",
        spec.description,
    )


def compute_sample_weights(y: np.ndarray, group_labels: list[str], mode: str) -> np.ndarray:
    y = np.asarray(y, dtype=np.int64)
    weights = np.ones(len(y), dtype=np.float64)
    counts = {label: int(np.sum(y == label)) for label in np.unique(y)}
    for i, label in enumerate(y):
        weights[i] *= 1.0 / max(1, counts[int(label)])
    if mode == "class_and_group_balanced":
        group_counts: dict[tuple[int, str], int] = {}
        for label, group in zip(y, group_labels):
            key = (int(label), str(group))
            group_counts[key] = group_counts.get(key, 0) + 1
        for i, (label, group) in enumerate(zip(y, group_labels)):
            weights[i] *= 1.0 / max(1, group_counts[(int(label), str(group))])
    elif mode != "class_balanced":
        raise ValueError(f"unknown weight mode {mode}")
    weights *= len(weights) / max(1e-12, float(np.sum(weights)))
    return weights


def train_spec(
    spec: RepairSpec,
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
    exclude_attack_label: str | None = None,
    fit_tail_scores: dict[str, np.ndarray] | None = None,
) -> tuple[ckh.Candidate, dict[str, Any], list[dict[str, Any]]]:
    old_seed = ckh.SEED
    ckh.SEED = int(seed)
    cand = make_candidate(spec, seed, "" if exclude is None and exclude_attack_label is None else "_leaveout")
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    groups: list[str] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, label: int, cap: int, local_exclude: tuple[str, str] | None = exclude) -> None:
        idx = sample_role_indices(spec, role, frame_by_role, cap, local_exclude, fit_tail_scores)
        if role == "support_train" and exclude_attack_label is not None:
            frame = frame_by_role[role]
            idx = idx[frame.iloc[idx]["attack_label"].astype(str).to_numpy() != str(exclude_attack_label)]
        xs.append(ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)[idx])
        ys.append(np.full(len(idx), label, dtype=np.int64))
        key_cols = ["source_group"] if spec.sampler != "device_family_time_block" else ["device_family", "time_block"]
        role_groups = group_key(frame_by_role[role], idx, key_cols).astype(str).tolist()
        groups.extend([f"{role}:{g}" for g in role_groups])
        audit.append(
            {
                "candidate": cand.name,
                "variant": spec.name,
                "sampler": spec.sampler,
                "weight_mode": spec.weight_mode,
                "seed": seed,
                "role": role,
                "phase": "fit",
                "label": label,
                "rows": len(idx),
                "unique_source_groups": int(frame_by_role[role].iloc[idx]["source_group"].astype(str).nunique()) if "source_group" in frame_by_role[role] and len(idx) else 0,
                "unique_device_families": int(frame_by_role[role].iloc[idx]["device_family"].astype(str).nunique()) if "device_family" in frame_by_role[role] and len(idx) else 0,
            }
        )

    try:
        add("support_train", ckh.CLASS_ATTACK, FULL_CAP, None)
        add("id_calib", ckh.CLASS_ID, TRAIN_CAP)
        add("ood_val", ckh.CLASS_OOD, TRAIN_CAP)
        add("ood_stress", ckh.CLASS_HARD_OOD, TRAIN_CAP)
        x_train = np.vstack(xs)
        y_train = np.concatenate(ys)
        sample_weight = compute_sample_weights(y_train, groups, spec.weight_mode)
        model = ckh.build_model(cand.model, multiclass=True)
        model.fit(np.asarray(x_train, dtype=np.float32), y_train, sample_weight=sample_weight)
        return cand, {"multiclass_model": model}, audit
    finally:
        ckh.SEED = old_seed


def baseline_fit_tail_scores(
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> dict[str, np.ndarray]:
    baseline = SPECS[0]
    cand, fitted, _audit = train_spec(baseline, seed, x_by_role, frame_by_role)
    out: dict[str, np.ndarray] = {}
    for role in ["id_calib", "ood_val", "ood_stress"]:
        x = ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)
        out[role] = ckh.decision_scores(cand, fitted, x)["attack_score"]
    return out


def thresholds_for(
    cand: ckh.Candidate,
    fitted: dict[str, Any],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> dict[str, float]:
    return ckj.thresholds_for(cand, fitted, x_by_role, frame_by_role, exclude=exclude)


def eval_main(
    spec: RepairSpec,
    cand: ckh.Candidate,
    fitted: dict[str, Any],
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role)
    rows, parts = ckj.eval_all_roles(cand, fitted, thresholds, seed, "main", x_by_role, frame_by_role)
    for row in rows:
        row["variant"] = spec.name
        row["sampler"] = spec.sampler
        row["weight_mode"] = spec.weight_mode
    return rows, parts


def group_rows_for_parts(spec: RepairSpec, seed: int, parts: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows = ckj.grouped_anatomy(
        parts,
        ["source_group", "device_family", "time_block", "attack_label", "attack_family", "support_seen"],
        "main",
        seed,
    )
    for row in rows:
        row["variant"] = spec.name
    return rows


def aggregate_variant_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(role_rows)
    out: list[dict[str, Any]] = []
    if df.empty:
        return out
    for (variant, role), group in df.groupby(["variant", "role"], sort=True):
        row: dict[str, Any] = {"variant": variant, "role": role, "seeds": int(group["seed"].nunique()), "rows": int(group["rows"].iloc[0])}
        for metric in ["hard_alarm_rate", "conflict_review_rate", "raw_alarm_rate"]:
            vals = group[metric].astype(float)
            row[f"{metric}_mean"] = float(vals.mean())
            row[f"{metric}_min"] = float(vals.min())
            row[f"{metric}_max"] = float(vals.max())
            row[f"{metric}_std"] = float(vals.std(ddof=0))
        out.append(row)
    return out


def compact_matrix(summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(summary)
    rows: list[dict[str, Any]] = []
    if df.empty:
        return rows
    for variant, group in df.groupby("variant", sort=True):
        def val(role: str, col: str) -> float:
            sub = group[group["role"] == role]
            if sub.empty:
                return float("nan")
            return float(sub[col].iloc[0])

        rows.append(
            {
                "variant": variant,
                "future_hard_mean": val("future_query", "hard_alarm_rate_mean"),
                "future_hard_min": val("future_query", "hard_alarm_rate_min"),
                "future_review_mean": val("future_query", "conflict_review_rate_mean"),
                "sealed_attack_hard_mean": val("sealed_final_attack", "hard_alarm_rate_mean"),
                "sealed_attack_hard_min": val("sealed_final_attack", "hard_alarm_rate_min"),
                "sealed_attack_review_mean": val("sealed_final_attack", "conflict_review_rate_mean"),
                "sealed_ood_hard_mean": val("sealed_final_ood", "hard_alarm_rate_mean"),
                "sealed_ood_hard_max": val("sealed_final_ood", "hard_alarm_rate_max"),
                "sealed_ood_review_mean": val("sealed_final_ood", "conflict_review_rate_mean"),
                "sealed_ood_review_max": val("sealed_final_ood", "conflict_review_rate_max"),
                "ood_stress_hard_max": val("ood_stress", "hard_alarm_rate_max"),
                "ood_stress_review_mean": val("ood_stress", "conflict_review_rate_mean"),
            }
        )
    return rows


def read_csv_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return pd.read_csv(path).to_dict("records")


def select_leave_groups_from_ckj(max_groups: int = 4) -> dict[str, list[str]]:
    path = ROOT / "runs" / "issue27ckj_c4_stability_and_shortcut_anatomy_2026-06-25" / "run_spec.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            groups = payload.get("selected_leave_groups", {})
            return {
                "device_family": list(groups.get("device_family", []))[:max_groups],
                "source_group": list(groups.get("source_group", []))[:max_groups],
                "attack_label": list(groups.get("attack_label", []))[:max_groups],
            }
        except Exception:
            pass
    return {"device_family": [], "source_group": [], "attack_label": []}


def eval_leave_stress(
    specs: list[RepairSpec],
    selected_groups: dict[str, list[str]],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    seed = SEEDS[0]
    for spec in specs:
        fit_tail_scores = baseline_fit_tail_scores(seed, x_by_role, frame_by_role) if spec.sampler == "source_group_plus_fit_tail" else None
        for field in ["source_group", "device_family"]:
            for value in selected_groups.get(field, []):
                cand, fitted, audit = train_spec(spec, seed, x_by_role, frame_by_role, exclude=(field, value), fit_tail_scores=fit_tail_scores)
                thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role, exclude=(field, value))
                for item in audit:
                    audit_rows.append({**item, "split": f"leave_{field}", "held_field": field, "held_value": value})
                eval_rows, _parts = ckj.eval_all_roles(
                    cand,
                    fitted,
                    thresholds,
                    seed,
                    f"leave_{field}",
                    x_by_role,
                    frame_by_role,
                    include=(field, value),
                )
                for row in eval_rows:
                    row["variant"] = spec.name
                    row["held_field"] = field
                    row["held_value"] = value
                rows.extend(eval_rows)
        for value in selected_groups.get("attack_label", []):
            cand, fitted, audit = train_spec(
                spec,
                seed,
                x_by_role,
                frame_by_role,
                exclude_attack_label=value,
                fit_tail_scores=fit_tail_scores,
            )
            thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role)
            for item in audit:
                audit_rows.append({**item, "split": "leave_attack_label", "held_field": "attack_label", "held_value": value})
            eval_rows, _parts = ckj.eval_all_roles(
                cand,
                fitted,
                thresholds,
                seed,
                "leave_attack_label",
                x_by_role,
                frame_by_role,
                include=("attack_label", value),
            )
            for row in eval_rows:
                row["variant"] = spec.name
                row["held_field"] = "attack_label"
                row["held_value"] = value
            rows.extend(eval_rows)
    return rows, audit_rows


def build_readout(
    matrix: list[dict[str, Any]],
    leave_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    seconds: float,
) -> list[str]:
    lines = [
        "# issue27ckk group-balanced / worst-group C4",
        "",
        "## Scope",
        "",
        "Repair experiment. Fixed detector family: raw115 C4 four-class HistGB.",
        "Only legal fit roles are used for training. No query/select/final role is used for fit.",
        "",
        "## Candidate matrix",
        "",
        "| variant | future hard mean/min | future review | sealed attack hard mean/min | sealed OOD hard mean/max | sealed OOD review mean/max | ood_stress hard max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['variant']} | {ckh.fmt(row['future_hard_mean'])}/{ckh.fmt(row['future_hard_min'])} | {ckh.fmt(row['future_review_mean'])} | {ckh.fmt(row['sealed_attack_hard_mean'])}/{ckh.fmt(row['sealed_attack_hard_min'])} | {ckh.fmt(row['sealed_ood_hard_mean'])}/{ckh.fmt(row['sealed_ood_hard_max'])} | {ckh.fmt(row['sealed_ood_review_mean'])}/{ckh.fmt(row['sealed_ood_review_max'])} | {ckh.fmt(row['ood_stress_hard_max'])} |"
        )

    lines.extend(["", "## Leave-device/family stress snapshot", ""])
    lines.extend(["| variant | held field | held value | role | rows | hard | review | raw |", "|---|---|---|---|---:|---:|---:|---:|"])
    for row in leave_rows:
        if int(row.get("rows", 0)) == 0:
            continue
        if row.get("held_field") != "device_family":
            continue
        if row["role"] not in {"ood_stress", "ood_val", "sealed_final_ood"}:
            continue
        lines.append(
            f"| {row['variant']} | {row['held_field']} | {str(row['held_value'])[:60]} | {row['role']} | {row['rows']} | {ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {ckh.fmt(row['raw_alarm_rate'])} |"
        )

    lines.extend(["", "## Top seed42 group burdens", ""])
    lines.extend(["| variant | role | group field | value | rows | hard | review | hard count | review count |", "|---|---|---|---|---:|---:|---:|---:|---:|"])
    df = pd.DataFrame(group_rows)
    if not df.empty:
        df["burden"] = df["review_count"].astype(int) + 5 * df["hard_count"].astype(int)
        top = df[(df["rows"].astype(int) >= 50) & (df["burden"] > 0)].sort_values("burden", ascending=False).head(25)
        for _, row in top.iterrows():
            lines.append(
                f"| {row['variant']} | {row['role']} | {row['group_field']} | {str(row['group_value'])[:60]} | {row['rows']} | {ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {row['hard_count']} | {row['review_count']} |"
            )

    lines.extend(
        [
            "",
            "## Interpretation guardrail",
            "",
            "- A good repair must reduce review without hiding uncertainty by converting review into false hard attack alarms.",
            "- Leave-device-family collapse can only be partially addressed inside the current Gotham fit contract; if a family is absent from legal fit, training-view repair cannot create information ex nihilo.",
            "- If group-balanced views help average review but leave-device-family still collapses, issue27ckl should add invariant/causal representation and smarter heads.",
            "",
            f"Runtime seconds: `{ckh.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def build_interpretation(matrix: list[dict[str, Any]], leave_rows: list[dict[str, Any]]) -> list[str]:
    df = pd.DataFrame(matrix)
    lines = [
        "# issue27ckk diagnostic interpretation",
        "",
        "## Verdict",
        "",
        "This run tests whether legal group-balanced/worst-group training views are enough to repair C4's review instability and shortcut risk.",
        "",
    ]
    if not df.empty:
        # Lower sealed OOD review is useful only if attack retention stays high and hard OOD does not rise.
        candidates = df.copy()
        candidates["eligible"] = (
            (candidates["sealed_attack_hard_mean"] >= 0.99)
            & (candidates["future_hard_mean"] >= 0.97)
            & (candidates["sealed_ood_hard_max"] <= 0.01)
        )
        eligible = candidates[candidates["eligible"]].sort_values("sealed_ood_review_mean")
        if not eligible.empty:
            best = eligible.iloc[0]
            lines.extend(
                [
                    f"Best eligible candidate by sealed OOD review: `{best['variant']}`.",
                    "",
                    f"- future hard mean/min: `{ckh.fmt(best['future_hard_mean'])}` / `{ckh.fmt(best['future_hard_min'])}`",
                    f"- sealed attack hard mean/min: `{ckh.fmt(best['sealed_attack_hard_mean'])}` / `{ckh.fmt(best['sealed_attack_hard_min'])}`",
                    f"- sealed OOD hard mean/max: `{ckh.fmt(best['sealed_ood_hard_mean'])}` / `{ckh.fmt(best['sealed_ood_hard_max'])}`",
                    f"- sealed OOD review mean/max: `{ckh.fmt(best['sealed_ood_review_mean'])}` / `{ckh.fmt(best['sealed_ood_review_max'])}`",
                    "",
                ]
            )
            rejected = candidates[~candidates["eligible"]].copy()
            if not rejected.empty:
                lines.extend(["Rejected trade-offs:", ""])
                for _, row in rejected.sort_values("sealed_ood_review_mean").iterrows():
                    reasons: list[str] = []
                    if float(row["sealed_attack_hard_mean"]) < 0.99:
                        reasons.append(f"sealed attack hard mean {ckh.fmt(row['sealed_attack_hard_mean'])} < 0.99")
                    if float(row["future_hard_mean"]) < 0.97:
                        reasons.append(f"future hard mean {ckh.fmt(row['future_hard_mean'])} < 0.97")
                    if float(row["sealed_ood_hard_max"]) > 0.01:
                        reasons.append(f"sealed OOD hard max {ckh.fmt(row['sealed_ood_hard_max'])} > 0.01")
                    lines.append(
                        f"- `{row['variant']}`: sealed OOD review mean `{ckh.fmt(row['sealed_ood_review_mean'])}`, rejected because "
                        + "; ".join(reasons)
                        + "."
                    )
                lines.append("")
        else:
            lines.extend(["No candidate met the conservative eligibility guardrail.", ""])
    leave = pd.DataFrame(leave_rows)
    if not leave.empty:
        bad = leave[
            (leave["held_field"] == "device_family")
            & (leave["role"].isin(["ood_stress", "ood_val"]))
            & (leave["rows"].astype(int) > 0)
            & (leave["hard_alarm_rate"].astype(float) > 0.1)
        ]
        if not bad.empty:
            worst = bad.sort_values("hard_alarm_rate", ascending=False).iloc[0]
            lines.extend(
                [
                    "## Remaining shortcut risk",
                    "",
                    "At least one device-family leave-out stress case still has hard alarm above `10%`.",
                    "That means training-view repair alone has not fully solved cross-family generalization.",
                    f"Worst observed case: `{worst['variant']}` leaving `{worst['held_value']}` on `{worst['role']}` produced hard alarm `{ckh.fmt(worst['hard_alarm_rate'])}`.",
                    "",
                ]
            )
    lines.extend(
        [
            "## Data-use boundary",
            "",
            "Training used only support_train, id_calib fit, ood_val fit, and ood_stress fit.",
            "No support_val select, same_file/future query select, or sealed final rows were used for fitting.",
        ]
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--skip-leaveout", action="store_true")
    parser.add_argument("--leaveout-only", action="store_true", help="reuse existing main matrices and only recompute leave-out stress")
    parser.add_argument("--max-leave-groups", type=int, default=4)
    args = parser.parse_args()
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, support_labels, input_audit = cki.prepare_roles(args.smoke)
    ckj.add_diagnostic_columns(frame_by_role, support_labels)
    inventory = cki.role_inventory(frame_by_role)
    seeds = SEEDS[:1] if args.smoke else SEEDS
    specs = SPECS[:2] if args.smoke else SPECS

    old_cap = ckh.BENIGN_CAP_PER_ROLE
    old_eval_cap = ckh.EVAL_CAP_PER_ROLE
    ckh.BENIGN_CAP_PER_ROLE = TRAIN_CAP
    ckh.EVAL_CAP_PER_ROLE = FULL_CAP

    role_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []

    try:
        if args.leaveout_only:
            role_rows = read_csv_records(OUT / "role_metrics_by_candidate_seed.csv")
            group_rows = read_csv_records(OUT / "review_anatomy_by_group_seed42.csv")
            train_rows = [row for row in read_csv_records(OUT / "train_audit.csv") if str(row.get("split", "")) == "main"]
        else:
            for seed in seeds:
                fit_tail_scores_cache: dict[str, np.ndarray] | None = None
                for spec in specs:
                    fit_tail_scores = None
                    if spec.sampler == "source_group_plus_fit_tail":
                        if fit_tail_scores_cache is None:
                            fit_tail_scores_cache = baseline_fit_tail_scores(seed, x_by_role, frame_by_role)
                        fit_tail_scores = fit_tail_scores_cache
                    cand, fitted, audit = train_spec(spec, seed, x_by_role, frame_by_role, fit_tail_scores=fit_tail_scores)
                    for item in audit:
                        train_rows.append({**item, "split": "main"})
                    rows, parts = eval_main(spec, cand, fitted, seed, x_by_role, frame_by_role)
                    role_rows.extend(rows)
                    if seed == seeds[0]:
                        group_rows.extend(group_rows_for_parts(spec, seed, parts))

        selected_groups = select_leave_groups_from_ckj(args.max_leave_groups)
        leave_rows: list[dict[str, Any]] = []
        leave_train_rows: list[dict[str, Any]] = []
        if not args.skip_leaveout:
            leave_specs = specs if args.smoke else [spec for spec in SPECS if spec.name in LEAVEOUT_SPEC_NAMES]
            leave_rows, leave_train_rows = eval_leave_stress(leave_specs, selected_groups, x_by_role, frame_by_role)
            train_rows.extend(leave_train_rows)
    finally:
        ckh.BENIGN_CAP_PER_ROLE = old_cap
        ckh.EVAL_CAP_PER_ROLE = old_eval_cap

    summary = aggregate_variant_summary(role_rows)
    matrix = compact_matrix(summary)
    seconds = time.time() - started
    write_csv(OUT / "candidate_matrix.csv", [spec.__dict__ for spec in SPECS])
    write_csv(OUT / "role_inventory.csv", inventory)
    write_csv(OUT / "train_audit.csv", train_rows)
    write_csv(OUT / "role_metrics_by_candidate_seed.csv", role_rows)
    write_csv(OUT / "aggregate_variant_metrics.csv", summary)
    write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    write_csv(OUT / "review_anatomy_by_group_seed42.csv", group_rows)
    write_csv(OUT / "leave_out_stress_metrics.csv", leave_rows)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "legal-fit group-balanced and worst-group C4 repair",
            "smoke": args.smoke,
            "seeds": seeds,
            "train_cap": TRAIN_CAP,
            "eval_cap": "full",
            "sealed_final_roles_used_for_training": False,
            "fit_roles_only": ["support_train", "id_calib fit", "ood_val fit", "ood_stress fit"],
            "candidate_specs": [spec.__dict__ for spec in SPECS],
            "leaveout_only": args.leaveout_only,
            "leaveout_candidate_specs": [name for name in LEAVEOUT_SPEC_NAMES],
            "leave_groups_from_issue27ckj": select_leave_groups_from_ckj(args.max_leave_groups),
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "role_inventory.csv",
                "train_audit.csv",
                "role_metrics_by_candidate_seed.csv",
                "aggregate_variant_metrics.csv",
                "candidate_summary_matrix.csv",
                "review_anatomy_by_group_seed42.csv",
                "leave_out_stress_metrics.csv",
                "diagnostic_interpretation.md",
                "codex_readout.md",
            ],
        },
    )
    readout = build_readout(matrix, leave_rows, group_rows, seconds)
    write_md(OUT / "codex_readout.md", readout)
    write_md(OUT / "diagnostic_interpretation.md", build_interpretation(matrix, leave_rows))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


if __name__ == "__main__":
    main()
