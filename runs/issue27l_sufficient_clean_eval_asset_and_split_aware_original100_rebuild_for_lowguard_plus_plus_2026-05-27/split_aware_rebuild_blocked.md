# Split-Aware Rebuild Blocked

Split-aware rebuild/evaluation was not executed because the newly found full Mirai assets require a feature compatibility audit first.

Executable state strategies after compatibility is resolved:
- `continuous_state_baseline`: reproduce the existing feature CSV as a diagnostic reference;
- `reset_at_split_boundary`: rebuild or slice features with state reset per split, if original100/restored115 mapping is confirmed;
- `train_state_then_eval_online`: preferred deployment-like state strategy once raw/feature generation is pinned down.
