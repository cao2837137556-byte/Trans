# issue27ba Summary

1. issue27ba completed: yes
2. primary_verdict: `stress_gate_kills_attack_repair_needed`
3. task type: disjoint OOD stress pool plus gate selection diagnostic; not formal benchmark
4. 115D frontend/split changed: no
5. OOD stress source: unused pre-registered OOD-val benign files only
6. final OOD used for stress selection/gate selection: no
7. attack eval/dev-heavy query used for gate selection: no
8. OOD stress rows: `6000`
9. OOD stress devices: `{"building-monitor": 2000, "predictive-maintenance": 2000, "stream-consumer": 2000}`
10. selected gate: `per_seed_dev_selected_mixed`
11. selected active label budget: `per_seed_dev_selected`
12. selected radius quantile: `per_seed_dev_selected`
13. selected margin: `per_seed_dev_selected`
14. triple attack hard min: `0.0`
15. OOD val hard max: `0.0`
16. OOD stress hard max: `0.0`
17. final OOD hard max report-only: `0.0023333333333333335`
18. current formal benchmark allowed: no
19. next action: `issue27bb_attack_preserving_ood_gate_repair_on_disjoint_stress_pool`
20. commit hash: pending
