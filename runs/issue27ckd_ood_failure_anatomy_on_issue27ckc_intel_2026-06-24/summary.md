# issue27ckd OOD failure anatomy on issue27ckc Intel replay

## Scope

- Source run: `issue27ckc_frozen_medium_mainline_replay_on_certified_1m_intel_2026-06-24`.
- Analysis level: aggregate and label/device tables already returned by the full HPC replay.
- This report does not retrain or promote any model.
- Limitation: the source run did not save per-sample score vectors, so nearest-neighbor feature-space proof requires a targeted score-cache replay.

## Main conclusion

The failure is structural rather than a small threshold accident: development OOD calibration looks clean, but hard OOD roles are scored almost exactly like attack and are not suppressed by the OOD-risk path. In parallel, attack detection is strongly support-coverage dominated.

## Dataset-role summary

| Weighting | Dataset role | Kind | Rows | Parent hard | Temporal hard | Attack score | OOD-risk | Diagnosis |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| medium_mass_ratio_recalibrated | id_calib | benign_id | 51497 | 0.0001 | 0.0000 | 0.0000 | 1.0000 | calibration_clean |
| medium_mass_ratio_recalibrated | ood_val | benign_ood | 12205 | 0.0026 | 0.0002 | 0.0003 | 0.9997 | calibration_clean |
| medium_mass_ratio_recalibrated | support_val | attack | 69 | 0.9826 | 0.9391 | 0.9390 | 0.0610 | strong_attack_detection |
| medium_mass_ratio_recalibrated | same_file_query | attack | 125679 | 0.9774 | 0.9356 | 0.9355 | 0.0645 | strong_attack_detection |
| medium_mass_ratio_recalibrated | future_query | attack | 378145 | 0.7114 | 0.5870 | 0.5869 | 0.4131 | mixed_or_intermediate |
| medium_mass_ratio_recalibrated | ood_stress | benign_ood | 229900 | 0.9975 | 0.9973 | 0.9971 | 0.0029 | hard_ood_scored_as_attack_and_not_suppressed |
| medium_mass_ratio_recalibrated | sealed_final_attack | attack | 110104 | 0.9054 | 0.7959 | 0.7958 | 0.2042 | mixed_or_intermediate |
| medium_mass_ratio_recalibrated | sealed_final_ood | benign_ood | 154900 | 0.9989 | 0.9975 | 0.9973 | 0.0027 | hard_ood_scored_as_attack_and_not_suppressed |
| strict_frozen_weight4 | id_calib | benign_id | 51497 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | calibration_clean |
| strict_frozen_weight4 | ood_val | benign_ood | 12205 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | calibration_clean |
| strict_frozen_weight4 | support_val | attack | 69 | 0.9594 | 0.9565 | 0.9564 | 0.0436 | strong_attack_detection |
| strict_frozen_weight4 | same_file_query | attack | 125679 | 0.9556 | 0.9533 | 0.9531 | 0.0465 | strong_attack_detection |
| strict_frozen_weight4 | future_query | attack | 378145 | 0.5802 | 0.5578 | 0.5577 | 0.4364 | mixed_or_intermediate |
| strict_frozen_weight4 | ood_stress | benign_ood | 229900 | 0.9248 | 0.9248 | 0.9246 | 0.0754 | hard_ood_scored_as_attack_and_not_suppressed |
| strict_frozen_weight4 | sealed_final_attack | attack | 110104 | 0.7579 | 0.7556 | 0.7555 | 0.2438 | mixed_or_intermediate |
| strict_frozen_weight4 | sealed_final_ood | benign_ood | 154900 | 0.9968 | 0.9968 | 0.9966 | 0.0034 | hard_ood_scored_as_attack_and_not_suppressed |

## Threshold-free generalization

| Weighting | Comparison | Stage | Temporal AUC | Temporal AP | Parent AUC | Parent AP | Diagnosis |
|---|---:|---:|---:|---:|---:|---:|---|
| medium_mass_ratio_recalibrated | dev_query_union_vs_ood_stress | read_only | 0.3383 | 0.6267 | 0.4324 | 0.7639 | inverted_or_ood_dominates |
| medium_mass_ratio_recalibrated | sealed_attack_vs_sealed_ood | report_only | 0.3992 | 0.3728 | 0.4167 | 0.6014 | inverted_or_ood_dominates |
| medium_mass_ratio_recalibrated | support_val_select_vs_ood_val_select | calibration_select | 0.9694 | 0.8983 | 0.9999 | 0.9837 | separable |
| strict_frozen_weight4 | dev_query_union_vs_ood_stress | read_only | 0.3658 | 0.6361 | 0.3397 | 0.6252 | inverted_or_ood_dominates |
| strict_frozen_weight4 | sealed_attack_vs_sealed_ood | report_only | 0.3794 | 0.3663 | 0.0438 | 0.2874 | inverted_or_ood_dominates |
| strict_frozen_weight4 | support_val_select_vs_ood_val_select | calibration_select | 0.9783 | 0.9568 | 1.0000 | 0.9956 | separable |

