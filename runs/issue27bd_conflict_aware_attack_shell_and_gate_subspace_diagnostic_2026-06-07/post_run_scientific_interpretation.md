# Post-Run Scientific Interpretation

issue27bd is a medium diagnostic, not a formal benchmark.

## What Changed

issue27bc used strict full-115D purity gating and collapsed hard attack alarms to zero. issue27bd kept the raw attack detector on full Kitsune115, but moved prototype gate evidence into fixed Kitsune115 family subspaces and added a pseudo-query-calibrated outer attack shell with conflict-aware hard override.

The selected dev-frozen gate uses the `HH` subspace for prototype evidence:

- raw detector score space: full 115D
- prototype gate subspace: `HH`
- active-label budget: 64
- review budget: 3%
- final/report-only roles were not used for selection

## Key Results

- dev attack hard min: 0.642857
- report-only attack hard min: 0.628750
- OOD val hard max: 0.000000
- OOD stress hard max: 0.007368
- final OOD hard max report-only: 0.019667
- final OOD review max report-only: 0.030000

## Reading

This is a real improvement over issue27bc because attack hard alarms are no longer collapsed to zero. The result supports the idea that gate evidence does not have to use the same full-115D space as the raw detector.

However, it is still below the paper-grade target:

- report-only attack hard min is only about 0.63, not high enough;
- final OOD report-only hard is about 1.97%, still above the 1% target;
- review is bounded at 3%, but this does not make the run formal.

## Next Step

The recommended next step is not full/larger benchmark. The next issue should either:

1. add a past-only temporal consistency diagnostic on the selected conflict-aware shell gate, or
2. if we want to stay single-packet first, refine the HH-subspace attack shell and final-OOD veto using only dev-side roles.

No final/report-only role should be used for tuning either path.
