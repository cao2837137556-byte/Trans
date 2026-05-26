from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE25B = ROOT / "runs" / "issue25b_strong_baseline_protocol_and_fairness_design_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE26B = ROOT / "runs" / "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22"

PRIMARY_VERDICT = "deployment_protocol_plausible_needs_robustness_simulation"
SECONDARY_VERDICT = "lowguard_should_be_framed_as_guarded_adaptation_protocol"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    if columns is None:
        columns = []
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "NA") for key in columns})


def write_md(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def build_deployment_assumptions() -> list[dict[str, Any]]:
    rows = [
        {
            "assumption_id": "A01",
            "assumption_name": "high-purity attack supports",
            "description": "A small set of confirmed attack examples is available before adaptation.",
            "required_by_lowguard": "yes, positives for the guarded few-shot adapter",
            "realistic_source": "SOC tickets after analyst triage, incident response cases, red-team exercises, sandbox or honeypot captures",
            "confidence_level": "medium",
            "contamination_risk": "medium",
            "mitigation": "use only confirmed cases; keep eval traffic excluded; record support provenance; run support-noise simulation",
            "paper_claim_allowed": "assumes a small high-purity support set can be obtained in deployment workflows",
            "paper_claim_forbidden": "32 attack supports are always available or always clean",
        },
        {
            "assumption_id": "A02",
            "assumption_name": "analyst-confirmed attacks",
            "description": "Human analysts confirm selected alerts/incidents as attacks.",
            "required_by_lowguard": "yes, strongest support source",
            "realistic_source": "post-alert investigation, incident response, case management labels",
            "confidence_level": "high",
            "contamination_risk": "low_to_medium",
            "mitigation": "two-person review for support promotion; delayed labels; audit log; avoid using unresolved alerts",
            "paper_claim_allowed": "analyst confirmation is the safest operational support source",
            "paper_claim_forbidden": "all SOC labels are correct or immediate",
        },
        {
            "assumption_id": "A03",
            "assumption_name": "trusted-rule-confirmed attacks",
            "description": "High precision deterministic rules nominate support candidates.",
            "required_by_lowguard": "optional, support candidate source",
            "realistic_source": "signature alerts with strong IOCs, IDS rules with low historical false positive rate",
            "confidence_level": "medium",
            "contamination_risk": "medium",
            "mitigation": "use rules only as candidate filters; analyst confirmation preferred; compare with random and kcenter supports",
            "paper_claim_allowed": "trusted rules can reduce support acquisition cost",
            "paper_claim_forbidden": "rule-confirmed labels are equivalent to ground truth",
        },
        {
            "assumption_id": "A04",
            "assumption_name": "historical incident cases",
            "description": "Previously confirmed incidents provide support examples.",
            "required_by_lowguard": "yes or optional depending site maturity",
            "realistic_source": "archived incident cases and postmortem packet/flow windows",
            "confidence_level": "medium",
            "contamination_risk": "medium",
            "mitigation": "time-split incidents; avoid future leakage; simulate label delay and temporal shift",
            "paper_claim_allowed": "historical incidents are a plausible support source",
            "paper_claim_forbidden": "historical incidents cover all future attack shifts",
        },
        {
            "assumption_id": "A05",
            "assumption_name": "honeypot / sandbox / red-team attacks",
            "description": "Controlled attack-like traffic provides labeled positives.",
            "required_by_lowguard": "optional",
            "realistic_source": "red-team exercises, sandbox detonation, honeypot captures",
            "confidence_level": "medium",
            "contamination_risk": "low label risk; medium distribution mismatch risk",
            "mitigation": "treat as auxiliary supports; test source-specific support robustness; avoid overclaiming real-world coverage",
            "paper_claim_allowed": "controlled positives can be used as support candidates",
            "paper_claim_forbidden": "lab positives perfectly represent production attacks",
        },
        {
            "assumption_id": "A06",
            "assumption_name": "OOD benign guard from recent trusted normal traffic",
            "description": "Recent trusted benign OOD traffic constrains low-alert thresholding and training.",
            "required_by_lowguard": "yes, negative/guard data",
            "realistic_source": "quiet-period traffic, allowlisted maintenance windows, verified normal segments",
            "confidence_level": "medium",
            "contamination_risk": "medium",
            "mitigation": "quarantine recent traffic before promotion; scan with independent detectors; run OOD contamination simulation",
            "paper_claim_allowed": "LOW-GUARD assumes trusted benign-OOD guard samples",
            "paper_claim_forbidden": "OOD benign data is always clean",
        },
        {
            "assumption_id": "A07",
            "assumption_name": "OOD benign guard from analyst-confirmed false positives",
            "description": "False-positive alerts confirmed benign become hard benign guard examples.",
            "required_by_lowguard": "optional but useful",
            "realistic_source": "SOC false-positive closure labels",
            "confidence_level": "medium",
            "contamination_risk": "medium_to_high",
            "mitigation": "delay promotion; require closure reason; keep separate from final eval; simulate attack contamination",
            "paper_claim_allowed": "confirmed false positives can seed the OOD benign guard",
            "paper_claim_forbidden": "closed false positives are never attacks",
        },
        {
            "assumption_id": "A08",
            "assumption_name": "ID benign calibration set",
            "description": "Known in-distribution benign traffic is available for calibration.",
            "required_by_lowguard": "yes",
            "realistic_source": "deployment baseline period, asset onboarding windows",
            "confidence_level": "high",
            "contamination_risk": "low_to_medium",
            "mitigation": "baseline hygiene checks; remove known incidents; immutable calibration snapshot",
            "paper_claim_allowed": "ID calibration is required for guarded thresholding",
            "paper_claim_forbidden": "ID calibration is automatically clean in every site",
        },
        {
            "assumption_id": "A09",
            "assumption_name": "OOD validation set",
            "description": "A held-out benign-OOD validation slice is used to enforce the 1% alarm budget.",
            "required_by_lowguard": "yes",
            "realistic_source": "recent verified benign drift, false-positive closure set, shadow-mode benign review",
            "confidence_level": "medium",
            "contamination_risk": "medium",
            "mitigation": "validation-only use; no final eval reuse; contamination stress test",
            "paper_claim_allowed": "thresholds are calibrated using ID calibration + OOD validation only",
            "paper_claim_forbidden": "OOD validation labels are free or always perfect",
        },
        {
            "assumption_id": "A10",
            "assumption_name": "final OOD eval exclusion",
            "description": "Final OOD and attack eval are never used for threshold/support/model selection.",
            "required_by_lowguard": "yes, central leakage control",
            "realistic_source": "protocol rule, locked audit logs",
            "confidence_level": "high",
            "contamination_risk": "low if enforced",
            "mitigation": "immutable final eval; manifest audit; report-only rule",
            "paper_claim_allowed": "current evidence enforces final eval exclusion",
            "paper_claim_forbidden": "final eval can be reused for deployment tuning",
        },
        {
            "assumption_id": "A11",
            "assumption_name": "no autonomous self-training",
            "description": "LOW-GUARD does not automatically train on its own alerts.",
            "required_by_lowguard": "yes, to prevent feedback contamination",
            "realistic_source": "offline gated update policy",
            "confidence_level": "high",
            "contamination_risk": "high if violated",
            "mitigation": "shadow/canary mode; human-confirmed promotion only; rollback on alarm drift",
            "paper_claim_allowed": "fully autonomous online self-training is outside scope",
            "paper_claim_forbidden": "LOW-GUARD safely self-trains from its own predictions",
        },
        {
            "assumption_id": "A12",
            "assumption_name": "periodic offline update",
            "description": "Model updates happen periodically after gated label/provenance checks.",
            "required_by_lowguard": "recommended",
            "realistic_source": "weekly/monthly SOC model review cycle",
            "confidence_level": "medium",
            "contamination_risk": "medium",
            "mitigation": "offline retraining; shadow validation; canary gate; rollback trigger",
            "paper_claim_allowed": "LOW-GUARD is compatible with periodic offline update",
            "paper_claim_forbidden": "continuous online adaptation has been validated",
        },
    ]
    return rows


def build_alert_budget() -> list[dict[str, Any]]:
    summary = read_csv(ISSUE25C / "locked_bins_baseline_summary.csv")
    wanted = [
        "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR",
        "M0_V1_original100_fixed_guard_LR",
        "M8_DevNet_like_MLP_top64",
        "M4_top64_random32_fixed_guard_LR",
        "M1_V2_top32_fixed_guard_LR",
        "M7_HistGB_shallow_top64",
        "M5_Isolation_Forest_top64",
        "M6_OC_SVM_top64",
        "M9_DeepSAD_like_center_top64",
        "M3_top64_no_guard_LR",
    ]
    rows = []
    for method in wanted:
        row = summary[summary["method"].eq(method)] if not summary.empty and "method" in summary.columns else pd.DataFrame()
        if row.empty:
            rows.append(
                {
                    "method": method,
                    "locked_ood_alarm_max": "NA",
                    "alarms_per_10k_ood_events": "NA",
                    "alarms_per_100k_ood_events": "NA",
                    "feasible_under_1pct": "NA",
                    "deployment_interpretation": "missing from issue25c aggregate",
                }
            )
            continue
        r = row.iloc[0]
        alarm = float(r["locked_ood_alarm_max"])
        feasible = alarm <= 0.01
        if method == "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR":
            interp = "Within current locked protocol, stays well below the 1% low-alert budget while keeping strong detection."
        elif feasible:
            interp = "Within the alarm budget, but must be compared on detection and robustness; not automatically better."
        else:
            interp = "Exceeds the 1% low-alert budget in at least one locked bin; deployment-risky under the official constraint."
        rows.append(
            {
                "method": method,
                "locked_ood_alarm_max": f"{alarm:.6f}",
                "alarms_per_10k_ood_events": f"{alarm * 10000:.1f}",
                "alarms_per_100k_ood_events": f"{alarm * 100000:.1f}",
                "feasible_under_1pct": "yes" if feasible else "no",
                "deployment_interpretation": interp,
            }
        )
    return rows


def build_label_budget_plan() -> list[dict[str, Any]]:
    return [
        {
            "experiment_name": "shot_sensitivity_4_8_16_32_64",
            "purpose": "Test whether deployment assumption of 32 supports is fragile or label-efficient.",
            "required_inputs": "frozen top64 features, support pool, ID/OOD train/cal/val, locked bins",
            "protocol": "Run frozen LOW-GUARD with support counts 4/8/16/32/64; same threshold rule; final eval report-only.",
            "expected_runtime": "low_to_medium",
            "whether_slurm_needed": "no for local smoke; maybe no for full LR matrix",
            "risk": "support count sweep could be seen as tuning if final eval is used; pre-register counts",
            "priority": "P0",
            "go_no_go_condition": "Proceed if 8/16/32 show stable low-alert detection; stop/pivot if only 64 works.",
        },
        {
            "experiment_name": "support_noise_5pct_10pct",
            "purpose": "Simulate analyst/rule label noise in attack supports.",
            "required_inputs": "support pool plus controlled mislabeled benign injection candidates",
            "protocol": "Replace 5%/10% supports with benign samples before training; no final eval selection.",
            "expected_runtime": "low",
            "whether_slurm_needed": "no",
            "risk": "noise model may be simplistic",
            "priority": "P0",
            "go_no_go_condition": "Proceed if OOD alarm remains under budget and detection degrades gracefully.",
        },
        {
            "experiment_name": "ood_benign_contamination_1pct_5pct",
            "purpose": "Stress the OOD benign guard against attack contamination.",
            "required_inputs": "OOD train/val pools and held-out attack rows not used for eval selection",
            "protocol": "Inject 1%/5% attack rows into OOD_train or OOD_val only; record threshold shifts.",
            "expected_runtime": "low_to_medium",
            "whether_slurm_needed": "no for LR; maybe no for baseline pack",
            "risk": "must avoid using final attack eval for contamination selection",
            "priority": "P0",
            "go_no_go_condition": "Proceed if 1% contamination is robust; flag limitation if 5% breaks thresholding.",
        },
        {
            "experiment_name": "label_delay_earlier_support_later_eval",
            "purpose": "Model realistic delayed labels by using only earlier attack bins as supports.",
            "required_inputs": "bin-level support/eval manifests and preferably timestamp metadata",
            "protocol": "Supports from earlier bins; eval on later bins; threshold from ID/OOD validation only.",
            "expected_runtime": "medium",
            "whether_slurm_needed": "unknown until metadata recovered",
            "risk": "current issue26b metadata blocks clean temporal proof",
            "priority": "P1",
            "go_no_go_condition": "Proceed only after raw/bin-to-time provenance is sufficient.",
        },
        {
            "experiment_name": "support_source_kcenter_random_rulelike",
            "purpose": "Compare realistic support acquisition mechanisms.",
            "required_inputs": "attack train pool, kcenter support IDs, random seeds, proxy high-confidence rule score or margin",
            "protocol": "Compare kcenter vs random vs rule-like high-confidence selection under fixed budget.",
            "expected_runtime": "low",
            "whether_slurm_needed": "no",
            "risk": "rule-like proxy must be pre-registered and not use final eval",
            "priority": "P1",
            "go_no_go_condition": "Proceed if kcenter is not the only workable source; if not, narrow deployment claim.",
        },
        {
            "experiment_name": "one_shot_vs_periodic_update_simulation",
            "purpose": "Test whether periodic offline updates help or create instability.",
            "required_inputs": "time/bin manifests and staged support pools",
            "protocol": "Compare one-shot supports to periodically added confirmed supports; no autonomous self-training.",
            "expected_runtime": "medium",
            "whether_slurm_needed": "unknown; likely no for LR, yes if expanded baselines",
            "risk": "requires clean temporal/update ordering",
            "priority": "P2",
            "go_no_go_condition": "Run after label-delay split is clean.",
        },
        {
            "experiment_name": "shadow_mode_alarm_budget_evaluation",
            "purpose": "Translate scores into operational workload without changing alerting.",
            "required_inputs": "report-only scoring stream, OOD/attack labels for offline audit",
            "protocol": "Score in shadow mode; compute alarm workload under frozen threshold; no production alerts.",
            "expected_runtime": "low_to_medium",
            "whether_slurm_needed": "no unless stream is large",
            "risk": "offline labels may lag; cannot claim live SOC deployment",
            "priority": "P1",
            "go_no_go_condition": "Proceed if alarm budget is stable under replay and rollback thresholds are clear.",
        },
    ]


def pipeline_design() -> str:
    stages = [
        ("Stage 0: cold-start base detector", "existing dA / base IDS / prior anomaly score", "initial alerts and candidate incidents", "SOC owner + model owner", "base detector scores must not use final eval", "high false positive drift", "alarm explosion or known incident leakage", "Base detector supplies candidates; LOW-GUARD is not a cold-start replacement."),
        ("Stage 1: high-purity support collection", "confirmed incidents, trusted rules, red-team/honeypot cases", "small support pool with provenance", "analyst or incident response lead", "support rows cannot overlap final attack eval", "mislabeled supports or biased attack family", "support provenance fails or support source not confirmed", "Assume small high-purity supports; do not claim labels are free."),
        ("Stage 2: benign-OOD guard collection", "recent trusted normal traffic and confirmed false positives", "OOD benign train/validation guard pool", "SOC analyst + data owner", "OOD guard cannot include final OOD eval", "attack contamination inside benign guard", "OOD validation alarm unstable or contamination detected", "OOD guard is trusted/validated benign drift, not arbitrary production traffic."),
        ("Stage 3: offline LOW-GUARD training", "frozen representation, support pool, ID/OOD benign train", "minimal guarded adapter instance", "model owner", "no final eval for representation/support/model choice", "training on unresolved alerts creates feedback", "provenance or contamination audit fails", "Training is offline and gated, not autonomous self-training."),
        ("Stage 4: validation-only thresholding", "ID calibration + OOD validation scores", "threshold under 1% OOD validation alarm", "model owner + reviewer", "final OOD/attack eval cannot set threshold", "OOD validation labels may be noisy", "OOD validation exceeds budget or labels untrusted", "Threshold is validation-calibrated under low-alert budget."),
        ("Stage 5: shadow mode", "frozen trained model and threshold", "score/alarm simulation without production alerts", "SOC operations", "shadow labels cannot be used to tune final threshold in the same evaluation", "operator feedback may bias later labels", "shadow workload exceeds budget", "Shadow mode estimates workload; it is not full deployment proof."),
        ("Stage 6: canary deployment", "shadow-passed model", "limited-scope production alerts", "SOC lead + model owner", "canary results should be logged separately", "localized drift or user impact", "alarm rate above 1% target, analyst overload, confirmed false-positive burst", "Canary is a cautious deployment gate."),
        ("Stage 7: rollback trigger", "live/near-live workload and confirmed label drift metrics", "rollback or freeze decision", "SOC incident commander", "rollback criteria must be pre-registered", "delayed labels can hide failures", "OOD alarm breach, support contamination, or incident miss audit", "LOW-GUARD needs rollback controls."),
        ("Stage 8: periodic update", "new confirmed supports and benign guard after quarantine", "new offline candidate version", "change advisory / model governance", "do not self-train from predictions", "feedback contamination from previous model alerts", "update fails shadow/canary or provenance audit", "Periodic offline updates are plausible but need robustness simulation."),
    ]
    body = ["# Deployment Pipeline Design"]
    for name, inp, out, verifier, leak, contam, rollback, paper in stages:
        body.append(f"## {name}\n")
        body.append(f"- input: {inp}")
        body.append(f"- output: {out}")
        body.append(f"- who verifies it: {verifier}")
        body.append(f"- leakage risk: {leak}")
        body.append(f"- contamination risk: {contam}")
        body.append(f"- rollback condition: {rollback}")
        body.append(f"- how to express it in paper: {paper}\n")
    return "\n".join(body)


def lr_vs_framework_md() -> str:
    return """# LR vs Framework Positioning

## Is LR the core contribution?

No. LR is the current minimal deployable instantiation. The core contribution should be framed as a low-alert guarded few-shot adaptation protocol: OOD-safe representation selection, confirmed attack support coreset, OOD benign guard, and validation-calibrated thresholding.

## Should LOW-GUARD be written as framework/protocol?

Yes. The paper should present LOW-GUARD as a protocol for adapting an IDS under benign-OOD drift and low-alert constraints. The LR head is attractive because it is transparent, cheap, stable, and easy to audit.

## If Guarded DevNet-like or Guarded HistGB becomes stronger, does the main story survive?

Yes, if the protocol framing is used. A stronger guarded adapter would become another LOW-GUARD instance. The current claim should not be that LR is universally optimal; it should be that the guarded adaptation protocol is effective and the LR instance is a strong minimal baseline.

## How to write LR as a minimal deployable instantiation?

Write it as: `LOW-GUARD-LR`, a lightweight linear adapter trained from confirmed attack supports and benign guard samples, with threshold selected only from ID calibration + OOD validation.

## How to avoid the attack "it is just Logistic Regression"?

- Emphasize the deployment problem: low-alert IDS under benign-OOD drift.
- Emphasize the protocol: support provenance, OOD guard, final eval exclusion, low-alert threshold.
- Show strong baselines: DevNet-like and random32 approach detection but exceed the 1% OOD alarm budget.
- Keep LR's role honest: simple, auditable, and not claimed as universal optimum.

## External baseline vs guarded baseline vs LOW-GUARD instance

- External baseline: method family tested under fair input/label budget rules, e.g. DevNet-like or DeepSAD-like.
- Guarded baseline: a baseline wrapped with the same ID/OOD validation threshold protocol.
- LOW-GUARD instance: a method that follows the full protocol, including support provenance, benign-OOD guard, low-alert validation threshold, and deployment update constraints.
"""


def reviewer_defense_md() -> str:
    return """# Reviewer Defense: Deployment Protocol

## Q1: How do you obtain 32 attack samples in reality?

From analyst-confirmed incidents, high-confidence IDS rules after review, historical cases, red-team exercises, honeypots, or sandbox-confirmed samples. We do not claim they are free or always available; issue27b should test smaller budgets.

## Q2: Can the OOD benign guard be attack-contaminated?

Yes. That is a core risk. The protocol requires quarantine, analyst confirmation for false-positive promotion, and OOD-contamination simulations before strong deployment claims.

## Q3: Does the training protocol create a feedback loop?

Not in the current scope. LOW-GUARD should be offline and gated. It must not self-train from its own alerts without human confirmation and provenance checks.

## Q4: Is the method only offline?

The current evidence supports offline training plus shadow/canary deployment. Fully autonomous online learning is not validated.

## Q5: Why not directly use DevNet / DeepSAD?

Issue25c tested DevNet-like and DeepSAD-like baselines under a fair low-alert protocol. DevNet-like was competitive in detection but exceeded the 1% OOD alarm budget; DeepSAD-like did not threaten the main method.

## Q6: Why is LR not a weakness?

LR is the minimal auditable adapter. The claim is not "LR is the best possible neural detector"; the claim is that guarded few-shot adaptation under a low-alert protocol works and can be implemented with a simple transparent head.

## Q7: Does OOD alarm <=1% have deployment meaning?

Yes. It bounds analyst workload. For example, 0.45% OOD alarm means about 45 alerts per 10k OOD events, while 1.04% means about 104 alerts per 10k and breaches the official budget.

## Q8: If temporal metadata is missing, are deployment claims too strong?

Temporal-generalization claims would be too strong. Deployment-protocol claims can be made as assumptions and controls, but formal temporal validation remains pending.

## Q9: If cross-dataset validation does not succeed, how can the paper write this?

As a within-dataset low-alert adaptation result with clear external-validity limits. Do not claim universal generalization; use second-environment results as boundary evidence or future work.

## Q10: How does the method go online, get monitored, and roll back?

Deploy through shadow mode, then canary. Roll back if OOD alarm exceeds budget, false positives spike, support contamination is discovered, or incident miss audit fails. Updates should be periodic and offline.
"""


def claim_update_md() -> str:
    return """# Claim Update After Issue27a

## Allowed

- LOW-GUARD is better framed as a guarded few-shot adaptation protocol rather than a standalone LR detector.
- The minimal LR head is a deployable instantiation of the protocol.
- The deployment setting assumes a small number of high-purity attack supports and trusted benign-OOD guard samples.
- Fully autonomous online self-training is outside the current scope.
- Deployment claims require support-noise, label-budget, OOD-contamination, label-delay, and update-simulation experiments.

## Not Allowed

- LOW-GUARD is fully deployable in all SOCs.
- 32 attack supports are always available.
- OOD benign labels are always clean.
- The method supports autonomous self-training.
- Temporal generalization is proven.
- Cross-dataset generalization is proven.
- LR is universally optimal.

## Recommended Wording

Use `LOW-GUARD-LR` for the current minimal instance and `LOW-GUARD protocol` for the broader contribution. Keep deployment claims conditional on trusted support/guard provenance and offline gated updates.
"""


def next_decision_md() -> str:
    return """# Issue27b Next Experiment Decision

## Recommended Next Step

`issue27b_deployment_robustness_simulation_for_lowguard_top64_2026-05-22`

## Why This Now

Issue25c already handled strong baselines, while issue26a/26b showed formal temporal validation is blocked by metadata. The most direct remaining reviewer attack is deployment realism: support availability, support noise, OOD benign contamination, label delay, and update safety.

## Why Not Adapter Failure Archaeology First

Adapter upgrades reopen model-search space and weaken the claim boundary. Current LOW-GUARD-LR already survives strong baselines under the locked protocol. Upgrade work should wait until deployment robustness reveals a concrete failure mode.

## Why Not Data-Scale / Cross-Dataset Rebuild First

External validity remains important, but issue27a is about deployment protocol. Cross-dataset work can proceed later as issue27/28, ideally with a new clean protocol. It should not be mixed into this deployment audit.

## Required Inputs

- Frozen selected_source_rich_top64 features.
- Existing kcenter32 support provenance and attack train pools.
- ID/OOD train/cal/validation slices.
- Locked bins 5/6/7/8 and consistency settings for report-only evaluation.
- Contamination candidates that do not overlap final eval.

## Slurm Need

Likely no for LR-only simulations. Slurm is only needed if the matrix expands to many neural baselines or large stream replay.

## Expected Paper Evidence

- Label-budget sensitivity table.
- Support-noise robustness table.
- OOD benign contamination sensitivity table.
- Label-delay / earlier-support-later-eval boundary if metadata permits.
- Shadow-mode workload interpretation under the 1% alarm budget.
"""


def risk_register() -> list[dict[str, Any]]:
    return [
        {"risk_name": "support availability risk", "severity": "high", "reason": "Some SOCs may not have 32 confirmed attack supports.", "mitigation": "Run 4/8/16/32/64 shot sensitivity."},
        {"risk_name": "support label noise risk", "severity": "high", "reason": "Analyst or rule labels can be wrong.", "mitigation": "Run 5%/10% support-noise simulation and require provenance."},
        {"risk_name": "OOD benign contamination risk", "severity": "high", "reason": "Attack traffic can hide inside recent benign/OOD guard samples.", "mitigation": "Run 1%/5% OOD contamination stress tests."},
        {"risk_name": "feedback contamination risk", "severity": "high", "reason": "Training on model-generated alerts can create self-confirming loops.", "mitigation": "No autonomous self-training; delayed human-confirmed promotion only."},
        {"risk_name": "final eval leakage risk", "severity": "high", "reason": "Deployment tuning could accidentally reuse report-only final eval.", "mitigation": "Keep immutable final eval and audit manifests."},
        {"risk_name": "temporal metadata gap", "severity": "medium", "reason": "issue26b did not recover raw timestamp/packet-order metadata.", "mitigation": "Avoid temporal claims until metadata or second environment is available."},
        {"risk_name": "LR overclaim risk", "severity": "medium", "reason": "Reviewers may attack the method as just Logistic Regression.", "mitigation": "Frame LR as minimal LOW-GUARD instance, not the entire contribution."},
        {"risk_name": "alert workload risk", "severity": "medium", "reason": "Methods near or above 1% OOD alarm can overload analysts.", "mitigation": "Report alarms per 10k/100k OOD events."},
        {"risk_name": "cross-site validity risk", "severity": "high", "reason": "Current positive evidence is within dataset.", "mitigation": "Keep second-environment work as separate future validation."},
        {"risk_name": "update instability risk", "severity": "medium", "reason": "Periodic updates may drift or amplify errors.", "mitigation": "Shadow/canary gates and rollback triggers."},
    ]


def summary_md(alert_rows: list[dict[str, Any]]) -> str:
    main_alarm = next((r for r in alert_rows if r["method"] == "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR"), {})
    return f"""# Issue27a Deployment Feasibility And Guarded Training Protocol Audit Summary

## Verdict

- primary_verdict: `{PRIMARY_VERDICT}`
- secondary_verdict: `{SECONDARY_VERDICT}`

## 1. Does LOW-GUARD's training protocol have deployment plausibility?

Yes, with constraints. The protocol is plausible if it is framed as offline, gated, few-shot adaptation using high-purity attack supports and trusted benign-OOD guard samples. It is not evidence of fully autonomous SOC deployment.

## 2. Credible sources of high-purity attack supports

- Analyst-confirmed incidents.
- Trusted-rule candidates after analyst confirmation.
- Historical incident cases.
- Honeypot / sandbox / red-team captures.

The strongest source is analyst-confirmed attacks. Rule-like or lab sources are useful but need contamination and distribution-shift caveats.

## 3. Credible sources of OOD benign guard samples

- Recent trusted normal traffic after quarantine.
- Analyst-confirmed false positives.
- Verified maintenance or benign drift windows.

These are plausible but not automatically clean. OOD benign contamination is a priority risk.

## 4. Main deployment risks

- Support labels may be unavailable or noisy.
- OOD benign guard may contain attacks.
- Model-generated alerts could contaminate future training if used without human confirmation.
- Temporal/external generalization is still not proven.

## 5. How to prevent feedback contamination

LOW-GUARD should not self-train from its own alerts. Updates should be offline, delayed, provenance-logged, and promoted only after shadow/canary checks.

## 6. LR positioning

LR should be written as `LOW-GUARD-LR`, the minimal deployable adapter. The main contribution is the guarded few-shot adaptation protocol, not LR as a universally optimal model.

## 7. Naming / positioning

Recommended wording: `LOW-GUARD protocol` for the framework and `LOW-GUARD-LR` for the current implementation.

## 8. Deployment claims allowed

- The protocol is deployment-plausible under explicit support/guard assumptions.
- Current locked results meet the 1% OOD alarm budget for the LOW-GUARD-LR instance.
- Main method locked OOD max is `{main_alarm.get("locked_ood_alarm_max", "NA")}`, about `{main_alarm.get("alarms_per_10k_ood_events", "NA")}` alerts per 10k OOD events.
- Final eval exclusion and validation-only thresholding are enforced in inspected artifacts.

## 9. Deployment claims not allowed

- Fully deployable in all SOCs.
- 32 supports are always available.
- OOD benign labels are always clean.
- Autonomous online self-training is validated.
- Temporal or cross-dataset generalization is proven.

## 10. Next issue27b

Run deployment robustness simulation: shot sensitivity, support-noise, OOD-contamination, support-source comparison, label-delay if metadata permits, and shadow-mode workload evaluation.

## 11. Slurm

Not needed for issue27a. Likely not needed for LR-only issue27b simulations; use Slurm only for large stream replay or neural baseline expansion.
"""


def create_outputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    deployment_rows = build_deployment_assumptions()
    alert_rows = build_alert_budget()
    label_rows = build_label_budget_plan()
    risks = risk_register()

    write_csv(OUT / "deployment_assumption_inventory.csv", deployment_rows)
    write_md(OUT / "deployment_pipeline_design.md", pipeline_design())
    write_csv(OUT / "alert_budget_interpretation.csv", alert_rows)
    write_csv(OUT / "label_budget_robustness_plan.csv", label_rows)
    write_md(OUT / "lr_vs_framework_positioning.md", lr_vs_framework_md())
    write_md(OUT / "reviewer_defense_deployment_protocol.md", reviewer_defense_md())
    write_md(OUT / "issue27b_next_experiment_decision.md", next_decision_md())
    write_md(OUT / "claim_update_after_issue27a.md", claim_update_md())
    write_csv(OUT / "risk_register_deployment_protocol.csv", risks)
    write_md(OUT / "summary.md", summary_md(alert_rows))

    config = {
        "run": "issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "task_type": "deployment_feasibility_and_guarded_training_protocol_audit",
        "primary_verdict": PRIMARY_VERDICT,
        "secondary_verdict": SECONDARY_VERDICT,
        "model_training": False,
        "cross_dataset_validation": False,
        "temporal_validation": False,
        "main_method_changed": False,
        "topk_changed": False,
        "support_budget_changed": False,
        "adapter_changed": False,
        "threshold_protocol_changed": False,
        "manuscript_changed": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    run_spec = {
        "issue": "issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22",
        "question": "Is LOW-GUARD better framed as a deployable guarded few-shot adaptation protocol, and what deployment assumptions need evidence?",
        "serves_claim": "LOW-GUARD-LR is a minimal deployable instance under explicit support/guard assumptions, not a universal LR detector claim.",
        "reviewer_attacks_defended": [
            "where do 32 attack supports come from",
            "OOD benign guard contamination",
            "feedback contamination",
            "just Logistic Regression",
            "low-alert budget operational meaning",
        ],
        "success_interpretation": "Protocol is plausible but needs robustness simulations.",
        "failure_interpretation": "Deployment assumptions are too strong and claims must be reframed.",
        "paper_destination": "method/protocol framing and reviewer-defense appendix; not a new performance result",
        "final_eval_leakage_policy": "final OOD and attack eval remain report-only",
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")

    write_md(
        OUT / "command.txt",
        """git branch --show-current
git status --short
Get-Content issue25c summary/recommended/by_seed/summary CSVs
Get-Content issue25b summary and threshold protocol
Get-Content issue23 locked validation asset report
Get-Content issue26b summary
Get-Content mainline handoff and experiment map
python runs/issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22/generate_issue27a_outputs.py
apply_patch runs/mainline_docs/mainline_handoff.md issue27a append
apply_patch runs/mainline_docs/mainline_experiment_map.md issue27a append
""",
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows, ["file", "size_bytes"])


if __name__ == "__main__":
    create_outputs()
