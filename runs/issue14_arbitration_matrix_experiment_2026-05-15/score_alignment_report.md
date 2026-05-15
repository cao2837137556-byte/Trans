# Score Alignment Report

Base detector score assets are available for the current low-OOD protocol:

- dA ID/OOD/attack score caches: available.
- Transformer ID/OOD/attack score caches: available.

The blocking item is GDA-minimal row-level scoring:

- issue11 `run_issue11_fixed_config_ablation.py` computes `decision_function` scores in memory for ID calibration, OOD validation, final OOD eval, and attack eval.
- issue11 persists aggregate seed metrics, thresholds, support provenance, and threshold provenance.
- issue11 does not persist per-sample `gda_score`, `gda_high`, predictions, or fitted model artifacts.

Because mode-gated arbitration requires `base_high(x)` and `gda_high(x)` on the exact same final OOD and attack eval row ids, this pack does not compute strategy metrics.

See `score_alignment_report.csv` and `gda_score_artifact_inventory.csv`.
