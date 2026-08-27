# CKDE-S Lane G r2 — Kimi Result Terminal Review (Route Sealed)

- Reviewer: Kimi
- Date: 2026-08-27
- Result report: `runs/mainline_docs/ckde_s_d0_lane_g_r2_real_execution_result_20260827.md` (commit `5bfd8f9`)
- Output namespace: `runs/issue27ckde_s_d0_lane_g_geometry_audit_v1_2026-08-27_r2_localwin_cpu`
- Verdict: **RESULT REVIEW PASS — G1 confirmed by independent recomputation. CKDE-S is
  formally sealed as `CKDE_S_NO_GO_INTERNAL_GEOMETRY`. Lane M is cancelled as
  scientifically unnecessary.**

## 1. Integrity verification

- SHA256SUMS: **13/13 independently recomputed and matched** (my own `sha256sum -c`).
- Verdict JSON conforms to the frozen claim contract: exact `claim_scope` sentence, both
  excluded devices named verbatim, 5 protected / 7 unprotected families with the literal
  `UNPROTECTED_BY_REPRESENTATION_EVIDENCE` status, device/session/record denominators
  separated, `rank_retry_permitted=false`, `lane_m_authorized=false`.
- Boundary counters clean: network 0, pcap 0, support_val 0, report 0, FINAL 0,
  training 0. Open counters consistent with the executed stages
  (uid/missing=1, representation=1, probe=1).
- First run's engineering-failure namespace preserved; r2 used a fresh namespace; no
  evidence overwritten.
- Pre-run regression gate 41/41 PASS (already independently reproduced by me at
  `a397626`).

## 2. Independent scientific recomputation

I re-derived the complete G1 chain from the pinned artifacts with an independent script
(frozen math only, no gate changes). **Every value reproduces exactly:**

| Quantity | Codex | Kimi recomputation | Match |
|---|---:|---:|:--:|
| D_finite / r_finite | 13 / 4 | 13 / 4 | YES |
| Excluded devices | `iotsim-...-tls-1_0`, `normal_1.pcap` | identical pair | YES |
| median projection distance | 0.1565 (max 0.20) | 0.1565 | YES |
| worst projection distance | 0.5757 (max 0.35) | 0.5757 | YES |
| median principal angle | 18.2386° (max 20°) | 18.2386° | YES |
| worst principal angle | 89.3635° (max 35°) | 89.3635° | YES |
| worst held-out device | `iotsim-building-monitor-...-28_5-0` | identical | YES |
| median between/within R | 8.4643 (min 2.0) | 8.4643 | YES |
| devices with R ≥ 1 | 13/13 (need 11) | 13/13 | YES |

The per-device stability table shows the failing device carries **360 independent
sessions** — this is a well-supported structural failure, not small-sample noise.

## 3. What the result establishes (and what it does not)

Established, within the frozen claim scope ("geometry of the encodable
(`missing=false`) subset of the frozen fit pool"):

1. **Device identity is strongly structured, not temporal drift.** Median R = 8.46 with
   13/13 devices ≥ 1: between-device displacement dominates within-device causal
   early/late drift by an order of magnitude. The earlier suspicion that 256-packet
   windows or temporal accumulation caused the device problem is falsified again, now at
   representation level.
2. **But the structure is not globally low-rank.** The median device is stable under
   leave-one-device-out (0.1565 / 18.2°, both PASS), yet one well-supported device's
   shift direction sits ~89° from the rank-4 subspace learned from the rest. Device
   nuisance directions are partially idiosyncratic; no shared frozen-rank subspace
   covers every device. A global "learn once, subtract everywhere" correction cannot be
   certified on this representation.
3. **The worst-device guard did its job.** The same anti-averaging discipline that
   stopped CKDA D1's hydraulic pool from being hidden by a macro number has now stopped
   a median-passing subspace from being promoted. This is the frozen contract working as
   designed, and I will not entertain relaxing it after observation.

Not established (claim boundaries):

- The negative covers the **frozen method** (rank by the count-only rule = 4, equal
  weighting, this representation). It does not prove that no subspace of any rank or any
  re-weighting could be stable; exploring those would be post-observation rank/gate
  shopping and is forbidden under this route.
- No G2–G4 evidence exists: the run stopped before attack-gradient geometry, and no
  protection-space claim is made in either direction.

## 4. Ruling on the joint state machine

Per the frozen lattice, `Lane G ≠ G4` → `CKDE_S_NO_GO_INTERNAL_GEOMETRY`. I confirm:

- **CKDE-S is formally sealed.** No retry, no rank change, no device exclusion, no
  constant adjustment.
- **Lane M is cancelled, not merely paused.** Its purpose was to source paired external
  data for validating a commissioning mechanism. D0 has now shown the mechanism's
  internal geometric premise (a stable global device-nuisance subspace) does not hold on
  the frozen representation. Running Lane M now would spend external-data budget to
  rescue a mechanism that cannot be rescued, which is outcome-driven continuation. The
  N-BaIoT/CICIoT metadata reconnaissance therefore does not proceed under CKDE-S.

## 5. Convergent-negatives record (for the research log)

CKDE-S is the **third independent structural negative** on post-hoc correction of the
frozen E3/P2 stack for cross-device benign robustness:

1. **CKDE-Q** (score-level calibration): safety cap 1.1e-08 — benign tail and attack
   floor coincide; 23/23 devices, 123/123 arms fell back. No score-level room.
2. **CKDE-R** (representation adaptation): state A — zero attack devices have
   pre-attack benign centers; adaptation unidentifiable.
3. **CKDE-S** (subspace removal): G1 — device nuisance is real and dominant but not
   globally low-rank; one 360-session device is ~orthogonal to the shared subspace.

Together with CKDB (no legal corpus mix), CKDC (no fusion certificate), and CKDD (no
retraining feasibility), the correction-design space on the current representation is
now exhaustively closed with pre-registered, independently recomputed evidence. The
implication for the next design round is substantive, not merely negative: **the
limitation sits in the representation/data layer itself** (including the encoder's
device/family-structured encodability — 6,424 whole-session-missing sessions), not in
any post-hoc geometry, threshold, fusion, or retraining scheme. Any future route must
change the input layer (representation, commissioning data, or detector architecture)
rather than correct its outputs, and must be argued against this six-route evidence
base before implementation.

## 6. Sealed items and authorizations

- CKDE-S: **sealed** (`CKDE_S_NO_GO_INTERNAL_GEOMETRY`).
- Lane M: **cancelled** under CKDE-S; any future external-corpus idea requires a new
  route, new pre-registration, and fresh user authorization.
- CKDA D1 attack-side results (97.37% / 96.68% local), the hydraulic mechanism
  diagnosis, and the HPC replay obligation are unaffected and stand as recorded.
- FINAL, report, training, HPC, network: remain sealed. No further execution is
  authorized under CKDE-S.
