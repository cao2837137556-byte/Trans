# issue27ckao_c1_strict_leave_device_family_canary_v1_2026-07-09

Mode: `smoke`

## Selected held device families

| held family | total | OOD rows | attack rows | ood_val | ood_stress | sealed OOD | future attack | sealed attack |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iotsim-stream-consumer | 3000 | 3000 | 0 | 0 | 3000 | 0 | 0 | 0 |
| iotsim-hydraulic-system | 3000 | 3000 | 0 | 3000 | 0 | 0 | 0 | 0 |
| domotic-monitor | 3000 | 0 | 3000 | 0 | 0 | 0 | 3000 | 0 |
| combined-cycle | 3000 | 0 | 3000 | 0 | 0 | 0 | 3000 | 0 |
| iotsim-ip-camera-street | 3000 | 3000 | 0 | 0 | 0 | 3000 | 0 | 0 |

## Held-family evaluation

| candidate | held family | role | rows | hard rate | desired | error |
|---|---|---|---:|---:|---|---:|
| G1_graph_interaction_only_histgb | iotsim-stream-consumer | ood_val | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | iotsim-stream-consumer | ood_stress | 3000 | 1.0000 | low | 1.0000 |
| G1_graph_interaction_only_histgb | iotsim-stream-consumer | future_query | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | iotsim-stream-consumer | sealed_final_ood | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | iotsim-stream-consumer | sealed_final_attack | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | iotsim-stream-consumer | ood_val | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | iotsim-stream-consumer | ood_stress | 3000 | 0.9330 | low | 0.9330 |
| Z1_zeek_semantic_only_histgb | iotsim-stream-consumer | future_query | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | iotsim-stream-consumer | sealed_final_ood | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | iotsim-stream-consumer | sealed_final_attack | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | iotsim-stream-consumer | ood_val | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | iotsim-stream-consumer | ood_stress | 3000 | 1.0000 | low | 1.0000 |
| N1_netflow_style_only_histgb | iotsim-stream-consumer | future_query | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | iotsim-stream-consumer | sealed_final_ood | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | iotsim-stream-consumer | sealed_final_attack | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | iotsim-stream-consumer | ood_val | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | iotsim-stream-consumer | ood_stress | 3000 | 1.0000 | low | 1.0000 |
| C1_cicflow_style_only_histgb | iotsim-stream-consumer | future_query | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | iotsim-stream-consumer | sealed_final_ood | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | iotsim-stream-consumer | sealed_final_attack | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | iotsim-stream-consumer | ood_val | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | iotsim-stream-consumer | ood_stress | 3000 | 1.0000 | low | 1.0000 |
| M1_all_external_blocks_histgb | iotsim-stream-consumer | future_query | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | iotsim-stream-consumer | sealed_final_ood | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | iotsim-stream-consumer | sealed_final_attack | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-stream-consumer | ood_val | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-stream-consumer | ood_stress | 3000 | 1.0000 | low | 1.0000 |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-stream-consumer | future_query | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-stream-consumer | sealed_final_ood | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-stream-consumer | sealed_final_attack | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | iotsim-hydraulic-system | ood_val | 3000 | 0.6113 | low | 0.6113 |
| G1_graph_interaction_only_histgb | iotsim-hydraulic-system | ood_stress | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | iotsim-hydraulic-system | future_query | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | iotsim-hydraulic-system | sealed_final_ood | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | iotsim-hydraulic-system | sealed_final_attack | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | iotsim-hydraulic-system | ood_val | 3000 | 0.0263 | low | 0.0263 |
| Z1_zeek_semantic_only_histgb | iotsim-hydraulic-system | ood_stress | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | iotsim-hydraulic-system | future_query | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | iotsim-hydraulic-system | sealed_final_ood | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | iotsim-hydraulic-system | sealed_final_attack | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | iotsim-hydraulic-system | ood_val | 3000 | 0.2577 | low | 0.2577 |
| N1_netflow_style_only_histgb | iotsim-hydraulic-system | ood_stress | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | iotsim-hydraulic-system | future_query | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | iotsim-hydraulic-system | sealed_final_ood | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | iotsim-hydraulic-system | sealed_final_attack | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | iotsim-hydraulic-system | ood_val | 3000 | 0.9907 | low | 0.9907 |
| C1_cicflow_style_only_histgb | iotsim-hydraulic-system | ood_stress | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | iotsim-hydraulic-system | future_query | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | iotsim-hydraulic-system | sealed_final_ood | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | iotsim-hydraulic-system | sealed_final_attack | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | iotsim-hydraulic-system | ood_val | 3000 | 1.0000 | low | 1.0000 |
| M1_all_external_blocks_histgb | iotsim-hydraulic-system | ood_stress | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | iotsim-hydraulic-system | future_query | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | iotsim-hydraulic-system | sealed_final_ood | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | iotsim-hydraulic-system | sealed_final_attack | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-hydraulic-system | ood_val | 3000 | 1.0000 | low | 1.0000 |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-hydraulic-system | ood_stress | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-hydraulic-system | future_query | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-hydraulic-system | sealed_final_ood | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-hydraulic-system | sealed_final_attack | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | domotic-monitor | ood_val | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | domotic-monitor | ood_stress | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | domotic-monitor | future_query | 3000 | 0.9203 | high | 0.0797 |
| G1_graph_interaction_only_histgb | domotic-monitor | sealed_final_ood | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | domotic-monitor | sealed_final_attack | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | domotic-monitor | ood_val | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | domotic-monitor | ood_stress | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | domotic-monitor | future_query | 3000 | 0.9990 | high | 0.0010 |
| Z1_zeek_semantic_only_histgb | domotic-monitor | sealed_final_ood | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | domotic-monitor | sealed_final_attack | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | domotic-monitor | ood_val | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | domotic-monitor | ood_stress | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | domotic-monitor | future_query | 3000 | 1.0000 | high | 0.0000 |
| N1_netflow_style_only_histgb | domotic-monitor | sealed_final_ood | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | domotic-monitor | sealed_final_attack | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | domotic-monitor | ood_val | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | domotic-monitor | ood_stress | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | domotic-monitor | future_query | 3000 | 0.9943 | high | 0.0057 |
| C1_cicflow_style_only_histgb | domotic-monitor | sealed_final_ood | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | domotic-monitor | sealed_final_attack | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | domotic-monitor | ood_val | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | domotic-monitor | ood_stress | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | domotic-monitor | future_query | 3000 | 0.9943 | high | 0.0057 |
| M1_all_external_blocks_histgb | domotic-monitor | sealed_final_ood | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | domotic-monitor | sealed_final_attack | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | domotic-monitor | ood_val | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | domotic-monitor | ood_stress | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | domotic-monitor | future_query | 3000 | 0.9987 | high | 0.0013 |
| M2_raw115_plus_all_external_blocks_histgb | domotic-monitor | sealed_final_ood | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | domotic-monitor | sealed_final_attack | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | combined-cycle | ood_val | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | combined-cycle | ood_stress | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | combined-cycle | future_query | 3000 | 0.4327 | high | 0.5673 |
| G1_graph_interaction_only_histgb | combined-cycle | sealed_final_ood | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | combined-cycle | sealed_final_attack | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | combined-cycle | ood_val | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | combined-cycle | ood_stress | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | combined-cycle | future_query | 3000 | 0.8477 | high | 0.1523 |
| Z1_zeek_semantic_only_histgb | combined-cycle | sealed_final_ood | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | combined-cycle | sealed_final_attack | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | combined-cycle | ood_val | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | combined-cycle | ood_stress | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | combined-cycle | future_query | 3000 | 0.5180 | high | 0.4820 |
| N1_netflow_style_only_histgb | combined-cycle | sealed_final_ood | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | combined-cycle | sealed_final_attack | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | combined-cycle | ood_val | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | combined-cycle | ood_stress | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | combined-cycle | future_query | 3000 | 0.9817 | high | 0.0183 |
| C1_cicflow_style_only_histgb | combined-cycle | sealed_final_ood | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | combined-cycle | sealed_final_attack | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | combined-cycle | ood_val | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | combined-cycle | ood_stress | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | combined-cycle | future_query | 3000 | 0.9817 | high | 0.0183 |
| M1_all_external_blocks_histgb | combined-cycle | sealed_final_ood | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | combined-cycle | sealed_final_attack | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | combined-cycle | ood_val | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | combined-cycle | ood_stress | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | combined-cycle | future_query | 3000 | 0.9817 | high | 0.0183 |
| M2_raw115_plus_all_external_blocks_histgb | combined-cycle | sealed_final_ood | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | combined-cycle | sealed_final_attack | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | iotsim-ip-camera-street | ood_val | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | iotsim-ip-camera-street | ood_stress | 0 | nan | low | nan |
| G1_graph_interaction_only_histgb | iotsim-ip-camera-street | future_query | 0 | nan | high | nan |
| G1_graph_interaction_only_histgb | iotsim-ip-camera-street | sealed_final_ood | 3000 | 0.0280 | low | 0.0280 |
| G1_graph_interaction_only_histgb | iotsim-ip-camera-street | sealed_final_attack | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | iotsim-ip-camera-street | ood_val | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | iotsim-ip-camera-street | ood_stress | 0 | nan | low | nan |
| Z1_zeek_semantic_only_histgb | iotsim-ip-camera-street | future_query | 0 | nan | high | nan |
| Z1_zeek_semantic_only_histgb | iotsim-ip-camera-street | sealed_final_ood | 3000 | 0.0077 | low | 0.0077 |
| Z1_zeek_semantic_only_histgb | iotsim-ip-camera-street | sealed_final_attack | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | iotsim-ip-camera-street | ood_val | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | iotsim-ip-camera-street | ood_stress | 0 | nan | low | nan |
| N1_netflow_style_only_histgb | iotsim-ip-camera-street | future_query | 0 | nan | high | nan |
| N1_netflow_style_only_histgb | iotsim-ip-camera-street | sealed_final_ood | 3000 | 0.1723 | low | 0.1723 |
| N1_netflow_style_only_histgb | iotsim-ip-camera-street | sealed_final_attack | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | iotsim-ip-camera-street | ood_val | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | iotsim-ip-camera-street | ood_stress | 0 | nan | low | nan |
| C1_cicflow_style_only_histgb | iotsim-ip-camera-street | future_query | 0 | nan | high | nan |
| C1_cicflow_style_only_histgb | iotsim-ip-camera-street | sealed_final_ood | 3000 | 0.0050 | low | 0.0050 |
| C1_cicflow_style_only_histgb | iotsim-ip-camera-street | sealed_final_attack | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | iotsim-ip-camera-street | ood_val | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | iotsim-ip-camera-street | ood_stress | 0 | nan | low | nan |
| M1_all_external_blocks_histgb | iotsim-ip-camera-street | future_query | 0 | nan | high | nan |
| M1_all_external_blocks_histgb | iotsim-ip-camera-street | sealed_final_ood | 3000 | 0.0050 | low | 0.0050 |
| M1_all_external_blocks_histgb | iotsim-ip-camera-street | sealed_final_attack | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-ip-camera-street | ood_val | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-ip-camera-street | ood_stress | 0 | nan | low | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-ip-camera-street | future_query | 0 | nan | high | nan |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-ip-camera-street | sealed_final_ood | 3000 | 0.4237 | low | 0.4237 |
| M2_raw115_plus_all_external_blocks_histgb | iotsim-ip-camera-street | sealed_final_attack | 0 | nan | high | nan |

## Guardrail

- Fit roles exclude the held device_family.
- Threshold/select roles exclude the held device_family.
- Evaluation includes only the held device_family.
- Query/future/sealed roles remain report-only.
- This is a Level-2 canary, not cross-dataset proof.
- Runtime seconds: 374.7.
