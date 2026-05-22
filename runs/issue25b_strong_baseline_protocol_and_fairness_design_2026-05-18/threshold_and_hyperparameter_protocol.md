# Threshold and Hyperparameter Protocol

## Universal Rule

For every method:

1. Fit or train only on allowed training data.
2. Select hyperparameters only using train/cal/val.
3. Select threshold tau only using ID calibration + OOD validation.
4. Official OOD target is 1%.
5. final OOD eval and attack eval are report-only.
6. No method may choose threshold, hyperparameters, representation, support, architecture, early stopping, or score orientation using final eval.
7. If validation proxy is unavailable or unreliable, mark the method as diagnostic only.

## Hyperparameter Selection Objective

Primary validation objective:

- Maximize attack-side validation or support-holdout proxy subject to OOD validation alarm <= 1%.

Fallback objective when no clean attack validation proxy exists:

- Use pre-registered method-native validation score quality, then apply the common 1% OOD validation threshold.
- Mark the method as limited if no attack-side proxy is available.

## Threshold Calibration

All methods must output a scalar score where larger means more anomalous or attack-like. If a method's native orientation is reversed, orientation must be determined from training/calibration data only.

Threshold tau is calibrated by ID calibration + OOD validation under the 1% low-alert budget. The final OOD eval cannot be used to adjust tau.

## Reporting

Report both validation-selected hyperparameters and final report-only metrics. Do not report only the best final result. If multiple validation-tied configurations exist, use a deterministic tie-breaker:

1. lower OOD validation alarm;
2. simpler model;
3. lower training cost;
4. fixed lexical order of configuration name.
