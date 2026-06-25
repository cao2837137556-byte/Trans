"""issue27ckj: C4 stability and shortcut anatomy.

This is a diagnosis, not a repair.  It freezes the best issue27cki baseline:

    C4_fewshot_multiclass_raw115_cap20000

and asks whether it is stable and whether its remaining review/error mass is
concentrated in Gotham source/device/family shortcuts.

No new head is introduced here.  Sealed final attack/OOD remain report-only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
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


ISSUE = "issue27ckj_c4_stability_and_shortcut_anatomy_2026-06-25"
OUT = ROOT / "runs" / ISSUE
TRAIN_CAP = 20_000
FULL_CAP = cki.FULL_CAP
SEEDS = [42, 43, 44, 45, 46]
ROLE_EVAL = ckh.ROLE_EVAL


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def device_family(value: Any) -> str:
    text = str(value)
    if not text or text == "nan":
        return "NA"
    text = Path(text).stem
    return re.sub(r"-\d+$", "", text)


def attack_family(value: Any) -> str:
    text = str(value)
    if not text or text == "nan":
        return "NA"
    # Keep attack taxonomy coarse enough to expose family shortcuts while
    # preserving labels such as Mirai GRE/TCP/UDP Flooding.
    parts = text.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else text


def add_diagnostic_columns(frame_by_role: dict[str, pd.DataFrame], support_labels: set[str]) -> None:
    for role, frame in frame_by_role.items():
        if "source_group" in frame:
            frame["source_family"] = frame["source_group"].map(device_family)
        if "device" in frame:
            frame["device_family"] = frame["device"].map(device_family)
        if "attack_label" in frame:
            frame["attack_family"] = frame["attack_label"].map(attack_family)
            frame["support_seen"] = np.where(frame["attack_label"].astype(str).isin(support_labels), "seen", "unseen")
        else:
            frame["attack_family"] = "NA"
            frame["support_seen"] = "NA"
        if "packet_timestamp_epoch" in frame and len(frame) >= 4:
            try:
                frame["time_block"] = pd.qcut(
                    frame["packet_timestamp_epoch"].astype(float).rank(method="first"),
                    q=4,
                    labels=["q1", "q2", "q3", "q4"],
                ).astype(str)
            except ValueError:
                frame["time_block"] = "single"
        else:
            frame["time_block"] = "NA"


def candidate(seed: int, name_suffix: str = "") -> ckh.Candidate:
    suffix = f"_seed{seed}{name_suffix}"
    return ckh.Candidate(
        f"C4_cap20000{suffix}",
        "fewshot_direct",
        "raw115",
        "multiclass_id_ood_hardood_attack",
        "histgb_shallow",
        "C4 raw115 four-class head with benign/OOD train cap 20000.",
    )


def idx_for(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int = FULL_CAP,
    exclude: tuple[str, str] | None = None,
    include: tuple[str, str] | None = None,
) -> np.ndarray:
    frame = frame_by_role[role]
    idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].to_numpy() == phase)
    if exclude is not None and exclude[0] in frame:
        field, value = exclude
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() != str(value)]
    if include is not None and include[0] in frame:
        field, value = include
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() == str(value)]
    return ckh.deterministic_cap(idx, cap)


def train_c4(
    cand: ckh.Candidate,
    seed: int,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
    exclude_attack_label: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    old_seed = ckh.SEED
    ckh.SEED = int(seed)
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int, local_exclude: tuple[str, str] | None = exclude) -> None:
        idx = idx_for(frame_by_role, role, phase, cap, exclude=local_exclude)
        xs.append(ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)[idx])
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append({"role": role, "phase": phase, "label": label, "rows": len(idx)})

    try:
        support_exclude = exclude
        if exclude_attack_label is not None:
            support_exclude = ("attack_label", exclude_attack_label)
        add("support_train", "fit", ckh.CLASS_ATTACK, FULL_CAP, local_exclude=support_exclude)
        add("id_calib", "fit", ckh.CLASS_ID, TRAIN_CAP)
        add("ood_val", "fit", ckh.CLASS_OOD, TRAIN_CAP)
        add("ood_stress", "fit", ckh.CLASS_HARD_OOD, TRAIN_CAP)
        x_train = np.vstack(xs)
        y_train = np.concatenate(ys)
        model = ckh.balanced_fit(ckh.build_model(cand.model, multiclass=True), x_train, y_train)
        return {"multiclass_model": model}, audit
    finally:
        ckh.SEED = old_seed


def thresholds_for(
    cand: ckh.Candidate,
    fitted: dict[str, Any],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    exclude: tuple[str, str] | None = None,
) -> dict[str, float]:
    scores = []
    roles_used = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = idx_for(frame_by_role, role, "select", FULL_CAP, exclude=exclude)
        if not len(idx):
            continue
        x = ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)[idx]
        scores.append(ckh.decision_scores(cand, fitted, x)["attack_score"])
        roles_used.append(role)
    if not scores:
        raise RuntimeError(f"No threshold rows after exclusion {exclude}")
    return {
        "attack_threshold": float(max(np.quantile(score, ckh.BENIGN_SAFE_Q) for score in scores)),
        "hard_ood_gate": float("nan"),
        "threshold_roles": "|".join(roles_used),
    }


def decide_part(
    cand: ckh.Candidate,
    fitted: dict[str, Any],
    thresholds: dict[str, float],
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
    if len(idx) == 0:
        frame["candidate"] = cand.name
        frame["role_kind"] = role_kind
        frame["attack_score"] = pd.Series(dtype=float)
        frame["hard_ood_score"] = pd.Series(dtype=float)
        frame["conflict_score"] = pd.Series(dtype=float)
        frame["candidate_raw_alarm"] = pd.Series(dtype=bool)
        frame["candidate_conflict_review"] = pd.Series(dtype=bool)
        frame["candidate_hard_alarm"] = pd.Series(dtype=bool)
        return frame
    x = ckh.feature_matrix(cand.feature_set, role, x_by_role, frame_by_role)[idx]
    score = ckh.decision_scores(cand, fitted, x)
    raw = score["attack_score"] > thresholds["attack_threshold"]
    review = raw & (score["conflict_score"] > score["attack_score"])
    hard = raw & ~review
    frame["candidate"] = cand.name
    frame["role_kind"] = role_kind
    frame["attack_score"] = score["attack_score"]
    frame["hard_ood_score"] = score["hard_ood_score"]
    frame["conflict_score"] = score["conflict_score"]
    frame["candidate_raw_alarm"] = raw
    frame["candidate_conflict_review"] = review
    frame["candidate_hard_alarm"] = hard
    return frame


def summarize_part(
    cand: ckh.Candidate,
    split: str,
    seed: int,
    role: str,
    phase: str,
    part: pd.DataFrame,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    rows = len(part)
    return {
        "candidate": cand.name,
        "split": split,
        "seed": seed,
        "role": role,
        "phase": phase,
        "rows": rows,
        "raw_alarm_rate": ckh.rate(part["candidate_raw_alarm"]) if rows else float("nan"),
        "conflict_review_rate": ckh.rate(part["candidate_conflict_review"]) if rows else float("nan"),
        "hard_alarm_rate": ckh.rate(part["candidate_hard_alarm"]) if rows else float("nan"),
        "review_count": int(part["candidate_conflict_review"].sum()) if rows else 0,
        "hard_count": int(part["candidate_hard_alarm"].sum()) if rows else 0,
        "attack_score_mean": float(part["attack_score"].mean()) if rows else float("nan"),
        "attack_score_p95": float(part["attack_score"].quantile(0.95)) if rows else float("nan"),
        "attack_threshold": thresholds["attack_threshold"],
        "threshold_roles": thresholds.get("threshold_roles", ""),
    }


def eval_all_roles(
    cand: ckh.Candidate,
    fitted: dict[str, Any],
    thresholds: dict[str, float],
    seed: int,
    split: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    parts: dict[str, pd.DataFrame] = {}
    for role, phase, role_kind in ROLE_EVAL:
        part = decide_part(cand, fitted, thresholds, role, phase, role_kind, x_by_role, frame_by_role, include=include, exclude=exclude)
        rows.append(summarize_part(cand, split, seed, role, phase, part, thresholds))
        parts[role] = part
    return rows, parts


def grouped_anatomy(
    parts: dict[str, pd.DataFrame],
    fields: list[str],
    split: str,
    seed: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for role, part in parts.items():
        for field in fields:
            if field not in part:
                continue
            for value, group in part.groupby(field, dropna=False, sort=True):
                rows = len(group)
                if rows == 0:
                    continue
                review_count = int(group["candidate_conflict_review"].sum())
                hard_count = int(group["candidate_hard_alarm"].sum())
                raw_count = int(group["candidate_raw_alarm"].sum())
                out.append(
                    {
                        "split": split,
                        "seed": seed,
                        "role": role,
                        "group_field": field,
                        "group_value": str(value),
                        "rows": rows,
                        "raw_alarm_rate": raw_count / rows,
                        "conflict_review_rate": review_count / rows,
                        "hard_alarm_rate": hard_count / rows,
                        "raw_alarm_count": raw_count,
                        "review_count": review_count,
                        "hard_count": hard_count,
                        "attack_score_mean": float(group["attack_score"].mean()),
                        "attack_score_p95": float(group["attack_score"].quantile(0.95)),
                    }
                )
    return out


def aggregate_seed_metrics(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame([row for row in role_rows if row["split"] == "seed_stability"])
    out: list[dict[str, Any]] = []
    for role, group in df.groupby("role", sort=True):
        row = {"role": role, "seeds": int(group["seed"].nunique()), "rows": int(group["rows"].iloc[0])}
        for metric in ["hard_alarm_rate", "conflict_review_rate", "raw_alarm_rate"]:
            values = group[metric].astype(float)
            row[f"{metric}_mean"] = float(values.mean())
            row[f"{metric}_std"] = float(values.std(ddof=0))
            row[f"{metric}_min"] = float(values.min())
            row[f"{metric}_max"] = float(values.max())
        out.append(row)
    return out


def select_leave_groups(anatomy: list[dict[str, Any]], max_groups: int) -> dict[str, list[str]]:
    df = pd.DataFrame(anatomy)
    out: dict[str, list[str]] = {"source_group": [], "device_family": [], "attack_label": []}
    if df.empty:
        return out
    # Focus on groups with actual burden, not tiny shards.  These are stress
    # probes, not exhaustive leave-one-out training.
    for field in ["source_group", "device_family"]:
        sub = df[
            (df["group_field"] == field)
            & (df["rows"].astype(int) >= 100)
            & (df["role"].isin(["id_calib", "ood_val", "ood_stress", "sealed_final_ood"]))
        ].copy()
        if sub.empty:
            continue
        sub["burden"] = sub["review_count"].astype(int) + 5 * sub["hard_count"].astype(int)
        sub = sub.sort_values(["burden", "rows"], ascending=False)
        out[field] = sub["group_value"].drop_duplicates().head(max_groups).tolist()
    sub = df[
        (df["group_field"] == "attack_label")
        & (df["rows"].astype(int) >= 20)
        & (df["role"].isin(["support_val", "same_file_query", "future_query", "sealed_final_attack"]))
    ].copy()
    if not sub.empty:
        sub["burden"] = sub["review_count"].astype(int) + (sub["rows"].astype(int) - sub["hard_count"].astype(int))
        sub = sub.sort_values(["burden", "rows"], ascending=False)
        out["attack_label"] = sub["group_value"].drop_duplicates().head(max_groups).tolist()
    return out


def build_readout(
    seed_summary: list[dict[str, Any]],
    primary_rows: list[dict[str, Any]],
    anatomy: list[dict[str, Any]],
    leave_rows: list[dict[str, Any]],
    selected_groups: dict[str, list[str]],
    seconds: float,
) -> list[str]:
    lines = [
        "# issue27ckj C4 stability and shortcut anatomy",
        "",
        "## Scope",
        "",
        "Diagnosis only. Fixed baseline: `C4_fewshot_multiclass_raw115_cap20000`.",
        "No new detector head, no causal/invariant repair, no threshold tuning.",
        "Sealed final roles remain report-only.",
        "",
        "## Seed stability summary",
        "",
        "| role | seeds | hard mean | hard min | hard max | review mean | review max | raw mean |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in seed_summary:
        lines.append(
            f"| {row['role']} | {row['seeds']} | {ckh.fmt(row['hard_alarm_rate_mean'])} | {ckh.fmt(row['hard_alarm_rate_min'])} | {ckh.fmt(row['hard_alarm_rate_max'])} | {ckh.fmt(row['conflict_review_rate_mean'])} | {ckh.fmt(row['conflict_review_rate_max'])} | {ckh.fmt(row['raw_alarm_rate_mean'])} |"
        )
    lines.extend(["", "## Primary seed42 role metrics", ""])
    lines.extend(["| role | rows | hard | review | review count | raw | threshold |", "|---|---:|---:|---:|---:|---:|---:|"])
    for row in primary_rows:
        lines.append(
            f"| {row['role']} | {row['rows']} | {ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {row['review_count']} | {ckh.fmt(row['raw_alarm_rate'])} | {ckh.fmt(row['attack_threshold'])} |"
        )
    lines.extend(["", "## Top review / hard groups", ""])
    lines.extend(["| role | field | value | rows | review | review count | hard | hard count |", "|---|---|---|---:|---:|---:|---:|---:|"])
    df = pd.DataFrame(anatomy)
    if not df.empty:
        df["burden"] = df["review_count"].astype(int) + 5 * df["hard_count"].astype(int)
        top = df[(df["rows"].astype(int) >= 50) & (df["burden"] > 0)].sort_values("burden", ascending=False).head(20)
        for _, row in top.iterrows():
            lines.append(
                f"| {row['role']} | {row['group_field']} | {str(row['group_value'])[:80]} | {row['rows']} | {ckh.fmt(row['conflict_review_rate'])} | {row['review_count']} | {ckh.fmt(row['hard_alarm_rate'])} | {row['hard_count']} |"
            )
    lines.extend(["", "## Leave-out stress groups", ""])
    for field, values in selected_groups.items():
        lines.append(f"- `{field}`: `{', '.join(values) if values else 'none'}`")
    lines.extend(["", "## Leave-out stress metrics", ""])
    lines.extend(["| split | held field | held value | role | rows | hard | review | raw | threshold |", "|---|---|---|---|---:|---:|---:|---:|---:|"])
    for row in leave_rows:
        if int(row["rows"]) == 0:
            continue
        lines.append(
            f"| {row['split']} | {row.get('held_field', '')} | {str(row.get('held_value', ''))[:70]} | {row['role']} | {row['rows']} | {ckh.fmt(row['hard_alarm_rate'])} | {ckh.fmt(row['conflict_review_rate'])} | {ckh.fmt(row['raw_alarm_rate'])} | {ckh.fmt(row['attack_threshold'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrail",
            "",
            "- If seed stability is good but group burden is concentrated, C4 is not enough; issue27ckk should repair training views with group/worst-group balancing.",
            "- If leave-out stress collapses under source/device/family, C4 has shortcut risk and should not be promoted as a robust detector.",
            "- Leave-attack-label-out is zero-shot attack stress only; failure there is a coverage/active-labeling signal, not a direct violation of the few-shot problem setting.",
            "",
            f"Runtime seconds: `{ckh.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--max-leave-groups", type=int, default=4)
    args = parser.parse_args()
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, support_labels, input_audit = cki.prepare_roles(args.smoke)
    add_diagnostic_columns(frame_by_role, support_labels)
    inventory = cki.role_inventory(frame_by_role)

    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    anatomy_rows: list[dict[str, Any]] = []
    leave_rows: list[dict[str, Any]] = []
    primary_rows: list[dict[str, Any]] = []
    primary_parts: dict[str, pd.DataFrame] = {}

    old_cap = ckh.BENIGN_CAP_PER_ROLE
    old_eval_cap = ckh.EVAL_CAP_PER_ROLE
    ckh.BENIGN_CAP_PER_ROLE = TRAIN_CAP
    ckh.EVAL_CAP_PER_ROLE = FULL_CAP
    try:
        for seed in SEEDS[:1] if args.smoke else SEEDS:
            cand = candidate(seed)
            fitted, audit = train_c4(cand, seed, x_by_role, frame_by_role)
            thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role)
            for item in audit:
                train_rows.append({"split": "seed_stability", "seed": seed, "candidate": cand.name, **item})
            rows, parts = eval_all_roles(cand, fitted, thresholds, seed, "seed_stability", x_by_role, frame_by_role)
            role_rows.extend(rows)
            if seed == SEEDS[0]:
                primary_rows = rows
                primary_parts = parts
                anatomy_rows = grouped_anatomy(
                    parts,
                    ["source_group", "device", "source_family", "device_family", "time_block", "attack_label", "attack_family", "support_seen"],
                    "primary_seed42",
                    seed,
                )

        selected_groups = select_leave_groups(anatomy_rows, args.max_leave_groups)
        stress_seed = SEEDS[0]
        for field in ["source_group", "device_family"]:
            for value in selected_groups.get(field, []):
                cand = candidate(stress_seed, f"_leave_{field}_{slug(value)}")
                fitted, audit = train_c4(cand, stress_seed, x_by_role, frame_by_role, exclude=(field, value))
                thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role, exclude=(field, value))
                for item in audit:
                    train_rows.append({"split": f"leave_{field}", "held_field": field, "held_value": value, "seed": stress_seed, "candidate": cand.name, **item})
                rows, _parts = eval_all_roles(
                    cand,
                    fitted,
                    thresholds,
                    stress_seed,
                    f"leave_{field}",
                    x_by_role,
                    frame_by_role,
                    include=(field, value),
                )
                for row in rows:
                    row["held_field"] = field
                    row["held_value"] = value
                leave_rows.extend(rows)

        for value in selected_groups.get("attack_label", []):
            cand = candidate(stress_seed, f"_leave_attack_label_{slug(value)}")
            fitted, audit = train_c4(cand, stress_seed, x_by_role, frame_by_role, exclude_attack_label=value)
            thresholds = thresholds_for(cand, fitted, x_by_role, frame_by_role)
            for item in audit:
                train_rows.append({"split": "leave_attack_label", "held_field": "attack_label", "held_value": value, "seed": stress_seed, "candidate": cand.name, **item})
            rows, _parts = eval_all_roles(
                cand,
                fitted,
                thresholds,
                stress_seed,
                "leave_attack_label",
                x_by_role,
                frame_by_role,
                include=("attack_label", value),
            )
            for row in rows:
                row["held_field"] = "attack_label"
                row["held_value"] = value
            leave_rows.extend(rows)
    finally:
        ckh.BENIGN_CAP_PER_ROLE = old_cap
        ckh.EVAL_CAP_PER_ROLE = old_eval_cap

    seed_summary = aggregate_seed_metrics(role_rows)
    seconds = time.time() - started
    cki.write_csv(OUT / "aggregate_seed_metrics.csv", seed_summary)
    cki.write_csv(OUT / "role_metrics_by_seed.csv", role_rows)
    cki.write_csv(OUT / "train_audit.csv", train_rows)
    cki.write_csv(OUT / "role_inventory.csv", inventory)
    cki.write_csv(OUT / "review_anatomy_by_group.csv", anatomy_rows)
    cki.write_csv(OUT / "leave_out_stress_metrics.csv", leave_rows)
    cki.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "C4-cap20000 stability, review anatomy, and bounded shortcut stress diagnosis",
            "smoke": args.smoke,
            "seeds": (SEEDS[:1] if args.smoke else SEEDS),
            "fixed_candidate": "C4_fewshot_multiclass_raw115_cap20000",
            "train_cap": TRAIN_CAP,
            "eval_cap": "full",
            "max_leave_groups": args.max_leave_groups,
            "selected_leave_groups": selected_groups,
            "sealed_final_roles_used_for_training": False,
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "aggregate_seed_metrics.csv",
                "role_metrics_by_seed.csv",
                "train_audit.csv",
                "role_inventory.csv",
                "review_anatomy_by_group.csv",
                "leave_out_stress_metrics.csv",
                "diagnostic_interpretation.md",
                "shortcut_risk_report.md",
                "codex_readout.md",
            ],
        },
    )
    readout = build_readout(seed_summary, primary_rows, anatomy_rows, leave_rows, selected_groups, seconds)
    cki.write_md(OUT / "shortcut_risk_report.md", readout)
    cki.write_md(OUT / "codex_readout.md", readout)
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


if __name__ == "__main__":
    main()
