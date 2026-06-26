# issue27ckm group-invariant training v1

## Scope

Fixed frontend/head: raw115 + C4 four-class HistGB.
Only the training objective/weights change. Environments are device/source families.

## Main matrix

| variant | future hard mean/min | future review | sealed attack hard mean/min | sealed attack review | sealed OOD hard mean/max | sealed OOD review mean/max |
|---|---:|---:|---:|---:|---:|---:|
| M0_c4_baseline | 0.9717/0.9016 | 0.0274 | 0.9944/0.9922 | 0.0041 | 0.0026/0.0034 | 0.0733/0.1047 |
| M1_device_family_env_balanced | 0.9146/0.8550 | 0.0842 | 0.9970/0.9967 | 0.0020 | 0.0064/0.0078 | 0.1289/0.1805 |
| M2_source_family_env_balanced | 0.9146/0.8550 | 0.0842 | 0.9970/0.9967 | 0.0020 | 0.0064/0.0078 | 0.1289/0.1805 |
| M3_device_family_dro | 0.9116/0.8859 | 0.0870 | 0.9967/0.9958 | 0.0020 | 0.0061/0.0076 | 0.0927/0.1223 |
| M4_source_family_dro | 0.9116/0.8859 | 0.0870 | 0.9967/0.9958 | 0.0020 | 0.0061/0.0076 | 0.0927/0.1223 |

## Leave-device-family stress

| variant | held value | role | rows | hard | review | raw |
|---|---|---|---:|---:|---:|---:|
| M0_c4_baseline | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0037 | 0.0468 | 0.0504 |
| M3_device_family_dro | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0105 | 0.0585 | 0.0690 |
| M4_source_family_dro | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0105 | 0.0585 | 0.0690 |
| M0_c4_baseline | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0026 | 0.0193 | 0.0219 |
| M3_device_family_dro | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0023 | 0.1093 | 0.1116 |
| M4_source_family_dro | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0023 | 0.1093 | 0.1116 |
| M0_c4_baseline | iotsim-stream-consumer | ood_stress | 79950 | 0.9977 | 0.0009 | 0.9986 |
| M3_device_family_dro | iotsim-stream-consumer | ood_stress | 79950 | 0.9976 | 0.0009 | 0.9985 |
| M4_source_family_dro | iotsim-stream-consumer | ood_stress | 79950 | 0.9976 | 0.0009 | 0.9985 |
| M0_c4_baseline | iotsim-hydraulic-system | ood_val | 12205 | 0.5083 | 0.1926 | 0.7009 |
| M3_device_family_dro | iotsim-hydraulic-system | ood_val | 12205 | 0.5263 | 0.1718 | 0.6981 |
| M4_source_family_dro | iotsim-hydraulic-system | ood_val | 12205 | 0.5263 | 0.1718 | 0.6981 |

## Guardrail

- A valid invariant-training improvement must reduce sealed OOD review without raising sealed OOD hard false alarms.
- It must preserve sealed/future attack hard detection.
- It must reduce leave-device-family collapse, not merely move uncertainty from review into hard false alarms.
- This is causal-inspired invariant training only; it is not a full causal discovery claim.

Runtime seconds: `1147.2`.
