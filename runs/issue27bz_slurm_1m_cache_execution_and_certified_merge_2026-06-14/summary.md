# issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14 Summary

1. issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14 completed: yes
2. primary_verdict: `slurm_1m_certified_asset_ready_for_larger_sanity_replay`
3. materialized rows: `1000000`
4. feature columns: `115`
5. role counts: `{"id_benign_train": 151000, "id_benign_calib": 80000, "ood_benign_val": 24000, "ood_benign_stress": 230000, "sealed_final_ood": 155000, "attack_support_candidate_pool": 90000, "dev_future_attack_query": 235000, "sealed_final_attack": 35000}`
6. model-ready counts after warmup: `{"id_benign_train": 150650, "id_benign_calib": 79600, "ood_benign_val": 23500, "ood_benign_stress": 229900, "sealed_final_ood": 154900, "attack_support_candidate_pool": 89900, "dev_future_attack_query": 234850, "sealed_final_attack": 34950}`
7. numeric finite pass: `True`
8. completed all file quotas: `True`
9. cache hits / cache writes: `28` / `0`
10. final/report-only used for fit/selection: `False`
11. model run: no
12. formal benchmark: no
13. X path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\kitsune115_larger_sanity_1m_certified_v1\gotham_kitsune115_1m_certified_train_state_then_eval_online_X.npy`
14. sidecar path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived\kitsune115_larger_sanity_1m_certified_v1\gotham_kitsune115_1m_certified_train_state_then_eval_online_sidecar.csv.gz`
15. next recommended issue: `issue27ca_larger_sanity_replay_on_certified_1m_asset` if this pass holds
16. commit/push: not performed

## issue27bz Additional Certification

- HPC validation was checked before merge and was PASS.
- No quarantine cache was used; local stale quarantine files are ignored.
- Non-ID rows came from completed valid caches; ID train rows were regenerated as the stateful train chain.
- This asset is a data asset only; it is not a model result.
