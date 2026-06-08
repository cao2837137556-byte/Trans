# Issue27bg Next Action

recommended_next_action = `issue27bg_shared_scorer_region_refinement_before_ood_gate`

- If strong-ready, repair OOD gate while preserving attack bank.
- This run is not strong-ready because attack hard min is below 0.93.
- Next: improve the attack-side scorer/region construction first, e.g. a shared scorer with region-balanced calibration or a region-refinement diagnostic.
- Do not run full/larger formal benchmark from this medium diagnostic.
