# issue27cf Validation Report

Status: `PASS`

Validation checks:

- `config.json`, `run_spec.json`, and `support_bank_hashes.json` parse successfully.
- `eligible_candidate_manifest.csv.gz` contains `69492` eligible candidate rows.
- `support_bank_sidecar.csv` contains `512` selected support-bank rows.
- `support_train_indices.csv` contains `385` rows.
- `support_val_indices.csv` contains `127` rows.
- `support_train` and `support_val` candidate IDs are disjoint.
- `role_access_audit.csv` reports pass for source role, final/report-only exclusion, train/val disjointness, and candidate reuse lock.
- `invariant_validation.csv` reports no invariant errors.

Scientific boundary:

- No model training was performed.
- No detection metric was computed.
- No `dev_future_attack_query`, `sealed_final_attack`, or final/report-only role was used for support selection.
- Unselected candidate reuse remains `pending_forbidden_until_explicit_issue`.

Remaining blocker:

- `issue27cd` still has partial `dev_future_attack_query_exact` chunks localized to combined-cycle-1. Model replay remains blocked until issue27cg repairs or replans that query alignment.
