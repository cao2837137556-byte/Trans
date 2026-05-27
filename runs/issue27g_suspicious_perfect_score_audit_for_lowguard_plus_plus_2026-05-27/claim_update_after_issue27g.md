# Claim Update After Issue27g

## Allowed

- LOW-GUARD++ formal result passed suspicious-perfect-score anomaly audit.
- The result remains bounded to `original100 + HistGB-Conservative` under the locked low-alert protocol.
- LOW-GUARD-LR remains the minimal stable instance.
- Original100 contains high-cardinality near-perfect separator features; these did not meet the stricter label-like/split-like flag, but feature provenance should be documented before strong main-text upgrading.
- This does not prove temporal, deployment, or cross-dataset generalization.

## Still Not Allowed

- HistGB universally dominates LR.
- LOW-GUARD works for all models.
- Deployment robustness is proven.
- Temporal generalization is proven.
- Cross-dataset generalization is proven.
- Final eval was used for model selection.
