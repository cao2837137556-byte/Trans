# Support Similarity Analysis

The analysis uses original100 features and issue16b support IDs. Distances are standardized using each holdout's attack train pool only, so final attack eval is not used to fit the distance scale.

## Summary

| holdout_name | positive_budget | seed_group | n_seeds | eval_to_nearest_support_distance_mean | eval_to_nearest_support_distance_max | eval_to_support_centroid_distance_mean | current_eval_nearest_support_mean_proxy | holdout_vs_current_nearest_distance_ratio |
|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | 16 | heldout_47_51 | 5 | 338.085754 | 7463.461426 | 340.932597 | 5.661796 | 60.169288 |
| chrono_late_train_early_eval | 16 | main_42_46 | 5 | 338.077037 | 7462.970215 | 340.728095 | 5.662890 | 59.759359 |
| chrono_late_train_early_eval | 32 | heldout_47_51 | 5 | 337.483286 | 7455.171387 | 340.592768 | 4.716958 | 71.586842 |
| chrono_late_train_early_eval | 32 | main_42_46 | 5 | 337.318743 | 7456.457520 | 340.794066 | 4.570260 | 74.135388 |
| holdout_bin_2 | 16 | heldout_47_51 | 5 | 313.714445 | 7372.862793 | 317.727703 | 5.496995 | 57.303137 |
| holdout_bin_2 | 16 | main_42_46 | 5 | 313.851535 | 7371.650391 | 317.855364 | 5.372003 | 58.514225 |
| holdout_bin_2 | 32 | heldout_47_51 | 5 | 311.634037 | 7369.239258 | 317.611210 | 4.287182 | 72.711923 |
| holdout_bin_2 | 32 | main_42_46 | 5 | 311.868431 | 7372.803223 | 317.549907 | 4.613402 | 67.851777 |

## Interpretation

`holdout_bin_2` shows weaker detection and should be treated as a support/attack-shift candidate. If its support-to-eval distance is larger than the chrono holdout, the next repair should target support diversity or representation coverage rather than increasing model complexity blindly.
