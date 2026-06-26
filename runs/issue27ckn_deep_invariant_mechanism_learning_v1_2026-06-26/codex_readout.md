# issue27ckn deep invariant mechanism learning v1

## Scope

Causal-inspired invariant representation diagnostic. C0 is C4 raw115 HistGB; N1/N2/N3 are small neural encoders.
No report-only role is used for detector/scaler/adversary/probe/threshold fitting.

## Main matrix

| variant | future hard mean/min | future review | sealed attack hard mean/min | sealed attack review | sealed OOD hard mean/max | sealed OOD review mean/max |
|---|---:|---:|---:|---:|---:|---:|
| C0_c4_histgb | 0.9590/0.9016 | 0.0400 | 0.9942/0.9922 | 0.0043 | 0.0029/0.0034 | 0.0789/0.1047 |
| N1_mlp_erm | 0.9299/0.9231 | 0.0000 | 0.7289/0.7211 | 0.0000 | 0.0046/0.0046 | 0.0000/0.0000 |
| N2_dann_device_family | 0.8128/0.7514 | 0.0000 | 0.7803/0.7350 | 0.0000 | 0.0047/0.0049 | 0.0000/0.0000 |
| N3_dann_source_family | 0.8981/0.8698 | 0.0000 | 0.7665/0.7412 | 0.0000 | 0.0048/0.0050 | 0.0000/0.0000 |

## Leave-device-family stress

| variant | held value | role | rows | hard | review | raw |
|---|---|---|---:|---:|---:|---:|
| C0_c4_histgb | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0037 | 0.0468 | 0.0504 |
| N1_mlp_erm | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0054 | 0.0000 | 0.0054 |
| N2_dann_device_family | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0054 | 0.0000 | 0.0054 |
| C0_c4_histgb | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0026 | 0.0193 | 0.0219 |
| N1_mlp_erm | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0032 | 0.0000 | 0.0032 |
| N2_dann_device_family | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0032 | 0.0000 | 0.0032 |
| C0_c4_histgb | iotsim-stream-consumer | ood_stress | 79950 | 0.9977 | 0.0009 | 0.9986 |
| N1_mlp_erm | iotsim-stream-consumer | ood_stress | 79950 | 0.9976 | 0.0000 | 0.9976 |
| N2_dann_device_family | iotsim-stream-consumer | ood_stress | 79950 | 0.9971 | 0.0000 | 0.9971 |
| C0_c4_histgb | iotsim-hydraulic-system | ood_val | 12205 | 0.5083 | 0.1926 | 0.7009 |
| N1_mlp_erm | iotsim-hydraulic-system | ood_val | 12205 | 0.3897 | 0.0846 | 0.4743 |
| N2_dann_device_family | iotsim-hydraulic-system | ood_val | 12205 | 0.2977 | 0.0000 | 0.2977 |

## Representation shortcut probe

| variant | target | eval role | known label rate | known-label balanced acc | all-label balanced acc |
|---|---|---|---:|---:|---:|
| C0_c4_histgb | device_family | ood_stress | 1.0000 | 0.9987 | 0.9987 |
| C0_c4_histgb | device_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| C0_c4_histgb | source_family | ood_stress | 1.0000 | 0.9987 | 0.9987 |
| C0_c4_histgb | source_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| N1_mlp_erm | device_family | ood_stress | 1.0000 | 0.9978 | 0.9978 |
| N1_mlp_erm | device_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| N1_mlp_erm | source_family | ood_stress | 1.0000 | 0.9978 | 0.9978 |
| N1_mlp_erm | source_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| N2_dann_device_family | device_family | ood_stress | 1.0000 | 0.9972 | 0.9972 |
| N2_dann_device_family | device_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| N2_dann_device_family | source_family | ood_stress | 1.0000 | 0.9972 | 0.9972 |
| N2_dann_device_family | source_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| N3_dann_source_family | device_family | ood_stress | 1.0000 | 0.9973 | 0.9973 |
| N3_dann_source_family | device_family | sealed_final_ood | 0.0000 | nan | 0.0000 |
| N3_dann_source_family | source_family | ood_stress | 1.0000 | 0.9973 | 0.9973 |
| N3_dann_source_family | source_family | sealed_final_ood | 0.0000 | nan | 0.0000 |

## Guardrail

- A valid deep invariant improvement must reduce sealed OOD review/hard without sacrificing sealed/future attack hard detection.
- It must reduce leave-device-family collapse.
- Lower domain-probe accuracy is useful only if detection guardrails also pass.
- This is causal-inspired invariant representation learning, not a full causal discovery claim.

Runtime seconds: `576.7`.
