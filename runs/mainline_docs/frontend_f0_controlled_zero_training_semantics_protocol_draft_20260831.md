# Frontend-F0 Controlled Zero-Training Semantic Prototype Protocol (DRAFT)

- Date: 2026-08-31
- Branch: `codex/exp-mainline`
- Status: **DRAFT; NON-EXECUTABLE; independent review required before freeze**
- Author: Codex
- User authorization consumed here: **drafting only**
- Scope: frozen fit/select terminal-target universe only
- Route: Frontend-F0 challenger intake under the frozen Coverage Extension (CE)

## 1. Decision question

This protocol asks one deliberately narrow question:

> Can one deterministic, zero-training semantic layer assign every frozen target
> a causal, bounded, auditable event context across the observed TCP/UDP,
> ICMP/GRE, other IP, and five-tuple-ineligible traffic, without changing any
> incumbent score or alarm?

It does **not** ask whether a new encoder detects attacks, lowers OOD false
positives, or replaces netFound.  The prototype stops after semantic coverage.
Its only possible positive consequence is permission to draft a separately
reviewed learned-challenger intake protocol.

This is a one-candidate stop-loss experiment.  No second zero-training parser,
no parameter sweep, and no outcome-conditioned repair is permitted under this
protocol.

## 2. Immutable evidence basis

The protocol is grounded in the following reviewed documents.  Their current
byte identities are normative inputs to any later implementation:

| Document | SHA-256 |
|---|---|
| `runs/mainline_docs/frontend_f0_challenger_requirements_frozen_20260830.md` | `b46caf0d308531f512ffedd3a9dea8d1438c22a8d136f7c1965dff8ea3f411b0` |
| `runs/mainline_docs/frontend_f0_step0b_result_20260830.md` | `35272de7aae784e0966eab9f158f75cd3f0f65c387ada395a4cbe583a1670a78` |
| `runs/mainline_docs/frontend_f0_coverage_extension_protocol_frozen_20260831.md` | `0b102b7929e2a1ad2e269e35a5a225880a97d34bcc036d586b7066bcc5cddcfe` |
| `runs/mainline_docs/frontend_f0_coverage_extension_kimi_freeze_verification_20260831.md` | `c0a201623ff2d385519588eb8b1feea86725bde21c19923092c4fbdb4b33f515` |

The frozen target topology is:

| Quantity | Frozen value |
|---|---:|
| all fit/select terminal targets | 25,467 |
| incumbent finite | 13,827 |
| incumbent missing | 11,640 |
| missing benign | 11,478 |
| missing attack | 162 |
| unsupported non-TCP/UDP predicate | 11,605 |
| no IP five-tuple key predicate | 9,605 |
| timestamp-regression predicate | 47 |
| non-finite target timestamp | 0 |

Primitive predicates overlap.  In particular, 9,605 targets are both outside
the old TCP/UDP gate and without an old IP five-tuple key.  Merely allowing more
IP protocol numbers is therefore not a complete candidate.

## 3. Claim and authorization boundary

### 3.1 Permitted claim

The maximum positive claim is:

> On the pinned 25,467-target fit/select universe, one preregistered,
> deterministic, zero-training semantic construction can (or cannot) provide
> causal and bounded context coverage meeting the frozen availability and
> anti-degeneracy gates.

### 3.2 Explicit non-claims

Even a PASS does not establish:

- a finite learned embedding;
- retained attack information;
- lower benign OOD false-positive rate;
- preserved attack recall;
- repair of the finite hydraulic failure mode;
- cross-device generalization;
- report or FINAL performance; or
- superiority to the incumbent frontend.

### 3.3 Prohibited actions

This draft does not authorize implementation or execution.  Even after a future
freeze, the following remain separately authorization-gated:

- opening real PCAP members;
- producing learned embeddings;
- fitting, tuning, or selecting any parameter;
- loading model weights or detector scores;
- changing any incumbent alarm;
- opening viewed/report/FINAL roles;
- network retrieval, HPC submission, or training.

## 4. Literal meaning of zero-training

The prototype contains **no learned parameter**.  Specifically, it may not:

1. call `fit`, `partial_fit`, backpropagation, gradient descent, clustering,
   metric learning, dimensionality reduction, or threshold optimization;
