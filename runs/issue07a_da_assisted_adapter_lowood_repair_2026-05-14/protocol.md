# Issue07a Protocol

## Scope
This run tests only dA-assisted few-shot adapter branches under the current low-OOD primary protocol. It does not retrain dA, does not use Transformer, and does not modify the manuscript.

## Data roles
- ID benign: train `[0,8000)`, calibration `[10000,15000)`, final eval `[15000,50000)`.
- OOD benign: train `[0,8000)`, validation `[8000,10000)`, final eval `[10000,20000)`.
- High-purity attack: train pool `4122` rows, validation `1374` rows, final eval `1375` rows.

## Methods
- `da_score_only_fewshot_lr`: one-dimensional dA score input, L2 LogisticRegression adapter.
- `original100_plus_da_score_fewshot_lr`: original100 features concatenated with dA score, L2 LogisticRegression adapter.

## Fairness
- Final OOD eval is not used for training or threshold selection.
- Final attack eval is not used for training or threshold selection.
- dA scores are reused from existing aligned cache; dA is not retrained.
- Threshold policy: `guarded_id_calib_and_ood_val_target1pct`.
