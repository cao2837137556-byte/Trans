# Frontend-F2 D0 structural addendum (FROZEN)

Date: 2026-09-04

Status: FROZEN before D0 execution and before any additional incumbent score
is opened.

Parent contract SHA-256:
`2a2b323a383de391c272bdc01dff1716819f25615dd6c0545a91723c38011a54`.

Numeric-semantics erratum SHA-256:
`c573ef26df6bf559b5c4006d0a0aa284c760a600294f059d1a0b102c1e997e49`.

## 1. Why two structural checks precede another training run

Continuous teacher preservation cannot solve two impossibilities:

1. a deterministic GRU cannot give different logits to byte-identical token
   prefixes carrying contradictory protected labels;
2. the prior 4,400-row internal-validation split has now exposed aggregate
   outcomes and five row-level failures, so reusing it for F2 checkpoint
   selection would adapt to an already viewed exam.

Both questions are answerable from the already authorized fit corpus without
opening a representation or score. They are mandatory D0 gates.

## 2. Input-identifiability audit

Recompute the frozen Frontend-F1 vocabulary solely from contexts whose parent
split is `train`, using the exact hash ordering in the pinned F1
implementation. Its identity must equal
`e5ca926798949ca0da1c87795d38aec9fc10c17ae52ecc844a489a98781efd4c`.

For every target in the 13,866-row parent training split, define the causal
input prefix as context signatures from index zero through that target's
`event_index`, inclusive. Compute two unambiguous SHA-256 identities:

```text
canonical_prefix_sha = SHA256(canonical JSON UTF-8 signature list)
token_prefix_sha = SHA256(canonical JSON UTF-8 integer-token list)
```

For both identity types, report every bucket containing more than one true
label, with owner, teacher kind, UID, source, family, and row counts. No row is
suppressed.

The hard contradiction is a token-prefix bucket containing both:

- an A `attack_hard` target; and
- an A `benign_normal` target.

If any hard contradiction exists, D0 terminates as
`F2_D0_NO_IDENTIFIABLE_PROTECTED_INPUT_FUNCTION`. Cross-owner and
teacher-wrong conflicts are reported as feasibility limitations but are not
silently promoted to the hard state because the frozen B utility gate does not
require every B benign row to become normal and teacher-wrong benign is
deliberately correctable.

Required output: `f2_d0_input_identifiability.json` plus
`f2_d0_conflicting_prefix_buckets.csv`. Required conservation:

```text
audited parent-train rows = 13866
audited parent-train contexts = 9307
```

## 3. Fresh nested F2 checkpoint split

The parent internal-validation sources remain closed throughout F2 training,
early stopping, and checkpoint selection. After one F2 checkpoint is frozen,
that entire parent split may be replayed exactly once as a kill-only regression
gate; it can reject but never select, tune, or trigger a retry.

Construct a fresh nested split only inside the 13,866-row parent training
universe. The indivisible unit remains `source_group`. Define:

```text
stratum = "attack_present" if any row in source_group is attack else "benign_only"
key = SHA256("frontend-f2-d1-internal-val-v1\0" || stratum || "\0" || source_group)
```

Within each stratum, sort `(key, source_group)`. Assign the first
`max(1, ceil(N_stratum / 5))` source groups to nested internal validation and
all remaining groups to nested training. No score, representation, device,
family, owner, or observed F1/F2 result participates.

Persist the literal source lists and a row/context table by nested split,
owner, label, teacher kind, source, and family as
`f2_d0_nested_split.json` and `f2_d0_nested_split_census.csv`.

The split is identifiable only if both nested sides contain at least one A
correct attack and one A correct benign context, and nested training contains
at least one B benign context and one B attack context. B attack absence from
nested validation is reported but is not repaired by moving a source. Failure
is `F2_D0_NO_IDENTIFIABLE_FRESH_CHECKPOINT_SPLIT`.

## 4. Training-dynamics claim boundary

The terminal five failures contributed all terminal attack-side hinge loss,
so this route must not claim that Frontend-F1 empirically ignored them through
mean dilution. The justified statement is narrower: mean-only training is not
structurally aligned with a zero-flip acceptance gate. Parent §7's worst-attack
term is retained for that prospective alignment, not presented as a proven
retrospective cause.

A future F2 ledger must persist per epoch:

- all component train and nested-validation losses;
- A protected attack flips;
- A protected benign new-hard rows;
- B benign hard rows and B attack hard rows;
- minimum correct-attack student logit margin;
- mean and maximum teacher-envelope violation.

This is mandatory diagnostic observability, not a new selection metric.

## 5. Combined D0 state

D0 can pass only if the parent continuous-envelope gate, the numeric-interface
gate, the protected-input identifiability gate, and the fresh nested-split gate
all pass. The combined success state is
`F2_D0_OLD_FUNCTION_PRESERVATION_FEASIBLE`.

All parent zero counters and authorization boundaries remain unchanged. This
addendum authorizes no optimizer step, checkpoint access, internal-validation
score, select, viewed, report, FINAL, PCAP, or deployment action.
