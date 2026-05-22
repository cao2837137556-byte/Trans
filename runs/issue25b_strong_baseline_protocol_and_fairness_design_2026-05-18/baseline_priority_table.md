# Baseline Priority Table

## Required

- V1 original100 fixed guard LR。
- V2_top32 source_rich fixed guard LR。
- Enhanced LOW-GUARD+ top64 fixed guard LR。
- top64 no guard。
- top64 random32。
- Isolation Forest。
- OC-SVM。
- HistGB shallow。
- DevNet-like lightweight。
- DeepSAD-like lightweight。

## Optional

- LOF。
- full_source_rich variants。
- RoSAS-like design-only unless implementation is clean。
- issue24c fusion reference。
- issue24 weighted LR / SVM reference。

## Design-Only

- Large neural anomaly detector。
- Continual learning method。
- Routing/promotion method。
- Full RoSAS if implementation cost or protocol mismatch is high。

## Priority Logic

Required baselines defend the core reviewer attacks:

- "It is only LR."
- "It is only feature engineering."
- "Few-shot anomaly methods already solve this."
- "Unsupervised anomaly detection would be enough."
- "The OOD guard/support coreset may be unnecessary."

Optional baselines are useful for appendix or additional robustness but should not block issue25c unless they are cheap and protocol-clean.

Design-only methods should not be forced into issue25c because incomplete or unfair implementations would create weaker evidence than a transparent limitation.
