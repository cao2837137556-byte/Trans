# issue27ckg Label Support Region Registry Summary

primary_verdict: `label_support_region_registry_v1_and_versioned_update_protocol_ready`

- formal region kind: `label_support_region`
- exact-label regions: `10`
- support_train_view_v1 rows: `385`
- support_val_view_v1 rows: `127`
- initial 512 mutated: `false`
- unknown-traffic autorouting by region: `false`
- geometric strong/weak role: `diagnostic only`
- simulation archive events: `6`
- simulation accepted/quarantined: `2` / `4`
- simulation promotions: `2`
- simulation support view rows: `387`
- production promotion enabled: `false` pending empirical budget certification
- model training: `false`
- sealed-final access: `false`

Close-out:

```text
solved: Instantiated one exact-label support-region registry, immutable initial train/validation views, append-only archive and candidate schemas, budgeted promotion policy, version lineage, model-update contract, rollback contract, and an end-to-end simulation.
changed_mainline: yes
active_blocker: production extension budgets and model non-regression are not yet empirically certified; wait for the frozen issue27ckc capability replay before choosing the first model-update ablation.
frozen: one formal label-support-region abstraction, initial 385/127 role split, archive/candidate hard gates, version lineage, and rollback semantics.
superseded: treating geometric strong/weak regions as a required deployment registry or using them to force unknown traffic into known labels.
next_action: certify_update_budget_and_run_binary_attack_head_nonregression_ablation_after_issue27ckc_results.
```
