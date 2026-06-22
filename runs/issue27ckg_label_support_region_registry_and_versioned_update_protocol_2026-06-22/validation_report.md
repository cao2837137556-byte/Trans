# issue27ckg Validation Report

Status: `PASS`

- Ten unique exact-label regions instantiated.
- All ten regions are active for label management regardless of geometry status.
- Unknown-traffic automatic label routing is disabled.
- Frozen 385 support-train and 127 support-val views reproduced with no overlap.
- Two legal simulated human labels entered archive/candidate flow.
- Duplicate, sealed, unknown-label, and incomplete-provenance fixtures were quarantined.
- Simulation-only budget promoted two candidates and produced a 387-row candidate training view.
- Production promotion remains disabled.
- No model training, controller change, sealed-final access, or initial-bank mutation occurred.
- Deterministic rerun passed for the registry, frozen train/validation views,
  archive/candidate schemas, promotion policy, archive and promotion audits,
  simulated candidate view, invariants, and final results.
