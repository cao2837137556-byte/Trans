# Issue24b Adapter Bottleneck Diagnosis Summary

## Outcome

- Preflight passed: yes.
- Row-level score asset gap: issue23/24 did not persist row-level scores; representative seed `42` scores were reconstructed for fixed existing methods only.
- New adapter trained as method candidate: no.
- topK/support/representation changed: no.
- final eval used for new rule validation: no; final labels are used only for diagnosis.

## Main Diagnosis

- LR bottleneck: not a clear adapter bottleneck. LR is already strong under source_rich_top64; first-order OOD-tail weighting does not change detection.
- bin6/bin7 V2_top64 under V1 mainly because V1 has a small attack-side rescue set: mean V1-high/V2-low attack rate `0.024626` vs V2-high/V1-low `0.010490`.
- bin8 V2_top64 wins because V2 has a larger attack-side rescue set: V2-high/V1-low `0.056338` vs V1-high/V2-low `0.009390`.
- Weighted LR no-gain reason: locked detection delta vs LR `0.000000`; it slightly lowers OOD max but barely changes attack ranking.
- SVM failure reason: locked detection delta vs LR `-0.277167` and OOD max `0.018000`; margin calibration is unstable and violates low-alert constraints.
- Fusion potential: `strong`.
- Ranking bottleneck evidence: `weak`.
- Nonlinear separability evidence: `moderate`.
- Unique next action: `issue24c_v1_v2_residual_fusion_adapter_retry_2026-05-18`.

## Key Tables

Error overlap:

| holdout | split | n | both_high | v1_high_v2_low | v1_low_v2_high | both_low | both_high_rate | v1_high_v2_low_rate | v1_low_v2_high_rate | both_low_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| holdout_bin_5 | attack_eval | 877 | 820 | 28 | 29 | 0 | 0.935006 | 0.031927 | 0.033067 | 0.000000 |
| holdout_bin_6 | attack_eval | 1001 | 950 | 30 | 21 | 0 | 0.949051 | 0.029970 | 0.020979 | 0.000000 |
| holdout_bin_7 | attack_eval | 1141 | 1116 | 22 | 0 | 3 | 0.978089 | 0.019281 | 0.000000 | 0.002629 |
| holdout_bin_8 | attack_eval | 426 | 352 | 4 | 24 | 46 | 0.826291 | 0.009390 | 0.056338 | 0.107981 |


Fusion potential:

| holdout | split | v1_v2_score_correlation | v1_high_v2_low_rate | v1_low_v2_high_rate | fusion_potential |
|---|---|---|---|---|---|
| holdout_bin_5 | attack_eval | 0.598630 | 0.031927 | 0.033067 | strong |
| holdout_bin_6 | attack_eval | 0.657365 | 0.029970 | 0.020979 | weak |
| holdout_bin_7 | attack_eval | 0.530040 | 0.019281 | 0.000000 | weak |
| holdout_bin_8 | attack_eval | 0.791301 | 0.009390 | 0.056338 | moderate |
