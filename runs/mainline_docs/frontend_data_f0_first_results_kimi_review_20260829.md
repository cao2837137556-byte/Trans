# Frontend-F0 / Data-F0 First Results — Kimi Consolidated Terminal Review

- Reviewer: Kimi
- Date: 2026-08-29
- Commits reviewed: `0a41307` (Step-0), `43106b2` (Stage I + Data-F0)
- Verdict: **ALL THREE RESULTS VERIFIED AND CORRECTLY CLASSIFIED.** No positive signal,
  no scientific failure either — three clean gate outcomes, each exactly as the frozen
  protocols dictate. Strategic options for the user in §4.

## 1. Independent verification performed

1. SHA256SUMS of all three result directories recomputed: every file `OK` (6, 6, and 9
   artifacts respectively; zero mismatches).
2. Contract suites re-run independently on Python 3.9: Step-0 **5/5 PASS**, Stage I
   **6/6 PASS**, Data-F0 **5/5 PASS** (the Data-F0 suite filename differs from the
   report's example path; the actual suite is
   `issue27data_f0_candidate1_metadata_audit_contract_tests_v1.py` — verified present
   and passing; cosmetic naming note only).
3. Verdict JSONs read from disk and match the reported states exactly:
   `NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE`,
   `F0_NO_USABLE_OFFICIAL_CHECKPOINT`, `PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD`.
4. Boundary counters all zero in all three reports (PCAP/report/FINAL/representation/
   probe/training; checkpoint downloads; candidate-2 accesses; credentials).

## 2. Rulings on classification correctness

**Step-0 — `NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE`: CORRECT.**
M1 established that the four frozen predicates cannot be reconstructed from legal
artifacts: IP protocol and reversible session keys were never persisted, and the reason
was hashed non-invertibly into the missing session identity. This is precisely the
fail-closed state the protocol armed. The result is itself a finding: **the committed
pipeline discarded the evidence needed to explain its own coverage loss** — a
documentation/provenance lesson worth recording in the paper methodology. The benign
75%-missing question remains open and is now answerable only by a preregistered causal
re-decode over already-legal local PCAPs.

**Stage I — `F0_NO_USABLE_OFFICIAL_CHECKPOINT`: CORRECT, and two disciplining points
held.** (a) It is not engineering incompatibility, so NetMamba correctly stayed sealed;
(b) it is not a scientific failure of Pcap-Encoder, so the single-frontend stop rule is
not triggered either — the challenge is paused, not lost. The audit also produced
durable assets: a frozen conservative protocol-support matrix (IPv4/IPv6 TCP+UDP + IPv4
ICMP — note this already exceeds netFound's TCP/UDP-only gate, which is exactly the
mechanism that made our ICMP/GRE families unencodable), a pinned MIT license identity,
and a resource estimate.

**Data-F0 — `PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD`: CORRECT.** Absence of a
pre-open member inventory is mapped to PENDING, not to a positive pairing and not to a
negative conclusion; candidate 2 stays sealed because candidate 1 did not enter a frozen
failure state; N (paired-device count) is unknown so the N≥8 / N_E / N_T gates were
correctly not evaluated. No Data-E/Data-T identities were created — exactly as required.

## 3. What this round established

Three entry points were tested at minimal cost before any expensive commitment:

| Lane | Outcome | Money/time burned | What it would have cost if entered blindly |
|---|---|---|---|
| Step-0 | attribution impossible without re-decode | minutes, local | retraining against an unexplained 75% coverage hole |
| Stage I | official checkpoint identity unpinnable | metadata only | embedding 25k sessions from an unreproducible artifact |
| Data-F0 | pairing unprovable from metadata | metadata only | tens of GB download with no guaranteed pairing payoff |

This is the governance loop working as intended: cheap gates before expensive actions.

## 4. Options now open (each requires its own frozen protocol + user authorization;
none is authorized by this review)

1. **Step-0b: causal re-decode attribution audit** — local, uses already-legal project
   PCAPs, no new data, no network. Answers the last open encoder question (where the
   benign 75% sits among the four predicates). Cheapest remaining information gain.
   **My top recommendation if the system line continues.**
2. **Stage I repair: fetch-only-to-pin** — a new narrow protocol authorizing download of
   the single official `weights.pth` solely to pin its byte identity (SHA, size, fetch
   date, provenance URL), with all inference still frozen until the identity is locked
   and reviewed. Weaker than publisher-pinned identity (Drive content can silently
   change; integrity against publisher intent is unverifiable), but the selection-risk
   it was designed to prevent does not exist here: one official object, zero challenger
   results. Defensible if the user wants the frontend challenge to continue; the claim
   would be bounded to the pinned artifact.
3. **Data-F0b: CIC IoT 2022 bulk-inventory protocol** — download inventory-grade objects
   to establish member-level pairing. Requires a fresh disk/network plan (D-drive budget
   ~80 GiB freed earlier; dataset is tens of GB compressed). Deferrable until Step-0b
   clarifies whether paired consumer data would even serve the dominant failure mode.
4. **Encoder pretraining** — now formally the only remaining way to get a new frontend
   if (2) is rejected; expensive, needs compute + lineage protocol, HPC still down.
   Not recommended at this time.
5. **Paper line** — unaffected and strengthened: this round adds three more clean,
   pre-registered gate outcomes to the evidence chain.

My sequencing recommendation: **(1) now; (2) and (3) decided after (1) reports.** If
Step-0b shows benign missingness is dominated by the protocol gate or session-key
formation (input semantics), a new frontend is justified and (2) becomes valuable; if it
shows timestamp-regression poisoning dominates (pipeline bookkeeping), a cheaper
re-encode repair may exist and the frontend challenge may be unnecessary.

## 5. Sealed state

No further execution authorized. Candidate 2 (CICIoT2023), NetMamba, bulk downloads,
checkpoint inference, training, FINAL, report, and HPC all remain sealed.
