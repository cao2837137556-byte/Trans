# issue27x Summary

1. issue27x completed: `true`.
2. primary_verdict: `gotham_larger_sample_promising_needs_full_manifest`.
3. allowed_mode: `limited_csv_extract`.
4. D free space: `71.136 GiB`.
5. storage_target_mismatch: `False`.
6. larger sample coverage: devices `air-quality, building-monitor, city-power, combined-cycle, combined-cycle-tls, cooler-motor, domotic-monitor, hydraulic-system, ip-camera-museum, ip-camera-street`; protocols `coap, data, dns, dtls, goose, http, icmp, mqtt, ntp, rtcp, telnet, tls`; attack types `C&C Communication, File Download, Ingress Tool Transfer, Mirai C&C Communication, Mirai UDP Flooding, Reporting, TCP Scan, Telnet Brute Force, Unknown`.
7. row-level manifest built: `true`, sampled rows `11721`.
8. PCAP/CSV pairing: `medium_confidence_filename_path_match`, sampled pairing ok `True`.
9. most promising split: `device_disjoint_benign_drift`.
10. claim-safe ID/OOD benign: `not_yet`; promising but needs fuller manifest and exact final-eval holdout contract.
11. attack support/eval disjoint: `not_yet`; plausible but needs file/device/time-disjoint contract.
12. largest artifact risk: `label_vs_file_id` / `high`.
13. artifact risk controllable by split design: `partially`, but not enough to enter Feature/interface gate now.
14. Gotham can enter Feature/interface gate: `false`.
15. current model experiments allowed: `false`.
16. further D cleanup needed: `recommended`, but current limited mode was sufficient for streaming sampled manifest.
17. issue27y recommendation: fuller manifest and pre-registered split contract.
18. Slurm needed: `not for issue27x`; maybe later for full feature extraction.
19. commit hash: pending.
