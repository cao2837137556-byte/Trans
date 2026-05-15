# Score Alignment Report

Score alignment passed for issue14b.

- dA base scores cover current low-OOD ID/OOD/attack score spaces.
- Transformer base scores cover current low-OOD ID/OOD/attack score spaces.
- GDA-minimal scores were recovered for `final_ood_eval` and `attack_eval` using the same row-id slices as issue11.
- The recovered GDA seed-level metrics match issue11, confirming that this is score recovery for the fixed issue11 configuration rather than a new model search.

See `score_alignment_report.csv` and `gda_recovery_validation.csv`.
