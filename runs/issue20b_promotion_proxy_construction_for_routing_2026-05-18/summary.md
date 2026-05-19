# Issue20b Promotion Proxy Construction Summary

## Outcome

- Preflight passed: yes.
- issue20 naive proxy failure retained: yes.
- Final eval used for proxy construction: no.
- Final metrics are report-only: yes.
- V1 definition changed: no.
- V2 definition changed: no.
- V2/topK/margin repaired again: no.
- Recommended next step: `proxy_asset_recovery_or_stronger_validation_proxy_design_before_issue20c`.
- Recommendation status: `no clean proxy: current candidates either under-promote holdout_bin_2 or false-promote primary_lowood`.

## Why Issue20 Failed

Issue20 selected V1 for all three settings. That was safe for primary_lowood but wrong for holdout_bin_2 and conservative for chrono_late. The direct cause is a weak promotion proxy: holdout_bin_2 lacked attack-side proxy evidence, while chrono_late's existing attack validation proxy did not reflect the final harder-shift advantage of V2. This is not evidence that V2 is invalid; it is evidence that the promotion trigger is under-specified.

## Proxy Candidate Status

No clean proxy currently satisfies the required routing pattern. The diagnostic split is the key result:

- Support-holdout, tail-margin, and hybrid proxies are safe for primary_lowood but under-promote holdout_bin_2; they still select V1 where V2 is needed.
- Disagreement and representation-shift proxies can select V2 for holdout_bin_2, but they also false-promote V2 in primary_lowood and inherit primary OOD-over-budget risk.
- Therefore issue20b does not yet justify issue20c as focused routing validation with a locked proxy.

Displayed conservative hybrid proxy for audit, not as a sufficient trigger:

`proxy_E_hybrid_sup0.05_sep0.25sigma_review0.010`

Displayed proxy inputs by setting:

| setting | selected_champion | support_delta | delta_sep | estimated_review_burden |
|---|---|---|---|---|
| chrono_late_train_early_eval | V1 | -0.016167 | -8.461482 | 0.000000 |
| holdout_bin_2 | V1 | -0.038973 | -6.937223 | 0.000000 |
| primary_lowood | V1 | 0.036919 | -3.509418 | 0.000500 |


Report-only final metrics under that displayed proxy:

| setting | selected_champion | final_detection | final_ood_alarm | review_burden | feasible_rate |
|---|---|---|---|---|---|
| chrono_late_train_early_eval | V1 | 0.679802 | 0.001800 | 0.009600 | 1.000000 |
| holdout_bin_2 | V1 | 0.326409 | 0.001100 | 0.006800 | 1.000000 |
| primary_lowood | V1 | 0.929455 | 0.003600 | 0.013600 | 1.000000 |


## Proxy Ranking Snapshot

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


## Interpretation

Issue20b can compute stronger validation/support-side diagnostics, but the current proxies are not adequate promotion triggers. The correct next step is not V2 repair or V3; it is to recover/design a stronger validation-side promotion proxy, likely requiring more representative local attack validation or support-holdout evidence plus a stricter OOD validation guard. Final metrics remain report-only.
