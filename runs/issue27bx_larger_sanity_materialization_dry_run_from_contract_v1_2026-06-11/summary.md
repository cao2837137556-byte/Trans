# issue27bx Summary

1. issue27bx completed: yes
2. primary_verdict: `larger_sanity_materialization_partial_needs_quota_or_frontend_fix`
3. strategy materialized: `train_state_then_eval_online`
4. emitted rows: `226355`
5. feature columns: `115`
6. role counts: `{"id_benign_train": 65751, "id_benign_calib": 5832, "ood_benign_val": 14772, "ood_benign_stress": 35000, "sealed_final_ood": 35000, "attack_support_candidate_pool": 20000, "dev_future_attack_query": 35000, "sealed_final_attack": 15000}`
7. model-ready counts after warmup: `{"id_benign_train": 65151, "id_benign_calib": 5682, "ood_benign_val": 14272, "ood_benign_stress": 34350, "sealed_final_ood": 34900, "attack_support_candidate_pool": 19900, "dev_future_attack_query": 34850, "sealed_final_attack": 14950}`
8. numeric finite pass: `True`
9. completed all file quotas: `False`
10. final/report-only used for fit/selection: `False`
11. model run: no
12. formal benchmark: no
13. state hash mode: `lightweight_local_pilot_no_pickle_state_hash`
14. local pilot caveat: role-complete ~250k local smoke after the 1M local attempt exposed slow attack-PCAP extraction; exact pickle state hashes are deferred
15. X path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\kitsune115_larger_sanity_v1\gotham_kitsune115_larger_sanity_train_state_then_eval_online_X.npy`
16. sidecar path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\kitsune115_larger_sanity_v1\gotham_kitsune115_larger_sanity_train_state_then_eval_online_sidecar.csv.gz`
17. next recommended issue: `issue27by_larger_sanity_replay_current_frozen_system` if pilot passes, otherwise quota/frontend repair
18. commit/push: not performed
