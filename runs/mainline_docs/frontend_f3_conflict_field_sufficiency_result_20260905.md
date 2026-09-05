# Frontend-F3 targeted conflict-field audit — result

Result: `F3_CONFLICT_FIELDS_CANDIDATE_PASS`

Frozen protocol commit: `7241de4`  
Implementation commit: `b6a4e24`  
Result directory: `runs/frontend_f3_conflict_field_sufficiency_v1_20260905`

## Outcome

The current coarse H1–H4 event signature reproduced both Frontend-F2 hard contradictions exactly. The first frozen refinement level, L1, separated both contradictions without endpoint identifiers, raw high ports, labels, scores, representations, or payload bytes.

| level | unique prefixes among 28 rows | mixed-label buckets | protected hard contradictions |
|---|---:|---:|---:|
| L0 incumbent | 2 | 2 | 2 |
| **L1 causal shape** | **6** | **0** | **0** |
| L2 port taxonomy | 8 | 0 | 0 |
| L3 network-header shape | 8 | 0 | 0 |

Per the frozen order, L1 is the only surviving candidate. L2/L3 are not promoted.

## What L1 added

L1 retains the existing signature and adds only exact frame length, log2-microsecond causal inter-arrival bucket, transport data length, and TCP flags. It does not add IP/MAC identity or raw ephemeral ports.

The outcome-bearing 26-row TCP bucket split as follows:

- the Mirai C&C row ended with a 70-byte frame and 4-byte TCP data;
- the benign rows ended mainly with 80-byte frames and 14-byte TCP data, with causal timing forming three benign subgroups;
- therefore the attack prefix no longer equals any protected benign prefix.

The two-row UDP bucket also split (109/73-byte frame/UDP length versus 84/48), but this is descriptive only because those target-frame lengths had been viewed before the protocol freeze.

## Independent verification

- result package SHA256SUMS: 6/6 recomputed successfully;
- targets: 28/28, comprising 2 protected attacks and 26 protected benign rows;
- members: 8/8, each freshly decoded in two passes with equal discovery/replay packet counts;
- L0 prefix identities equal the two previously committed F2 conflict identities;
- emitted L1–L3 signatures contain neither raw endpoint values nor raw registered/dynamic ports;
- all select/viewed/report/FINAL/model/score/representation/payload/training counters are zero.

## Claim boundary and next gate

This is a real positive signal, but only a necessary-condition result. It does **not** yet show ability inheritance, detection improvement, or OOD-FPR improvement. It shows that the prior impossibility was caused by an overly coarse semantic signature and that a small, deployable input refinement can remove the two known contradictions.

The next worthwhile action is a full original-fit audit: re-decode all 13,866 F1 training targets using frozen L1, verify that no protected mixed-label token-prefix contradictions remain, measure vocabulary/cardinality feasibility, and then apply the already exposed five-row internal-validation set only as a kill-only check. Only if that audit passes is one final continuous old-P2 function-distillation training scientifically worth running.

