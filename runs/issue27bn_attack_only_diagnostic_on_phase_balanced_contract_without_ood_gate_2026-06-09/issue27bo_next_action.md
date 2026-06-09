# issue27bo Next Action

recommended_next_action = `issue27bo_ood_gate_repair_after_attack_contract_recovery`

- If dev attack is recovered but report-only remains weak, do not tune on report-only; inspect task boundary or expand legal development-side attack phases.
- If dev attack is not recovered, do not enter OOD-gate repair; revisit model head/representation only after confirming contract semantics.
- OOD-gate repair remains blocked unless legal dev attack hard-min reaches `0.93` and the report-only replay does not show an obvious task-boundary break.
