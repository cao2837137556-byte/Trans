# issue27bs Summary

1. issue27bs completed: yes
2. primary_verdict: `temporal_evidence_head_dev_passed_ready_for_controller_stability`
3. task type: lightweight temporal-evidence head diagnostic
4. 115D frontend changed: no
5. split/support changed: no
6. final/report-only used for fit/selection: no
7. selected feature set: `current_plus_temporal`
8. selected model kind: `histgb_shallow`
9. dev attack min: `1.0`
10. dev OOD max: `0.0`
11. report-only attack min: `0.972972972972973`
12. final OOD max report-only: `0.004333333333333333`
13. bq base dev attack min: `0.984375`
14. bq base dev OOD max: `0.25933333333333336`
15. bq base report-only attack min: `0.6501501501501501`
16. caveat: current validation is time-half fit/select, not group/file-disjoint.
17. caveat: selected feature set includes parent BQ evidence; ablation is required.
18. next action: `issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay`
19. formal benchmark allowed: no
20. commit hash: reported in final response
