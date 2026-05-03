# Postprocess Recovery Note

The E1 benchmark measurements completed and wrote `deployment_cost_table.csv`, `deployment_cost_aggregate.csv`, `benchmark_config.json`, and `env.txt` before the initial summary rendering step failed.

This recovery step regenerated only `summary.md`, `manifest.json`, `stderr.log`, and this note from the already-written CSV/JSON outputs. It did not rerun benchmark timing, retrain any backbone, modify split/seed/budget settings, or alter measured CSV values.

This is a process-transparency note, not a benchmark-result warning.
