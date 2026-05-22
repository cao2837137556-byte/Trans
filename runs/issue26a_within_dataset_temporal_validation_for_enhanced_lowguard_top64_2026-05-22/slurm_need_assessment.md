# Slurm Need Assessment

| task_name | local_feasible | estimated_cost | requires_large_parquet_scan | requires_multi_seed | requires_model_training | requires_slurm | recommended_partition_if_known | recommended_time | recommended_mem | recommended_cpus | recommended_log_paths | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| issue26a inventory/report generation | yes | low | no | no | no | no | NA | NA | NA | NA | D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22 | Only reads existing CSV/MD/JSON assets and writes inventory reports. |
| issue26b formal/purged temporal validation | unknown | medium | unknown | yes | yes, lightweight LR/baselines only if executed | unknown | standard CPU partition if available | 01:00:00 to 04:00:00 after smoke | 8G to 32G depending on raw asset rebuild | 4 to 8 | runs/issue26b_*/stdout.log; runs/issue26b_*/stderr.log; slurm-%j.out/.err | Formal validation may rebuild temporal splits and run multi-seed matrix; local smoke first. |

Conclusion: issue26a does not need Slurm.
