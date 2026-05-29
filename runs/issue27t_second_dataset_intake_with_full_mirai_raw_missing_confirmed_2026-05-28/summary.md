# issue27t Second Dataset Intake Summary

1. issue27t completed: `true`.
2. primary_verdict: `second_dataset_candidates_need_manual_access_or_download_confirmation`.
3. full Mirai paired raw confirmed missing: `true`; user confirmed only feature CSV + labels were downloaded, and issue27s found no paired raw pcap/input stream.
4. local available pcap / dataset candidates: local IoT23/public_data pcaps and labeled logs; small CICIoT2023 public_data CSV subsets; local ToN-IoT-style train_test_network CSV; local BoT-IoT 5% flow CSVs.
5. external candidates in pool: Gotham Dataset 2025, ToN-IoT, CICIoT2023, BoT-IoT/NF-BoT-IoT, UNSW-IoTraffic auxiliary, GeNIS 2025 fallback.
6. top recommended datasets: Gotham Dataset 2025 and ToN-IoT / TON_IoT network.
7. Gotham fit: raw PCAP + CSV + metadata + labels shape appears strongest for low-OOD-alert Data Gate; risk is 23.8GB size and metadata must be verified before raw download.
8. ToN-IoT fit: IoT/IIoT network data with labels and likely raw/log/security-event metadata; risk is access/manual download and local CSV alone is not enough.
9. user download confirmation needed: `yes`, before any PCAP/large archive download.
10. download path plan: `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\raw|metadata|labels|derived|manifests`; never C drive/Downloads/Desktop/temp.
11. model experiments allowed now: `false`; still Data validity gate.
12. issue27u recommendation: Gotham metadata intake and Data Gate precheck; ToN-IoT fallback if Gotham blocks.
13. Slurm needed: not for issue27t; maybe later for feature extraction over large raw PCAP.
14. commit hash: pending.
