# Issue26b Split Metadata Recovery And Temporal Asset Build Summary

## Outcome

- Task type: split metadata recovery + clean temporal asset build.
- Formal temporal validation executed: no.
- Model training executed: no.
- TopK/support/adapter/threshold changed: no.
- Final OOD/attack eval used for selection: no.
- Slurm used: no.

## 1. Was timestamp / packet-order / bin provenance recovered?

- Bin provenance: yes, at coarse attack-bin level from issue23/25c asset reports.
- Row/support provenance: partial, through support provenance and issue18 row-level score artifacts.
- Threshold provenance: yes, inspected assets record ID calibration + OOD validation and no final eval use.
- Raw timestamp / packet-order / capture/session provenance: no. Source code supports timestamp extraction, but current run assets do not persist a row-level timestamp or packet-order manifest for formal temporal splitting.

## 2. Available Metadata

- `locked_asset_report.csv` / `locked_validation_asset_report.csv`: train/eval bins, attack train-pool counts, attack eval counts.
- `support_provenance.csv` / `support_id_provenance.csv`: selected attack row IDs and no attack-eval/final-OOD selection flags.
- `threshold_provenance.csv`: threshold source and no final-eval threshold selection.
- issue18 `row_level_scores.parquet`: row-level score IDs for older holdout_bin_2 and chrono_late diagnostics only.

## 3. Missing Metadata

- Raw packet timestamp.
- Packet order or packet index for all current candidate rows.
- window_start / window_end.
- capture_id / flow_id / session boundary.
- Full final attack/OOD eval row manifests for new unused temporal windows.
- Bin-to-clock-time mapping.

## 4. Clean Temporal Candidate

No clean candidate was found. `earlier-to-later` remains partial, but its eval bins `6/7/8` overlap issue23/25c locked evidence. With current metadata, it is a consistency/planning object, not a clean formal temporal proof.

## 5. Recommended Issue26c Candidate

No formal candidate is ready. The recommended next action is `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.

## 6. Purge / Embargo

Required for any future chronological or adjacent-window validation. A numeric gap cannot be responsibly fixed until raw timestamp/order/capture metadata is recovered.

## 7. Sample Size

Existing split sizes are recoverable at coarse level: ID train 8000, ID calibration 5000, OOD train 8000, OOD validation 2000, OOD eval about 10000. Attack eval size varies; locked bin 8 remains small at 426 rows.

## 8. Slurm

Not needed for issue26b. Slurm may be needed only for a large raw metadata scan or future formal multi-seed temporal validation.

## 9. Claim Change

The temporal claim does not become stronger. issue26b strengthens provenance hygiene and defines the blocker: current assets are good enough for bin-level audit, but not enough for clean purged temporal proof.

## 10. Next Step

Unique next step: `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.
