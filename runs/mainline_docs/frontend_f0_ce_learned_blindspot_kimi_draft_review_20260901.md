# Kimi Draft Review — Frontend-F0 CE Learned Blind-Spot Branch D0/D1 Protocol

- Date: 2026-09-01
- Reviewer: Kimi (independent review role)
- Reviewed draft: `runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_draft_20260901.md`
- Reviewed commit: `b700f3d` (verified single-file commit)
- Governing chain: requirements `6495a6e`; CE `fa8ff1d`/`1e68c55`; ZT draft
  review `2cce672`; ZT FROZEN `5829c3a`; ZT-2 result `6f210af`

## Verdict

**DRAFT ACCEPTED — freeze authorized after one mandatory pre-freeze addition
(M1: cross-phase context resolution + frozen census literals) and two
modifications (Q1, Q7) are incorporated.**

The draft is structurally sound: incumbent ownership immutable, semantic
contract dominant over the candidate, fit-only label-free learning with
context-grouped isolation, sparse-attack honesty, and a representation PASS
that buys only the right to draft a detector-head protocol. The reviewer's
independent census (below) both grounds the requested numerical rulings and
surfaces one structural fact the draft does not yet handle: **19 frozen
semantic contexts span the fit/select phase boundary**.

## 0. Governance note — ZT chain retrospective verification

The ZT FROZEN (`5829c3a`), implementation (`07cb50d`, `2daa901`), and real
execution (`6f210af`) proceeded between reviewer checkpoints. The reviewer has
now retrospectively verified this chain independently:

- FROZEN vs reviewed draft (`2cce672`): full diff contains only C1, C2, §16
  rulings, and status updates — zero scientific drift. FROZEN SHA
  `532bb52e…` recomputed ✓.
- ZT-2 result bundle: **16/16 SHA256SUMS recomputed OK** ✓.
- Per-target status table spot-check: 25,467 rows / unique UIDs, all
  semantic-finite, tier split H1 13,953 / H2 1,909 / H3 9,579 / H4 26, raw
  endpoints emitted nowhere, labels read nowhere, verdict
  `ZT_SEMANTIC_COVERAGE_PASS`, all six boundary counters 0 ✓.
- Draft-pinned ZT-2 artifact hashes: status table `73aa2834…`, result report
  `64266351…` — both recomputed, match ✓.

**ZT-2 is accepted as a valid positive prerequisite.** Procedural reminder,
non-blocking this once: FROZEN conversion, implementation review, and
execution-result review are independent gates; future chains must not run
ahead of them.

## 1. Reviewer's independent context census (count-only, frozen artifacts)

Computed from the pinned ZT-2 status table exact-joined to the frozen
fit/select plan and availability container (25,467/25,467 one-to-one, zero
misses):

| Quantity | Value |
|---|---:|
| independent semantic contexts (member, context_id, epoch) | 18,187 |
| fit rows / fit contexts | 18,398 / 12,908 |
| select rows / select contexts | 7,069 / 5,298 |
| **cross-phase contexts (contain both fit and select rows)** | **19** (132 fit rows + 32 select rows) |
| fit contexts after whole-context exclusion | 12,889 (18,266 rows) |
| old-missing rows / contexts | 11,640 / 9,379 |
| old-missing fit benign rows / contexts | 6,666 / 5,178 |
| old-missing select benign rows / contexts | 4,812 / 4,157 |
| old-missing attack rows / independent contexts | **162 / 44** |
| — fit attack contexts (pre-exclusion) | 40 (File Download 2, C&C 6, ICMP 17, GRE 14, UDP **1**) |
| — select attack contexts | 15 (C&C 3, ICMP 5, GRE 7) |
| — attack contexts that are cross-phase | 11 |

## 2. M1 — mandatory pre-freeze addition: cross-phase context resolution

The draft's D0-A leakage gate ("fails closed if one semantic context appears
in more than one phase") would, executed as written, terminate immediately on
the 19 cross-phase contexts the reviewer has already counted. The FROZEN
document must therefore define the resolution now, not discover it at D0:

**Ruling: whole-context exclusion from encoder training.** A context
containing any select-phase row is assigned entirely to the evaluation side
and excluded from encoder fitting, vocabulary fitting, and checkpoint choice.
Cost is immaterial: 19 contexts / 132 fit rows (0.15% of fit contexts). This
is conservative, mechanically simple, and requires no change to the frozen
semantic contract (contexts are not redefined; they are only excluded from
one side). The 11 attack-bearing cross-phase contexts follow the same rule;
the post-exclusion fit attack-context count is frozen in the D0 addendum.

## 3. Rulings on §17 questions

**Q1 — minimums deferred vs set now: MODIFY — set the literal lower bounds in
the FROZEN document now.** The census above is computable today from
already-frozen legal artifacts, so there is no reason to let D0 "discover"
denominators and then propose bounds beside them. D0-A becomes mechanical
re-verification of frozen literals. Frozen bounds (rationale in parentheses):

