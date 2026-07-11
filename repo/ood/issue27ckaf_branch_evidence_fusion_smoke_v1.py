"""issue27ckaf: branch evidence fusion smoke v1.

Goal:

    Verify the next contract before any expensive HPC run:

        A1 = CKAE low-shortcut weak attack evidence only
        A2 = A1 + selected conflict/context branch
        A3 = A2 + selected raw115 context-only

This is deliberately not a "throw every feature into a neural net" experiment.
The attack branch cannot see raw115.  Context/raw features are conflict-only.
Demote features are not used.  Query/future/sealed rows are report-only.

This script reuses the CKZ neural two-branch training/evaluation skeleton, but
replaces the frontend with a CKAE-selected branch frontend.
"""

from __future__ import annotations

import argparse
import json
import math
import re
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

import issue27ckac_frontend_feature_utility_audit_v1 as ckac  # noqa: E402
import issue27ckae_goal_aligned_feature_search_v1 as ckae  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402
import issue27ckz_neural_interaction_causal_router_v1 as ckz  # noqa: E402


ISSUE = "issue27ckaf_branch_evidence_fusion_smoke_v1_2026-07-06"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = ckz.DEFAULT_HELD_VALUES
SEED = ckz.SEED


@dataclass(frozen=True)
class FusionSpec:
    name: str
    use_context: bool
    use_raw_context: bool
    description: str


FUSION_SPECS = [
    FusionSpec(
        name="A1_attack_only",
        use_context=False,
        use_raw_context=False,
        description="Attack branch uses CKAE low-shortcut weak attack evidence; conflict branch is a zero baseline.",
    ),
    FusionSpec(
        name="A2_attack_plus_context",
        use_context=True,
        use_raw_context=False,
        description="A1 plus selected CKAE/CKY conflict-context evidence.",
    ),
    FusionSpec(
        name="A3_attack_context_rawctx",
        use_context=True,
        use_raw_context=True,
        description="A2 plus selected raw115 context-only dimensions; raw115 never enters the attack branch.",
    ),
]


def slug(text: Any, limit: int = 96) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:limit] or "empty"


