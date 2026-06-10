# issue27bt Decision

primary_verdict = `temporal_head_group_stable_with_parent_evidence_no_parent_ood_overbudget`

- time_half current_plus_temporal report attack min: `0.972972972972973`
- time_half no_parent_oodrisk report attack min: `0.481981981981982`
- group_disjoint current_plus_temporal report attack min: `0.9707207207207207`
- group_disjoint no_parent_oodrisk report attack min: `0.9831111111111112`
- group_disjoint no_parent_oodrisk dev attack min: `0.9375`
- group_disjoint no_parent_oodrisk dev OOD max: `0.025333333333333333`
- group_disjoint no_parent_oodrisk final OOD max: `0.0`
- group_disjoint current_plus_temporal dev attack/OOD/report attack: `1.0` / `0.0` / `0.9707207207207207`
- parent dependency report-attack deltas time/group: `(0.490990990990991, -0.012390390390390471)`
- group drop report-attack delta: `0.0022522522522523403`
- caveat: id_calib has one source group, so group-disjoint fallback is unavoidable for that role in the current medium asset.
- interpretation: the temporal head survives source-group replay when parent BQ evidence is allowed; without parent OOD-risk, attack remains high but dev OOD is over budget.
