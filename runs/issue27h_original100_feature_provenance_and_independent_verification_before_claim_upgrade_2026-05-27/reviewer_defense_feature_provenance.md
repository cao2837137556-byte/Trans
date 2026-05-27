# Reviewer Defense: Feature Provenance

## Q1: Are the three separator features labels or split IDs?

No evidence of explicit label/split/bin fields was found. They map to KitNET HH radius/magnitude traffic statistics.

## Q2: Could they still encode time or capture source?

Indirectly, yes. KitNET statistics are time-updated flow statistics, so they can reflect traffic phase and capture conditions. That is a scientific signal if controlled, but it must be bounded and audited.

## Q3: Does removing the top separators destroy LOW-GUARD++?

See `feature_ablation_summary.csv`. The claim gate uses remove-top3 and LR comparison as the main test.

## Q4: Does top3-only being strong invalidate the result?

Not by itself. If top3-only is strong and remove-top3 remains strong, the model has redundant evidence. If remove-top3 collapses, LOW-GUARD++ depends on high-risk separators and should be demoted.

## Q5: Is there clean independent validation?

No. This issue provides non-locked consistency only. Clean independent validation or a second environment is still needed for a stronger main-text upgrade.
