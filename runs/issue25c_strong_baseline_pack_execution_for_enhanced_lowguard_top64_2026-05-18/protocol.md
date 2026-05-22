# Protocol

This run executes the issue25b strong baseline protocol.

## Fixed Main Method

- Representation: selected_source_rich_top64.
- Support: kcenter32 confirmed attack supports.
- Adapter: fixed OOD guard LR.
- Threshold: ID calibration + OOD validation under 1% OOD alarm target.

## Evaluation Objects

- Locked bins: holdout_bin_5, holdout_bin_6, holdout_bin_7, holdout_bin_8.
- Consistency checks: primary_lowood, holdout_bin_2, chrono_late_train_early_eval.
- Seeds: 42-46 main and 47-51 held-out.

## Fairness Rules

- Unsupervised baselines do not use attack supports for model fitting.
- Few-shot/semi-supervised baselines use the same kcenter32 support budget.
- Hyperparameters are selected only by train/cal/val or support-holdout evidence.
- Thresholds use ID calibration + OOD validation only.
- final OOD eval and final attack eval are report-only.
