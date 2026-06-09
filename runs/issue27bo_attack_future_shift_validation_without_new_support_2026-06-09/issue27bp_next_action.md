# issue27bp Next Action

recommended_next_action = `issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation`

- If proceeding to OOD repair, keep the frozen support and attack threshold path intact.
- OOD repair must be attack-preserving and must report whether it kills the validated future-shift attack buckets.
- Final/report-only roles remain replay-only and cannot be used for gate selection.
