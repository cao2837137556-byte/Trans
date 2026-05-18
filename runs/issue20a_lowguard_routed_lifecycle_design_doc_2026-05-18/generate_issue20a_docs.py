from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue20a_lowguard_routed_lifecycle_design_doc_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE19 = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE17 = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE16B = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
ISSUE15 = ROOT / "runs" / "issue15_review_budget_constrained_arbitration_2026-05-15"
ISSUE14B = ROOT / "runs" / "issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, columns: list[str] | None = None) -> str:
    if columns is not None:
        df = df[columns].copy()
    if df.empty:
        return "_No rows._\n"
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, row in df.iterrows():
        vals = []
        for value in row:
            if isinstance(value, float):
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE19B / "summary.md",
        ISSUE19B / "v1_vs_v2_by_dataset.csv",
        ISSUE19B / "alarm_budget_curve_summary.csv",
        ISSUE19B / "feasible_operating_points.csv",
        ISSUE19B / "non_regression_report.md",
        ISSUE19B / "mode_routing_implication.md",
        ISSUE19B / "claim_boundary.md",
        ISSUE19 / "summary.md",
        ISSUE15 / "review_budget_metrics_summary.csv",
        ISSUE14B / "strategy_metrics_summary.csv",
        ISSUE18 / "diagnostic_decision.md",
        ISSUE17 / "summary.md",
        ISSUE16B / "summary.md",
    ]
    return [str(path) for path in required if not path.exists()]


