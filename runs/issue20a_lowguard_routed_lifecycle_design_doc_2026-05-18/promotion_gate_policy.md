# Low-Alert Promotion Gate Policy

## A. Promotion Inputs

- OOD validation alarm.
- Confirmed attack support performance.
- Detection proxy on local attack validation or support holdout.
- Review burden.
- Score or feature drift indicators.
- Seed/window stability.
- Cost and latency, when available.
- Provenance checks for supports, threshold, scaler, and feature selection.

## B. Promotion Conditions

A challenger can be promoted to champion only if all conditions hold:

- Detection proxy is meaningfully better than the current champion in the relevant mode.
- OOD alarm is within the target budget, normally <= 1%.
- Review burden does not exceed the operational review budget.
- Support, threshold, scaler, and feature provenance are clean.
- The improvement appears across at least N validation windows or seed groups.
- No leakage or protocol rule is violated.

## C. Rejection Conditions

- OOD alarm exceeds budget.
- Improvement appears only in one narrow window.
- Detection gain is small while false alarm or review burden increases.
- Provenance is incomplete or contaminated.
- V1/V2 conflict samples increase sharply without a review budget.
- Cost or latency is unacceptable.

## D. Rollback Rule

After promotion, if OOD alarm or review burden exceeds runtime limits, the system rolls back to the previous champion. Historical V1/V2 scores remain available for audit. Old models are not deleted immediately; they become fallback or analysis references.

## E. Candidate Operating Point Rule

Issue19b found diagnostic V2 operating-point slack on holdout_bin_2 for 1.2% and 1.5% validation targets, but those are not official thresholds. Any 1.2% / 1.5% candidate must be pre-registered and pass locked validation before replacing the 1% operating point. The system cannot hand-select a threshold such as final OOD alarm 0.008 from final evaluation.
