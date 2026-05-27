# Feature Provenance Mapping

The three high-cardinality near-perfect separator features map to standard KitNET/Kitsune original frontend traffic statistics, not explicit label/split/bin columns.

| feature_id | original100_index | feature_name_if_available | mapped_kitnet_family | mapped_statistic_type | lambda | could_encode_label | could_encode_split | could_encode_bin | could_encode_timestamp_or_order | risk_level |
|---|---|---|---|---|---|---|---|---|---|---|
| separator_1 | 46 | HH_radius_lambda_0.01 | HH | radius | 0.010000 | False | False | not_directly_but_time_evolving_stat_can_reflect_window | indirect_temporal_dynamics_via_decay | medium_low |
| separator_2 | 47 | HH_magnitude_lambda_0.01 | HH | magnitude | 0.010000 | False | False | not_directly_but_time_evolving_stat_can_reflect_window | indirect_temporal_dynamics_via_decay | medium_low |
| separator_3 | 39 | HH_radius_lambda_0.1 | HH | radius | 0.100000 | False | False | not_directly_but_time_evolving_stat_can_reflect_window | indirect_temporal_dynamics_via_decay | medium_low |


Technical interpretation: these features are generated from decayed host-host traffic statistics (`HH radius` and `HH magnitude`) in `repo/kitsune_frontend_original/netStat.py` and `AfterImage.py`. They can reflect temporal traffic dynamics because the statistics are updated online with timestamps, but this is different from carrying a row id or label field. Packet-level provenance would still be needed for a final artifact-proof statement.
