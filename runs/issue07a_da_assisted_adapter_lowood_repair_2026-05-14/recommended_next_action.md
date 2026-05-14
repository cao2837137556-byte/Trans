# Recommended Next Action

If the dA-score-only adapter repairs the dA-only collapse, it can support the lifecycle idea that dA scores can be recalibrated by few-shot target alignment.

If `original100_plus_da_score` improves over `original100_only`, keep it as a candidate adapter input. If it does not improve, retain original100-only LR as the minimal target-alignment baseline and treat dA score as useful mainly for cold-start diagnostics.

Do not start Transformer adapter experiments until full-ID Transformer score recovery is complete.
