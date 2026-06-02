# Diagnostic Key Findings

- Scope: medium Gotham Kitsune115 diagnostic only; not a formal benchmark and not a model ranking.
- Support selector: `kcenter32`; support pool rows = 2250; selected rows = 32.
- Static selector comparison: kcenter32 and issue27ai first32 have zero overlap on both state strategies.
- Forbidden role access: pass; final OOD eval and attack eval were not used for fit, threshold, support, or selection.

## Reset At Split Boundary

- LR full guarded: final_ood_alarm=0.048333, attack_eval_detection=0.000889, feasible_under_1pct=False.
- HistGB full guarded: final_ood_alarm=0.009333, attack_eval_detection=0.194667, feasible_under_1pct=True.
- DeepSADStyle_Lite full guarded: final_ood_alarm=0.042000, attack_eval_detection=0.762667, feasible_under_1pct=False.
- DevNetStyle_MLP full guarded: final_ood_alarm=0.192333, attack_eval_detection=0.000889, feasible_under_1pct=False.

## Train State Then Eval Online

- LR full guarded: final_ood_alarm=0.208667, attack_eval_detection=0.000889, feasible_under_1pct=False.
- HistGB full guarded: final_ood_alarm=0.023000, attack_eval_detection=0.257333, feasible_under_1pct=False.
- DeepSADStyle_Lite full guarded: final_ood_alarm=0.008667, attack_eval_detection=0.000000, feasible_under_1pct=True.
- DevNetStyle_MLP full guarded: final_ood_alarm=0.127667, attack_eval_detection=0.000889, feasible_under_1pct=False.

## Interpretation Boundary

- The kcenter32 migration materially changes the support set, but medium findings remain diagnostic.
- Several guarded variants still show low attack detection or OOD overbudget under the 1% constraint.
- HistGB under reset_at_split_boundary is the cleanest feasibility signal in this medium diagnostic, but this is not a mainline decision.
- Full/larger asset materialization or a defensible exclusion policy is still required before formal ranking.
