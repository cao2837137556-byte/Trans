# Support-Holdout Proxy Report

| setting | support_pool_size | support_size | support_holdout_size | support_holdout_detection_v1 | support_holdout_detection_v2 | delta_support_holdout_detection |
|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | 2568 | 32 | 2536 | 1.000000 | 0.983833 | -0.016167 |
| holdout_bin_2 | 5523 | 32 | 5491 | 1.000000 | 0.961027 | -0.038973 |
| primary_lowood | 4122 | 32 | 4090 | 0.932274 | 0.969193 | 0.036919 |

Support-holdout comes from local attack train pool after removing selected supports. It is not final attack eval, but it may still be optimistic because it is close to the support acquisition process.
