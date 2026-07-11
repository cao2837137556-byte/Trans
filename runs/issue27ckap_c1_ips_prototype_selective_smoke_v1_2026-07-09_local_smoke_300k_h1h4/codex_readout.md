# issue27ckap_c1_ips_prototype_selective_smoke_v1_2026-07-09

## Selected held families

| held family | total | OOD | attack | ood_val | ood_stress | sealed OOD | future | sealed attack |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iotsim-stream-consumer | 4000 | 4000 | 0 | 0 | 4000 | 0 | 0 | 0 |
| iotsim-hydraulic-system | 4000 | 4000 | 0 | 4000 | 0 | 0 | 0 | 0 |
| domotic-monitor | 4000 | 0 | 4000 | 0 | 0 | 0 | 4000 | 0 |
| combined-cycle | 4000 | 0 | 4000 | 0 | 0 | 0 | 4000 | 0 |
| iotsim-ip-camera-street | 4000 | 4000 | 0 | 0 | 0 | 4000 | 0 | 0 |

## Held-family metrics

| route | held family | role | rows | hard | raw | review | desired | error |
|---|---|---|---:|---:|---:|---:|---|---:|
| H1_c1_mlp_ce | iotsim-stream-consumer | ood_stress | 4000 | 1.0000 | 1.0000 | 0.0000 | low | 1.0000 |
| H2_c1_supcon_proto | iotsim-stream-consumer | ood_stress | 4000 | 1.0000 | 1.0000 | 0.0000 | low | 1.0000 |
| H3_c1_supcon_rex_proto | iotsim-stream-consumer | ood_stress | 4000 | 1.0000 | 1.0000 | 0.0000 | low | 1.0000 |
| H4_c1_supcon_rex_proto_selective_budget | iotsim-stream-consumer | ood_stress | 4000 | 1.0000 | 1.0000 | 0.0000 | low | 1.0000 |
| H1_c1_mlp_ce | iotsim-hydraulic-system | ood_val | 4000 | 0.9978 | 0.9978 | 0.0000 | low | 0.9978 |
| H2_c1_supcon_proto | iotsim-hydraulic-system | ood_val | 4000 | 0.9998 | 0.9998 | 0.0000 | low | 0.9998 |
| H3_c1_supcon_rex_proto | iotsim-hydraulic-system | ood_val | 4000 | 0.9958 | 0.9958 | 0.0000 | low | 0.9958 |
| H4_c1_supcon_rex_proto_selective_budget | iotsim-hydraulic-system | ood_val | 4000 | 0.9958 | 0.9958 | 0.0000 | low | 0.9958 |
| H1_c1_mlp_ce | domotic-monitor | future_query | 4000 | 0.9782 | 0.9782 | 0.0000 | high | 0.0218 |
| H2_c1_supcon_proto | domotic-monitor | future_query | 4000 | 0.9798 | 0.9798 | 0.0000 | high | 0.0202 |
| H3_c1_supcon_rex_proto | domotic-monitor | future_query | 4000 | 0.9698 | 0.9698 | 0.0000 | high | 0.0302 |
| H4_c1_supcon_rex_proto_selective_budget | domotic-monitor | future_query | 4000 | 0.9698 | 0.9698 | 0.0000 | high | 0.0302 |
| H1_c1_mlp_ce | combined-cycle | future_query | 4000 | 0.4437 | 0.4437 | 0.0000 | high | 0.5563 |
| H2_c1_supcon_proto | combined-cycle | future_query | 4000 | 0.4113 | 0.4120 | 0.0008 | high | 0.5887 |
| H3_c1_supcon_rex_proto | combined-cycle | future_query | 4000 | 0.3935 | 0.3940 | 0.0005 | high | 0.6065 |
| H4_c1_supcon_rex_proto_selective_budget | combined-cycle | future_query | 4000 | 0.3935 | 0.3940 | 0.0000 | high | 0.6065 |
| H1_c1_mlp_ce | iotsim-ip-camera-street | sealed_final_ood | 4000 | 0.0025 | 0.0025 | 0.0000 | low | 0.0025 |
| H2_c1_supcon_proto | iotsim-ip-camera-street | sealed_final_ood | 4000 | 0.0020 | 0.0020 | 0.0000 | low | 0.0020 |
| H3_c1_supcon_rex_proto | iotsim-ip-camera-street | sealed_final_ood | 4000 | 0.0020 | 0.0020 | 0.0000 | low | 0.0020 |
| H4_c1_supcon_rex_proto_selective_budget | iotsim-ip-camera-street | sealed_final_ood | 4000 | 0.0020 | 0.0020 | 0.0000 | low | 0.0020 |

## Guardrail

- Fixed frontend: C1 CICFlow-style evidence from issue27ckai.
- Fit/select exclude held device_family.
- Eval includes only held device_family.
- Prototype/review thresholds use non-held legal select roles only.
- Query/future/sealed roles are report-only.
- Runtime seconds: 413.5.
