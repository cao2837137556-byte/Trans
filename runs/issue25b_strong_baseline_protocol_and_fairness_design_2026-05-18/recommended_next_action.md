# Recommended Next Action

## Unique Recommendation

`issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18`

## Reason

Issue25b only designs the fairness protocol. It does not run baselines and cannot support any claim that Enhanced LOW-GUARD+ has beaten strong baselines.

The next scientific bottleneck is empirical comparison against:

- unsupervised anomaly baselines;
- semi-supervised / few-shot anomaly baselines;
- shallow nonlinear tabular baselines;
- internal ablations for representation, OOD guard, and support coreset.

## Stop Rule Before Issue25c

If execution preflight finds missing features, missing labels, missing validation split, missing support provenance, or inability to threshold a baseline under 1% OOD validation alarm, repair the asset first or mark the method diagnostic-only. Do not force an unfair baseline run.
