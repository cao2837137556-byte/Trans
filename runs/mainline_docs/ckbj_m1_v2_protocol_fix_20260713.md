# CKBJ / CKBH-v2 formal M1 correction — 2026-07-13

## Status

`LOCAL_IMPLEMENTATION_AND_CONTRACT_TESTS_COMPLETE; HPC_NOT_SUBMITTED`

The completed CKBI Stage A cache remains valid and read-only.  Job `150548`
and any duplicate built from commit `195b1c26` must not be used as formal M1
evidence: that revision contained deterministic contract failures and an
invalid cross-source negative sampler.

## Immutable data boundary

- CKBE base T0 remains `26` sources / `34,622` targets; manifest SHA-256 is
  `b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67`.
- CKAT base C1 source plan remains `26` sources; SHA-256 is
  `414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebc128f2`.
- CKAT base C1 target manifest remains `34,622` targets; SHA-256 is
  `74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158`.
- CKBI remains a separate four-source, `290,445`-target, label-free,
  report-only TGN extension.
- CKBJ creates the matching C1 canonical-time features for exactly those four
  CKBI sources/targets.  It is materialized inside the metrics-producing
  Stage B job, is hash-bound to CKBI and CKAT, and has zero fit/select use.
- The underlying strict 1M role split is not changed.  Fit/select use the
  frozen `train-cap=4000` / `eval-cap=3000` cohort.  Report membership is the
  union of the immutable base target manifest and the CKBI report extension;
  the code never re-caps the full report table into a different cohort.

## Corrected causal flow

```text
legal fit target events only
  -> source-local PyG TGNMemory
  -> IdentityMessage + LastAggregator + internal TimeEncoder
  -> LastNeighborLoader + official-example TransformerConv embedding
  -> link / reverse / ACK-RST / retry SSL
  -> fresh fit-only replay
  -> all legal support_train, family-balanced per-event verifier

legal fit context + legal select targets only
  -> fresh select replay -> C1/verifier gate selection

report source, fresh reset, torch.no_grad(), frozen weights/thresholds
  -> label-free chronological raw history
  -> score current target before update_state
  -> update current event only after scoring
  -> metrics; review=0
```

Fit embeddings never replay select/report events.  Select embeddings replay
only legal fit context plus legal select targets.  Report replay is separately
reset and may update memory only from label-free past events; it cannot update
weights, normalization, C1, negatives, or a gate.

## Corrected negative sampling

The old sampler drew from the maximum node capacity across all sources.  Since
the graph IDs are source-local, that produced mostly nonexistent ghost nodes.
The corrected candidate universe is:

```text
current source's nodes observed strictly before the current fit event
- current src
- current dst
- existing PyG LastNeighborLoader neighbours of src
```

If the set is empty, the negative is skipped and counted.  The audit records
pool min/mean/max, sampled/skipped counts, `ghost_node_negatives=0`, and
`future_node_identity_used=false` for every source/epoch.

## Gate and metric corrections

- No eligible threshold now means a diagnostic fallback plus an obligatory
  gate-contract failure; it can never become a formal GO signal.
- `overall_attack_hard_recall` excludes `support_train`.  It uses evaluation
  attacks only; `support_val` remains separately visible.
- Global report OOD receives its own CSV instead of being silently discarded.
- M1-C1 deltas receive paired source bootstrap intervals, with episode-cluster
  fallback when a table has only one source.
- The single-seed decision additionally fails closed on missing metrics,
  incomplete alignment, nonfinite loss, invalid negatives, incomplete support
  use, gate failure, report-extension leakage, or nonzero review.
- A seed-27 result is `GO_SIGNAL` only when the registered hard constraints
  pass and stream OOD improves by at least 10 percentage points to at most
  90%.  Otherwise it stops as `NO_GO` or `INCONCLUSIVE_STOP`; it never launches
  seeds 37/47 automatically.

## Local evidence

- Python compilation: pass.
- Slurm shell syntax: pass.
- PyG causal unit test, seed 27: pass.
- Current target before update: pass.
- Future mutation invariance / past mutation sensitivity: pass.
- Fresh source reset equivalence: pass.
- Fit-only future outcome ignores non-fit event mutation: pass.
- Past-seen source-local negative contract: pass.
- Gate with no attack-preserving threshold is marked failed: pass.
- Frozen CKAT plan and target hashes/cardinalities: pass.
- Repeatable test entrypoint:
  `repo/ood/issue27ckbj_tgn_m1_contract_tests_v1.py`.
- No repeated environment preparation, independent preflight, or synthetic
  optimization job was run.

## Formal outputs

The single formal job writes attack preservation, strict Level-2, global OOD,
per-family recall, paired delta CI, support-row/family uses, SSL task balance,
negative pools, role/target alignment, held exclusion, memory resets/batching,
source-local-node proxy audit, loss curves, base/extension hashes, environment,
wall time, in-job RSS, job ID, and a single-seed decision JSON.

## Resource envelope and next action

Prepared request: one node, 16 CPUs, 128 GiB, 48-hour upper bound, seed 27.
The longer limit protects the six protocols plus four-source C1 report-cache
materialization; actual accounting stops when the job finishes.

Next action: review the local diff and bundle, then submit only
`scripts/issue27ckbj_tgn_m1_formal_v2.slurm`.  Do not rerun CKBI Stage A and do
not submit the old CKBH-v1 Slurm file.
