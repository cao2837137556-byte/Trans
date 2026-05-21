# Fusion Potential Report

Fusion potential is `strong`. The pattern is not a universal complementarity story: V1 rescues some bin6/bin7 attacks, while V2 rescues bin8. A future residual/fusion adapter is only justified if it is validation-gated and does not increase OOD alarms.

| holdout | split | v1_v2_score_correlation | v1_high_v2_low_rate | v1_low_v2_high_rate | fusion_potential |
|---|---|---|---|---|---|
| holdout_bin_5 | attack_eval | 0.598630 | 0.031927 | 0.033067 | strong |
| holdout_bin_5 | final_ood_eval | -0.004766 | 0.001800 | 0.004400 | none |
| holdout_bin_6 | attack_eval | 0.657365 | 0.029970 | 0.020979 | weak |
| holdout_bin_6 | final_ood_eval | -0.005798 | 0.001800 | 0.004400 | none |
| holdout_bin_7 | attack_eval | 0.530040 | 0.019281 | 0.000000 | weak |
| holdout_bin_7 | final_ood_eval | 0.039240 | 0.001900 | 0.004000 | none |
| holdout_bin_8 | attack_eval | 0.791301 | 0.009390 | 0.056338 | moderate |
| holdout_bin_8 | final_ood_eval | 0.076421 | 0.004800 | 0.003700 | none |
