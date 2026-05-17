# Issue16b Protocol

## Scope

Formal harder-holdout validation for LOW-GUARD-minimal under pre-registered v7.4 hard-holdout candidates. This is not second-environment validation, not model upgrade, and not hyperparameter search.

## Holdouts

- `chrono_late_train_early_eval`: train bins 6,7,8; validation bin 5; eval bins 2,3,4.
- `holdout_bin_2`: train bins 3,4,5,6,7,8; no independent attack validation; eval bin 2.

## Method Matrix

- `original100_plain_lr`: original100 representation, few-shot LR, OOD benign weight 1.
- `original100_fixed_guard_lr`: original100 representation, few-shot LR, fixed OOD benign weight 2.

Base-only dA/Transformer harder-holdout baselines were not available under this protocol and are reported as missing.

## Fixed Configuration

- LogisticRegression: C=1.0, L2, liblinear, class_weight=balanced, max_iter=2000, random_state=42.
- Budgets: 16 and 32.
- Seeds: 42-46 main, 47-51 held-out.
- Threshold protocol: local ID calibration + OOD validation guard, target OOD alarm 0.01.
- Scaler fit scope: ID benign train + OOD benign train + selected attack supports only.
- Final OOD eval and attack eval are not used for training, scaler fitting, or threshold selection.

## Protocol Split

Only local-calibration protocol was run. Transfer-threshold protocol was not run because current model/scaler/threshold artifacts do not directly transfer to v7.4 hard-holdout windows.
