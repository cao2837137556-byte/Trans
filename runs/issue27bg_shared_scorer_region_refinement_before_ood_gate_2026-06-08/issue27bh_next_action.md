# Issue27bh Next Action

recommended_next_action = `issue27bh_attack_scorer_region_design_rethink_before_ood_gate`

- If attack >=0.93, proceed to attack-preserving OOD gate repair.
- If attack remains below 0.93, do not tune OOD gate; rethink attack-side scorer/region design first.
- Do not run full/larger formal benchmark from this medium diagnostic.
