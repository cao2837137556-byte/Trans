# Issue27l Next Action

Recommended next action: `issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset`.

Scope:
- acquire or construct a sufficiently large clean future/capture evaluation object;
- run split-aware original100 rebuild with `reset_at_split_boundary` and `train_state_then_eval_online`;
- then evaluate frozen LOW-GUARD++ and safer variants under report-only final eval.
