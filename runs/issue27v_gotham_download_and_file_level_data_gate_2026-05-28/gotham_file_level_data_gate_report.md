# Gotham File-Level Data Gate Report

Primary file-level gate status: `gotham_file_level_gate_passed_ready_for_sample_data_gate`.

- `pcap_real_exists`: `True` (110)
- `labelled_csv_real_exists`: `True` (78 CSVs; label column detected in preview=True)
- `metadata_or_readme_exists`: `True` (metadata files=0; readme files=1)
- `label_or_attack_file_candidate_exists`: `True` (label file candidates=0; label column=True; README attack types=True)
- `timestamp_metadata_available`: `True` (CSV preview frame.time/timestamp=True)
- `device_source_capture_metadata_available`: `partial_filename_csv_readme` (README/device/source terms and packet fields=True; no separate metadata JSON found in archive listing)
- `id_ood_attack_split_constructable`: `needs_sample_data_gate` (file-level gate only)
- `row_order_artifact_auditable`: `needs_sample_data_gate` (requires row-level sample)
- `source_capture_artifact_auditable`: `needs_sample_data_gate` (requires metadata/sample)
- `model_experiments_allowed`: `False` (still Data validity gate)

This gate does not authorize model experiments. If metadata extraction is blocked by low free space, the next action is to free D: space before sample Data Gate.
