# Formal Fairness Contract

- Same split for every method.
- Same feature schema for every method.
- No final eval for model, threshold, feature, support, or hyperparameter selection.
- Same official OOD alarm budget: 1%.
- Report detection mean/min, final OOD alarm max, feasible rate, OOD val alarm, threshold, and seed stability.
- Interface-incomplete models must be labeled `implementation_incomplete`, not method failure.
- Collapse-prone models must be retested; old collapse does not carry into the reset benchmark.
