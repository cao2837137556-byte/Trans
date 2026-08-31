# Frontend-F0 Coverage Extension M1 Denominator Clarification

- Date: 2026-08-31
- Author: Codex
- Governing draft: `frontend_f0_coverage_extension_protocol_draft_20260830.md`
- Draft commit: `e7a7075`
- Independent review: `frontend_f0_coverage_extension_kimi_draft_review_20260830.md`
- Review commit: `d76915a`
- Status: **PRE-FREEZE BLOCKING CLARIFICATION; NO FROZEN PROTOCOL EMITTED**

## 1. Outcome first

M1 correctly requires one exact incumbent verdict identity before the CE
protocol can freeze. The incumbent is fixed as **candidate `E3`, probe `P2`**,
because CE is intended to preserve the current strongest CKDA D1 attack branch,
not substitute G0's different missing-row semantics.

However, the review's proposed denominator
`old-missing benign-select = 5,242` is inconsistent with the frozen CKDA D1
fit/select plan. The mechanically valid denominator is:

```text
old-missing benign rows with frozen phase == select = 4,812
H_old under frozen E3/P2 = 4,812
material reduction gate = max(300, ceil(0.10 * 4,812)) = 482
```

The difference is exactly 430 rows: `ood_val = 381` and `id_calib = 49`.
Both are frozen as `phase=fit`, not `phase=select`. Including them in CE-5
development utility would make fitted rows contribute to a selection verdict.
That would violate the inherited fit/select isolation and cannot be introduced
as a mechanical freeze edit.

Therefore no FROZEN CE protocol or sidecar is generated in this commit. A
narrow independent ruling must first confirm the corrected denominator, or
explicitly reopen the scientific protocol and justify a different role rule.

## 2. Pinned incumbent identity for M1

All paths below are relative to the repository root unless stated otherwise.

| Identity item | Frozen value |
|---|---|
| candidate | `E3` |
| probe | `P2` |
| score/verdict artifact | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_select_scores.csv.gz` |
| score/verdict SHA-256 | `bc34268eea2c4545a425cba8adf641a214f75dae5435858a86ee0bb3aabe3419` |
| threshold marker | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_threshold_freeze_marker.json` |
| threshold-marker SHA-256 | `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |
| P2 threshold | `0.065159872174263` |
| P2 frontier SHA-256 | `aa36fc5f096fcfbfc1175a14f760b9a48e2be2a2e01a561f4598ef2a8ed41958` |
| probe-state artifact | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz` |
| probe-state SHA-256 | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |
| fit/select plan SHA-256 | `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| missing identity artifact | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz` (`uid` and `missing` arrays only for this count) |
| missing identity SHA-256 | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |

The threshold marker itself records `candidate_id=E3`, `select_rows=7069`, the
P2 threshold literal, and the hashes of the score, frontier, plan, embedding,
and probe-state artifacts. No challenger score, report score, or FINAL asset is
opened for this clarification.

## 3. Mechanical reconstruction

The count uses an exact one-to-one UID join among:

1. the single `candidate_id=E3, probe_id=P2` slice of the frozen select-score
   artifact;
2. `uid` and `missing` from the frozen fit/select embedding container; and
3. the frozen fit/select plan fields `uid`, `phase`, `role`, and
   `label_metric_only`.

Join assertions and counts:

| Assertion | Result |
|---|---:|
| P2 score rows | 7,069 |
| unique P2 score UIDs | 7,069 |
| missing-identity join misses | 0 |
| fit/select-plan join misses | 0 |
| score-role vs plan-role mismatches | 0 |
| frozen select benign rows | 7,000 |
| old-missing select benign rows | 4,812 |
| incumbent-hard among those rows (`H_old`) | 4,812 |
| rows with score exactly P2 threshold | 4,812 |
| required CE hard-count reduction | 482 |

The 4,812 rows decompose exactly as:

| Frozen phase | Frozen role | old-missing benign rows | E3/P2 hard |
|---|---|---:|---:|
| `select` | `aux_normal_select` | 3,518 | 3,518 |
| `select` | `aux_select` | 1,294 | 1,294 |
| **Total** | | **4,812** | **4,812** |

The frozen plan separately places the two disputed roles in `phase=fit`:

| Frozen phase | Frozen role | old-missing benign rows |
|---|---|---:|
| `fit` | `ood_val` | 381 |
| `fit` | `id_calib` | 49 |
| **Total excluded from CE-5 select utility** | | **430** |

Thus `4,812 + 430 = 5,242`. The arithmetic in the review is reproducible, but
its semantic label "benign-select" is not compatible with the frozen `phase`
field or CKDA D1's role isolation.

## 4. Conditions 4 and 5 under the pinned E3/P2 baseline

The frozen select artifact contains 69 `support_val` attacks. Exactly 23 are
old-missing, and all 23 have E3/P2 `hard=1` at the frozen threshold. In fact,
all 69 select attacks are incumbent-hard.

Therefore, for this pinned baseline:

- CE-5 condition 4 explicitly tests the challenger's behavior on the exact 23
  old-missing `support_val` rows and preserves their denominator as a visible
  kill-only guard;
- CE-5 condition 5 requires every incumbent-hard select attack to remain hard
  under routed CE and therefore **subsumes condition 4 on the current frozen
  rows**; and
- condition 4 remains intentionally redundant because it makes the sparse
  missing-attack denominator and family table impossible to hide.

This overlap is an observed consequence of the pinned E3/P2 artifact, not a
generic claim about all learned probes or all future datasets.

## 5. Q6 prerequisite mapping accepted

The FROZEN protocol should state mechanically:

- CE-2 requires `F0_ENCODER_ONLY_PASS` plus the frozen count/identity/copy
  artifacts; it does not require `F1_FRONTEND_CHALLENGE_PASS` because it opens
  no challenger representation or score;
- CE-4 requires `F1_FRONTEND_CHALLENGE_PASS` and a separate user authorization
  before any challenger development decision is emitted.

This is accepted exactly as ruled in `d76915a`.

## 6. Narrow ruling requested from Kimi

Please rule on one blocking question only:

> May M1 use the mechanically frozen definition
> `phase=select AND label_metric_only=0 AND old_missing=true`, yielding
> denominator `4,812`, `H_old=4,812`, and literal reduction gate `482`?

Recommended ruling: **ACCEPT**. It preserves the inherited split and removes
the only pre-freeze ambiguity.

If the answer is no, the alternative is not a mechanical correction. It must
identify a frozen authority that legitimately reclassifies `ood_val` and
`id_calib` from `fit` to `select`, explain why those rows did not fit the
incumbent/challenger head, and reopen independent review of the CE utility
denominator. Until that happens, `5,242` must not enter the FROZEN contract.

## 7. Authorization boundary

This clarification performs only a count-only reconstruction of already
frozen legal artifacts. It does not authorize or perform:

- CE implementation or execution;
- challenger retrieval, decoding, embedding, scoring, or training;
- report/viewed/FINAL access;
- HPC submission; or
- any change to the incumbent or challenger scientific rules.