## Support coverage gap

| Weighting | Role | Coverage | Rows per seed | Parent detection | Temporal detection |
|---|---:|---:|---:|---:|---:|
| medium_mass_ratio_recalibrated | future_query | seen_in_support | 217423 | 0.9290 | 0.8376 |
| medium_mass_ratio_recalibrated | future_query | unseen_in_support | 160722 | 0.4171 | 0.2480 |
| medium_mass_ratio_recalibrated | sealed_final_attack | seen_in_support | 79940 | 0.9936 | 0.9650 |
| medium_mass_ratio_recalibrated | sealed_final_attack | unseen_in_support | 30164 | 0.6715 | 0.3478 |
| strict_frozen_weight4 | future_query | seen_in_support | 217423 | 0.8292 | 0.8146 |
| strict_frozen_weight4 | future_query | unseen_in_support | 160722 | 0.2434 | 0.2104 |
| strict_frozen_weight4 | sealed_final_attack | seen_in_support | 79940 | 0.9457 | 0.9460 |
| strict_frozen_weight4 | sealed_final_attack | unseen_in_support | 30164 | 0.2600 | 0.2511 |

## Weak attack groups, worst 20 by temporal detection

| Weighting | Role | Attack label | Device | Coverage | Rows per seed | Parent | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|
| medium_mass_ratio_recalibrated | same_file_query | Ingress Tool Transfer | combined-cycle | seen_in_support | 2381 | 0.0000 | 0.0000 |
| medium_mass_ratio_recalibrated | future_query | Mirai C&C Communication | building-monitor | seen_in_support | 358 | 0.0173 | 0.0000 |
| medium_mass_ratio_recalibrated | future_query | Mirai C&C Communication | combined-cycle | seen_in_support | 358 | 0.0162 | 0.0000 |
| medium_mass_ratio_recalibrated | future_query | Reporting | domotic-monitor | unseen_in_support | 72 | 0.0000 | 0.0000 |
| strict_frozen_weight4 | future_query | Reporting | domotic-monitor | unseen_in_support | 72 | 0.0000 | 0.0000 |
| medium_mass_ratio_recalibrated | future_query | Reporting | combined-cycle | unseen_in_support | 64 | 0.0000 | 0.0000 |
| strict_frozen_weight4 | support_val | Mirai C&C Communication | ip-camera-museum | seen_in_support | 2 | 0.0000 | 0.0000 |
| medium_mass_ratio_recalibrated | support_val | Merlin ICMP Flooding | city-power | seen_in_support | 1 | 1.0000 | 0.0000 |
| medium_mass_ratio_recalibrated | future_query | Telnet Brute Force | domotic-monitor | unseen_in_support | 12000 | 0.0798 | 0.0022 |
| medium_mass_ratio_recalibrated | future_query | Telnet Brute Force | combined-cycle | unseen_in_support | 12000 | 0.0551 | 0.0032 |
| medium_mass_ratio_recalibrated | future_query | UDP Scan | combined-cycle | unseen_in_support | 4242 | 0.0227 | 0.0047 |
| strict_frozen_weight4 | future_query | Telnet Brute Force | air-quality | unseen_in_support | 12000 | 0.0057 | 0.0048 |
| strict_frozen_weight4 | future_query | Telnet Brute Force | city-power | unseen_in_support | 12000 | 0.0070 | 0.0060 |
| medium_mass_ratio_recalibrated | future_query | Telnet Brute Force | air-quality | unseen_in_support | 12000 | 0.1784 | 0.0064 |
| medium_mass_ratio_recalibrated | future_query | Merlin ICMP Flooding | domotic-monitor | seen_in_support | 9793 | 0.5248 | 0.0067 |
| strict_frozen_weight4 | future_query | Mirai C&C Communication | building-monitor | seen_in_support | 358 | 0.0112 | 0.0067 |
| strict_frozen_weight4 | future_query | UDP Scan | combined-cycle | unseen_in_support | 4242 | 0.0094 | 0.0073 |
| medium_mass_ratio_recalibrated | future_query | Telnet Brute Force | city-power | unseen_in_support | 12000 | 0.2317 | 0.0090 |
| medium_mass_ratio_recalibrated | future_query | Telnet Brute Force | building-monitor | unseen_in_support | 12000 | 0.0930 | 0.0091 |
| medium_mass_ratio_recalibrated | future_query | TCP Scan | city-power | unseen_in_support | 12000 | 0.4982 | 0.0098 |

