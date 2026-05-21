# Fusion Candidate Definitions

- F0_V1_baseline: original100+kcenter32+fixed guard LR.
- F1_V2_top64_baseline: selected_source_rich_top64+kcenter32+fixed guard LR.
- F2_linear_alpha_selected: validation-selected alpha from {0.50, 0.60, 0.70, 0.80, 0.90}; score = alpha*z(V2)+(1-alpha)*z(V1).
- F3_residual_lr_selected: validation-selected C from {0.01, 0.1, 1.0}; LR over [V1, V2, V2-V1, max(V1,V2), min(V1,V2)] standardized score features.
- F4_conservative_max_selected: validation-selected beta from {0.50, 0.75, 1.00}; score = max(z(V2), beta*z(V1)).

z-score normalization is fit using ID calibration plus OOD validation scores only.
