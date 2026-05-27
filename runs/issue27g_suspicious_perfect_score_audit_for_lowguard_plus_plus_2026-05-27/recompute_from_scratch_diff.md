# Recompute From Scratch Diff

Scratch recompute status: `matches_issue27f`.

This rerun reloads assets, rebuilds support rows, refits the frozen HistGB config, recalibrates threshold from ID_calib + OOD_val, and reports final eval for seed 42/43 and bins 5/8. It does not rely on issue27f cached by-seed metrics except for comparison.

| holdout | seed | recompute_attack_detection | recompute_final_ood_alarm | recompute_id_calib_alarm | recompute_ood_val_alarm | recompute_threshold | issue27f_attack_detection | issue27f_final_ood_alarm | issue27f_id_calib_alarm | issue27f_ood_val_alarm | issue27f_threshold | abs_diff_attack_detection | abs_diff_final_ood_alarm | abs_diff_threshold | scratch_train_eval_time | matches_issue27f_metrics |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| holdout_bin_5 | 42 | 1.000000 | 0.000100 | 0.004600 | 0.000000 | 0.002742 | 1.000000 | 0.000100 | 0.004600 | 0.000000 | 0.002742 | 0.000000 | 0.000000 | 0.000000 | 0.561921 | True |
| holdout_bin_5 | 43 | 1.000000 | 0.000100 | 0.004800 | 0.000000 | 0.003181 | 1.000000 | 0.000100 | 0.004800 | 0.000000 | 0.003181 | 0.000000 | 0.000000 | 0.000000 | 0.565915 | True |
| holdout_bin_8 | 42 | 1.000000 | 0.000100 | 0.005000 | 0.000000 | 0.001621 | 1.000000 | 0.000100 | 0.005000 | 0.000000 | 0.001621 | 0.000000 | 0.000000 | 0.000000 | 0.552894 | True |
| holdout_bin_8 | 43 | 1.000000 | 0.000100 | 0.005000 | 0.000000 | 0.002135 | 1.000000 | 0.000100 | 0.005000 | 0.000000 | 0.002135 | 0.000000 | 0.000000 | 0.000000 | 0.554621 | True |
