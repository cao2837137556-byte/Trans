# Issue16c Failure Analysis Summary

## Read Status

Issue16b was successfully read. No manuscript or historical result file was modified.

## Main Failure Type

The leading diagnosis is:

- T1 attack representation shift,
- T5 feature/domain shift.

T2 support mismatch remains a plausible repair target, but the nearest-support-distance proxy does not prove it as the dominant cause. T3 guard over-conservatism is not the leading explanation because plain LR is also weak on `holdout_bin_2`.

## Plain LR vs Fixed Guard

Fixed guard lowers OOD high alarm but does not materially improve detection. Plain LR is also feasible and weak on `holdout_bin_2`, so the failure is not caused mainly by the OOD guard.

## Support Similarity

Support-to-holdout distance diagnostics were generated in `support_similarity_summary.csv` and `support_similarity_by_seed.csv`. They do not by themselves prove support mismatch as the dominant cause, but they provide the audit basis for a leakage-safe support diversity repair.

## Feature Drift

Feature drift diagnostics were generated in `feature_drift_summary.csv` and `top_shifted_features.csv`. `holdout_bin_2` should be treated as an attack-window shift, not a low-OOD alarm-control failure.

## Threshold Diagnosis

OOD high alarm remains below 1%, so the main failure is attack-side missed detection. OOD target curves were not computed because issue16b did not save row-level score arrays, and issue16c is not allowed to retrain models.

## Recommended Repair

First choice: `support_diversity_selection`.

This is a minimal mechanism test, not a claim that support mismatch is already proven. Do not immediately upgrade LR to MLP/prototype/full neural GDA. The next experiment should test whether better train-pool support coverage repairs `holdout_bin_2` without loosening the low-alert constraint.
