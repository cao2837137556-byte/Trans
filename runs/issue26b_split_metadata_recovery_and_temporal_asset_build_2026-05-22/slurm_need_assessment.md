# Slurm Need Assessment

| field | value |
|---|---|
| task_name | issue26b_split_metadata_recovery_and_temporal_asset_build |
| local_feasible | yes |
| estimated_cost | low |
| requires_large_parquet_scan | no for this issue26b inventory |
| requires_multi_seed | no |
| requires_model_training | no |
| requires_slurm | no |
| recommended_partition_if_known | NA |
| recommended_time | NA |
| recommended_mem | NA |
| recommended_cpus | NA |
| recommended_log_paths | NA |
| reason | This round only scans existing manifests/provenance and writes planning artifacts. Slurm is only appropriate for large raw data scans or formal multi-seed issue26c validation after metadata is recovered. |
