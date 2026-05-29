# ID/OOD Drift Validity Report

Verdict: `ood_shift_too_artificial_or_row_order_bound`.

Key diagnostic values:

- best ID-vs-OOD diagnostic AUC: `0.998820`
- rank-normalized ID-vs-OOD diagnostic AUC: `0.881677`
- drop-top10-shift-features ID-vs-OOD diagnostic AUC: `0.510872`
- max per-feature KS: `0.690666`
- median per-feature KS: `0.010696`
- ID/OOD label vs row-order correlation: `0.624333`

Interpretation:

ID and OOD benign are distinguishable in anonymous clean115, so the shift is not too weak. The problem is that the split is explicitly row-order derived and lacks timestamp/capture/session metadata. Therefore this cannot be described as temporal, deployment, or capture-disjoint benign drift. It is at most a within-dataset distributional shift until raw provenance is recovered.
