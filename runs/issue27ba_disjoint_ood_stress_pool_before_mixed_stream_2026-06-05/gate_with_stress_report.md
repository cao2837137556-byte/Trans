# Gate With Disjoint OOD Stress Report

primary_verdict = `stress_gate_kills_attack_repair_needed`

The OOD stress pool is dev-side and selected before looking at final OOD replay.

## Selected Replay Stats

- selected_active_label_budget: `per_seed_dev_selected`
- selected_gate_name: `per_seed_dev_selected_mixed`
- selected_radius_quantile: `per_seed_dev_selected`
- selected_margin: `per_seed_dev_selected`
- selected_config_count: `4`
- selected_configs: `budget=128|gate=attack_advantage_margin|q=0.75|margin=-0.25;budget=128|gate=attack_advantage_margin|q=0.95|margin=-0.25;budget=64|gate=attack_advantage_margin|q=0.75|margin=-0.25;budget=64|gate=attack_advantage_margin|q=0.95|margin=-0.25`
- triple_attack_hard_min: `0.0`
- triple_attack_score_or_review_min: `0.0`
- medium_attack_hard_min: `0.064`
- dev_heavy_hard_min: `0.076`
- final_ood_hard_max: `0.0023333333333333335`
- final_ood_review_max: `0.014666666666666666`
- ood_val_hard_max: `0.0`
- ood_val_review_max: `0.0`
- ood_stress_hard_max: `0.0`
- ood_stress_review_max: `0.0007017543859649122`

## Interpretation Rule

- If OOD stress is controlled but final OOD still explodes, the stress pool still misses the final tail.
- If OOD stress itself explodes, the gate repair has a legal dev signal and should be fixed before mixed-stream work.
- Final OOD remains report-only and cannot change this issue's selected gate.
