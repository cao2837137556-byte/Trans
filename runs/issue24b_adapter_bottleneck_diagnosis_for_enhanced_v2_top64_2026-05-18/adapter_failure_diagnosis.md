# Adapter Failure Diagnosis

Weighted LR:
- Detection delta vs LR: `0.000000`.
- It slightly lowers OOD max but does not change locked mean or min detection.
- Interpretation: OOD-tail weighting mostly shifts the threshold/tail safety, not the attack ranking.

Linear SVM:
- Detection delta vs LR: `-0.277167`.
- OOD max: `0.018000`.
- Interpretation: hinge-margin scoring is poorly calibrated under the guarded threshold and few-shot support; it pushes enough OOD tail high to violate the low-alert constraint.
