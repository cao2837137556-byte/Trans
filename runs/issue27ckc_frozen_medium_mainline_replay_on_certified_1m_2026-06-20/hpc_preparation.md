# issue27ckc HPC Preparation

status: `slurm_ready_local_smoke_passed_full_run_not_started`

## Correction

`issue27ckb` was a raw static scorer ablation. It did not replay the strongest frozen medium architecture and therefore cannot answer the user's requested mainline-effect question.

`issue27ckc` is the corrective experiment:

```text
Kitsune115D
-> frozen medium full-115D attack scorer
-> parent OOD-risk
-> past-only temporal attack/OOD heads
-> bounded controller
```

## Frozen Data

- certified 1M benign/OOD asset;
- issue27cf 512-row support bank: 385 train and 127 validation;
- issue27ch 93 complete exact-label attack chunks;
- no reuse of the remaining attack candidate pool;
- OOD stress and certified query roles are read-only after freeze;
- sealed final attack/OOD are report-only.

## Matrix

- primary: medium weighted normal-to-attack mass ratio preserved on the larger fit set, seeds 42-46;
- control: strict historical support weight 4, seeds 42-46;
- total: 10 Slurm array jobs.

## Local Verification

- Python syntax: passed.
- Input and frozen-medium-config preflight: passed.
- One-job smoke: passed.
- Smoke aggregation: passed.
- Smoke outputs removed before packaging.

## Transfer Kit

`D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckc_frozen_medium_mainline_replay_hpc_20260620`
