# Gotham115 Migration Plan

## Purpose

Migrate the recovered old `kcenter32` support selector and guarded protocol
permissions to Gotham Kitsune115 medium diagnostics. This is not a formal
benchmark and does not import old performance claims.

## Fixed Inputs

- Dataset asset: issue27af/issue27ag Gotham Kitsune115 medium asset certificate
- Feature schema: Gotham Kitsune-style 115D
- Split: already fixed by prior Gotham contract
- Support pool: only rows with role `attack_support`
- Report-only roles: `final_ood_benign_eval` and `attack_eval`

## Selector Migration

1. Load the fixed Gotham115 medium asset through the existing immutable loader.
2. Select candidate rows only from the `attack_support` role.
3. Fit selector-local `StandardScaler` only on attack_support feature rows.
4. Run Euclidean farthest-first k-center with budget 32.
5. Output `support_indices_32`, selector configuration, role-access audit, and
   hash of selected global row IDs.
6. Verify no selected row comes from `attack_eval`, `final_ood_benign_eval`,
   `ood_benign_val`, or benign training roles.

## Forbidden Access

- Do not use `final_ood_benign_eval` for support selection, thresholding,
  model selection, feature selection, or hyperparameter selection.
- Do not use `attack_eval` for support selection, thresholding, model
  selection, feature selection, or hyperparameter selection.
- Do not re-split or re-materialize the medium asset in issue27ak.

## Next Diagnostic

The next issue should be
`issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.

It should compare the recovered kcenter32 support selector against the
diagnostic first32 placeholder only as a protocol sanity/diagnostic check, not
as a formal model ranking.
