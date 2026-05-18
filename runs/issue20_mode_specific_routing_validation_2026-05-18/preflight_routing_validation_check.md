# Preflight Routing Validation Check

- V1 fixed as original100 + kcenter32 + fixed guard LR: yes.
- V2 fixed as selected_source_rich_top32 + kcenter32 + fixed guard LR: yes.
- Routing rule uses validation-side OOD alarm and attack validation proxy only: yes.
- Routing rule does not use final OOD eval or final attack eval: yes.
- Strategies include always-V1, always-V2, OR, AND, routed, and oracle upper bound: yes.
- Review queue and conflict counts are recorded: yes.
- Primary low-OOD V2 OOD-over-budget negative result is retained: yes.
- holdout_bin_2 V1 detection collapse is retained: yes.
- No V1/V2 threshold or model definition is changed: yes.
- Routing rule is fixed before this run and not adjusted by results: yes.
