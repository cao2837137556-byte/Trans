# CKDC D0-E longest-session mechanism — implementation and result

**Date:** 2026-08-20

**Protocol SHA-256:** `68a44073187bad6391affca4255998e48ed5a9a84f1292341ff556643eb3de88`
**Execution:** local, report-descriptive only, no PCAP, no training, no FINAL

## 1. Validation

Added:

- `repo/ood/issue27ckdc_d0e_long_session_mechanism_v1.py`
- `repo/ood/issue27ckdc_d0e_long_session_contract_tests_v1.py`

Contract suite: **14/14 PASS**, including Python 3.9 grammar, metadata-only longest-session
selection, deterministic tie handling, the 65-target support gate, all three classifications,
stable causal order, FINAL fail-closed, and no replacement of existing outputs.

The execution joined exactly 3,000 hydraulic P2 rows to immutable session metadata.  Five
longest sessions were selected using target count and session-ID tie-break only; no score or hard
state participated in selection.  Output `SHA256SUMS` verifies 4/4 result members.

## 2. Result

All five source groups receive `SESSION_CLASS_CONFLICT`:

| source | longest-session targets | ordinal-1 P2 score | ordinal-1 hard | ordinal-65+ hard | first hard ordinal | M7 hard rows |
|---|---:|---:|---:|---:|---:|---:|
| hydraulic-12 | 455 | 0.957849 | yes | 100% | 1 | 0 |
| hydraulic-13 | 449 | 0.976179 | yes | 100% | 1 | 0 |
| hydraulic-14 | 450 | 0.972933 | yes | 100% | 1 | 0 |
| hydraulic-15 | 454 | 0.973518 | yes | 100% | 1 | 0 |
| hydraulic-2 | 455 | 0.959148 | yes | 100% | 1 | 0 |

Every selected session remains hard from its first target onward.  The mechanical verdict is:

`SESSION_CLASS_SIGNAL`

## 3. Interpretation

The parent aggregate (early ordinal about 5%-7% hard versus late ordinal 100% hard) was a session
composition effect.  Each source contains many short sessions that P2 mostly treats as normal and
one long session type that P2 treats as attack from its first observable target.  There is no
evidence here that P2 crosses into the attack region only after accumulating a long history.

Therefore:

1. **Do not advance a longer-window fix.**  The observed failure exists at ordinal 1, before
   later-session content could rescue a causal prefix.
2. **Retain the domain/session-class diagnosis.**  E3/P2 and C1 consistently treat this session
   type as attack-like, while M7 consistently supplies normality-side evidence.
3. **Do not train the obvious fusion.**  Parent D0 showed zero legal select attacks in the
   `P2 hard / M7 normal` quadrant, so the current split cannot validate when trusting M7 would
   suppress a real attack.
4. **Do not reopen external-data acquisition.**  CKDB remains closed.

## 4. What this changes

CKDC is no longer a generic time-scale route.  Any future system candidate must address a
session-class/domain conflict while preserving the 51,057 already-viewed attacks in the same
P2-hard/M7-normal report quadrant.  It needs fresh, legally independent conflict-attack support or
a predeclared one-shot confirmation on untouched evaluation material; the current select split
cannot supply that evidence.

This diagnosis does not authorize FINAL access.  Formal CKDA HPC replay remains independently
required when the cluster is available.
