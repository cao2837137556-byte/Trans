# issue27bt Summary

1. issue27bt completed: yes
2. primary_verdict: `temporal_head_group_stable_with_parent_evidence_no_parent_ood_overbudget`
3. task type: temporal head stability/ablation/group-disjoint validation
4. 115D frontend changed: no
5. split/support changed: no
6. final/report-only used for fit/selection: no
7. time_half current_plus_temporal report attack min: `0.972972972972973`
8. time_half no_parent_oodrisk report attack min: `0.481981981981982`
9. group_disjoint current_plus_temporal report attack min: `0.9707207207207207`
10. group_disjoint no_parent_oodrisk report attack min: `0.9831111111111112`
11. group_disjoint no_parent_oodrisk dev attack min: `0.9375`
12. group_disjoint no_parent_oodrisk dev OOD max: `0.025333333333333333`
13. group_disjoint no_parent_oodrisk final OOD max: `0.0`
14. group_disjoint current_plus_temporal dev attack/OOD/report attack: `1.0` / `0.0` / `0.9707207207207207`
15. caveat: id_calib is single-source in the medium asset, so full group-disjoint threshold calibration needs broader asset validation.
16. interpretation: temporal signal is group-stable with parent evidence; no-parent ablation keeps attack high but fails the 1% dev OOD budget.
17. next action: `issue27bu_no_parent_temporal_ood_risk_repair_or_mini_flow_graph`
18. formal benchmark allowed: no
19. commit hash: reported in final response
