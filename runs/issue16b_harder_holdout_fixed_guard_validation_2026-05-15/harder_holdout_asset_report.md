# Harder-Holdout Asset Report

The run used the pre-registered v7.4 paired hard-holdout candidates and original100 assets recovered during issue16.

| holdout_name | holdout_type | train_bins | val_bins | eval_bins | train_pool_count | attack_val_count | attack_eval_count | feature_path | id_feature_path | ood_feature_path | row_id_availability | comparability_risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| holdout_bin_2 | leave_one_attack_window_out | 3,4,5,6,7,8 |  | 2 | 5523 | 0 | 1348 | D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage1_2026-03-31\data\attack_source_100.csv | D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stage1_2026-03-25\data\id_source_100.npy | D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stage1_2026-03-25\data\ood_benign_source_100.npy | attack row index from stage2 manifest bins | local-calibration hard-holdout; not second-environment and not strict threshold transfer |
| chrono_late_train_early_eval | chronological_cross_window | 6,7,8 | 5 | 2,3,4 | 2568 | 877 | 3426 | D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage1_2026-03-31\data\attack_source_100.csv | D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stage1_2026-03-25\data\id_source_100.npy | D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stage1_2026-03-25\data\ood_benign_source_100.npy | attack row index from stage2 manifest bins | local-calibration hard-holdout; not second-environment and not strict threshold transfer |


These assets support local-calibration harder-holdout validation. They do not constitute a second-environment dataset, and the current model/scaler/threshold artifacts were not treated as safely transferable to this v7.4 protocol.
