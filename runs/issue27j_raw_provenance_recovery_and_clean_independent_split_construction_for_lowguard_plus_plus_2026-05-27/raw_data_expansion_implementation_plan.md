# Raw Data Expansion Implementation Plan

Recommended next action: `issue27k_row_level_original100_rebuild_and_purged_split_construction`.

Minimum required fields:
- raw packet timestamp;
- packet_order / packet_id;
- capture/session id;
- row_id and feature_row;
- window_start / window_end;
- attack label mapping;
- benign OOD mapping;
- feature name mapping;
- original100 reconstruction script or reproducible extraction command.

| task | target_file | script_to_inspect_or_create | expected_output | estimated_cost | local_or_slurm | risk | priority |
|---|---|---|---|---|---|---|---|
| create_original100_row_sidecar_manifest | runs/<new_extraction>/row_level_original100_manifest.csv | repo/ood/kitsune_frontend_original_extract.py | row_id, packet_order, timestamp, capture_id, source_pcap, feature_row, hash/fingerprint | low_medium | local_for_current_30k; slurm_if_large | low | P0 |
| rebuild_attack_original100_with_sidecar | runs/issue27k_provenance_rebuild/attack_original100_with_manifest.npy | repo/ood/kitsune_frontend_original_extract.py | Feature matrix exactly matching current attack rows plus explicit row mapping | medium | local_possible_for_30k | medium_due_exact_reproducibility_check | P0 |
| construct_purged_chronological_candidate | runs/issue27k_clean_split/clean_split_manifest.csv | new issue27k split builder | train/cal/val/eval ids, timestamp ranges, purge gap, support/eval disjointness | medium | local | medium_if_future_window_small | P0 |
| recover_additional_capture_or_session | runs/issue27k_capture_disjoint_assets/ | repo/ood/kitsune_frontend_original_extract.py and raw public_data | Unused attack/benign capture original100 assets | medium_high | maybe_slurm | medium | P1 |
| second_environment_feature_builder_check | runs/issue27k_second_environment_feasibility/ | new compatibility audit | Whether external raw traffic can be mapped to Kitsune original100 | high | slurm_if_large | medium_schema_confounding | P2 |


Compute note: current 30k/50k extraction is likely local-feasible. Slurm may be useful for full-capture or second-environment reconstruction.
