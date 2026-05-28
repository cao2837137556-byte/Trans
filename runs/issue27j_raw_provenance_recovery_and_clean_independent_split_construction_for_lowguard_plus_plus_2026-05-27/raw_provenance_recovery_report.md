# Raw Provenance Recovery Report

Raw packet / timestamp assets found: `True`.
Row-level mapping recoverable by extraction order: `True`.

Key recovered assets:

| asset_name | asset_type | exists | row_count | contains_raw_timestamp | contains_packet_order | contains_row_id | contains_capture_id | contains_label_mapping | can_reconstruct_original100 | limitations |
|---|---|---|---|---|---|---|---|---|---|---|
| id_raw_pcap | pcap | True | binary_pcap | True | True | False | True | False | True | No persisted packet hash manifest; mapping relies on deterministic extraction order. |
| id_extracted_tsv | tsv_packet_table | True | 50000 | True | True | True | True | False | True | Row_id is implicit row order, not a persisted explicit id column. |
| id_full_feature_npy | npy_feature_matrix | True | 50000x100 | False | False | False | False | False | False | Feature matrix has no embedded timestamp or row ids. |
| id_source_matrix | source_feature_matrix | True | 50000x100 | False | False | False | False | False | False | Current paper asset used by experiments; provenance is implicit via stage metadata. |
| id_feature_headers | feature_name_mapping | True | 100 | False | False | False | False | False | True | Feature names only; no row provenance. |
| ood_raw_pcap | pcap | True | binary_pcap | True | True | False | True | False | True | No persisted packet hash manifest; mapping relies on deterministic extraction order. |
| ood_extracted_tsv | tsv_packet_table | True | 20000 | True | True | True | True | False | True | Row_id is implicit row order, not a persisted explicit id column. |
| ood_full_feature_npy | npy_feature_matrix | True | 20000x100 | False | False | False | False | False | False | Feature matrix has no embedded timestamp or row ids. |
| ood_source_matrix | source_feature_matrix | True | 20000x100 | False | False | False | False | False | False | Current paper asset used by experiments; provenance is implicit via stage metadata. |
| ood_feature_headers | feature_name_mapping | True | 100 | False | False | False | False | False | True | Feature names only; no row provenance. |
| attack_raw_pcap | pcap | True | binary_pcap | True | True | False | True | False | True | No persisted packet hash manifest; mapping relies on deterministic extraction order. |
| attack_extracted_tsv | tsv_packet_table | True | 30000 | True | True | True | True | False | True | Row_id is implicit row order, not a persisted explicit id column. |
| attack_full_feature_npy | npy_feature_matrix | True | 30000x100 | False | False | False | False | False | False | Feature matrix has no embedded timestamp or row ids. |
| attack_source_matrix | source_feature_matrix | True | 10000x100 | False | False | False | False | False | False | Current paper asset used by experiments; provenance is implicit via stage metadata. |
| attack_feature_headers | feature_name_mapping | True | 100 | False | False | False | False | False | True | Feature names only; no row provenance. |
| attack_zeek_labeled_log | zeek_labeled_log | True | 23145 | True | False | False | True | True | False | Flow-level labels do not provide packet-level one-to-one labels without timestamp/window mapping. |
| stage1_data_manifest | json_manifest | True | NA | False | False | False | True | True | False | Capture-level and file-level provenance, not row-level split manifest. |
| stage2_attack_manifest | json_manifest | True | 10 | False | False | False | False | True | False | Has bin IDs and counts, but no per-row timestamp ranges or support/eval row IDs. |
| frontend_original_netstat | source_code | True | NA | False | False | False | False | False | True | Defines feature semantics but not row provenance. |
| frontend_original_afterimage | source_code | True | NA | False | False | False | False | False | True | Defines decay/stat update semantics; no data asset. |
| frontend_original_extract_script | source_code | True | NA | True | True | True | False | False | True | Can rebuild features but current script does not emit a row-level sidecar manifest. |
| second_env_ciciot_raw | external_raw_csv | True | 127151x39 | False | False | False | False | True | False | Schema is not Kitsune original100-compatible without a dedicated feature builder. |


Attack bin counts recovered from TSV + stage2 manifest:

| bin | row_count | timestamp_min | timestamp_max | conn_total | conn_mal | mal_ratio | packet_count |
|---|---|---|---|---|---|---|---|
| 0.000000 | 1624.000000 | 1545403816.870900 | 1545404416.517753 | 52.000000 | 4.000000 | 0.076923 | 1624.000000 |
| 1.000000 | 1297.000000 | 1545404417.061944 | 1545405016.662421 | 180.000000 | 136.000000 | 0.755556 | 1297.000000 |
| 2.000000 | 1348.000000 | 1545405017.862232 | 1545405613.222477 | 161.000000 | 144.000000 | 0.894410 | 1348.000000 |
| 3.000000 | 958.000000 | 1545405617.302398 | 1545406215.887825 | 157.000000 | 143.000000 | 0.910828 | 958.000000 |
| 4.000000 | 1120.000000 | 1545406216.901494 | 1545406816.020304 | 163.000000 | 150.000000 | 0.920245 | 1120.000000 |
| 5.000000 | 877.000000 | 1545406818.854184 | 1545407415.219472 | 156.000000 | 139.000000 | 0.891026 | 877.000000 |
| 6.000000 | 1001.000000 | 1545407416.999450 | 1545408016.498897 | 157.000000 | 147.000000 | 0.936306 | 1001.000000 |
| 7.000000 | 1141.000000 | 1545408019.319034 | 1545408614.978946 | 172.000000 | 155.000000 | 0.901163 | 1141.000000 |
| 8.000000 | 426.000000 | 1545408617.058792 | 1545409215.938754 | 135.000000 | 124.000000 | 0.918519 | 426.000000 |
| 9.000000 | 208.000000 | 1545409218.717927 | 1545409458.709300 | 59.000000 | 52.000000 | 0.881356 | 208.000000 |


Interpretation:
- Current original100 source matrices can be traced back to pcap -> TSV -> feature extraction -> source matrix slices.
- This gives useful provenance, but it is still not a formal clean validation split because the row-level sidecar was not persisted and unused future/capture validation assets are insufficient.