## Score tie / threshold anatomy

| Weighting | Score | Threshold | Equal mass | Strict above mass | Diagnosis |
|---|---:|---:|---:|---:|---|
| medium_mass_ratio_recalibrated | parent_attack_score | 0.012325198942781961 | 0.0170 | 0.0092 | nondegenerate |
| medium_mass_ratio_recalibrated | parent_attack_score | 0.016998485286639876 | 0.0170 | 0.0084 | nondegenerate |
| medium_mass_ratio_recalibrated | parent_attack_score | 0.01776340612042322 | 0.0020 | 0.0093 | nondegenerate |
| medium_mass_ratio_recalibrated | parent_attack_score | 0.018532874625085537 | 0.0028 | 0.0087 | nondegenerate |
| medium_mass_ratio_recalibrated | parent_attack_score | 0.019177980712155145 | 0.0027 | 0.0086 | nondegenerate |
| medium_mass_ratio_recalibrated | temporal_attack_score | 2.939835892077895e-05 | 1.0000 | 0.0000 | degenerate_tie_or_near_binary_threshold |
| strict_frozen_weight4 | parent_attack_score | 0.0027570905699389084 | 0.0164 | 0.0085 | nondegenerate |
| strict_frozen_weight4 | parent_attack_score | 0.002788595867860858 | 0.0112 | 0.0069 | nondegenerate |
| strict_frozen_weight4 | parent_attack_score | 0.0029946689883346175 | 0.0164 | 0.0062 | nondegenerate |
| strict_frozen_weight4 | parent_attack_score | 0.0035585964447935737 | 0.0164 | 0.0059 | nondegenerate |
| strict_frozen_weight4 | parent_attack_score | 0.004906748399862994 | 0.0164 | 0.0015 | nondegenerate |
| strict_frozen_weight4 | temporal_attack_score | 2.939835892077895e-05 | 1.0000 | 0.0000 | degenerate_tie_or_near_binary_threshold |

## Deterministic hypotheses supported by this run

| Weighting | Finding | Evidence | Status |
|---|---:|---:|---:|
| medium_mass_ratio_recalibrated | ood_calibration_does_not_transfer | ood_val temporal=0.0002; ood_stress temporal=0.9973; sealed_final_ood temporal=0.9975 | supported |
| medium_mass_ratio_recalibrated | hard_ood_not_suppressed_by_ood_risk | ood_stress attack_score=0.9971, risk=0.0029; sealed_final_ood attack_score=0.9973, risk=0.0027 | supported |
| medium_mass_ratio_recalibrated | attack_detection_is_support_coverage_dominated | future seen temporal=0.8376; future unseen temporal=0.2480 | supported |
| strict_frozen_weight4 | ood_calibration_does_not_transfer | ood_val temporal=0.0000; ood_stress temporal=0.9248; sealed_final_ood temporal=0.9968 | supported |
| strict_frozen_weight4 | hard_ood_not_suppressed_by_ood_risk | ood_stress attack_score=0.9246, risk=0.0754; sealed_final_ood attack_score=0.9966, risk=0.0034 | supported |
| strict_frozen_weight4 | attack_detection_is_support_coverage_dominated | future seen temporal=0.8146; future unseen temporal=0.2104 | supported |

## What this rules in

1. OOD calibration is non-transferable: `ood_val` is clean but `ood_stress` and `sealed_final_ood` fail.
2. The hard OOD roles are not merely unsuppressed edge cases; they receive high attack scores and low OOD-risk values.
3. The temporal path is not the sole root cause. Parent hard alarms are already very high on hard OOD roles.
4. Attack detection is support-coverage dominated: seen-in-support attack roles are strong, unseen roles are weak.

## What this does not yet prove

The current artifacts cannot prove which exact feature dimensions or support neighbors cause the hard OOD confusion, because issue27ckc did not persist per-sample score vectors or nearest-neighbor identities.

## Recommended next experiment

Run a targeted score-cache anatomy, not another full model sweep: persist row-level parent/temporal attack score, OOD-risk, hard decision, role, label/device, and nearest support/attack/benign prototypes for `ood_val`, `ood_stress`, `sealed_final_ood`, `future_query`, and `sealed_final_attack`. A small stratified cache is enough locally if the full feature store is available; otherwise use the Intel partition.
