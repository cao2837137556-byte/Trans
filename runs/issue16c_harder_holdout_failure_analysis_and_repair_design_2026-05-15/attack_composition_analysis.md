# Attack Composition Analysis

Stage2 attack-bin metadata is available, but richer attack-family/device metadata was not found in issue16b assets.

| holdout_name | role | bins | row_count | metadata_type | notes |
|---|---|---|---|---|---|
| holdout_bin_2 | train_bins | 3,4,5,6,7,8 | 5523 | stage2_attack_bin | Bin metadata available; attack family/device labels were not found in issue16b assets. |
| holdout_bin_2 | eval_bins | 2 | 1348 | stage2_attack_bin | Bin metadata available; attack family/device labels were not found in issue16b assets. |
| chrono_late_train_early_eval | train_bins | 6,7,8 | 2568 | stage2_attack_bin | Bin metadata available; attack family/device labels were not found in issue16b assets. |
| chrono_late_train_early_eval | eval_bins | 2,3,4 | 3426 | stage2_attack_bin | Bin metadata available; attack family/device labels were not found in issue16b assets. |

## Interpretation

`holdout_bin_2` is explicitly a leave-one-attack-window-out case: train bins exclude bin 2 and eval is bin 2. This supports the interpretation that the failure is a harder attack-window shift rather than an OOD alarm-control failure.
