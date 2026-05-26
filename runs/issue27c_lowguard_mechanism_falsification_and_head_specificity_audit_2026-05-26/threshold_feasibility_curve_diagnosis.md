# Threshold Feasibility Curve Diagnosis

The stricter target curve was computed using ID calibration + OOD validation only. Final OOD and attack eval remain report-only. The curve does not select a better target; it asks whether non-LR heads merely lack safety margin.

Interpretation:
- DevNet-like's near miss at 1% indicates a safety-margin problem, not a clear LOW-GUARD++ candidate.
- As targets tighten, non-LR detection degrades or remains OOD-risky, so the current evidence does not justify upgrading beyond LOW-GUARD-LR.
- LR retains the clearest feasible low-alert operating point.

Target snapshot:

| head_id | head_family | ood_val_target | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | id_calib_alarm_mean | ood_val_alarm_mean | threshold_source | selection_used_final_eval | threshold_uses_final_eval |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LOW_GUARD_LR_reference | lr | 0.010000 | 0.949705 | 0.882629 | 0.004500 | 1.000000 | 0.010000 | 0.000750 | id_calib_plus_ood_val_guarded | False | False |
| DevNet_like_MLP | devnet_like_mlp | 0.010000 | 0.947497 | 0.895305 | 0.010100 | 0.975000 | 0.009935 | 0.002188 | id_calib_plus_ood_val_guarded | False | False |
| HistGB_shallow | histgb | 0.010000 | 0.755626 | 0.230047 | 0.013900 | 0.675000 | 0.006565 | 0.007437 | id_calib_plus_ood_val_guarded | False | False |
| DeepSAD_like_center | deepsad_like_center | 0.010000 | 0.037650 | 0.002805 | 0.013400 | 0.250000 | 0.002240 | 0.009962 | id_calib_plus_ood_val_guarded | False | False |
| LOW_GUARD_LR_reference | lr | 0.005000 | 0.949119 | 0.880282 | 0.003700 | 1.000000 | 0.004900 | 0.000625 | id_calib_plus_ood_val_guarded | False | False |
| DevNet_like_MLP | devnet_like_mlp | 0.005000 | 0.943188 | 0.887324 | 0.007400 | 0.500000 | 0.004950 | 0.001162 | id_calib_plus_ood_val_guarded | False | False |
| HistGB_shallow | histgb | 0.005000 | 0.750575 | 0.224413 | 0.008200 | 0.925000 | 0.002465 | 0.002213 | id_calib_plus_ood_val_guarded | False | False |
| DeepSAD_like_center | deepsad_like_center | 0.005000 | 0.016822 | 0.001052 | 0.007700 | 0.500000 | 0.000875 | 0.004562 | id_calib_plus_ood_val_guarded | False | False |
