# Support Bank State Machine

This state machine governs support samples, not detector outputs.

```text
candidate
-> eligible_candidate
-> selected_support
-> support_train | support_val
-> active_memory
-> merged_memory | retired_memory | quarantined_memory
```

## State Definitions

- `candidate`: materialized row from a development-side attack candidate role.
- `eligible_candidate`: candidate row that passes exact-label, timestamp, role, and quarantine checks.
- `selected_support`: eligible candidate selected by a later issue under a declared budget.
- `support_train`: selected support row allowed for model fitting or attack head fitting in later issues.
- `support_val`: selected support row allowed for support-side validation/calibration in later issues.
- `active_memory`: support row currently active in the support bank.
- `merged_memory`: row retained for provenance after region merge, not necessarily active for training.
- `retired_memory`: row kept for audit but not used for training.
- `quarantined_memory`: row excluded from training, selection, calibration, and controller tuning.

## Illegal Transitions

- final/report-only role -> any support state.
- Benign/Unknown row -> eligible candidate.
- quarantined row -> selected support.
- support_val -> support_train without a new explicit issue and new manifest.
- unselected candidate -> model training.