def row_for(df: pd.DataFrame, holdout: str, seed_group: str = "main_42_46") -> dict:
    rows = df[(df["holdout"] == holdout) & (df["seed_group"] == seed_group)]
    if rows.empty:
        rows = df[df["holdout"] == holdout]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))

    v1v2 = pd.read_csv(ISSUE19B / "v1_vs_v2_by_dataset.csv") if (ISSUE19B / "v1_vs_v2_by_dataset.csv").exists() else pd.DataFrame()
    alarm = pd.read_csv(ISSUE19B / "alarm_budget_curve_summary.csv") if (ISSUE19B / "alarm_budget_curve_summary.csv").exists() else pd.DataFrame()
    feasible = pd.read_csv(ISSUE19B / "feasible_operating_points.csv") if (ISSUE19B / "feasible_operating_points.csv").exists() else pd.DataFrame()
    review = pd.read_csv(ISSUE15 / "review_budget_metrics_summary.csv") if (ISSUE15 / "review_budget_metrics_summary.csv").exists() else pd.DataFrame()
    strategy = pd.read_csv(ISSUE14B / "strategy_metrics_summary.csv") if (ISSUE14B / "strategy_metrics_summary.csv").exists() else pd.DataFrame()

    primary = row_for(v1v2, "primary_lowood")
    hb2 = row_for(v1v2, "holdout_bin_2")
    chrono = row_for(v1v2, "chrono_late_train_early_eval")

    evidence_table = v1v2[
        [
            "dataset",
            "holdout",
            "seed_group",
            "v1_detection_mean",
            "v1_ood_alarm_max",
            "v2_detection_mean",
            "v2_ood_alarm_max",
            "delta_detection_v2_minus_v1",
        ]
    ].copy() if not v1v2.empty else pd.DataFrame()

    candidate_v2 = feasible[
        feasible.get("method_version", pd.Series(dtype=str)).eq("V2_LOW_GUARD_plus")
        & feasible.get("ood_target_label", pd.Series(dtype=str)).isin(["1.2pct", "1.5pct", "2.0pct"])
    ][
        [
            "dataset",
            "holdout",
            "seed_group",
            "ood_target_label",
            "attack_high_detection_mean",
            "final_ood_high_alarm_max",
        ]
    ].copy() if not feasible.empty else pd.DataFrame()

    review_slice = pd.DataFrame()
    if not review.empty:
        review_slice = review[
            review["review_policy"].isin(["review_off", "review_top_0.5pct", "review_top_1pct", "review_all"])
            & review["base_detector"].eq("dA")
            & review["seed_group"].isin(["main_paired_42_46", "heldout_support_47_51"])
        ].copy()
        keep_cols = [
            "base_detector",
            "seed_group",
            "review_policy",
            "review_budget_used_mean",
            "attack_high_detection_mean",
            "OOD_high_alarm_mean",
            "attack_review_rate_mean",
            "OOD_review_rate_mean",
            "OOD_total_burden_mean",
        ]
        review_slice = review_slice[[c for c in keep_cols if c in review_slice.columns]]

    strategy_slice = pd.DataFrame()
    if not strategy.empty:
        strategy_slice = strategy[
            strategy["base_detector"].eq("dA")
            & strategy["strategy"].isin(["base_only", "gda_only", "OR_policy", "AND_policy", "mode_gated_arbitration"])
            & strategy["seed_group"].isin(["main_paired_42_46", "heldout_support_47_51"])
        ].copy()
        keep_cols = [
            "base_detector",
            "strategy",
            "seed_group",
            "attack_high_detection_mean",
            "OOD_high_alarm_mean",
            "attack_review_rate_mean",
            "OOD_review_rate_mean",
        ]
        strategy_slice = strategy_slice[[c for c in keep_cols if c in strategy_slice.columns]]

    primary_v1 = float(primary.get("v1_detection_mean", float("nan")))
    primary_v1_ood = float(primary.get("v1_ood_alarm_max", float("nan")))
    primary_v2 = float(primary.get("v2_detection_mean", float("nan")))
    primary_v2_ood = float(primary.get("v2_ood_alarm_max", float("nan")))
    hb2_v1 = float(hb2.get("v1_detection_mean", float("nan")))
    hb2_v1_ood = float(hb2.get("v1_ood_alarm_max", float("nan")))
    hb2_v2 = float(hb2.get("v2_detection_mean", float("nan")))
    hb2_v2_ood = float(hb2.get("v2_ood_alarm_max", float("nan")))
    chrono_v1 = float(chrono.get("v1_detection_mean", float("nan")))
    chrono_v1_ood = float(chrono.get("v1_ood_alarm_max", float("nan")))
    chrono_v2 = float(chrono.get("v2_detection_mean", float("nan")))
    chrono_v2_ood = float(chrono.get("v2_ood_alarm_max", float("nan")))

    write_text(
        OUT / "summary.md",
        f"""
# Issue20a LOW-GUARD-Routed Lifecycle Design Summary

## Purpose

This design pack freezes the current deployment interpretation after issue19b. It does not run experiments, train models, modify the manuscript, or modify historical numbers. Its role is to prepare issue20 mode-specific routing validation and future Method/System writing.

## Evidence Snapshot

{md_table(evidence_table)}

## System Positioning

`LOW-GUARD-Routed` is a mode-specific routed adaptation system:

- V1 / LOW-GUARD-minimal: `original100 + kcenter32 + fixed guard LR`.
- V2 / LOW-GUARD+: `selected_source_rich_top32 + kcenter32 + fixed guard LR`.
- V1 remains the primary low-OOD stable module because primary low-OOD has V1 detection {primary_v1:.4f} with OOD max {primary_v1_ood:.4f}, while V2 has detection {primary_v2:.4f} but OOD max {primary_v2_ood:.4f}.
- V2 is a harder attack-side shift repair module because holdout_bin_2 improves from V1 detection {hb2_v1:.4f} to V2 detection {hb2_v2:.4f}, with V2 OOD max {hb2_v2_ood:.4f}.
- V2 also improves chrono_late from {chrono_v1:.4f} to {chrono_v2:.4f}, with OOD max {chrono_v2_ood:.4f}.

## Core Conclusion

Single-adapter deployment is unsafe: always-V1 misses harder attack-side shift, while always-V2 exceeds the primary low-OOD alert budget. The correct next step is not another ad hoc V3, but a bounded routed lifecycle with a Low-Alert Promotion Gate.

## Next Step

Unique first choice: `issue20_mode_specific_routing_validation_2026-05-18`.
""",
    )

    write_text(
        OUT / "lowguard_routed_lifecycle_design.md",
        f"""
# LOW-GUARD-Routed Lifecycle Design

## A. System Motivation

Primary low-OOD and harder attack-side shift impose different constraints. In the primary low-OOD setting, V1 is conservative and stable: detection {primary_v1:.4f}, OOD max {primary_v1_ood:.4f}. V2 is not a safe universal replacement there because OOD max rises to {primary_v2_ood:.4f}, above the 1% budget, while detection changes only slightly.

In holdout_bin_2, always-V1 fails the attack-side shift: detection {hb2_v1:.4f}. V2 repairs that failure with detection {hb2_v2:.4f} and OOD max {hb2_v2_ood:.4f}. Therefore the scientific conclusion is not "V2 replaces V1"; it is that benign-OOD drift and attack-side shift require mode-specific low-alert adaptation.

## B. Runtime Architecture

```text
Incoming traffic
  -> feature extraction
  -> V1 score and V2 score
  -> drift monitor
  -> promotion / routing gate
  -> high_priority_alert / needs_review / low_priority_or_background
```

The architecture keeps base detector evidence and adapter evidence separate until the routing gate decides which adapter controls high-priority alerting. Review is a bounded safety net, not the main high-priority channel.

## C. Three Operating Modes

### Mode 0: cold-start / ordinary monitoring

Before high-purity confirmed attack supports are available, the system relies on the deployed base detector for cold-start anomaly monitoring. LOW-GUARD adapters are not the primary alerting model in this mode.

### Mode 1: primary low-OOD stable adaptation

V1 is the active champion. It is used when validation evidence indicates primary low-OOD-like traffic and the stricter OOD alarm budget is best served by original100 fixed guard.

### Mode 2: harder attack-side shift adaptation

V2 becomes active only after validation evidence shows a harder attack-side shift and confirms that V2 satisfies the low-alert budget. V2 is not activated merely because it is more sensitive on a prior final evaluation.

## D. Champion-Challenger Lifecycle

- Current champion: the currently active adapter for a specific mode.
- Shadow challenger: a candidate adapter evaluated on validation windows without controlling production high-priority alerting.
- Validation gate: checks attack-side proxy improvement, OOD alarm budget, review burden, provenance, and stability.
- Promotion: challenger becomes champion only inside the mode for which it passed the gate.
- Rejection: challenger remains offline or in shadow if it fails the gate.
- Rollback: if a promoted champion violates runtime alert or review budgets, the system rolls back to the previous champion.
- Retirement: stale models may be archived after enough clean windows, but scores/provenance remain auditable.

## E. Why This Is Not Infinite Nesting

This is a bounded lifecycle, not V1 -> V2 -> V3 unbounded stacking. The system maintains a finite model pool, requires a promotion gate, rejects candidates that fail validation, and uses cooldown or validation windows before promotion. Old champions are fallback references, not infinitely accumulated alerting modules. A new adapter is not allowed to become active simply because it looks better on a final report.
""",
    )

    write_text(
        OUT / "promotion_gate_policy.md",
        """
# Low-Alert Promotion Gate Policy

## A. Promotion Inputs

- OOD validation alarm.
- Confirmed attack support performance.
- Detection proxy on local attack validation or support holdout.
- Review burden.
- Score or feature drift indicators.
- Seed/window stability.
- Cost and latency, when available.
- Provenance checks for supports, threshold, scaler, and feature selection.

## B. Promotion Conditions

A challenger can be promoted to champion only if all conditions hold:

- Detection proxy is meaningfully better than the current champion in the relevant mode.
- OOD alarm is within the target budget, normally <= 1%.
- Review burden does not exceed the operational review budget.
- Support, threshold, scaler, and feature provenance are clean.
- The improvement appears across at least N validation windows or seed groups.
- No leakage or protocol rule is violated.

## C. Rejection Conditions

- OOD alarm exceeds budget.
- Improvement appears only in one narrow window.
- Detection gain is small while false alarm or review burden increases.
- Provenance is incomplete or contaminated.
- V1/V2 conflict samples increase sharply without a review budget.
- Cost or latency is unacceptable.

## D. Rollback Rule

After promotion, if OOD alarm or review burden exceeds runtime limits, the system rolls back to the previous champion. Historical V1/V2 scores remain available for audit. Old models are not deleted immediately; they become fallback or analysis references.

## E. Candidate Operating Point Rule

Issue19b found diagnostic V2 operating-point slack on holdout_bin_2 for 1.2% and 1.5% validation targets, but those are not official thresholds. Any 1.2% / 1.5% candidate must be pre-registered and pass locked validation before replacing the 1% operating point. The system cannot hand-select a threshold such as final OOD alarm 0.008 from final evaluation.
""",
    )

    write_text(
        OUT / "v1_v2_deployment_roles.md",
        f"""
# V1/V2 Deployment Roles

## V1: LOW-GUARD-minimal

- Role: primary low-OOD stable module.
- Strength: conservative low OOD alarm. Primary low-OOD OOD max is {primary_v1_ood:.4f}.
- Weakness: insufficient attack-side harder-shift detection. holdout_bin_2 detection is {hb2_v1:.4f}.
- Use case: primary low-OOD / conservative mode.

## V2: LOW-GUARD+

- Role: harder attack-side shift repair module.
- Strength: strong holdout_bin_2 repair, from {hb2_v1:.4f} to {hb2_v2:.4f}; chrono_late also improves from {chrono_v1:.4f} to {chrono_v2:.4f}.
- Weakness: primary low-OOD OOD max rises to {primary_v2_ood:.4f}, so V2 is unsafe as a universal replacement.
- Use case: activated only when validation evidence indicates harder attack-side shift and OOD alarm remains controlled.

## Conflict Handling

| V1 high | V2 high | output |
|---|---|---|
| false | false | low_priority_or_background |
| true | true | high_priority_alert |
| true | false | needs_review |
| false | true | high_priority_alert if V2 mode active; otherwise needs_review |

V1 high / V2 low is preserved as review evidence. V1 low / V2 high is high-priority only when V2 has passed the promotion/routing gate for the active mode.
""",
    )

    write_text(
        OUT / "reviewer_defense.md",
        """
# Reviewer Defense Notes

## Q1: Are you just stacking whichever model looks best?

No. The routing gate is constrained by a low-alert budget, validation evidence, review burden, and provenance checks. Issue20 must compare routed deployment against always-V1, always-V2, OR, AND, and review-heavy policies.

## Q2: Why not replace V1 with V2?

Because V2 is not uniformly safer. In primary low-OOD, V2 exceeds the 1% OOD budget, while V1 remains below it. V2 is a harder-shift repair module, not a universal replacement.

## Q3: What if V2 also fails later?

The system uses a bounded champion-challenger lifecycle. A candidate must pass a promotion gate before becoming active. Failed candidates remain in shadow or are rejected; they are not stacked indefinitely.

## Q4: Does low attack fraction in review weaken the contribution?

Review is a safety net, not a confirmed attack pool. The high-priority alert channel is controlled by the active champion. Review preserves base-only or challenger-conflict evidence for auditing and later model updates.

## Q5: Is this just MLOps rather than research?

The research point is the low-alert intrusion detection problem under benign-OOD drift: a high-recall adapter can be unsafe under OOD alarm constraints, so promotion must be budget-bound and evidence-driven. This is tied to measured V1/V2 conflicts, not generic engineering process.

## Q6: Did you select the model using final evaluation?

No. The proposed routing and promotion rules must use validation windows. Final OOD and attack evaluations are for reporting only. Issue19b alarm-budget slack is diagnostic and requires locked validation.

## Q7: Will V3/V4 cause catastrophic forgetting or model proliferation?

The lifecycle retains old champions as fallback and audit references, uses validation windows and rollback, and rejects candidates that fail the gate. It is not unconstrained continual learning.
""",
    )

    write_text(
        OUT / "issue20_routing_validation_plan.md",
        """
# Issue20 Routing Validation Plan

## A. Experimental Goal

Validate whether LOW-GUARD-Routed is better than:

- always V1;
- always V2;
- OR ensemble;
- AND ensemble;
- review-all;
- oracle upper bound, if applicable.

## B. Data Settings

Required:

- primary low-OOD;
- holdout_bin_2;
- chrono_late_train_early_eval.

Optional:

- ordinary compatibility, only if a comparable guarded protocol can be defined without leakage.

## C. Pre-Registered Routing Rule

A simple first routing rule:

- If V2 validation OOD alarm <= 1%, and V2 attack validation or support-holdout detection proxy exceeds V1 by at least 5 percentage points, activate V2.
- Otherwise activate V1.

If attack validation is unavailable or too small, use a held-out support proxy and mark the limitation. The rule must not use final OOD eval or attack eval.

## D. Output Metrics

- Attack high detection.
- OOD high alarm.
- Feasible rate.
- Review burden.
- Conflict count.
- Selected champion.
- Wrong-routing cases.
- Routing decision provenance.

## E. Success Standard

- Primary low-OOD selects V1 and avoids V2's OOD over-budget failure.
- holdout_bin_2 selects V2 and recovers detection.
- chrono_late selects V2 or remains feasible with the selected champion.
- Routed system improves the worst-case tradeoff over always-V1 and always-V2.
- Review burden remains bounded.
""",
    )

    write_text(
        OUT / "paper_framing_insert.md",
        """
# 论文写作草稿：LOW-GUARD-Routed

单一适配器不足以覆盖所有部署阶段的漂移形态。在 primary low-OOD 场景中，LOW-GUARD-minimal 保持较低 OOD 告警，并提供稳定的攻击检出；但在 harder attack-side shift 场景中，它的攻击检出明显下降。LOW-GUARD+ 能显著修复 harder shift 下的攻击检出，但在 primary low-OOD 上会超过 1% OOD 告警预算。因此，直接用 V2 替代 V1 并不安全。

基于这一观察，本文后续方法应表述为 LOW-GUARD-Routed：一个部署阶段的低告警路由式适配系统。系统维护当前 champion adapter 和 shadow challenger adapter。候选适配器只有在低告警验证窗口中同时满足攻击检出代理收益、OOD 告警预算、review burden 和 provenance clean 条件时，才允许晋升为特定模式下的 champion。

该机制不是无约束的 V1/V2/V3 堆叠。未通过 promotion gate 的模型保持 shadow 状态或被拒绝；已上线模型若在运行时违反 OOD 告警或 review burden 约束，则回滚到上一 champion。V1 high / V2 low 的冲突样本进入 bounded review queue，而不是直接高优先告警，也不是丢弃。review queue 是安全兜底和审计入口，不应被解释为确认攻击样本池。

该设计的边界也必须明确：issue19b 只证明 V1 与 V2 在不同漂移模式下具有互补角色，并动机化 routing validation。LOW-GUARD-Routed 的策略有效性仍需要后续 issue20 routing validation 证明；alarm-budget curve 中的候选 operating point 也必须经过 locked validation，不能基于 final OOD eval 直接改变正式阈值。
""",
    )

    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- V1 and V2 have complementary deployment roles.
