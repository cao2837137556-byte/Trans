# issue27cc Summary

1. issue27cc completed: `true`.
2. primary_verdict: `targeted_multitype_attack_contract_ready_for_slurm_exact_label_materialization`.
3. task type: targeted multi-attack exact-label contract planning; no model training and no feature extraction.
4. scanned CSV files: `8`.
5. scanned attack segments: `78964`.
6. current exact-filter reusable support rows: `86336`.
7. newly planned targeted support rows: `69492`.
8. planned development/query attack rows: `537460`.
9. planned sealed final attack exact rows: `110104`.
10. support labels after current reuse + targeted plan: `['File Download', 'Ingress Tool Transfer', 'Merlin C&C Communication', 'Merlin ICMP Flooding', 'Merlin TCP Flooding', 'Merlin UDP Flooding', 'Mirai C&C Communication', 'Mirai GRE Flooding', 'Mirai TCP Flooding', 'Mirai UDP Flooding', 'TCP Scan', 'Telnet Brute Force']`.
11. benign/Unknown rows planned for attack roles: `0` by construction.
12. same-file support/query reuse: allowed only for development-side time-forward query with embargo; not clean final.
13. current certified 1M asset mutation: `false`.
14. next step: implement Slurm exact-label materializer (`issue27cd`) before any model replay.
