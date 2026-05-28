# Original100 Reconstruction Report

Reconstruction feasibility:

| role | has_feature_name_mapping | can_call_netstat_afterimage | source_vs_existing_extraction_allclose | can_reconstruct_continuous_state_baseline | can_reset_at_split_boundary | can_train_state_then_eval_online | rebuild_not_executed_full | reason_not_full_rebuilt |
|---|---|---|---|---|---|---|---|---|
| id | True | True | True | True | True | True | True | Existing extracted feature cache already aligns; full split-aware rebuild should be issue27l after split is chosen. |
| ood | True | True | True | True | True | True | True | Existing extracted feature cache already aligns; full split-aware rebuild should be issue27l after split is chosen. |
| attack | True | True | True | True | True | True | True | Existing extracted feature cache already aligns; full split-aware rebuild should be issue27l after split is chosen. |


Key points:
- Feature name mapping exists for all three roles.
- Kitsune `netStat.py` / `AfterImage.py` are available and define the original100 stream statistics.
- Current source matrices align with previously extracted feature caches by row order.
- Full split-aware re-extraction was not executed in this issue because no clean purged split was selected.
- `reset_at_split_boundary` and `train_state_then_eval_online` are implementable, but should be run only after selecting a clean split to avoid producing unused experimental artifacts.
