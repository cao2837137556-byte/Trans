# issue27w Summary

1. issue27w completed: `true`.
2. primary_verdict: `gotham_sample_gate_promising_needs_more_space_and_larger_sample`.
3. sampled CSV / PCAP / metadata: CSV previews from `processed/iotsim-combined-cycle-2.csv, processed/iotsim-combined-cycle-tls-1.csv, processed/iotsim-hydraulic-system-8.csv, processed/iotsim-air-quality-1.csv, processed/iotsim-combined-cycle-10.csv, processed/iotsim-city-power-1.csv`; README metadata; PCAPs were not extracted, only matched by archive listing.
4. CSV label column: `yes`.
5. CSV frame.time: `yes`.
6. labels vs README / filenames: labels are consistent with README multiclass packet-level dataset; processed filenames are device-level and do not directly encode attack labels.
7. device / protocol / source: `partial_yes`; device/source from file paths and packet fields, protocol from `frame.protocols`.
8. benign multi-device/protocol/multi-stage potential: `yes_promising`; benign families include `air-quality, city-power, combined-cycle, combined-cycle-tls, hydraulic-system`.
9. attack labels and types: `C&C Communication, File Download, Ingress Tool Transfer, Mirai UDP Flooding, Reporting, TCP Scan, Telnet Brute Force, Unknown`.
10. ID/OOD benign split constructable: `yes_promising`, especially device/protocol-disjoint.
11. attack support/eval disjoint constructable: `yes_promising`, but needs larger manifest to control file/device/time artifacts.
12. most promising split: `device_disjoint_benign_drift`.
13. largest artifact risk: label/source/time coupling and benign-prefix-then-attack row-order in mixed files.
14. Gotham can enter larger sample Data Gate: `true`.
15. current model experiments allowed: `false`.
16. need to clean D first: `recommended`, because only about 20GB remained after issue27v.
17. issue27x recommendation: larger sample manifest and split gate, no model training.
18. Slurm needed: `not for sample gate`; maybe later for full feature extraction.
19. commit hash: pending.
