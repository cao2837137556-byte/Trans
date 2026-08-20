# CKDC D0 existing-evidence diagnosis — implementation and result

**Date:** 2026-08-20  
**Protocol:** `ckdc_d0_existing_evidence_diagnostic_preregistered_20260820.md`  
**Protocol SHA-256:** `2088de963f70c3b783a9c4f9c2a6e6a3f2f6053e2117c68067592c8f2d742d18`  
**Execution:** local, read-only, no PCAP, no training, no FINAL

## 1. Implementation

Added:

- `repo/ood/issue27ckdc_d0_existing_evidence_diagnostic_v1.py`
- `repo/ood/issue27ckdc_d0_existing_evidence_contract_tests_v1.py`

The implementation verifies every frozen input SHA, proves CKBW held-view invariance before
deduplication, performs exact one-to-one joins, fails closed on FINAL markers, writes through a
temporary result directory, and refuses to replace any existing result directory.

Contract suite: **25/25 PASS**.  The suite includes Python 3.9 grammar parsing and the previously
observed failure classes: exact joins, truth-table directions, bin edges, concentration clauses,
minimum independent support, atomic output, no-verdict engineering failure, and E3 cap semantics.

## 2. Input and execution validation

- immutable input identities: all PASS;
- legal select rows: 7,069, unique UID coverage 7,069/7,069;
- roles: 4,000 `aux_normal_select`, 3,000 `aux_select`, 69 `support_val`;
- CKBW duplicate-view disagreements: zero for M7 hard, tail score, normal threshold, and attack
  threshold;
- hydraulic report rows: 3,000, across 742 sessions and five source groups;
- PCAP opened: 0;
- FINAL opened: 0;
- model training: 0.

The result `SHA256SUMS` independently verifies 8/8 output members.

## 3. H3 result — current split cannot identify a safe M7 correction

Legal select quadrants are:

| metric label | P2/M7 quadrant | rows |
|---|---|---:|
| benign | P2 hard / M7 normal | 4,986 |
| benign | P2 normal / M7 normal | 2,014 |
| attack | P2 hard / M7 hard | 69 |
| attack | P2 hard / M7 normal | **0** |

The benign side is broad enough (4,986 rows, six source groups, maximum source share 73.95%), but
the critical attack side has zero rows and zero attack families.  Therefore the frozen conjunction
mechanically returns:

`NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT`

This is not evidence that M7-class evidence is useless.  It says the current legal select split
contains no example of the failure a bounded correction must avoid.  Training a correction now
would either be unvalidated or would use the already-viewed report partition for selection.

## 4. H1 result — strong descriptive topology, insufficient independent late support

Exact VIEWED hydraulic facts reproduce:

- P2 hard: 2,289/3,000 = 76.30%;
- M7 hard: 0/3,000 = 0%;
- five source groups, 742 sessions.

For every source group, ordinal 1-4 has only about 5.3%-7.2% P2 hard, whereas ordinal 65+ has
100% P2 hard.  However the late rows in each source come from **one** long session, not at least
five independent sessions:

| source | early rows/sessions | early P2 hard | late rows/sessions | late P2 hard |
|---|---:|---:|---:|---:|
| hydraulic-12 | 150 / 147 | 6.67% | 391 / 1 | 100% |
| hydraulic-13 | 152 / 149 | 5.26% | 385 / 1 | 100% |
| hydraulic-14 | 152 / 149 | 5.92% | 386 / 1 | 100% |
| hydraulic-15 | 151 / 148 | 5.30% | 390 / 1 | 100% |
| hydraulic-2 | 152 / 149 | 7.24% | 391 / 1 | 100% |

The preregistered independent-support rule therefore returns:

`INSUFFICIENT_EARLY_LATE_SUPPORT`

The large raw contrast must not be reported as hundreds of independent confirmations.  It may be
a late-stage effect, or merely a distinct long-session type that P2 misclassifies from its first
target.  The present aggregation cannot distinguish those mechanisms.

## 5. E3 capability result

Static and behavioral contract checks confirm:

- 10 ms burst gap;
- at most 12 merged bursts passed to netFound;
- at most 6 packets per burst (72 content records total);
- earliest bursts retained;
- duration remains current-inclusive through the latest observed packet;
- later packet contents and later burst structure beyond the caps are absent.

Verdict: `EARLY_BURST_CONTENT_CAPPED_DURATION_VISIBLE`.

This is a capability boundary, not yet an empirical claim that the cap caused hydraulic failure.

## 6. Scientific decision

1. **Do not train an E3+M7 correction on the current split.**  The decisive conflict-attack
   support is absent from legal selection data.
2. **Do not claim that longer context fixes hydraulic.**  The first time-course gate is
   underidentified because late support is one long session per source.
3. **Do not return to external-data acquisition.**  CKDB is already closed and this D0 did not
   reopen it.
4. A final, cheap diagnostic may distinguish `late degradation` from `long-session identity` by
   selecting each source's longest session using metadata only and inspecting its first target
   versus later targets.  That comparison must be frozen before its scores are read.  It still
   cannot authorize training; it can only decide whether a neutral retention audit is warranted.

## 7. Claim boundary

This result diagnoses why the obvious system upgrade cannot yet be learned safely.  It does not
reduce the already observed CKDA attack-side signal, does not validate a new system, and does not
replace the required formal CKDA HPC replay.
