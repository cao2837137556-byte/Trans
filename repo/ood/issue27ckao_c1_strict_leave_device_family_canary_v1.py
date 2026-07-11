"""issue27ckao: C1 strict leave-device-family canary.

Purpose
-------
This is a Level-2 generalization canary for the new external-style frontend.
It answers a narrow question before we build a more advanced backend:

    Does the C1 CICFlow-style evidence space survive a strict
    leave-device-family protocol better than raw115?

Boundary
--------
No query/future/sealed rows are used for fitting, thresholding, model choice,
or feature selection.  For each held device_family:

* fit roles exclude the held family;
* threshold/select roles exclude the held family;
* report rows include only the held family;
* source_group/device are used only to define environment splits and audits,
  not as model features.

This script is intentionally not the final backend route.  It is the canary
that decides whether C1 is a credible Level-2 frontend foundation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckao_c1_strict_leave_device_family_canary_v1_2026-07-09"
OUT_BASE = cko.ROOT / "runs" / ISSUE

DEFAULT_CANDIDATES = "R0_raw115_only_histgb,C1_cicflow_style_only_histgb"
KNOWN_CANARY_FAMILIES = [
    # Two old failure OOD families.
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    # Two attack-bearing families in the current certified attack roles.
    "domotic-monitor",
    "combined-cycle",
    # One large sealed OOD family, useful when max_recorded_index keeps it.
    "iotsim-ip-camera-street",
]


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def source_or_device_family(value: Any) -> str:
    text = str(value)
    if not text or text == "nan":
        return "NA"
    stem = Path(text).stem
    return re.sub(r"-\d+$", "", stem) or "NA"


def add_family_columns(frame_by_role: dict[str, pd.DataFrame]) -> None:
    for _role, frame in frame_by_role.items():
        if "source_group" in frame:
            frame["source_family"] = frame["source_group"].map(source_or_device_family)
        else:
            frame["source_family"] = "NA"
        if "device" in frame:
            device_family = frame["device"].map(source_or_device_family)
        else:
            device_family = pd.Series(["NA"] * len(frame), index=frame.index)
        source_family = frame["source_family"].astype(str)
        device_family = device_family.astype(str)
        frame["device_family"] = np.where(
            (device_family == "") | (device_family == "NA"),
            source_family,
            device_family,
        )


def cap_value(cap: int) -> int:
    return cko.FULL_CAP if int(cap) <= 0 else int(cap)


def role_indices_filtered(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    frame = frame_by_role[role]
    if phase == "all":
        idx = np.arange(len(frame), dtype=np.int64)
    else:
        idx = np.flatnonzero(frame["phase"].astype(str).to_numpy() == str(phase))
    if include is not None and include[0] in frame:
        field, value = include
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() == str(value)]
    if exclude is not None and exclude[0] in frame:
        field, value = exclude
        idx = idx[frame.iloc[idx][field].astype(str).to_numpy() != str(value)]
    return cko.deterministic_cap(idx, cap_value(cap))


def count_for(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    held_value: str,
    cap: int,
) -> int:
    return int(len(role_indices_filtered(frame_by_role, role, phase, cap, include=("device_family", held_value))))


def count_without(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    held_value: str,
    cap: int,
) -> int:
    return int(len(role_indices_filtered(frame_by_role, role, phase, cap, exclude=("device_family", held_value))))


def select_leave_groups(
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    max_groups: int,
    min_eval_rows: int,
    requested: str,
) -> list[dict[str, Any]]:
    values: set[str] = set()
    for role in ["ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"]:
        frame = frame_by_role.get(role)
        if frame is not None and "device_family" in frame:
            values.update(v for v in frame["device_family"].astype(str).dropna().unique().tolist() if v and v != "NA")

    rows: dict[str, dict[str, Any]] = {}
    for value in sorted(values):
        counts = {
            "ood_val": count_for(frame_by_role, "ood_val", "select", value, eval_cap),
            "ood_stress": count_for(frame_by_role, "ood_stress", "select", value, eval_cap),
            "sealed_final_ood": count_for(frame_by_role, "sealed_final_ood", "all", value, eval_cap),
            "future_query": count_for(frame_by_role, "future_query", "select", value, eval_cap),
            "sealed_final_attack": count_for(frame_by_role, "sealed_final_attack", "all", value, eval_cap),
        }
        total = int(sum(counts.values()))
        if total >= int(min_eval_rows):
            rows[value] = {
                "held_field": "device_family",
                "held_value": value,
                "total_eval_rows": total,
                "ood_eval_rows": int(counts["ood_val"] + counts["ood_stress"] + counts["sealed_final_ood"]),
                "attack_eval_rows": int(counts["future_query"] + counts["sealed_final_attack"]),
                **counts,
            }

    selected: list[dict[str, Any]] = []
    if requested:
        for value in [v.strip() for v in requested.split(",") if v.strip()]:
            if value in rows and value not in {r["held_value"] for r in selected}:
                selected.append(rows[value])
    else:
        for value in KNOWN_CANARY_FAMILIES:
            if value in rows and value not in {r["held_value"] for r in selected}:
                selected.append(rows[value])
        # Add strongest OOD and attack families not already covered.
        ood_sorted = sorted(rows.values(), key=lambda r: (int(r["ood_eval_rows"]), int(r["total_eval_rows"])), reverse=True)
        attack_sorted = sorted(rows.values(), key=lambda r: (int(r["attack_eval_rows"]), int(r["total_eval_rows"])), reverse=True)
        for pool in [ood_sorted, attack_sorted]:
            for row in pool:
                if len(selected) >= int(max_groups):
                    break
                if row["held_value"] not in {r["held_value"] for r in selected}:
                    selected.append(row)
            if len(selected) >= int(max_groups):
                break

    return selected[: int(max_groups)]


def build_train_set(
    candidate: ckai.Candidate,
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    train_cap: int,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []
    exclude = ("device_family", held_value)

    def add(role: str, phase: str, label: int, cap: int) -> None:
        before = len(role_indices_filtered(frame_by_role, role, phase, cap, include=None, exclude=None))
        idx = role_indices_filtered(frame_by_role, role, phase, cap, exclude=exclude)
        mat = frontend.matrix(candidate, role, idx)
        xs.append(mat)
        ys.append(np.full(len(idx), int(label), dtype=np.int64))
        audit.append(
            {
                "candidate": candidate.name,
                "held_field": "device_family",
                "held_value": held_value,
                "role": role,
                "phase": phase,
                "label": int(label),
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
    return x, y, audit


def fit_candidate(
    candidate: ckai.Candidate,
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    train_cap: int,
) -> tuple[Any, list[dict[str, Any]]]:
    x, y, audit = build_train_set(candidate, frontend, frame_by_role, held_value, train_cap)
    if len(np.unique(y)) < 2:
        raise RuntimeError(f"not enough training classes for held={held_value}, candidate={candidate.name}")
    model = ckh.balanced_fit(ckh.build_model(candidate.model, multiclass=True), x, y)
    for row in audit:
        row["train_classes"] = "|".join(str(int(v)) for v in sorted(np.unique(y).tolist()))
        row["train_rows_total"] = int(len(y))
    return model, audit


def attack_threshold(
    candidate: ckai.Candidate,
    model: Any,
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    eval_cap: int,
) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    parts: list[np.ndarray] = []
    exclude = ("device_family", held_value)
    for role in ["id_calib", "ood_val", "ood_stress"]:
        before = len(role_indices_filtered(frame_by_role, role, "select", eval_cap))
        idx = role_indices_filtered(frame_by_role, role, "select", eval_cap, exclude=exclude)
        if len(idx):
            scores = ckai.score_attack(model, frontend.matrix(candidate, role, idx))
            parts.append(scores)
            q = float(np.quantile(scores, ckai.BENIGN_Q))
        else:
            q = float("nan")
        rows.append(
            {
                "candidate": candidate.name,
                "held_field": "device_family",
                "held_value": held_value,
                "role": role,
                "phase": "select",
                "rows_before_exclude": int(before),
                "rows_after_exclude": int(len(idx)),
                "held_rows_removed": int(before - len(idx)),
                "benign_q": float(ckai.BENIGN_Q),
                "role_attack_quantile": q,
            }
        )
    if not parts:
        raise RuntimeError(f"No non-held benign/OOD threshold rows for held={held_value}")
    threshold = float(max(np.quantile(part, ckai.BENIGN_Q) for part in parts if len(part)))
    for row in rows:
        row["attack_threshold"] = threshold
    return threshold, rows


def eval_held_role(
    candidate: ckai.Candidate,
    model: Any,
    threshold: float,
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held_value: str,
    role: str,
    phase: str,
    kind: str,
    eval_cap: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices_filtered(frame_by_role, role, phase, eval_cap, include=("device_family", held_value))
    if len(idx) == 0:
        return (
            {
                "candidate": candidate.name,
                "held_field": "device_family",
                "held_value": held_value,
                "role": role,
                "phase": phase,
                "role_kind": kind,
                "rows": 0,
                "attack_threshold": float(threshold),
                "hard_alarm_rate": float("nan"),
                "attack_score_mean": float("nan"),
                "conflict_score_mean": float("nan"),
                "desired_hard_direction": "high" if "attack" in kind else "low",
                "error_rate_for_role": float("nan"),
            },
            pd.DataFrame(),
        )
    x = frontend.matrix(candidate, role, idx)
    attack = ckai.score_attack(model, x)
    conflict = ckai.score_conflict(model, x)
    hard = attack > float(threshold)
    desired = "high" if "attack" in kind else "low"
    hard_rate = ckg.rate(hard)
    err = 1.0 - hard_rate if desired == "high" else hard_rate
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    part["candidate"] = candidate.name
    part["held_value"] = held_value
    part["role"] = role
    part["role_kind"] = kind
    part["attack_score"] = attack
    part["conflict_score"] = conflict
    part["hard_alarm"] = hard
    return (
        {
            "candidate": candidate.name,
            "held_field": "device_family",
            "held_value": held_value,
            "role": role,
            "phase": phase,
            "role_kind": kind,
            "rows": int(len(idx)),
            "attack_threshold": float(threshold),
            "hard_alarm_rate": hard_rate,
            "attack_score_mean": float(np.mean(attack)),
            "conflict_score_mean": float(np.mean(conflict)),
            "desired_hard_direction": desired,
            "error_rate_for_role": float(err),
        },
        part,
    )


def build_preflight_audit(
    frame_by_role: dict[str, pd.DataFrame],
    selected_groups: list[dict[str, Any]],
    train_cap: int,
    eval_cap: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for held in selected_groups:
        value = str(held["held_value"])
        for role, phase, bucket, cap in [
            ("support_train", "fit", "fit", cko.FULL_CAP),
            ("id_calib", "fit", "fit", train_cap),
            ("ood_val", "fit", "fit", train_cap),
            ("ood_stress", "fit", "fit", train_cap),
            ("id_calib", "select", "threshold", eval_cap),
            ("ood_val", "select", "threshold", eval_cap),
            ("ood_stress", "select", "threshold", eval_cap),
            ("support_val", "select", "support_select_not_threshold_benign", eval_cap),
        ]:
            all_idx = role_indices_filtered(frame_by_role, role, phase, cap)
            kept_idx = role_indices_filtered(frame_by_role, role, phase, cap, exclude=("device_family", value))
            leaked = int(np.sum(frame_by_role[role].iloc[kept_idx]["device_family"].astype(str).to_numpy() == value)) if len(kept_idx) else 0
            rows.append(
                {
                    "held_value": value,
                    "bucket": bucket,
                    "role": role,
                    "phase": phase,
                    "rows_before_exclude": int(len(all_idx)),
                    "rows_after_exclude": int(len(kept_idx)),
                    "held_rows_removed": int(len(all_idx) - len(kept_idx)),
                    "held_rows_remaining_after_exclude": leaked,
                    "pass_no_held_leakage": bool(leaked == 0),
                }
            )
        for role, phase, kind in cko.ROLE_EVAL:
            idx = role_indices_filtered(frame_by_role, role, phase, eval_cap, include=("device_family", value))
            nonheld = 0
            if len(idx):
                nonheld = int(np.sum(frame_by_role[role].iloc[idx]["device_family"].astype(str).to_numpy() != value))
            rows.append(
                {
                    "held_value": value,
                    "bucket": "eval_include_only",
                    "role": role,
                    "phase": phase,
                    "rows_before_exclude": "",
                    "rows_after_exclude": int(len(idx)),
                    "held_rows_removed": "",
                    "held_rows_remaining_after_exclude": "",
                    "nonheld_rows_in_eval_include": nonheld,
                    "pass_eval_only_held": bool(nonheld == 0),
                }
            )
    return rows


def build_readout(
    selected_groups: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    seconds: float,
    mode: str,
) -> list[str]:
    lines = [
        f"# {ISSUE}",
        "",
        f"Mode: `{mode}`",
        "",
        "## Selected held device families",
        "",
        "| held family | total | OOD rows | attack rows | ood_val | ood_stress | sealed OOD | future attack | sealed attack |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in selected_groups:
        lines.append(
            f"| {row['held_value']} | {row['total_eval_rows']} | {row['ood_eval_rows']} | {row['attack_eval_rows']} | "
            f"{row['ood_val']} | {row['ood_stress']} | {row['sealed_final_ood']} | {row['future_query']} | {row['sealed_final_attack']} |"
        )
    if role_rows:
        lines.extend(
            [
                "",
                "## Held-family evaluation",
                "",
                "| candidate | held family | role | rows | hard rate | desired | error |",
                "|---|---|---|---:|---:|---|---:|",
            ]
        )
        for row in role_rows:
            if row["role"] not in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}:
                continue
            lines.append(
                f"| {row['candidate']} | {row['held_value']} | {row['role']} | {row['rows']} | "
                f"{cko.fmt(row['hard_alarm_rate'])} | {row['desired_hard_direction']} | {cko.fmt(row['error_rate_for_role'])} |"
            )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit roles exclude the held device_family.",
            "- Threshold/select roles exclude the held device_family.",
            "- Evaluation includes only the held device_family.",
            "- Query/future/sealed roles remain report-only.",
            "- This is a Level-2 canary, not cross-dataset proof.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT_BASE if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)

    smoke = not bool(args.full)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke)
    x_by_role, frame_by_role, cap_rows = ckai.filter_roles_by_recorded_index(
        x_by_role,
        frame_by_role,
        int(args.max_recorded_index),
    )
    add_family_columns(frame_by_role)

    selected_groups = select_leave_groups(
        frame_by_role,
        int(args.eval_cap),
        int(args.max_leave_groups),
        int(args.min_eval_rows),
        str(args.held_values),
    )
    if not selected_groups:
        raise RuntimeError("No held device_family groups selected; lower --min-eval-rows or inspect roles")

    preflight_rows = build_preflight_audit(frame_by_role, selected_groups, int(args.train_cap), int(args.eval_cap))
    preflight_pass = all(
        bool(row.get("pass_no_held_leakage", True)) and bool(row.get("pass_eval_only_held", True))
        for row in preflight_rows
    )

    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    part_frames: list[pd.DataFrame] = []

    if args.mode == "smoke":
        if not preflight_pass:
            raise RuntimeError("Preflight failed; refusing to run smoke")
        cache = ckai.ExternalFlowFeatureCache(cko.GOTHAM_ZIP)
        frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)
        candidate_names = {v.strip() for v in str(args.candidates).split(",") if v.strip()}
        candidates = [c for c in ckai.CANDIDATES if c.name in candidate_names]
        if not candidates:
            raise RuntimeError("No valid candidates selected")
        for held in selected_groups:
            held_value = str(held["held_value"])
            for candidate in candidates:
                model, audit = fit_candidate(candidate, frontend, frame_by_role, held_value, int(args.train_cap))
                train_rows.extend(audit)
                threshold, thr_rows = attack_threshold(candidate, model, frontend, frame_by_role, held_value, int(args.eval_cap))
                threshold_rows.extend(thr_rows)
                for role, phase, kind in cko.ROLE_EVAL:
                    row, part = eval_held_role(
                        candidate,
                        model,
                        threshold,
                        frontend,
                        frame_by_role,
                        held_value,
                        role,
                        phase,
                        kind,
                        int(args.eval_cap),
                    )
                    role_rows.append(row)
                    part_frames.append(part)
        cko.write_csv(out / "external_extraction_audit.csv", cache.audit_rows)
        cko.write_csv(out / "attack_family_summary.csv", ckai.family_summary(part_frames))
        cko.write_csv(out / "source_group_summary.csv", ckai.grouped_performance_summary(part_frames, "source_group", min_rows=int(args.group_min_rows)))
        cko.write_csv(out / "device_summary.csv", ckai.grouped_performance_summary(part_frames, "device", min_rows=int(args.group_min_rows)))

    seconds = time.time() - started
    cko.write_csv(out / "selected_leave_groups.csv", selected_groups)
    cko.write_csv(out / "strict_leave_preflight_audit.csv", preflight_rows)
    cko.write_csv(out / "role_cap_audit.csv", cap_rows)
    cko.write_csv(out / "leave_role_metrics.csv", role_rows)
    cko.write_csv(out / "leave_train_audit.csv", train_rows)
    cko.write_csv(out / "leave_threshold_audit.csv", threshold_rows)
    cko.write_md(out / "codex_readout.md", build_readout(selected_groups, role_rows, seconds, args.mode))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "mode": args.mode,
            "full": bool(args.full),
            "smoke_input": bool(smoke),
            "max_recorded_index": int(args.max_recorded_index),
            "train_cap": int(args.train_cap),
            "eval_cap": int(args.eval_cap),
            "max_leave_groups": int(args.max_leave_groups),
            "min_eval_rows": int(args.min_eval_rows),
            "candidates": str(args.candidates),
            "selected_leave_groups": selected_groups,
            "preflight_pass": bool(preflight_pass),
            "data_use_boundary": {
                "fit_roles_exclude_held_device_family": True,
                "threshold_roles_exclude_held_device_family": True,
                "eval_roles_include_only_held_device_family": True,
                "query_future_sealed_used_for_training_or_thresholding": False,
                "source_group_device_used_as_features": False,
            },
            "input_audit": input_audit,
            "role_cap_audit": cap_rows,
            "seconds": seconds,
        },
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": args.mode,
                "preflight_pass": bool(preflight_pass),
                "out": str(out),
                "held_groups": [r["held_value"] for r in selected_groups],
                "seconds": seconds,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "smoke"], default="preflight")
    parser.add_argument("--full", action="store_true", help="Use full 1M role materialization before max_recorded_index filtering.")
    parser.add_argument("--max-recorded-index", type=int, default=300000)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=8000)
    parser.add_argument("--max-leave-groups", type=int, default=5)
    parser.add_argument("--min-eval-rows", type=int, default=128)
    parser.add_argument("--held-values", default="", help="Comma-separated device_family values. Empty uses canary auto-selection.")
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES)
    parser.add_argument("--group-min-rows", type=int, default=30)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
