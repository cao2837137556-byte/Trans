# Recommended Next Action

## Verdict

Issue16b verdict: `mixed_or_negative`.

Reason: Fixed guard keeps OOD high alarm feasible, but at least one pre-registered harder holdout has weak 32-shot attack detection (minimum mean=0.222700).

## Next Step

Treat this as boundary evidence. Prioritize failure analysis and same-protocol few-shot anomaly baselines; do not upgrade to complex adapters yet.

## Priority

1. Analyze why `holdout_bin_2` has weak attack recovery before running more model variants.
2. Run same-protocol few-shot anomaly baselines to determine whether LOW-GUARD-minimal is still competitive on this harder holdout.
3. Run OOD target sensitivity only after preserving threshold/support provenance.
4. Do not claim second-environment validation from this run.
5. Do not upgrade to MLP/prototype/full neural GDA until the harder-holdout failure mode and baseline gap are understood.
