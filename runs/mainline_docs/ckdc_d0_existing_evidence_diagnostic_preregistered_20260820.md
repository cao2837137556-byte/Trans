# CKDC D0 existing-evidence diagnostic — FROZEN preregistration

**Status:** `FROZEN`  
**Date:** 2026-08-20  
**Route:** CKDC  
**Scope:** read-only diagnosis of already generated, non-FINAL artifacts  
**Scientific authority:** diagnostic only; this document does not authorize a new model,
training, threshold selection, report reopening, FINAL access, or HPC submission.

## 1. Question

CKDA D1 established a strong attack-side representation result but failed its per-pool OOD
guardrail.  The only failed pool was `iotsim-hydraulic-system`; frozen M7 produced no hard
alerts on the same 3,000 rows, while a Boolean `P2 AND M7` destroyed attack recall.

CKDC D0 asks two narrower questions before any system design:

1. **H3 support:** does the legal fit/select partition contain both benign and attack examples
   in the `P2 hard / M7 normal` conflict quadrant, so that a bounded normality correction could
   be identified without using the already-viewed report partition?
2. **H1 time course:** on the already-viewed hydraulic report rows, is P2 failure concentrated
   late in a causal session, which would justify a separate empirical audit of information lost
   by E3's early-burst representation?

This protocol explicitly does **not** assume that E3 uses a 256-packet window.  The frozen I1
candidate used a 256-packet prefix but never trained.  The actual CKDA D1 result came from E3.

## 2. Correct E3 capability premise

The immutable E3 implementation is audited as code, not inferred from the I1 contract:

- packets are grouped into direction-specific bursts;
- a new burst begins after a gap greater than 10 ms;
- direction-specific bursts are merged and ordered by first timestamp;
- only the earliest 12 merged bursts are retained;
- only the first 6 packets of each retained burst are represented;
- therefore at most 72 packet-content records are visible;
- `flow_duration` is nevertheless computed through the latest causally observed packet.

Consequently H1 is **early-burst content truncation / loss of later causal structure**, not a
generic `256 < median 662` claim.  M7 and E3 also differ in feature view and scorer, so their
comparison is not a clean horizon-only ablation.

## 3. Immutable inputs

All paths are repository-relative unless an absolute transfer path is shown.

