# CKDE-S D0 Lane G pre-implementation erratum (FROZEN)

**Date:** 2026-08-26
**Status:** FROZEN ERRATUM; NON-EXECUTABLE pending independent review
**Parent contract:** `ckde_s_d0_attack_protected_device_shift_and_paired_corpus_preregistered_20260826.md`
**Parent SHA-256:** `e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6`

## 1. Why this erratum exists

The parent contract requires, before implementation, exact input identities and literal SVD and
orthogonality tolerances.  Its FROZEN text retained those requirements but did not materialize the
identities or the two literals.  Codex detected the omission after Lane G implementation was
authorized but before implementation, synthetic testing, or any real embedding-array open.

Implementing with locally chosen values would create post-freeze degrees of freedom.  Therefore
this erratum closes only those omissions.  It changes no scientific gate, rank rule, denominator,
role, state transition, claim boundary, or authorization boundary in the parent contract.

## 2. Exact Lane G input identities

Lane G may use only these exact existing artifacts; globbing and newest-timestamp discovery remain
forbidden:

| Identity | Repository-relative path | SHA-256 |
|---|---|---|
| fit/select embeddings | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz` | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| embedding metadata | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz.metadata.csv.gz` | `120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd` |
| fit/select plan | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv` | `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| frozen probe/P2 state | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz` | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |

The P2 identity is the existing frozen 769-to-128-to-1 ReLU MLP plus its 768-coordinate
normalizer and missingness indicator.  Implementation must require the exact state keys and
shapes already validated by CKDE-R; any mismatch is an engineering failure with no scientific
verdict.

## 3. Literal numerical conventions

All Lane G linear algebra is `float64`.  The following constants and comparisons are immutable:

```text
SVD_RELATIVE_TOLERANCE = 1e-10
ORTHOGONALITY_TOLERANCE = 1e-10
GRADIENT_NORM_FLOOR = 1e-12
```

For every SVD-based span or rank calculation with ordered singular values `s_0 >= s_1 >= ...`,
the retained rank is the count satisfying the strict comparison:

```text
s_i > SVD_RELATIVE_TOLERANCE * s_0
```

A non-finite spectrum or `s_0 <= 0` is an engineering failure.  No absolute fallback tolerance,
matrix-size-dependent alternate rule, eigengap choice, or in-run rank downgrade is allowed.

Each P2 attack-logit gradient is normalized only when its Euclidean norm is finite and strictly
greater than `GRADIENT_NORM_FLOOR`; otherwise execution fails without a scientific verdict.

The removable-space orthogonality condition is the parent contract's spectral-norm test with the
literal bound:

```text
||P_Uremove P_Vraw||_2 <= ORTHOGONALITY_TOLERANCE
```

Principal-angle cosine values may be clipped to `[-1, 1]` solely before `arccos` to absorb
floating-point roundoff.  This clipping cannot change any rank or gate.

## 4. Required regression gates

Before real Lane G execution, synthetic contract tests must prove:

1. all four artifact paths and hashes are exact and fail closed on drift;
2. the count-only rank gate runs before opening either NPZ array;
3. strict SVD-boundary equality is rejected;
4. zero and non-finite spectra fail without a verdict;
5. zero, floor-equal, and non-finite gradients fail without a verdict;
6. the spectral orthogonality comparison uses `<= 1e-10` exactly;
7. no alternative tolerance or rank-retry path exists;
8. Python 3.9 grammar and runtime-API gates pass.

## 5. Authorization boundary

This erratum does not consume Lane G execution authorization and does not authorize implementation
against an unreviewed contract.  After independent SHA/diff review, the user's existing Lane G
implementation authorization may be consumed for code and synthetic tests.  Opening real
embedding arrays and producing a scientific Lane G verdict still requires the separate execution
authorization specified by the parent FROZEN contract.
