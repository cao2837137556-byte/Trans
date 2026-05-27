# Original100 Feature Leakage Diagnosis

Flagged label-like/split-like features: `0`.

Several original100 dimensions can be highly predictive of attack-vs-final-OOD, which may simply reflect real traffic structure. The stricter leakage flag requires near-perfect single-feature separation plus low-cardinality or dominant-value behavior. Under that stricter rule, the current audit does not identify an obvious label-like/split-like feature.

High-cardinality near-perfect separator features: `3`. These are not automatically label-like, but they are a reviewer-facing caution because original100 feature names/provenance are not recovered in this audit.

Top single-feature separation proxies:

| feature_index | feature_semantic | feature_family | lambda | stat_slot | unique_count | top_value_frequency | integer_like_rate | attack_vs_final_ood_abs_corr | single_feature_auc_attack_vs_final_ood | label_like_flag | split_like_flag | high_cardinality_perfect_separator |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 46 | HH_radius_lambda_0.01 | HH | 0.010000 | radius | 13211 | 0.000595 | 0.383042 | 0.325579 | 1.000000 | False | False | True |
| 47 | HH_magnitude_lambda_0.01 | HH | 0.010000 | magnitude | 13275 | 0.000149 | 0.005132 | 0.877811 | 1.000000 | False | False | True |
| 39 | HH_radius_lambda_0.1 | HH | 0.100000 | radius | 12639 | 0.000595 | 0.282782 | 0.226828 | 0.999365 | False | False | True |
| 12 | MI_dir_weight_lambda_0.01 | MI_dir | 0.010000 | weight | 13319 | 0.005132 | 0.006620 | 0.844035 | 0.957774 | False | False | False |
| 43 | HH_weight_lambda_0.01 | HH | 0.010000 | weight | 13319 | 0.005132 | 0.006620 | 0.844035 | 0.957774 | False | False | False |
| 62 | HH_jit_weight_lambda_0.01 | HH_jit | 0.010000 | weight | 13125 | 0.010264 | 0.013165 | 0.852330 | 0.940716 | False | False | False |
| 63 | HH_jit_mean_lambda_0.01 | HH_jit | 0.010000 | mean | 13391 | 0.000446 | 0.001934 | 0.081461 | 0.937364 | False | False | False |
| 60 | HH_jit_mean_lambda_0.1 | HH_jit | 0.100000 | mean | 13206 | 0.000446 | 0.004165 | 0.084058 | 0.933112 | False | False | False |
| 57 | HH_jit_mean_lambda_1 | HH_jit | 1.000000 | mean | 11826 | 0.002678 | 0.012570 | 0.083725 | 0.929667 | False | False | False |
| 54 | HH_jit_mean_lambda_3 | HH_jit | 3.000000 | mean | 11711 | 0.003124 | 0.012495 | 0.083108 | 0.929400 | False | False | False |
| 51 | HH_jit_mean_lambda_5 | HH_jit | 5.000000 | mean | 11668 | 0.003124 | 0.012718 | 0.082415 | 0.928155 | False | False | False |
| 59 | HH_jit_weight_lambda_0.1 | HH_jit | 0.100000 | weight | 12240 | 0.015619 | 0.016065 | 0.748025 | 0.925881 | False | False | False |
| 36 | HH_weight_lambda_0.1 | HH | 0.100000 | weight | 12988 | 0.007289 | 0.007810 | 0.692739 | 0.924957 | False | False | False |
| 9 | MI_dir_weight_lambda_0.1 | MI_dir | 0.100000 | weight | 12988 | 0.007289 | 0.007810 | 0.692739 | 0.924957 | False | False | False |
| 40 | HH_magnitude_lambda_0.1 | HH | 0.100000 | magnitude | 12929 | 0.000149 | 0.003942 | 0.591412 | 0.914776 | False | False | False |


The top near-perfect features map to ordinary KitNET traffic-stat families such as HH radius/magnitude at short decay windows, not to explicit row IDs, labels, split IDs, or support flags. This reduces but does not eliminate artifact concern, because we still need source-level provenance for how original100 rows were generated and aligned.

Limitation: HistGB has no stable native feature_importances_ attribute. The `histgb_importance_proxy` column uses single-feature AUC for leakage screening, not for model selection.
