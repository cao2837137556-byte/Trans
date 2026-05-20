# Preflight Primary Non-Regression Check

- Successfully read issue22 top64 results: yes.
- V1 / V2_top32 / V2_top64 complete primary metrics are available: yes.
- primary_lowood detection already exists in issue22 outputs: yes.
- Rebuild was not needed: fixed issue22 seed-level outputs were reused.
- V2_top64 is fixed as source_rich_top64 + kcenter32 + fixed guard LR: yes.
- topK was not re-selected: yes.
- final eval was not used to adjust thresholds: yes.
- seed-level metrics are available: yes.
- low-alert / alarm-budget metrics are available: yes.
- This is non-regression check, not locked validation: yes.
