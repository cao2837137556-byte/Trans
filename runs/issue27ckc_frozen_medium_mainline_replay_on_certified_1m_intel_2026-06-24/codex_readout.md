# issue27ckc Intel HPC replay readout

## Run identity

- Run: `issue27ckc_frozen_medium_mainline_replay_on_certified_1m_intel_2026-06-24`
- HPC jobs: Intel partition array `55722`, aggregate `55723`
- Mode: `full_hpc`
- Completed jobs: `10`
- Smoke: `False`
- Architecture: Kitsune115D front end, frozen medium attack scorer, parent OOD-risk, past-only temporal heads, bounded controller
- Data: certified 1M benign/OOD, frozen 512 support bank, complete-only exact-label attack subset
- Mixed stream: no; role-separated offline replay
- Formal benchmark: no

## Main result

This run is complete and usable for diagnosis, but it should not be promoted as a deployable detector.

The model shows strong detection for support-covered attack families, especially Mirai/Merlin flood-like traffic. However, it fails the harder OOD separation requirement: large benign OOD roles are also classified as attack at very high rates.

## Threshold-free comparison summary

| Weighting | Comparison | Temporal AUC mean | Temporal AP mean | Parent AUC mean | Parent AP mean |
|---|---:|---:|---:|---:|---:|
| medium_mass_ratio_recalibrated | support_val_select_vs_ood_val_select | 0.9694 | 0.8983 | 0.9999 | 0.9837 |
| medium_mass_ratio_recalibrated | dev_query_union_vs_ood_stress | 0.3383 | 0.6267 | 0.4324 | 0.7639 |
| medium_mass_ratio_recalibrated | sealed_attack_vs_sealed_ood | 0.3992 | 0.3728 | 0.4167 | 0.6014 |
| strict_frozen_weight4 | support_val_select_vs_ood_val_select | 0.9783 | 0.9568 | 0.9999 | 0.9956 |
| strict_frozen_weight4 | dev_query_union_vs_ood_stress | 0.3658 | 0.6361 | 0.3397 | 0.6252 |
| strict_frozen_weight4 | sealed_attack_vs_sealed_ood | 0.3794 | 0.3663 | 0.0438 | 0.2874 |

## Role-level failure signal

OOD benign control is the blocker.

| Weighting | Role | Temporal hard alarm mean | Parent hard alarm mean |
|---|---:|---:|---:|
| medium_mass_ratio_recalibrated | ood_stress | 0.9973 | 0.9975 |
| medium_mass_ratio_recalibrated | sealed_final_ood | 0.9975 | 0.9989 |
| strict_frozen_weight4 | ood_stress | 0.9248 | 0.9248 |
| strict_frozen_weight4 | sealed_final_ood | 0.9968 | 0.9968 |

This means the detector is not simply "high recall"; it is over-firing on OOD benign traffic.

## Support coverage diagnosis

Weighted temporal detection shows a sharp split between support-covered and unseen attacks.

| Weighting | Role | Support coverage | Temporal detection | Parent detection |
|---|---:|---:|---:|---:|
| medium_mass_ratio_recalibrated | future_query | seen_in_support | 0.8376 | 0.9290 |
| medium_mass_ratio_recalibrated | future_query | unseen_in_support | 0.2480 | 0.4171 |
| medium_mass_ratio_recalibrated | sealed_final_attack | seen_in_support | 0.9650 | 0.9936 |
| medium_mass_ratio_recalibrated | sealed_final_attack | unseen_in_support | 0.3478 | 0.6715 |
| strict_frozen_weight4 | future_query | seen_in_support | 0.8146 | 0.8292 |
| strict_frozen_weight4 | future_query | unseen_in_support | 0.2104 | 0.2434 |
| strict_frozen_weight4 | sealed_final_attack | seen_in_support | 0.9460 | 0.9457 |
| strict_frozen_weight4 | sealed_final_attack | unseen_in_support | 0.2511 | 0.2600 |

Strong families include Mirai/Merlin GRE/TCP/UDP/flood-like traffic. Weak families include Telnet Brute Force, TCP/UDP Scan, Reporting, and unseen C&C-like traffic.

## Interpretation

The current frozen support setup is useful as an attack-memory component, but not sufficient as a general deployable detector. It behaves like a strong detector for known or near-known attack families, while confusing difficult benign OOD with attack traffic.

The next scientific step should be OOD failure anatomy and calibration repair, not immediate support expansion. Adding support may improve some unseen attack families, but it will not by itself solve the high OOD benign false-alarm rate shown here.

## Recommended next action

1. Treat this run as a complete offline capability diagnostic.
2. Do not promote either weighting as production/default.
3. Analyze why `ood_stress` and `sealed_final_ood` receive near-attack scores.
4. Separate attack-family memory from benign OOD rejection more cleanly before running support-update budget experiments.
