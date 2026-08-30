# Frontend-F0 Step-0b causal re-decode result

- Date: 2026-08-30
- Branch: `codex/exp-mainline`
- Execution preflight: `732299c`
- Reviewed implementation: `d65f705`
- Independent implementation review: `727bbda` (`PASS`)
- Frozen protocol SHA-256: `ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794`
- Execution environment: local Windows, Python 3.9, TShark 4.6.6
- Runtime: approximately 30 minutes, member-atomic and internet-independent

## Result

**Terminal state: `MIXED_MISSINGNESS_MECHANISMS`.**

The real R1-R4 run decoded all 30 reviewed packet members through their exact
inclusive target cutoffs.  All 25,467 reconstructed target missingness values
matched the frozen availability artifact exactly.

| Quantity | Result |
|---|---:|
| Targets | 25,467 |
| Exact missingness matches | 25,467 / 25,467 |
| Missing targets | 11,640 |
| Finite targets | 13,827 |
| Independent sessions | 8,464 |
| Devices | 8 |
| Packet members opened | 30 |
| Report / FINAL / model / score / training opens | 0 / 0 / 0 / 0 / 0 |

The generated `SHA256SUMS` covers 11 required result artifacts.  All 11 hashes
were independently recomputed after execution with zero mismatch.  The
Python-3.9 contract battery also passed 32/32 immediately before execution.

## Exact missingness-cause topology

Primitive predicates use any-true semantics and therefore overlap.

| Predicate / descriptive primary reason | Any-true missing targets | Primary-reason targets |
|---|---:|---:|
| `UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP` | 11,605 | 1,988 |
| `NO_IP_SESSION_KEY` | 9,605 | 9,605 |
| `SESSION_TIMESTAMP_REGRESSION` | 47 | 47 |
| `NONFINITE_TARGET_TIMESTAMP` | 0 | 0 |

The exact boolean-pattern decomposition is:

| Predicate pattern | Targets |
|---|---:|
| no session key + unsupported protocol | 9,605 |
| session key present + unsupported protocol | 1,988 |
| timestamp regression only | 35 |
| timestamp regression + unsupported protocol | 12 |

## Benign-versus-attack descriptive split

Labels were joined only after the exact R3 equivalence gate.  They did not
participate in decoding or attribution.

| Role | Targets | Missing | Missing rate | Main topology |
|---|---:|---:|---:|---|
| Benign | 21,013 | 11,478 | 54.62% | 100% unsupported-protocol; 9,605 also lack a session key |
| Attack | 4,454 | 162 | 3.64% | 127 unsupported-protocol; 47 timestamp regression |

The 162 missing attack targets belong to five families: Mirai GRE flooding
(70), Merlin ICMP flooding (51), Merlin C&C communication (32), Mirai UDP
flooding (6), and File Download (3).  No non-finite timestamp target was
observed.

## Scientific interpretation

This is a positive diagnosis but not a detection-performance result.

1. The missingness is not attributable to a single tunable resource or a
   threshold.  A configuration-only re-encode proposal is not supported.
2. The dominant benign blind spot is mechanically tied to frontend input
   semantics: protocol support and session-key construction.  Every missing
   benign target activates the unsupported-protocol predicate, and most also
   lack a session key.
3. A challenger frontend now has concrete requirements: explicitly declared
   protocol coverage beyond the frozen TCP/UDP path, a session representation
   for currently keyless events, causal handling of timestamp regression, and
   per-device/per-family encodability reporting.
4. Fixing encodability does not by itself prove lower OOD false positives or
   preserved attack recall.  Any challenger must still pass the separately
   frozen availability and geometry instruments before performance evaluation.

The maximum claim remains the missingness-cause topology of the pinned
frozen-E3 fit/select terminal-target universe.  No report, FINAL, deployment,
or performance claim is made.
