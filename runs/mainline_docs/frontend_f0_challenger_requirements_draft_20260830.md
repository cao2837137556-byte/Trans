# Frontend-F0 Challenger Requirements (DRAFT)

- Date: 2026-08-30
- Status: **DRAFT; discussion/review only; NON-EXECUTABLE**
- Basis: Step-0b result commit `41699ed`; independent result review `85bc105`
- Scope: the frozen fit/select terminal-target universe only
- Purpose: freeze what any replacement frontend must prove before choosing,
  retrieving, training, or executing a challenger

## 1. Why this document exists

Step-0b converted the old generic `missing=true` state into an exact causal
topology on 25,467 frozen fit/select terminal targets:

| Fact | Exact result |
|---|---:|
| missing targets | 11,640 |
| finite targets | 13,827 |
| unsupported non-TCP/UDP predicate | 11,605 |
| no IP five-tuple session key predicate | 9,605 |
| causal timestamp-regression predicate | 47 |
| non-finite target timestamp predicate | 0 |
| benign targets missing | 11,478 / 21,013 (54.62%) |
| attack targets missing | 162 / 4,454 (3.64%) |

The predicates overlap. In particular, 9,605 targets simultaneously lack the
old IP five-tuple key and fall outside the old TCP/UDP protocol gate. Therefore
the next frontend cannot be defined as merely "allow more protocol numbers".
It must jointly provide protocol/event coverage and a causal representation
unit for events for which a TCP/UDP five-tuple does not exist.

This is a requirements contract, not a model nomination. Pcap-Encoder,
NetMamba, a retrained encoder, and any later candidate are judged by the same
contract. No candidate receives a rule change because another candidate
failed.

## 2. Claim boundary

The strongest fact available now is:

> On the pinned fit/select target universe, frozen E3 missingness is dominated
> by frontend input semantics, especially non-TCP/UDP coverage and absence of
> an IP five-tuple session key.

This does **not** establish that missingness caused the hydraulic false-positive
rate, that higher encodability improves OOD detection, or that any replacement
frontend preserves attack recall. Those are later, separately gated questions.

## 3. Non-negotiable target and data contract

### 3.1 Full target universe

The challenger must emit exactly one status row for every one of the 25,467
frozen target UIDs. Each row is either:

- a finite, fixed-width representation; or
- `missing=true` with one literal reason from a dictionary frozen before real
  challenger outputs are opened.

No UID may be silently dropped, deduplicated, reassigned to another role, or
removed because its protocol/session shape is inconvenient.

### 3.2 No narrow-support escape hatch

Step-0b decoded every target through its exact inclusive cutoff and found zero
non-finite target timestamps. For this challenge, the mandatory protocol/event
support matrix is therefore the **entire observed 25,467-target universe**, not
only a candidate-selected TCP/UDP subset.

A challenger may document protocols outside the present corpus as out of
scope, but it may not exclude any observed target from the denominator by
declaring that target's protocol unsupported. Unsupported observed targets
remain ordinary missing failures in all availability gates.

### 3.3 Data isolation

- Only already legal fit/select packet prefixes may be used for compatibility,
  availability, geometry, or later head development.
- Report, FINAL, cooler-motor, and any other sealed role remain unopened.
- Labels, roles, source names, device names, member paths, and target UIDs may
  be used for audit joins only; they are forbidden frontend input features.
- No report/viewed outcome may choose a parser, session rule, tokenizer,
  checkpoint, representation dimension, or fallback policy.

## 4. Required frontend capabilities

### R1 — declared packet/event coverage

Before opening challenger outputs, the implementation must publish a literal
support matrix covering at least:

- IPv4 and IPv6 TCP;
- IPv4 and IPv6 UDP;
- IP protocols without transport ports, including the observed ICMP/GRE attack
  cases; and
- observed non-IP or otherwise five-tuple-ineligible packet events through a
  deterministic event-native fallback.

The matrix must state the decoder fields required, missing behavior, and
whether raw bytes, link-layer endpoints, network-layer endpoints, transport
endpoints, direction, length, and timestamp are consumed. A broad opaque-byte
fallback is allowed only if its causal unit and identity-leakage controls are
also frozen.

### R2 — keyless-event causal context

The frontend must define a deterministic context hierarchy that does not
require TCP/UDP ports for every event. It may use protocol-native flows,
endpoint-pair contexts, or a bounded member-local event context, but the exact
hierarchy must be frozen before real outputs.

