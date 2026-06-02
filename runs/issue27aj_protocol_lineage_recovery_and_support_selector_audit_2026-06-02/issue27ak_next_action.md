# Issue27ak Next Action

Recommended next task:

`issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`

## Required Scope

- Reuse the fixed issue27af/issue27ag Gotham Kitsune115 medium asset.
- Do not re-split data.
- Do not change support pool membership.
- Implement recovered `kcenter32` support selection on the `attack_support`
  role only.
- Emit support selector audit files and selected support hash.
- Then run only medium diagnostic guarded-protocol checks if the selector audit
  passes.

## Boundary

This remains a medium diagnostic. It is not a formal benchmark, does not decide
the final mainline, and cannot use final OOD eval or attack eval for selection.