- LOW-GUARD-Routed is motivated by the fact that no single adapter dominates all drift settings.
- Low-Alert Promotion Gate prevents unsafe promotion of high-recall but high-alarm adapters.
- Champion-challenger lifecycle avoids unbounded model replacement.

## Cannot Say

- V2 is the final universal model.
- V3/V4 will automatically solve future drift.
- Routing has been experimentally validated before issue20.
- Lifecycle alone is the main algorithmic contribution.
- A-zone readiness is achieved.
""",
    )

    risk_rows = [
        ["routing overfit risk", "high", "Routing rule could be shaped around issue19b settings.", "Pre-register issue20 rule and report failures."],
        ["validation proxy weakness", "high", "Support/validation proxy may not represent final attack shift.", "Report proxy limits and wrong-routing cases."],
        ["V2 overfit to holdout_bin_2", "high", "V2 was motivated by holdout_bin_2 repair.", "Evaluate primary and chrono_late together."],
        ["alarm-budget cherry-picking", "high", "1.2/1.5 target could be cherry-picked.", "Treat as locked-validation candidates only."],
        ["model proliferation risk", "medium", "Champion-challenger can become uncontrolled if every failure creates a model.", "Use finite pool, promotion gate, retirement."],
        ["catastrophic forgetting", "medium", "New champion may suppress old evidence.", "Keep old champion scores and rollback."],
        ["malicious behavior contamination", "medium", "Confirmed supports may be noisy or attacker-influenced.", "Require support provenance and bounded promotion."],
        ["review burden underestimation", "medium", "Review queue may exceed operations budget.", "Report high-priority and review burden separately."],
        ["deployment cost", "medium", "Running V1/V2 in parallel has cost.", "Record latency and cost in issue20 if available."],
        ["unclear trigger condition risk", "high", "Routing trigger may be ambiguous.", "Issue20 must record selected champion and decision provenance."],
    ]
    with (OUT / "risk_register.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["risk_name", "severity", "reason", "mitigation"])
        writer.writerows(risk_rows)

    write_text(
        OUT / "recommended_next_action.md",
        """
