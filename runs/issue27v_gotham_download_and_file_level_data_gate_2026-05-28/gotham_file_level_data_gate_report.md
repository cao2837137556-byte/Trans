# Gotham File-Level Data Gate Report

Primary file-level gate status: `gotham_download_incomplete_resume_required`.

- `pcap_real_exists`: `blocked_storage_insufficient` (0)
- `labelled_csv_real_exists`: `blocked_storage_insufficient` (0)
- `metadata_or_readme_exists`: `blocked_storage_insufficient` (0)
- `label_or_attack_file_candidate_exists`: `blocked_storage_insufficient` (0)
- `timestamp_metadata_available`: `blocked_storage_insufficient` (requires selective metadata inspection)
- `device_source_capture_metadata_available`: `blocked_storage_insufficient` (requires selective metadata inspection)
- `id_ood_attack_split_constructable`: `blocked_storage_insufficient` (file-level gate only)
- `row_order_artifact_auditable`: `blocked_storage_insufficient` (requires row-level sample)
- `source_capture_artifact_auditable`: `blocked_storage_insufficient` (requires metadata/sample)
- `model_experiments_allowed`: `False` (still Data validity gate)

This gate does not authorize model experiments. If blocked by storage, the next action is to free D: space or move the dataset root to a user-approved large D: location, then rerun the same file-level gate.
