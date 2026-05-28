# Row-Level Sidecar Manifest Report

Sidecar manifest constructed: `True`.

Rows:
- ID: 50000
- OOD benign: 20000
- attack: 10000
- total: 80000

Alignment summary:

| role | source_rows | tsv_rows_used | full_feature_rows_used | source_vs_full_allclose | source_vs_full_max_abs_diff | source_vs_full_mean_abs_diff | source_vs_full_max_rel_diff | source_vs_full_p99999_abs_diff | allclose_tolerance | timestamp_monotonic | duplicate_timestamp_count | duplicate_feature_hash_count | alignment_confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| id | 50000 | 50000 | 50000 | True | 0.053686 | 0.000522 | 0.000000 | 0.014567 | atol=1e-6,rtol=1e-6 | True | 0 | 0 | high | Source matrix aligns to extracted feature cache by row order. |
| ood | 20000 | 20000 | 20000 | True | 7.723359 | 0.000301 | 0.000000 | 3.919313 | atol=1e-6,rtol=1e-6 | True | 0 | 0 | high | Source matrix aligns to extracted feature cache by row order. |
| attack | 10000 | 10000 | 10000 | True | 0.111439 | 0.000205 | 0.000000 | 0.098045 | atol=1e-6,rtol=1e-6 | True | 0 | 0 | high | Source matrix aligns to extracted feature cache by row order. |


Interpretation:
- extracted TSV row order, feature cache row order, and current original100 source matrix row order align for the current cached assets.
- the detailed row-order alignment audit is saved in `original100_row_alignment_check.csv`.
- packet hash is a TSV-row fingerprint, not raw packet bytes.
- raw pcap source paths are recorded, but byte-level pcap-to-row hashing was not performed in this issue.
- row-level provenance is now explicit enough for split construction planning, but not enough by itself to create a new clean validation object.
