# CKBE HPC Python-3.9 compatibility fix — 2026-07-12

## What failed

The first CKBE cache handoff packaged `torch-geometric 2.8.0`.  That release
requires Python 3.10+, while the cluster's validated `issue27ckc` environment
is Python 3.9.21.  Environment preparation therefore failed before the event
plan was created; the subsequently submitted r1 array had no valid frozen
plan and must not be used.

## r3 correction

- Pin official `torch-geometric 2.6.1`, whose wheel metadata declares
  `Requires-Python: >=3.8`.
- Package the complete PyG direct runtime dependency closure, including
  `fsspec`, rather than incorrectly assuming it exists in the old cluster
  environment.
- Source `scripts/00_env_issue27ckc.sh` first, so NumPy/Torch come from the
  known cluster runtime rather than a bare virtual environment.
- Require a successful NumPy + Torch + `TGNMemory` import before emitting the
  26-source frozen plan.
- Use a new run id ending in `_r3`; no incomplete r1/r2 plan/cache is reused.
- `scripts/issue27ckbe_remote_prepare_r3.sh` prepares but does not submit.  A
  human may inspect only Slurm resource directives before the explicit array
  submission.

## Scientific contract unchanged

This is an environment and fail-fast handoff repair only.  It does not change
the raw source set, event message schema, source-local node reset, label-free
cache rule, fit/select/report boundaries, or held-family exclusions described
in CKBD.

## Validated locally

The packaged PyG 2.6.1 wheel successfully imported with `TGNMemory` in an
isolated compatibility smoke.  The HPC preparation still performs the
authoritative Python-3.9 import check before any Slurm work is submitted.
