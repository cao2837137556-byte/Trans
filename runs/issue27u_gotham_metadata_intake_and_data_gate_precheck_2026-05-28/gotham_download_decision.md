# Gotham Download Decision

Decision: `gotham_ready_for_full_download_with_user_confirmation`.

Do not download automatically in this issue.

Recommended next download, only with user confirmation:

1. `GothamDataset2025.zip` from Zenodo record `https://zenodo.org/records/14502760`.
2. Save only under `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw`.
3. Preserve Zenodo metadata under `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\metadata`.
4. Write file hashes and extraction manifest under `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\manifests`.

Expected download size: `23.825GB decimal / 22.189GiB`.

Expected decompressed size: unknown; plan for significantly more than the zip size.

Recommended immediate follow-up after user confirmation:

- download the zip to the D: dataset root.
- inspect zip file listing before extraction.
- extract only metadata/README/CSV schema first if possible.
- do not run models.
