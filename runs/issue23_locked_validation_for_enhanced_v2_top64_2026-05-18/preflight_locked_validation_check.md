# Preflight Locked Validation Check

- Successfully read issue22 / issue22b: yes.
- Main method fixed as selected_source_rich_top64 + kcenter32 + fixed guard LR: yes.
- topK re-selected: no.
- threshold target re-selected: no.
- final eval used to select configuration: no.
- locked validation object available: yes.
- locked validation object used for top64 selection: no.
- seed-level results available: yes.
- low-FPR / OOD budget metrics available: yes.
- routing / promotion / V3 attempted: no.

Locked validation objects: `holdout_bin_5, holdout_bin_6, holdout_bin_7, holdout_bin_8`.

Excluded from locked proof:

- `holdout_bin_2`: used directly in issue22 top64 discovery.
- `holdout_bin_3`: eval bin overlaps issue22 chrono_late discovery eval bins.
- `holdout_bin_4`: eval bin overlaps issue22 chrono_late discovery eval bins.
