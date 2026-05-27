# Separator Distribution Diagnosis

The separator features show strong attack-vs-final-OOD separation, but support-vs-attack-eval KS distances are large rather than near zero. This suggests the support set is not a duplicate copy of attack_eval on these features; in fact, kcenter supports are often more extreme than the held-out attack_eval distribution on the same traffic-stat dimensions.

Support/attack summary:

| feature_index | split | mean | median | q05 | q95 | ks_to_attack_eval | unique_count |
|---|---|---|---|---|---|---|---|
| 39 | attack_eval | 2207.188131 | 2370.547867 | 226.089509 | 3185.817557 | 0.000000 | 847.000000 |
| 39 | support | 282420.799227 | 176818.720703 | 183.166813 | 715607.418750 | 0.625000 | 30.000000 |
| 46 | attack_eval | 2362.678459 | 2543.444458 | 239.790664 | 2653.556720 | 0.000000 | 846.250000 |
| 46 | support | 279755.483853 | 411983.527344 | 255.499984 | 507285.687891 | 0.703308 | 28.000000 |
| 47 | attack_eval | 127.042689 | 129.195788 | 107.314630 | 130.380504 | 0.000000 | 845.250000 |
| 47 | support | 755.858042 | 1052.684875 | 93.687667 | 1211.671628 | 0.692554 | 32.000000 |


Benign split drift summary:

| feature_index | split | mean | median | q05 | q95 | ks_to_final_ood |
|---|---|---|---|---|---|---|
| 39 | id_calib | 128859.202216 | 139871.101562 | 26610.393652 | 154484.971094 | 0.899900 |
| 39 | id_train | 130555.689577 | 139861.710938 | 25903.467090 | 155232.114062 | 0.896875 |
| 39 | ood_eval | 26777.997848 | 16881.294922 | 6888.587280 | 109113.949609 | 0.000000 |
| 39 | ood_train | 22784.368890 | 16486.101562 | 6608.560669 | 47679.330078 | 0.026375 |
| 39 | ood_val | 22216.774804 | 16672.123047 | 6873.405444 | 34182.391406 | 0.030000 |
| 46 | id_calib | 131691.183083 | 140396.242188 | 29434.842969 | 142181.141406 | 0.898500 |
| 46 | id_train | 136646.522418 | 140907.640625 | 28929.146484 | 153286.525781 | 0.893425 |
| 46 | ood_eval | 31771.094972 | 20870.319336 | 19470.861816 | 80788.241797 | 0.000000 |
| 46 | ood_train | 27246.806920 | 20838.673828 | 19438.703027 | 63817.552539 | 0.050175 |
| 46 | ood_val | 26870.917158 | 20848.274414 | 19499.165039 | 60421.958789 | 0.040100 |
| 47 | id_calib | 380.289731 | 396.274933 | 192.021201 | 402.045840 | 0.912600 |
| 47 | id_train | 384.200668 | 396.374939 | 189.926732 | 410.489191 | 0.908675 |
| 47 | ood_eval | 248.932854 | 245.338577 | 225.517203 | 273.108469 | 0.000000 |
| 47 | ood_train | 244.812714 | 243.658386 | 221.597006 | 264.771678 | 0.062850 |
| 47 | ood_val | 245.066862 | 244.026894 | 223.235925 | 263.348688 | 0.062000 |


Boundary: this is a distribution sanity check, not raw packet identity proof.
