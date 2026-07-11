"""issue27ckt: leave-device-family stress for CKS neural frontend/head.

This diagnostic asks whether the promising issue27cks capped-smoke result is
still credible when an entire device family is removed from legal fit and
threshold-selection roles, then evaluated only on the held family.

It is a stress diagnostic, not a repair:

    fit/threshold exclude held device_family
    eval includes only held device_family
    query/future/sealed rows stay report-only
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

import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27cks_neural_causal_selective_head_v1 as cks  # noqa: E402


ISSUE = "issue27ckt_neural_leave_device_family_stress_v1_2026-07-01"
OUT = cko.ROOT / "runs" / ISSUE

DEFAULT_CANDIDATE_NAMES = {
    "N1_raw_flow_mlp_selective",
    "N2_raw_flow_aug_mlp_selective",
    "N3_raw_flow_aug_adv_rex_selective",
}


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def family(value: Any) -> str:
    text = str(value)
    if not text or text == "nan":
        return "NA"
    stem = Path(text).stem
    return re.sub(r"-\d+$", "", stem)


def add_family_columns(frame_by_role: dict[str, pd.DataFrame]) -> None:
    for _role, frame in frame_by_role.items():
        if "source_group" in frame:
            frame["source_family"] = frame["source_group"].map(family)
        else:
            frame["source_family"] = "NA"
        if "device" in frame:
            device_family = frame["device"].map(family)
        else:
            device_family = pd.Series(["NA"] * len(frame), index=frame.index)
        source_family = frame["source_family"].astype(str)
        device_family = device_family.astype(str)
        frame["device_family"] = np.where((device_family == "") | (device_family == "NA"), source_family, device_family)


def rows_for(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, field: str, value: str, cap: int) -> int:
    if role not in frame_by_role or field not in frame_by_role[role]:
        return 0
    idx = cks.role_indices_filtered(frame_by_role, role, phase, cap, include=(field, value))
    return int(len(idx))


def select_leave_groups(frame_by_role: dict[str, pd.DataFrame], max_groups: int, min_rows: int, eval_cap: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    values: set[str] = set()
    for role in ["ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"]:
        frame = frame_by_role.get(role)
        if frame is not None and "device_family" in frame:
            values.update(v for v in frame["device_family"].astype(str).dropna().unique().tolist() if v and v != "NA")
    for value in sorted(values):
        counts = {
            "ood_val": rows_for(frame_by_role, "ood_val", "select", "device_family", value, eval_cap),
            "ood_stress": rows_for(frame_by_role, "ood_stress", "select", "device_family", value, eval_cap),
            "sealed_final_ood": rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", value, eval_cap),
            "future_query": rows_for(frame_by_role, "future_query", "select", "device_family", value, eval_cap),
            "sealed_final_attack": rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", value, eval_cap),
        }
        total = sum(counts.values())
        if total >= min_rows:
            rows.append({"held_field": "device_family", "held_value": value, "total_eval_rows": total, **counts})
    rows.sort(key=lambda r: (int(r["sealed_final_ood"]) + int(r["ood_stress"]) + int(r["future_query"]), int(r["total_eval_rows"])), reverse=True)
    return rows[:max_groups]


def eval_leave_group(
    candidate: cks.NeuralCandidate,
    held_value: str,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    exclude = ("device_family", held_value)
    include = ("device_family", held_value)
    fitted, train_rows, history_rows = cks.fit_neural_candidate(candidate, builder, frame_by_role, train_cap, exclude=exclude)
    attack_thr = cks.attack_threshold(fitted, builder, frame_by_role, eval_cap, exclude=exclude)
    policy = cks.REVIEW_POLICIES[0]
    thr = cks.review_margin_threshold(fitted, builder, frame_by_role, attack_thr, eval_cap, policy, exclude=exclude)

    eval_rows: list[dict[str, Any]] = []
    for role, phase, kind in cko.ROLE_EVAL:
        row, _part = cks.eval_role(
            fitted,
            policy,
            thr,
            builder,
            frame_by_role,
            role,
            phase,
            kind,
            eval_cap,
            include=include,
        )
        row["split"] = "leave_device_family"
        row["held_field"] = "device_family"
        row["held_value"] = held_value
        eval_rows.append(row)
    for row in train_rows:
        row["candidate"] = candidate.name
        row["split"] = "leave_device_family"
        row["held_field"] = "device_family"
        row["held_value"] = held_value
    for row in history_rows:
        row["split"] = "leave_device_family"
        row["held_field"] = "device_family"
        row["held_value"] = held_value
    threshold_rows = [{**thr, "held_field": "device_family", "held_value": held_value}]
    return eval_rows, train_rows + threshold_rows, history_rows


def build_readout(leave_rows: list[dict[str, Any]], selected_groups: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckt neural leave-device-family stress v1",
        "",
        "## Selected held groups",
        "",
        "| held family | total eval rows | ood_val | ood_stress | sealed OOD | future attack | sealed attack |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in selected_groups:
        lines.append(
            f"| {row['held_value']} | {row['total_eval_rows']} | {row['ood_val']} | {row['ood_stress']} | "
            f"{row['sealed_final_ood']} | {row['future_query']} | {row['sealed_final_attack']} |"
        )

    lines.extend(
        [
            "",
            "## Leave-device-family stress",
            "",
            "| candidate | held family | role | rows | hard | review | raw |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in leave_rows:
        if row["role"] not in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}:
            continue
        lines.append(
            f"| {row['candidate']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['hard_alarm_rate'])} | {cko.fmt(row['conflict_review_rate'])} | {cko.fmt(row['raw_alarm_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit and threshold selection exclude the held device_family.",
            "- Evaluation includes only the held device_family.",
            "- P0 conflict-only policy is used to avoid hiding failure inside extra review.",
            "- This is still capped local smoke, not full cross-dataset proof.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    cks.set_seeds()
    OUT.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(True)
    x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
        x_by_role,
        frame_by_role,
        int(args.role_cap),
        int(args.source_cap),
        cap_rule="leave-device-family capped local stress",
    )
    add_family_columns(frame_by_role)

    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    if args.held_values:
        selected_groups = []
        for value in [item.strip() for item in args.held_values.split(",") if item.strip()]:
            counts = {
                "ood_val": rows_for(frame_by_role, "ood_val", "select", "device_family", value, args.eval_cap),
                "ood_stress": rows_for(frame_by_role, "ood_stress", "select", "device_family", value, args.eval_cap),
                "sealed_final_ood": rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", value, args.eval_cap),
                "future_query": rows_for(frame_by_role, "future_query", "select", "device_family", value, args.eval_cap),
                "sealed_final_attack": rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", value, args.eval_cap),
            }
            selected_groups.append({"held_field": "device_family", "held_value": value, "total_eval_rows": sum(counts.values()), **counts})
    else:
        selected_groups = select_leave_groups(frame_by_role, args.max_leave_groups, args.min_eval_rows, args.eval_cap)
    candidate_names = set(args.candidates.split(",")) if args.candidates else DEFAULT_CANDIDATE_NAMES
    candidates = [c for c in cks.NEURAL_CANDIDATES if c.name in candidate_names]

    leave_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    for held in selected_groups:
        held_value = str(held["held_value"])
        for candidate in candidates:
            rows, train, hist = eval_leave_group(candidate, held_value, builder, frame_by_role, args.train_cap, args.eval_cap)
            leave_rows.extend(rows)
            train_rows.extend(train)
            history_rows.extend(hist)

    seconds = time.time() - started
    cko.write_csv(OUT / "selected_leave_groups.csv", selected_groups)
    cko.write_csv(OUT / "leave_device_family_stress_metrics.csv", leave_rows)
    cko.write_csv(OUT / "leave_train_and_threshold_audit.csv", train_rows)
    cko.write_csv(OUT / "leave_train_history_and_env_audit.csv", history_rows)
    cko.write_csv(OUT / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(OUT / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_md(OUT / "codex_readout.md", build_readout(leave_rows, selected_groups, seconds))
    cko.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "leave-device-family stress for CKS neural candidates",
            "role_cap": args.role_cap,
            "source_cap": args.source_cap,
            "train_cap": args.train_cap,
            "eval_cap": args.eval_cap,
            "max_leave_groups": args.max_leave_groups,
            "min_eval_rows": args.min_eval_rows,
            "selected_leave_groups": selected_groups,
            "candidates": [asdict(c) for c in candidates],
            "data_use_boundary": {
                "fit_and_threshold_exclude": "held device_family",
                "eval_include": "held device_family only",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "input_audit": input_audit,
            "role_cap_audit": role_cap_rows,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(OUT), "held_groups": len(selected_groups), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=4096)
    parser.add_argument("--source-cap", type=int, default=4096)
    parser.add_argument("--train-cap", type=int, default=2048)
    parser.add_argument("--eval-cap", type=int, default=4096)
    parser.add_argument("--max-leave-groups", type=int, default=3)
    parser.add_argument("--min-eval-rows", type=int, default=128)
    parser.add_argument("--held-values", default="", help="comma-separated device_family values to stress instead of auto-selection")
    parser.add_argument("--candidates", default="N1_raw_flow_mlp_selective,N2_raw_flow_aug_mlp_selective,N3_raw_flow_aug_adv_rex_selective")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
