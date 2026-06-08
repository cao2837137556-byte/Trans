# issue27bj Next Action

recommended_next_action = `issue27bj_metric_head_refinement_or_task_boundary_audit_before_ood_gate`

- Do not enter OOD-gate repair unless attack hard min reaches at least 0.93.
- If attack recovery remains below 0.93, refine metric evidence or audit task/label boundary before touching OOD gate.
- Do not use final/report-only roles for any parameter selection.
