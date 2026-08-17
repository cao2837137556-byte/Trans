# CKDB D0-P1 Kimi freeze verification — PASS

Date: 2026-08-17
Reviewer: Kimi
Target: `ckdb_d0_p1_external_metadata_audit_preregistered_20260817.md` (Codex commit `1316f9f`)

## Verdict: FREEZE PASS — protocol is FROZEN and executable-pending-user-authorization

## Independent verification

1. **SHA-256**: recomputed locally from the file bytes.
   `9e96ad2860f812595d51376bc7b0bc1c3ae30e264e1918c946750689d363a3ba`
   matches the sidecar exactly. PASS.
2. **R1 six-point incorporation** (required by review `117c93f`):
   - (a) Audit 5 gate counts **post-clustering** independent domains;
     repeated days of one device = 1, all roles of one simulator = 1
     (§5 Audit 5, "counted after Audit 4 clustering"). PASS.
   - (b) eligible industrial corpus but post-clustering count < 3 →
     `CKDB_D0_P1_PENDING_METADATA`, missing evidence fixed as
     `SECOND_INDUSTRIAL_PROCESS_CORPUS`. PASS.
   - (c) no eligible industrial corpus → `CKDB_D0_P1_NO_IDENTIFIABLE_CORPUS_MIX`.
     PASS.
   - (d) second industrial corpus is a pre-frozen deficiency remedy, not an
     arbitrary third candidate; requires own preregistration, same eight
     audits, no use of viewed hydraulic/CKDA outcomes for selection, and
     separate user authorization (§1 boundary + §5 Audit 5 remedy paragraph).
     PASS.
   - (e) CIC horizon/scale `PENDING_NO_SMALL_FLOW_METADATA` does not by
     itself block the Tier-A-based domain gate. PASS.
   - (f) UNSW `flows.zip` per-packet/payload disguise → full quarantine and
     recorded safety failure, no silent use (§2.1 Tier B). PASS.
3. **Four draft-question closures** recorded verbatim in §9 and consistent
   with review `117c93f`. PASS.
4. **No scope drift versus the reviewed draft**: tiers, byte caps, taxonomy,
   eight audits, fail-closed ordering, and the 18 contract tests are
   unchanged; additions are exactly the R1/Q1–Q4 closure text. PASS.
5. **Authorization boundary** (§9): the FROZEN document itself authorizes no
   implementation and no download. PASS.

## What this verification authorizes

- The user may now authorize **D0-P1 metadata-only execution** (Tier A
  objects for both candidates; Tier B only after Tier A gates pass), which
  Codex must implement under the frozen §8 contract tests and my
  implementation review.

This verification does **not** authorize: implementation before user
execution authorization, any PCAP/full-archive download, HPC submission,
training, embedding, threshold work, or FINAL contact.
