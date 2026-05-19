# Attack/OOD Margin Proxy Report

| setting | support_holdout_detection_v1 | support_holdout_detection_v2 | delta_support_holdout_detection | sep_v1 | sep_v2 | delta_sep | v1_validation_ood_alarm | v2_validation_ood_alarm |
|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | 1.000000 | 0.983833 | -0.016167 | 19.751846 | 11.290364 | -8.461482 | 0.000000 | 0.010000 |
| holdout_bin_2 | 1.000000 | 0.961027 | -0.038973 | 20.174695 | 13.237472 | -6.937223 | 0.000000 | 0.006000 |
| primary_lowood | 0.932274 | 0.969193 | 0.036919 | 18.495514 | 14.986096 | -3.509418 | 0.000500 | 0.009500 |

Final eval is not used in these proxy inputs. The margin proxy is useful only if it can separate harder-shift settings without promoting V2 in primary low-OOD.