2. estimate a vocabulary, normalization statistic, bucket edge, timeout,
   protocol rule, or context rule from real outcomes;
3. use benign/attack labels while parsing events or constructing contexts;
4. use device/source identity to choose a different rule or constant;
5. use raw endpoint identifiers as numeric features or model inputs;
6. emit or consume a detector score, hard decision, or learned representation;
7. promote a failure into a new zero-training variant after seeing results.

The implementation, if later authorized, is limited to declarative packet
parsing, deterministic context assignment, status materialization, and audit
tables.

## 5. Declared observed-event support matrix

The prototype must attempt all observed targets.  Matrix membership may not be
used to remove a denominator row.

| Event class | Required decoded fields | Context tier | Ordinary semantic result |
|---|---|---|---|
| IPv4/IPv6 TCP | IP endpoints, ports, protocol, packet ordinal, finite timestamp | H1 transport | finite |
| IPv4/IPv6 UDP | IP endpoints, ports, protocol, packet ordinal, finite timestamp | H1 transport | finite |
| IPv4/IPv6 ICMP or ICMPv6 | IP endpoints, protocol, packet ordinal, finite timestamp | H2 network-protocol | finite |
| IPv4/IPv6 GRE | IP endpoints, protocol, packet ordinal, finite timestamp | H2 network-protocol | finite |
| other observed IP protocol without ports | IP endpoints, protocol, packet ordinal, finite timestamp | H2 network-protocol | finite |
| non-IP event with two link-layer endpoints | endpoints, EtherType/link type, packet ordinal, finite timestamp | H3 link-event | finite |
| event without a usable endpoint pair | link type, field-presence mask, packet ordinal, finite timestamp | H4 keyless event block | finite |
| corrupt decode or non-finite target time | available audit fields | none | missing with literal reason |

ICMP type/code, GRE key, TCP flags, addresses, ports, and hardware identifiers
may be retained as audit-only raw decoder fields where already legally present,
but none may alter the context-tier rules below after freeze.  Payload bytes are
never opened or represented.

The missing-reason dictionary is closed:

- `DECODER_CORRUPT_EVENT`
- `NONFINITE_EVENT_TIMESTAMP`
- `REQUIRED_PACKET_ORDINAL_ABSENT`
- `TARGET_NOT_REACHED_AT_EXACT_CUTOFF`
- `CONTEXT_CONSTRUCTION_INVARIANT_FAILURE`

An observed ICMP, GRE, other IP, or endpoint-less event may not be labeled
unsupported merely because it is inconvenient.

## 6. Frozen causal-context construction

### 6.1 Global invariants

All tiers obey the following invariants:

1. state is isolated by frozen source and packet member;
2. only packets at or before the current target cutoff may affect that target;
3. the current packet is included in the current target context;
4. no context crosses a member boundary;
5. no context contains more than **256 events**;
6. no context spans more than **300.0 surrogate seconds**;
7. an idle gap strictly greater than **60.0 surrogate seconds** opens a new
   context epoch;
8. all limits use current-inclusive comparisons; exact equality remains in the
   existing context;
9. state is released after its last frozen target and may not be rebuilt by
   irrelevant later packets; and
10. future packets or future timestamps cannot revise an earlier context.

These values are literals, not candidates.  They may be modified during draft
review, but after FROZEN they may not be tuned or swept.

### 6.2 Endpoint orientation and identity boundary

Endpoint values may be used only to test equality and to partition causal
contexts.  They are excluded from every numeric output.

For each member, endpoints receive past-only first-seen ordinal tokens.  The
first endpoint observed in a base context is orientation `A`; its peer is `B`.
Direction is emitted only as `A_TO_B`, `B_TO_A`, or `UNKNOWN`.

`causal_context_id` is an opaque SHA-256 digest of:

```text
"frontend-f0-zt-v1" || source_id || member_id || tier ||
canonical first-seen endpoint tokens || protocol class || epoch ordinal
```

The digest is an audit/join identifier, never a feature.  Raw endpoints and the
digest itself are forbidden from any later tensor unless a separate protocol
explicitly reauthorizes and audits them.

### 6.3 H1 — TCP/UDP transport context

The base key is:

```text
(IP version, IP protocol, unordered endpoint-token/port pair)
```

