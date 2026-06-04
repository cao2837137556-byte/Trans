# OOD-Safe Gate Repair Report

primary_verdict = `benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged`

This is a diagnostic gate repair on the medium Gotham Kitsune115 asset. It is not a formal benchmark.

Gate selection used only ID calibration, OOD validation, and base support validation. Final OOD, medium attack eval, and dev-heavy query were replay-only.

## Selected Gate Counts

- attack_advantage_margin_dev_v1: `5` seeds

## Report-Only Replay Summary

- final OOD after hard alarm max: `0.261`
- final OOD after attention max: `0.261`
- dev-heavy after detection min: `0.991`
- medium attack after detection min: `0.7644444444444445`
- fixed benign veto final OOD hard alarm max: `0.0026666666666666666`
- fixed benign veto dev-heavy detection min: `0.08975`
- fixed benign veto medium attack detection min: `0.628`

If the candidate is supported, the next step still requires a clean sealed-final replay because the current final OOD has already been used diagnostically in issue27av.
