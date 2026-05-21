# Fusion Selection Report

Selection metric: support-holdout detection, then support-holdout margin, then OOD validation alarm. Final eval is not used.

| evaluation_role | dataset | holdout | seed | fusion_family | config_id | support_val_detection | support_val_margin_q25 | ood_val_alarm | selection_score |
|---|---|---|---|---|---|---|---|---|---|
| locked | locked_harder_holdout | holdout_bin_5 | 42 | linear_alpha | alpha_0.90 | 1.000000 | 6.846895 | 0.000500 | 1006.846395 |
| locked | locked_harder_holdout | holdout_bin_5 | 42 | conservative_max | beta_0.50 | 1.000000 | 7.371951 | 0.000500 | 1007.371451 |
| locked | locked_harder_holdout | holdout_bin_5 | 42 | residual_lr | residual_C_1.0 | 1.000000 | 14.219422 | 0.000500 | 1014.218922 |
| locked | locked_harder_holdout | holdout_bin_5 | 43 | linear_alpha | alpha_0.50 | 1.000000 | 5.443964 | 0.000000 | 1005.443964 |
| locked | locked_harder_holdout | holdout_bin_5 | 43 | conservative_max | beta_1.00 | 1.000000 | 5.231969 | 0.000500 | 1005.231469 |
| locked | locked_harder_holdout | holdout_bin_5 | 43 | residual_lr | residual_C_1.0 | 1.000000 | 11.716582 | 0.000500 | 1011.716082 |
| locked | locked_harder_holdout | holdout_bin_5 | 44 | linear_alpha | alpha_0.90 | 1.000000 | 7.593642 | 0.001000 | 1007.592642 |
| locked | locked_harder_holdout | holdout_bin_5 | 44 | conservative_max | beta_0.75 | 1.000000 | 8.283792 | 0.001000 | 1008.282792 |
| locked | locked_harder_holdout | holdout_bin_5 | 44 | residual_lr | residual_C_1.0 | 1.000000 | 17.181460 | 0.001000 | 1017.180460 |
| locked | locked_harder_holdout | holdout_bin_5 | 45 | linear_alpha | alpha_0.90 | 1.000000 | 4.737611 | 0.000500 | 1004.737111 |
| locked | locked_harder_holdout | holdout_bin_5 | 45 | conservative_max | beta_0.50 | 1.000000 | 5.166977 | 0.001000 | 1005.165977 |
| locked | locked_harder_holdout | holdout_bin_5 | 45 | residual_lr | residual_C_1.0 | 1.000000 | 10.998145 | 0.001000 | 1010.997145 |
| locked | locked_harder_holdout | holdout_bin_5 | 46 | linear_alpha | alpha_0.90 | 1.000000 | 5.073189 | 0.001500 | 1005.071689 |
| locked | locked_harder_holdout | holdout_bin_5 | 46 | conservative_max | beta_0.75 | 1.000000 | 5.928431 | 0.001500 | 1005.926931 |
| locked | locked_harder_holdout | holdout_bin_5 | 46 | residual_lr | residual_C_1.0 | 1.000000 | 13.279896 | 0.001500 | 1013.278396 |
| locked | locked_harder_holdout | holdout_bin_5 | 47 | linear_alpha | alpha_0.90 | 1.000000 | 4.143692 | 0.000500 | 1004.143192 |
| locked | locked_harder_holdout | holdout_bin_5 | 47 | conservative_max | beta_0.50 | 1.000000 | 4.418044 | 0.002500 | 1004.415544 |
| locked | locked_harder_holdout | holdout_bin_5 | 47 | residual_lr | residual_C_1.0 | 1.000000 | 8.431751 | 0.002000 | 1008.429751 |
| locked | locked_harder_holdout | holdout_bin_5 | 48 | linear_alpha | alpha_0.90 | 0.875000 | 3.883398 | 0.002000 | 878.881398 |
| locked | locked_harder_holdout | holdout_bin_5 | 48 | conservative_max | beta_0.50 | 0.875000 | 4.229065 | 0.003000 | 879.226065 |
| locked | locked_harder_holdout | holdout_bin_5 | 48 | residual_lr | residual_C_0.1 | 1.000000 | 6.628089 | 0.004000 | 1006.624089 |
| locked | locked_harder_holdout | holdout_bin_5 | 49 | linear_alpha | alpha_0.90 | 1.000000 | 4.716944 | 0.000500 | 1004.716444 |
| locked | locked_harder_holdout | holdout_bin_5 | 49 | conservative_max | beta_0.50 | 1.000000 | 4.860241 | 0.000500 | 1004.859741 |
| locked | locked_harder_holdout | holdout_bin_5 | 49 | residual_lr | residual_C_1.0 | 1.000000 | 10.108066 | 0.000500 | 1010.107566 |
| locked | locked_harder_holdout | holdout_bin_5 | 50 | linear_alpha | alpha_0.90 | 1.000000 | 3.062067 | 0.001000 | 1003.061067 |
| locked | locked_harder_holdout | holdout_bin_5 | 50 | conservative_max | beta_1.00 | 1.000000 | 3.876269 | 0.001500 | 1003.874769 |
| locked | locked_harder_holdout | holdout_bin_5 | 50 | residual_lr | residual_C_1.0 | 1.000000 | 6.251320 | 0.000000 | 1006.251320 |
| locked | locked_harder_holdout | holdout_bin_5 | 51 | linear_alpha | alpha_0.90 | 1.000000 | 4.890165 | 0.001000 | 1004.889165 |
| locked | locked_harder_holdout | holdout_bin_5 | 51 | conservative_max | beta_0.75 | 1.000000 | 4.881296 | 0.001500 | 1004.879796 |
| locked | locked_harder_holdout | holdout_bin_5 | 51 | residual_lr | residual_C_1.0 | 1.000000 | 10.276501 | 0.000500 | 1010.276001 |
| locked | locked_harder_holdout | holdout_bin_6 | 42 | linear_alpha | alpha_0.90 | 1.000000 | 6.753489 | 0.001000 | 1006.752489 |
| locked | locked_harder_holdout | holdout_bin_6 | 42 | conservative_max | beta_0.50 | 1.000000 | 7.242280 | 0.001000 | 1007.241280 |
| locked | locked_harder_holdout | holdout_bin_6 | 42 | residual_lr | residual_C_1.0 | 1.000000 | 14.126143 | 0.001000 | 1014.125143 |
| locked | locked_harder_holdout | holdout_bin_6 | 43 | linear_alpha | alpha_0.50 | 1.000000 | 5.423465 | 0.000000 | 1005.423465 |
| locked | locked_harder_holdout | holdout_bin_6 | 43 | conservative_max | beta_1.00 | 1.000000 | 5.216164 | 0.000500 | 1005.215664 |
| locked | locked_harder_holdout | holdout_bin_6 | 43 | residual_lr | residual_C_1.0 | 1.000000 | 11.612915 | 0.000500 | 1011.612415 |
| locked | locked_harder_holdout | holdout_bin_6 | 44 | linear_alpha | alpha_0.90 | 1.000000 | 7.704098 | 0.000500 | 1007.703598 |
| locked | locked_harder_holdout | holdout_bin_6 | 44 | conservative_max | beta_0.75 | 1.000000 | 8.391668 | 0.001500 | 1008.390168 |
| locked | locked_harder_holdout | holdout_bin_6 | 44 | residual_lr | residual_C_1.0 | 1.000000 | 17.369163 | 0.000500 | 1017.368663 |
| locked | locked_harder_holdout | holdout_bin_6 | 45 | linear_alpha | alpha_0.90 | 1.000000 | 4.717562 | 0.000500 | 1004.717062 |
