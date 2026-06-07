# Post-Run Sanity Interpretation

This run should be read as a gate-design diagnostic, not a model-performance result.

## What Happened

- The raw attack heads still produced high raw-alarm rates on attack roles.
- After adding the strict pure-attack-core rule, hard alarms collapsed to zero.
- The collapse was not caused by final/report-only leakage or split mutation.
- The prototype-purity audit shows the dominant cause: many attack rows are also close to the ID/OOD benign prototype bank, so they become `mixed_conflict` rather than pure `attack_core`.
- Under a 1% review budget, most conflict attack rows become `review_overflow_no_alarm`.

## Key Evidence

- `support_medium_val` and `support_heavy_val` raw alarm rates are near 1.0, but hard alarm rates are 0.0 under the selected strict purity gate.
- `pseudo_medium_query` and `pseudo_heavy_query` also have high raw alarm rates, but are mostly conflict/overflow.
- `medium_attack_eval_report_only` and `dev_heavy_query_report_only` raw alarm rates remain high, but hard alarm remains 0.0.
- `final_ood_report_only` hard alarm is 0.0, but this is achieved by a gate that also kills attack hard alarms.

## Scientific Reading

The result does not say that Kitsune115 has no attack signal. It says that the current distance-only purity rule cannot safely separate attack-core from benign/OOD-core in the three-bank space. A useful next step should not simply loosen review budget or tune thresholds on report-only roles. It should redesign attack-region generalization or conflict handling using only development-side data.

## Next Direction

Recommended next issue: `issue27bd_attack_region_generalization_before_temporal_gate`.

The next diagnostic should focus on why attack prototypes and benign/OOD prototypes overlap so strongly:

- region-specific or class-conditional scaling,
- attack-region merging/splitting policy,
- conflict-aware hard-alarm override with dev-side pseudo-query protection,
- or a different feature subspace for prototype gating while keeping Kitsune115 as the model input.
