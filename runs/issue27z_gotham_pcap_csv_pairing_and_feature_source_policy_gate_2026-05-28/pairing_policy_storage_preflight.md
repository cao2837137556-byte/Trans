# Pairing Policy Storage Preflight

- D drive free space: 71.130 GiB
- Gotham zip: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw\GothamDataset2025.zip`
- md5: `7ca78c0517ccb3d2854e823678e0f206` (matches expected)
- allowed_mode: `pcap_metadata_streaming`
- Tooling: no `tshark/capinfos/tcpdump/scapy` command was available; PCAP metadata uses a Python streaming parser directly on zip members.
- No PCAP, full CSV, or archive-wide extraction is performed.