```text
total fit contexts after exclusion          >= 10,000   (actual 12,889)
old-missing benign fit contexts             >=  4,000   (actual 5,178)
select benign contexts for evaluation       >=  4,000   (actual 4,157 old-missing select benign)
fit attack contexts, global                 >=     30   (actual 40 pre-exclusion; post-exclusion
                                                         count frozen in D0 addendum)
per-family attack contexts                  report literally; <3 flags
                                            INSUFFICIENT for that family's rows
```

(30 is the floor below which even a global grouped canary is not meaningful;
the current census clears it with headroom, and any post-exclusion shortfall
terminates as `CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS` — no
resampling.)

**Q2 — nomination rule outcome-blindness: ACCEPT the two-tier rule.** The
ten-item rubric is assessable without real outcomes (identity, documentation,
synthetic battery). Strengthening, mandatory: the rubric must be recorded
item-by-item with evidence for every assessed mature component, and every
mature failure must carry literal reasons — no silent shopping. Do not name
the controlled encoder now; its architecture belongs to the D0 addendum.

**Q3 — all-fit vs old-missing-only training corpus: ACCEPT all-fit.**
Label-free representation learning needs the full traffic distribution;
restricting to the blind spot (5,178 benign contexts) would bias the encoder
toward rare protocols and waste the 12,889-context diversity. Deployment
ownership is untouched; labels, families, and old scores are unavailable to
the loss; the split is context-grouped (M1).

**Q4 — deterministic summary control: ACCEPT as a valid control.** It is
non-promotable, cannot own targets, and exists solely as the value-added
reference for the canary — same role as the frozen requirements'
shallow-header control. Its exact fields, bucketing, aggregation, and
dimension must be frozen in the D0 addendum before any learned array exists
(draft already requires this).

**Q5 — device-leakage metric and guard: freeze the following.** (a) Metric:
balanced accuracy of a frozen-capacity **linear** device classifier under
context-grouped splits. (b) Chance reference: permutation null, ≥1,000
permutations, 99th percentile. (c) Guard shape: **comparative, not absolute**
— the learned representation's device decodability may not exceed the
deterministic summary control's decodability by more than a frozen margin
(margin literal in the D0 addendum). Absolute "near-chance" is rejected as
the guard: devices legitimately differ in traffic, and CKDE-S died proving
that. (d) The masked-endpoint arm must independently pass the
attack-information canary; if unmasked passes and masked fails, the candidate
is fingerprint-reliant → `CEL_D1_DEVICE_OR_ENDPOINT_SHORTCUT_NO_GO`.

**Q6 — minimum independent missing-attack contexts: ruled in Q1's literal
table** (global ≥30; per-family <3 flags INSUFFICIENT; no per-family positive
claim under any count). The select 23 rows / 15 contexts remain kill-only.

**Q7 — small-MLP canary: MODIFY — remove it.** With ~40 fit attack contexts,
a trainable canary adds selection surface (capacity, stopping, seed) for no
identifiable gain. The ladder stops at nonparametric geometry + frozen linear
probe. If linear evidence is null and nonlinear structure is suspected, that
suspicion requires a new protocol, not an in-run upgrade.

**Q8 — inherited geometry constants: ACCEPT as provisional defaults, with
conditions.** Projection distance and principal angles are dimensionless and
computed by the same LODO construction, so 0.20/0.35 and 20°/35° are portable
*provided*: (a) metric definitions are reproduced verbatim in the D0
addendum; (b) the eligible-device denominator is disclosed literally; (c) if
eligible devices < 4, geometry is descriptive-only and cannot produce a
positive gate verdict; (d) the R-ratio guards (median ≥2.0, ≥80% devices
≥1.0) follow the same eligibility rule. The blind-spot branch spans ~5 benign
devices, so this is executable but thin — reported with denominators, as
usual.

## 4. Additional findings (no change required)

1. §7's label-isolation rules (no labels/families/old scores in the loss,
   fit-only vocabulary, deterministic hash-group internal validation nested in
   phase=fit, no class balancing) are exactly the discipline the thin attack
   evidence requires.
2. §9's value-added gate (`CEL_D1_NO_LEARNING_VALUE_ADDED`) is the correct
   answer to "why learned at all": 100% availability cannot rescue an encoder
   that adds nothing over fixed summary statistics.
3. §11.5 keeps the 23-row select guard kill-only and forbids repairing small
   denominators by row resampling — consistent with the CE contract and F1.
4. The claim matrix (§16) correctly marks hydraulic finite-target error and
   whole-system OOD FPR as **not measured** by this protocol.
5. Draft-pinned prerequisite hashes verified by the reviewer (§0).

## 5. Mechanics before freeze

1. Incorporate M1 (cross-phase whole-context exclusion + the 19-context
   disclosure) and Q1's literal bound table verbatim.
2. Apply the Q7 modification (canary ladder ends at linear).
3. Incorporate Q5's metric/guard definitions and Q8's portability conditions.
4. Update §17 from questions to these rulings.
5. Generate FROZEN + SHA-256 sidecar for reviewer SHA/diff verification.

This review authorizes mechanical revision toward FROZEN only. No
implementation, census execution, retrieval, training, or representation
generation is authorized.
