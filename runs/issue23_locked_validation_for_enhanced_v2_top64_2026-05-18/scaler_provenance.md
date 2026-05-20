# Scaler Provenance

Each method/holdout/seed fits StandardScaler only on the corresponding training matrix: ID benign train + OOD benign train + selected local attack supports. ID calibration, OOD validation, final OOD eval, and attack eval are transformed using that train-fitted scaler only.