The hierarchy must satisfy all of the following:

1. it uses only information at or before the target cutoff;
2. it never collapses all keyless traffic in a capture into one unbounded
   pseudo-session;
3. it never turns every keyless packet into a degenerate one-packet session
   merely to pass the availability gate;
4. state resets at frozen member/source boundaries;
5. its state and memory are explicitly bounded; and
6. changing a future packet leaves every earlier target representation
   byte-identical.

If a candidate requires a different semantic unit than a network session, the
output must call it `causal_context_id`, not mislabel it as a five-tuple
session. Device/session/record denominators remain separately reported.

### R3 — causal timestamp-regression handling

A negative decoded timestamp delta may not permanently poison the current and
all later targets into `missing=true`. The challenger must preregister one
global, device-agnostic causal policy, for example capture-order ordinal time,
a past-only monotone surrogate, or a bounded causal reset with an explicit
regression indicator.

The policy must:

- never reorder using future packets;
- never use a later timestamp to revise an earlier representation;
- expose the regression flag/count in the audit output;
- apply identically to benign and attack traffic; and
- preserve a finite target representation unless raw input is corrupt or the
  frozen decoder itself fails.

The exact policy is candidate-specific and must be frozen before execution.

### R4 — deterministic terminal representation

For a pinned checkpoint/configuration and packet prefix, repeated runs must
produce byte-identical finite/missing status and numerically deterministic
representations within a preregistered tolerance. Output width, pooling rule,
maximum context, truncation direction, tokenizer, padding, and fallback
behavior are immutable within a run.

### R5 — identity-leakage resistance

Raw addresses, hardware identifiers, protocol identifiers, and capture-local
ordering may carry device identity. Their use is not silently forbidden, but
must be declared and challenged through:

- the frozen shallow-header control;
- leave-one-device-out geometry;
- equal-device/equal-session weighting; and
- a feature ablation or masking audit frozen before learned-head results.

Beating netFound only by encoding a device fingerprint is not a frontend
advance.

### R6 — complete missingness accountability

Every candidate must ship a literal missing-reason dictionary. At minimum it
must distinguish:

- raw member absent/corrupt;
- decoder/schema failure;
- declared input genuinely unavailable;
- candidate resource/runtime failure; and
- scientifically unsupported event/context semantics.

Generic `UNENCODABLE` is forbidden. Per-device and per-exact-family finite
rates and reason counts, including zero rows, are mandatory.

## 5. Frozen measurement sequence

### Stage 0 — paper identity and feasibility, no embeddings

Pin before any real output:

- repository and license;
- checkpoint or separately authorized pretraining lineage;
- exact checkpoint SHA-256;
- pretraining-corpus overlap class;
- parser/decoder and runtime identities;
- support matrix and missing-reason dictionary;
- context hierarchy and timestamp-regression policy;
- output dimension and deterministic pooling;
- CPU/GPU/RAM/disk/runtime plan; and
- Python 3.9 plus target-platform compatibility.

Absence of a pinnable checkpoint remains
`F0_NO_USABLE_OFFICIAL_CHECKPOINT`. It does not authorize silent checkpoint
substitution or pretraining.

### Stage 1 — count-only availability

Run on the complete frozen 25,467-target universe, before representation values
or labels are consumed by a learned method. Reuse the already frozen absolute
gates:

```text
overall finite rate >= 0.90
every fit-benign device finite rate >= 0.80
every exact attack family finite rate >= 0.80
```

Because the current challenge mandates the whole observed protocol/event
universe, these denominators may not be narrowed by a support declaration.
All devices and families are reported individually; macro averages cannot hide
a failed group.

### Stage 2 — encoder-only measurement

Only a Stage-1 PASS may open representation arrays. Apply the frozen
Cross-Frontend Measurement Instrument without changing its geometry gates:

- count-only rank feasibility before arrays;
- causal early/late stability;
- leave-one-device-out projection distance;
- principal-angle stability;
- fit-only attack-information canary; and
- mandatory shallow-header control.

NetFound is the pinned reference baseline, not a success threshold substitute.
A relative improvement that misses an absolute guard remains NO-GO.

### Stage 3 — head-bound measurement

