# CKDE D1 Stage-P cap materialization — Kimi independent review

**Date:** 2026-08-26
**Reviewed:** commit `16e0b3e` (Stage-P artifact + NUMERICAL FROZEN)
**Reviewer:** Kimi

## Verdict: VERIFICATION PASS — cap accepted as frozen; scientific consequence assessed below

## 1. Independent recomputation (from committed artifacts)

- r2 result `SHA256SUMS`: 6/6 PASS. `ckde_d1_cap.json` SHA matches the value pinned in the
  NUMERICAL FROZEN.
- **Frontier re-derived row by row (2,475 candidates):** admissibility flag = (global loss
  ≤ 0.5pp) AND (max eligible-family loss ≤ 2pp) — **0 mismatches** against my recomputation;
  frontier strictly ascending; exactly two admissible thresholds (`theta_0`, `T_cap`);
  third candidate `0.15963729500984128` loses 139 attacks (3.17pp) and 100% in some family.
- Arithmetic: `T_cap − theta_0 = 1.1019905904463556e-08` — exact match.
- Family table: 29,700 rows = 2,475 × 12 exact labels; all T_cap family losses = 0.0.
- Boundary audit: benign/support-val/report/FINAL scores opened = 0; training = 0; non-fit rows
  scored = 0. PASS.
- NUMERICAL FROZEN SHA = sidecar = claim (`0ec11fdf...8fb4`); diff vs PRE-CAP is exactly:
  status line, literal value block + artifact pinning, authorization boundary. Zero rule drift.
- **Duplicate directory note (non-blocking):** `..._local` and `..._local_r2` have byte-identical
  `cap.json` and input audits, so there is no scientific discrepancy; the official artifact is r2
  per the report. Codex should add one line to the record explaining the rerun cause (the
  no-replace rule makes a re-execution create a new directory) so the audit trail is self-describing.

## 2. Scientific assessment — the cap is telling us something important

The headroom `cap ≈ 1.1e-11` is one floating-point ULP above the lowest fit-attack score. The
frontier shows why: P2's weakest ~139 fit attacks (3.17%) score in a band immediately above
`theta_0` (next distinct score 0.1596). **P2's operating threshold sits at the floor of its own
attack-score distribution** — a direct consequence of selecting the threshold for maximum attack
recall. Score-space upward calibration therefore has essentially no room to move *within any
attack-safety trust region*, not just ours.

Structural consequence for Stage A (before any benign score is opened): a device can receive a
non-fallback calibrated threshold only if its prefix 95th-percentile session score lies inside
`[theta_0, theta_0 + 1.1e-11]` — a measure-zero band. Every device whose prefix quantile exceeds
that band (i.e., every device that actually needs calibration, hydraulic-style) will mechanically
receive `CAP_EXCEEDED_ZERO_SHOT`. The Q arm cannot repair the devices it was designed for.

## 3. Recommendation on Stage A

I recommend **still authorizing Stage A**, because it converts this analytic expectation into
documented per-device evidence at trivial cost, and two of its outputs remain informative
regardless:

1. the exact per-device fallback rate (the paper-grade statement "score-space calibration is
   empty for X/23 development devices");
2. the N1 within-device stability read on devices whose prefixes stay below `theta_0` (they tell
   us how large the never-miscalibrated population is).

If Stage A returns the expected near-total fallback, the honest CKDE-Q terminal state is
`CKDE_D1_NO_MATERIAL_BENIGN_GAIN` (or the fallback-dominated equivalent), and the finding to
carry into the paper is: **threshold-level commissioning cannot rescue a detector whose operating
point was chosen at the attack-score floor; new-device capability must come from score-margin
structure, not threshold movement** — which redirects the main line toward representation-level
calibration (the deferred arm C idea) or acceptance of the claim boundary, both requiring fresh
preregistration.

## 4. Standing boundaries

Stage A requires the user's explicit separate authorization. FINAL sealed; CKDB/CKDC/CKDD closed;
CKDA D1 HPC replay pending cluster access.
