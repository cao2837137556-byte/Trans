# Issue26b Execution Plan

## Recommended Issue26b Setting

Recommended next work item: `issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22`.

Reason: issue26a found no P0/P1 temporal candidate with low leakage risk. The best apparent temporal object is `chrono_early_train_late_eval`, but its eval bins overlap issue23/25c locked evidence. A cleaner path is to recover raw split metadata and construct a purged/embargoed future-window asset before formal validation.

## Cleanliness Judgment

- Current clean status: not clean for formal temporal proof.
- Fix required: recover timestamp / packet-order / bin provenance and define a pre-registered purged or embargoed split.
- If no unused future window exists after recovery, issue26b should stop at asset-gap documentation rather than run a dressed-up consistency check.

## Required Inputs

- raw stage2 manifest with row-level order or timestamps;
- attack-bin provenance and bin-to-time mapping;
- ID/OOD benign train/cal/val/eval source paths;
- frozen `selected_source_rich_top64` feature list/provenance;
- kcenter32 support selection rule and allowed attack-train pool;
- threshold protocol: ID calibration + OOD validation at official 1pct OOD target;
- final OOD/attack eval partitions marked report-only.

## Purge / Embargo

Use purge/embargo if train and eval windows are adjacent or if flow/session adjacency may leak near-duplicate traffic. The purge size must be pre-registered from metadata, not tuned on final attack/OOD results.

## Runtime / Slurm

- Local: metadata recovery, manifest construction, and one single-seed smoke.
- Slurm: only if the formal multi-seed matrix or raw parquet scan is large.

## Planned Matrix

- Method: frozen Enhanced LOW-GUARD+ top64 only for first formal temporal pass.
- Controls if cost allows: V1 original100 fixed guard LR, V2 top32 fixed guard LR, random32 top64 fixed guard LR.
- Seeds: smoke `42`; formal `42,43,44,45,46`; heldout robustness `47,48,49,50,51` only after smoke passes.
- Output files: summary.md, preflight, temporal_split_manifest.csv, support_provenance.csv, threshold_provenance.csv, method_comparison_by_seed.csv, method_comparison_summary.csv, leakage_audit_report.md, command.txt, config.json, run_spec.json, manifest.csv.
