# issue27bf Summary

1. issue27bf completed: yes
2. primary_verdict: `bounded_attack_bank_heavy_gain_medium_retention_failure`
3. task type: bounded attack region bank diagnostic; bank-only; not formal benchmark
4. 115D frontend changed: no
5. split changed: no
6. raw scorer changed: no; issue27bd full-115D two-head score replayed
7. selected config: `{"attack_outer_norm": 1.0, "benign_core_norm": 0.75, "conflict_slack": 1.0, "inner_radius_q": 0.75, "outer_radius_q": 0.95, "prototype_budget": 128, "region_balance": "equal_region_total", "region_max": 8, "region_policy": "cluster_kcenter", "review_budget": 0.03, "score_floor_q": 0.0, "subspace_name": "HH_HpHp", "top_k": 3}`
8. dev attack hard min: `0.6428571428571429`
9. report-only attack hard min: `0.6415`
10. OOD stress hard max: `0.002456140350877193`
11. final OOD hard max report-only: `0.154`
12. dev review max: `0.02982456140350877`
13. final review max report-only: `0.03`
14. attack >=0.93 gate passed: `False`
15. OOD stress <=2% guard passed: `True`
16. review <=5% guard passed: `True`
17. final/report-only used for selection: no
18. current formal benchmark allowed: no
19. next action: `issue27bg_shared_scorer_region_refinement_before_ood_gate`
20. commit hash: reported in final response
