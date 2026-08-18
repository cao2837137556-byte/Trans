# CKDB D0-P3 Kimi freeze verification — PASS

Date: 2026-08-18
Reviewer: Kimi
Target: `ckdb_d0_p3_combined_large_download_and_census_preregistered_20260818.md`
(Codex commit `c1540f1`)

## Verdict: FREEZE PASS — protocol is FROZEN; implementation may begin

## Independent verification

1. **SHA-256** recomputed from file bytes:
   `de864fdb54a071a4db082c79071188f1445c244cd5c05376a4ad4f191fade5a1` —
   matches the sidecar exactly. PASS.
2. **Full diff against the reviewed draft**: every change is the mechanical
   incorporation of review `0e67e45`; no unrelated drift. Specifically:
   - **R1 (Q6)**: §8 now freezes the four-point route consequence verbatim —
     uncloseable P0-B → CIC=0,
     `NO_IDENTIFIABLE_THREE_INDUSTRIAL_DOMAINS_CIC_IDENTITY_UNRESOLVED`;
     post-transfer §8 failure → CIC=0, `CIC_BENIGN_BOUNDARY_FAILURE_NO_USE`;
     either way industrial maximum is 2 < 3, D0-P3 terminates with the named
     scientific result, and no third/replacement corpus may be searched or
     substituted. Wired into the §12 state machine (S0/S3) and §15
     non-authorizations. PASS.
   - **Q1**: §2 converts P0-A–P0-C into appendix blockers — metadata-only,
     no object bodies, no transient URLs/cookies/tokens/form state, own
     SHA-256 sidecar, independent expedited review before launch
     authorization. PASS.
   - **Q2**: §10.3 freezes "no numerical U2 minimum-mass kill gate" with
     quality tiers and claim caps. PASS.
   - **Q3**: §5.1 adds per-device holdout reporting and the mandatory
     `SMALL_N_FIVE_DEVICE_PROBE` warning (wide uncertainty, descriptive
     support/cap only, never replaces FINAL). PASS.
   - **Q4**: §5.2 freezes the verbatim claim-contract sentence — no broad
     unseen-industrial-domain generalization claim before FINAL; the claim
     rests on the single cooler-motor evaluation. PASS.
   - **Q5**: §7 attaches `BENIGN_ONLY_MEMBER_BY_PUBLISHER_SCENARIO` to every
     accepted PNNL normal member. PASS.
   - **Q7**: §16 records that the 40.48 GiB reading is evidence, not launch
     clearance; P0-D stays a fresh launch-time measurement. PASS.
   - Contract tests extended 30 → 33: new cases 18 (uncloseable P0-B
     consequence), 19 (post-transfer CIC failure consequence), 22
     (per-device holdout + small-n warning). PASS.
   - Authority chain cites review `0e67e45`; executable chain (sidecar
     verification → implementation + 33 tests → implementation review →
     appendix → fresh P0-D → explicit user authorization) is correct. PASS.

## What this verification authorizes

- Codex may implement the D0-P3 executor and its 33 contract tests, then
  present them for my implementation review. The remaining gates after
  that, in order: P0 launch appendix (user's authenticated inventory,
  metadata only) → my expedited appendix review → fresh P0-D storage
  measurement → explicit user authorization → transfer.

This verification does **not** authorize: implementation-adjacent retrieval,
account use, object-body download, archive opening, HPC, training,
embedding, threshold work, or FINAL contact.

## Practical note for the user (restated from review)

At 40.48 GiB free on D:, the frozen launch gate will very likely block.
Freeing substantially more space (or designating a larger volume) before
the authorization step will avoid a lawful refusal at launch time.
