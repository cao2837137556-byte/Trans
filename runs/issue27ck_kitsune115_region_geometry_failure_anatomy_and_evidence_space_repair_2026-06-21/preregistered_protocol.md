# issue27ck Preregistered Protocol

## Fixed Inputs

- issue27cf support bank: 385 train, 127 validation;
- issue27ch complete-only certified attack subset;
- ID train for transformation fitting only;
- OOD val for qualification;
- OOD stress and certified dev query read-only after selection;
- sealed final roles forbidden.

## Evidence Spaces

- S0: raw robust-scaled global Euclidean control.
- S1: ID q0.001/q0.999 winsorization, signed log1p for mean/std/radius/magnitude/covariance features, then robust-scaled global Euclidean.
- S2: raw robust scaling with clipped within-family mean squared distance and equal weighting across MI_dir, H, HH, HH_jit, and HpHp.
- S3: S1 transformation plus S2 family-balanced distance.

All spaces retain one medoid per exact label and the issue27cj tight/medium/wide shell rules. No region split is executed.

## Activation Gates

An active-strong region requires:

- support train at least 12;
- support validation at least 3;
- true-region uncertain coverage at least 0.80;
- nearest-region exact-label consistency at least 0.80;
- at least two provenance sources;
- OOD-val direct core intrusion at most 0.001;
- OOD-val direct core+near intrusion at most 0.01.

## Route Decision

- GO: at least three active-strong regions across at least two semantic groups.
- LIMITED_GO: one or two active-strong regions.
- STOP: zero active-strong regions.

Only support-val and OOD-val may select the evidence space. Stress/query results cannot change the selected space or registry.
