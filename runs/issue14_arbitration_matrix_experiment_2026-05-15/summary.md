# Issue14 Arbitration Matrix Experiment Summary

## 1. Outcome

This run completed the arbitration preflight and design pack, but did **not** compute base-only / GDA-only / OR / AND / mode-gated strategy metrics.

Reason: dA and Transformer base detector per-sample scores are available, but issue11 does not persist per-sample GDA-minimal scores or fitted model artifacts for `original100_fixed_guard_lr`.

Final status: `design_only_missing_gda_score`.

## 2. Score Availability

| score family | status |
|---|---|
| dA ID/OOD/attack scores | available and current-protocol aligned at asset-shape level |
| Transformer ID/OOD/attack scores | available and current-protocol aligned at asset-shape level |
| GDA-minimal original100 fixed-guard row-level scores | missing |

## 3. Strategy Metrics

Strategy metrics were intentionally left blank in `strategy_metrics_summary.csv` and `strategy_metrics_by_seed.csv`. Filling them from aggregate issue11 metrics would violate the same-row arbitration constraint.

## 4. Current Blocker

Issue11 computes decision scores in memory but writes only aggregate metrics, threshold provenance, and support provenance. Arbitration requires row-level `gda_high(x)` on exactly the same final OOD and attack eval row ids as `base_high(x)`.

## 5. Recommendation

Run a narrow score recovery task: `issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15`.

This recovery should reuse issue11 fixed configuration and only persist per-sample GDA scores. It should not search OOD weight, thresholds, seeds, support pools, scalers, or model hyperparameters.

## 6. Claim Boundary

This pack supports the claim that arbitration is well-specified and ready for score recovery. It does not support any empirical claim that mode-gated arbitration improves detection, OOD alarm, or review burden.

## 7. Repository Safety

- Manuscript modified: no.
- Existing experimental numbers modified: no.
- New training executed: no.
- Commit/push may include this design-only evidence pack after self-check.
