# Preflight LOW-GUARD+ Repair Check

- Method development uses train/support plus ID calibration and OOD validation only: True.
- source_rich row counts align with original100: True (`ID=(50000, 260)`, `OOD=(20000, 260)`, `attack=(10000, 260)`).
- Feature selection uses attack eval / final OOD eval: False.
- Margin hard negatives use final OOD eval / attack eval: False.
- Support comes from local harder-holdout attack train pool: True.
- K-center support uses eval: False.
- Main OOD target remains 1%: True.
- 0.5% / 2% are sensitivity only: True.
- original100 fixed-guard LR baseline retained: True.
- Large neural sweep performed: False.
- Calibration slice note: issue19 follows the issue17/issue18 repair-line local-calibration slice for direct comparison to kcenter support repair; this is recorded as a comparability caveat, not hidden.
