# OOD Benign Purity And Deployment Semantics

Purity verdict: `ood_benign_purity_supported`.

Deployment semantics verdict: `ood_deployment_semantics_weak`.

The OOD train, OOD validation, and final OOD evaluation ranges are labeled benign and are mutually disjoint where required. That supports label purity at the sidecar level.

However, the formal split has no timestamp, capture/session id, source-file id, or raw packet provenance. The OOD split is row-order based inside a benign prefix, and final OOD eval is adjacent to the attack suffix. Therefore the current evidence supports only a row-order/distributional within-dataset OOD split, not a deploy-time temporal drift claim.
