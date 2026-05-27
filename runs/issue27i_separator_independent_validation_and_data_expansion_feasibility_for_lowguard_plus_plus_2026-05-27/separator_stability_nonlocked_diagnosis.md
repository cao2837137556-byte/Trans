# Separator Stability On Non-Locked Assets

Evidence level: `consistency_only`.

Separator stability strong on available consistency assets: `False`.

| asset_name | feature_index | feature_name | auc | rank | top_high | support_ks | ood_ks |
|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | 39 | HH_radius_lambda_0.1 | 0.842441 | 19.000000 | 0.000000 | 0.404024 | 0.026375 |
| chrono_late_train_early_eval | 46 | HH_radius_lambda_0.01 | 0.510754 | 92.000000 | 0.000000 | 0.896673 | 0.050175 |
| chrono_late_train_early_eval | 47 | HH_magnitude_lambda_0.01 | 0.660799 | 59.000000 | 0.000000 | 0.810566 | 0.062850 |
| holdout_bin_2 | 39 | HH_radius_lambda_0.1 | 0.600575 | 68.000000 | 0.000000 | 0.503709 | 0.026375 |
| holdout_bin_2 | 46 | HH_radius_lambda_0.01 | 0.953000 | 14.000000 | 0.000000 | 0.957715 | 0.050175 |
| holdout_bin_2 | 47 | HH_magnitude_lambda_0.01 | 0.862093 | 22.000000 | 0.000000 | 0.957715 | 0.062850 |
| primary_lowood | 39 | HH_radius_lambda_0.1 | 0.999397 | 3.000000 | 1.000000 | 0.625000 | 0.026375 |
| primary_lowood | 46 | HH_radius_lambda_0.01 | 1.000000 | 1.000000 | 1.000000 | 0.781250 | 0.050175 |
| primary_lowood | 47 | HH_magnitude_lambda_0.01 | 1.000000 | 2.000000 | 1.000000 | 0.772523 | 0.062850 |


Boundary: these are not clean independent validation objects because primary / holdout_bin_2 / chrono_late were already part of earlier discovery or consistency evidence.
