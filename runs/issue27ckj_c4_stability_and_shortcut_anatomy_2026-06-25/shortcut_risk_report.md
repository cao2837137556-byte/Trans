# issue27ckj C4 stability and shortcut anatomy

## Scope

Diagnosis only. Fixed baseline: `C4_fewshot_multiclass_raw115_cap20000`.
No new detector head, no causal/invariant repair, no threshold tuning.
Sealed final roles remain report-only.

## Seed stability summary

| role | seeds | hard mean | hard min | hard max | review mean | review max | raw mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| future_query | 5 | 0.9717 | 0.9016 | 0.9929 | 0.0274 | 0.0975 | 0.9991 |
| id_calib | 5 | 0.0000 | 0.0000 | 0.0000 | 0.0010 | 0.0011 | 0.0010 |
| ood_stress | 5 | 0.0002 | 0.0002 | 0.0003 | 0.0044 | 0.0054 | 0.0046 |
| ood_val | 5 | 0.0000 | 0.0000 | 0.0000 | 0.0093 | 0.0100 | 0.0093 |
| same_file_query | 5 | 0.9979 | 0.9966 | 0.9996 | 0.0021 | 0.0034 | 1.0000 |
| sealed_final_attack | 5 | 0.9944 | 0.9922 | 0.9957 | 0.0041 | 0.0062 | 0.9985 |
| sealed_final_ood | 5 | 0.0026 | 0.0018 | 0.0034 | 0.0733 | 0.1047 | 0.0759 |
| support_val | 5 | 0.9826 | 0.9710 | 0.9855 | 0.0174 | 0.0290 | 1.0000 |

## Primary seed42 role metrics

| role | rows | hard | review | review count | raw | threshold |
|---|---:|---:|---:|---:|---:|---:|
| id_calib | 51497 | 0.0000 | 0.0011 | 59 | 0.0011 | 0.0108 |
| ood_val | 12205 | 0.0000 | 0.0092 | 112 | 0.0092 | 0.0108 |
| ood_stress | 79950 | 0.0003 | 0.0054 | 432 | 0.0057 | 0.0108 |
| support_val | 69 | 0.9855 | 0.0145 | 1 | 1.0000 | 0.0108 |
| same_file_query | 67749 | 0.9983 | 0.0017 | 118 | 1.0000 | 0.0108 |
| future_query | 228649 | 0.9926 | 0.0061 | 1406 | 0.9988 | 0.0108 |
| sealed_final_ood | 154900 | 0.0033 | 0.0370 | 5736 | 0.0403 | 0.0108 |
| sealed_final_attack | 110104 | 0.9922 | 0.0062 | 681 | 0.9984 | 0.0108 |

## Top review / hard groups

| role | field | value | rows | review | review count | hard | hard count |
|---|---|---|---:|---:|---:|---:|---:|
| future_query | support_seen | seen | 140099 | 0.0028 | 386 | 0.9960 | 139540 |
| future_query | device_family | combined-cycle | 112729 | 0.0091 | 1024 | 0.9889 | 111481 |
| future_query | source_family | iotsim-combined-cycle | 112729 | 0.0091 | 1024 | 0.9889 | 111481 |
| future_query | device | combined-cycle | 112729 | 0.0091 | 1024 | 0.9889 | 111481 |
| sealed_final_attack | device_family | ip-camera-street | 110104 | 0.0062 | 681 | 0.9922 | 109243 |
| sealed_final_attack | device | ip-camera-street | 110104 | 0.0062 | 681 | 0.9922 | 109243 |
| sealed_final_attack | source_group | processed/iotsim-ip-camera-street-1.csv | 110104 | 0.0062 | 681 | 0.9922 | 109243 |
| sealed_final_attack | source_family | iotsim-ip-camera-street | 110104 | 0.0062 | 681 | 0.9922 | 109243 |
| future_query | source_group | processed/iotsim-domotic-monitor-1.csv | 91812 | 0.0041 | 380 | 0.9953 | 91380 |
| future_query | source_family | iotsim-domotic-monitor | 91812 | 0.0041 | 380 | 0.9953 | 91380 |
| future_query | device_family | domotic-monitor | 91812 | 0.0041 | 380 | 0.9953 | 91380 |
| future_query | device | domotic-monitor | 91812 | 0.0041 | 380 | 0.9953 | 91380 |
| future_query | source_group | processed/iotsim-combined-cycle-1.csv | 88575 | 0.0088 | 780 | 0.9892 | 87622 |
| future_query | support_seen | unseen | 88550 | 0.0115 | 1020 | 0.9873 | 87427 |
| sealed_final_attack | support_seen | seen | 79940 | 0.0006 | 49 | 0.9993 | 79884 |
| future_query | time_block | q4 | 70323 | 0.0017 | 118 | 0.9959 | 70032 |
| same_file_query | support_seen | seen | 67749 | 0.0017 | 118 | 0.9983 | 67631 |
| same_file_query | source_group | processed/iotsim-ip-camera-museum-1.csv | 65263 | 0.0018 | 118 | 0.9982 | 65145 |
| same_file_query | device_family | ip-camera-museum | 65263 | 0.0018 | 118 | 0.9982 | 65145 |
| same_file_query | device | ip-camera-museum | 65263 | 0.0018 | 118 | 0.9982 | 65145 |

