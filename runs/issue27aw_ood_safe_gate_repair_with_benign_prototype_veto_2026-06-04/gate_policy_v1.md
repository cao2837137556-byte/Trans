# Gate Policy v1

Draft diagnostic policy, frozen per seed from development roles only.

- Base alarm comes from the existing old-protocol HistGB score and NP/order-stat threshold.
- ID/OOD/attack prototype coverage is computed in a common StandardScaler space fitted on ID fit, OOD train, and base support train.
- `benign_prototype_veto_v1`: suppress base alarms that are benign-covered but not attack-covered.
- `conflict_review_v1`: suppress benign-only alarms and route benign+attack conflicts to review.
- `attack_advantage_*`: allow benign-covered alarms only when attack distance is closer than benign distance by the dev-calibrated margin.
- Final OOD cannot be used to pick the gate or margin.
