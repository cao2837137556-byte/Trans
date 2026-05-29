# LOW-GUARD++ Failure Diagnosis Plan

issue27p does not show a uniform LOW-GUARD++ collapse; it shows instability:

- LOW-GUARD++ mean/min/OOD max = `0.731811` / `0.096397` / `0.028139`.
- Worst detection seed = `44` with detection `0.096397`.
- Worst OOD seed = `42` with final OOD alarm `0.028139`.

Minimum diagnosis:

1. Score distribution by seed for ID_train, OOD_train, ID_calib, OOD_val, final_OOD, support, and attack_eval.
2. Attack_eval row-block or cluster stratification, especially for seed `44`.
3. kcenter32 support coverage audit against attack_eval clusters and nearest-support distances.
4. HistGB feature importance and top-column ablation under anonymous clean115.
5. Validation-only threshold target curve; final eval remains report-only.
6. Bounded train/val-only repair tests: support k=32/64/128, OOD weight sensitivity, and small HistGB conservative grid.

The diagnosis must not use final eval to choose a repaired configuration. A repair that only wins by final eval selection is invalid.
