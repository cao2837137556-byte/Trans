# CKBV r13 finalization boundary fix

Date: 2026-07-27  
Scope: local correction before any r12 HPC submission  
Scientific protocol changed: no

## Deterministic r12 failure prevented

The immutable CKBQ prediction artifact contains the original core/auxiliary
records but no `ton:` records. The r12 sensitivity audit passed the mixed
`select_benign` pool, including 4,000 ToN `aux_normal_select` records, to
`base_decisions()`. That helper correctly requires complete immutable CKBQ
coverage, so r12 would have failed during result finalization after the main
computation.

Read-only inspection of the frozen artifact found 277,326 prediction rows and
zero UIDs beginning with `ton:`. The formal select pool independently contains
4,000 ToN `aux_normal_select` rows in every protocol.

## r13 boundary

- Non-ToN select rows must still exist in the frozen CKBQ artifact and their
  fresh C1 decisions must match it exactly.
- ToN select rows are audit-only and use the already-selected C1 threshold on
  the preregistered conservative `c1_score=1.0` (all hard) policy. They do not
  request nonexistent frozen CKBQ rows or create a favorable C1 comparison.
- Missing frozen coverage for any non-ToN row remains a hard failure.
- The audit reports the frozen-prediction and ToN-threshold-only row counts
  separately; the validator requires exactly 4,000 ToN select rows per
  protocol.
- No model, score, threshold, fit/select membership, frozen manifest, raw51
  mask, attack denominator, or review policy is changed.

## Permanent regression gates

The formal contract unit now executes the real mixed core/ToN audit helper and
also verifies that a missing non-ToN frozen row is rejected. The result
validator additionally requires:

1. the exact five formal protocols;
2. every protocol-by-pool total and per-source reconciliation;
3. full = observable + masked for every composition row;
4. one complete C1/gate audit row per protocol;
5. valid count/rate and gate-threshold relationships;
6. the explicit frozen-versus-ToN C1 provenance boundary;
7. exact raw51 provenance in both environment and run specification;
8. the existing 8,682/7,329/1,353 mask composition and unchanged attack
   denominators.

This is a finalization/evidence correction only. It must not be interpreted as
a scientific result or a change to the preregistered seed-27 experiment.
