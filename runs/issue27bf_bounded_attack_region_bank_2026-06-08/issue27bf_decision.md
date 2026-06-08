# issue27bf Decision

primary_verdict = `bounded_attack_bank_heavy_gain_medium_retention_failure`

- selected config: `{"attack_outer_norm": 1.0, "benign_core_norm": 0.75, "conflict_slack": 1.0, "inner_radius_q": 0.75, "outer_radius_q": 0.95, "prototype_budget": 128, "region_balance": "equal_region_total", "region_max": 8, "region_policy": "cluster_kcenter", "review_budget": 0.03, "score_floor_q": 0.0, "subspace_name": "HH_HpHp", "top_k": 3}`
- dev attack hard min: `0.6428571428571429`
- report-only attack hard min: `0.6415`
- OOD stress hard max: `0.002456140350877193`
- final OOD hard max report-only: `0.154`
- dev review max: `0.02982456140350877`

Go/No-Go: only attack hard min >= 0.93 with OOD stress <=2% and review <=5% should proceed to OOD-gate repair. This run does not authorize formal benchmark by itself.
