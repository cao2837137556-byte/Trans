# Region-Aware Score Gate Logic

This diagnostic does not replace anomaly scores with distance-only rules.

Runtime logic being tested:

1. Extract Gotham Kitsune115 features.
2. Compute an attack score with a frozen HistGB-style head.
3. Compute coverage against each attack region registry entry.
4. Hard alarm requires score above the pre-registered threshold.
5. Low-score samples that are close to an attack region are counted as weak-review candidates, not as hard detections.
6. Samples far from all attack regions remain unknown/uncovered and should go to a buffer or active-labeling route.

Distance/coverage is therefore a routing and confidence mechanism, not the detector itself.
