# Issue26a Within-Dataset Temporal Validation Feasibility Summary

## Outcome

- Task type: within-dataset temporal / data-scale feasibility + evidence inventory.
- Formal temporal validation executed: no.
- Optional minimal temporal validation executed: no.
- Reason not run: No P0/P1 candidate has low leakage risk. The best available temporal candidate, chrono_early_train_late_eval, overlaps issue23/25c locked eval bins and requires purge/embargo plus metadata recovery before formal validation.
- Main method remains frozen: Enhanced LOW-GUARD+ top64 = selected_source_rich_top64 + kcenter32 + fixed OOD guard LR + 1pct OOD-validation-calibrated threshold.
- TopK/support/adapter/threshold changed: no.
- Final OOD/attack eval used for selection: no.
- Slurm needed for issue26a: no.

## What Temporal Evidence Is Most Needed After Issue25c

The project now needs a clean chronological or purged future-window validation object that was not used in top64 discovery, support selection, threshold selection, adapter choice, issue23 locked validation, or issue25c strong-baseline formation.

## What Existing Evidence Supports

- primary_lowood: primary/non-regression evidence under the current protocol.
- holdout_bin_2: hard-shift discovery evidence; useful consistency signal, not clean proof.
- chrono_late_train_early_eval: temporal-looking consistency evidence, but it participated in candidate confirmation/discovery and cannot be upgraded into formal temporal proof.
- locked bins 5/6/7/8: same-dataset locked validation evidence already used in issue23 and issue25c. They support current locked-bin claims but are not new temporal evidence.

## Claims Still Not Allowed

- Temporal generalization has been proven.
- External generalization has been proven.
- Consistency checks equal formal temporal validation.
- Repeated locked-bin analysis is a new clean validation.
- Second environment is no longer needed.

## Data-Scale Inventory Findings

- Existing ID/OOD slices are reasonably sized for lightweight inventory: ID train 8000, ID calibration 5000, OOD train 8000, OOD validation 2000, final OOD eval about 10000 in existing outputs.
- Attack eval size varies substantially by bin: holdout_bin_8 has only 426 attack eval rows, so worst-bin claims need row-count caveats.
- The project still has single-domain risk because all issue26a evidence is within-dataset.
- Raw timestamp/order metadata sufficient for a new purged formal temporal split was not recovered from the issue25c report pack.

## Clean Candidate Judgment

- Clean new temporal candidate found: no.
- Best partial candidate: `chrono_early_train_late_eval`.
- Why not clean: its late eval bins overlap issue23/25c locked bins 6/7/8, and purge/embargo metadata is not yet recovered.

## Issue26b Readiness

Issue26b can start as metadata recovery and temporal asset build, but not yet as formal validation. The recommended immediate next step is `issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22`.

## Slurm Judgment

Issue26a was local-only. Issue26b should remain local through metadata recovery and one smoke run. Slurm becomes appropriate only for large raw scans or multi-seed formal validation after the protocol is frozen.

## Second Environment Boundary

Second environment remains necessary for issue27. It is not part of issue26a and is not replaced by within-dataset temporal inventory.

## Files Read From Issue25c

Priority files read: baseline_method_comparison_summary.csv, locked_bins_baseline_summary.csv, ablation_component_summary.csv, consistency_primary_holdout_chrono.csv, low_fpr_metrics_baseline_summary.csv.
Available additional CSVs: baseline_candidate_definitions.csv, baseline_complexity_summary.csv, baseline_hyperparameter_validation_rows.csv, baseline_method_comparison_by_seed.csv, baseline_search_space.csv, baseline_selected_configs.csv, locked_asset_report.csv, locked_bins_baseline_by_seed.csv, manifest.csv, risk_register.csv, support_provenance.csv, threshold_provenance.csv.
