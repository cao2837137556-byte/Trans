#!/usr/bin/env python3
"""Recompute the reviewer-facing CKBQ seed-27 result diagnosis.

Report labels are used only for post-hoc route diagnosis.  This program never
changes a model, threshold, gate, prediction, or scientific decision.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


PRIMARY = "M3-StaticTemporalConsensus"
BASELINE = "M0-C1"
ATTACK_ROLES = [
    "future_query",
    "same_file_query",
    "sealed_final_attack",
    "support_val",
]
HELD_ROLES = {
    "iotsim-ip-camera-street": "sealed_final_ood",
    "iotsim-predictive-maintenance": "aux_report",
    "iotsim-stream-consumer": "ood_stress",
    "iotsim-hydraulic-system": "ood_val",
}


def bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    mapped = series.astype(str).str.strip().str.lower().map(
        {"true": True, "1": True, "false": False, "0": False}
    )
    if mapped.isna().any():
        bad = sorted(series.loc[mapped.isna()].astype(str).unique().tolist())
        raise RuntimeError(f"invalid booleans: {bad}")
    return mapped.astype(bool)


def selected_gate(selection: pd.DataFrame) -> pd.Series:
    selected = selection.loc[
        selection["candidate"].eq(PRIMARY) & bool_series(selection["selected"])
    ]
    global_gate = selected.loc[
        selected["held_value"].eq("GLOBAL_ATTACK_PRESERVATION")
    ]
    if len(global_gate) != 1:
        raise RuntimeError("missing unique registered global primary gate")
    return global_gate.iloc[0]


def family_diagnosis(
    predictions: pd.DataFrame,
    attack_summary: pd.DataFrame,
) -> pd.DataFrame:
    attack = predictions.loc[
        predictions["held_value"].eq("GLOBAL_ATTACK_PRESERVATION")
        & predictions["label_metric_only"].eq(1)
        & predictions["role"].isin(ATTACK_ROLES)
    ].copy()
    attack["c1_hard"] = bool_series(attack[f"hard__{BASELINE}"])
    attack["primary_hard"] = bool_series(attack[f"hard__{PRIMARY}"])
    attack["suppressed_c1_attack"] = attack["c1_hard"] & ~attack["primary_hard"]
    grouped = (
        attack.groupby("attack_family", sort=True)
        .agg(
            rows=("uid", "size"),
            c1_hard=("c1_hard", "sum"),
            primary_hard=("primary_hard", "sum"),
            suppressed_c1_attack=("suppressed_c1_attack", "sum"),
        )
        .reset_index()
    )
    formal = attack_summary.loc[
        attack_summary["candidate"].eq(PRIMARY)
        & attack_summary["metric"].eq("attack_family_recall")
        & attack_summary["attack_family"].notna(),
        [
            "attack_family",
            "hard_recall",
            "c1_hard_recall",
            "delta_vs_c1_pp",
            "delta_ci_low_pp",
            "delta_ci_high_pp",
            "ci_clusters",
        ],
    ].drop_duplicates("attack_family")
    return grouped.merge(formal, on="attack_family", how="left").sort_values(
        ["delta_vs_c1_pp", "attack_family"], na_position="last"
    )


def exact_oracle_feasibility(
    predictions: pd.DataFrame,
    strict: pd.DataFrame,
) -> dict[str, object]:
    """Test score-space capability with report labels, never select a gate.

    For every exact static score boundary, compute the least aggressive
    temporal boundary that achieves the preregistered weak held signal.  Then
    test the report attack constraints.  Monotonicity makes this an exact
    feasibility test for the registered OR gate family.
    """

    attack_all = predictions.loc[
        predictions["held_value"].eq("GLOBAL_ATTACK_PRESERVATION")
        & predictions["label_metric_only"].eq(1)
        & predictions["role"].isin(ATTACK_ROLES)
    ].copy()
    attack_all["c1_hard"] = bool_series(attack_all[f"hard__{BASELINE}"])
    attack_all["reliable"] = bool_series(attack_all["temporal_reliable"])
    attack = attack_all.loc[attack_all["c1_hard"] & attack_all["reliable"]].copy()

    total_attack_rows = int(len(attack_all))
    allowed_overall = int(math.floor(0.005 * total_attack_rows + 1e-12))
    family_totals = attack_all.groupby("attack_family").size().to_dict()
    major_allowance = {
        family: int(math.floor(0.02 * int(rows) + 1e-12))
        for family, rows in family_totals.items()
        if int(rows) >= 15
    }

    held_arrays: dict[str, np.ndarray] = {}
    held_meta: dict[str, tuple[int, int, int]] = {}
    required_suppression: dict[str, int] = {}
    for held, role in HELD_ROLES.items():
        part = predictions.loc[
            predictions["held_value"].eq(held)
            & predictions["role"].eq(role)
            & predictions["label_metric_only"].eq(0)
        ].copy()
        part["c1_hard"] = bool_series(part[f"hard__{BASELINE}"])
        part["reliable"] = bool_series(part["temporal_reliable"])
        c1_part = part.loc[part["c1_hard"] & part["reliable"]]
        held_arrays[held] = c1_part[
            ["static_attack_score", "temporal_attack_score"]
        ].to_numpy(dtype=np.float64)
        baseline = strict.loc[
            strict["candidate"].eq(BASELINE) & strict["held_value"].eq(held)
        ]
        if len(baseline) != 1:
            raise RuntimeError(f"missing strict baseline: {held}")
        total = int(baseline.iloc[0]["rows"])
        c1_hits = int(round(float(baseline.iloc[0]["c1_hard_rate"]) * total))
        maximum_rate = min(0.90, float(baseline.iloc[0]["c1_hard_rate"]) - 0.05)
        maximum_hits = int(math.floor(maximum_rate * total + 1e-12))
        held_meta[held] = (total, c1_hits, maximum_hits)
        required_suppression[held] = c1_hits - maximum_hits

    static_values = np.concatenate(
        [attack["static_attack_score"].to_numpy(dtype=np.float64)]
        + [array[:, 0] for array in held_arrays.values()]
    )
    static_grid = np.nextafter(np.unique(static_values), np.inf)
    attack_static = attack["static_attack_score"].to_numpy(dtype=np.float64)
    attack_temporal = attack["temporal_attack_score"].to_numpy(dtype=np.float64)
    attack_family = attack["attack_family"].to_numpy()

    feasible: list[dict[str, float | int]] = []
    closest: dict[str, float | int] | None = None
    for static_threshold in static_grid:
        temporal_threshold = -np.inf
        possible = True
        for held, array in held_arrays.items():
            eligible = array[array[:, 0] < static_threshold, 1]
            needed = required_suppression[held]
            if len(eligible) < needed:
                possible = False
                break
            if needed:
                boundary = np.partition(eligible, needed - 1)[needed - 1]
                temporal_threshold = max(
                    temporal_threshold,
                    float(np.nextafter(boundary, np.inf)),
                )
        if not possible:
            continue
        suppressed = (attack_static < static_threshold) & (
            attack_temporal < temporal_threshold
        )
        attack_suppressed = int(suppressed.sum())
        family_excess = 0
        for family, allowance in major_allowance.items():
            family_suppressed = int((suppressed & (attack_family == family)).sum())
            family_excess = max(family_excess, family_suppressed - allowance)
        violation = max(attack_suppressed - allowed_overall, family_excess)
        record: dict[str, float | int] = {
            "constraint_violation_rows": int(violation),
            "attack_suppressed": attack_suppressed,
            "family_excess_rows": int(family_excess),
            "static_threshold": float(static_threshold),
            "temporal_threshold": float(temporal_threshold),
        }
        if closest is None or (
            record["constraint_violation_rows"],
            record["attack_suppressed"],
            record["family_excess_rows"],
        ) < (
            closest["constraint_violation_rows"],
            closest["attack_suppressed"],
            closest["family_excess_rows"],
        ):
            closest = record
        if attack_suppressed <= allowed_overall and family_excess <= 0:
            for held, array in held_arrays.items():
                total, c1_hits, _ = held_meta[held]
                held_suppressed = int(
                    (
                        (array[:, 0] < static_threshold)
                        & (array[:, 1] < temporal_threshold)
                    ).sum()
                )
                record[f"hard_rate__{held}"] = (c1_hits - held_suppressed) / total
            feasible.append(record)

    if closest is None:
        raise RuntimeError("oracle feasibility scan did not evaluate any boundary")
    closest["attack_delta_pp"] = -100.0 * int(closest["attack_suppressed"]) / total_attack_rows
    return {
        "scope": "report-label post-hoc capability diagnosis only; forbidden for model or threshold selection",
        "registered_gate_family": "C1 candidate AND (static_attack OR temporal_attack); cold fails hard",
        "exact_static_boundaries_evaluated": int(len(static_grid)),
        "overall_attack_rows": total_attack_rows,
        "allowed_overall_suppression_rows": allowed_overall,
        "major_family_count": int(len(major_allowance)),
        "required_held_suppression_rows": required_suppression,
        "feasible_boundary_count": int(len(feasible)),
        "current_score_space_can_meet_all_registered_constraints": bool(feasible),
        "closest_boundary": closest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    decision = json.loads((root / "ckbq_single_seed_go_no_go.json").read_text())
    if decision.get("candidate") != PRIMARY or decision.get("decision") != "NO_GO":
        raise RuntimeError("unexpected formal decision")
    predictions = pd.read_csv(root / "ckbq_record_predictions.csv.gz")
    attack_summary = pd.read_csv(root / "attack_preservation_summary.csv")
    strict = pd.read_csv(root / "strict_level2_summary.csv")
    selection = pd.read_csv(root / "ckbq_candidate_selection.csv")
    gate = selected_gate(selection)
    families = family_diagnosis(predictions, attack_summary)
    oracle = exact_oracle_feasibility(predictions, strict)

    attack = predictions.loc[
        predictions["held_value"].eq("GLOBAL_ATTACK_PRESERVATION")
        & predictions["label_metric_only"].eq(1)
        & predictions["role"].isin(ATTACK_ROLES)
    ].copy()
    attack["c1_hard"] = bool_series(attack[f"hard__{BASELINE}"])
    attack["primary_hard"] = bool_series(attack[f"hard__{PRIMARY}"])
    attack["suppressed"] = attack["c1_hard"] & ~attack["primary_hard"]
    role_loss = (
        attack.groupby("role")
        .agg(rows=("uid", "size"), c1_hard=("c1_hard", "sum"), primary_hard=("primary_hard", "sum"), suppressed=("suppressed", "sum"))
        .reset_index()
    )
    role_loss["delta_pp"] = 100.0 * (
        role_loss["primary_hard"] - role_loss["c1_hard"]
    ) / role_loss["rows"]

    thresholds = {
        key: float(gate[key])
        for key in ("c1_shield_threshold", "static_threshold", "temporal_threshold")
    }
    attack_temporal_only = (
        attack["c1_hard"]
        & attack["c1_score"].lt(thresholds["c1_shield_threshold"])
        & attack["static_attack_score"].lt(thresholds["static_threshold"])
        & bool_series(attack["temporal_reliable"])
        & attack["temporal_attack_score"].ge(thresholds["temporal_threshold"])
    )
    hydraulic = predictions.loc[
        predictions["held_value"].eq("iotsim-hydraulic-system")
        & predictions["role"].eq("ood_val")
        & predictions["label_metric_only"].eq(0)
    ].copy()
    hydraulic_c1 = bool_series(hydraulic[f"hard__{BASELINE}"])
    hydraulic_temporal_only = (
        hydraulic_c1
        & hydraulic["c1_score"].lt(thresholds["c1_shield_threshold"])
        & hydraulic["static_attack_score"].lt(thresholds["static_threshold"])
        & bool_series(hydraulic["temporal_reliable"])
        & hydraulic["temporal_attack_score"].ge(thresholds["temporal_threshold"])
    )
    payload = {
        "status": "CKBQ_RESULT_DIAGNOSIS_COMPLETE",
        "formal_decision": decision,
        "selected_global_thresholds": thresholds,
        "attack_suppressed_total": int(attack["suppressed"].sum()),
        "attack_suppressed_future": int(
            attack.loc[attack["role"].eq("future_query"), "suppressed"].sum()
        ),
        "temporal_only_attack_rescues_at_registered_gate": int(attack_temporal_only.sum()),
        "temporal_only_hydraulic_false_alarms_at_registered_gate": int(hydraulic_temporal_only.sum()),
        "role_attack_loss": role_loss.to_dict(orient="records"),
        "oracle_score_space_feasibility": oracle,
        "interpretation": {
            "static_branch": "real multi-held normality signal but suppresses future attacks",
            "temporal_branch": "does not provide an efficient attack-rescue frontier under the registered gate",
            "route": "representation-plus-gate NO_GO; not repairable by selecting another current score threshold",
        },
    }
    families.to_csv(out / "ckbq_attack_family_diagnosis.csv", index=False, lineterminator="\n")
    (out / "ckbq_result_diagnosis.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": payload["status"],
        "families": int(len(families)),
        "oracle_feasible": oracle["current_score_space_can_meet_all_registered_constraints"],
        "closest_attack_delta_pp": oracle["closest_boundary"]["attack_delta_pp"],
    }, indent=2))


if __name__ == "__main__":
    main()