# Recommended Next Action

Unique first choice: `issue20_mode_specific_routing_validation_2026-05-18`.

Do not first continue repairing V2. Do not first create V3. The immediate scientific question is whether a validation-only routing gate can choose V1 for primary low-OOD and V2 for harder attack-side shift without using final evaluation.

If routing succeeds, then follow with V2 operating-point locked validation, 64-shot sensitivity, and selected-feature stability. If routing fails, redefine the mode trigger before adding new adapters.
""",
    )

    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Do not modify the manuscript now. After issue20 validation, append the following if supported:

`Issue20a froze the LOW-GUARD-Routed lifecycle design: V1 remains the primary low-OOD champion, V2 is a harder-shift challenger/repair candidate, and promotion requires a low-alert validation gate rather than final-eval threshold selection. Next step is issue20 mode-specific routing validation.`
""",
    )

    provenance = {
        "run": "issue20a_lowguard_routed_lifecycle_design_doc_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "issue19b": str(ISSUE19B),
            "issue19": str(ISSUE19),
            "issue18": str(ISSUE18),
            "issue17": str(ISSUE17),
            "issue16b": str(ISSUE16B),
            "issue15": str(ISSUE15),
            "issue14b": str(ISSUE14B),
        },
        "experiment_run": False,
        "model_training": False,
        "manuscript_modified": False,
        "historical_numbers_modified": False,
    }
    (OUT / "config.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
