# issue27bg Summary

1. issue27bg completed: yes
2. primary_verdict: `shared_scorer_no_sufficient_attack_recovery`
3. task type: shared scorer + bounded region bank diagnostic; not formal benchmark
4. 115D frontend changed: no
5. split changed: no
6. raw scorer changed: yes, from issue27bd two-head replay to shared HistGB attack scorer
7. selected config: `{"attack_outer_norm": 1.0, "benign_core_norm": 0.75, "conflict_slack": 1.0, "inner_radius_q": 0.75, "outer_radius_q": 0.95, "prototype_budget": 128, "region_max": 8, "region_policy": "cluster_kcenter", "review_budget": 0.03, "scorer_kind": "shared_histgb", "subspace_name": "HH_HpHp", "top_k": 3, "weighting_policy": "medium_region_boost"}`
8. dev attack hard min: `0.6428571428571429`
9. report-only attack hard min: `0.4062222222222222`
10. OOD stress hard max: `0.0`
11. final OOD hard max report-only: `0.0006666666666666666`
12. dev review max: `0.02982456140350877`
13. final review max report-only: `0.03`
14. attack >=0.93 gate passed: `False`
15. OOD stress <=2% guard passed: `True`
16. review <=5% guard passed: `True`
17. final/report-only used for selection: no
18. current formal benchmark allowed: no
19. next action: `issue27bh_attack_scorer_region_design_rethink_before_ood_gate`
20. commit hash: reported in final response
