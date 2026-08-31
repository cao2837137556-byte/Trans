# Kimi Draft Review — Frontend-F0 Controlled Zero-Training Semantic Prototype Protocol

- Date: 2026-08-31
- Reviewer: Kimi (independent review role)
- Reviewed draft: `runs/mainline_docs/frontend_f0_controlled_zero_training_semantics_protocol_draft_20260831.md`
- Reviewed commit: `1e82990` (verified single-file commit)
- Governing chain: requirements `6495a6e`; Step-0b `41699ed`/`85bc105`; CE
  ruling `539b313`; CE FROZEN `fa8ff1d`/`1e68c55`

## Verdict

**DRAFT ACCEPTED — freeze authorized after two minor mechanical
clarifications (C1, C2) are incorporated.** The draft is a faithful,
well-bounded translation of the resource-cheapest candidate path (§12 of the
CE protocol): deterministic semantics only, no learned parameter, one
stop-loss candidate, full-universe measurement with CE integration reserved,
and a PASS that buys only the right to draft a learned-challenger protocol.

## Evidence-basis verification

Reviewer recomputed all four §2 document hashes: challenger requirements
`b46caf0d…`, Step-0b result `35272de7…`, CE FROZEN `0b102b79…`, CE freeze
verification `c0a20162…` — all match. ✓

## Rulings on §16 questions

**Q1 — H1/H2/H3/H4 hierarchy and the partition/feature distinction: ACCEPT.**
The hierarchy maps exactly onto the Step-0b diagnosis: the 1,988 "keyed but
unsupported-protocol" targets land in H2; the 9,605 dual-predicate targets
(non-IP, no five-tuple) land in H3/H4; the 13,827 incumbent-finite targets
stay in H1. Context partitioning uses endpoint equality only; numeric output
excludes endpoints entirely. The distinction is structurally enforced (§6.2,
§7 `raw_endpoint_values_emitted=false`, §8.11), not merely declared.

**Q2 — literal `256 / 300s / 60s` bounds: ACCEPT.** The 256-event bound is
consistent with the incumbent's representation budget; 300s/60s are standard
ICS sessionization values. Crucially, the bounds only split contexts — they
cannot manufacture missingness (the missing dictionary has five literal
causes, none bound-related), so the availability gates are not hostage to
these values. Their real risk is degeneracy, which is handled by Q3's
evidence obligations. After FROZEN the values are untunable; a coverage
failure terminates the candidate. That is the intended stop-loss.

**Q3 — H4 base class and anti-singleton/global-merge tests: ACCEPT.** The
base class (link type, EtherType, IP version, IP protocol, field-presence
bitmask) is the coarsest deterministic grouping that still separates
semantically distinct keyless streams. Same-class runs share bounded blocks;
class changes and epoch rules force splits. Tests 8/9 and obligations §8.8/8.9
cover both degenerate extremes synthetically; per-device/per-family
context-size distributions expose them on real data as mandatory evidence.

**Q4 — monotone timestamp surrogate as the only regression policy: ACCEPT.**
`t_star(i) = max(t_star(i-1), t_raw(i))` with strict-less regression counting
is one of the three policies permitted by frozen requirement R3, never
poisons later targets, never reorders history, and is identical for benign
and attack traffic. Regression counts surface in the output schema
(`timestamp_regression_count_in_context`), preserving auditability.

**Q5 — first-seen endpoint tokens and opaque-ID boundary: ACCEPT.** The
first-seen ordinal token construction is the correct design: because tokens
encode observation *order* rather than identity, a bijective endpoint
remapping preserves token assignment, hence the context partition and even
the digest inputs — which is precisely what obligation §8.10 and test 19
prove. Raw endpoints never enter numeric output; the digest is audit/join
only.

**Q6 — reuse of frozen `0.90/0.80/0.80` for semantic reachability: ACCEPT.**
Same values, same full-universe and missing-subset denominators, same
per-device/per-family individual reporting including zero rows. Continuity
with the inherited instrument is preserved; the added conjunct "all 13,827
incumbent-finite targets remain semantic-finite" is a genuine gate (decoder
corruption or ordinal absence could violate it), not a tautology.

**Q7 — PASS authorizes only a new learned-challenger DRAFT: ACCEPT.** The
draft correctly refuses to let semantic coverage imply detection capability,
OOD improvement, hydraulic repair, or superiority (§3.2), and
`ZT_SEMANTIC_COVERAGE_PASS` is explicitly not `F0_ENCODER_ONLY_PASS`, not
`F1_FRONTEND_CHALLENGE_PASS`, not CE promotion.

**Q8 — one-candidate stop rule and mature-component-first consequence:
ACCEPT.** One preregistered construction, no sweep, no outcome-conditioned
repair, no second zero-training variant; a PASS routes to mature-component
sourcing under a new protocol (§14.8), consistent with CE §12 anti-waste.

## Required clarifications before FROZEN (mechanical, no scientific change)

**C1 — Port-bearing non-TCP/UDP IP protocols need an explicit tier rule.**
The §5 matrix row "other observed IP protocol without ports → H2" is silent
on IP protocols that *do* carry ports (e.g., SCTP). If such an event is
observed, tier assignment is currently ambiguous. Add one sentence to §5/§6.4:
any observed IP protocol other than TCP/UDP is H2, and its port fields, when
present, are audit-only attributes that never enter the H2 context key. (If
no such protocol exists in the corpus, the rule is still needed so the
decoder cannot encounter an unclassified event class at runtime.)

**C2 — State what can produce `ZT_CONTEXT_DEGENERACY_NO_GO` on real data.**
§8 makes real-data context-size distributions "mandatory evidence, not a
tunable gate", while §11 lists `ZT_CONTEXT_DEGENERACY_NO_GO` as a terminal
state. As written, only the synthetic battery (obligations 8/9) can
mechanically trigger it. State this explicitly — e.g., "degeneracy NO-GO is
emitted only for synthetic-battery failures; real-data distributions are
descriptive evidence carried into the learned-challenger design review" — so
no one can later claim a real-data distribution retroactively failed (or
passed) a gate that does not exist.

## Additional findings (no change required)

1. The missing-reason dictionary is closed at five literals and none is
   bound-related — bounds split contexts but cannot manufacture missingness.
   Clean separation.
2. Boundary semantics are consistent throughout: current-inclusive
   comparisons, exact equality stays in epoch (tests 12–14), current packet
   included in current target (append-before-gate parity with the frozen
   embedder), tail release without rebuild (obligation 12, test 28).
3. ZT-2's real decode reuses the same 30 reviewed members and exact
   Step-0b cutoffs, is member-atomic and resumable with byte-identical
   resume (test 29), and requires a fresh user execution authorization after
   implementation review — the authorization chain is intact.
4. Labels are joinable only after identity/conservation gates (§7, test 24);
   `label_columns_read_during_construction` must be 0 — matches the
   Step-0b label-discipline.
5. §13's 32-test minimum covers every tier, boundary, causality, leakage,
   lifecycle, resume, and engineering-failure behavior; no observed real-world
   rate may be encoded as a success expectation (§9 ZT-1).

## Mechanics before freeze

1. Incorporate C1 and C2 verbatim; update §16 from questions to the eight
   rulings above.
2. Generate FROZEN + SHA-256 sidecar for reviewer SHA/diff verification.

This review authorizes mechanical revision toward FROZEN only. No
implementation, execution, PCAP opening, or retrieval is authorized.
