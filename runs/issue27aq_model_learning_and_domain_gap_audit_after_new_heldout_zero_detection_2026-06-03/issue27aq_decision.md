# Issue27aq Decision

- primary_verdict: `zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal`
- Scope: model learning and domain-gap audit after issue27ap zero detection.
- No protocol repair, no new support construction, no formal benchmark.
- New heldout and final OOD remained score-only/report-only.

## Key Evidence

- Fit imbalance: ID rows=3000, support_train rows=128, ratio=23.438:1.
- Max support_train detection at threshold: 0.000000.
- Max support_val detection at threshold: 0.000000.
- Max new heldout detection at threshold: 0.000000.
- Raw support score signal is present, but the OOD-tail threshold is above the support_train/support_val maxima in this fixed replay.
- OOD-vs-new heldout max feature AUC(abs): 0.996699.
- New heldout nearest support_train distance p95: 8179.160645.

## Interpretation

- If support_val is already undetected under the selected threshold, the zero heldout result cannot be attributed only to the newly held-out files.
- If raw feature separability remains high but score/threshold detection is zero, the immediate blocker is learning/calibration rather than the 115D frontend alone.
