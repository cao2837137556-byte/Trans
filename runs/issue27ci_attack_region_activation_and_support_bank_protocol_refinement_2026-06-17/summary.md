# issue27ci Summary

primary_verdict: `support_region_protocol_v1_frozen_without_region_instantiation`

issue27ci completed: yes
model_training: no
formal_benchmark: no
threshold_tuning: no
controller_changed: no
region_instantiation: no
radius_values_fixed: no
sealed_final_used: no

## Result

issue27ci freezes the attack-region protocol layer between the existing issue27cf support bank and any future region instantiation.

The current `512` support rows are clean selected support memory, not yet active attack regions. The `16` issue27cf `region_manifest.csv` rows are provenance seeds, not active geometric regions.

## Frozen Protocol

- `exact_attack_label`, `semantic_attack_group`, `provenance_seed`, `candidate_geometric_region`, and `active_evidence_region` are separate layers.
- Candidate regions must be proposed from `support_train`.
- `support_val` can validate compactness and shell behavior, but cannot create regions.
- Certified dev query can stress protocol behavior, but cannot tune thresholds, create support, or activate regions.
- Sealed final attack/OOD roles remain report-only.
- Out-of-region means `support_bank_cannot_explain`, not benign.
- Initial support bank and future online registry are separated.

## Close-out

```text
solved: Froze support_region_protocol_v1 and clarified that current 512 support rows and 16 provenance seeds are not yet active attack regions.
changed_mainline: yes
active_blocker: initial_region_registry_v1 has not been instantiated; no region prototypes, radii, shell boundaries, or OOD-overlap audits exist yet.
frozen: support-region layer definitions, activation states, role access matrix, evidence output schema, initial-vs-online registry boundary, protocol invariants.
superseded: treating exact labels, semantic groups, or issue27cf provenance region_id values as active attack regions.
next_action: issue27cj_attack_region_instantiation_on_frozen_support_bank.
```
