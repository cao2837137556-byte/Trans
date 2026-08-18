# CKDB D0-P1 Kimi result review — RESULT PASS

Date: 2026-08-18
Reviewer: Kimi
Target: Codex result commit `0385ff4`, run
`runs/issue27ckdb_d0_p1_external_metadata_audit_v1_2026-08-17_local_r10/`

## Verdict: RESULT REVIEW PASS — terminal state `CKDB_D0_P1_PENDING_METADATA` accepted; pre-frozen second-industrial-corpus remedy is the next and only next gate

## What I independently verified

1. **Verdict JSON**: `status=CKDB_D0_P1_PENDING_METADATA`,
   `missing_evidence=SECOND_INDUSTRIAL_PROCESS_CORPUS`,
   consumer post-cluster domains 27, industrial 1,
   `large_download_authorized=false`; boundary counters all zero
   (PCAP/FINAL/labels/models/training/HPC). This matches the outcome I
   predicted as the designed R1 realization at implementation review —
   no discretion was exercised anywhere.
2. **Hash chain**: recomputed all `SHA256SUMS` entries in the result package
   myself: **20/20 PASS**. `flows.zip` hash in the manifest equals the
   report's claimed `91d99c0f...ce64`. Download directory contains exactly
   the 9 planned objects, nothing more.
3. **Contract tests at the execution commit**: reran the suite myself:
   **30/30 PASS** (23 original + 7 new engineering regressions).
4. **Retrieval-plan drift audit** (plan SHA changed `07eddd24...` →
   `0abf7b61...` after my implementation review): same schema version, same
   frozen contract SHA (`9e96ad28...`), same 2 candidates, same 9 objects,
   same URLs, same byte caps. The only changes are final-redirect host
   allowlist additions:
   - `dryad-assetstore-merritt-west.s3.us-west-2.amazonaws.com` — Dryad's
     own Merritt asset store, the actual redirect target of the official
     `datadryad.org/downloads/file_stream/...` URLs;
   - `api.crossref.org` — the DOI registration agency's metadata API,
     replacing the unreachable IEEE WAF shell for descriptor metadata.
   Both are primary-source/DOI-infrastructure hosts within FROZEN §3.1.
   No scope, object, or cap drift. The 7 new regression tests pin exactly
   these real-network behaviors. Accepted as engineering adaptation, not
   protocol amendment.
5. **Data consistency**: device inventory, coverage matrix, horizon/scale,
   lineage, and allowlist CSVs all match the report's numbers.

## Frozen-contract compliance

- R1 mechanics fired exactly as frozen: CIC six roles clustered to one
  simulator domain → mechanical `PENDING_METADATA` + named missing evidence.
- Long-TCP descriptor stayed literal and descriptive; 17.46% prevalence was
  not used as an inclusion patch (coverage CSV and report both state this).
- F1 satisfied: raw fraction (`0.000797` packets>256; `0.174638` long-TCP)
  is tabulated next to the mapped horizon status.
- F2 satisfied: capture ranges are tabulated from primary device metadata.
- E3 arm stays permanently `POSSIBLE_OVERLAP` (comparison-only); UNSW claim
  ceiling `UNLABELED_NORMAL_CLAIM` preserved in the benign-boundary CSV.

## Scientific observations for the record (descriptive, no gate consumed)

1. **Capture range now settled by primary evidence**: device metadata gives
   first_seen 2016-09-30 through last_seen 2017-04-13, confirming the
   round-3 ruling with corpus-internal data rather than the descriptor
   paper alone.
2. **UNSW's long flows are duration-driven, packet-sparse**: packet-count
   q50/q90/q99 = 2/10/20, while duration q90/q99 = 7,072 s / ~458,198 s
   (~5.3 days); 17.46% of flows satisfy the long-bidirectional-TCP
   descriptor almost entirely through duration. Hydraulic's failure-mode
   flows were packet-dense (median ~662 packets). Therefore UNSW can train
   duration-horizon robustness but likely not packet-horizon robustness of
   the hydraulic kind. This is a design input for the later CKDB
   representation/window discussion — recorded now, before any design
   choices, so it cannot be retrofitted into a selection story.
3. **CIC access path**: the allowlist records the benign tree as
   `PENDING_FORM_RESOLVED`; CIC distribution requires an access form. If CIC
   remains in play, the user will eventually need to complete that form
   personally; no automated credential path exists or should exist.

## What this review authorizes

- Codex may draft the **second-industrial-corpus amendment** under the
  pre-frozen remedy: candidate proposed through the frozen domain-type
  taxonomy (never hydraulic resemblance), same eight audits, own
  preregistration, my review, then user authorization before any download.

This review does **not** authorize: any PCAP/large download (including UNSW
`pcaps.zip`), CIC form submission, HPC, training, embedding, threshold work,
or FINAL contact.
