# CKDB D0-P1 Kimi implementation review — PASS

Date: 2026-08-17
Reviewer: Kimi
Target: Codex implementation commit `bbfb4eb`
Scope: `repo/ood/issue27ckdb_d0_p1_external_metadata_audit_v1.py`, its test
suite, and `runs/mainline_docs/ckdb_d0_p1_retrieval_plan_20260817.json`

## Verdict: IMPLEMENTATION REVIEW PASS — metadata-only execution authorized under the user's existing authorization

## What I independently verified (not from the report)

1. **Contract tests**: ran `python -m unittest
   repo.ood.test_issue27ckdb_d0_p1_external_metadata_audit_v1` myself:
   **23/23 PASS**, offline.
2. **Frozen identities**: recomputed SHA-256 of the FROZEN protocol
   (`9e96ad28...63a3ba`) and retrieval plan (`07eddd24...5d74f`); both match
   the report and the sidecar verified at freeze.
3. **Retrieval plan contents**: exactly 2 candidates; 8 Tier A objects +
   1 Tier B object; per-object host allowlists are primary-source only
   (`iotanalytics.unsw.edu.au`, `datadryad.org`, `doi.org`,
   `ieeexplore.ieee.org`, `www.unb.ca`, `cicresearch.ca`); per-object byte
   caps sit inside the frozen 20 MiB / 128 MiB tier caps; the two future
   large objects are recorded as `FUTURE_USER_AUTHORIZATION_REQUIRED_NOT_EXECUTABLE`.
4. **R1 realization in code** (`parse_cic_roles` + `build_coverage_and_horizon`):
   all six CIC roles get one `cluster_id=CIC_SIMULATED_SUBSTATION_1`;
   `independent_domain_counted=1` only for the first role; verdict branch
   `cic_clusters < 3` → `CKDB_D0_P1_PENDING_METADATA` with
   `SECOND_INDUSTRIAL_PROCESS_CORPUS`. UNSW devices each form their own
   cluster (27 expected, enforced by exact row count). Correct.
5. **Frozen long-TCP descriptor**: literal
   `bidirectional TCP AND (packets > 256 OR duration >= 300)`, computed over
   aggregate columns only; forbidden per-packet/payload header fields reject
   the object; `SafetyError` → physical quarantine + re-raise → engineering
   failure with **no verdict file** (verdict deleted if partially written).
6. **FINAL/report/label/model boundary**: `FINAL_MARKERS` (cooler-motor,
   seed37/47 variants) raise on any matching context; verdict counters
   hardcode `final_files_opened=0, pcap_files_opened=0, models_opened=0,
   label_columns_read=0`; no PCAP reader, model import, or training path
   exists in the module.
7. **Verdict can never authorize download**: `large_download_authorized:
   False` is a hardcoded literal in the verdict builder.
8. **Eligibility mechanics**: `tier_a_pass` requires identity `PASS` and a
   benign-boundary status starting with `PASS`; Tier B is unreachable when
   Tier A fails (`eligible_tier_b_specs`); engineering failure path emits
   only `engineering_failure.json` with `scientific_verdict: NOT_EMITTED`.

## Answers to Codex's five review questions

1. **Dryad license phrase check sufficient?** Yes. Dryad applies one
   per-dataset license (default CC0) on the landing page we retrieve;
   requiring an explicit reuse phrase on the primary page is the right
   fail-closed posture. No narrower token needed.
2. **UNSW `UNLABELED_NORMAL_CLAIM` + claim ceiling the intended reading?**
   Yes. The authors claim normal activity without attack ground truth, so
   eligibility passes but all downstream claims are capped
   (`PASS_WITH_CLAIM_CEILING` correctly counts as pass via the `startswith`
   check while the ceiling string travels with the row). Matches FROZEN
   Audit 3.
3. **E3 permanently comparison-only under `POSSIBLE_OVERLAP`?** Yes. The
   frozen rule bars upgrading `POSSIBLE_OVERLAP` by inference; netFound's
   incomplete pretraining disclosure means no later empirical result can
   promote the E3 arm. Correct and intentionally conservative.
4. **CIC clustering forcing `SECOND_INDUSTRIAL_PROCESS_CORPUS` the intended
   R1 realization?** Yes — and this sets the honest expectation now: barring
   an official multi-site inventory we have not seen, D0-P1's overall verdict
   will be `CKDB_D0_P1_PENDING_METADATA`, which activates the pre-frozen
   second-industrial-corpus amendment path. That is the designed outcome,
   not a failure.
5. **Tier-B aggregate-flow safety rules sufficient?** Yes for every
   masquerade class we can name: PCAP magic/member rejection, exact
   27-member aggregate CSV expectation, required aggregate columns,
   forbidden per-packet/payload columns, quarantine on any violation.
   Residual risk (per-packet rows hiding under innocent column names) is
   bounded: quantiles would be visibly degenerate, and no training or model
   may consume this metadata regardless.

## Findings recorded, neither blocking

- **F1 (implementation constant, a priori)**: the horizon status mapping
  uses `fraction_packet_count_gt_256 >= 0.05` to distinguish
  `PREFIX_256_COVERS_MOST_OBSERVED_FLOWS` from
  `PREFIX_256_TRUNCATES_MATERIAL_LONG_HORIZON`. This threshold is not in the
  FROZEN protocol. It was chosen before any download, is descriptive only,
  and gates nothing — acceptable. Requirement: the result report must
  present the raw fraction alongside the mapped status, and any future
  design decision that consumes horizon status needs its own freeze
  amendment naming this constant.
- **F2 (evidence presentation)**: Audit 2 lineage rows are static assertions
  with conservative ceilings (`NO_KNOWN_OVERLAP` at best, E3 permanently
  `POSSIBLE_OVERLAP`). The ceilings are the safe direction, so this is fine;
  the result report should still tabulate the actual capture-range evidence
  (UNSW `first_seen`/`last_seen` from the device summary) next to those rows
  so the timeline is evidence-backed rather than merely asserted.

## What this review authorizes

- Codex may consume the user's existing D0-P1 authorization and execute the
  metadata-only audit exactly as frozen (Tier A → audits 1–4 → Tier B gate →
  audits 5–8), then present the packaged result for my independent result
  review.

This review does **not** authorize: any PCAP/full-archive download, the
second-industrial-corpus amendment execution, HPC submission, training,
embedding, threshold work, or FINAL contact.
