# issue27ckb HPC Preparation

status: `slurm_ready_local_smoke_passed_full_run_not_started`

## Purpose

Run a static offline capability snapshot while the online deployment protocol and attack-region evidence contract continue to be developed locally.

This run may diagnose model capacity, support-query transfer, benign-OOD false alarms, and sealed replay stability. It cannot establish online deployability or formal benchmark performance.

## Frozen Experiment Matrix

- HistGradientBoosting with support weight 64, seeds 42/43/44.
- HistGradientBoosting with support weight 256, seeds 42/43/44.
- Balanced logistic regression baseline.
- No automatic winner promotion.

## Data Reuse

The HPC already contains:

- the Gotham archive under the paper04 data root;
- the certified 1M Kitsune115 benign/OOD asset from issue27by/issue27bz;
- the 99 exact-label attack chunk outputs from issue27cd.

The new transfer kit uploads no large dataset. It contains only:

- the issue27ckb runner;
- frozen support/chunk contracts;
- Slurm/bootstrap/status/validation scripts;
- optional CPython 3.9 Linux wheels for scikit-learn and dependencies.

## Transfer Kit

Local path:

`D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckb_offline_capability_hpc_20260618`

Remote upload path:

`/public/home/jiangxinwei.zr/work/_upload_issue27ckb`

## Local Verification

- Python syntax check: passed.
- Plan/input preflight: passed.
- Seven-job smoke execution: passed.
- Smoke aggregation: passed.
- Full-data Slurm run: not started.

Smoke outputs were removed after verification and are not part of the transfer delta or tracked issue artifacts.