The epoch rule in §6.1 bounds repeated transport conversations.  TCP control
flags do not reset a context in this semantics-only prototype; they remain
audit fields.  This avoids silently giving TCP a richer hand-written semantic
model than non-TCP protocols.

### 6.4 H2 — portless IP protocol context

The base key is:

```text
(IP version, IP protocol, unordered endpoint-token pair)
```

ICMP type/code and optional GRE key are event attributes, not context keys.
Thus the prototype represents a causal conversation without pretending that a
portless protocol has transport ports.

### 6.5 H3 — non-IP link-event context

When two link-layer endpoints exist, the base key is:

```text
(link type, EtherType if present else literal NONE,
 unordered endpoint-token pair)
```

The same epoch rule applies.  The context must be named
`causal_context_id`; it must not be called a flow or five-tuple session.

### 6.6 H4 — fully keyless event block

When no usable endpoint pair exists, the prototype uses a member-local bounded
event block.  Its base class is:

```text
(link type, EtherType if present, IP version if present,
 IP protocol if present, decoder field-presence bitmask)
```

A new block begins on the first eligible event, a base-class change, an idle
gap greater than 60.0 surrogate seconds, an elapsed span that would exceed
300.0 surrogate seconds, or an event that would raise block size above 256.

This fallback is neither one capture-wide pseudo-session nor forced singleton
packetization.  Repeated same-class keyless events within the frozen bounds
must share a block.

### 6.7 Timestamp-regression policy

Packet ordinal, not timestamp sorting, defines causal processing order.

For each active base context, let `t_raw(i)` be the decoded finite timestamp and
`t_star(i)` its causal surrogate:

```text
t_star(0) = t_raw(0)
t_star(i) = max(t_star(i-1), t_raw(i))
delta_star(i) = t_star(i) - t_star(i-1)
regression(i) = [t_raw(i) < t_star(i-1)]
```

A regression is counted and clamped; it does not poison all later targets and
does not reorder history.  A non-finite timestamp remains a literal missing
failure.  The policy is identical for benign and attack traffic.

## 7. Semantic materialization schema

The prototype emits no embedding.  It emits exactly one semantic status row
per frozen target with the following columns:

- `uid`
- `source_id`
- `member_id`
- `target_packet_ordinal`
- `semantic_finite`
- `semantic_missing_reason`
- `context_tier`
- `causal_context_id`
- `context_epoch`
- `context_event_count`
- `context_surrogate_span_seconds`
- `direction_code`
- `link_type`
- `ip_version_or_none`
- `ip_protocol_or_none`
- `transport_ports_present`
- `timestamp_regression_count_in_context`
- `raw_endpoint_values_emitted` (must be `false`)
- `label_columns_read_during_construction` (must be `0`)

All fields except `uid`, frozen lineage identifiers, and the opaque context ID
are descriptive audits, not model inputs.  Labels may be joined only after the
25,467-row identity and conservation gates have passed.

## 8. Anti-degeneracy and causality proof obligations

The prototype must prove all of the following before any PASS:

1. exactly one status row exists for each of 25,467 frozen UIDs;
2. no unregistered UID exists;
3. all 13,827 incumbent-finite targets remain semantically finite;
4. no context crosses source/member boundaries;
5. no context exceeds 256 events or 300.0 surrogate seconds;
6. future packet mutation leaves every earlier row byte-identical;
7. timestamp regression never reorders or revises earlier rows;
8. a synthetic repeated H4 event cohort forms at least one context of size
   greater than one;
9. two separated H4 cohorts cannot collapse into one member-wide context;
10. a bijective per-member remapping of endpoint identities preserves the
    complete context partition and every non-ID semantic field;
11. raw endpoint identifiers do not appear in numeric or textual semantic
    outputs;
12. state is empty after all exact cutoffs have completed; and
13. role labels, report, FINAL, detector scores, model weights, and learned
    arrays remain unopened during construction.

Dataset context-size distributions are mandatory evidence, not a tunable gate:
counts, minimum, quartiles, maximum, singleton fraction, and hierarchy-tier
share must be reported by benign device and exact attack family.  This exposes
pseudo-session and singleton degeneration without using observed rates to
change the rule.

## 9. Frozen stage sequence

