# CKBV r17 Post-formal Pool-Semantic Recovery

Status: `FROZEN_FOR_METADATA_ONLY_RECOVERY`

## Scope

AMD job `154917` completed the seed-27 formal model computation and emitted
the registered scientific result.  It then exited in
`phase=validate_and_pack` because the validator expected the raw51 mask
composition in `core_ood_val_select`, although the frozen role contract places
all 1,353 masked `hydraulic-system-1` rows in `ood_val / fit`.

The duplicate Intel job `154918` reached the same terminal condition.  r17
recovers only AMD job `154917`; it does not combine partitions or treat them as
independent scientific seeds.

## Authoritative pool semantics

The immutable `ckbu_role_usage_audit.csv` proves the GLOBAL fit provenance:

| role | eligible | frozen | outside frozen cohort | incomplete |
| --- | ---: | ---: | ---: | ---: |
| `id_calib` | 0 | 0 | 0 | 0 |
| `ood_val` | 8,682 | 8,682 | 0 | 0 |
| `ood_stress` | 0 | 0 | 0 | 0 |

Therefore the already-emitted `core_fit_benign` sensitivity rows may be
relabelled, without changing their values, as the explicit
`core_ood_val_fit` audit:

- full: 8,682;
- observable: 7,329;
- masked: 1,353;
- sole masked source:
  `processed/iotsim-hydraulic-system-1.csv`.

The frozen select pool remains empty:
`core_ood_val_select = 0 / 0 / 0`.  The select C1/gate rows contain no masked
records, so the correction cannot alter gate or threshold selection.

## Recovery boundary

r17 is metadata-only.  It:

1. requires the source Slurm job to remain `FAILED`;
2. requires `job_failure.txt` to record `phase=validate_and_pack`;
3. verifies the role-usage provenance above;
4. preserves the original sensitivity audit as
   `ckbu_raw51_mask_sensitivity_audit.pre_pool_semantic_recovery.csv`;
5. atomically adds only the missing `core_ood_val_fit` composition rows;
6. hashes all scientific outputs before and after and rejects any change;
7. reruns the corrected validator and creates the pullback archive.

It does not submit Slurm work, retrain a model, re-decode a PCAP, change a
score, modify a gate or threshold, alter a target denominator, or open a new
held set.

The local bundle builder is compatible with Windows PowerShell 5.  Its
relative-path helper is root-confined and exercised before payload hashing;
the archive is then clean-extracted and revalidated.  Independent archive
inspection rejected `r18` because its staging contract generated Python
bytecode.  The builder now uses `python -B` and fails closed on
`__pycache__`, `.pyc`, or `.pyo`; only the `r19` artifact is uploadable.

## Scientific result

The scientific decision remains `NO_GO`.  The result is nevertheless valid
and must be archived because it supplies a real route signal:

- all required held OOD families improve by at least 5 percentage points and
  end at or below 90% hard rate;
- overall attack hard recall improves by about 7.416 percentage points;
- review remains zero;
- a major attack-family recall drop still exceeds the 2 percentage-point
  preservation limit.

The recovery makes this completed result auditable and pullable; it does not
turn `NO_GO` into `GO`.

## Permanent regression gate

Future formal finalization must emit and validate both pool identities:

- `core_ood_val_fit = 8682 / 7329 / 1353`;
- `core_ood_val_select = 0 / 0 / 0`.

The combined fit count is insufficient evidence by itself.  Finalization must
also verify the independent immutable role audit and reject any non-zero
`id_calib` or `ood_stress` contribution, any select leakage, or any scientific
output hash drift.
