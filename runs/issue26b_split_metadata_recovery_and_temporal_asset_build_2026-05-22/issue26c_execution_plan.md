# Issue26c Execution Plan

## Recommended Issue26c Action

`issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`

## Why

Issue26b recovered bin-level provenance and support/threshold provenance, but not enough raw timestamp / packet-order / capture metadata to construct a low-leakage clean temporal validation object.

## Candidate Status

- `earlier-to-later`: partial, not clean; eval bins overlap issue23/25c locked evidence.
- `future-window holdout`: scientifically preferred, but unavailable until raw temporal metadata is recovered.
- `purged temporal split`: blocked by missing timestamp/order/capture metadata.

## Inputs Needed

- Raw stage2 manifest with row-level timestamp or packet order.
- Bin-to-time or capture-window mapping.
- Full attack eval row list per bin.
- ID/OOD benign split manifests with train/cal/val/eval labels.
- Pre-registered purge/embargo rule.

## Purge / Embargo

Required for any adjacent or future-window temporal split. Do not tune gap size on final eval metrics.

## Slurm

Not needed until a clean formal candidate is available. If raw manifests are large, do only a small local schema smoke and prepare Slurm for the full scan.

## Proposed Seeds For Future Formal Validation

- Smoke: `42`.
- Formal: `42,43,44,45,46`.
- Heldout robustness after smoke: `47,48,49,50,51`.

## Output File Plan

Future issue26c should write: `temporal_split_manifest.csv`, `support_provenance.csv`, `threshold_provenance.csv`, `method_comparison_by_seed.csv`, `method_comparison_summary.csv`, `leakage_audit_report.md`, `command.txt`, `config.json`, `run_spec.json`, and `manifest.csv`.
