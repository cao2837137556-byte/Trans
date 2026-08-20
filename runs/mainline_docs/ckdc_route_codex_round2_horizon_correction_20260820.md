# CKDC route discussion — Codex round 2 horizon correction

Date: 2026-08-20

Author: Codex (implementation/design side)

Status: `FACTUAL_CORRECTION_BEFORE_D0_FREEZE`

## Outcome first

The previous CKDC discussion used "the 256-packet representation" as the H1
premise. That premise conflates the unexecuted I1 candidate with the E3
candidate that actually produced the CKDA D1 P2 result. It must be corrected
before CKDC D0 is frozen.

The local CKDA D1 result under discussion is E3/P2. Its exact frozen E3 input is
not the I1 current-inclusive last-256-packet prefix.

## Exact lineage

The CKDA D1 FROZEN contract defines:

- I1: a current-inclusive maximum of the most recent 256 packets;
- E3: the D0-pinned official netFound preprocessing and checkpoint.

I1 did not train because its benign-corpus gate failed. The state machine then
advanced to E3, and E3/P2 produced the 97.37% global and 96.68% future-query
attack recall result.

The SHA-pinned E3 implementation uses this causal content budget at target time:

1. group session packets into direction-specific bursts separated by more than
   10 ms;
2. merge bursts by their first timestamp and retain the earliest 12 bursts;
3. retain at most the first 6 packets of each retained burst;
4. expose at most 72 packet-content records to netFound;
5. separately expose `flow_duration`, computed from the first timestamp through
   the latest causally observed session timestamp.

The streaming state may temporarily hold up to 12 bursts per direction, but
the final `netfound_flow` transformation sorts both directions together and
keeps only the earliest 12. Later packets can still extend `flow_duration`, but
their packet content, direction sequence, byte totals, and later-burst
structure are excluded after the burst budget is full.

## Corrected H1

The supported hypothesis is not:

> E3 failed because a 256-packet window is shorter than hydraulic's median 662
> packets.

The corrected hypothesis is:

> E3 may fail because its early-burst content budget discards later causal
> structure in packet-dense long sessions; total elapsed duration remains
> visible, so duration absence alone cannot explain the failure.

This distinction matters. Hydraulic may be misclassified because:

- the earliest burst content itself resembles attack traffic;
- later polling/cyclic behavior that proves normality is discarded;
- the duration scalar is visible but insufficient;
- or representation horizon is not the dominant cause at all.

## Required change to CKDC D0

The H1 diagnostic must now audit the exact E3 truncation mechanism before any
alternate representation is implemented:

1. per-target total causal packet count;
2. total causal burst count under the frozen 10 ms rule;
3. retained burst count and retained packet count;
4. discarded packet and discarded burst fractions;
5. whether later causal direction transitions, polling cycles, and byte mass
   are excluded;
6. the already visible total-duration scalar.

These descriptors must first be defined and computed on legal fit/select roles.
VIEWED hydraulic rows may receive the same frozen descriptive readout only
after the implementation identity and bins are fixed. They may not select an
alternate burst budget, packet limit, pooling rule, or horizon.

If a paired representation audit is later authorized, its control arm is the
exact frozen E3 early-burst representation. The alternate arm must differ in
one declared dimension: it may add a fixed causal accumulated summary of later
events, but it may not simultaneously change encoder, loss, threshold, and
fusion structure.

## Effect on the M7 proposal

This correction does not weaken the reason to audit M7. M7 uses a distinct
51-dimensional source-local past-only process state and may carry later-history
normality evidence that E3 discards. It does, however, prevent us from calling
the comparison a simple 256-versus-full-history test. M7 and E3 differ in both
feature view and scoring mechanism, so M7's hydraulic behavior is evidence for
an information-view conflict, not a clean horizon ablation by itself.

No experiment, threshold, model, or FINAL asset is authorized by this factual
correction.
