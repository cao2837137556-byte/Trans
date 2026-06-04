# Coverage-Aware Active Labeling Protocol

This issue is a mechanism viability diagnostic, not a formal benchmark.

## Prospective Replay

- The previous new heldout probe is consumed here as a development-side heavy incoming stream.
- For each heavy file, the first 1000 rows are treated as unlabeled active-label candidates.
- The remaining rows form `dev_heavy_query_after_active_labeling` and are report-only.
- Candidate labels are hidden during selection; selected rows are then sent to an oracle to simulate analyst labeling.

## Gate

- Coverage-aware selection uses support distance and feature diversity only.
- OOD-safe calibration uses `id_calib`, `ood_val`, and base `support_val` only.
- Final OOD, medium attack_eval, and dev query are report-only.

## Caveat

Because this consumes the previous new heldout probe as a development stream, a future clean heavy final set is required before any formal claim.
