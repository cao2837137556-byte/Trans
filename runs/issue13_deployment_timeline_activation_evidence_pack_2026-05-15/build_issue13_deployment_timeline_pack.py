from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


ROOT = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
OUT = ROOT / "runs" / "issue13_deployment_timeline_activation_evidence_pack_2026-05-15"

RUNS = {
    "issue02": ROOT / "runs/issue02_original_da_normal_attack_sanity_run_2026-05-08",
    "issue06b": ROOT / "runs/issue06b_transformer_normal_attack_sanity_run_2026-05-08",
    "issue07a": ROOT / "runs/issue07a_da_assisted_adapter_lowood_repair_2026-05-14",
    "issue07b": ROOT
    / "runs/issue07b_transformer_assisted_adapter_lowood_repair_2026-05-14_rerun_with_recovered_scores",
    "issue09": ROOT / "runs/issue09_source_rich_representation_probe_2026-05-14",
    "issue10": ROOT / "runs/issue10_minimal_ood_guarded_lr_source_rich_2026-05-14",
    "issue11": ROOT / "runs/issue11_fixed_config_ood_guard_lr_ablation_2026-05-14",
    "issue12": ROOT / "runs/issue12_base_detector_representation_recovery_and_guarded_probe_2026-05-15",
}


def fnum(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def fmt(v: Optional[float]) -> str:
    if v is None:
        return "NA"
    return f"{v:.4f}"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def get_row(df: pd.DataFrame, **conds: Any) -> Optional[pd.Series]:
    if df.empty:
        return None
    mask = pd.Series([True] * len(df))
    for key, value in conds.items():
        if key not in df.columns:
            return None
        mask &= df[key].astype(str).eq(str(value))
    subset = df[mask]
    if subset.empty:
        return None
    return subset.iloc[0]


def add_timeline(
    rows: List[Dict[str, Any]],
    *,
    phase: str,
    method: str,
    input_representation: str,
    base_detector_role: str,
    adapter_role: str,
    setting: str,
    budget: Any,
    seed_group: str,
    detection_mean: Optional[float],
    detection_min: Optional[float],
    ood_alarm_mean: Optional[float],
    ood_alarm_max: Optional[float],
    feasible_rate: Optional[float],
    main_conclusion: str,
    paper_role: str,
    claim_strength: str,
    source_run_path: Path,
) -> None:
    rows.append(
        {
            "phase": phase,
            "method": method,
            "input_representation": input_representation,
            "base_detector_role": base_detector_role,
            "adapter_role": adapter_role,
            "setting": setting,
            "budget": budget,
            "seed_group": seed_group,
            "detection_mean": detection_mean,
            "detection_min": detection_min,
            "ood_alarm_mean": ood_alarm_mean,
            "ood_alarm_max": ood_alarm_max,
            "feasible_rate": feasible_rate,
            "main_conclusion": main_conclusion,
            "paper_role": paper_role,
            "claim_strength": claim_strength,
            "source_run_path": str(source_run_path),
        }
    )


def write_md(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(rows: List[Dict[str, Any]], cols: List[str]) -> str:
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in rows:
        vals = []
        for col in cols:
            val = row.get(col, "")
            if isinstance(val, float):
                vals.append(f"{val:.4f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    timeline_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, str]] = []

    for name, path in RUNS.items():
        if not path.exists():
            missing_rows.append({"asset": name, "path": str(path), "status": "missing", "note": "Required run directory not found."})

    # Phase 0: ordinary setting.
    issue02 = read_csv(RUNS["issue02"] / "combined_sanity_comparison.csv")
    da_ord = get_row(issue02, model_name="da_reference_clean115", threshold_name="benign_calib_q99")
    if da_ord is not None:
        add_timeline(
            timeline_rows,
            phase="Phase 0: cold-start ordinary setting",
            method="dA ordinary sanity",
            input_representation="clean115",
            base_detector_role="classic cold-start normal-only detector",
            adapter_role="not active; no attack supports required",
            setting="ordinary normal-vs-attack; no OOD benign",
            budget="NA",
            seed_group="single dA reference",
            detection_mean=fnum(da_ord.attack_detection_mean),
            detection_min=fnum(da_ord.attack_detection_min),
            ood_alarm_mean=fnum(da_ord.benign_false_alarm_mean),
            ood_alarm_max=fnum(da_ord.benign_false_alarm_max),
            feasible_rate=None,
            main_conclusion="dA is strong in the ordinary normal-vs-attack setting; later collapse should not be framed as dA being intrinsically weak.",
            paper_role="appendix sanity / deployment timeline motivation",
            claim_strength="A-level ordinary-setting sanity for dA",
            source_run_path=RUNS["issue02"],
        )
    else:
        missing_rows.append({"asset": "issue02 dA ordinary q99", "path": str(RUNS["issue02"]), "status": "missing", "note": "Could not locate q99 row."})

    issue06b = read_csv(RUNS["issue06b"] / "transformer_vs_da_same_split_comparison.csv")
    tr_ord = get_row(issue06b, threshold_name="same_subset_benign_calib_q99")
    if tr_ord is not None:
        add_timeline(
            timeline_rows,
            phase="Phase 0: cold-start ordinary setting",
            method="Transformer ordinary same-subset sanity",
            input_representation="clean115",
            base_detector_role="plausible modern contextual base detector candidate",
            adapter_role="not active; no attack supports required",
            setting="ordinary normal-vs-attack large-subset sanity; no OOD benign",
            budget="NA",
            seed_group="large-subset seed 20260508",
            detection_mean=fnum(tr_ord.transformer_attack_detection),
            detection_min=fnum(tr_ord.transformer_attack_detection),
            ood_alarm_mean=fnum(tr_ord.transformer_benign_false_alarm),
            ood_alarm_max=fnum(tr_ord.transformer_benign_false_alarm),
            feasible_rate=None,
            main_conclusion="Transformer is close to dA on the same normal-vs-attack subset, but not clearly superior.",
            paper_role="appendix sanity / base detector candidate evidence",
            claim_strength="B-level same-subset sanity evidence",
            source_run_path=RUNS["issue06b"],
        )
    else:
        missing_rows.append({"asset": "issue06b Transformer ordinary same-subset q99", "path": str(RUNS["issue06b"]), "status": "missing", "note": "Could not locate q99 row."})

    # Phase 1: base-only low-OOD collapse.
    issue07a_base = read_csv(RUNS["issue07a"] / "fixed_baseline_metrics.csv")
    da_low = get_row(issue07a_base, baseline="fixed_baseline_da_only")
    if da_low is not None:
        add_timeline(
            timeline_rows,
            phase="Phase 1: open-world low-OOD before adaptation",
            method="dA-only guarded low-OOD baseline",
            input_representation="dA RMSE score",
            base_detector_role="low-OOD collapse diagnostic baseline",
            adapter_role="not active",
            setting="current low-OOD guarded protocol",
            budget="NA",
            seed_group="fixed baseline",
            detection_mean=fnum(da_low.attack_detection),
            detection_min=fnum(da_low.attack_detection),
            ood_alarm_mean=fnum(da_low.final_ood_alarm),
            ood_alarm_max=fnum(da_low.final_ood_alarm),
            feasible_rate=fnum(da_low.feasible_rate),
            main_conclusion="dA shows near-zero attack detection at the guarded low-OOD working point.",
            paper_role="main collapse reference / timeline Phase 1",
            claim_strength="A-level current-protocol baseline",
            source_run_path=RUNS["issue07a"],
        )
    else:
        missing_rows.append({"asset": "dA-only low-OOD baseline", "path": str(RUNS["issue07a"]), "status": "missing", "note": "fixed_baseline_da_only not found."})

    issue07b_base = read_csv(RUNS["issue07b"] / "fixed_baseline_metrics.csv")
    tr_low = get_row(issue07b_base, baseline="fixed_baseline_transformer_only")
    if tr_low is not None:
        add_timeline(
            timeline_rows,
            phase="Phase 1: open-world low-OOD before adaptation",
            method="Transformer-only guarded low-OOD baseline",
            input_representation="Transformer scalar anomaly score",
            base_detector_role="modern base detector low-OOD diagnostic baseline",
            adapter_role="not active",
            setting="current low-OOD guarded protocol",
            budget="NA",
            seed_group="fixed baseline",
            detection_mean=fnum(tr_low.attack_detection),
            detection_min=fnum(tr_low.attack_detection),
            ood_alarm_mean=fnum(tr_low.final_ood_alarm),
            ood_alarm_max=fnum(tr_low.final_ood_alarm),
            feasible_rate=fnum(tr_low.feasible_rate),
            main_conclusion="Transformer scalar score also collapses at the guarded low-OOD working point.",
            paper_role="timeline Phase 1 / modern base detector diagnostic",
            claim_strength="B-level current-protocol scalar baseline",
            source_run_path=RUNS["issue07b"],
        )
    else:
        missing_rows.append({"asset": "Transformer-only low-OOD baseline", "path": str(RUNS["issue07b"]), "status": "missing", "note": "fixed_baseline_transformer_only not found."})

    # Phase 2: score-level adaptation attempts.
    issue07a_sum = read_csv(RUNS["issue07a"] / "method_comparison_summary.csv")
    issue07b_sum = read_csv(RUNS["issue07b"] / "method_comparison_summary.csv")
    score_specs = [
        (issue07a_sum, RUNS["issue07a"], "da_score_only_fewshot_lr", "dA score-only few-shot LR", "dA scalar score", "Scalar dA score is insufficient for few-shot repair.", "C-level / negative score-fusion evidence"),
        (issue07a_sum, RUNS["issue07a"], "original100_plus_da_score_fewshot_lr", "original100 + dA score few-shot LR", "original100 + dA scalar score", "Adding dA scalar score does not materially improve over original100-only LR.", "B-level negative fusion evidence"),
        (issue07b_sum, RUNS["issue07b"], "transformer_score_only_fewshot_lr", "Transformer score-only few-shot LR", "Transformer scalar score", "Scalar Transformer score is insufficient for few-shot repair.", "C-level / negative score-fusion evidence"),
        (issue07b_sum, RUNS["issue07b"], "original100_plus_transformer_score_fewshot_lr", "original100 + Transformer score few-shot LR", "original100 + Transformer scalar score", "Adding Transformer scalar score does not materially improve over original100-only LR.", "B-level negative fusion evidence"),
    ]
    for df, path, method_key, method_name, rep, conclusion, strength in score_specs:
        for budget in [16, 32]:
            row = get_row(df, method=method_key, positive_budget=budget)
            if row is None:
                missing_rows.append({"asset": f"{method_key} budget {budget}", "path": str(path), "status": "missing", "note": "method row not found."})
                continue
            add_timeline(
                timeline_rows,
                phase="Phase 2: score-level adaptation attempt",
                method=method_name,
                input_representation=rep,
                base_detector_role="scalar score provider only",
                adapter_role="minimal few-shot LR adapter",
                setting="current low-OOD guarded protocol",
                budget=budget,
                seed_group="main seeds 42-46",
                detection_mean=fnum(row.attack_detection_mean),
                detection_min=fnum(row.attack_detection_min),
                ood_alarm_mean=fnum(row.ood_alarm_mean),
                ood_alarm_max=fnum(row.ood_alarm_max),
                feasible_rate=fnum(row.feasible_rate),
                main_conclusion=conclusion,
                paper_role="negative mechanism evidence / timeline Phase 2",
                claim_strength=strength,
                source_run_path=path,
            )

    # Phase 3/4: minimal and guarded adaptation from issue11.
    issue11 = read_csv(RUNS["issue11"] / "method_comparison_summary.csv")
    phase11_specs = [
        ("Phase 3: few-shot minimal adaptation", "original100_plain_lr", "original100 plain few-shot LR", "original100", "minimal target-alignment adapter", "original100-only LR is the minimal repair baseline; it is not the final GDA."),
        ("Phase 4: guarded deployment adaptation", "original100_fixed_guard_lr", "GDA-minimal: original100 fixed OOD guard LR", "original100", "fixed OOD-benign guarded few-shot adapter", "Current most stable GDA-minimal configuration; validates fixed OOD guard mechanism."),
        ("Phase 4: guarded deployment adaptation", "source_rich_fixed_guard_lr", "source_rich fixed OOD guard LR", "source_rich 260D", "fixed OOD-benign guarded few-shot adapter", "source_rich is useful but not the stable protagonist."),
        ("Phase 4: guarded deployment adaptation", "original100_plus_source_rich_fixed_guard_lr", "original100 + source_rich fixed OOD guard LR", "original100 + source_rich 260D", "fixed OOD-benign guarded few-shot adapter", "source_rich plus guard can be strong on paired seeds but is bounded by held-out seed behavior."),
    ]
    for phase, method_key, method_name, rep, adapter_role, conclusion in phase11_specs:
        for seed_group in ["main_paired_42_46", "heldout_support_47_51"]:
            for budget in [16, 32]:
                row = get_row(issue11, method=method_key, seed_group=seed_group, positive_budget=budget)
                if row is None:
                    missing_rows.append({"asset": f"{method_key} {seed_group} budget {budget}", "path": str(RUNS["issue11"]), "status": "missing", "note": "method row not found."})
                    continue
                add_timeline(
                    timeline_rows,
                    phase=phase,
                    method=method_name,
                    input_representation=rep,
                    base_detector_role="base detector remains parallel monitor; not replaced",
                    adapter_role=adapter_role,
                    setting="current low-OOD guarded protocol",
                    budget=budget,
                    seed_group=seed_group,
                    detection_mean=fnum(row.attack_detection_mean),
                    detection_min=fnum(row.attack_detection_min),
                    ood_alarm_mean=fnum(row.ood_alarm_mean),
                    ood_alarm_max=fnum(row.ood_alarm_max),
                    feasible_rate=fnum(row.feasible_rate),
                    main_conclusion=conclusion,
                    paper_role="timeline Phase 3/4 evidence",
                    claim_strength="A-level for fixed guard mechanism; bounded for representation superiority",
                    source_run_path=RUNS["issue11"],
                )

    # Phase 5: Transformer hidden integration check.
    issue12 = read_csv(RUNS["issue12"] / "method_comparison_summary.csv")
    phase12_specs = [
        ("transformer_hidden_fixed_guard_lr", "Transformer hidden-only fixed guard LR", "Transformer outputLayer hidden", "hidden-only remains insufficient"),
        ("original100_plus_transformer_hidden_fixed_guard_lr", "original100 + Transformer hidden fixed guard LR", "original100 + Transformer hidden", "base-detector hidden integration is feasible but not a stable main gain over original100 fixed guard"),
    ]
    for method_key, method_name, rep, conclusion in phase12_specs:
        for seed_group in ["main_paired_42_46", "heldout_support_47_51"]:
            for budget in [16, 32]:
                row = get_row(issue12, method=method_key, seed_group=seed_group, positive_budget=budget)
                if row is None:
                    missing_rows.append({"asset": f"{method_key} {seed_group} budget {budget}", "path": str(RUNS["issue12"]), "status": "missing", "note": "method row not found."})
                    continue
                add_timeline(
                    timeline_rows,
                    phase="Phase 5: base-detector representation integration check",
                    method=method_name,
                    input_representation=rep,
                    base_detector_role="Transformer hidden representation provider candidate",
                    adapter_role="fixed OOD-benign guarded few-shot adapter",
                    setting="current low-OOD guarded protocol",
                    budget=budget,
                    seed_group=seed_group,
                    detection_mean=fnum(row.attack_detection_mean),
                    detection_min=fnum(row.attack_detection_min),
                    ood_alarm_mean=fnum(row.ood_alarm_mean),
                    ood_alarm_max=fnum(row.ood_alarm_max),
                    feasible_rate=fnum(row.feasible_rate),
                    main_conclusion=conclusion,
                    paper_role="B-level representation integration evidence",
                    claim_strength="B-level feasible integration; not main-gain proof",
                    source_run_path=RUNS["issue12"],
                )

    timeline = pd.DataFrame(timeline_rows)
    timeline.to_csv(OUT / "timeline_summary_table.csv", index=False)

    missing = pd.DataFrame(missing_rows or [{"asset": "none", "path": "NA", "status": "none", "note": "No key baseline directories or rows were missing for issue13 evidence pack."}])
    missing.to_csv(OUT / "missing_baseline_report.csv", index=False)

    system_role_rows = [
        {
            "component": "dA / Transformer",
            "role": "cold-start detector; ordinary anomaly model; low-OOD collapse diagnostic baseline; background generic anomaly monitor; optional representation provider",
            "not_role": "not fully replaced by GDA-minimal",
        },
        {
            "component": "GDA-minimal",
            "role": "deployment-stage few-shot adapter activated after low-OOD degradation evidence and high-purity attack supports are available",
            "not_role": "not active as the primary alerting model at cold start",
        },
        {
            "component": "fixed OOD guard",
            "role": "suppresses OOD benign high-score tail and improves low-alarm feasibility",
            "not_role": "not a searched global optimum; current fixed mechanism only",
        },
        {
            "component": "source_rich",
            "role": "optional representation signal and auditability asset",
            "not_role": "not a stable universal replacement for original100",
        },
        {
            "component": "Transformer hidden",
            "role": "base-detector representation integration evidence",
            "not_role": "not currently the strongest improvement source",
        },
        {
            "component": "review queue",
            "role": "handles base-high / GDA-low conflicts, protects against unseen anomalies, and motivates issue14 arbitration",
            "not_role": "not yet experimentally validated in issue13",
        },
    ]
    write_md(
        OUT / "system_role_table.md",
        "# System Role Table\n\n" + md_table(system_role_rows, ["component", "role", "not_role"]),
    )

    write_md(
        OUT / "activation_rule_draft.md",
        """
# Activation Rule Draft

GDA-minimal is not active as the primary alerting model during cold start. It is activated only when:

1. A base detector such as dA or Transformer is already deployed.
2. Benign OOD traffic or environment shift is observed.
3. The base detector shows low-OOD working-point degradation under the target alert budget.
4. A small set of high-purity confirmed attack samples becomes available.
5. ID benign and OOD benign calibration/validation samples are available for guarded thresholding.
6. Support provenance and threshold provenance checks pass.

After activation:

- The base detector continues running as a cold-start and generic anomaly monitor.
- GDA-minimal controls attack-oriented high-priority alerts under the low-OOD alarm constraint.
- Base-only high samples are routed to review, not suppressed.
- GDA-only high samples become GDA-driven high-priority alerts.
- Both-high samples become the strongest high-priority alerts.
- Both-low samples remain low-priority/background.

This is a proposed deployment rule, not a completed arbitration experiment.
""",
    )

    write_md(
        OUT / "arbitration_matrix_draft.md",
        """
# Arbitration Matrix Draft

Definitions:

- `base_high = base_score >= base_threshold`
- `gda_high = gda_score >= gda_guarded_threshold`

| base_high | gda_high | output |
|---|---|---|
| false | false | low_priority_or_background |
| true | true | high_priority_alert |
| false | true | GDA_driven_high_priority_alert |
| true | false | needs_review |

Issue14 should compare:

1. base-only
2. GDA-only
3. OR policy
4. AND policy
5. mode-gated arbitration

Issue13 only defines these policies. It does not validate arbitration performance.
""",
    )

    write_md(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

Allowed:

- GDA-minimal is a deployment-stage adapter.
- Fixed OOD guard is validated as a stable mechanism under the current low-OOD protocol.
- The base detector remains necessary for cold-start and generic anomaly monitoring.
- Transformer hidden integration is feasible but not yet a stable improvement source over original100 fixed guard.
- source_rich is useful but not the stable main claim.

Forbidden:

- GDA replaces the base detector once OOD appears.
- Full GDA is completed.
- The detector-agnostic framework is proven.
- source_rich is consistently superior to original100.
- Transformer hidden consistently improves over original100 fixed guard.
- A-zone innovation is fully complete.
""",
    )

    write_md(
        OUT / "evidence_map.md",
        """
# Evidence Map

## A-level evidence

- Fixed OOD guard mechanism: issue10/issue11 show lower OOD alarm and improved feasibility without major detection loss.
- original100 fixed guard as current stable GDA-minimal: issue11 gives main and held-out support seed evidence.
- Support and threshold provenance cleanliness: support IDs and threshold provenance pass in issue11/issue12.

## B-level evidence

- source_rich is useful but unstable: source_rich can improve or complement detection, but held-out seed evidence limits universal claims.
- Transformer hidden integration is feasible: issue12 recovers current-protocol hidden cache and shows original100+hidden fixed guard can remain feasible, but it does not clearly beat original100 fixed guard on held-out seeds.

## C-level / negative evidence

- Scalar score fusion is insufficient: dA and Transformer score-only adapters fail; original100+scalar score does not materially improve over original100-only.
- Hidden-only failure: Transformer hidden alone remains low-detection and high-OOD-alarm.
- Detector-agnostic adaptation is not yet proven.

## Missing evidence

- Arbitration matrix experiment.
- Harder holdout or second-environment validation.
- Upgraded adapter beyond LR.
- External validation.
""",
    )

    write_md(
        OUT / "recommended_next_action.md",
        """
# Recommended Next Action

Issue13 successfully organizes the deployment timeline and activation rule. The next experimental step should be:

`issue14_arbitration_matrix_experiment_2026-05-15`

Compare:

- base-only
- GDA-only
- OR policy
- AND policy
- mode-gated arbitration

Primary objective:

- quantify attack detection,
- OOD alarm,
- and review volume.

If issue14 is too broad, first implement a small feasibility inventory using existing base scores and GDA-minimal scores. Do not claim arbitration is validated until the policy-level experiment is run.
""",
    )

    risk_rows = [
        {"risk_name": "timeline overclaim", "severity": "high", "reason": "Issue13 is evidence organization, not a new validated system experiment.", "mitigation": "Use proposed activation rule and draft arbitration language."},
        {"risk_name": "GDA-minimal confused with full GDA", "severity": "high", "reason": "Current validated mechanism is fixed-guard LR.", "mitigation": "Define GDA-minimal explicitly as original100 + fixed OOD guard + few-shot LR."},
        {"risk_name": "base detector replacement framing", "severity": "high", "reason": "Base detectors remain useful for cold-start and generic anomaly monitoring.", "mitigation": "State that GDA-minimal runs alongside base detector."},
        {"risk_name": "source_rich overclaim", "severity": "medium", "reason": "source_rich is useful but not stable over original100 held-out seeds.", "mitigation": "Keep source_rich as optional representation/auditability evidence."},
        {"risk_name": "Transformer hidden overclaim", "severity": "medium", "reason": "hidden integration feasible but not stable main-gain source.", "mitigation": "Use B-level evidence wording."},
        {"risk_name": "arbitration not yet validated", "severity": "medium", "reason": "Review queue and arbitration matrix are only specified in issue13.", "mitigation": "Move policy comparison to issue14."},
    ]
    pd.DataFrame(risk_rows).to_csv(OUT / "risk_register.csv", index=False)

    write_md(
        OUT / "doc_update_patch_suggestion.md",
        """
# Mainline Docs Patch Suggestion

No mainline docs were edited in this run. If desired, append the following short strategy note to `runs/mainline_docs/mainline_experiment_map.md` and `runs/mainline_docs/mainline_handoff.md`.

## 2026-05-15 Strategy Update: Deployment Timeline and Activation Rule

Issue13 organizes the current evidence into a deployment timeline:

1. dA and Transformer remain cold-start/base detectors in ordinary normal-vs-attack settings.
2. Under current low-OOD guarded evaluation, base scalar scores show working-point collapse.
3. Scalar score-level few-shot fusion is insufficient.
4. The current stable deployment-stage adapter is GDA-minimal: original100 representation + fixed OOD-benign guard + few-shot LR.
5. source_rich and Transformer hidden provide representation-level signals, but neither is yet a stable primary source of gain over original100 fixed guard.
6. The next required experiment is issue14 arbitration: base-only, GDA-only, OR, AND, and mode-gated review policy.

This update does not change the manuscript and does not claim full GDA or detector-agnostic adaptation is proven.
""",
    )

    # Summary.
    strongest = issue11[
        (issue11["method"] == "original100_fixed_guard_lr")
        & (issue11["seed_group"] == "heldout_support_47_51")
        & (issue11["positive_budget"] == 32)
    ]
    strongest_note = ""
    if not strongest.empty:
        r = strongest.iloc[0]
        strongest_note = (
            f"Current stable method: original100 fixed guard LR 32-shot held-out seeds, "
            f"detection mean {fmt(fnum(r.attack_detection_mean))}, OOD alarm mean/max "
            f"{fmt(fnum(r.ood_alarm_mean))}/{fmt(fnum(r.ood_alarm_max))}, feasible {fmt(fnum(r.feasible_rate))}."
        )

    write_md(
        OUT / "summary.md",
        f"""
# Issue13 Deployment Timeline Activation Evidence Pack Summary

## 1. Purpose

This pack organizes existing evidence into a deployment timeline and activation rule. It does not train any model, rerun experiments, modify prior results, or edit the manuscript.

## 2. Timeline status

The timeline was generated successfully from existing CSV/JSON/MD assets. Key phases are:

- Phase 0: ordinary cold-start normal-vs-attack sanity.
- Phase 1: low-OOD working-point collapse before adaptation.
- Phase 2: scalar score-level adaptation attempts.
- Phase 3: few-shot minimal target-alignment adapter.
- Phase 4: guarded deployment adaptation.
- Phase 5: base-detector representation integration check.

## 3. Current stable method

{strongest_note}

For main-paper framing, this should be called `GDA-minimal` only in the limited sense of original100 representation + fixed OOD-benign guard + few-shot LR adapter. It is not full neural GDA.

## 4. Activation rule

GDA-minimal activates after:

1. base detector deployment,
2. observed benign OOD/environment shift,
3. low-OOD working-point degradation,
4. available high-purity confirmed attack supports,
5. available ID/OOD benign calibration/validation data,
6. passed support and threshold provenance checks.

The base detector continues running after activation; it is not replaced.

## 5. Missing baselines

See `missing_baseline_report.csv`. Missing rows are not fabricated.

## 6. Next step

Recommended next step: `issue14_arbitration_matrix_experiment_2026-05-15`, comparing base-only, GDA-only, OR, AND, and mode-gated arbitration by attack detection, OOD alarm, and review volume.

## 7. Safety

- Manuscript modified: False.
- Mainline docs modified: False.
- Existing experimental numbers modified: False.
- New model training: False.
- Full GDA claim introduced: False.
""",
    )

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file():
            manifest_rows.append({"file": str(path), "role": path.name})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)

    write_md(
        OUT / "run_metadata.json",
        json.dumps(
            {
                "run_tag": "issue13_deployment_timeline_activation_evidence_pack_2026-05-15",
                "created_at_local": datetime.now().isoformat(timespec="seconds"),
                "training_performed": False,
                "manuscript_modified": False,
                "mainline_docs_modified": False,
                "source_runs": {k: str(v) for k, v in RUNS.items()},
            },
            indent=2,
            ensure_ascii=False,
        ),
    )


if __name__ == "__main__":
    main()
