# issue27y Summary

1. issue27y complete: yes.
2. primary_verdict: gotham_data_contract_promising_needs_feature_pairing_or_full_manifest.
3. allowed_mode: full_file_summary_plus_sampled_row_manifest.
4. All 78 CSV file-level summary complete: yes.
5. Fuller row manifest complete: yes, 13372 rows.
6. Row manifest type: stratified sampled row manifest.
7. PCAP/CSV pairing confidence: medium filename/path pairing; summary {'medium_filename_path_match': 78}.
8. Label/file/device/protocol/time shortcut risk: material; label/file risk remains high and must be controlled by file-disjoint contracts and feature-source policy.
9. At least one preregistered split contract found: yes.
10. Recommended split contract: gotham_device_disjoint_v1.
11. ID benign train constructible: yes under gotham_device_disjoint_v1, pending feature/source policy.
12. OOD benign validation constructible: yes under gotham_device_disjoint_v1, pending feature/source policy.
13. Final OOD benign eval constructible: yes under gotham_device_disjoint_v1, report-only.
14. Attack support/eval disjoint constructible: yes at file level, but needs PCAP/row-level strengthening.
15. Size adequacy: primary contract appears size-adequate, but size alone is not sufficient for claim safety.
16. Gotham can enter Feature / interface gate: not yet; it first needs PCAP/CSV pairing strengthening and feature-source shortcut policy.
17. Current model experiments allowed: no.
18. issue27z recommendation: PCAP/CSV pairing and feature-source policy gate.
19. Slurm needed: not for issue27z metadata/pairing; likely for full feature extraction later.
20. commit hash: pending.
