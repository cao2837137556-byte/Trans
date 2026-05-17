# Issue19 Protocol

This is a controlled LOW-GUARD+ repair pilot after issue18 diagnosed a representation/score bottleneck. It keeps the base LOW-GUARD-minimal ingredients fixed where possible: local harder-holdout supports, OOD benign weight 2, L2 LogisticRegression, and guarded ID-calibration + OOD-validation thresholding.

The pilot tests selected source_rich features and a lightweight hard-negative margin adapter. It does not train dA or Transformer, does not use final OOD eval or attack eval for feature/margin/threshold selection, and does not select 2% OOD target as a new method.
