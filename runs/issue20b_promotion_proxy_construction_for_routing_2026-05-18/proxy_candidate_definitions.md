# Proxy Candidate Definitions

## Proxy A: support-holdout detection

Split each local attack train pool into selected kcenter32 supports and a support-holdout remainder. Rebuild fixed V1/V2 with the selected supports, then compare support-holdout high-rate under the guarded threshold. This uses only local attack train pool samples, not final attack eval.

## Proxy B: attack-vs-OOD tail margin

Compute `Sep(M) = median(score on support-holdout) - q99(score on OOD validation)` for V1 and V2. Promote V2 only if its separation improves by a pre-registered small threshold and OOD validation remains within budget.

## Proxy C: disagreement/review risk

Measure V1/V2 disagreement on OOD validation, including V2-only and V1-only rates. This is not sufficient alone to identify attack-side shift, but it estimates conflict and review burden.

## Proxy D: representation-shift proxy

Compare support-holdout vs OOD validation standardized mean shift in selected_source_rich_top32 and original100 spaces. This is a representation-side diagnostic, not a standalone proof.

## Proxy E: hybrid promotion proxy

Promote V2 only when OOD validation is within budget, either support-holdout detection or tail-margin evidence favors V2, and estimated review burden is bounded. Threshold candidates are diagnostic-stage and must be locked before issue20c.
