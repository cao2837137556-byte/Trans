# issue27bs Next Action

recommended_next_action = `issue27bs_mini_interaction_graph_or_temporal_controller_repair_without_final_leakage`

- If past-only temporal features have signal but the controller remains overbudget, test a controller repair with bounded review and sealed final replay.
- If temporal signal is weak because sidecar lacks flow fields, build a mini interaction-graph diagnostic from PCAP/sidecar metadata before rejecting the graph route.
- Do not move to full/formal benchmark until attack evidence and OOD-risk are both stable under dev-side constraints.
