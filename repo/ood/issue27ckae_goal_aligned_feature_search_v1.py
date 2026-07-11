"""issue27ckae: goal-aligned frontend feature search v1.

This is the next step after CKAC/CKAD:

* CKAC showed raw115 is mostly useful as conflict/context, not direct attack
  evidence.
* CKAD showed that hand-writing more conjunctive mechanism products is not
  enough; the new products became conflict/context or demote features.

So this file does not blindly add more dimensions.  It performs a small,
auditable feature search:

1. Build the CKY interaction/causal frontend with row alignment preserved by
   role/index.
2. Select attack-mechanism seed features using fit-only legal data.
3. Select conflict/context seed features using fit-only legal data.
4. Generate a bounded set of soft interaction, consensus, and attack-vs-context
   disentangling candidates.
5. Score the generated candidates with CKAC's legal fit/select audit.

The generated candidates are still frontend candidates, not final detector
results.  Query/future/sealed/held-family rows are report-only diagnostics and
are never used for feature generation or legal selection.
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
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402


ISSUE = "issue27ckae_goal_aligned_feature_search_v1_2026-07-05"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = ckac.DEFAULT_HELD_VALUES


@dataclass(frozen=True)
class GeneratedFeature:
    name: str
    group: str
    transform: str
    operands: tuple[str, ...]
    hard_attack_allowed: bool
    rationale: str


def slug(text: Any, limit: int = 96) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:limit] or "empty"


def finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def fmt(value: Any, digits: int = 4) -> str:
    try:
        out = float(value)
    except Exception:
        return "nan"
    if not math.isfinite(out):
        return "nan"
    return f"{out:.{digits}f}"


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(np.asarray(x, dtype=np.float32), 0.0)


def clip_pos(x: np.ndarray, hi: float = 8.0) -> np.ndarray:
    return np.clip(np.asarray(x, dtype=np.float32), 0.0, hi).astype(np.float32)


def fit_only_attack_seed_score(row: dict[str, Any]) -> float:
    """Fit-only seed score.

    This intentionally does not use support_val/select.  It is used only to
    choose primitive seeds before generating candidates.
    """

    attack_score = (
        0.45 * finite(row.get("strength_attack_vs_oodish_fit"))
        + 0.35 * finite(row.get("strength_attack_vs_hard_ood_fit"))
        + 0.20 * finite(row.get("strength_attack_vs_id_fit"))
    )
    penalty = 0.35 * finite(row.get("max_shortcut_strength_fit")) + 0.15 * finite(row.get("strength_id_vs_oodish_fit"))
    return float(attack_score - penalty)


def fit_only_context_seed_score(row: dict[str, Any]) -> float:
    """Fit-only score for conflict/context evidence.

    High values mean the feature is likely useful for conflict, OOD context, or
    shortcut diagnosis.  These features are not allowed to directly support a
    hard attack.
    """

    return float(
        max(
            finite(row.get("max_shortcut_strength_fit")),
            finite(row.get("strength_id_vs_oodish_fit")),
            finite(row.get("strength_attack_vs_oodish_fit")) * 0.50,
        )
    )


def add_seed_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        row2 = dict(row)
        row2["fit_only_attack_seed_score"] = fit_only_attack_seed_score(row2)
        row2["fit_only_context_seed_score"] = fit_only_context_seed_score(row2)
        row2["seed_selection_boundary"] = "fit_only_support_train_id_calib_ood_val_ood_stress"
        out.append(row2)
    return out


def build_cky_spaces(frontend: cky.InteractionCausalFrontend) -> list[ckac.FeatureSpace]:
    _ = frontend.matrix("support_train", np.asarray([0], dtype=np.int64), "full")
    reg = frontend.registry()
    spaces: list[ckac.FeatureSpace] = []
    for block in ["attack_mechanism", "conflict_context"]:
        names = [str(row["feature_name"]) for row in reg if str(row["evidence_group"]) == block]
        spaces.append(
            ckac.FeatureSpace(
                name=f"cky_{block}",
                feature_names=names,
                feature_groups=[block] * len(names),
                matrix_fn=lambda role, idx, b=block: frontend.matrix(role, idx, b),
                description=f"CKY {block} primitive seed space",
            )
        )
    return spaces


def choose_seed_names(
    scored_rows: list[dict[str, Any]],
    max_attack_seeds: int,
    max_context_seeds: int,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    df = pd.DataFrame(scored_rows)
    if df.empty:
        return [], [], []

    attack = df[df["feature_space"] == "cky_attack_mechanism"].copy()
    attack = attack.sort_values(
        ["fit_only_attack_seed_score", "strength_attack_vs_oodish_fit", "strength_attack_vs_hard_ood_fit"],
        ascending=False,
    ).head(max_attack_seeds)

    context = df[df["feature_space"] == "cky_conflict_context"].copy()
    context = context.sort_values(
        ["fit_only_context_seed_score", "max_shortcut_strength_fit", "strength_id_vs_oodish_fit"],
        ascending=False,
    ).head(max_context_seeds)

    seed_rows: list[dict[str, Any]] = []
    attack_names = [str(v) for v in attack["feature_name"].tolist()]
    context_names = [str(v) for v in context["feature_name"].tolist()]
    for rank, (_idx, row) in enumerate(attack.iterrows(), start=1):
        seed_rows.append(
            {
                "seed_rank": rank,
                "seed_kind": "attack_mechanism_seed",
                "feature_space": row["feature_space"],
                "feature_name": row["feature_name"],
                "fit_only_attack_seed_score": row["fit_only_attack_seed_score"],
                "fit_only_context_seed_score": row["fit_only_context_seed_score"],
                "max_shortcut_strength_fit": row["max_shortcut_strength_fit"],
                "strength_attack_vs_oodish_fit": row["strength_attack_vs_oodish_fit"],
                "strength_attack_vs_hard_ood_fit": row["strength_attack_vs_hard_ood_fit"],
                "seed_selection_boundary": "fit_only_no_select_no_query_no_future_no_sealed",
            }
        )
    for rank, (_idx, row) in enumerate(context.iterrows(), start=1):
        seed_rows.append(
            {
                "seed_rank": rank,
                "seed_kind": "conflict_context_seed",
                "feature_space": row["feature_space"],
                "feature_name": row["feature_name"],
                "fit_only_attack_seed_score": row["fit_only_attack_seed_score"],
                "fit_only_context_seed_score": row["fit_only_context_seed_score"],
                "max_shortcut_strength_fit": row["max_shortcut_strength_fit"],
                "strength_attack_vs_oodish_fit": row["strength_attack_vs_oodish_fit"],
                "strength_id_vs_oodish_fit": row["strength_id_vs_oodish_fit"],
                "seed_selection_boundary": "fit_only_no_select_no_query_no_future_no_sealed",
            }
        )
    return attack_names, context_names, seed_rows


class GoalAlignedFeatureSearch:
    """Bounded generator over CKY primitive evidence.

    Attack outputs are built from attack seeds alone or from attack seeds
    explicitly calibrated against context seeds.  Pure context outputs are kept
    conflict-only.
    """

    def __init__(
        self,
        frontend: cky.InteractionCausalFrontend,
        attack_seeds: list[str],
        context_seeds: list[str],
        pair_seed_limit: int,
        context_pair_limit: int,
    ) -> None:
        self.frontend = frontend
        self.attack_seeds = list(dict.fromkeys(attack_seeds))
        self.context_seeds = list(dict.fromkeys(context_seeds))
        self.pair_seed_limit = max(0, int(pair_seed_limit))
        self.context_pair_limit = max(0, int(context_pair_limit))
        _ = self.frontend.matrix("support_train", np.asarray([0], dtype=np.int64), "full")
        self.registry = self.frontend.registry()
        self.base_names = [str(row["feature_name"]) for row in self.registry]
        self.base_groups = [str(row["evidence_group"]) for row in self.registry]
        self.name_to_index = {name: i for i, name in enumerate(self.base_names)}
        self.features = self._build_features()
        self.feature_names = [feat.name for feat in self.features]
        self.feature_groups = [feat.group for feat in self.features]

    def _safe_name(self, prefix: str, *parts: str) -> str:
        joined = "__".join(slug(part, 42) for part in parts)
        return slug(f"{prefix}__{joined}", 140)

    def _build_features(self) -> list[GeneratedFeature]:
        feats: list[GeneratedFeature] = []
        attack = [name for name in self.attack_seeds if name in self.name_to_index]
        context = [name for name in self.context_seeds if name in self.name_to_index]
        pair_attack = attack[: self.pair_seed_limit]
        pair_context = context[: self.context_pair_limit]

        for name in attack:
            feats.append(
                GeneratedFeature(
                    name=self._safe_name("seed_attack", name),
                    group="ckae_attack_seed",
                    transform="identity",
                    operands=(name,),
                    hard_attack_allowed=True,
                    rationale="Fit-only selected CKY attack-mechanism primitive.",
                )
            )
        for name in context:
            feats.append(
                GeneratedFeature(
                    name=self._safe_name("seed_context", name),
                    group="ckae_conflict_context",
                    transform="identity",
                    operands=(name,),
                    hard_attack_allowed=False,
                    rationale="Fit-only selected CKY conflict/context primitive; never direct hard attack.",
                )
            )

        for i, left in enumerate(pair_attack):
            for right in pair_attack[i + 1 :]:
                feats.append(
                    GeneratedFeature(
                        name=self._safe_name("attack_min", left, right),
                        group="ckae_attack_soft_interaction",
                        transform="pair_min",
                        operands=(left, right),
                        hard_attack_allowed=True,
                        rationale="Soft AND between two attack-mechanism seeds.",
                    )
                )
                feats.append(
                    GeneratedFeature(
                        name=self._safe_name("attack_geo", left, right),
                        group="ckae_attack_soft_interaction",
                        transform="pair_geo",
                        operands=(left, right),
                        hard_attack_allowed=True,
                        rationale="Geometric soft AND between two attack-mechanism seeds.",
                    )
                )

        for attack_name in pair_attack:
            feats.append(
                GeneratedFeature(
                    name=self._safe_name("attack_over_ctxmax", attack_name),
                    group="ckae_attack_context_calibrated",
                    transform="over_context_max",
                    operands=(attack_name, *pair_context),
                    hard_attack_allowed=True,
                    rationale="Attack seed divided by aggregate conflict/context pressure.",
                )
            )
            feats.append(
                GeneratedFeature(
                    name=self._safe_name("attack_minus_ctxmean", attack_name),
                    group="ckae_attack_context_calibrated",
                    transform="minus_context_mean",
                    operands=(attack_name, *pair_context),
                    hard_attack_allowed=True,
                    rationale="Attack seed residual after conflict/context pressure.",
                )
            )
            for context_name in pair_context:
                feats.append(
                    GeneratedFeature(
                        name=self._safe_name("attack_over_ctx", attack_name, context_name),
                        group="ckae_attack_context_calibrated",
                        transform="over_context",
                        operands=(attack_name, context_name),
                        hard_attack_allowed=True,
                        rationale="Pairwise attack-vs-context ratio candidate.",
                    )
                )
                feats.append(
                    GeneratedFeature(
                        name=self._safe_name("attack_minus_ctx", attack_name, context_name),
                        group="ckae_attack_context_calibrated",
                        transform="minus_context",
                        operands=(attack_name, context_name),
                        hard_attack_allowed=True,
                        rationale="Pairwise attack-vs-context positive residual candidate.",
                    )
                )

        if attack:
            feats.extend(
                [
                    GeneratedFeature(
                        name="attack_consensus_mean",
                        group="ckae_attack_consensus",
                        transform="attack_mean",
                        operands=tuple(attack),
                        hard_attack_allowed=True,
                        rationale="Mean consensus across selected attack-mechanism seeds.",
                    ),
                    GeneratedFeature(
                        name="attack_consensus_max",
                        group="ckae_attack_consensus",
                        transform="attack_max",
                        operands=tuple(attack),
                        hard_attack_allowed=True,
                        rationale="Max consensus across selected attack-mechanism seeds.",
                    ),
                    GeneratedFeature(
                        name="attack_consensus_top2_mean",
                        group="ckae_attack_consensus",
                        transform="attack_top2_mean",
                        operands=tuple(attack),
                        hard_attack_allowed=True,
                        rationale="Top-2 mean consensus across selected attack-mechanism seeds.",
                    ),
                ]
            )
        if context:
            feats.extend(
                [
                    GeneratedFeature(
                        name="context_pressure_mean",
                        group="ckae_conflict_context",
                        transform="context_mean",
                        operands=tuple(context),
                        hard_attack_allowed=False,
                        rationale="Aggregate conflict/context pressure.",
                    ),
                    GeneratedFeature(
                        name="context_pressure_max",
                        group="ckae_conflict_context",
                        transform="context_max",
                        operands=tuple(context),
                        hard_attack_allowed=False,
                        rationale="Max conflict/context pressure.",
                    ),
                ]
            )
        return feats

    def _cols(self, base: np.ndarray, names: tuple[str, ...]) -> list[np.ndarray]:
        return [base[:, self.name_to_index[name]].astype(np.float32) for name in names if name in self.name_to_index]

    def matrix(self, role: str, idx: np.ndarray) -> np.ndarray:
        base = np.asarray(self.frontend.matrix(role, idx, "full"), dtype=np.float32)
        if len(idx) == 0:
            return np.zeros((0, len(self.features)), dtype=np.float32)
        cols: list[np.ndarray] = []
        for feat in self.features:
            parts = self._cols(base, feat.operands)
            if not parts:
                val = np.zeros(len(idx), dtype=np.float32)
            elif feat.transform == "identity":
                val = parts[0]
            elif feat.transform == "pair_min":
                val = np.minimum(clip_pos(parts[0]), clip_pos(parts[1]))
            elif feat.transform == "pair_geo":
                val = np.sqrt(np.maximum(clip_pos(parts[0]) * clip_pos(parts[1]), 0.0)).astype(np.float32)
            elif feat.transform == "over_context":
                val = parts[0] / (1.0 + np.abs(parts[1]))
            elif feat.transform == "minus_context":
                val = relu(parts[0] - parts[1])
            elif feat.transform == "over_context_max":
                if len(parts) == 1:
                    val = parts[0]
                else:
                    ctx = np.maximum.reduce([np.abs(p) for p in parts[1:]])
                    val = parts[0] / (1.0 + ctx)
            elif feat.transform == "minus_context_mean":
                if len(parts) == 1:
                    val = parts[0]
                else:
                    ctx = np.mean(np.vstack(parts[1:]), axis=0).astype(np.float32)
                    val = relu(parts[0] - ctx)
            elif feat.transform in {"attack_mean", "context_mean"}:
                val = np.mean(np.vstack(parts), axis=0).astype(np.float32)
            elif feat.transform in {"attack_max", "context_max"}:
                val = np.maximum.reduce(parts).astype(np.float32)
            elif feat.transform == "attack_top2_mean":
                stacked = np.vstack(parts)
                if stacked.shape[0] == 1:
                    val = stacked[0]
                else:
                    top2 = np.sort(stacked, axis=0)[-2:, :]
                    val = np.mean(top2, axis=0).astype(np.float32)
            else:
                raise ValueError(f"unknown transform: {feat.transform}")
            cols.append(np.nan_to_num(val, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32))
        return np.vstack(cols).T.astype(np.float32) if cols else np.zeros((len(idx), 0), dtype=np.float32)

    def registry_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for i, feat in enumerate(self.features):
            rows.append(
                {
                    "feature_index": i,
                    **asdict(feat),
                    "operands": "|".join(feat.operands),
                    "seed_attack_count": len(self.attack_seeds),
                    "seed_context_count": len(self.context_seeds),
                }
            )
        return rows


def build_readout(
    out: Path,
    seed_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
    stress_rows: list[dict[str, Any]],
    seconds: float,
) -> list[str]:
    seed = pd.DataFrame(seed_rows)
    gen = pd.DataFrame(generated_rows)
    man = pd.DataFrame(manifest_rows)
    stress = pd.DataFrame(stress_rows)
    counts = gen["recommendation"].value_counts().to_dict() if not gen.empty else {}
    lines = [
        "# issue27ckae goal-aligned feature search v1",
        "",
        "## Scope",
        "",
        "Bounded frontend candidate search.  This is not a detector result.",
        "Seed selection uses fit-only legal data; generated candidates are scored with legal fit/select.",
        "Future/query/sealed/held-family rows remain report-only.",
        "",
        "## Selected primitive seeds",
        "",
        "| kind | rank | feature | fit attack seed | context seed | shortcut |",
        "|---|---:|---|---:|---:|---:|",
    ]
    if not seed.empty:
        for _idx, row in seed.head(20).iterrows():
            lines.append(
                f"| {row['seed_kind']} | {int(row['seed_rank'])} | {row['feature_name']} | "
                f"{fmt(row.get('fit_only_attack_seed_score'))} | {fmt(row.get('fit_only_context_seed_score'))} | "
                f"{fmt(row.get('max_shortcut_strength_fit'))} |"
            )
    lines.extend(
        [
            "",
            "## Top generated attack-evidence candidates",
            "",
            "| rank | feature | group | score | shortcut | recommendation |",
            "|---:|---|---|---:|---:|---|",
        ]
    )
    if not man.empty:
        attack = man[man["purpose"] == "attack_evidence_candidate"].head(15)
        for _idx, row in attack.iterrows():
            lines.append(
                f"| {int(row['rank'])} | {row['feature_name']} | {row['feature_group']} | "
                f"{fmt(row['legal_selection_score'])} | {fmt(row['max_shortcut_strength_fit'])} | {row['recommendation']} |"
            )
    lines.extend(
        [
            "",
            "## Strongest generated conflict/context candidates",
            "",
            "| rank | feature | group | score | shortcut | recommendation |",
            "|---:|---|---|---:|---:|---|",
        ]
    )
    if not man.empty:
        conflict = man[man["purpose"] == "conflict_context_candidate"].head(12)
        for _idx, row in conflict.iterrows():
            lines.append(
                f"| {int(row['rank'])} | {row['feature_name']} | {row['feature_group']} | "
                f"{fmt(row['legal_selection_score'])} | {fmt(row['max_shortcut_strength_fit'])} | {row['recommendation']} |"
            )
    lines.extend(
        [
            "",
            "## Generated group summary",
            "",
            "| group | count | max score | mean score | attack cand | weak attack | conflict | demote | max shortcut |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in group_rows[:18]:
        lines.append(
            f"| {row['feature_group']} | {row['feature_count']} | {fmt(row['max_legal_selection_score'])} | "
            f"{fmt(row['mean_legal_selection_score'])} | {row['candidate_attack_evidence_count']} | "
            f"{row['weak_attack_evidence_count']} | {row['conflict_context_count']} | "
            f"{row['demote_or_discard_count']} | {fmt(row['max_shortcut_strength_fit'])} |"
        )
    if not stress.empty:
        stress2 = stress.sort_values("attack_affinity_positive_means_closer_to_attack", ascending=False).head(12)
        lines.extend(
            [
                "",
                "## Report-only held-family warnings",
                "",
                "| held | role | feature | affinity | rows |",
                "|---|---|---|---:|---:|",
            ]
        )
        for _idx, row in stress2.iterrows():
            lines.append(
                f"| {row['held_value']} | {row['role']} | {row['feature_name']} | "
                f"{fmt(row['attack_affinity_positive_means_closer_to_attack'])} | {int(row['rows'])} |"
            )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Primitive seed selection: fit-only support_train/id_calib/ood_val/ood_stress.",
            "- Generated feature legal scoring: fit + select legal roles only.",
            "- Query/future/sealed and held-family stress rows are report-only diagnostics.",
            "- Pure context features cannot directly support hard attack.",
            "- This step validates frontend candidates before neural-head integration.",
            f"- recommendation counts: {json.dumps({str(k): int(v) for k, v in counts.items()}, ensure_ascii=False)}",
            f"- output: `{out}`",
            f"- runtime seconds: {fmt(seconds, 1)}",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(bool(args.smoke))
    ckt.add_family_columns(frame_by_role)
    role_cap_rows: list[dict[str, Any]] = []
    if int(args.source_cap) > 0:
        x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            int(args.role_cap),
            int(args.source_cap),
            cap_rule="ckae feature-search capped diagnostic",
        )

    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=bool(args.smoke), local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    frontend = cky.InteractionCausalFrontend(builder)

    base_spaces = build_cky_spaces(frontend)
    primitive_rows: list[dict[str, Any]] = []
    primitive_audit: list[dict[str, Any]] = []
    for space in base_spaces:
        rows, audit = ckac.score_feature_space(space, frame_by_role, int(args.seed_eval_cap), int(args.min_group_rows))
        primitive_rows.extend(rows)
        primitive_audit.extend(audit)
    primitive_rows = add_seed_scores(primitive_rows)
    attack_seeds, context_seeds, seed_rows = choose_seed_names(
        primitive_rows,
        int(args.max_attack_seeds),
        int(args.max_context_seeds),
    )

    generator = GoalAlignedFeatureSearch(
        frontend,
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
        description="CKAE generated soft interaction / consensus / attack-context disentangling candidates.",
    )
    generated_rows, generated_audit = ckac.score_feature_space(
        generated_space,
        frame_by_role,
        int(args.eval_cap),
        int(args.min_group_rows),
    )
    group_rows = ckac.group_summary(generated_rows)
    manifest_rows = ckac.recommended_manifest(
        generated_rows,
        int(args.max_attack_features),
        int(args.max_conflict_features),
    )
    held_values = [v.strip() for v in str(args.held_values).split(",") if v.strip()]
    stress_rows = ckac.held_stress_rows(
        [generated_space],
        frame_by_role,
        generated_rows,
        held_values,
        int(args.eval_cap),
        int(args.stress_top_k),
    )
    seconds = time.time() - started

    cko.write_csv(out / "primitive_seed_scores.csv", primitive_rows)
    cko.write_csv(out / "selected_seed_manifest.csv", seed_rows)
    cko.write_csv(out / "generated_feature_registry.csv", generator.registry_rows())
    cko.write_csv(out / "generated_feature_scores.csv", generated_rows)
    cko.write_csv(out / "generated_feature_group_scores.csv", group_rows)
    cko.write_csv(out / "recommended_frontend_manifest.csv", manifest_rows)
    cko.write_csv(out / "held_family_feature_stress_report_only.csv", stress_rows)
    cko.write_csv(out / "role_usage_audit.csv", primitive_audit + generated_audit)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "cky_frontend_registry.csv", frontend.registry())
    cko.write_md(out / "codex_readout.md", build_readout(out, seed_rows, generated_rows, group_rows, manifest_rows, stress_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "smoke": bool(args.smoke),
            "role_cap": int(args.role_cap),
            "source_cap": int(args.source_cap),
            "seed_eval_cap": int(args.seed_eval_cap),
            "eval_cap": int(args.eval_cap),
            "max_attack_seeds": int(args.max_attack_seeds),
            "max_context_seeds": int(args.max_context_seeds),
            "pair_seed_limit": int(args.pair_seed_limit),
            "context_pair_limit": int(args.context_pair_limit),
            "held_values": held_values,
            "data_use_boundary": {
                "seed_selection_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "seed_selection_uses_select": False,
                "generated_candidate_legal_scoring_roles": [
                    "support_train fit",
                    "id_calib fit",
                    "ood_val fit",
                    "ood_stress fit",
                    "support_val select",
                    "id_calib select",
                    "ood_val select",
                    "ood_stress select",
                ],
                "query_future_sealed_used_for_selection": False,
                "held_family_stress_used_for_selection": False,
            },
            "frontend_contract": {
                "pure_context_direct_hard_attack_allowed": False,
                "source_or_device_used_as_inference_feature": False,
                "flow_temporal_state": "current/past-only within processed source file",
                "row_alignment": "CKQ builder role/index aligned matrices",
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", default=True)
    parser.add_argument("--role-cap", type=int, default=384)
    parser.add_argument("--source-cap", type=int, default=48)
    parser.add_argument("--seed-eval-cap", type=int, default=384)
    parser.add_argument("--eval-cap", type=int, default=384)
    parser.add_argument("--min-group-rows", type=int, default=8)
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--max-attack-seeds", type=int, default=10)
    parser.add_argument("--max-context-seeds", type=int, default=8)
    parser.add_argument("--pair-seed-limit", type=int, default=8)
    parser.add_argument("--context-pair-limit", type=int, default=6)
    parser.add_argument("--max-attack-features", type=int, default=48)
    parser.add_argument("--max-conflict-features", type=int, default=48)
    parser.add_argument("--stress-top-k", type=int, default=20)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
