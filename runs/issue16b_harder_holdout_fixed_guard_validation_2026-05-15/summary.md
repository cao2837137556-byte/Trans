# Issue16b Harder-Holdout Fixed-Guard Validation Summary

## 1. Outcome

Harder-holdout validation ran successfully under the local-calibration protocol. Transfer-threshold protocol was not run because current LOW-GUARD-minimal model/scaler/threshold artifacts do not directly transfer to v7.4 holdout windows.

## 2. Holdouts

- `chrono_late_train_early_eval`
- `holdout_bin_2`

## 3. Core 32-shot Results

| holdout_name | method | seed_group | attack_high_detection_mean | attack_high_detection_min | ood_high_alarm_mean | ood_high_alarm_max | feasible_rate |
|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | original100_fixed_guard_lr | heldout_47_51 | 0.733800 | 0.686807 | 0.001500 | 0.002400 | 1.000000 |
| chrono_late_train_early_eval | original100_plain_lr | heldout_47_51 | 0.734384 | 0.687099 | 0.002360 | 0.002900 | 1.000000 |
| chrono_late_train_early_eval | original100_fixed_guard_lr | main_42_46 | 0.691827 | 0.682720 | 0.001520 | 0.001700 | 1.000000 |
| chrono_late_train_early_eval | original100_plain_lr | main_42_46 | 0.691302 | 0.682428 | 0.002340 | 0.002900 | 1.000000 |
| holdout_bin_2 | original100_fixed_guard_lr | heldout_47_51 | 0.222700 | 0.199555 | 0.001480 | 0.001800 | 1.000000 |
| holdout_bin_2 | original100_plain_lr | heldout_47_51 | 0.225371 | 0.203264 | 0.001940 | 0.002300 | 1.000000 |
| holdout_bin_2 | original100_fixed_guard_lr | main_42_46 | 0.321217 | 0.232938 | 0.001540 | 0.003000 | 1.000000 |
| holdout_bin_2 | original100_plain_lr | main_42_46 | 0.323145 | 0.232938 | 0.002220 | 0.003500 | 1.000000 |


## 4. LOW-GUARD-minimal Validity

LOW-GUARD-minimal here means `original100_fixed_guard_lr`, 32-shot, fixed OOD benign weight 2. The issue16b verdict is `mixed_or_negative`.

Reason: Fixed guard keeps OOD high alarm feasible, but at least one pre-registered harder holdout has weak 32-shot attack detection (minimum mean=0.222700).

The result is best treated as harder-holdout boundary evidence, not a strong generalization result. It does not prove second-environment validation.

## 5. Fixed Guard Value

See `fixed_guard_vs_plain_harder_holdout.csv`. Fixed guard lowers OOD high alarm relative to plain LR, but plain LR is already feasible in this local-calibration harder-holdout protocol and fixed guard does not materially improve attack detection. Its independent value here is alarm-control, not detection gain.

## 6. Provenance

- Support overlap with attack eval: False.
- Support overlap with attack validation: False.
- Threshold uses final OOD eval: False.
- Threshold uses attack eval: False.

## 7. Missing Baselines

dA-only and Transformer-only harder-holdout base scores were not available under this exact issue16b protocol. Therefore delta-vs-base is not claimed.

## 8. Next Step

Treat this as boundary evidence. Prioritize failure analysis and same-protocol few-shot anomaly baselines; do not upgrade to complex adapters yet.

## 9. Safety

- Manuscript modified: False.
- Existing experimental numbers modified: False.
- dA / Transformer trained: False.
- Hyperparameter search: False.
- Full GDA claim introduced: False.
