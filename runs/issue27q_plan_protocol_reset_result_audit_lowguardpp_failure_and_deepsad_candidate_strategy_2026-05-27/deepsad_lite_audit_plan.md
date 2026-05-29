# DeepSADStyle_Lite Audit Plan

DeepSADStyle_Lite is the current issue27p leader under the anonymous-clean115 protocol reset, with
detection_mean `0.886735`, detection_min `0.886731`,
final_OOD_alarm_max `0.008175`, and feasible_rate `1.000000`.

This result is promising but not yet claim-safe. The highest-priority concern is not just high performance;
it is the near seed-invariance and the fact that the implementation is a DeepSAD-style Lite weighted-center
objective, not exact Deep SAD.

P0 audit steps:

1. Recompute score direction from saved split artifacts and verify that higher scores are more anomalous.
2. Verify support rows are train-side only and disjoint from attack eval.
3. Replay threshold construction with assertions that only ID_calib and OOD_val scores are used.
4. Run label permutation, support removal, and support shuffle negative controls.
5. Audit feature dependence: top columns, top-k ablation, row-index proxy test, and distribution drift across train/val/final.
6. Expand seeds from 42-46 to 42-51 only after P0 controls pass.
7. Add attack-cluster or attack-row-block stratification so the high aggregate detection is not hiding a weak sub-family.

Claim boundary:

- If audit passes, the candidate can be called a strong `DeepSADStyle_Lite` reset-protocol candidate.
- It cannot be called exact Deep SAD without an exact objective implementation and fair rerun.
- It cannot be used for external generalization claims.
