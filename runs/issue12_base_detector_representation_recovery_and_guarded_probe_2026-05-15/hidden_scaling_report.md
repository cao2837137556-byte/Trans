# Hidden Scaling Report

- Scaler: `StandardScaler`.
- Fit scope: training data only: ID benign train + OOD benign train + selected high-purity attack supports.
- Hidden cache itself is generated without fitting any scaler on final OOD eval or attack eval.
- Final OOD eval and attack eval are never used for scaler fitting or threshold selection.
