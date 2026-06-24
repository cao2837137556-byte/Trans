# issue27cke hard-OOD score-cache locator

## Purpose

This is a localization run, not a new model result. It reuses the frozen issue27ckc scoring stack and inspects why hard benign OOD is accepted as attack.

## Key role-level evidence

### medium_mass_ratio_recalibrated

| role | rows | temporal hard | parent hard | temporal attack mean | temporal risk mean | attack distance mean | benign distance mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| ood_val | 12205 | 0.0001 | 0.0011 | 0.0001 | 0.9999 | 0.5602 | 0.2522 |
| ood_stress | 229900 | 0.9972 | 0.9974 | 0.9970 | 0.0030 | 0.1309 | 1.2116 |
| sealed_final_ood | 154900 | 0.9972 | 0.9992 | 0.9970 | 0.0030 | 0.1326 | 1.2368 |
| future_query | 378145 | 0.5706 | 0.6558 | 0.5706 | 0.4294 | 12.0306 | 3.9984 |
| sealed_final_attack | 110104 | 0.7933 | 0.9021 | 0.7932 | 0.2068 | 0.3502 | 2.1014 |

### strict_frozen_weight4

| role | rows | temporal hard | parent hard | temporal attack mean | temporal risk mean | attack distance mean | benign distance mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| ood_val | 12205 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.5602 | 0.2522 |
| ood_stress | 229900 | 0.6830 | 0.6830 | 0.6829 | 0.3171 | 0.1309 | 1.2116 |
| sealed_final_ood | 154900 | 0.9966 | 0.9966 | 0.9964 | 0.0036 | 0.1326 | 1.2368 |
| future_query | 378145 | 0.4846 | 0.5424 | 0.4845 | 0.5155 | 12.0306 | 3.9984 |
| sealed_final_attack | 110104 | 0.6993 | 0.6993 | 0.6992 | 0.3008 | 0.3502 | 2.1014 |

## Parent OOD-risk fit audit

| job | weighting | role | risk label | rows used | row source |
|---:|---|---|---:|---:|---|
| 1 | medium_mass_ratio_recalibrated | id_calib | 1 | 3285 | fit_raw_alarm_rows |
| 1 | medium_mass_ratio_recalibrated | ood_val | 1 | 1647 | fit_raw_alarm_rows |
| 1 | medium_mass_ratio_recalibrated | support_val | 0 | 58 | fit_raw_alarm_rows |
| 6 | strict_frozen_weight4 | id_calib | 1 | 3341 | fit_raw_alarm_rows |
| 6 | strict_frozen_weight4 | ood_val | 1 | 1082 | fit_raw_alarm_rows |
| 6 | strict_frozen_weight4 | support_val | 0 | 58 | fit_raw_alarm_rows |

## What the selected hard OOD rows are nearest to

Counts below use only selected diagnostic rows, not the full OOD corpus. They locate the failure mode without turning this into another full experiment.

