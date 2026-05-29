# Anonymous Clean115 Feature Risk Report

Feature schema verdict: `anonymous_clean115_feature_semantics_too_weak_for_main_claim`.

The anonymous clean115 matrix is technically usable for a protocol-reset diagnostic benchmark: it has 115 features, the dirty116 index-like column was removed, and labels align with rows. But feature semantics are not strong enough for a main claim:

- restored115/common100/original100 mapping remains low-confidence or blocked.
- source/capture/session metadata is unavailable.
- issue27q_P0P1 showed strong scale dependence: rank-normalized DeepSADStyle_Lite collapses while raw features remain strong.
- top anonymous features have medium-to-high label and row-order correlations, even without near-perfect single-column separators.

The safe interpretation is diagnostic within-dataset anonymous clean115 only. Main claims require raw pcap/extractor-level reconstruction, feature names/order recovery, or a second dataset with validated feature provenance.
