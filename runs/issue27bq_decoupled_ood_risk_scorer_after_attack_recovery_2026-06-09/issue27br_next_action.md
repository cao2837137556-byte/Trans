# issue27br Next Action

recommended_next_action = `issue27br_strengthen_ood_risk_or_task_boundary_before_larger`

- If the decoupled OOD-risk scorer only partially improves the frontier, do not go full.
- Next repair should either strengthen OOD-risk labels/features or run a task-boundary audit for OOD/attack overlap.
- Keep final/report-only replay sealed.
