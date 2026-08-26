# CKDE-S D0 Lane G implementation report

**Date:** 2026-08-26

**Status:** IMPLEMENTED AND SYNTHETICALLY VALIDATED; REAL EMBEDDING EXECUTION NOT AUTHORIZED

**Branch:** `codex/exp-mainline`

## 1. Authorization consumed

This change consumes only the user's Lane G **implementation** authorization after Kimi's
independent erratum review at commit `1dc444f`.  It does not consume the separately required
scientific execution authorization.  The implementation and its tests have not invoked the real
Lane G entry point and have not deserialized either frozen NPZ input.

Frozen authorities:

- parent contract SHA-256: `e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6`;
- pre-implementation erratum SHA-256:
  `156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d`.

The four real-input byte identities were independently rehashed during implementation review and
match the erratum exactly.  This byte hashing is not an array open and produced no statistics.

## 2. Implemented files

1. `repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_v1.py`
2. `repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py`

The audit implements the frozen G0--G4 chain:

1. exact contract, erratum, plan, metadata, embedding, and probe-state identities;
2. exact metadata join and metadata-only device/session census;
3. count-only rank `min(4, floor((D-1)/3))` before NPZ deserialization;
4. equal-session device centers and equal-device global center;
5. rank-fixed LODO projection distance/principal-angle stability;
6. causal early/late between-versus-within-device stability;
7. frozen-P2 logit gradients in the original 768-dimensional representation coordinates;
8. equal-session family gradient span, contrast contamination, and attack-orthogonal removable
   subspace;
9. literal G0--G4 terminal states with no in-run lower-rank retry;
10. staged atomic outputs and engineering-failure cleanup that leaves no scientific verdict.

## 3. Operational definitions made explicit

The parent contract's unit is one complete causal session embedding.  The implementation maps a
session to the last frozen target by `(source_group, session_id, event_position, uid)` after role
filtering.  Thus each session contributes exactly one terminal causal prefix and cannot gain weight
from having more target records.  A selected terminal session whose representation is marked
missing is an engineering failure, not a scientific zero vector.

The retained-energy gate is computed per device as

```text
||P_Uremove (c_d-c_g)||^2 / ||P_U (c_d-c_g)||^2
```

and consumes the equal-device median, matching the contract's phrase “median between-device
energy.”  No record-weighted alternative exists.

These two operationalizations are called out for Kimi to inspect explicitly before real execution;
they are not selected from observed Lane G outcomes.

## 4. Fail-closed boundaries

- `pin_inputs()` requires all six contract/data identities before any computation.
- `load_metadata_only()` reads only the plan and compressed session metadata.
- `count_rank_gate()` must pass before `load_arrays()` is reachable.
- G0 count failure emits `embedding_arrays_opened=0` and
  `probe_state_arrays_opened=0`.
- only fit-benign roles define device geometry and only fit-attack roles define protection geometry;
  support-val/report/FINAL/PCAP/training counters stay zero.
- non-finite or zero spectra, rank deficiency, missing terminal session embeddings, non-finite
  gradients, gradient norms `<=1e-12`, identity drift, or schema drift are engineering failures.
- engineering failure deletes the staged scientific directory and writes only
  `<output>_control/engineering_failure.json`.

## 5. Synthetic validation

Command executed with the actual Python 3.9 runtime:

```text
py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py
```

Result: `22/22 PASS`.

The suite covers all eight erratum regression gates plus terminal-session equal weighting, fixed
rank, LODO geometry, early/late stability, analytic P2 gradient behavior, projection sign
invariance, literal state identities, role separation, and engineering-failure cleanup.  In
particular it tests strict SVD equality rejection, exact inclusive orthogonality at `1e-10`, and
zero/floor-equal/non-finite gradient rejection.

Additional checks:

```text
py -3.9 -m py_compile <implementation> <contract-tests>
git diff --check -- <implementation> <contract-tests>
```

Both pass.  Static scanning finds no Python 3.10-only `match/case`, `removeprefix`,
`removesuffix`, `strict=`, or `Path.write_text(newline=...)` path.

## 6. Independent review requests

Please review these before authorizing real execution:

1. Confirm that “complete causal session embedding” is correctly operationalized as the last
   frozen target per source/session after legal-role filtering.
2. Confirm the retained between-device energy fraction formula in Section 3.
3. Confirm that all eligible exact fit-attack families with at least 15 independent sessions are
   the contract's “eligible major families” for the `residual >= 0.50` conjunct; the implementation
   reports the full family table verbatim.
4. Confirm the count gate genuinely precedes both NPZ deserializations and that G0 cannot reach an
   array loader.
5. Confirm the P2 gradient is the frozen **logit** gradient with missing representation coordinates
   zeroed, rather than the BCE gradient or final-layer-only proxy.

## 7. Authorization state

Implementation is complete and ready for Kimi's independent code/test review.  No real embedding
array, probe-state array, scientific Lane G output, network request, model training, report artifact,
or FINAL artifact has been opened or produced by this implementation turn.

Real Lane G execution remains blocked until the user separately authorizes it after review.