| weighting | role | selector | nearest support label | selected rows | share |
|---|---|---|---|---:|---:|
| medium_mass_ratio_recalibrated | ood_stress | highest_benign_minus_attack | File Download | 69 | 0.8625 |
| medium_mass_ratio_recalibrated | ood_stress | highest_benign_minus_attack | Mirai C&C Communication | 9 | 0.1125 |
| medium_mass_ratio_recalibrated | ood_stress | highest_benign_minus_attack | Merlin TCP Flooding | 2 | 0.0250 |
| medium_mass_ratio_recalibrated | ood_stress | lowest_temporal_ood_risk | File Download | 79 | 0.9875 |
| medium_mass_ratio_recalibrated | ood_stress | lowest_temporal_ood_risk | Merlin C&C Communication | 1 | 0.0125 |
| medium_mass_ratio_recalibrated | ood_stress | nearest_attack_region | File Download | 80 | 1.0000 |
| medium_mass_ratio_recalibrated | ood_stress | top_parent_attack | Merlin TCP Flooding | 77 | 0.9625 |
| medium_mass_ratio_recalibrated | ood_stress | top_parent_attack | Mirai C&C Communication | 3 | 0.0375 |
| medium_mass_ratio_recalibrated | ood_stress | top_temporal_attack | File Download | 79 | 0.9875 |
| medium_mass_ratio_recalibrated | ood_stress | top_temporal_attack | Merlin C&C Communication | 1 | 0.0125 |
| medium_mass_ratio_recalibrated | sealed_final_ood | highest_benign_minus_attack | Merlin ICMP Flooding | 78 | 0.9750 |
| medium_mass_ratio_recalibrated | sealed_final_ood | highest_benign_minus_attack | File Download | 2 | 0.0250 |
| medium_mass_ratio_recalibrated | sealed_final_ood | lowest_temporal_ood_risk | File Download | 80 | 1.0000 |
| medium_mass_ratio_recalibrated | sealed_final_ood | nearest_attack_region | File Download | 80 | 1.0000 |
| medium_mass_ratio_recalibrated | sealed_final_ood | top_parent_attack | Merlin TCP Flooding | 71 | 0.8875 |
| medium_mass_ratio_recalibrated | sealed_final_ood | top_parent_attack | Merlin ICMP Flooding | 5 | 0.0625 |
| medium_mass_ratio_recalibrated | sealed_final_ood | top_parent_attack | Mirai C&C Communication | 4 | 0.0500 |
| medium_mass_ratio_recalibrated | sealed_final_ood | top_temporal_attack | File Download | 80 | 1.0000 |
| strict_frozen_weight4 | ood_stress | highest_benign_minus_attack | File Download | 69 | 0.8625 |
| strict_frozen_weight4 | ood_stress | highest_benign_minus_attack | Mirai C&C Communication | 9 | 0.1125 |
| strict_frozen_weight4 | ood_stress | highest_benign_minus_attack | Merlin TCP Flooding | 2 | 0.0250 |
| strict_frozen_weight4 | ood_stress | lowest_temporal_ood_risk | File Download | 79 | 0.9875 |
| strict_frozen_weight4 | ood_stress | lowest_temporal_ood_risk | Merlin C&C Communication | 1 | 0.0125 |
| strict_frozen_weight4 | ood_stress | nearest_attack_region | File Download | 80 | 1.0000 |
| strict_frozen_weight4 | ood_stress | top_parent_attack | Merlin TCP Flooding | 73 | 0.9125 |
| strict_frozen_weight4 | ood_stress | top_parent_attack | Mirai C&C Communication | 7 | 0.0875 |
| strict_frozen_weight4 | ood_stress | top_temporal_attack | File Download | 79 | 0.9875 |
| strict_frozen_weight4 | ood_stress | top_temporal_attack | Merlin C&C Communication | 1 | 0.0125 |
| strict_frozen_weight4 | sealed_final_ood | highest_benign_minus_attack | Merlin ICMP Flooding | 78 | 0.9750 |
| strict_frozen_weight4 | sealed_final_ood | highest_benign_minus_attack | File Download | 2 | 0.0250 |
| strict_frozen_weight4 | sealed_final_ood | lowest_temporal_ood_risk | File Download | 80 | 1.0000 |
| strict_frozen_weight4 | sealed_final_ood | nearest_attack_region | File Download | 80 | 1.0000 |
| strict_frozen_weight4 | sealed_final_ood | top_parent_attack | Merlin TCP Flooding | 66 | 0.8250 |
| strict_frozen_weight4 | sealed_final_ood | top_parent_attack | Merlin ICMP Flooding | 10 | 0.1250 |
| strict_frozen_weight4 | sealed_final_ood | top_parent_attack | Mirai C&C Communication | 4 | 0.0500 |
| strict_frozen_weight4 | sealed_final_ood | top_temporal_attack | File Download | 80 | 1.0000 |

## Largest hard-OOD source groups

| weighting | role | source group | hard rows | share | temporal attack mean | temporal risk mean |
|---|---|---|---:|---:|---:|---:|
| medium_mass_ratio_recalibrated | ood_stress | processed/iotsim-stream-consumer-1.csv | 149545 | 0.6505 | 0.9998 | 0.0002 |
| strict_frozen_weight4 | ood_stress | processed/iotsim-stream-consumer-1.csv | 102374 | 0.4453 | 0.9998 | 0.0002 |
| medium_mass_ratio_recalibrated | sealed_final_ood | processed/iotsim-ip-camera-street-2.csv | 99636 | 0.6432 | 0.9998 | 0.0002 |
| strict_frozen_weight4 | sealed_final_ood | processed/iotsim-ip-camera-street-2.csv | 99552 | 0.6427 | 0.9998 | 0.0002 |
| medium_mass_ratio_recalibrated | ood_stress | processed/iotsim-stream-consumer-2.csv | 79700 | 0.3467 | 0.9998 | 0.0002 |
| medium_mass_ratio_recalibrated | sealed_final_ood | processed/iotsim-ip-camera-museum-2.csv | 54834 | 0.3540 | 0.9998 | 0.0002 |
| strict_frozen_weight4 | sealed_final_ood | processed/iotsim-ip-camera-museum-2.csv | 54823 | 0.3539 | 0.9998 | 0.0002 |
| strict_frozen_weight4 | ood_stress | processed/iotsim-stream-consumer-2.csv | 54645 | 0.2377 | 0.9998 | 0.0002 |

## Current localization conclusion

1. If `ood_val` remains clean while `ood_stress` and `sealed_final_ood` are near-one hard alarms, the validation OOD slice is not representative of the hard benign OOD that appears after freeze.
2. If hard OOD has high temporal attack score but low temporal OOD-risk, the failure is not merely a threshold bug. The OOD-risk evidence is anti-calibrated for hard OOD.
3. If hard OOD is also close to attack regions (`d_attack_outer_min` around or below 1), the 115D/evidence geometry itself is confounding benign OOD with support-covered attack modes.
4. The next fix should therefore target OOD evidence/calibration before controller wiring: add hard-OOD calibration or a conservative OOD veto, then rerun the same frozen-role replay.

## Run metadata

| job | weighting | support weight | parent threshold | temporal threshold | seconds |
|---:|---|---:|---:|---:|---:|
| 1 | medium_mass_ratio_recalibrated | 31.0034 | 0.0170 | 0.0000 | 40.9 |
| 6 | strict_frozen_weight4 | 4.0000 | 0.0036 | 0.0000 | 29.4 |
