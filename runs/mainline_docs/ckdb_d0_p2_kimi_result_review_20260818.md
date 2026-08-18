# CKDB D0-P2 Kimi result review — RESULT PASS + F1 adjudication

Date: 2026-08-18
Reviewer: Kimi
Target: Codex result commit `fb1a069`, run
`runs/issue27ckdb_d0_p2_pnnl_metadata_audit_v1_2026-08-18_local/`

## Verdict: RESULT REVIEW PASS — designed pending state confirmed; combined large-download/census protocol may be drafted

## What I independently verified

1. **Verdict JSON**: `CKDB_D0_P2_PENDING_METADATA`,
   `PNNL_CORPUS_METADATA_PENDING`, sole reason code
   `PENDING_ARCHIVE_INVENTORY`; PNNL 1 + CIC 1 = combined 2 (< 3);
   `post_download_pre_use_boundary_verification_required=true`; every
   boundary counter 0/false (tar/PCAP/FINAL/labels/models/registration/
   training/HPC; `large_download_authorized=false`).
2. **Hash chain**: recomputed all `SHA256SUMS` entries myself:
   **17/17 PASS**. Report's per-object SHAs match the manifest; the DOI
   landing correctly deduplicated to the DataHub page identity.
3. **Retrieval discipline**: exactly the six frozen Tier-A objects, total
   138,037 bytes (≪ 20 MiB cap), no HEAD/Range, all final hosts first-party
   or DOI infrastructure.
4. **C1–C3 evidence is factually grounded, not keyword luck**: I fetched
   the official DataHub page myself earlier in this review cycle — it names
   electric and natural-gas process models (OPAL-RT microgrid vs gas
   distribution simulator), sector-specific fleets (SAGE RTU / SEL 451 /
   GE D30 vs ROC 800 / FloBoss / ControlWave), and sector-distinct networks
   ("the electrical and gas networks"). The TRUE verdicts match the
   underlying official text.
5. **Allowlist**: the tar entry is `NOT_EXECUTABLE_REQUIRES_NEW_USER_AUTHORIZATION`
   with intended use frozen as
   `POST_DOWNLOAD_PRE_USE_BENIGN_BOUNDARY_VERIFICATION_THEN_CENSUS_ONLY_IF_PASS`.

## F1 adjudication (reserved at implementation review `5e1ca71`)

The F1 concern was that C1–C3 insufficiency would mechanically yield
PENDING where frozen §9 state 2 might require NO_IDENTIFIABLE, leaving the
distinction to review judgment. **In this run the tension does not fire:**
C1–C3 are all TRUE on affirmative official evidence, so state 2's
"fewer than two domains" clause never arises from C1–C3. The sole non-TRUE
condition is C4, whose `PENDING_ARCHIVE_INVENTORY` → `PENDING_METADATA`
mapping was explicitly frozen (Q3 ruling, review `14e281a`). The mechanical
verdict coincides with the strict reading. **F1 is closed: verdict
confirmed correct, no residual adjudication debt.**

## Scientific state (plain terms)

- PNNL is structurally what we hoped: two genuinely distinct industrial
  process systems (C1–C3 affirmative).
- But the frozen contract refuses to count them as two usable benign
  domains until the opaque archive's normal units prove separable
  post-download. PNNL therefore contributes 1 domain for now; combined
  industrial = 2; the route gate remains 3.
- The only way to resolve C4 is the pre-accepted risky step: download the
  tar under a new preregistered protocol, run the fail-closed
  post-download/pre-use boundary verification, and isolate the archive
  with NO-GO if verification fails.

## What this review authorizes

- Codex may draft the **combined large-download/census preregistration**.
  Per the converged U-series placements and boundaries, that draft must
  include, before any authorization is requested:
  1. exact object identities for UNSW `pcaps.zip`, the PNNL tar, and the
     CIC benign tree (now that the user's form access is live), with
     expected bytes/SHA where published;
  2. the fail-closed post-download/pre-use PNNL boundary verification
     (isolation + NO-GO on failure, no replacement corpus);
  3. U2's coverage census with corpus-global descriptors;
  4. U3's `EXTERNAL_BENIGN_REPORT_HOLDOUT` deterministic selection rule
     and the mechanical industrial-holdout two-option choice, frozen from
     metadata counts before bodies open;
  5. U6's storage/transfer/cleanup plan with minimum free-space gates;
  6. the decision on whether U2 needs a numerical minimum-mass kill gate,
     taken before bodies open.
  The draft goes through the usual path: my review → FROZEN + sidecar → my
  freeze verification → explicit user authorization → download.

This review does **not** authorize: any large download, registration use,
HPC, training, embedding, threshold work, or FINAL contact.
