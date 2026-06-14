# Initial Support Bank Contract v1

This contract separates the large `attack_support_candidate_pool` from the actual initial analyst-labelled support bank.

## Definitions

- `attack_support_candidate_pool`: development-side attack candidate rows that may be used to simulate analyst-confirmed support selection.
- `initial_support_bank`: a bounded labelled subset selected from the candidate pool.
- default candidate budget: `B=128` total attack rows, not per attack type or per region.
- default train/val split: 75% support_train and 25% support_val.
- budget grid audited: `[32, 64, 128, 256]`.
- main selector: `phase_file_balanced_kcenter_standardized115_v1`.

## Hard Rules

- Support can only come from `attack_support_candidate_pool` rows with `selection_allowed=true`, `model_ready_hint=true`, and `sealed_final=false`.
- `dev_future_attack_query`, `sealed_final_attack`, and `sealed_final_ood` are forbidden for support selection.
- `support_val` must remain separate from `support_train`.
- `B` is a global support budget, not a per-region budget.
- Attack regions are memory/prototype/routing units, not one model head per region.
- Region cap for this contract: `R_max=8`.
