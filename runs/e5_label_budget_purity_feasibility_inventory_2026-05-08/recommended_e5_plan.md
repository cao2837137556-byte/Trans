# Recommended E5 Plan

## Decision

E5 is worth opening, but only as a bounded sensitivity package. It should not change the paper center, add a new method, or become a broad model-comparison benchmark.

Recommended decision:

`start_minimal_e5_after_user_approval`

## E5-A: Label-Budget Sensitivity

### Main-text design

- Representation: `original100`
- Budgets: `4, 8, 16, 32, 64`
- Threshold policy: `guarded_id_calib_and_ood_val_target1pct`
- Seeds: `42, 43, 44, 45, 46`
- Model: same L2 LogisticRegression head
- Negative labels: ID benign + OOD benign
- Positive labels: stage2 high-purity attack support
- Final OOD eval and attack eval: never used for threshold selection

Expected outputs:

- `budget_sensitivity_results.csv`
- `budget_sensitivity_summary.csv`
- `selected_support_ids_full.csv`
- `budget_detection_curve.png/pdf`
- `budget_ood_alarm_curve.png/pdf`
- `summary.md`

Paper role:

- Main text compact table or figure.
- Appendix seed-level details.

Interpretation boundary:

- Supports that 16/32-shot are not arbitrary single-budget choices.
- Does not prove cross-dataset generalization.
- Does not require 64-shot to be the recommended deployment point.

## E5-B: Label-Purity / Positive-Contamination Sensitivity

### Main or appendix design

- Representation: `original100`
- Budgets: `16, 32`
- Contamination rates: `0%, 10%, 25%, 50%`
- Contamination source: OOD benign
- Threshold policy: `guarded_id_calib_and_ood_val_target1pct`
- Seeds: `42, 43, 44, 45, 46`
- Model: same L2 LogisticRegression head

Implementation rule:

- Replace the selected high-purity attack support positives with OOD benign samples at the specified contamination ratio.
- Keep training labels as positive for the contaminated support set only for stress testing.
- Log both the original attack support IDs and replacement OOD benign IDs.
- Do not sample contaminants from final OOD eval.
- Do not use attack eval or final OOD eval for threshold selection.

Expected outputs:

- `purity_sensitivity_results.csv`
- `purity_sensitivity_summary.csv`
- `contaminated_support_provenance.csv`
- `purity_degradation_curve.png/pdf`
- `summary.md`

Paper role:

- Main text if the result is clean and compact.
- Appendix if curves are noisy or space is limited.

Interpretation boundary:

- This is a controllable positive-purity stress test.
- It is not a complete model of real SOC labeling noise.
- It should be used to quantify the boundary of the high-purity-positive assumption.

## Source-Rich Policy

Source_rich is not required for E5.

Recommended handling:

- Do not include source_rich in the E5 main run.
- If cost is low, reuse existing v7.2 16/32/64 rows as appendix context.
- Do not run source_rich contamination sensitivity unless original100 E5-B is already clean and there is a specific paper need.

## Fixed-Threshold Policy

Guarded is the E5 main policy.

Recommended handling:

- Main text: guarded only.
- Appendix: fixed ID q99 only if it adds clarity without table explosion.

## Seed Policy

Use seeds `42,43,44,45,46`.

Do not expand to 10 seeds by default. Add 10 seeds only if:

- 4-shot or contamination curves are too noisy to interpret; or
- a reviewer-facing robustness argument explicitly needs a wider seed estimate.

## Workload

Estimated workload:

- E5-A original100: low.
- E5-B original100 OOD contamination: medium.
- Source_rich appendix: low if reusing existing 16/32/64 rows; medium if adding 4/8.

## Go / No-Go Conditions

Proceed only if the formal E5 run will also generate:

- support ID provenance for every budget and seed;
- contamination provenance for every contaminated support set;
- threshold provenance inherited from E3;
- paper-facing summary with clear boundary language.

Do not proceed if:

- the contamination source cannot be kept disjoint from final OOD eval;
- scripts would need to alter the current split or threshold definition;
- the plan expands into a broad benchmark or source_rich replacement story.
