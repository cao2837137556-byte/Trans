# Scaler Provenance

For each method / holdout / budget / seed, `StandardScaler` is fit only on:

- ID benign train rows,
- OOD benign train rows,
- selected high-purity attack support rows from the pre-registered hard-holdout train pool.

The scaler is never fit on final OOD eval, attack eval, OOD validation, or ID calibration.