## Leave-out stress groups

- `source_group`: `processed/iotsim-ip-camera-street-2.csv, processed/iotsim-ip-camera-museum-2.csv, processed/iotsim-stream-consumer-2.csv, processed/iotsim-hydraulic-system-12.csv`
- `device_family`: `iotsim-ip-camera-street, iotsim-ip-camera-museum, iotsim-stream-consumer, iotsim-hydraulic-system`
- `attack_label`: `TCP Scan, UDP Scan, Merlin C&C Communication, Mirai C&C Communication`

## Leave-out stress metrics

| split | held field | held value | role | rows | hard | review | raw | threshold |
|---|---|---|---|---:|---:|---:|---:|---:|
| leave_source_group | source_group | processed/iotsim-ip-camera-street-2.csv | sealed_final_ood | 99950 | 0.0037 | 0.0468 | 0.0504 | 0.0108 |
| leave_source_group | source_group | processed/iotsim-ip-camera-museum-2.csv | sealed_final_ood | 54950 | 0.0026 | 0.0193 | 0.0219 | 0.0108 |
| leave_source_group | source_group | processed/iotsim-stream-consumer-2.csv | ood_stress | 79950 | 0.0003 | 0.0054 | 0.0057 | 0.0108 |
| leave_source_group | source_group | processed/iotsim-hydraulic-system-12.csv | ood_val | 2446 | 0.0000 | 0.0131 | 0.0131 | 0.0108 |
| leave_device_family | device_family | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0037 | 0.0468 | 0.0504 | 0.0108 |
| leave_device_family | device_family | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0026 | 0.0193 | 0.0219 | 0.0108 |
| leave_device_family | device_family | iotsim-stream-consumer | ood_stress | 79950 | 0.9977 | 0.0009 | 0.9986 | 0.0059 |
| leave_device_family | device_family | iotsim-hydraulic-system | ood_val | 12205 | 0.5083 | 0.1926 | 0.7009 | 0.0134 |
| leave_attack_label | attack_label | TCP Scan | future_query | 36000 | 0.9877 | 0.0114 | 0.9991 | 0.0108 |
| leave_attack_label | attack_label | TCP Scan | sealed_final_attack | 15000 | 0.9569 | 0.0353 | 0.9922 | 0.0108 |
| leave_attack_label | attack_label | UDP Scan | future_query | 4242 | 0.9017 | 0.0983 | 1.0000 | 0.0108 |
| leave_attack_label | attack_label | Merlin C&C Communication | support_val | 5 | 0.0000 | 0.6000 | 0.6000 | 0.0084 |
| leave_attack_label | attack_label | Merlin C&C Communication | same_file_query | 6827 | 0.5883 | 0.1917 | 0.7800 | 0.0084 |
| leave_attack_label | attack_label | Merlin C&C Communication | future_query | 9933 | 0.6662 | 0.3258 | 0.9919 | 0.0084 |
| leave_attack_label | attack_label | Mirai C&C Communication | support_val | 2 | 0.0000 | 0.5000 | 0.5000 | 0.0087 |
| leave_attack_label | attack_label | Mirai C&C Communication | same_file_query | 106 | 0.5566 | 0.2075 | 0.7642 | 0.0087 |
| leave_attack_label | attack_label | Mirai C&C Communication | future_query | 358 | 0.1425 | 0.2011 | 0.3436 | 0.0087 |

## Interpretation guardrail

- If seed stability is good but group burden is concentrated, C4 is not enough; issue27ckk should repair training views with group/worst-group balancing.
- If leave-out stress collapses under source/device/family, C4 has shortcut risk and should not be promoted as a robust detector.
- Leave-attack-label-out is zero-shot attack stress only; failure there is a coverage/active-labeling signal, not a direct violation of the few-shot problem setting.

Runtime seconds: `395.2`.
