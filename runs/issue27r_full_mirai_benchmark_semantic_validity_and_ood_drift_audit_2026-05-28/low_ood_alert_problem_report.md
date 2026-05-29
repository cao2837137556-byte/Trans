# Low-OOD-Alert Problem Validity Report

Verdict: `low_ood_alert_problem_artifact_risk`.

Issue27p contains operating-point tradeoffs: some methods are high detection but over the OOD budget, some are OOD-feasible with low detection, and DeepSADStyle_Lite is strong but suspicious after issue27q_P0P1 negative controls.

This is enough to keep the low-OOD-alert question alive as a diagnostic phenomenon. It is not enough for a main paper claim while OOD deployment semantics and attack/benign semantics remain blocked by row-order/source/feature-provenance uncertainty.

The score dumps needed for a complete fixed-ID-threshold versus OOD-calibrated threshold curve were not saved for every issue27p method. The CSV records the available issue27p operating point and marks full curve replay as a required follow-up after semantic validity is fixed.
