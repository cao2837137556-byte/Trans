# issue27ab Summary

1. issue27ab complete: yes.
2. primary_verdict: `kitsune115_blocked_by_pcap_label_alignment`.
3. Formal frontend route: Gotham raw PCAP -> restored Kitsune/AfterImage/netStat 115D.
4. Existing original frontend status: original checked-in netStat emits 100D because Hstat is commented.
5. Restored 115D status: Host BW Hstat restored explicitly in the issue27ab script; original files left unchanged.
6. Feature schema count: `115`.
7. Feature schema hash: `21e49ad2c80614c16012ea8fc2cb1df54db54071a060ab14025d58775703e8d6`.
8. Smoke packet limit per selected PCAP: `1500`.
9. Warmup/grace packets per state: `100`.
10. Attack-onset CSV scan row limit: `100000`.
11. State strategies executed: `reset_at_split_boundary`, `train_state_then_eval_online`.
12. Strategy shape results: `[{"strategy": "reset_at_split_boundary", "rows": 4128, "columns": 115, "has_115_columns": true, "nan_count": 0, "inf_count": 0, "finite_rate": 1.0, "warmup_packets_per_role": 100, "model_metric_computed": false}, {"strategy": "train_state_then_eval_online", "rows": 4128, "columns": 115, "has_115_columns": true, "nan_count": 0, "inf_count": 0, "finite_rate": 1.0, "warmup_packets_per_role": 100, "model_metric_computed": false}]`.
13. PCAP/label alignment blocked: `true`.
14. Numeric instability blocked: `false`.
15. Future contamination audit: pass under branch-based train-state strategy; final OOD eval is report-only and discarded.
16. Model metrics computed: no.
17. Strict 8D feature artifact role: engineering smoke only; not formal method-ranking input.
18. issue27ac recommendation: attack-onset alignment, then broader split-aware Gotham Kitsune115 materialization.
19. Slurm needed: likely for full causal attack-onset extraction if pure Python AfterImage remains slow.
20. commit hash: recorded in final response.