| Input | Identity |
|---|---|
| CKDA D1 FROZEN contract | `runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md`; SHA-256 `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9` |
| CKDA fit/select plan | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv`; SHA-256 `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| CKDA select scores | same stage, `ckda_d1_select_scores.csv.gz`; SHA is taken from the stage `SHA256SUMS` and verified before read |
| CKDA threshold marker | same stage, `ckda_d1_threshold_freeze_marker.json`; SHA-256 `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |
| CKDA report scores | same stage, `ckda_d1_report_scores.csv.gz`; SHA-256 `7ed1c0e9ebd0cbfc95669a064dcf1f57dd343fc4106611216575232432a0e6f9` |
| CKDA report target metadata | same stage, `ckda_d1_report_target_metadata.csv`; SHA-256 `628c542108b4b582e74cd6ed0e5474a5f69225bd6a7c054200998d7448bfe65e` |
| CKDA report embedding metadata | same stage, `ckda_d1_report_embeddings.npz.metadata.csv.gz`; SHA is taken from `SHA256SUMS` and verified before read |
| CKBW record predictions | `D:/study/paper/anomaly_detection/paper04/supercompute_transfer/ckbw_157624_extract/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624/ckbw_record_predictions.csv.gz`; SHA-256 `d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85` |
| E3 embedder | `repo/ood/issue27ckda_d1_e3_embed_v1.py`; SHA-256 `360cbaa72f818e6fc423b16f3b4989333bfba002a1423085ff15b2cb1569de14` |
| netFound flow adapter | `repo/ood/issue27ckda_d0_resource_pilot_v1.py`; SHA-256 `ec1cb7be1f47e2ef7862905f3e89c75c0295fb1565fa0820d174a6e11409856a` |

Any identity mismatch is an engineering failure and produces no scientific verdict.

## 4. Data boundaries

### 4.1 Legal actionability partition

Only rows whose CKDA role is one of:

- `support_val`,
- `aux_normal_select`,
- `aux_select`

may support a `GO_*` decision for a future learnable correction.  Their P2 score/hard state was
frozen before the report partition was opened.

### 4.2 VIEWED report partition

The CKDA report partition has already been opened.  It may be used only for:

- exact denominator reproduction;
- descriptive time-course diagnosis;
- falsification or limitation statements.

It may not select a feature, window, threshold, model, loss, or correction rule.  In particular,
the observed hydraulic result may not choose a new horizon arm.

### 4.3 FINAL exclusion

The following remain forbidden:

- every `cooler-motor` FINAL source;
- seed 37/47 FINAL material;
- any new FINAL decode, score, label, or metric;
- any mutation of CKDA D1 artifacts.

The implementation must fail closed if a row/path contains a FINAL marker.

## 5. D0-A — identity and denominator audit

Before analysis, verify:

1. every input identity in §3;
2. select P2 has exactly one row per UID;
3. CKBW duplicates across held-value views are invariant for M7 hard state,
   `tail_margin_score`, and both frozen thresholds before one UID copy is retained;
4. the select join is exact and one-to-one after invariant deduplication;
5. report P2 has exactly one row per UID and joins report metadata exactly;
6. no FINAL marker is present;
7. no output file exists from a previous run unless the output directory is a new run identity.

## 6. D0-B — legal conflict-support audit

Use the P2 frozen hard column and frozen M7 hard state.  Produce the four exact quadrants:

| P2 | M7 | meaning |
|---|---|---|
| normal | normal | shared normal |
| normal | hard | M7-only hard |
| hard | normal | candidate normality-correction conflict |
| hard | hard | shared hard |

Report counts by:

- role;
- metric label;
- attack family;
- source group;
- quadrant.

The continuous M7 `tail_margin_score` may be described, but no margin cut is scanned or selected.

### H3 actionability gate

`H3_LEGAL_SUPPORT_PRESENT` requires all of:

1. at least 300 benign select rows in `P2 hard / M7 normal`;
2. those benign rows span at least 3 source groups;
3. at least 30 attack select rows in `P2 hard / M7 normal`;
4. those attack rows span at least 3 attack families;
5. no source group or attack family supplies more than 80% of its side's qualifying rows.

If any clause fails, H3 is classified
`NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT`.  Report rows cannot repair this failure.

## 7. D0-C — E3 capability audit

The implementation performs static and behavioral contract checks that mechanically establish:

- burst gap = 10 ms;
- maximum merged bursts = 12;
- maximum packets per burst = 6;
- maximum content records = 72;
- retained bursts are earliest-first;
- later causal duration remains visible;
- later packet contents and later burst structure beyond the caps are not represented.

This produces a **capability boundary**, not a claim about how often real targets exceed the cap.
No PCAP is opened in this D0.

## 8. D0-D — VIEWED hydraulic causal time-course audit

Restrict to report rows with device family `iotsim-hydraulic-system` and probe `P2`.
Within each immutable `session_id`, sort by `(timestamp_epoch, event_position, uid)` and compute:

- `target_ordinal_so_far` (1-indexed);
- `elapsed_seconds_so_far` from the first target timestamp in that session;
- the provided capture-level `event_position` (explicitly **not** called session packet count).

Use only these fixed bins:

### Target ordinal bins

- `1`
- `2-4`
- `5-16`
- `17-64`
- `65+`

### Elapsed-time bins

- `0-1s`
- `(1,10]s`
- `(10,60]s`
- `(60,300]s`
- `(300,1800]s`
- `>1800s`

### Capture event-position bins

- `0-72`
- `73-256`
- `257-1024`
- `1025+`

For every bin and hydraulic source group, report rows, sessions, P2 hard rate, M7 hard rate,
median P2 score, and interquartile P2 score.  Empty cells remain explicit.

### H1 descriptive support rule

Define `early` as target ordinal `1-4` and `late` as `65+`.  A hydraulic source is eligible for
comparison only if both sides contain at least 30 rows and at least 5 sessions.

`H1_TIME_COURSE_SUPPORT_PRESENT` requires at least 3 hydraulic source groups with an absolute
late-minus-early P2 hard-rate change of at least 10 percentage points in the same direction.

- If the change is positive, record `LATE_STAGE_DEGRADATION_SIGNAL`.
- If negative, record `LATE_STAGE_IMPROVEMENT_SIGNAL`.
- Otherwise record `NO_CONSISTENT_TIME_COURSE_SIGNAL`.

This rule can authorize only a later, separately frozen empirical retention audit.  It cannot
authorize a new model or choose a horizon.

## 9. Mechanical verdict

The result JSON contains independent fields rather than forcing one route-wide binary:

- `h3_verdict`:
  - `H3_LEGAL_SUPPORT_PRESENT`, or
  - `NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT`;
- `h1_verdict`:
  - `H1_TIME_COURSE_SUPPORT_PRESENT`, or
  - `NO_CONSISTENT_TIME_COURSE_SIGNAL`, or
  - `INSUFFICIENT_EARLY_LATE_SUPPORT`;
- `e3_capability_verdict`:
  - `EARLY_BURST_CONTENT_CAPPED_DURATION_VISIBLE` only if every §7 check passes.

Allowed next actions:

- H3 PASS only authorizes drafting a separately frozen bounded-correction protocol.
- H1 PASS only authorizes drafting a separately frozen, label-free empirical retention audit.
- neither result authorizes training, report reuse for selection, FINAL access, or HPC.
- if H3 fails, no learned M7 correction may be claimed identifiable on the current split.

## 10. Outputs

The implementation writes atomically:

1. `ckdc_d0_input_audit.json`
2. `ckdc_d0_select_quadrants.csv`
3. `ckdc_d0_select_support_summary.csv`
4. `ckdc_d0_e3_capability_audit.json`
5. `ckdc_d0_hydraulic_time_course.csv`
6. `ckdc_d0_hydraulic_source_contrasts.csv`
7. `ckdc_d0_verdict.json`
8. `ckdc_d0_result_report.md`
9. `SHA256SUMS`

Engineering failure removes any verdict and writes only `engineering_failure.json`.

## 11. Implementation contract tests

Before execution, tests must cover at least:

1. every immutable SHA gate;
2. exact one-to-one select join;
3. duplicate-view invariance before CKBW deduplication;
4. missing UID fail-closed;
5. FINAL marker fail-closed;
6. exact four-quadrant truth table;
7. each H3 conjunction and one all-pass synthetic case;
8. fixed bin boundary inclusivity;
9. deterministic within-session ordering ties;
10. early/late minimum support;
11. same-direction 3-source H1 rule;
12. capture position never relabeled as session packet count;
13. E3 constants and earliest-first behavior;
14. later duration visible while later content is capped;
15. atomic outputs;
16. engineering failure produces no scientific verdict;
17. Python 3.9 syntax and runtime compatibility.

## 12. Claim boundary

CKDC D0 can establish whether the current legal split contains identifiable support for a future
M7-class correction and whether already-viewed hydraulic errors have a consistent causal
time-course signature.  It cannot establish that a correction works, that a longer representation
works, or that the final system meets publication targets.
