# CKBQ auxiliary warm-up validator correction (2026-07-21)

## Scope

This correction applies only to validation and recovery of the completed
CKBQ seed-27 AMD run `153037`. It does not retrain a model, change any score,
select a different gate, open a report label during fit/select, or alter the
frozen 1M split.

## Deterministic mismatch

The frozen CKBO auxiliary contract materializes 600 model-ready rows after
`WARMUP_PACKETS=500`. CKBQ correctly reused that contract: auxiliary temporal
record index zero is normalized to raw event position 500, so its raw9 window
is aligned with the same packet that produced the frozen CKBO/AfterImage row.
The formal AMD run therefore emitted 1,100 events per auxiliary source, a
target offset of 500, and 600 target rows.

The original CKBQ validator and one preregistration sentence incorrectly
hard-coded 856 events and offset 256. That stale check rejected the completed
run after `CKBQ_FORMAL_COMPLETE`; it was not a training, data, memory, Slurm,
or scientific-decision failure. Changing the model to offset 256 would be
incorrect because it would misalign the temporal packet with the frozen
auxiliary feature row.

## Corrected validation

The validator now derives each source's expected warm-up, target count, role,
and raw path from the frozen `ckbo_auxiliary_benign_manifest.csv`. It requires:

- the frozen warm-up to remain 500 and model-ready count to remain 600;
- temporal `events = warmup + target_rows` and `target_offset = warmup`;
- exact role and raw-source agreement across manifests;
- exact target-position SHA-256 recomputation;
- exact temporal-cache SHA-256 recomputation;
- exact auxiliary-temporal manifest SHA-256 agreement with the environment
  record;
- unchanged label-free, source-anonymous, current-inclusive, future-free
  causality fields.

The failed Slurm state remains part of provenance. Recovery is permitted only
after verifying that the formal program emitted `CKBQ_FORMAL_COMPLETE` and
that the sole terminal error was the stale auxiliary temporal validator.

The first recovery validator reproduced only the target-position payload
bytes. CKBQ's `sha256_arrays` contract also prefixes the NumPy dtype and shape,
so that recovery attempt conservatively rejected all 31 sources without
packing. The corrected recovery reproduces the complete
`dtype || shape || payload` digest. This second validator-only correction also
does not change or rerun the experiment.

## Scientific boundary

The recovered result remains the preregistered seed-27 `NO_GO`: it contains a
real multi-held OOD suppression signal but violates attack-preservation
constraints. Validator recovery does not promote it to a positive result.
