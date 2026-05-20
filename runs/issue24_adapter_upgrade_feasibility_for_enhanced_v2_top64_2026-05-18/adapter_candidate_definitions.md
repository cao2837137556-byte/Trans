# Adapter Candidate Definitions

- A0_lr_baseline: current fixed OOD guard logistic regression on selected_source_rich_top64.
- A1_low_fpr_weighted_lr: logistic regression with OOD-validation high-tail hard negatives added as weighted negatives.
- A2_linear_svm_margin: linear SVM margin scorer using fixed source_rich_top64 and weighted benign/attack samples.
- A3_hist_gradient_boosting: not run in this pass after the full grid exceeded the execution budget; kept as future design-only candidate.
- A4_devnet_like_lightweight_adapter: design-only in this pass; not run to avoid neural sweep creep.
- A5_deepsad_like_center_margin_adapter: design-only in this pass; not run due to objective/protocol risk.
