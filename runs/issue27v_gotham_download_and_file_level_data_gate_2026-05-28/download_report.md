# Download Report

- source: `https://zenodo.org/api/records/14502760/files/GothamDataset2025.zip/content`
- target: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw\GothamDataset2025.zip`
- download_status: `already_present_md5_ok`
- attempted in final postprocess run: `False`
- log: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\manifests\download_log.txt`

The zip may have been downloaded by an earlier user-approved issue27v resume attempt to the same target path. When the final postprocess run sees a complete file with matching md5, it skips re-download and records `already_present_md5_ok`.

If this gate must be rerun, use `python repo/ood/issue27v_gotham_download_file_gate.py --user-approved-download-only`; the script will reuse/resume the same target path.
