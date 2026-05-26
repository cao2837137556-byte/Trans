# Mechanism Verdict And Claim Boundary

## Primary verdict

`lowguard_lr_success_mechanistically_supported`

## Secondary verdicts

- `representation_linearization_explains_lr_advantage`
- `lowguard_effect_head_specific_lr_only_so_far`
- `non_lr_results_inconclusive_due_to_proxy_implementation`

## Rationale

LR has a clean falsification pattern: P0 detects attacks but fails OOD, P1 controls OOD by collapsing detection, and P2/P3 preserve detection while controlling OOD. That pattern supports a real OOD-guarded training mechanism rather than a threshold-only artifact.

At the same time, the non-LR results do not establish head-agnostic transfer. DevNet-like is a near miss, but its OOD max remains over 1%. DeepSAD-like and DevNet-like are proxies, not full method implementations, so they cannot be used to make broad negative claims.

## Claim boundary

Allowed:
- Current evidence supports LOW-GUARD-LR as the strongest feasible instance.
- Broader head-agnostic transfer is not established.
- LR success appears linked to source-rich top64, OOD-guarded training, and validation-only thresholding.

Not allowed:
- LOW-GUARD works for all heads.
- Nonlinear adapters are useless.
- DevNet or Deep SAD are defeated.
- LR is universally optimal.
- Deployment robustness, temporal generalization, or cross-dataset generalization is proven.
