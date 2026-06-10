# Lightweight Temporal Evidence Head Spec

- This is a medium diagnostic, not a formal benchmark.
- The 115D Kitsune frontend, split, and support contract stay fixed.
- Each non-report-only role is split by past-only ordering into a fit half and a select half.
- Final OOD and sealed attack roles are replay-only and never used for fit or threshold/model selection.
- The temporal head compares three feature sets: current evidence only, past temporal only, and current evidence plus past temporal.
- Past temporal features were generated in issue27br with `shift(1)` rolling windows, so current/future rows are excluded.
- The controller is deliberately simple: attack head raw alarm, OOD-risk head suppresses only if high risk and not strong attack.
