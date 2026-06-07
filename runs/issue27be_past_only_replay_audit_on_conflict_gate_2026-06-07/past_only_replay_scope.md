# Past-Only Replay Scope

This issue is a small audit, not a new enhancement module.

- It reuses the frozen issue27bd gate configuration.
- It does not run a new grid search.
- It does not add temporal smoothing.
- It does not run a full/larger formal benchmark.
- It confirms report-only roles are replayed only after all fit/calibration/gate choices are frozen.

Important caveat: issue27bd used dev-side pseudo-query rows from support/active-label splits for shell calibration. These rows are not clean final evaluation, but they mean the result remains diagnostic rather than formal.
