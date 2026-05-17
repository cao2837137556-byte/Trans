# Preflight Support Provenance Check

- Harder holdout support attack pool is local to each harder holdout attack train pool: True.
- Support selection uses only attack train pool features: True.
- Support has no overlap with attack eval / attack validation: True.
- Support selection uses final OOD eval or attack eval: False.
- Local calibration protocol follows issue16b: True.
- Scaler fit scope is ID train + OOD train + selected supports: True.
- Threshold source is ID calibration + OOD validation only: True.
- OOD weight changed from 2: False.

Preflight status: `True`.
