# issue27u Gotham Metadata Intake Summary

1. issue27u completed: `true`.
2. primary_verdict: `gotham_ready_for_full_download_with_user_confirmation`.
3. Gotham raw PCAP: `yes`, according to official Zenodo metadata.
4. labelled CSV: `yes`, processed packet-level CSV is reported.
5. timestamp/order: `yes`, metadata files reportedly include timestamps.
6. device/source/capture metadata: `yes/promising`, device-level files from 78 heterogeneous IoT devices are reported.
7. benign multi-stage/environment: `promising_not_yet_verified`; non-IID device traffic suggests possible ID/OOD benign split, but file-level labels must be inspected.
8. attack labels: `yes`, deterministic labels from orchestration logs and metadata attack types are reported.
9. support for low-OOD-alert benchmark: `promising`, but not validated until file-level Data Gate.
10. largest risk: Zenodo exposes a single `23.825GB decimal / 22.189GiB` zip; no small per-device download path was visible in API metadata.
11. user confirmation needed: `yes` before any raw/full download.
12. recommended download: `GothamDataset2025.zip` only after confirmation; inspect zip listing/metadata before extraction.
13. planned path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw|metadata|labels|derived|manifests`.
14. model experiments allowed: `false`.
15. if Gotham not suitable: fallback to ToN-IoT metadata intake.
16. Slurm needed: not for metadata; possibly for feature extraction after large download.
17. commit hash: pending.
