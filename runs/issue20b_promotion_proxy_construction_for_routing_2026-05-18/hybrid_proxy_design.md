# Hybrid Proxy Design

Clean issue20c candidate status: `no clean proxy: current candidates either under-promote holdout_bin_2 or false-promote primary_lowood`.

Displayed conservative hybrid candidate: `proxy_E_hybrid_sup0.05_sep0.25sigma_review0.010`.

Rationale:

- It keeps the low-alert gate: V2 validation OOD alarm must be <= 1%.
- It requires attack-side evidence through support-holdout detection or tail-margin improvement.
- It bounds estimated review burden.
- It does not use final OOD eval or final attack eval.

Important boundary: the displayed hybrid candidate is not sufficient as-is if it still under-promotes holdout_bin_2. Issue20b final metrics are report-only and cannot be used as the trigger in deployment.

Top diagnostic proxy rows:

| proxy_name | primary_selects_v1_rate | holdout_bin2_selects_v2_rate | chrono_selects_v2_rate | proxy_correct_rate | proxy_strict_correct_rate | feasibility_rate | max_final_ood_alarm_report_only |
|---|---|---|---|---|---|---|---|
| proxy_C_disagreement_review_budget_0.005 | 0.000000 | 1.000000 | 1.000000 | 0.666667 | 0.666667 | 0.666667 | 0.015600 |
| proxy_C_disagreement_review_budget_0.010 | 0.000000 | 1.000000 | 1.000000 | 0.666667 | 0.666667 | 0.666667 | 0.015600 |
| proxy_C_disagreement_review_budget_0.020 | 0.000000 | 1.000000 | 1.000000 | 0.666667 | 0.666667 | 0.666667 | 0.015600 |
| proxy_D_representation_relative_shift_positive | 0.000000 | 1.000000 | 1.000000 | 0.666667 | 0.666667 | 0.666667 | 0.015600 |
| proxy_A_support_holdout_delta_0.05 | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_A_support_holdout_delta_0.10 | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_B_tail_margin_delta_0.00sigma | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_B_tail_margin_delta_0.25sigma | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_B_tail_margin_delta_0.50sigma | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_E_hybrid_sup0.05_sep0.00sigma_review0.005 | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_E_hybrid_sup0.05_sep0.00sigma_review0.010 | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
| proxy_E_hybrid_sup0.05_sep0.00sigma_review0.020 | 1.000000 | 0.000000 | 0.000000 | 0.666667 | 0.333333 | 1.000000 | 0.003600 |