def finite(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def fmt(value: Any, digits: int = 4) -> str:
    val = finite(value)
    if math.isnan(val):
        return "nan"
    return f"{val:.{digits}f}"


def choose_attack_features(
    generated_rows: list[dict[str, Any]],
    max_features: int,
    shortcut_max: float,
    selection_mode: str = "top",
) -> list[str]:
    df = pd.DataFrame(generated_rows)
    if df.empty:
        return []
    allowed_groups = {
        "ckae_attack_seed",
        "ckae_attack_soft_interaction",
        "ckae_attack_context_calibrated",
        "ckae_attack_consensus",
    }
    mask = (
        df["feature_group"].isin(allowed_groups)
        & df["recommendation"].isin(["candidate_attack_evidence", "weak_attack_evidence_needs_group_check"])
        & (pd.to_numeric(df["max_shortcut_strength_fit"], errors="coerce") <= float(shortcut_max))
    )
    part = df[mask].copy()
    if part.empty:
        # Last-resort smoke fallback: still do not take demote/context.  Pick
        # the best low-shortcut attack-like rows so the run remains diagnostic.
        part = df[
            df["feature_group"].isin(allowed_groups)
            & (pd.to_numeric(df["max_shortcut_strength_fit"], errors="coerce") <= float(shortcut_max))
        ].copy()
    part = part.sort_values(
        ["legal_selection_score", "strength_attack_vs_oodish_select", "strength_attack_vs_oodish_fit"],
        ascending=False,
    )
    if str(selection_mode) == "top":
        return [str(v) for v in part.head(int(max_features))["feature_name"].tolist()]

    # Do not let one mechanism family monopolize the branch.  The first CKAF
    # smoke selected ten near-duplicates around fanout_accel_failure, which
    # made same_file attacks invisible.  Prefer one identity seed per mechanism,
    # then fill with bounded interactions.
    identity = part[part["feature_name"].astype(str).str.startswith("seed_attack__")].copy()
    selected: list[str] = []
    primitive_use: dict[str, int] = {}

    def primitives(name: str) -> list[str]:
        known = [
            "fanout_accel_failure",
            "flood_failed",
            "fast_scan_failed",
            "sustained_scan_failed",
            "dst_pressure_failed",
            "dst_pressure_accel_failure",
            "pair_spread_failed",
            "mechanism_consensus",
            "sustained_flood_imbalance",
            "many_to_one_pressure",
            "burst_fanout",
        ]
        hits = [item for item in known if item in name]
        if hits:
            return hits
        if name.startswith("seed_attack__"):
            return [name.replace("seed_attack__", "", 1)]
        return [name]

    def can_add(name: str, cap: int) -> bool:
        if name in selected:
            return False
        return all(primitive_use.get(token, 0) < cap for token in primitives(name))

    def add(name: str) -> None:
        selected.append(name)
        for token in primitives(name):
            primitive_use[token] = primitive_use.get(token, 0) + 1

    for _idx, row in identity.iterrows():
        name = str(row["feature_name"])
        if can_add(name, cap=1):
            add(name)
        if len(selected) >= int(max_features):
            break
    if len(selected) < int(max_features):
        for _idx, row in part.iterrows():
            name = str(row["feature_name"])
            if can_add(name, cap=2):
                add(name)
            if len(selected) >= int(max_features):
                break
    return selected[: int(max_features)]


def choose_generated_context_features(generated_rows: list[dict[str, Any]], max_features: int) -> list[str]:
    df = pd.DataFrame(generated_rows)
    if df.empty:
        return []
    mask = (
        (df["feature_group"] == "ckae_conflict_context")
        & (df["recommendation"] == "candidate_conflict_context")
    )
    part = df[mask].copy()
    part = part.sort_values(
        ["max_shortcut_strength_fit", "strength_id_vs_oodish_fit", "legal_selection_score"],
        ascending=False,
    ).head(int(max_features))
    return [str(v) for v in part["feature_name"].tolist()]


def choose_raw_context_features(raw_rows: list[dict[str, Any]], max_features: int) -> list[str]:
    df = pd.DataFrame(raw_rows)
    if df.empty:
        return []
    part = df[df["recommendation"] == "candidate_conflict_context"].copy()
    part = part.sort_values(
        ["max_shortcut_strength_fit", "strength_id_vs_oodish_fit", "legal_selection_score"],
        ascending=False,
    ).head(int(max_features))
    return [str(v) for v in part["feature_name"].tolist()]


class SelectedBranchFrontend:
    """Frontend with explicit attack/context/raw branch separation."""

    def __init__(
        self,
        name: str,
        generator: ckae.GoalAlignedFeatureSearch,
        x_by_role: dict[str, np.ndarray],
        attack_names: list[str],
        context_names: list[str],
        raw_context_names: list[str],
        spec: FusionSpec,
    ) -> None:
        self.name = name
        self.generator = generator
        self.x_by_role = x_by_role
        self.attack_names = list(dict.fromkeys(attack_names))
        self.context_names = list(dict.fromkeys(context_names)) if spec.use_context else []
        self.raw_context_names = list(dict.fromkeys(raw_context_names)) if spec.use_raw_context else []
        self.spec = spec
        self.gen_index = {name: i for i, name in enumerate(generator.feature_names)}
        self.raw_names = ckac.raw_feature_names()
        self.raw_index = {name: i for i, name in enumerate(self.raw_names)}
        self.attack_cols = [self.gen_index[name] for name in self.attack_names if name in self.gen_index]
        self.context_cols = [self.gen_index[name] for name in self.context_names if name in self.gen_index]
        self.raw_cols = [self.raw_index[name] for name in self.raw_context_names if name in self.raw_index]

    def matrix(self, role: str, idx: np.ndarray, block: str = "full") -> np.ndarray:
        idx = np.asarray(idx, dtype=np.int64)
        if block == "attack_mechanism":
            generated = self.generator.matrix(role, idx)
            if self.attack_cols:
                return generated[:, self.attack_cols].astype(np.float32)
            return np.zeros((len(idx), 1), dtype=np.float32)
        if block == "conflict_context":
            parts: list[np.ndarray] = []
            if self.context_cols:
                generated = self.generator.matrix(role, idx)
                parts.append(generated[:, self.context_cols].astype(np.float32))
            if self.raw_cols:
                raw = np.asarray(self.x_by_role[role][idx], dtype=np.float32)
                parts.append(raw[:, self.raw_cols].astype(np.float32))
            if parts:
                return np.hstack(parts).astype(np.float32)
            return np.zeros((len(idx), 1), dtype=np.float32)
        if block == "full":
            return np.hstack([self.matrix(role, idx, "attack_mechanism"), self.matrix(role, idx, "conflict_context")]).astype(np.float32)
        raise ValueError(f"unknown block: {block}")

    def registry(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for i, name in enumerate(self.attack_names):
            if name in self.gen_index:
                rows.append(
                    {
                        "frontend": self.name,
                        "branch": "attack_mechanism",
                        "feature_index": i,
                        "feature_name": name,
                        "source_space": "ckae_generated",
                        "hard_attack_allowed": True,
                        "contract": "may support attack score; selected low-shortcut CKAE evidence only",
                    }
                )
        offset = 0
        for i, name in enumerate(self.context_names):
            if name in self.gen_index:
                rows.append(
                    {
                        "frontend": self.name,
                        "branch": "conflict_context",
                        "feature_index": offset + i,
                        "feature_name": name,
                        "source_space": "ckae_generated_context",
                        "hard_attack_allowed": False,
                        "contract": "context/conflict only; cannot directly support hard attack",
                    }
                )
        offset += len(self.context_names)
        for i, name in enumerate(self.raw_context_names):
            if name in self.raw_index:
                rows.append(
                    {
                        "frontend": self.name,
                        "branch": "conflict_context",
                        "feature_index": offset + i,
                        "feature_name": name,
                        "source_space": "raw115_context_only",
                        "hard_attack_allowed": False,
                        "contract": "raw115 demoted to context-only; cannot enter attack branch",
                    }
                )
        if not self.context_names and not self.raw_context_names:
            rows.append(
                {
                    "frontend": self.name,
                    "branch": "conflict_context",
                    "feature_index": 0,
                    "feature_name": "__zero_conflict_baseline__",
                    "source_space": "zero",
                    "hard_attack_allowed": False,
                    "contract": "A1 conflict branch disabled baseline",
                }
            )
        return rows


def build_feature_selection(
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    builder: ckq.FlowTemporalBuilder,
    args: argparse.Namespace,
) -> tuple[ckae.GoalAlignedFeatureSearch, dict[str, Any]]:
    cky_frontend = cky.InteractionCausalFrontend(builder)
    primitive_spaces = ckae.build_cky_spaces(cky_frontend)
    primitive_rows: list[dict[str, Any]] = []
    primitive_audit: list[dict[str, Any]] = []
    for space in primitive_spaces:
        rows, audit = ckac.score_feature_space(space, frame_by_role, int(args.seed_eval_cap), int(args.min_group_rows))
        primitive_rows.extend(rows)
        primitive_audit.extend(audit)
    primitive_rows = ckae.add_seed_scores(primitive_rows)
    attack_seeds, context_seeds, seed_rows = ckae.choose_seed_names(
        primitive_rows,
        int(args.max_attack_seeds),
        int(args.max_context_seeds),
    )
    generator = ckae.GoalAlignedFeatureSearch(
        cky_frontend,
        attack_seeds=attack_seeds,
        context_seeds=context_seeds,
        pair_seed_limit=int(args.pair_seed_limit),
        context_pair_limit=int(args.context_pair_limit),
    )
    generated_space = ckac.FeatureSpace(
        name="ckae_generated",
        feature_names=generator.feature_names,
        feature_groups=generator.feature_groups,
        matrix_fn=generator.matrix,
        description="CKAE generated evidence features.",
    )
    generated_rows, generated_audit = ckac.score_feature_space(
        generated_space,
        frame_by_role,
        int(args.eval_cap),
        int(args.min_group_rows),
    )
    raw_names = ckac.raw_feature_names()
    raw_space = ckac.FeatureSpace(
        name="raw115",
        feature_names=raw_names,
        feature_groups=[ckac.raw_family(name) for name in raw_names],
        matrix_fn=lambda role, idx: np.asarray(x_by_role[role][idx], dtype=np.float32),
        description="raw115 dimensions audited for context-only use.",
    )
    raw_rows, raw_audit = ckac.score_feature_space(raw_space, frame_by_role, int(args.eval_cap), int(args.min_group_rows))

    attack_names = choose_attack_features(
        generated_rows,
        int(args.max_attack_features),
        float(args.attack_shortcut_max),
        str(args.attack_selection_mode),
    )
    context_names = choose_generated_context_features(generated_rows, int(args.max_context_features))
    raw_context_names = choose_raw_context_features(raw_rows, int(args.max_raw_context_features))
    selection = {
        "primitive_rows": primitive_rows,
        "primitive_audit": primitive_audit,
        "selected_seed_rows": seed_rows,
        "generated_rows": generated_rows,
        "generated_audit": generated_audit,
        "raw_rows": raw_rows,
        "raw_audit": raw_audit,
        "attack_names": attack_names,
        "context_names": context_names,
        "raw_context_names": raw_context_names,
    }
    return generator, selection


def neural_candidate_for(spec: FusionSpec, args: argparse.Namespace) -> ckz.NeuralRouterCandidate:
    return ckz.NeuralRouterCandidate(
        name=spec.name,
        hidden_dim=int(args.hidden_dim),
        epochs=int(args.epochs),
        lr=float(args.lr),
        weight_decay=float(args.weight_decay),
        dropout=float(args.dropout),
        adv_lambda=float(args.adv_lambda),
        rex_lambda=float(args.rex_lambda),
        worst_group_lambda=float(args.worst_group_lambda),
        conflict_include_id=True,
        description=spec.description,
    )


def eval_frontend(
    spec: FusionSpec,
    frontend: SelectedBranchFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    args: argparse.Namespace,
    held_values: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate = neural_candidate_for(spec, args)
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    leave_group_rows: list[dict[str, Any]] = []

    rows, thrs, trains, hist = ckz.eval_candidate(
        candidate,
        frontend,
        frame_by_role,
        int(args.train_cap),
        int(args.eval_cap),
        float(args.benign_q),
        split="main",
    )
    role_rows.extend(rows)
    threshold_rows.extend(thrs)
    train_rows.extend(trains)
    history_rows.extend(hist)

    for held_value in held_values:
        counts = {
            "ood_val": ckt.rows_for(frame_by_role, "ood_val", "select", "device_family", held_value, int(args.eval_cap)),
            "ood_stress": ckt.rows_for(frame_by_role, "ood_stress", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_ood": ckt.rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", held_value, int(args.eval_cap)),
            "future_query": ckt.rows_for(frame_by_role, "future_query", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_attack": ckt.rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", held_value, int(args.eval_cap)),
        }
        leave_group_rows.append({"candidate": spec.name, "held_field": "device_family", "held_value": held_value, "total_eval_rows": sum(counts.values()), **counts})
        include = ("device_family", held_value)
        exclude = ("device_family", held_value)
        rows, thrs, trains, hist = ckz.eval_candidate(
            candidate,
            frontend,
            frame_by_role,
            int(args.train_cap),
            int(args.eval_cap),
            float(args.benign_q),
            split="leave_device_family",
            include=include,
            exclude=exclude,
        )
        role_rows.extend(rows)
        threshold_rows.extend(thrs)
        train_rows.extend({"held_value": held_value, **row} for row in trains)
        history_rows.extend({"held_value": held_value, **row} for row in hist)
    return role_rows, threshold_rows, train_rows, history_rows, leave_group_rows


def build_branch_manifest(frontends: list[SelectedBranchFrontend]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frontend in frontends:
        rows.append(
            {
                "candidate": frontend.name,
                "attack_features": len(frontend.attack_cols),
                "generated_context_features": len(frontend.context_cols),
                "raw_context_features": len(frontend.raw_cols),
                "attack_branch_uses_raw115": False,
                "raw115_direct_hard_attack_allowed": False,
                "description": frontend.spec.description,
            }
        )
    return rows


def build_readout(
    branch_rows: list[dict[str, Any]],
    main_rows: list[dict[str, Any]],
    leave_rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
    seconds: float,
) -> list[str]:
    lines = [
        "# issue27ckaf branch evidence fusion smoke v1",
        "",
        "## Scope",
        "",
        "Local smoke for branch-separated evidence fusion.",
        "A1/A2/A3 test attack evidence, conflict evidence, and raw115 context incrementally.",
        "",
        "## Branch contract",
        "",
        "| candidate | attack features | generated context | raw context | raw enters attack? |",
        "|---|---:|---:|---:|---|",
    ]
    for row in branch_rows:
        lines.append(
            f"| {row['candidate']} | {row['attack_features']} | {row['generated_context_features']} | "
            f"{row['raw_context_features']} | {row['attack_branch_uses_raw115']} |"
        )
    lines.extend(
        [
            "",
            "## Main roles",
            "",
            "| candidate | policy | future h/r/s | sealed attack h/r/s | sealed OOD h/r/s | OOD-stress h/r/s |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in main_rows:
        lines.append(
            f"| {row['candidate']} | {row['policy']} | "
            f"{fmt(row['future_hard'])}/{fmt(row['future_review'])}/{fmt(row['future_suppress'])} | "
            f"{fmt(row['sealed_attack_hard'])}/{fmt(row['sealed_attack_review'])}/{fmt(row['sealed_attack_suppress'])} | "
            f"{fmt(row['sealed_ood_hard'])}/{fmt(row['sealed_ood_review'])}/{fmt(row['sealed_ood_suppress'])} | "
            f"{fmt(row['ood_stress_hard'])}/{fmt(row['ood_stress_review'])}/{fmt(row['ood_stress_suppress'])} |"
        )
    lines.extend(
        [
            "",
            "## Leave-device-family stress",
            "",
            "| candidate | policy | held family | role | rows | hard | review | suppress | attack/conflict/margin mean |",
            "|---|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in leave_rows:
        if int(row["rows"]) == 0:
            continue
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{fmt(row['hard_alarm_rate'])} | {fmt(row['review_rate'])} | {fmt(row['suppress_rate'])} | "
            f"{fmt(row['attack_score_mean'])}/{fmt(row['conflict_score_mean'])}/{fmt(row['margin_score_mean'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold audit",
            "",
            "| candidate | split | held | policy | attack thr | margin review thr | support hard/review/suppress |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in threshold_rows:
        lines.append(
            f"| {row['candidate']} | {row['split']} | {row.get('held_value','')} | {row['policy']} | "
            f"{fmt(row['attack_threshold'])} | {fmt(row['margin_review_threshold'])} | "
            f"{fmt(row['support_hard_rate'])}/{fmt(row['support_review_rate'])}/{fmt(row['support_suppress_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit uses only support_train/id_calib/ood_val/ood_stress fit phases.",
            "- Thresholds use only id_calib/ood_val/ood_stress/support_val select phases.",
            "- Query/future/sealed rows are report-only.",
            "- Leave-family stress excludes held device_family from fit and thresholds.",
            "- CKAE feature scoring is development-side feature selection, not final benchmark proof.",
            "- h/r/s = hard/review/suppress.",
            f"- Runtime seconds: {fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    ckz.set_seeds()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(True)
    ckt.add_family_columns(frame_by_role)
    role_cap_rows: list[dict[str, Any]] = []
    if int(args.source_cap) > 0:
        x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            int(args.role_cap),
            int(args.source_cap),
            cap_rule="ckaf branch-fusion capped diagnostic",
        )

    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    generator, selection = build_feature_selection(x_by_role, frame_by_role, builder, args)
    frontends = [
        SelectedBranchFrontend(
            spec.name,
            generator,
            x_by_role,
            attack_names=selection["attack_names"],
            context_names=selection["context_names"],
            raw_context_names=selection["raw_context_names"],
            spec=spec,
        )
        for spec in FUSION_SPECS
    ]

    held_values = [item.strip() for item in str(args.held_values).split(",") if item.strip()]
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    leave_group_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    for frontend in frontends:
        rows, thrs, trains, hist, leaves = eval_frontend(frontend.spec, frontend, frame_by_role, args, held_values)
        role_rows.extend(rows)
        threshold_rows.extend(thrs)
        train_rows.extend(trains)
        history_rows.extend(hist)
        leave_group_rows.extend(leaves)
        registry_rows.extend(frontend.registry())

    main_rows = ckz.main_summary(role_rows)
    leave_rows = ckz.leave_summary(role_rows)
    branch_rows = build_branch_manifest(frontends)
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(out / "branch_manifest.csv", branch_rows)
    cko.write_csv(out / "branch_feature_registry.csv", registry_rows)
    cko.write_csv(out / "main_summary_matrix.csv", main_rows)
    cko.write_csv(out / "leave_device_family_summary_matrix.csv", leave_rows)
    cko.write_csv(out / "role_metrics.csv", role_rows)
    cko.write_csv(out / "threshold_policy_audit.csv", threshold_rows)
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "train_history_and_env_audit.csv", history_rows)
    cko.write_csv(out / "selected_leave_groups.csv", leave_group_rows)
    cko.write_csv(out / "selected_seed_manifest.csv", selection["selected_seed_rows"])
    cko.write_csv(out / "ckae_generated_feature_scores.csv", selection["generated_rows"])
    cko.write_csv(out / "raw115_context_feature_scores.csv", selection["raw_rows"])
    cko.write_csv(out / "ckae_generated_feature_registry.csv", generator.registry_rows())
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "alignment_audit.csv", alignment_rows)
    cko.write_md(out / "codex_readout.md", build_readout(branch_rows, main_rows, leave_rows, threshold_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "role_cap": int(args.role_cap),
            "source_cap": int(args.source_cap),
            "train_cap": int(args.train_cap),
            "eval_cap": int(args.eval_cap),
            "seed_eval_cap": int(args.seed_eval_cap),
            "benign_q": float(args.benign_q),
            "fusion_specs": [asdict(spec) for spec in FUSION_SPECS],
            "neural_template": {
                "hidden_dim": int(args.hidden_dim),
                "epochs": int(args.epochs),
                "lr": float(args.lr),
                "weight_decay": float(args.weight_decay),
                "dropout": float(args.dropout),
                "adv_lambda": float(args.adv_lambda),
                "rex_lambda": float(args.rex_lambda),
                "worst_group_lambda": float(args.worst_group_lambda),
                "conflict_include_id": True,
            },
            "selected_feature_counts": branch_rows,
            "attack_selection_mode": str(args.attack_selection_mode),
            "selected_attack_features": selection["attack_names"],
            "selected_context_features": selection["context_names"],
            "selected_raw_context_features": selection["raw_context_names"],
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "query_future_sealed_used_for_training_or_thresholding": False,
                "leave_family_exclusion": "held device_family excluded from fit and thresholds",
                "raw115_direct_attack_branch": False,
            },
            "input_audit": input_audit,
            "torch_version": getattr(ckz.torch, "__version__", "missing") if ckz.torch is not None else "missing",
            "alignment_audit_rows": len(alignment_rows),
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=512)
    parser.add_argument("--source-cap", type=int, default=0)
    parser.add_argument("--seed-eval-cap", type=int, default=512)
    parser.add_argument("--eval-cap", type=int, default=512)
    parser.add_argument("--train-cap", type=int, default=512)
    parser.add_argument("--min-group-rows", type=int, default=8)
    parser.add_argument("--max-attack-seeds", type=int, default=10)
    parser.add_argument("--max-context-seeds", type=int, default=8)
    parser.add_argument("--pair-seed-limit", type=int, default=8)
    parser.add_argument("--context-pair-limit", type=int, default=6)
    parser.add_argument("--max-attack-features", type=int, default=12)
    parser.add_argument("--attack-selection-mode", choices=["top", "diverse"], default="top")
    parser.add_argument("--max-context-features", type=int, default=8)
    parser.add_argument("--max-raw-context-features", type=int, default=16)
    parser.add_argument("--attack-shortcut-max", type=float, default=0.45)
    parser.add_argument("--hidden-dim", type=int, default=48)
    parser.add_argument("--epochs", type=int, default=55)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument("--adv-lambda", type=float, default=0.0)
    parser.add_argument("--rex-lambda", type=float, default=0.0)
    parser.add_argument("--worst-group-lambda", type=float, default=0.0)
    parser.add_argument("--benign-q", type=float, default=ckz.BENIGN_SAFE_Q)
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