Only a Stage-2 encoder-only PASS and separate user authorization permit head
training. Train the same frozen P2 method contract from scratch in challenger
coordinates. Old netFound weights or gradients are forbidden. Recompute
equal-family attack protection and name every unprotected family.

### Stage 4 — performance attribution

Performance evaluation is outside this requirements draft. It requires a new
FROZEN protocol and must preserve the current zero-shot baseline, per-device
OOD FPR, global/unseen-device attack recall, exact-family recall, and the
report/FINAL one-shot boundary.

## 6. Mandatory causality and anti-degeneracy tests

Before real execution, the implementation test suite must include at least:

1. mutate packets after a target; the earlier representation is unchanged;
2. timestamp regression before a target yields the preregistered causal policy,
   not permanent silent missingness;
3. timestamp regression after a target cannot affect that target;
4. an ICMP target and a GRE target receive finite deterministic contexts;
5. a non-IP/five-tuple-ineligible target receives a bounded deterministic
   context;
6. unrelated keyless event streams are not merged into one global state;
7. repeated keyless events are not forced into per-packet singleton contexts;
8. member/source boundaries clear all state;
9. every expected UID survives output readback exactly once;
10. missing-reason rows conserve the full target count;
11. labels/source names/member paths cannot enter model tensors; and
12. Python 3.9 syntax and runtime API gates pass on the actual execution host.

Synthetic tests prove contract behavior, not scientific performance.

## 7. Stop states

The following terminal states are literal and non-promotional:

```text
FRONTEND_REQUIREMENTS_IDENTITY_FAILURE
FRONTEND_INPUT_SEMANTICS_NO_GO
FRONTEND_CAUSALITY_NO_GO
FRONTEND_RESOURCE_NO_GO
F0_NO_USABLE_OFFICIAL_CHECKPOINT
F0_LINEAGE_OR_LICENSE_NO_GO
F0_INSUFFICIENT_ENCODABILITY
F0_DEVICE_GEOMETRY_NO_GO
F0_ATTACK_INFORMATION_NO_GO
F0_HEADER_CONTROL_NOT_BEATEN
F0_ENCODER_ONLY_PASS
F1_ATTACK_PROTECTION_NO_GO
F1_FRONTEND_CHALLENGE_PASS
```

No failed state authorizes a second model, a relaxed support matrix, a changed
context hierarchy, a lower availability threshold, or a new family-specific
patch. Any backup activation must already be preregistered and may occur only
for an engineering incompatibility, never after scientific failure.

## 8. Required durable outputs for any challenger

1. immutable input/checkpoint/runtime identity manifest;
2. protocol/event support matrix;
3. context/sessionization contract;
4. timestamp-regression policy and audit;
5. target-level availability table;
6. per-device and per-family availability/reason tables;
7. resource measurements and checkpoint/resume audit;
8. Stage-2 geometry/canary/header-control results if authorized;
9. all applicable terminal verdicts; and
10. `SHA256SUMS` covering every result artifact.

## 9. Open review questions

Kimi is asked to decide the following before freezing:

1. **Full-universe mandate:** confirm that all 25,467 successfully redecoded
   targets must remain in Stage-1 denominators, closing the narrow support
   declaration loophole.
2. **Keyless fallback boundary:** confirm that the six R2 constraints are
   sufficient to permit candidate-specific context hierarchies without
   prescribing one model architecture.
3. **Regression requirement:** confirm that a timestamp regression must remain
   representable under a frozen causal policy rather than being allowed as an
   ordinary missing reason.
4. **Availability gates:** confirm reuse of 0.90 / 0.80 / 0.80 on the full
   universe, including small exact-family denominators.
5. **Identity-leakage audit:** decide whether the Stage-2 shallow-header control
   plus a preregistered masking/ablation audit is sufficient, or whether raw
   endpoint identifiers must be forbidden categorically.
6. **Candidate ordering:** confirm that Pcap-Encoder's checkpoint blocker and
   NetMamba's sealed state remain unchanged; this requirements freeze does not
   select or activate either candidate.

## 10. Authorization boundary

This DRAFT authorizes only independent design review and mechanical revision.
It authorizes no code, checkpoint retrieval, network access, model selection,
pretraining, PCAP decode, representation generation, head training, score
opening, report/FINAL access, HPC submission, or performance claim.

After review, a FROZEN requirements document and SHA-256 sidecar are required.
Candidate intake, implementation, and each execution stage then require their
own explicit authorization.
