# Download And Storage Plan

No large downloads were performed in issue27t.

All future data must live under:

`D:\study\paper\anomaly_detection\paper04\datasets`

Directory template:

- `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\raw`
- `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\metadata`
- `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\labels`
- `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\derived`
- `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\manifests`

Git rules:

- Do not stage raw PCAP, pcapng, zip, 7z, tar.gz, or large CSV files.
- Only stage small README, manifest, hash, and metadata pointer files.
- Do not download to `C:\Users`, Downloads, Desktop, or temp directories.

Next user-confirmed downloads:

1. Gotham metadata/index first, then raw PCAP only after size confirmation.
2. ToN-IoT network raw/log/security-event metadata package if Gotham is blocked.
3. CICIoT2023 only if top two paths fail or the user wants a larger fallback.
