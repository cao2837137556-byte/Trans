# Region-Aware OOD-Safe Gate Logic Spec

This task adds a post-score gate after issue27ay per-region heads.

- `no_gate`: attack alarm is `medium_head OR heavy_head`.
- `soft_benign_veto`: raw alarms close to benign/OOD and without enough attack advantage go to review or suppress.
- `attack_advantage_margin`: raw alarms become hard alarms only when attack coverage beats benign/OOD coverage by a pre-registered margin.
- `conflict_to_review`: raw alarms close to both attack and benign/OOD are reviewed; benign-only raw alarms are suppressed.

All radii and margins are selected from dev roles only. Final OOD, medium attack eval, and dev-heavy query are replay-only.
