# Frontend-F2 D0 numeric-semantics erratum (FROZEN)

Date: 2026-09-04

Status: FROZEN before D0 execution and before any additional incumbent score
is opened.

Parent contract SHA-256:
`2a2b323a383de391c272bdc01dff1716819f25615dd6c0545a91723c38011a54`.

## 1. Narrow defect

Parent §4 specified the all-float64 matrix helper previously used by the
teacher-benign and five-margin audits. That helper is decision-equivalent for
the already inspected strong-margin rows, but it is not the exact continuous
function used by the formal incumbent CKDA probe.

There are three relevant numerical paths:

1. formal CKDA incumbent: float64 normalizer transform, then conversion of the
   full feature row to float32 before the frozen PyTorch P2;
2. Frontend-F1 differentiable wrapper: representation, mean, scale, and P2 are
   all float32;
3. prior count/five-row audit helper: normalizer and P2 matrix operations are
   float64.

Continuous logits will become teacher targets, so path 3 may not define them.
This is an identity correction, not a change to any row, split, quantile,
envelope formula, or scientific gate in the parent.

Pinned implementation identities:

| implementation | SHA-256 |
|---|---|
| `repo/ood/issue27ckda_d1_representation_probe_v1.py` | `f8f477ca78d8ed1fa490880d24a01f65111e3f910eaa8ab72af154d8a143de4e` |
| `repo/ood/issue27frontend_f1_d1_train_v1.py` | `6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634` |

## 2. Canonical incumbent raw logit

Parent §4 is superseded only for numerical evaluation. For each authorized old
float32 representation row:

```text
normalized64 = (representation.astype(float64) - mean64) / scale64
features32 = column_stack(normalized64, missing=0).astype(float32)
hidden32 = relu(linear(features32, old_P2_layer1_float32))
canonical_old_logit32 = linear(hidden32, old_P2_layer2_float32)
canonical_old_score32 = sigmoid(canonical_old_logit32)
```

The raw pre-sigmoid `canonical_old_logit32`, promoted to float64 only for CSV
serialization and distribution arithmetic, is the sole value consumed by the
parent §6 quantiles and any future teacher target.

## 3. F1-wrapper interface audit

On the same 8,353 authorized training-A representations, also compute without
gradient:

```text
f1_normalized32 = (representation_float32 - mean_float32) / scale_float32
f1_old_logit32 = frozen_P2_float32(f1_normalized32, missing=0)
```

Persist `f2_d0_p2_interface_comparison.json` containing:

- hard disagreements at the frozen threshold;
- maximum, median, Q95, and Q99 absolute logit difference;
- maximum absolute score difference;
- counts by true label for both paths.

Required gate:

```text
canonical_vs_f1_wrapper_hard_disagreements = 0
```

Any disagreement terminates D0 as
`F2_D0_P2_INTERFACE_NUMERICAL_DRIFT`. Continuous differences are reported
verbatim and may not be hidden, but no post-result numeric tolerance is added.

## 4. Output and claim correction

The parent CSV fields `old_logit` and `old_score` mean canonical formal-CKDA
values defined in §2 above. Parent teacher-class conservation must use those
canonical scores. The previously inspected five-row conclusion remains valid
because all five incumbent score margins exceed 0.933 under the all-float64
helper; this erratum does not reopen or recompute them.

All parent zero counters, row counts, envelope rules, and authorization
boundaries remain unchanged. This erratum adds one comparison output and no
new training permission.
