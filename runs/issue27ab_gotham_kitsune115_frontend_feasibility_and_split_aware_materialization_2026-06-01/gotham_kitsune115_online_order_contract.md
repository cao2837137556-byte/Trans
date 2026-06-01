# Gotham Kitsune115 Online Order Contract

## reset_at_split_boundary
- Each role/file initializes a fresh frontend state.
- No frontend state crosses split roles.
- This is the cleanest contamination control and a conservative reference.

## train_state_then_eval_online
- Build `S_train_after_id` from ID benign train only.
- OOD validation uses a clone of `S_train_after_id` and is discarded after validation-side use.
- Final OOD eval uses a report-only clone of `S_train_after_id` and is discarded; it does not feed support or attack eval.
- Attack support uses a clone of `S_train_after_id`.
- Attack eval uses a clone of the post-support state and is report-only.
- This branch-based order prevents final eval packets from contaminating later state.
