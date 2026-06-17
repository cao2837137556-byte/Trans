# issue27cj Next Action

Recommended next issue:

`issue27cj_attack_region_instantiation_on_frozen_support_bank`

Scope:

- Use issue27cf `support_train` to propose candidate regions/prototypes.
- Use issue27cf `support_val` to validate compactness and shell behavior.
- Use development benign/OOD roles only for OOD-overlap audit.
- Use certified issue27ch dev query only for protocol stress reports.
- Do not train models, tune controller thresholds, or access sealed final roles.

Expected outputs:

- `initial_region_registry_v1.csv`
- `prototype_manifest.csv`
- `region_compactness_audit.csv`
- `support_val_shell_audit.csv`
- `ood_overlap_audit.csv`
- `certified_dev_query_region_stress.csv`
- `region_limitations.md`

Open until issue27cj:

- exact distance metric;
- standardization recipe;
- candidate split/merge thresholds;
- shell radius quantiles;
- unknown-rate interpretation.
