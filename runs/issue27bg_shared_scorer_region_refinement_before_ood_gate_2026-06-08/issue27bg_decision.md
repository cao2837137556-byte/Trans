# issue27bg Decision

primary_verdict = `shared_scorer_no_sufficient_attack_recovery`

- selected config: `{"attack_outer_norm": 1.0, "benign_core_norm": 0.75, "conflict_slack": 1.0, "inner_radius_q": 0.75, "outer_radius_q": 0.95, "prototype_budget": 128, "region_max": 8, "region_policy": "cluster_kcenter", "review_budget": 0.03, "scorer_kind": "shared_histgb", "subspace_name": "HH_HpHp", "top_k": 3, "weighting_policy": "medium_region_boost"}`
- dev attack hard min: `0.6428571428571429`
- report-only attack hard min: `0.4062222222222222`
- OOD stress hard max: `0.0`
- final OOD hard max report-only: `0.0006666666666666666`
- dev review max: `0.02982456140350877`

Go/No-Go: OOD-gate repair is allowed only if attack hard min >= 0.93 with OOD stress <=2% and review <=5%.
