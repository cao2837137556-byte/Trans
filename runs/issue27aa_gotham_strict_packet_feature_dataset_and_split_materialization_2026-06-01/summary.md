# issue27aa Summary

1. issue27aa complete: yes.
2. primary_verdict: gotham_strict_feature_dataset_ready_for_model_interface_smoke.
3. Dataset version: gotham_strict_packet_header_v1.
4. Strict feature artifact path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\strict_packet_feature_dataset_v1\gotham_strict_packet_header_v1_features.csv.gz`.
5. Sidecar artifact path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\strict_packet_feature_dataset_v1\gotham_strict_packet_header_v1_sidecar.csv.gz`.
6. Rows materialized: 26736743.
7. Strict features: frame.len, ip.flags, ip.tos, ip.ttl, tcp.flags, tcp.pdu.size, tcp.window_size_scalefactor, tcp.window_size_value.
8. Forbidden/source-like fields absent from feature matrix: yes.
9. Split roles materialized: {'id_benign_train': 1716285, 'ood_benign_val': 1308423, 'final_ood_benign_eval': 842307, 'excluded_benign_in_attack_support_file': 4537619, 'attack_support_pool': 7619570, 'excluded_benign_in_attack_eval_file': 3859919, 'attack_eval': 15250158}.
10. Attack support/eval disjoint: yes, by preregistered file-role contract.
11. Final eval report-only: yes.
12. Feature sparsity/blocking issues: none blocking; high-missing=['ip.tos', 'tcp.pdu.size']; constant=[].
13. Current model experiments allowed: no; next is interface smoke only.
14. issue27ab recommendation: strict packet interface smoke, no model selection.
15. Slurm needed: not for interface smoke; likely for later full benchmark or PCAP-derived feature extraction.
16. commit hash: pending.
