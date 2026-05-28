# Issue27m Next Action

Recommended next action: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`.

Run order:
1. Audit full Mirai / official 100k / my-gold feature-label alignment and decide whether they map to original100, restored115, or an incompatible frontend.
2. Construct a full-Mirai clean split with train-side support, validation-only thresholding, and report-only eval.
3. Build the compatible split-aware feature matrices.
4. Only if those gates pass, run frozen-compatible LOW-GUARD++ report-only evaluation and safer variants.
