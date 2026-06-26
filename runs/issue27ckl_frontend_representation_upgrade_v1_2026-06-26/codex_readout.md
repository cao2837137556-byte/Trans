# issue27ckl frontend representation upgrade v1

## Scope

Fixed head: C4 HistGB four-class ID / OOD / hard-OOD / attack.
Only the frontend representation changes. Robust statistics are fit only from legal benign fit roles.

## Main candidate matrix

| feature set | future hard mean/min | future review | sealed attack hard mean/min | sealed attack review | sealed OOD hard mean/max | sealed OOD review mean/max |
|---|---:|---:|---:|---:|---:|---:|
| F0_raw115 | 0.9717/0.9016 | 0.0274 | 0.9944/0.9922 | 0.0041 | 0.0026/0.0034 | 0.0733/0.1047 |
| F1_device_family_robust_only | 0.9996/0.9996 | 0.0004 | 0.9999/0.9999 | 0.0000 | 0.0262/0.0277 | 0.2585/0.3806 |
| F1_device_family_robust_tail | 0.9994/0.9987 | 0.0006 | 0.9998/0.9992 | 0.0002 | 0.0266/0.0280 | 0.1934/0.2121 |
| F1_global_robust_only | 0.7947/0.7713 | 0.1240 | 0.9881/0.9847 | 0.0092 | 0.0120/0.0187 | 0.0315/0.0438 |
| F1_global_robust_tail | 0.9685/0.9324 | 0.0310 | 0.9932/0.9926 | 0.0055 | 0.0108/0.0162 | 0.1578/0.2472 |

## Leave-device-family stress

| feature set | held value | role | rows | hard | review | raw | fallback |
|---|---|---|---:|---:|---:|---:|---:|
| F0_raw115 | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0037 | 0.0468 | 0.0504 | nan |
| F1_global_robust_tail | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0237 | 0.0997 | 0.1234 | nan |
| F1_global_robust_only | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0204 | 0.0202 | 0.0406 | nan |
| F1_device_family_robust_tail | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0363 | 0.3022 | 0.3384 | 1.0000 |
| F1_device_family_robust_only | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0377 | 0.3008 | 0.3384 | nan |
| F0_raw115 | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0026 | 0.0193 | 0.0219 | nan |
| F1_global_robust_tail | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0027 | 0.0242 | 0.0268 | nan |
| F1_global_robust_only | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0007 | 0.0049 | 0.0056 | nan |
| F1_device_family_robust_tail | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0095 | 0.0183 | 0.0278 | 1.0000 |
| F1_device_family_robust_only | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0088 | 0.0190 | 0.0278 | nan |
| F0_raw115 | iotsim-stream-consumer | ood_stress | 79950 | 0.9977 | 0.0009 | 0.9986 | nan |
| F1_global_robust_tail | iotsim-stream-consumer | ood_stress | 79950 | 0.9978 | 0.0006 | 0.9984 | nan |
| F1_global_robust_only | iotsim-stream-consumer | ood_stress | 79950 | 0.9976 | 0.0009 | 0.9985 | nan |
| F1_device_family_robust_tail | iotsim-stream-consumer | ood_stress | 79950 | 0.9997 | 0.0003 | 1.0000 | 1.0000 |
| F1_device_family_robust_only | iotsim-stream-consumer | ood_stress | 79950 | 0.9997 | 0.0003 | 1.0000 | nan |
| F0_raw115 | iotsim-hydraulic-system | ood_val | 12205 | 0.5083 | 0.1926 | 0.7009 | nan |
| F1_global_robust_tail | iotsim-hydraulic-system | ood_val | 12205 | 0.4852 | 0.1325 | 0.6177 | nan |
| F1_global_robust_only | iotsim-hydraulic-system | ood_val | 12205 | 0.4871 | 0.1353 | 0.6224 | nan |
| F1_device_family_robust_tail | iotsim-hydraulic-system | ood_val | 12205 | 0.9760 | 0.0240 | 1.0000 | 1.0000 |
| F1_device_family_robust_only | iotsim-hydraulic-system | ood_val | 12205 | 0.9760 | 0.0240 | 1.0000 | nan |

## Shortcut probe snapshot

| feature set | target | eval role | accuracy | balanced acc |
|---|---|---|---:|---:|
| F0_raw115 | device_family | ood_stress | 0.9987 | 0.9987 |
| F0_raw115 | device_family | sealed_final_ood | 0.0000 | 0.0000 |
| F0_raw115 | source_family | ood_stress | 0.9987 | 0.9987 |
| F0_raw115 | source_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_global_robust_tail | device_family | ood_stress | 0.9987 | 0.9987 |
| F1_global_robust_tail | device_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_global_robust_tail | source_family | ood_stress | 0.9987 | 0.9987 |
| F1_global_robust_tail | source_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_global_robust_only | device_family | ood_stress | 0.9980 | 0.9980 |
| F1_global_robust_only | device_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_global_robust_only | source_family | ood_stress | 0.9980 | 0.9980 |
| F1_global_robust_only | source_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_device_family_robust_tail | device_family | ood_stress | 1.0000 | 1.0000 |
| F1_device_family_robust_tail | device_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_device_family_robust_tail | source_family | ood_stress | 1.0000 | 1.0000 |
| F1_device_family_robust_tail | source_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_device_family_robust_only | device_family | ood_stress | 1.0000 | 1.0000 |
| F1_device_family_robust_only | device_family | sealed_final_ood | 0.0000 | 0.0000 |
| F1_device_family_robust_only | source_family | ood_stress | 1.0000 | 1.0000 |
| F1_device_family_robust_only | source_family | sealed_final_ood | 0.0000 | 0.0000 |

## Guardrail

- A useful frontend upgrade must reduce sealed OOD review without raising sealed OOD hard false alarms.
- It must not reduce sealed/future attack hard detection.
- It must improve leave-device-family collapse; otherwise it is only an in-Gotham cosmetic repair.
- Group-aware features use fit-only group baselines and fall back to global robust baselines for unknown/under-sampled groups.

Runtime seconds: `2005.5`.
