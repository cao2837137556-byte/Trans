# CKBE HPC Python-3.9 compatibility fix — 2026-07-12

## What failed

The first CKBE cache handoff packaged `torch-geometric 2.8.0`.  That release
requires Python 3.10+, while the cluster's validated `issue27ckc` environment
is Python 3.9.21.  Environment preparation therefore failed before the event
plan was created; the subsequently submitted r1 array had no valid frozen
plan and must not be used.

## Final runtime policy correction

- The cluster policy prohibits user-managed package installation.  CKBE must
  source only `scripts/00_env_issue27ckc.sh`, which is the project-provisioned
  Python 3.9/Torch/PyG environment.
- The runtime gate imports NumPy, Torch, PyG, `fsspec`, and `TGNMemory`; no
  `pip`, wheelhouse, Conda creation, or container pull occurs.
- The `r1`/`r2`/`r3` bundle preparation scripts are explicitly superseded and
  must not be used for submission.
- The immutable plan and the single-source Slurm canary are created only after
  this read-only runtime check passes.

## Scientific contract unchanged

This is an environment and fail-fast handoff repair only.  It does not change
the raw source set, event message schema, source-local node reset, label-free
cache rule, fit/select/report boundaries, or held-family exclusions described
in CKBD.

## Validated locally

The packaged PyG 2.6.1 wheel successfully imported with `TGNMemory` in an
isolated compatibility smoke.  The HPC preparation still performs the
authoritative Python-3.9 import check before any Slurm work is submitted.
