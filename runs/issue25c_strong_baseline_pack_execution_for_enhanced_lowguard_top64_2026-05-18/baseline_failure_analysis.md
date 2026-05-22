# Baseline Failure Analysis

## Baselines Over OOD Budget

See `locked_bins_baseline_summary.csv` for `locked_ood_alarm_max`. Any method with OOD max above 0.01 is not deployable under the official low-alert budget.

## Baselines That Threaten Main Method

Strongest feasible method: `M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR`.

Baseline fully dominates Enhanced LOW-GUARD+ under locked mean/min/OOD criteria: `False`.

## Complex Baselines

Complex baselines are interpreted by low-alert deployment metrics, not only AUC. A method that improves AUC but worsens OOD alarm or locked min detection does not replace the main method.

## Not-Run Baselines

LOF, full_source_rich variants, RoSAS-like, and large neural / continual learning baselines remain optional or design-only according to issue25b. They are not reported as completed experiments.
