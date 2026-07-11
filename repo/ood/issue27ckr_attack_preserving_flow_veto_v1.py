"""issue27ckr: attack-preserving flow-temporal veto v1.

This runner keeps raw115 as the primary attack detector and uses
flow-temporal evidence only as a constrained review/veto layer.

Protocol boundary:

- Raw115 and flow-temporal encoders are fit only on legal fit roles.
- A binary evidence gate is trained on out-of-fold raw/flow probabilities from
  the same legal fit roles.
- Gate thresholds are selected only from support_val attack rows, by explicit
  attack-hard drop budgets.
- same_file/future/sealed rows remain report-only.

Decision:

    raw115 alarm -> raw115 conflict check -> optional flow evidence review

The flow gate can only turn a raw hard alarm into review; it never creates a
new attack alarm.  This is deliberately attack-preserving and conservative.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402


ISSUE = "issue27ckr_attack_preserving_flow_veto_v1_2026-07-01"
OUT = cko.ROOT / "runs" / ISSUE


@dataclass(frozen=True)
class VetoBudget:
    name: str
    max_support_hard_drop: float
    max_gate_attack_threshold: float
    description: str


VETO_BUDGETS = [
    VetoBudget(
        "R1_gate_abs050_drop005",
        0.0050,
        0.50,
        "Review only if the gate is confidently non-attack: P(attack) < 0.50; support attack hard drop budget <= 0.50pp.",
    ),
    VetoBudget(
        "R2_gate_abs025_drop005",
        0.0050,
        0.25,
        "Review only if the gate is strongly non-attack: P(attack) < 0.25; support attack hard drop budget <= 0.50pp.",
    ),
    VetoBudget(
        "R3_gate_abs010_drop005",
        0.0050,
        0.10,
        "Review only if the gate is very strongly non-attack: P(attack) < 0.10; support attack hard drop budget <= 0.50pp.",
    ),
    VetoBudget(
        "R4_gate_abs050_drop010",
        0.0100,
        0.50,
        "Same confident non-attack gate with a looser support attack hard drop budget <= 1.00pp.",
    ),
]


def positive_score(model: Any, x: np.ndarray) -> np.ndarray:
    return ckh.positive_score(model, np.asarray(x, dtype=np.float32), positive_label=1)


def proba_scores(proba: np.ndarray) -> dict[str, np.ndarray]:
    attack = proba[:, ckh.CLASS_ATTACK]
    hard_ood = proba[:, ckh.CLASS_HARD_OOD]
    ood = proba[:, ckh.CLASS_OOD]
    identity = proba[:, ckh.CLASS_ID]
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "ood_score": ood,
        "id_score": identity,
        "conflict_score": np.maximum.reduce([identity, ood, hard_ood]),
    }


def evidence_features(raw_proba: np.ndarray, flow_proba: np.ndarray) -> np.ndarray:
    return ckq.evidence_from_block_probas({"raw": raw_proba, "flow": flow_proba}, include_margins=True)


def fit_evidence_gate(
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    chunks, y4, train_audit = ckq.fit_chunks(frame_by_role, train_cap)
    x_raw = ckq.matrix_for_chunks(builder, ckq.RAW_BLOCK, chunks)
    x_flow = ckq.matrix_for_chunks(builder, ckq.FLOW_BLOCK, chunks)
    raw_oof, raw_full, raw_rows = ckq.fit_block_oof_and_full("raw", x_raw, y4)
    flow_oof, flow_full, flow_rows = ckq.fit_block_oof_and_full("flow_temporal", x_flow, y4)

    gate_x = evidence_features(raw_oof, flow_oof)
    gate_y = (y4 == ckh.CLASS_ATTACK).astype(np.int64)
    gate = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=False), gate_x, gate_y)
    gate_score = positive_score(gate, gate_x)
    pred = gate_score >= 0.5
    gate_rows = [
        {
            "gate": "binary_attack_preserving_oof_gate",
            "train_rows": len(gate_y),
            "feature_dim": gate_x.shape[1],
            "attack_rows": int(np.sum(gate_y == 1)),
            "benign_rows": int(np.sum(gate_y == 0)),
            "train_accuracy_at_0_5": float(np.mean(pred == gate_y)) if len(gate_y) else float("nan"),
            "note": "gate trained on out-of-fold raw/flow evidence from legal fit roles only",
        }
    ]
    for row in train_audit:
        row["candidate"] = "shared_raw_flow_gate_fit_set"
    fitted = {"raw_model": raw_full, "flow_model": flow_full, "gate_model": gate}
    return fitted, train_audit, raw_rows + flow_rows + gate_rows


def raw_attack_threshold(fitted: dict[str, Any], builder: ckq.FlowTemporalBuilder, frame_by_role: dict[str, pd.DataFrame], eval_cap: int) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = cko.role_indices(frame_by_role, role, "select", eval_cap)
        x = builder.matrix(ckq.RAW_BLOCK, role, idx)
        raw_proba = ckq.proba4(fitted["raw_model"], x)
        parts.append(raw_proba[:, ckh.CLASS_ATTACK])
    return float(max(np.quantile(part, cko.BENIGN_SAFE_Q) for part in parts))


def role_evidence(
    fitted: dict[str, Any],
    builder: ckq.FlowTemporalBuilder,
    role: str,
    idx: np.ndarray,
) -> dict[str, np.ndarray]:
    raw_x = builder.matrix(ckq.RAW_BLOCK, role, idx)
    flow_x = builder.matrix(ckq.FLOW_BLOCK, role, idx)
    raw_proba = ckq.proba4(fitted["raw_model"], raw_x)
    flow_proba = ckq.proba4(fitted["flow_model"], flow_x)
    gate_x = evidence_features(raw_proba, flow_proba)
    gate_attack = positive_score(fitted["gate_model"], gate_x)
    raw = proba_scores(raw_proba)
    flow = proba_scores(flow_proba)
    out = {
        "raw_attack_score": raw["attack_score"],
        "raw_conflict_score": raw["conflict_score"],
        "raw_hard_ood_score": raw["hard_ood_score"],
        "flow_attack_score": flow["attack_score"],
        "flow_conflict_score": flow["conflict_score"],
        "flow_hard_ood_score": flow["hard_ood_score"],
        "gate_attack_score": gate_attack,
        # Compatibility with aggregate/readout expectations.
        "attack_score": raw["attack_score"],
        "conflict_score": np.maximum(raw["conflict_score"], 1.0 - gate_attack),
    }
    return out


def baseline_decision(score: dict[str, np.ndarray], raw_threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw_alarm = score["raw_attack_score"] > raw_threshold
    raw_conflict = raw_alarm & (score["raw_conflict_score"] > score["raw_attack_score"])
    raw_hard = raw_alarm & (~raw_conflict)
    return raw_alarm, raw_conflict, raw_hard


def gate_threshold_for_budget(
    fitted: dict[str, Any],
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    raw_threshold: float,
    eval_cap: int,
    budget: VetoBudget,
) -> dict[str, Any]:
    idx = cko.role_indices(frame_by_role, "support_val", "select", eval_cap)
    score = role_evidence(fitted, builder, "support_val", idx)
    raw_alarm, raw_conflict, raw_hard = baseline_decision(score, raw_threshold)
    baseline_hard_rate = ckg.rate(raw_hard)
    baseline_review_rate = ckg.rate(raw_conflict)
    hard_scores = score["gate_attack_score"][raw_hard]
    if len(hard_scores) == 0 or baseline_hard_rate <= 0:
        threshold = -math.inf
        expected_quantile = 0.0
        quantile_threshold = -math.inf
    else:
        expected_quantile = min(1.0, max(0.0, budget.max_support_hard_drop / max(1e-12, baseline_hard_rate)))
        quantile_threshold = float(np.quantile(hard_scores, expected_quantile))
        threshold = min(quantile_threshold, float(budget.max_gate_attack_threshold))
    extra = raw_hard & (score["gate_attack_score"] < threshold)
    hard = raw_hard & (~extra)
    return {
        "candidate": budget.name,
        "max_support_hard_drop": budget.max_support_hard_drop,
        "max_gate_attack_threshold": budget.max_gate_attack_threshold,
        "gate_attack_threshold": threshold,
        "support_quantile_gate_attack_threshold": quantile_threshold,
        "expected_support_raw_hard_quantile": expected_quantile,
        "support_rows": len(idx),
        "support_baseline_raw_alarm_rate": ckg.rate(raw_alarm),
        "support_baseline_review_rate": baseline_review_rate,
        "support_baseline_hard_rate": baseline_hard_rate,
        "support_policy_extra_review_rate": ckg.rate(extra),
        "support_policy_hard_rate": ckg.rate(hard),
        "support_observed_hard_drop": baseline_hard_rate - ckg.rate(hard),
        "threshold_role": "support_val select only",
    }


def score_part(
    name: str,
    raw_threshold: float,
    gate_threshold: float | None,
    role: str,
    phase: str,
    role_kind: str,
    frame_part: pd.DataFrame,
    score: dict[str, np.ndarray],
) -> tuple[dict[str, Any], pd.DataFrame]:
    raw_alarm, raw_conflict, raw_hard = baseline_decision(score, raw_threshold)
    if gate_threshold is None:
        extra_review = np.zeros(len(raw_alarm), dtype=bool)
    else:
        extra_review = raw_hard & (score["gate_attack_score"] < gate_threshold)
    conflict = raw_conflict | extra_review
    hard = raw_alarm & (~conflict)

    part = frame_part.copy().reset_index(drop=True)
    for key, val in score.items():
        part[key] = val
    part["raw_alarm"] = raw_alarm
    part["raw_conflict_review"] = raw_conflict
    part["gate_extra_review"] = extra_review
    part["conflict_review"] = conflict
    part["hard_alarm"] = hard
    return (
        {
            "feature_set": name,
            "role": role,
            "phase": phase,
            "role_kind": role_kind,
            "rows": len(part),
            "attack_threshold": raw_threshold,
            "gate_attack_threshold": "" if gate_threshold is None else gate_threshold,
            "raw_alarm_rate": ckg.rate(raw_alarm),
            "raw_conflict_review_rate": ckg.rate(raw_conflict),
            "gate_extra_review_rate": ckg.rate(extra_review),
            "conflict_review_rate": ckg.rate(conflict),
            "hard_alarm_rate": ckg.rate(hard),
            "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
            "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(part) else float("nan"),
            "gate_attack_score_mean": float(np.mean(score["gate_attack_score"])) if len(part) else float("nan"),
        },
        part,
    )


def eval_candidate(
    name: str,
    fitted: dict[str, Any],
    raw_threshold: float,
    gate_threshold: float | None,
    builder: ckq.FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    role_rows: list[dict[str, Any]] = []
    group_metrics: list[dict[str, Any]] = []
    spec = cko.FeatureSpec(name, "attack_preserving_flow_veto", "raw115 primary attack detector plus constrained flow evidence review")
    for role, phase, kind in cko.ROLE_EVAL:
        idx = cko.role_indices(frame_by_role, role, phase, eval_cap)
        score = role_evidence(fitted, builder, role, idx)
        row, part = score_part(name, raw_threshold, gate_threshold, role, phase, kind, frame_by_role[role].iloc[idx], score)
        role_rows.append(row)
        group_metrics.extend(cko.group_rows(spec, role, part))
    return role_rows, group_metrics


def build_readout(matrix: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], audit: list[dict[str, Any]], seconds: float, smoke: bool) -> list[str]:
    requested = sum(int(row.get("requested_rows", 0)) for row in audit)
    computed = sum(int(row.get("computed_new_rows", 0)) for row in audit)
    oob = sum(int(row.get("out_of_bounds_rows", 0)) for row in audit)
    lines = [
        "# issue27ckr attack-preserving flow veto v1",
        "",
        "## Scope",
        "",
        "Raw115 remains the primary attack detector. Flow-temporal evidence can only move a raw hard alarm into review.",
        "Gate thresholds are selected from support_val only; query/future/sealed rows are report-only.",
        f"Mode: `{'smoke' if smoke else 'full'}`.",
        "",
        "## Main matrix",
        "",
        "| candidate | future hard | same-file hard | sealed attack hard/review | sealed OOD hard/review | OOD-stress hard/review |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['feature_set']} | {cko.fmt(row['future_hard'])} | {cko.fmt(row['same_file_hard'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold audit",
            "",
            "| candidate | support hard baseline | support hard policy | observed drop | gate threshold |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in threshold_rows:
        if row["candidate"] == "R0_raw115_control":
            continue
        lines.append(
            f"| {row['candidate']} | {cko.fmt(row['support_baseline_hard_rate'])} | "
            f"{cko.fmt(row['support_policy_hard_rate'])} | {cko.fmt(row['support_observed_hard_drop'])} | "
            f"{cko.fmt(row['gate_attack_threshold'])} |"
        )
    lines.extend(
        [
            "",
            "## Flow-temporal extraction audit",
            "",
            f"- files read: `{len(audit)}`",
            f"- requested/computed rows: `{requested}/{computed}`",
            f"- out-of-bounds rows: `{oob}`",
            "",
            "## Guardrail",
            "",
            "- The gate never creates a new attack alarm; it only reviews a raw hard alarm.",
            "- Threshold selection uses support_val attack rows only.",
            "- Report/query/final rows remain report-only.",
            "",
            f"Runtime seconds: `{cko.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    role_cap_requested = args.role_cap is not None
    smoke = bool(args.smoke or args.micro_smoke or role_cap_requested)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke)
    role_cap_rows: list[dict[str, Any]] = []
    if args.micro_smoke or role_cap_requested:
        per_phase_cap = args.micro_role_cap if args.micro_smoke else int(args.role_cap)
        per_source_cap = args.micro_source_cap if args.micro_smoke else int(args.source_cap)
        cap_rule = (
            "earliest recorded_index rows per phase/source for local-context micro-smoke only"
            if args.micro_smoke
            else "earliest recorded_index rows per phase/source for complete-past capped smoke"
        )
        x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            per_phase_cap,
            per_source_cap,
            cap_rule=cap_rule,
        )

    train_cap = ckq.MICRO_TRAIN_CAP if args.micro_smoke else (cko.SMOKE_TRAIN_CAP if smoke else cko.TRAIN_CAP)
    eval_cap = ckq.MICRO_EVAL_CAP if args.micro_smoke else (cko.SMOKE_EVAL_CAP if smoke else cko.FULL_CAP)
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=smoke, local_context_only=args.micro_smoke)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    fitted, train_rows, oof_rows = fit_evidence_gate(builder, frame_by_role, train_cap)
    raw_threshold = raw_attack_threshold(fitted, builder, frame_by_role, eval_cap)

    threshold_rows: list[dict[str, Any]] = [
        {
            "candidate": "R0_raw115_control",
            "attack_threshold": raw_threshold,
            "threshold_role": "id_calib/ood_val/ood_stress select",
        }
    ]
    for budget in VETO_BUDGETS:
        threshold_rows.append(gate_threshold_for_budget(fitted, builder, frame_by_role, raw_threshold, eval_cap, budget))

    role_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    rows, groups = eval_candidate("R0_raw115_control", fitted, raw_threshold, None, builder, frame_by_role, eval_cap)
    role_rows.extend(rows)
    group_rows.extend(groups)
    for row in threshold_rows:
        if row["candidate"] == "R0_raw115_control":
            continue
        rows, groups = eval_candidate(
            str(row["candidate"]),
            fitted,
            raw_threshold,
            float(row["gate_attack_threshold"]),
            builder,
            frame_by_role,
            eval_cap,
        )
        role_rows.extend(rows)
        group_rows.extend(groups)

    matrix = cko.aggregate(role_rows, group_rows)
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    cko.write_csv(OUT / "role_metrics.csv", role_rows)
    cko.write_csv(OUT / "group_metrics_by_source_device.csv", group_rows)
    cko.write_csv(OUT / "train_audit.csv", train_rows)
    cko.write_csv(OUT / "oof_gate_audit.csv", oof_rows)
    cko.write_csv(OUT / "threshold_audit.csv", threshold_rows)
    cko.write_csv(OUT / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(OUT / "alignment_audit.csv", alignment_rows)
    cko.write_csv(OUT / "role_cap_audit.csv", role_cap_rows)
    cko.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "attack-preserving constrained flow-temporal veto",
            "smoke": smoke,
            "micro_smoke": args.micro_smoke,
            "train_cap": train_cap,
            "eval_cap": eval_cap,
            "veto_budgets": [asdict(v) for v in VETO_BUDGETS],
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "raw_attack_threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
                "gate_threshold_role": "support_val select only",
                "report_only_roles_used_for_training_or_thresholding": False,
                "processed_label_used_as_feature": False,
                "flow_temporal_state": "current/past-only within processed source file",
                "gate_can_create_attack_alarm": False,
            },
            "input_audit": input_audit,
            "role_cap_audit": role_cap_rows,
            "alignment_audit": {"rows": len(alignment_rows), "purpose": "report-only raw115-to-flow-temporal row pairing evidence"},
            "outputs": [
                "candidate_summary_matrix.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "train_audit.csv",
                "oof_gate_audit.csv",
                "threshold_audit.csv",
                "flow_temporal_extraction_audit.csv",
                "alignment_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    cko.write_md(OUT / "codex_readout.md", build_readout(matrix, threshold_rows, cache.audit_rows, seconds, smoke))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds, "smoke": smoke, "micro_smoke": args.micro_smoke}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--micro-smoke", action="store_true")
    parser.add_argument("--micro-role-cap", type=int, default=512)
    parser.add_argument("--micro-source-cap", type=int, default=48)
    parser.add_argument("--role-cap", type=int, default=None)
    parser.add_argument("--source-cap", type=int, default=24)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
