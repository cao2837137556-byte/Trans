# CKDA D1 local L1 tail-reentry engineering failure and repair

Date: 2026-08-14  
Scope: local emergency L1 fit/select embedding only  
Scientific verdict: **none**  
Report opened: **no**

## 1. Observed failure

The reviewed local L1 launcher entered `e3_fit_select_embeddings` at
`2026-08-14T07:00:24Z` and terminated at `2026-08-14T07:28:09Z`.

The first member was the ToN-IoT `normal_1.pcap` fit member. Its discovery pass
completed the exact causal prefix of 1,999,922 packets and found all 4,000
selected targets. Before a member checkpoint was committed, the second pass
ended with:

```text
RuntimeError: local target session state not fully released
```

At failure:

- member checkpoints: 0;
- combined embeddings: absent;
- thresholds: not fitted or frozen;
- report assets and report labels: not opened;
- FINAL assets: not opened;
- scientific verdict: null.

This is therefore an engineering failure before any claim-producing result.

## 2. Root cause

The local memory-bounded adapter releases a session immediately after that
session's last selected target. The capture-level decoder must nevertheless
continue to the maximum selected target of every other session in the same
member.

The old condition retained any packet whose canonical session appeared in the
static `wanted` set. If a released session appeared again later as a non-target
packet, the packet recreated that session state. Since the session had no later
selected target, no later release event existed, and the final empty-state
assertion correctly failed.

The 32-target real equivalence canary did not contain this topology: its member
had only one retained target session and ended at that session's last target.

## 3. Minimal repair

The adapter now retains a packet only when both conditions hold:

1. its canonical session has a selected target in this member; and
2. the current packet position is not later than that session's last selected
   target position.

Formally, for session `s` and position `p`, state is retained iff
`s in last_target AND p <= last_target[s]`.

Packets after a session's final selected target cannot affect any requested
embedding. Ignoring them therefore changes memory lifetime only; it cannot
change a frozen target prefix, target order, batch order, checkpoint schema,
model, tokenizer, or score.

## 4. Permanent gates

- Added contract regression `test_36g_local_twopass_does_not_recreate_released_session_state`.
- The regression covers current-inclusive retention, post-cutoff exclusion,
  simultaneous activity of a different session, `None`, and an unrequested
  session.
- The launcher now writes a separate `local_embedding_attempt.txt` marker so an
  attempted L1 cannot be confused with the earlier L0 marker
  `embeddings_started=0`.

## 5. Verification

- Python compilation: PASS.
- CKDA D1 contract suite: **47/47 PASS**.
- Real frozen-vs-local equivalence canary: **PASS**, 32/32 targets.
- Maximum absolute representation delta: **0.0**.
- Frozen checkpoint SHA-256:
  `d1fe38bae2ee37f4eeecb5f799ea7cdcf4acb82295fcf9e8beccc6a03000e3ce`.
- Repaired local checkpoint SHA-256: identical to the frozen checkpoint.
- Round-6 representation digest: identical
  (`16925cc791d0b7e0df2a7b0fc93487cc00990bf3194b5a13b25b0f3d88743020`).

## 6. Authorization boundary

This document and the verification evidence authorize independent review of
the repair only. They do **not** authorize an automatic rerun.

After independent PASS, the same L1 scope may resume from zero completed member
checkpoints: 25,467 E3 fit/select embeddings, G0/P1/P2 probes, and threshold
freezing, stopping before report opening. L2 and any paper claim remain
separately gated.

