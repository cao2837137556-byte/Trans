# issue27bx3 Summary

1. issue27bx3 completed: yes
2. primary_verdict: `cache_aware_500k_materialization_ready_for_1m_runtime_profile`
3. materialized rows: `500000`
4. feature columns: `115`
5. role counts: `{"id_benign_train": 151000, "id_benign_calib": 30000, "ood_benign_val": 24000, "ood_benign_stress": 80000, "sealed_final_ood": 55000, "attack_support_candidate_pool": 45000, "dev_future_attack_query": 80000, "sealed_final_attack": 35000}`
6. model-ready counts after warmup: `{"id_benign_train": 150650, "id_benign_calib": 29750, "ood_benign_val": 23500, "ood_benign_stress": 79950, "sealed_final_ood": 54950, "attack_support_candidate_pool": 44950, "dev_future_attack_query": 79950, "sealed_final_attack": 34950}`
7. numeric finite pass: `True`
8. completed all file quotas: `True`
9. cache hits / cache writes: `0` / `20`
10. final/report-only used for fit/selection: `False`
11. model run: no
12. formal benchmark: no
13. X path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\kitsune115_larger_sanity_500k_v1\gotham_kitsune115_500k_train_state_then_eval_online_X.npy`
14. sidecar path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\kitsune115_larger_sanity_500k_v1\gotham_kitsune115_500k_train_state_then_eval_online_sidecar.csv.gz`
15. next recommended issue: `issue27bx4_1m_materialization_runtime_profile` if this pass holds
16. commit/push: not performed
