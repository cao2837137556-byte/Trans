# Issue27an Decision

- primary_verdict: `support_eval_distribution_mismatch_blocker_found`
- Scope: feature/state/onset/label alignment failure attribution only.
- No new model training, no split change, no frontend change, no support-pool reconstruction.
- Report-only oracle/separability analysis was used only for failure attribution.

## Evidence

- max_ood_vs_attack_eval_feature_auc_abs=0.992151
- median_ood_vs_attack_eval_feature_auc_abs=0.829002
- max_support_eval_related_feature_auc_abs=0.900509
- max_support_val_vs_attack_eval_feature_auc_abs=0.900509
- max_attack_eval_nearest_support_p95=8.414059
- max_attack_eval_nearest_support_max=884839.687500
- onset_rows_needing_review=False
- reset_online_attack_mean_abs_delta_max=0.000004
- support_val and/or selected support coverage differs materially from attack_eval; repair should target support/eval contract before adding heads

## Pair Upper Bounds

- id_vs_ood: max per-feature AUC(abs) = 0.806017
- ood_vs_attack_eval: max per-feature AUC(abs) = 0.992151
- attack_support_vs_attack_eval: max per-feature AUC(abs) = 0.659120
- support_val_vs_attack_eval: max per-feature AUC(abs) = 0.900509
