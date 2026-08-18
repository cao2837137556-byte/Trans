# CKDB D0-P2 Kimi implementation review — PASS

Date: 2026-08-18
Reviewer: Kimi
Target: Codex implementation commit `0b48e71`
Scope: `repo/ood/issue27ckdb_d0_p2_pnnl_metadata_audit_v1.py`, its test
suite, `runs/mainline_docs/ckdb_d0_p2_retrieval_plan_20260818.json`

## Verdict: IMPLEMENTATION REVIEW PASS — ready for user-authorized metadata execution

## What I independently verified

1. **Contract tests**: ran `python -m unittest
   repo.ood.test_issue27ckdb_d0_p2_pnnl_metadata_audit_v1` myself:
   **31/31 PASS**, offline (23 frozen + 8 hardening).
2. **Frozen identities**: recomputed — protocol
   `16926b7e...f41c4b6` matches the sidecar I verified at freeze; plan
   `5d1a313c...e80072` matches the report. The executor refuses to run on
   any other identity.
3. **Retrieval plan**: exactly 6 Tier-A objects; hosts limited to
   first-party and DOI infrastructure (`data.pnnl.gov`, `doi.org`,
   `www.osti.gov`, `api.datacite.org`); caps sum to 16 MiB (≤ frozen
   20 MiB total); largest object 4 MiB (≤ frozen 8 MiB per-object). The
   future tar entry has no executable URL and is marked
   `NOT_EXECUTABLE_REQUIRES_NEW_USER_AUTHORIZATION`.
4. **Four-condition gate** (`evaluate_independence` + `pnnl_domain_count`):
   C1–C3 are keyword evidence over official texts; C4 requires literal
   pre-open member naming (`electric_normal` ∧ `gas_normal`) that an opaque
   tar cannot supply. Count is 2 iff all four are TRUE, else 1 — conditions
   can only reduce, never inflate (Q4).
5. **PENDING_ARCHIVE_INVENTORY dominance** (Q3): C4 PENDING → benign row
   PENDING → verdict `CKDB_D0_P2_PENDING_METADATA` with
   `post_download_pre_use_boundary_verification_required=True`. The frozen
   consequence propagates exactly as ruled in review `14e281a`.
6. **Research-use fail-closed** (Q2): prohibited phrases →
   `INELIGIBLE`/NO-GO; explicit policy evidence → ELIGIBLE; anything else →
   PENDING, never silently eligible.
7. **Range/tar prohibition**: Range rejected both at plan validation and at
   request level; no tar body, member, PCAP, registration, label, model,
   training, HPC, or FINAL path exists in the module.
8. **Failure cleanup** (Q5): the exception path deletes verdict, report,
   SHA256SUMS, pullback archive and sidecar, leaving only
   `engineering_failure.json` with `NO_SCIENTIFIC_VERDICT`.
9. **Lineage ceilings**: netFound route permanently `POSSIBLE_OVERLAP`;
   FINAL identity-only (`FINAL_IDENTITY_ONLY_NOT_OPENED`); OSTI/DataCite
   timeline anchor per N1.

## Answers to Codex's five review questions

1. Six-object allowlist and caps: **YES**, byte-exact against the frozen
   boundary (item 3 above).
2. Research-use evidence fail-closed: **YES** (item 6).
3. `PENDING_ARCHIVE_INVENTORY` dominance: **YES** (item 5) — it caps the
   domain count at 1 and forces the pending verdict with the post-download
   verification flag, regardless of C1–C3 outcomes.
4. Conditions only reduce: **YES** (item 4).
5. Failure cleanup and non-executable tar: **YES** (items 7–8).

## Finding F1 (non-blocking, adjudication reserved for result review)

The FROZEN §9 state-2 clause "fewer than two PNNL post-clustering domains →
`NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS`" is mechanically unreachable in
this implementation: `evaluate_independence` emits only TRUE/PENDING (never
FALSE), so C1–C3 evidence insufficiency yields `PENDING_METADATA`, not
NO-GO. This is a defensible reading — §9 state 3 itself names "independence
evidence that could still be supplied" as a pending reason — but the
PENDING-vs-NO_IDENTIFIABLE distinction is now a review judgment rather than
a mechanical output. Requirement: at result review I will re-derive the
verdict from the per-condition evidence rows (the required
`independence_evidence.csv` already surfaces them verbatim) and adjudicate
then whether any evidence channel remains open (PENDING) or is exhausted
(NO-GO). No code change now.

## Expected terminal state (expectation setting, not a finding)

Because the tar is opaque and no pre-open member inventory exists, C4
cannot be TRUE in D0-P2. The mechanical terminal state will therefore
almost certainly be `CKDB_D0_P2_PENDING_METADATA` with
`post_download_pre_use_boundary_verification_required=True` — routing to
the combined large-download/census preregistration with the fail-closed
post-download boundary check. C1–C3 evidence quality determines what else
travels with that verdict. This is the designed path, not a failure.

## What this review authorizes

- The user may now authorize **D0-P2 metadata-only execution** (the six
  Tier-A objects). After execution, Codex presents the packaged result for
  my independent result review, including the F1 adjudication.

This review does **not** authorize: any PNNL tar/HEAD/range request,
registration automation, download of any large object, HPC, training,
embedding, threshold work, or FINAL contact.
