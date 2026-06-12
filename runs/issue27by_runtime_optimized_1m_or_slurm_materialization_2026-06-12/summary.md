# issue27by Summary

- issue: `issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12`
- primary_verdict: `slurm_ready_per_file_pipeline_smoke_passed`
- target rows in strict 1M contract: `1000000`
- rows already covered by valid cache: `694000`
- rows in stateful ID train chain: `151000`
- rows still requiring Slurm/local jobs: `155000`
- model training: no
- formal benchmark: no
- key correction: non-ID jobs require a frozen ID train frontend state snapshot; they are not independent empty-state jobs.
- final/report-only roles remain sealed and forbidden for fit/threshold/support selection/model selection.
