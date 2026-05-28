# Clean Split Construction Report

Clean independent split constructable now: `False`.

| split_name | required_metadata | available | can_construct_now | leakage_risk | expected_evidence_level | blocked_reason | construction_steps | recommended_priority |
|---|---|---|---|---|---|---|---|---|
| chronological_forward_split | packet timestamp; attack row->bin mapping; ID/OOD train/cal/val/eval maps | partial | False | medium | blocked_for_formal_independent | Earlier/later packet bins can be recovered, but current clean future attack window outside bins 5/6/7/8 is too small and OOD independent object is not new. | Persist row-level attack/ID/OOD manifests; define unused future window; keep final eval report-only. | P0 |
| purged_chronological_split | timestamp/window boundary plus embargo gap and splitwise feature reconstruction | partial | False | low_after_reconstruction_high_before | blocked_for_formal_independent | Feature state was computed continuously before splits; purged validation should rebuild/reset state around split boundaries. | Re-extract original100 with sidecar row manifest and optional state reset/gap. | P0 |
| future_window_eval_bin9 | unused bin 9 row ids and enough attack rows | partial | False | medium | small_diagnostic_only | Bin 9 is outside locked bins but has only 208 packet rows and was below the previous holdout min_eval_rows=300 / min_conn_per_bin=120 gate. | Could run only as a labeled diagnostic after explicit approval; not sufficient for issue27j formal clean validation. | P1_diagnostic |
| capture_disjoint_split | additional attack/benign captures with compatible original100 extraction | no | False | unknown | blocked_for_formal_independent | Current roles are already capture-separated for ID/OOD/attack, but there is no unused attack capture/session with matching original100 assets for independent validation. | Recover or create second attack/benign capture original100 assets with row-level manifests. | P1 |
| second_environment_split | compatible raw traffic, labels, and Kitsune original100 reconstruction | partial | False | medium_until_builder_compatible | future_external_validation | Potential raw external CSVs exist, but schema is not currently mapped into Kitsune original100. | Build/reuse original100 feature builder and pre-register split before evaluation. | P2 |


Conclusion:
- Issue27j recovers enough raw provenance to define what a clean split should look like.
- It does not yet produce a formal clean independent validation object.
- The next step should build a row-level original100 manifest and then construct a purged chronological or capture/session-disjoint split.
