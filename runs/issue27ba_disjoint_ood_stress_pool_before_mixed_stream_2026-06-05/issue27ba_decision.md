# Issue27ba Decision

primary_verdict = `stress_gate_kills_attack_repair_needed`

- Constructed a disjoint dev-side OOD stress pool from unused pre-registered OOD-val benign files.
- Did not use final OOD, attack eval, or dev-heavy query for gate/radius/threshold selection.
- Did not change the 115D frontend or existing medium split.
- Recommended next issue: `issue27bb_attack_preserving_ood_gate_repair_on_disjoint_stress_pool`.