### ZT-0 — identity and code-surface audit

No PCAP or array is opened.  Verify:

- all normative document hashes in §2;
- exact target and member manifests inherited from reviewed Step-0b;
- Python 3.9 compatibility;
- absence of learning/tuning imports and calls;
- literal constants and missing-reason dictionary;
- output path isolation and failure-marker behavior.

Any identity mismatch terminates before real decoding.

### ZT-1 — synthetic semantics and causality battery

Run only constructed packet/event fixtures covering every tier, exact boundary,
future mutation, timestamp regression, endpoint remapping, source/member reset,
tail release, and H4 anti-degeneracy behavior.

No real target count or observed result may be encoded as a test success
expectation except the already frozen identities and denominators.

### ZT-2 — real count-only causal re-decode

Requires a new user execution authorization after implementation review.  Use
the same 30 reviewed packet members and exact inclusive target cutoffs as
Step-0b.  Materialize semantic status only; no representation, model, score, or
label is opened.

Execution is member-atomic, resumable, and two-pass where required to discover
last-target cutoffs without future leakage.  A resumed member must reproduce
the same byte identity as a clean run.

### ZT-3 — post-construction descriptive join

Only after the exact UID and conservation gates pass may frozen role/device/
family columns be joined to compute availability and context-size tables.
No detector decision is computed.

## 10. Scientific gates

### 10.1 Full-universe semantic availability

All conditions are conjunctive:

```text
exact status rows = 25,467 / 25,467
overall semantic-finite rate >= 0.90
every benign device semantic-finite rate >= 0.80
every exact attack family semantic-finite rate >= 0.80
all 13,827 incumbent-finite targets remain semantic-finite
```

All benign devices and all exact attack families are reported, including zero
rows and unsupported outcomes.

### 10.2 CE missing-subset semantic availability

Only if §10.1 passes, evaluate the frozen 11,640 incumbent-missing targets:

```text
exact incumbent-missing status rows = 11,640 / 11,640
missing-subset semantic-finite rate >= 0.90
every benign device's incumbent-missing semantic-finite rate >= 0.80
every exact missing attack family's semantic-finite rate >= 0.80
```

This is a semantic reachability gate, not the CE-3 learned-embedding gate.

### 10.3 Structural gate

Every obligation in §8 must pass.  A coverage PASS cannot override a causality,
identity-leakage, global-merge, singleton-degeneration, or state-lifecycle
failure.

## 11. Literal terminal states

Exactly one terminal state is emitted:

- `ZT_IDENTITY_FAILURE`
- `ZT_PY39_OR_DEPENDENCY_FAILURE`
- `ZT_SEMANTICS_CONTRACT_FAILURE`
- `ZT_CAUSALITY_NO_GO`
- `ZT_CONTEXT_DEGENERACY_NO_GO`
- `ZT_RESOURCE_NO_GO`
- `ZT_INSUFFICIENT_SEMANTIC_COVERAGE`
- `ZT_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT`
- `ZT_SEMANTIC_COVERAGE_PASS`

`ZT_SEMANTIC_COVERAGE_PASS` means only that a learned challenger may be
specified in a new DRAFT.  It is **not** `F0_ENCODER_ONLY_PASS`,
`F1_FRONTEND_CHALLENGE_PASS`, CE promotion, or permission to train.

A scientific NO-GO closes this zero-training semantic construction.  Its
constants or hierarchy may not be modified after seeing the result.  An
engineering failure may be repaired only by a narrow regression-tested change
that leaves all frozen scientific rules untouched.

## 12. Required durable outputs

Any real execution must produce:

1. immutable input identity manifest;
2. contract and implementation identities;
3. literal support matrix and missing-reason dictionary;
4. exact 25,467-row semantic status table;
5. full-universe availability tables by role/device/family;
6. 11,640-row CE missing-subset availability tables;
7. context-size distributions by device/family and hierarchy tier;
8. timestamp-regression counts by device/family;
9. endpoint-remapping invariance report;
10. context-bound and lifecycle audit;
11. role/open-boundary audit;
12. resource and checkpoint manifest;
13. literal terminal verdict JSON;
14. human-readable result report;
15. `SHA256SUMS` over every scientific output.

## 13. Minimum implementation contract tests

