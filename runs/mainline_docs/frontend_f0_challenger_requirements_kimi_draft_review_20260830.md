# Kimi Draft Review — Frontend-F0 Challenger Requirements

- Date: 2026-08-30
- Reviewer: Kimi (independent review role)
- Reviewed draft: `runs/mainline_docs/frontend_f0_challenger_requirements_draft_20260830.md`
- Reviewed commit: `532b2b6` (single-file commit, verified: only the draft was added)
- Basis: Step-0b result `41699ed`; result review `85bc105`

## Verdict

**DRAFT ACCEPTED — freeze authorized after three mandatory strengthenings
(S1, S2, S3) are mechanically incorporated.**

The draft faithfully converts the Step-0b topology into a challenger-neutral
requirements contract: full-universe denominators, joint protocol+keyless
semantics, causal regression handling, count-only gates before arrays,
encoder-only geometry before head training, and unchanged candidate
blocker/seal states. The six open questions are ruled below. The three
strengthenings are mechanical additions; they change no threshold, no stage
order, and no candidate state.

## Rulings on the six open questions (§9)

### Q1 — Full-universe mandate: **ACCEPT**

All 25,467 redecoded targets stay in every Stage-1 denominator; declaring an
observed target's protocol unsupported may not narrow any denominator. The
draft's factual premise is verified: Step-0b decoded all 25,467 targets
through their exact cutoffs and found zero non-finite target timestamps, so no
observed target has a legitimate "input unavailable" exemption. The
narrow-support escape hatch is correctly closed.

### Q2 — Keyless fallback boundary: **ACCEPT with strengthening S1**

The six R2 constraints (cutoff-only information, no unbounded pseudo-session,
no forced singleton contexts, member/source state reset, bounded state,
future-packet invariance) are the right invariant set and are
architecture-neutral. One gap: constraints 2 and 3 are stated as prohibitions
whose violation is only visible through behavioral tests 6–7.

**S1 (mandatory):** add to §8 (required durable outputs) a per-device and
per-exact-family **causal-context size distribution** (event counts per
`causal_context_id`: min/quartiles/max, plus the count of distinct contexts).
This makes both degenerate extremes — one capture-wide pseudo-session and
all-singleton contexts — mechanically auditable from outputs rather than
intent.

### Q3 — Regression requirement: **ACCEPT**

A timestamp regression must remain representable under a preregistered causal
policy (capture-order ordinal time, past-only monotone surrogate, or bounded
causal reset with explicit regression indicator); permanent poisoning into
`missing=true` is forbidden; the regression flag/count must appear in audit
output. Today's 47 regression targets are attack-only and few, but the
requirement is about declared behavior on future captures, not about these 47.
The old embedder's poison semantics are a documented design choice, not a law;
requiring a frozen alternative per candidate is the correct generalization.

### Q4 — Availability gates 0.90/0.80/0.80: **ACCEPT with strengthening S3**

Reviewer recomputed the exact denominators from the Step-0b per-target
artifact to confirm the gates are operable:

| Group | Denominator | Current finite rate | 0.80 gate allows |
|---|---:|---:|---:|
| Mirai C&C Communication (smallest family) | 11 | 100% | ≤2 missing |
| File Download | 18 | 83.3% | ≤3 missing |
| Merlin C&C Communication | 35 | 8.6% | ≤7 missing |
| Merlin ICMP Flooding | 51 | 0% | ≤10 missing |
| Mirai GRE Flooding | 70 | 0% | ≤14 missing |
| Fit-benign devices (5) | 600–4,000 | 21.1%–70.3% | — |
| Overall | 25,467 | 54.3% | ≥0.90 required |

The gates are coarse for the 11-target family (one target = 9.1pp) but
fail-closed, and they directly force coverage of the two families the frozen
frontend misses entirely (GRE, ICMP) plus the benign devices where it reaches
at most 70.3%. Keeping the inherited gate triple preserves continuity with the
frozen measurement instrument. Accepted.

**S3 (mandatory):** the per-device 0.80 gate currently reads "every
fit-benign device". The frozen universe also contains select-side benign
devices (e.g., `city-power`, `combined-cycle`, `ip-camera-museum`). A
challenger passing all three inherited gates could still leave a select-side
benign device mostly unencodable, which would silently poison later OOD
evaluation on exactly that device. Extend the per-device gate to **every
benign device in the frozen 25,467-target universe, regardless of role**. This
is a scope correction of one gate, not a new threshold, and it follows
directly from the draft's own §3.2 no-narrowing principle.

### Q5 — Identity-leakage audit: **ACCEPT declaration-plus-controls; no categorical ban, with strengthening S2**

A categorical ban on raw endpoint identifiers is impractical (byte-level
decoders inherently observe addresses) and unnecessary if reliance is
measurable. The draft's control stack — shallow-header control, LODO
geometry, equal-device/equal-session weighting, and a preregistered
ablation/masking audit — is the right shape. One gap: "a feature ablation or
masking audit" is open-ended enough that a candidate could freeze an ablation
plan that never isolates endpoint identity.

**S2 (mandatory):** the preregistered ablation/masking plan must include, as
one mandatory arm, **raw endpoint-identifier masking** (addresses and hardware
identifiers normalized or removed) with downstream separability re-measured
under that arm. The audit design remains frozen before learned-head results;
the masking arm simply may not be absent from it.

### Q6 — Candidate ordering: **ACCEPT**

`F0_NO_USABLE_OFFICIAL_CHECKPOINT` for Pcap-Encoder and NetMamba's sealed
state remain unchanged. This requirements freeze selects and activates no
candidate; any future backup activation must be preregistered and limited to
engineering incompatibility, never post-hoc after scientific failure (§7,
verified consistent).

## Additional review findings (no change required)

1. Stage order (identity → count-only availability → encoder-only geometry →
   separately authorized head → later performance protocol) matches the
   reviewer position recorded in the Step-0b result review. Stage 3 correctly
   forbids old netFound weights/gradients and mandates same-contract
   retraining from scratch in challenger coordinates.
2. §3.3 forbids labels/roles/source/device/member/UID as frontend input
   features and forbids report/viewed outcomes from choosing any parser,
   session rule, tokenizer, checkpoint, dimension, or fallback policy — the
   viewed-data kill-only discipline correctly extends to frontend design
   choices.
3. R6's missing-reason dictionary correctly forbids generic `UNENCODABLE` and
   mandates zero-row reporting; this preserves Step-0b-grade accountability
   for every challenger.
4. Minor wording tension, non-blocking: R3 demands finite representation
   "unless raw input is corrupt or the frozen decoder itself fails", while R6
   lists "scientifically unsupported event/context semantics" as a missing
   reason. Since the regression policy is frozen per candidate before
   execution, which of the two applies will be unambiguous in practice.

## Required mechanics before freeze

1. Incorporate S1 (context-size distribution output), S2 (mandatory
   endpoint-masking ablation arm), S3 (per-device gate covers all benign
   devices) verbatim into the FROZEN document; no other scientific change.
2. Update §9 from open questions to these rulings.
3. Generate the FROZEN document plus SHA-256 sidecar and submit for reviewer
   SHA/diff freeze verification.

This review authorizes mechanical revision toward FROZEN only. It authorizes
no implementation, checkpoint retrieval, network access, decode, training, or
execution.
