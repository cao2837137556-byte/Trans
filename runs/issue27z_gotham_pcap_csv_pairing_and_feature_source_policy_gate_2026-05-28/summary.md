# issue27z Summary

1. issue27z complete: yes.
2. primary_verdict: gotham_ready_for_feature_interface_diagnostic_only.
3. allowed_mode: pcap_metadata_streaming.
4. PCAP/CSV pairing enhanced: yes, {'medium_filename_path_match': 74, 'high_packet_count_timestamp_match': 1, 'medium_plus_frame_timestamp_hint': 3}.
5. Pairing for primary split files sufficient: diagnostic-only yes; main feature path no.
6. Missing / low pairing files: none.
7. Source-like feature inventory complete: yes.
8. Fields forbidden from model input: attack_type, csv_archive_path, device, eth.dst, eth.src, file_id, frame.time, inferred_device, ip.dst, ip.src, label, pcap_archive_path, source/capture/path.
9. frame.time use: ordering / purge / split / audit / pairing only, not raw model input.
10. IP/MAC/port/protocol use: IP/MAC audit/pairing only; ports/protocol diagnostic only unless separately audited.
11. gotham_feature_source_policy_v1 formed: yes.
12. Gotham can enter Feature / interface gate: diagnostic only.
13. Gate type: ready_for_feature_interface_diagnostic_only.
14. Current model experiments allowed: no.
15. issue27aa recommendation: feature/interface gate under strict source policy, no model benchmark yet.
16. Slurm needed: not for issue27aa metadata/interface smoke; likely for full feature extraction later.
17. commit hash: pending.
