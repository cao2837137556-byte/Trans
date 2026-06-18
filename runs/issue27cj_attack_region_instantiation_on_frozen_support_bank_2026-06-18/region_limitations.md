# Region Limitations

## Registry Status

`initial_region_registry_v1.csv` is a diagnostic registry, not an operational attack-region registry.

No candidate is approved as a strong attack region.

## Scientific Limitations

1. Candidate regions were intentionally limited to one exact-label medoid. Six labels show split signals, but splitting a confounded space would create fragile islands rather than solve the underlying geometry.
2. Current support rows are concentrated in `tail_gt_10000`; phase generality is not established.
3. File Download, Ingress Tool Transfer, Merlin C&C Communication, and Mirai C&C Communication have only one provenance source group.
4. The primary ID-IQR scaling strongly amplifies heavy-tailed covariance/jitter dimensions.
5. The shrinkage-Mahalanobis challenger remains strongly OOD-confounded, so the failure is not resolved by covariance correction alone.
6. Dev-query results are coverage/interpretability diagnostics, not attack detection metrics.
7. Labels absent from the initial support bank naturally cannot achieve exact-label matches; supported-label analyses are reported separately.
8. OOD stress and dev query were read-only and did not change the frozen registry.

## Prohibited Interpretation

Do not claim:

- that one exact label equals one true attack mode;
- that the conflict-sensitive candidate can produce a hard attack decision;
- that query rows inside a shell are detected attacks;
- that out-of-region rows are benign;
- that more radius tuning will repair the geometry;
- that the support bank should be reselected based on these query outcomes.
