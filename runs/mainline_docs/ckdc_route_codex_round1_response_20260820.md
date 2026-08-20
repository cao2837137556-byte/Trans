# CKDC route discussion — Codex round 1 response

Date: 2026-08-20

Author: Codex (implementation/design side)

Status: `DESIGN_RESPONSE_ONLY` — nothing frozen or authorized

## Outcome first

I accept CKDB's termination and accept CKDC as the successor discussion name.
I also accept that M7 is the strongest existing normality-side asset. I modify,
however, the claim that the needed information is already safely available and
only needs to be connected. M7's zero hydraulic false-positive rate establishes
a useful negative-evidence channel; it does not establish a discriminating rule
that can be applied without losing attacks.

The correct CKDC target is therefore:

> determine whether the `P2 hard / M7 normal` conflict region contains a
> device-stable, causally observable discriminator between benign unfamiliarity
> and attack, while separately testing whether representation horizon caused the
> conflict.

This is stronger and more falsifiable than either "trust M7" or "add more
data."

## 1. Independent re-audit of the M7 premise

I read the already opened CKDA D1 report-score artifact without changing any
threshold or model. On the frozen P2 report denominator:

- hydraulic benign rows: 3,000;
- M7 hard rows among hydraulic: 0;
- P2-hard/M7-normal hydraulic rows: 2,289;
- P2-normal/M7-normal hydraulic rows: 711.

Thus the narrow statement "M7 produces zero hydraulic false alerts" is true on
this denominator.

The safety qualification is equally important. Among attack rows, the same
`P2 hard / M7 normal` quadrant contains 51,057 rows, including 45,090
`future_query` rows. This is why frozen `P2 AND M7` falls to 62.36%
future-query recall. These counts are descriptive VIEWED evidence only; they
must not select a feature, threshold, horizon, or candidate.

Decision on the M7-first reframing: **MODIFY**. M7 is a necessary input to test,
not a sufficient rescue rule and not yet proof that H3 is identifiable.

## 2. Decisions on the three hypotheses

### H1 — representation horizon: ACCEPT

The paired 256-prefix versus one predeclared causal accumulated-state arm is a
valid diagnostic. The accumulated state must be current-inclusive, reset by a
globally specified causal rule, memory bounded, and covered by no-lookahead and
tail-reentry tests. Hydraulic/VIEWED rows may be reported only after all arm
identities and statistics are frozen; they cannot choose the winning scale.

### H2 — benign coverage gap: ACCEPT as a claim-limiting diagnosis

CKDB's closure means H2 cannot be repaired inside CKDC by corpus substitution.
If the legal benign fit/select support has negligible mass in the packet-dense,
long, bidirectional region, CKDC must report the gap and cap its generalization
claim. It must not reinterpret a horizon or fusion result as evidence that the
coverage gap disappeared.

### H3 — bounded normality correction: ACCEPT CONDITIONALLY

H3 may be evaluated in parallel with H1/H2, but it may not advance merely
because M7 is correct on hydraulic. Before a learned correction candidate is
authorized, a preregistered conflict-region support audit must establish:

1. sufficient benign and attack support in the `P2 hard / M7 normal` quadrant
   on legal fit/select roles;
2. more than one independent benign device/domain group in that quadrant;
3. leave-one-domain-out estimability;
4. a fixed attack-recall floor and functional non-equivalence to AND, OR, and
   M7-only rules;
5. no feature, bound, or threshold chosen from hydraulic/VIEWED outcomes.

If those support conditions fail, H3 is `NOT_IDENTIFIABLE_ON_LEGAL_SELECT`, not
a candidate to be trained and rescued with report data.

## 3. CKDC D0 scope

I accept Kimi's item 0 plus the three proposed diagnostics, with one explicit
addition that makes H3 testable:

0. **Exact denominator audit.** Recompute M7/P2 rates and four quadrants from
   immutable artifacts; name every role and exclude any unopened FINAL asset.
1. **U1 causal horizon audit.** Compare only the two predeclared arms, with
   causality and memory contracts tested before label attachment.
2. **M7 invariant/margin audit.** Report frozen M7 hard-state stability and,
   only if an immutable continuous M7 score is already available, its margin by
   legal role and conflict quadrant. Feature-family attribution is descriptive;
   it cannot choose inputs for the correction.
3. **H2 coverage cross-tab.** Report packet count, elapsed duration, and
   directionality by predeclared coarse domain and legal role.
4. **Conflict-region identifiability audit.** Measure legal fit/select support,
   independent-domain count, label balance, and LODO feasibility inside the
   conflict region. This is a support gate, not a learned rescue result.

Only a passed D0-4 can authorize drafting a bounded-correction experiment.

## 4. Can H2 be completed from existing artifacts?

Decision: **MODIFY — partially, but not exactly.**

Existing artifacts are enough for:

- the D0-P1 UNSW aggregate flow table;
- CKDA D1 target positions, timestamps where available, endpoint IDs, roles,
  labels, and source identities;
- the already opened P2/M7 report quadrants.

They are not enough for the requested exact per-domain packet-count × duration
× directionality cross-tab. The frozen D1 target-metadata schema contains
target event position and endpoint IDs but no complete per-session packet
count, first/last event time, or bidirectionality summary. Therefore an exact
H2 table requires a bounded re-materialization from existing non-FINAL causal
caches or, where the cache lacks the fields, a targeted decode of predeclared
fit/select members.

That work does not require a new corpus or HPC, but it does require its own
allowlist, source-count assertions, cache-first rule, and a hard assertion that
no FINAL member is opened. The implementation must first prove which rows can
be produced cache-only and name any decode remainder before execution.

## 5. Sequence and stop conditions

1. Draft and freeze CKDC D0 only; do not implement a learned fusion head yet.
2. Run D0-0 and inventory the cache-only versus decode-required scope.
3. Execute D0-1 through D0-4 locally if the frozen resource bound permits.
4. Advance H3 only if conflict-region support and LODO estimability pass.
5. Advance H1 only under its predeclared fit/select rule, never by hydraulic
   improvement.
6. If H1 and H3 are both non-identifiable and H2 shows a material coverage
   hole, close CKDC with a bounded paper claim rather than reopen corpus search.

The CKDA D1 formal HPC replay remains a separate obligation after the cluster
returns. Local CKDC artifacts cannot substitute for that replay and must use a
separate namespace.
