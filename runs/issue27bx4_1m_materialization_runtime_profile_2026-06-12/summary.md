# issue27bx4 summary

- issue: issue27bx4_1m_materialization_runtime_profile_2026-06-12
- primary_verdict: cache_aware_1m_runtime_profile_blocked_by_local_runtime_bottleneck
- target_rows: 1000000
- completed_rows_before_interrupt: 845000
- missing_rows: 155000
- canonical_1m_asset_status: not_created; interrupted partial X/y/sidecar were renamed with `INCOMPLETE_INTERRUPTED_` to prevent accidental use.
- strict_data_cleanliness: preserved. No cross-role fallback, no final/report-only data used for fit/threshold/support selection/model selection, no model training, no formal benchmark.
- cache_status_summary: {'disabled_stateful_id_train': 7, 'hit': 20, 'miss_written': 6}
- blocker: `processed/iotsim-building-monitor-1.csv` under `dev_future_attack_query` did not complete after more than 70 minutes of active local CPU time; stderr remained empty.
- interpretation: 500k cache-aware materialization is stable; 1M local expansion exposed a real per-file Kitsune115 runtime bottleneck on a high-cost attack trace.
- next_recommended_issue: issue27by_runtime_optimized_1m_or_slurm_materialization
