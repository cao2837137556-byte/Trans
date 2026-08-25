# CKDD D0 + CKDE D0 FROZEN — Kimi freeze final review

**Date:** 2026-08-25
**Reviewed:** commit `605dc54`
**Reviewer:** Kimi

## Verdict: BOTH FROZEN CONFIRMED — audits await user authorization

## Checks performed

**SHA-256 independently recomputed (both match sidecars and Codex's claims):**

- CKDD D0: `0c33a0eca009242238910dffa004b8cec1fedc39b5e77f0e1be05e5b7850eb7a` — PASS
- CKDE D0: `1f36d0dba81e676af1a2bd29436e4fdf90e85642301cf30a9ca09af751f823a1` — PASS

**M1 (CKDD kill-only widening) — textually confirmed:**

- §8: "all already-viewed report attack rows, regardless of their current P2/M7 quadrant";
- the 51,057 conflict-quadrant attacks are a named sub-denominator reported separately;
- any viewed attack flipping hard→normal closes the route;
- verbatim-diagnostics clause ("emitted verbatim regardless of whether it supports or opposes
  CKDD; no conditional rerun") is present and pinned in the test list.

**S1 (CKDE one-sided threshold) — textually confirmed:**

- §6 formula frozen: `theta_d = theta_zero_shot + delta_d`, `0 <= delta_d <= cap_fit_attack`;
- "Calibration may raise the device threshold only; it may never lower it";
- `cap_fit_attack` derived from the 4,385 legal fit attacks only, frozen **before** any
  support-val access; the 69 support-val rows are a one-time sentinel and cannot revise the cap;
- contamination grid includes 10% and the exactly-one-attack-record-per-session injection mode;
- session-max aggregator fixed;
- correctly scoped: only D0 (count-only) is frozen now; D1 session budgets and the numeric cap
  await D0 evidence — no pretending to freeze numbers that don't exist yet.

## Authorization state

- Both D0 audits: require the user's explicit authorization to implement and execute (local,
  read-only, no training, no report scores, no FINAL, no PCAP, no HPC).
- CKDD training: requires D0 GO + a separately frozen training protocol + separate user
  authorization. At most one attempt.
- CKDE D1: requires D0 results + separate freeze + separate authorization.
- CKDA D1 formal HPC replay: pending cluster access.
