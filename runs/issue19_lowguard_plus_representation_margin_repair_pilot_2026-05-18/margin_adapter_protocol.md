# Margin Adapter Protocol

The implemented margin/deviation pilot is a lightweight hard-negative LR adapter. For margin candidates, a first-pass LR model identifies the top 5% OOD-validation tail samples. The final LR is then refit with those OOD-validation hard negatives appended as negatives with pre-registered extra weights `[2.0, 4.0, 8.0]`.

The scaler is still fit only on ID benign train, OOD benign train, and selected attack supports. OOD validation hard negatives are transformed by that scaler. Final OOD eval and attack eval are never used for hard-negative mining or margin choice.
