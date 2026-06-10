# issue27bt Next Action

recommended_next_action = `issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay`

- The lightweight temporal head has a strong medium diagnostic signal, but it must be stress-tested before any larger claim.
- Next step should run group/file-disjoint replay, remove parent `ood_risk` in an ablation, and verify the result is not a time-half/source-adjacency artifact.
- If those stability checks fail, then construct mini flow-interaction metadata from PCAP/processed CSV or run a task-boundary audit.
- Keep final/report-only roles sealed.
