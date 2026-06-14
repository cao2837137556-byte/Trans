# issue27cc Next Action

Recommended next task:

`issue27cc_targeted_multitype_attack_materialization_and_onset_realign`

Purpose:

- Do not train models.
- Do not change the 115D frontend.
- Do not use final/report-only rows for support selection.
- Use `targeted_multitype_materialization_request.csv` to materialize development-side attack support candidates across multiple attack types and onset phases.
- Rebuild dev query / sealed final attack only with exact label/onset checks, keeping them report-only.
- Require exact per-row CSV label audit before any later support bank or model replay.

Why:

- Current 1M support pool has useful multi-type signal after exact-label audit, but it misses major support-file attack types.
- Current dev/final attack roles contain substantial benign-prefix/onset alignment risk.
- Running model replay before this would mix support taxonomy uncertainty with model behavior.
