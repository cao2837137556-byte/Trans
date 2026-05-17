# Failure Analysis

This file records the issue16b boundary analysis. It should be read together with `method_comparison_summary.csv` and `fixed_guard_vs_plain_harder_holdout.csv`.

## Observed Verdict

- Verdict: `mixed_or_negative`.
- Reason: Fixed guard keeps OOD high alarm feasible, but at least one pre-registered harder holdout has weak 32-shot attack detection (minimum mean=0.222700).
- Weak holdouts: holdout_bin_2.
- Minimum fixed-guard 32-shot detection mean: 0.222700.
- Minimum fixed-guard 32-shot per-seed detection: 0.199555.
- Maximum fixed-guard 32-shot OOD high alarm: 0.003000.

## Failure Mode

- Primary weakness: attack detection drops sharply on `holdout_bin_2`, especially for held-out seeds.
- OOD alarm failure: not observed; fixed guard remains well below the 1% high-alarm budget.
- Fixed-guard independent value: lowers_ood_alarm_without_material_detection_gain. It lowers OOD alarm relative to plain LR, but plain LR is already feasible and fixed guard does not materially improve detection.
- Threshold transfer issue: transfer-threshold protocol was not applicable in this run because current model/scaler/threshold artifacts could not be transferred cleanly.
- Feature/label mismatch: not observed for the local-calibration protocol; v7.4 original100 features and stage2 attack row bins were available.

## Interpretation

Do not package this result as strong LOW-GUARD generalization. It is harder-holdout boundary evidence: the low-alert guard transfers as an alarm-control mechanism under local calibration, but attack recovery is not stable across both pre-registered holdouts.
