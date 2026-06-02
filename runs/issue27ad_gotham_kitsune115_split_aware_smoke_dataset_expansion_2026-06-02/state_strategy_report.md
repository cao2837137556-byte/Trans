# State Strategy Report

- `reset_at_split_boundary`: each file/role starts with a fresh frontend state.
- `train_state_then_eval_online`: ID benign train builds the frontend train state; every OOD/final/attack file uses an isolated clone of that train state and is discarded after extraction.
- Attack support state is not carried into attack eval in this smoke expansion, avoiding support/eval frontend-state contamination.