Before real execution, a future implementation must pass at least these tests:

1. IPv4 TCP bidirectional packets share H1 context;
2. IPv6 UDP bidirectional packets share H1 context;
3. ICMP packets share H2 context without invented ports;
4. GRE packets share H2 context without invented ports;
5. other portless IP protocol reaches finite H2 status;
6. non-IP endpoint-paired events reach H3 status;
7. fully keyless repeated events reach bounded H4 context;
8. H4 is not forced singleton;
9. H4 is not one member-wide pseudo-session;
10. member boundary resets all context state;
11. source boundary resets all context state;
12. idle gap `== 60.0` remains in epoch and `> 60.0` opens a new epoch;
13. span `== 300.0` remains in epoch and `> 300.0` opens a new epoch;
14. event 256 remains in epoch and event 257 opens a new epoch;
15. current target includes current packet;
16. a future packet mutation cannot alter prior target output;
17. timestamp regression clamps without reordering;
18. non-finite timestamp fails with the exact literal reason;
19. endpoint bijection preserves the context partition;
20. raw endpoint values are absent from outputs;
21. payload bytes are never requested;
22. every target receives exactly one status row;
23. duplicate or unregistered UID fails closed;
24. label join before identity conservation fails closed;
25. representation/model/score access fails closed;
26. report/FINAL access fails closed;
27. state is empty after last targets;
28. irrelevant tail packets cannot rebuild released state;
29. clean run and resumed run are byte-identical;
30. Python 3.9 compile and runtime API checks pass;
31. a terminal engineering failure removes any scientific verdict; and
32. every scientific output is covered by `SHA256SUMS`.

## 14. Resource and anti-waste contract

1. No network retrieval, pretrained checkpoint, GPU, or HPC is required.
2. The prototype reuses only already legal local packet members and the exact
   Step-0b cutoffs.
3. Execution is bounded to one preregistered construction and one clean result;
   no constant sweep or alternative hierarchy is allowed.
4. A small synthetic battery precedes all real decoding.
5. Real decoding is member-atomic and resumable; interrupted work does not
   justify changing scientific rules.
6. A resource pilot may measure wall time, peak RSS, and output bytes only.  It
   may not inspect scientific rates or choose constants.
7. A future implementation must publish a local storage budget and fail before
   decoding if the budget is unavailable.
8. A PASS leads to mature-component/challenger sourcing and a new protocol,
   not immediate custom encoder development.

## 15. Relationship to Coverage Extension

CE remains the normative first integration architecture:

```text
old_missing=false -> copy frozen incumbent E3/P2 score and verdict exactly
old_missing=true  -> future challenger branch, only after its own gates
```

This prototype never owns an alarm and never recomputes the 13,827 incumbent-
finite decisions.  Measuring all 25,467 targets preserves the examination
universe; CE later restricts only integration ownership.

Therefore existing attack capability is protected structurally, not by hoping
that a replacement model reproduces it.  The finite hydraulic false-positive
problem remains outside this protocol and may not be presented as solved by a
semantic-coverage PASS.

## 16. Review requests before freeze

Independent review should explicitly ACCEPT/MODIFY/REJECT:

1. the H1/H2/H3/H4 hierarchy and its distinction between context partitioning
   and model features;
2. the literal `256 events / 300 seconds / 60 seconds idle` bounds;
3. the H4 base-class definition and its anti-singleton/global-merge tests;
4. the monotone timestamp surrogate as the only regression policy;
5. the endpoint first-seen-token and opaque-ID boundary;
6. reuse of the frozen `0.90 / 0.80 / 0.80` availability gates for semantic
   reachability;
7. the rule that a PASS only authorizes a new learned-challenger DRAFT and does
   not equal any frozen F0/F1 verdict; and
8. the one-candidate stop rule and mature-component-first consequence.

## 17. Current authorization state

This document consumes the user's authorization to **draft only**.

Not authorized now:

- FROZEN conversion or SHA sidecar;
- implementation or tests;
- any real or synthetic execution;
- PCAP opening or re-decode;
- candidate retrieval or network access;
- representation generation;
- head training or detector-score opening;
- CE routing execution;
- report/FINAL access; or
- HPC submission.

The next legal action is independent review of this DRAFT.
