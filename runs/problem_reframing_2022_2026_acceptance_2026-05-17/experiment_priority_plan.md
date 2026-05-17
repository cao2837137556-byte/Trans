# Experiment Priority Plan

Every future experiment must pass the claim gate and reviewer gate before execution.

## S-level: formal harder holdout validation

- Purpose: Test whether LOW-GUARD-minimal survives harder cross-window evaluation.
- Target reviewer attack: single split / cherry-picked primary split
- Required inputs: v7.4 hard-holdout features, labels, support/eval manifests
- Output files: method_comparison_summary.csv; support_id_provenance.csv; threshold_provenance.csv
- Positive interpretation: Mechanism transfers to a harder holdout under fixed config.
- Negative interpretation: Current method is primary-split limited; keep as limitation or pivot to protocol paper.
- Stopping rule: If fixed guard fails on two pre-registered holdouts, stop adapter upgrade and analyze failure.

## S-level: few-shot anomaly baseline comparison

- Purpose: Defend against existing DevNet / Deep SAD / RoSAS-like few-shot anomaly methods.
- Target reviewer attack: few-shot anomaly detection already exists
- Required inputs: same low-OOD split, same supports, same threshold protocol
- Output files: baseline_comparison.csv; protocol.md; threshold_provenance.csv
- Positive interpretation: LOW-GUARD problem/protocol and fixed guard are competitive under fair baselines.
- Negative interpretation: Reframe as problem/protocol contribution or adopt stronger baseline as implementation.
- Stopping rule: If baselines dominate under clean protocol, do not claim method superiority.

## S-level: OOD target sensitivity 0.5 / 1 / 2

- Purpose: Show the mechanism is not tuned only to 1 percent OOD alarm.
- Target reviewer attack: OOD budget is arbitrary
- Required inputs: current fixed-config score/provenance or rerun with pre-registered budgets
- Output files: ood_budget_sensitivity.csv; figures; summary.md
- Positive interpretation: LOW-GUARD degrades smoothly across operating budgets.
- Negative interpretation: Claim only applies to the 1 percent low-alert point.
- Stopping rule: If only one budget works, do not broaden operating-region claim.

## S-level: shot sensitivity 8 / 16 / 32 / 64

- Purpose: Clarify label-budget boundary for LOW-GUARD-minimal.
- Target reviewer attack: chosen support budget is arbitrary
- Required inputs: same split, deterministic support sampling, full provenance
- Output files: shot_sensitivity_table.csv; seed_level_results.csv; support_id_provenance.csv
- Positive interpretation: Recovery is not tied to a single lucky positive budget.
- Negative interpretation: Method requires a narrower label-budget condition.
- Stopping rule: If low budgets fail, report boundary; do not chase support choices.

## S-level: threshold/provenance audit preserved

- Purpose: Keep leakage defense intact for every new experiment.
- Target reviewer attack: threshold or support leakage
- Required inputs: split manifest, support IDs, threshold source records
- Output files: support_id_provenance.csv; threshold_provenance.csv; audit_summary.md
- Positive interpretation: Protocol is auditable.
- Negative interpretation: Do not use the result as paper evidence.
- Stopping rule: Any leakage or missing provenance blocks claim use.

## A-level: second environment pilot

- Purpose: Probe external validity beyond the current capture.
- Target reviewer attack: single dataset
- Required inputs: external role manifest, comparable features, row IDs
- Output files: second_env_protocol.md; result_summary.csv; risk_register.csv
- Positive interpretation: External pilot supports generality cautiously.
- Negative interpretation: External validity remains limitation; analyze mismatch.
- Stopping rule: If role manifest is dirty, stop before model runs.

## A-level: modern unsupervised baselines

- Purpose: Show low-OOD collapse is not a weak dA-only artifact.
- Target reviewer attack: old baseline
- Required inputs: same low-OOD split and threshold protocol
- Output files: modern_baseline_table.csv; cost_summary.csv
- Positive interpretation: Problem persists under stronger base detectors.
- Negative interpretation: If a baseline solves it, reposition LOW-GUARD as deployment adaptation baseline.
- Stopping rule: Do not expand baseline zoo after two strong representative baselines.

## B-level: adapter upgrade

- Purpose: Test margin-GDA / deviation-GDA / prototype-GDA only after S-level evidence.
- Target reviewer attack: LR too simple
- Required inputs: formal harder-holdout and baseline results
- Output files: adapter_ablation.csv; claim_boundary.md
- Positive interpretation: A stronger adapter improves beyond LOW-GUARD-minimal.
- Negative interpretation: Keep LOW-GUARD-minimal as the clean baseline.
- Stopping rule: If no stable gain over fixed guard in two runs, stop.

## C-level: more score-level fusion

- Purpose: Not recommended unless a new pre-registered reason exists.
- Target reviewer attack: none currently
- Required inputs: new score source with explicit hypothesis
- Output files: negative_record.md if attempted
- Positive interpretation: Only auxiliary unless it beats fixed guard.
- Negative interpretation: Confirms scalar score compression is insufficient.
- Stopping rule: Default stop.
