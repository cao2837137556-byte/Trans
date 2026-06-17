# Protocol Invariants

These invariants must hold for issue27cj and later support-region work unless a later issue explicitly supersedes them.

1. `exact_attack_label != semantic_attack_group != provenance_seed != active_evidence_region`.
2. A single exact label may produce zero, one, or multiple candidate regions.
3. Multiple exact labels may overlap; overlap can produce `active_conflict_sensitive`, `ambiguous_region`, or future merge candidates.
4. A region may have multiple prototypes.
5. Numeric radius values are not frozen in issue27ci.
6. `out_of_region` means support cannot explain the sample; it does not mean benign.
7. `support_train` forms candidate regions; `support_val` validates compactness/shell behavior.
8. Certified dev query stresses protocol behavior but cannot create support, activate regions, tune thresholds, or select models.
9. Sealed final attack and sealed final OOD remain report-only.
10. The initial support bank is immutable; online update requires a separate versioned registry.
11. OOD-overlap audit must use development-allowed benign/OOD roles only and must not use sealed final OOD.
12. Region evidence is evidence only and cannot directly trigger hard/suppress/review/controller decisions in issue27ci.
