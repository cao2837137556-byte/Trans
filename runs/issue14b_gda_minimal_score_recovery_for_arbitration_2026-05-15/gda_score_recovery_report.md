# GDA-Minimal Score Recovery Report

Recovered method: `original100_fixed_guard_lr`.

Fixed configuration:

- positive budget: 32
- seeds: [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
- OOD benign weight: 2.0
- solver: LogisticRegression L2 liblinear
- scaler: fit on ID benign train + OOD benign train + selected support positives
- threshold: guarded ID calibration + OOD validation target 1%

This run refits the same fixed adapter configuration solely because issue11 did not persist row-level scores or fitted model artifacts. It does not search hyperparameters and does not change any support, split, threshold policy, or evaluation set.

Validation against issue11:

- all seeds passed: `True`
- validation file: `gda_recovery_validation.csv`
