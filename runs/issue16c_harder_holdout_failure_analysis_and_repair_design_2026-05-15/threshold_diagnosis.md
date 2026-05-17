# Threshold Diagnosis

Issue16b used local ID calibration + OOD validation thresholding. Final OOD eval and attack eval were not used for threshold selection.

| holdout_name | method | positive_budget | seed_group | threshold_mean | threshold_std | threshold_min | threshold_max | id_calib_alarm_mean | ood_val_alarm_mean | attack_detection_mean | ood_alarm_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | original100_fixed_guard_lr | 16 | heldout_47_51 | -3.497983 | 0.502056 | -4.346796 | -3.120385 | 0.009920 | 0.001000 | 0.695855 | 0.002020 |
| chrono_late_train_early_eval | original100_plain_lr | 16 | heldout_47_51 | -3.489406 | 0.463070 | -4.253867 | -3.124595 | 0.009720 | 0.003400 | 0.695271 | 0.003580 |
| chrono_late_train_early_eval | original100_fixed_guard_lr | 16 | main_42_46 | -3.679246 | 0.408754 | -4.132512 | -3.242221 | 0.009920 | 0.001000 | 0.711500 | 0.001980 |
| chrono_late_train_early_eval | original100_plain_lr | 16 | main_42_46 | -3.640713 | 0.399026 | -4.083048 | -3.227835 | 0.009920 | 0.001400 | 0.711208 | 0.002820 |
| chrono_late_train_early_eval | original100_fixed_guard_lr | 32 | heldout_47_51 | -3.937034 | 0.510058 | -4.555388 | -3.435858 | 0.009880 | 0.001000 | 0.733800 | 0.001500 |
| chrono_late_train_early_eval | original100_plain_lr | 32 | heldout_47_51 | -3.915261 | 0.485373 | -4.507838 | -3.428464 | 0.009880 | 0.002100 | 0.734384 | 0.002360 |
| chrono_late_train_early_eval | original100_fixed_guard_lr | 32 | main_42_46 | -3.429818 | 0.062347 | -3.482305 | -3.332950 | 0.009800 | 0.000000 | 0.691827 | 0.001520 |
| chrono_late_train_early_eval | original100_plain_lr | 32 | main_42_46 | -3.414634 | 0.051262 | -3.461772 | -3.337054 | 0.009880 | 0.001700 | 0.691302 | 0.002340 |
| holdout_bin_2 | original100_fixed_guard_lr | 16 | heldout_47_51 | -4.027954 | 0.670140 | -4.741803 | -3.304212 | 0.009840 | 0.001000 | 0.365282 | 0.002420 |
| holdout_bin_2 | original100_plain_lr | 16 | heldout_47_51 | -4.016619 | 0.690913 | -4.750533 | -3.287873 | 0.009960 | 0.003000 | 0.368843 | 0.003780 |
| holdout_bin_2 | original100_fixed_guard_lr | 16 | main_42_46 | -3.691005 | 0.562468 | -4.679081 | -3.261291 | 0.009880 | 0.000400 | 0.284866 | 0.001800 |
| holdout_bin_2 | original100_plain_lr | 16 | main_42_46 | -3.663371 | 0.575820 | -4.676101 | -3.230651 | 0.009920 | 0.000900 | 0.283828 | 0.002220 |
| holdout_bin_2 | original100_fixed_guard_lr | 32 | heldout_47_51 | -3.476913 | 0.121781 | -3.595493 | -3.303419 | 0.009920 | 0.000300 | 0.222700 | 0.001480 |
| holdout_bin_2 | original100_plain_lr | 32 | heldout_47_51 | -3.450685 | 0.114163 | -3.561809 | -3.284743 | 0.009920 | 0.001100 | 0.225371 | 0.001940 |
| holdout_bin_2 | original100_fixed_guard_lr | 32 | main_42_46 | -3.830452 | 0.425969 | -4.493965 | -3.481806 | 0.009840 | 0.000100 | 0.321217 | 0.001540 |
| holdout_bin_2 | original100_plain_lr | 32 | main_42_46 | -3.811382 | 0.429607 | -4.478008 | -3.489924 | 0.009920 | 0.000700 | 0.323145 | 0.002220 |

## Interpretation

- OOD high alarm remains below 1% on the hard holdouts, so the main failure is not OOD alarm overflow.
- The 0.5% / 1% / 2% diagnostic curve cannot be computed without row-level score arrays.
- OOD target sensitivity is a reasonable next diagnostic, but it must be run as a pre-registered analysis with saved row-level scores and no final-eval target selection.
