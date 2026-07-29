# CKBV r20 Run-Grounded Post-Formal Pool Recovery

Status: `FROZEN_FOR_METADATA_ONLY_RECOVERY`
Supersedes: `ckbv_r17_postformal_pool_semantic_recovery_20260729.md`
Date: 2026-07-29

## Why r17/r19 failed closed

The r17/r19 recovery hard-coded planning-document constants
(`id_calib=0, ood_val=8682`, fit composition `8682/7329/1353`) and claimed
they were proven by the immutable role-usage audit.  Executed against AMD job
`154917`, it failed closed on the run's own evidence before writing anything.
Failure-ledger Section 18 records the classification and permanent gates.

## Run-grounded truth (every constant below cites an immutable artifact)

From `ckbu_role_usage_audit.csv` (GLOBAL and every held protocol,
`frame_phase=fit, m1_phase=fit`):

| role | rows |
| --- | ---: |
| `support_train` | 385 |
| `id_calib` | 809 |
| `ood_val` | 2,604 |
| `ood_stress` | 0 |

All select-phase rows are 0 for every benign role.

From `ckbu_raw51_mask_sensitivity_audit.csv` (GLOBAL):

- `core_fit_benign = 3413/3413/0` — exactly `809 + 2,604`, all observable;
- `core_select_benign = 0/0/0`;
- `core_ood_val_select = 0/0/0`;
- no pool anywhere contains a masked row.

From `ckbu_environment.json` and `run_spec.json` (`raw51_observable_v1`):

- frozen targets 325,067; observable 323,714; masked 1,353;
- masked source `processed/iotsim-hydraulic-system-1.csv`;
- mask SHA-256 `b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df`;
- masked rows are fail-closed.

Interpretation: the raw51 mask acted at the frozen-target materialization
layer.  The 1,353 masked `hydraulic-system-1` rows never entered any pool this
run drew, which is why every pool reports zero masked rows.  The
`8682/7329/1353` planning figures describe that upstream target universe, not
pool composition, and must not be asserted as pool rows.

## Recovery action (metadata-only)

Against the untouched run root of AMD job `154917` (Slurm state `FAILED`,
`job_failure.txt` = `phase=validate_and_pack`):

1. preserve the original sensitivity audit as
   `ckbu_raw51_mask_sensitivity_audit.pre_pool_semantic_recovery.csv`
   (kept from r19 naming; created only if absent);
2. append only explicit, truthful derived rows:
   - `core_id_calib_fit` role_split row `809/809/0`;
   - `core_ood_val_fit` role_split row `2604/2604/0`;
   - a `target_materialization` row `325067/323714/1353` and the named masked
     source `processed/iotsim-hydraulic-system-1.csv` `1353/0/1353`;
3. require the arithmetic closure `809 + 2604 = 3413` against the already
   emitted `core_fit_benign` total;
4. hash all scientific outputs before and after; any change aborts;
5. rerun the corrected validator and create the pullback archive.

It does not submit Slurm work, retrain, re-decode PCAPs, recompute
checkpoints, change scores/gates/thresholds/denominators, or alter the
registered `NO_GO` decision.

## Corrected validator constants

- `core_id_calib_fit = 809/809/0` and `core_ood_val_fit = 2604/2604/0`,
  summing to `core_fit_benign = 3413/3413/0`;
- `core_ood_val_select = 0/0/0` and zero masked rows in every pool;
- select C1/gate rows contain zero masked rows;
- target-materialization mask row `325067/323714/1353` with the named source,
  cross-checked against `ckbu_environment.json` and `run_spec.json`;
- the independent role-usage audit must show fit `id_calib=809, ood_val=2604,
  ood_stress=0` and zero benign select usage.

## Scientific result (unchanged)

`NO_GO`: all four held OOD families improve by at least 5 pp and end at or
below 90% hard rate; overall attack hard recall improves about 7.416 pp;
review is zero; one major attack family still violates the 2 pp preservation
gate.  Seeds 37/47 remain locked; cooler-motor remains sealed.

## Permanent regression gate

Per failure-ledger Section 18: validator/recovery constants must cite named
run artifacts; arithmetic closure must hold; mask evidence is asserted only at
the materialization layer; scientific-hash verification is mandatory; local
negative cases (wrong provenance, fit drift, select leakage, idempotent
rerun) must pass before bundle construction.
