# DeepSADStyle_Lite Implementation Replay

DeepSADStyle_Lite is a weighted-center distance method:

- normal center and scale are estimated from ID_train + OOD_train.
- attack support is used only to form feature weights from support mean distance to the normal center.
- score is weighted squared distance to the normal center.
- higher score means more anomalous.
- threshold is max(99th percentile ID_calib score, 99th percentile OOD_val score).
- final OOD eval and attack eval are report-only.

This is not full Deep SAD. It is a DeepSAD-style Lite / weighted-center objective.
Replay of seeds 42..46 matches issue27p.
