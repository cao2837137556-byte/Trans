# Issue14b Protocol

- GDA-minimal configuration: `original100_fixed_guard_lr`.
- Positive budget: 32.
- Support seeds: 42-46 and held-out 47-51.
- OOD benign sample weight: 2.
- LogisticRegression config: C=1.0, L2, liblinear, class_weight=balanced, max_iter=2000, random_state=42.
- Scaler: StandardScaler fit on ID benign train + OOD benign train + selected attack supports only.
- Threshold: guarded ID calibration + OOD validation target 1% OOD alarm.
- Final OOD eval and attack eval are used only for reporting.
- Base thresholds for dA and Transformer are selected from ID calibration + OOD validation only.
