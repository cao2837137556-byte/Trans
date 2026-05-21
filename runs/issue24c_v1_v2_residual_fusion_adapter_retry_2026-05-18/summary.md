# Issue24c V1/V2 Residual Fusion Adapter Retry Summary

## Outcome

- Preflight passed: yes.
- V1/V2 score assets complete: yes, reconstructed under fixed protocols for all seeds/settings.
- Representation/support changed: no; V2 remains selected_source_rich_top64 and kcenter32.
- Fusion selection uses final eval: no.
- Status: `weak_optional_fusion_signal_no_adapter_replacement`.

## Locked Result

- Best method: `F4_conservative_max_selected`.
- Best locked detection mean: `0.950993`.
- Best locked detection min: `0.887324`.
- Best locked OOD max: `0.006500`.
- V2_top64 LR locked mean/min/OOD max: `0.949705` / `0.882629` / `0.004500`.
- Best mean delta vs V2_top64: `0.001288`.
- Best min delta vs V2_top64: `0.004695`.
- Best OOD max delta vs V2_top64: `0.002000`.
- bin6/bin7 mean detection delta vs V2_top64 for best fusion: `0.0`.
- bin8 detection delta vs V2_top64 for best fusion: `0.0046948356807511304`.
- consistency delta vs V2_top64 for primary_lowood / holdout_bin_2 / chrono_late: `0.001454545454545375` / `-0.03115727002967361` / `-0.0002918855808521359`.

## Interpretation

- Fusion was tested as a targeted retry motivated by issue24b complementarity, not as broad stacking.
- All alpha/C/beta candidates were selected using support-holdout plus ID/OOD validation evidence only.
- The observed gain is treated as adapter replacement only if it clears the bin6/bin7 repair and locked mean/min criteria. Otherwise V2_top64 LR remains the main adapter and fusion is at most an optional analysis variant.

## Locked Summary

| method | method_group | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | locked_feasible_rate_mean | locked_pauc_fpr_1pct_mean | locked_tpr_at_fpr_1pct_mean | delta_locked_detection_mean_vs_v2top64 | delta_locked_detection_min_vs_v2top64 | delta_locked_ood_alarm_max_vs_v2top64 | delta_locked_detection_mean_vs_v1 | delta_locked_ood_alarm_max_vs_v1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F4_conservative_max_selected | targeted_fusion_retry | 0.950993 | 0.887324 | 0.006500 | 1.000000 | 0.967895 | 0.955229 | 0.001288 | 0.004695 | 0.002000 | 0.006242 | 0.001200 |
| F2_linear_alpha_selected | targeted_fusion_retry | 0.950968 | 0.887793 | 0.003500 | 1.000000 | 0.974980 | 0.953231 | 0.001263 | 0.005164 | -0.001000 | 0.006217 | -0.001800 |
| F3_residual_lr_selected | targeted_fusion_retry | 0.950879 | 0.887324 | 0.006600 | 1.000000 | 0.969140 | 0.965715 | 0.001174 | 0.004695 | 0.002100 | 0.006128 | 0.001300 |
| F1_V2_top64_baseline | baseline | 0.949705 | 0.882629 | 0.004500 | 1.000000 | 0.972888 | 0.951466 | 0.000000 | 0.000000 | 0.000000 | 0.004954 | -0.000800 |
| F0_V1_baseline | baseline | 0.944751 | 0.835681 | 0.005300 | 1.000000 | 0.941631 | 0.960525 | -0.004954 | -0.046948 | 0.000800 | 0.000000 | 0.000000 |
