# Clean Eval Recovery Plan

Smallest useful next step: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`.

Rationale:
- We now have full Mirai/Botnet assets with labels, so the next blocker is not row count.
- The immediate gate is feature compatibility: current LOW-GUARD++ is frozen as original100 + HistGB, while the full Mirai CSV appears restored115-style.
- The chosen split should come from full Mirai first, not from the 80k-cache future-bin path.
- Slurm is not required for the audit itself; it may be needed if full raw extraction or second-environment extraction becomes necessary.

| task_id | task | target_file | expected_output | estimated_cost | local_or_slurm | risk | priority | success_condition |
|---|---|---|---|---|---|---|---|---|
| T1 | full_mirai_feature_compatibility_and_label_alignment_audit | issue27m/full_mirai_feature_compatibility_audit.csv | Map Mirai_dataset/my_gold/mirai3 features to original100 or restored115 and verify label-row alignment. | low | local | If feature mapping is not compatible, current LOW-GUARD++ original100 cannot be run directly. | P0 | clear decision: original100 subset mapping, restored115 rerun path, or incompatibility. |
| T2 | full_mirai_prior_use_and_clean_split_manifest | issue27m/full_mirai_clean_split_manifest.csv | ID/OOD/support/eval split using full Mirai labels without final-eval selection. | medium | local | No explicit timestamp in full CSV; use row order unless timestamped subset is used first. | P0 | sufficient benign/attack rows with disjoint support/eval and validation-only threshold policy. |
| T3 | split_aware_or_restored115_lowguardpp_report_only_eval | issue27m/clean_purged_lowguardpp_by_seed.csv | Only after T1/T2, evaluate frozen-compatible instance with no config/support/threshold search. | low-medium | local | Cannot run unless T1/T2 pass. | P1_after_gate | report-only clean/purged metrics with final_eval_used_for_selection=false. |
| T4 | optional_raw_ood_4_1_extension_or_second_environment_extraction | issue27m/raw_extraction_manifest.csv | Additional capture-disjoint or OOD future rows if P0 candidate remains weak. | medium-high | slurm_if_large | tshark unavailable locally; scapy may be slow. | P2 | new OOD/capture object with original100-compatible extraction. |
