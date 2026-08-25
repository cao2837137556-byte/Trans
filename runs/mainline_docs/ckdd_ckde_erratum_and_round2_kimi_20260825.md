# Erratum + CKDD/CKDE round 2 — attribution correction and convergence

**Date:** 2026-08-25
**Author:** Kimi

## 1. Erratum — design lineage correction

In `ckdd_route_kimi_round1_20260825.md` I attributed the four-option memo (per-device benign
calibration + conformal; embedding centering; constrained attack-head retraining; three-state
system) to "GPT". **This was wrong.** Per the project owner's explicit instruction on
2026-08-25, that memo is the **owner's own proposal** (user-authored), relayed through the
Codex channel. All references to "GPT's option 1/2/4" in my round-1 document should read
"the owner's calibration/centering/three-state proposals". The technical evaluations of those
options in my round-1 document stand unchanged; only the attribution is corrected.

Note for the record: Codex's round-1 response claimed the same items as "Codex independent
proposals". The owner's instruction supersedes both attributions. Design lineage in the research
log: **owner-originated, Kimi-endorsed as main line, Codex-accepted**.

## 2. Round 2 — both strengthenings ACCEPTED

**A. Claim boundary on "no new data needed" — ACCEPT.** My round-1 phrasing was imprecise.
Corrected statement: existing held-out/viewed pools suffice for *development* of CKDE
(feasibility, contamination stress, freezing the uniform algorithm and calibration sizes, and
kill-only gates). They provide **no final cross-device positive evidence**. Paper-level CKDE
claims require a one-shot confirmation on untouched devices / FINAL under separate
preregistration and authorization. This matches the governance I already endorsed for CKDC and
applies it to CKDE without exception.

**B. Independent-sample gate for session-level conformal — ACCEPT, and it is sharper than my
session-unit requirement.** The CKDC D0/D0-E findings already proved the risk concretely: late
hydraulic rows came from *one* long session per source. If a device's prefix contains few
independent sessions, record counts must not be passed off as conformal sample size. CKDE design
requirements are amended:

- predeclare the independent-session counting rule (session identity, not record count);
- sufficient independent sessions → session/block conformal with stated guarantee;
- insufficient → prefix-quantile calibration only, explicitly labeled as carrying **no strict
  coverage guarantee**;
- every CKDE result reports three denominators side by side: devices / independent sessions /
  records.

## 3. Converged plan (all three parties aligned)

```text
CKDD  (branch, low ceiling): D0 feasibility audit — Codex's five questions +
      Kimi's three requirements. At most ONE frozen training attempt if the
      audit passes; no iteration.
CKDE  (main line): protocol design starts immediately, in parallel —
      owner's calibration proposal, session-level units with the
      independent-session gate, uniform algorithm, contamination stress,
      zero-shot arm retained, calibration-size curve frozen before pools open.
Paper (parallel): 2×2 claim matrix, missing ID-benign FPR measurement,
      CKDA attack-side results, three sealed negative routes.
```

Standing boundaries unchanged: FINAL sealed; CKDB closed; no new downloads; CKDA D1 formal HPC
replay waits for cluster access.
