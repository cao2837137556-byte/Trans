# Score Distribution Audit

Large double-margin rows (attack min above threshold and OOD max below threshold): `0.000`.

Target 0.005 and 0.0075 produce identical thresholds in `0.275` of rows. This explains why issue27f's 0.005 and 0.0075 robustness rows were identical: the guarded threshold is pinned by the same ID/OOD validation order statistic for those targets, not by attack_eval.

Attack scores are above threshold in every audited seed/bin. The final OOD maximum is above threshold in `0.875` of rows, which is consistent with the reported `0.000100` alarm: typically one OOD tail sample crosses the threshold. This is less suspicious than a completely zero-tail OOD result, but the separation is still strong enough that negative controls remain the main sanity gate.

| holdout | seed | threshold | attack_detection | final_ood_alarm | min_attack_score | max_final_ood_score | attack_min_minus_threshold | threshold_minus_final_ood_max | score_gap_large_flag |
|---|---|---|---|---|---|---|---|---|---|
| holdout_bin_5 | 42 | 0.002742 | 1.000000 | 0.000100 | 0.064264 | 0.004172 | 0.061521 | -0.001429 | False |
| holdout_bin_5 | 43 | 0.003181 | 1.000000 | 0.000100 | 0.038782 | 0.003821 | 0.035601 | -0.000640 | False |
| holdout_bin_5 | 44 | 0.002245 | 1.000000 | 0.000100 | 0.062427 | 0.005378 | 0.060183 | -0.003133 | False |
| holdout_bin_5 | 45 | 0.002373 | 1.000000 | 0.000100 | 0.028246 | 0.003396 | 0.025873 | -0.001022 | False |
| holdout_bin_5 | 46 | 0.001956 | 1.000000 | 0.000100 | 0.101124 | 0.006781 | 0.099167 | -0.004824 | False |
| holdout_bin_5 | 47 | 0.002931 | 1.000000 | 0.000100 | 0.020136 | 0.004127 | 0.017205 | -0.001196 | False |
| holdout_bin_5 | 48 | 0.002268 | 1.000000 | 0.000100 | 0.022355 | 0.003758 | 0.020086 | -0.001489 | False |
| holdout_bin_5 | 49 | 0.002232 | 1.000000 | 0.000000 | 0.019119 | 0.002106 | 0.016886 | 0.000127 | False |
| holdout_bin_5 | 50 | 0.002763 | 1.000000 | 0.000100 | 0.062124 | 0.006600 | 0.059361 | -0.003837 | False |
| holdout_bin_5 | 51 | 0.003169 | 1.000000 | 0.000100 | 0.064536 | 0.006358 | 0.061366 | -0.003189 | False |
| holdout_bin_6 | 42 | 0.002743 | 1.000000 | 0.000100 | 0.064265 | 0.004172 | 0.061523 | -0.001429 | False |
| holdout_bin_6 | 43 | 0.003181 | 1.000000 | 0.000100 | 0.054358 | 0.003821 | 0.051176 | -0.000640 | False |
| holdout_bin_6 | 44 | 0.002245 | 1.000000 | 0.000100 | 0.062427 | 0.005378 | 0.060183 | -0.003133 | False |
| holdout_bin_6 | 45 | 0.002373 | 1.000000 | 0.000100 | 0.028199 | 0.003396 | 0.025826 | -0.001022 | False |
| holdout_bin_6 | 46 | 0.001957 | 1.000000 | 0.000100 | 0.101123 | 0.006349 | 0.099167 | -0.004392 | False |
| holdout_bin_6 | 47 | 0.002931 | 1.000000 | 0.000100 | 0.020136 | 0.004127 | 0.017205 | -0.001196 | False |
