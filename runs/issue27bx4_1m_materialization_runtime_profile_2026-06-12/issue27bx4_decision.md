# issue27bx4 Decision

primary_verdict = cache_aware_1m_runtime_profile_blocked_by_local_runtime_bottleneck

The 1M asset was not certified. The run completed 845,000 rows and then exposed a local runtime bottleneck on the additional `dev_future_attack_query` attack file `processed/iotsim-building-monitor-1.csv`. Because the strict contract forbids cross-role fallback and final/report-only reuse, the correct decision is to stop and record the bottleneck rather than force a dirty 1M asset.

This does not invalidate issue27bx3 500k. It says the next scale-up step must include runtime optimization, stronger per-file progress logging, or Slurm for high-cost attack traces.
