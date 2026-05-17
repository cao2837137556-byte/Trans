# Preflight Score Persistence Check

- Can reproduce issue17 random/kcenter 1% metrics: True.
- Row-level scores saved: True.
- Row-level fields include sample_id/row_id/split/label/holdout/seed/support_method/budget/score/threshold/high/margin fields: True.
- Scores come from the same model class and scaler protocol as issue17: True.
- Scaler fit uses only ID train + OOD train + selected supports: True.
- Thresholds use only ID calibration + OOD validation: True. For `random_32shot_baseline` at 1%, the persisted row-level view uses the issue17/issue16b recorded 1% threshold to exactly reproduce the reused random baseline; this recorded threshold was itself selected from ID calibration + OOD validation.
- Final OOD eval / attack eval used for threshold selection: False.
- Support selection uses eval: False.
- OOD weight fixed at 2: True.
