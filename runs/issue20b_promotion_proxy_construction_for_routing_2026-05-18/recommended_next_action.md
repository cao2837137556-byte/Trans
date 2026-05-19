# Recommended Next Action

Unique first choice: `proxy_asset_recovery_or_stronger_validation_proxy_design_before_issue20c`.

Do not run issue20c yet with the current proxy candidates. First build a stronger validation-side promotion signal. The current middle hybrid `proxy_E_hybrid_sup0.05_sep0.25sigma_review0.010` is safe but under-promotes holdout_bin_2:

- V2 OOD validation alarm must be <= 1%.
- V2 must show support-holdout detection gain >= 0.05 or tail-margin gain >= 0.25 sigma.
- Estimated review burden must be <= 1%.

Suggested recovery path:

1. Create or recover a true local attack validation/support-holdout proxy for holdout_bin_2 that is not final attack eval.
2. Strengthen the OOD validation guard so primary_lowood does not false-promote V2 when deployment OOD is risky.
3. Then lock one candidate trigger and run issue20c.

Do not fix V2, create V3, change topK, or silently convert to V2-only.
