# LOW-GUARD++ Claim Gate Decision

- primary_verdict: `lowguard_plus_plus_depends_on_high_risk_separators`
- issue27i_next_action: `issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus`

Diagnostics:

| remove_top3_dominates_lowguard_lr | remove_top3_feasible | only_top3_near_perfect | clean_independent_available | provenance_ok_no_direct_label_split | top3_final_auc_drop_share |
|---|---|---|---|---|---|
| False | True | True | False | True | 0.047384 |


Decision logic:
- Provenance maps to legal KitNET traffic statistics, not explicit label/split fields.
- Remove-top3 ablation is the main robustness gate against separator overdependence.
- Non-locked consistency is not clean independent validation; a clean independent/temporal/second-environment gate is still needed before very strong main-text upgrading.
