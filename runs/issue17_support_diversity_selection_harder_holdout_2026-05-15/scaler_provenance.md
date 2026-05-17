# Scaler Provenance

For every issue17 run, StandardScaler is fit only on ID benign train, OOD benign train, and the selected attack support rows. It is not fit on ID calibration, OOD validation, final OOD eval, or attack eval.
