# CKDE-R D0 + CKDE-Q Stage A — Kimi independent result review

**Date:** 2026-08-26
**Reviewed:** `3bf093e` (implementation), `dccf90f` (results)
**Reviewer:** Kimi

## Verdict: BOTH RESULTS INDEPENDENTLY REPRODUCED — closures accepted; one structural discovery added

## 1. CKDE-R D0 — state A reproduced

- SHA256SUMS 6/6 PASS.
- Verdict JSON: 5 attack devices, each with exactly **0** causally-prior same-device fit-benign
  sessions; 15 fit-benign devices / 11,409 benign records exist but none co-located with any
  attack device; no 2×2 device-family cycle; all four Audit-0 reason codes present.
- Role/open audit: `embedding_arrays_opened=0`, fail-closed before embeddings exactly as the
  FROZEN state machine requires; support-val/report/FINAL/PCAP/training all zero.
- Accepted as a **data-identifiability result**, not a method failure: representation
  commissioning is unanswerable with current legal evidence, and no viewed/report/FINAL data may
  patch the gap. CKDE-R closes cleanly.

## 2. CKDE-Q Stage A — fallback verdict reproduced, plus a structural discovery

- SHA256SUMS 7/7 PASS. Manifest recomputation: 161 rows = 23 baseline + 123
  `CAP_EXCEEDED_ZERO_SHOT` + 15 `INSUFFICIENT_SESSION_BUDGET_ZERO_SHOT`; `accepted_delta` is
  exactly 0 on every row; every applied threshold equals `theta_0`; all 123 requested deltas
  exceed the cap; suffix outcomes never opened (`stage_b_authorized=false` — correct, since zero
  method difference exists to evaluate).

**Discovery from my recomputation — the failure margin is exactly one ULP, everywhere:**

- All 123 requested deltas are identical: `1.102e-08 = cap + 1 ULP`;
- every device's prefix quantile lands at `q_raw = nextafter(T_cap)`, i.e., the 95th-percentile
  benign session score **is the same numerical value as the weakest fit-attack score**;
- the one-ULP excess is produced by the frozen `nextafter` tie-break on top of that coincidence.

This must not be read as "calibration almost worked". The correct reading is sharper and more
valuable: **at P2's operating point, the benign session-score tail and the attack-score floor
occupy the same quantized value.** There is no score margin to give back — the two distributions
touch at the threshold by construction (the threshold was selected at the attack floor). This is
the deepest evidence yet for the conclusion already forming across CKDE-Q and Stage-P:
capability for new devices cannot come from moving or per-device rescaling of this score; it
must come from score *structure* (representation or margin), which the current data cannot
support either (CKDE-R state A). The 1-ULP detail should appear in the paper's negative-results
narrative precisely because it preempts the reviewer question "would a slightly looser cap have
worked?" — the answer is no, the distributions coincide.

## 3. Project state after these closures

| Route | State |
|---|---|
| CKDB external corpora | closed (no legal three-domain mix) |
| CKDC fusion | closed (Option A vacuous; evidence families systematically opposed) |
| CKDD attack-head retraining | closed (no identifiable source-disjoint split) |
| CKDE-Q threshold calibration | closed (zero score margin; 23/23 fallback, archived) |
| CKDE-R representation calibration | closed (no same-device pairing; unidentifiable) |
| **Remaining live items** | **paper consolidation; CKDA D1 formal HPC replay; FINAL-gated one-shot confirmation design** |

Five routes, five clean, evidence-backed closures. The positive core that survives: CKDA D1's
attack-side results (97.37% / 96.68%, pending HPC replay), the hydraulic session-class
diagnosis, and a negative-results chain that systematically eliminates every post-hoc repair
family (fusion, retraining, threshold calibration, representation calibration) with named
mechanisms. That is a coherent paper: open-world detection attack-side advances plus a rigorous
account of where the information ceiling lies for zero-shot cross-device benign normality.

## 4. Standing boundaries

FINAL sealed; no route reopens without new preregistration and new evidence; CKDA D1 formal HPC
replay pending cluster recovery.
