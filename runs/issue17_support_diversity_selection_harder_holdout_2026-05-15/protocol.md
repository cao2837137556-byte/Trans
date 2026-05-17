# Issue17 Protocol

This is a targeted support-acquisition repair experiment after issue16b/issue16c failure analysis.

- Model: original100 fixed-guard LogisticRegression only.
- OOD benign weight: fixed at 2.
- Positive budget: 32-shot.
- Seeds: 42-46 main, 47-51 held-out.
- Holdouts: holdout_bin_2 and chrono_late_train_early_eval.
- Support selection uses only local harder-holdout attack train pool features.
- Scaler fit: ID benign train + OOD benign train + selected attack supports.
- Threshold: local ID calibration + OOD validation target 1%.
- Final OOD eval and attack eval are evaluation-only.
- No dA/Transformer training, no MLP/prototype/margin-GDA, no OOD-weight search.
