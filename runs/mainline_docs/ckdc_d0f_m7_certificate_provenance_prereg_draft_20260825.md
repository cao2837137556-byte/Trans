# CKDC D0-F — M7 suppression-provenance and Option-A certificate audit

**Status:** DRAFT — review required before freeze or execution

**Date:** 2026-08-25

## 1. Question and scope

This audit asks one bounded question:

> Does the single pre-existing CKBW Option-A conjunction define a non-vacuous,
> non-degenerate normality certificate on legal select data, while surviving a
> separate kill-only audit on already-viewed attacks?

This is not an open search over rules.  It does not train a model, fit a parameter, select a
threshold, open a PCAP, access FINAL, or authorize a new detector.

The two phases are physically and procedurally separated.  Phase A cannot open or summarize any
viewed report artifact.  Phase B cannot run unless Phase A has emitted an immutable candidate
marker whose complete identity is hashed.

## 2. Scientific status of the evidence

| evidence | role in D0-F |
|---|---|
| 7,069 legal select rows | only evidence allowed to determine `CERTIFICATE_CANDIDATE` versus `NO_CERTIFICATE` |
| 51,057 already-viewed report attacks in `P2 hard / M7 normal` | kill-only falsification; never positive evidence and never a selector |
| cooler-motor and seeds 37/47 | FINAL; forbidden to open |

Passing Phase B creates no scientific claim.  It may only permit a request for a separately
preregistered, separately authorized, one-shot untouched confirmation.

## 3. Immutable identities

The implementation must pin and verify before reading rows:

1. CKDA D1 FROZEN contract:
   `runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md`,
   SHA-256 `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`;
2. CKDA fit/select plan:
   `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv`,
   SHA-256 `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac`;
3. CKDA threshold marker:
   `ckda_d1_threshold_freeze_marker.json`,
   SHA-256 `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b`;
4. CKDA report scores, Phase-B only:
   `ckda_d1_report_scores.csv.gz`,
   SHA-256 `7ed1c0e9ebd0cbfc95669a064dcf1f57dd343fc4106611216575232432a0e6f9`;
5. CKBW record predictions:
   `ckbw_record_predictions.csv.gz`,
   SHA-256 `d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85`;
6. CKDC D0 legal-select output and its `SHA256SUMS`, committed under
   `runs/issue27ckdc_d0_existing_evidence_diagnostic_v1_2026-08-20_local/`.

Every join is exact on immutable UID.  Duplicate UID, missing required row, non-finite score,
threshold disagreement, role disagreement, or SHA mismatch is an engineering failure with no
scientific verdict.

## 4. The only candidate functional form

The candidate is a literal realization of CKBW Option A using only already-frozen decisions and
thresholds.  The CKBW score is an attack-oriented process score; therefore strong process
normality is the strict low side of the already-frozen normal threshold:

```text
tail_normal = tail_margin_score <= tail_margin_tau_normal
c1_normal   = c1_hard == 0
ckbq_normal = frozen_ckbq_hard == 0

normality_certificate = tail_normal AND c1_normal AND ckbq_normal
candidate_hard = P2_hard AND NOT normality_certificate
```

The inequalities, Boolean operators, missing-value behavior, and input columns are frozen here.
There is no new numeric cut.  Missing or non-finite evidence makes
`normality_certificate = false` (fail closed: preserve the P2 decision).

Forbidden alternatives include M7 normal alone, `P2 AND M7`, OR rules, per-source or per-family
exceptions, learned weights, score calibration, threshold scans, and any second candidate.

## 5. Phase A — legal select only

### 5.1 Pre-open boundary

Before any row is read, Phase A must assert that every path belongs to the legal fit/select plan
or committed CKDC D0 select outputs.  Paths containing report, held, future, sealed, cooler,
seed37, or seed47 identities are forbidden.  The Phase-A process receives no Phase-B path or
handle.

The expected legal denominator is exactly 7,069 rows:

- 4,000 `aux_normal_select`;
- 3,000 `aux_select`;
- 69 `support_val`.

The previous D0 sentinels must reproduce before the candidate is evaluated:

- benign `P2 hard / M7 normal`: 4,986;
- benign `P2 normal / M7 normal`: 2,014;
- attack `P2 hard / M7 hard`: 69;
- attack `P2 hard / M7 normal`: 0.

### 5.2 Mechanical `CERTIFICATE_CANDIDATE` gate

All clauses are conjunctive:

1. `normality_certificate` uses exactly the formula in section 4 and no fitted value;
2. among the 4,986 legal benign conflict rows, certificate coverage is at least 300 rows;
3. certificate coverage fraction among those rows is at least 5%;
4. covered benign conflicts span at least three frozen source groups;
5. the largest source-group share among covered benign conflicts is at most 80%;
6. all 69 legal `support_val` attacks remain hard;
7. `candidate_hard` differs from P2 hard on at least 300 legal benign conflict rows;
8. `candidate_hard` differs from `P2_hard AND M7_hard` on at least one legal row;
9. `normality_certificate` differs from `M7_normal` on at least one legal row;
10. review count, FINAL opens, report opens, PCAP opens, training operations, and fitted
    parameters are all zero.

The `300`, `5%`, three-group, and 80% clauses reuse the scale and diversity discipline of the
already-frozen CKDC conflict-support audit.  They are minimum non-vacuity conditions, not claims
of effectiveness.

If every clause passes, Phase A emits:

```text
CKDC_D0F_CERTIFICATE_CANDIDATE_FROZEN
```

and an atomic candidate marker containing the full formula, input identities, denominator,
clause results, output hashes, and its own SHA-256.  The implementation and candidate formula
cannot change after that marker exists.

If any clause fails, the only scientific verdict is:

```text
CKDC_D0F_NO_CERTIFICATE
```

Phase B is then forbidden and CKDC fusion closes.

## 6. Phase B — viewed attack kill-only falsification

Phase B requires a valid Phase-A candidate marker and independently re-hashes every immutable
input.  It may then open only the already-viewed report score artifact and the exact CKBW rows
needed for the frozen join.

The sentinel denominator is exactly 51,057 attack rows already known to be in
`P2 hard / M7 normal`, including 45,090 `future_query` rows.  Phase B must reproduce that
denominator before evaluating the candidate.  Any mismatch is an engineering failure, not a
scientific result.

For every sentinel attack row, evaluate the frozen section-4 formula.  The only pass condition is:

```text
hard_to_normal_flips == 0
```

Any flip yields:

```text
CKDC_D0F_VIEWED_SAFETY_FALSIFICATION_FAIL
```

and permanently closes this candidate.  No revised rule, inequality, missing-value treatment,
threshold, feature, exception, or replacement candidate is permitted.

Zero flips yields:

```text
CKDC_D0F_VIEWED_SAFETY_FALSIFICATION_PASS_NO_POSITIVE_EVIDENCE
```

This result supplies no estimate of generalization and authorizes no FINAL access.  It only
permits drafting a new one-shot confirmation protocol.

## 7. Causality, engineering, and Python compatibility contracts

The implementation must include contract tests that establish:

1. exact UID join and duplicate rejection;
2. Phase-A path allowlist rejects every viewed/FINAL marker before open;
3. Phase A has no Phase-B path, handle, import side effect, or output field;
4. exact `<=` normal-threshold boundary, including equality as normal evidence;
5. missing/non-finite evidence preserves P2 hard;
6. the candidate formula matches a literal truth table;
7. every Phase-A gate boundary (299/300, below/at 5%, 2/3 groups, above/at 80%);
8. support attack preservation is exact 69/69;
9. AND/M7 observational-equivalence failures close Phase A;
10. Phase-B launch requires the exact Phase-A marker and SHA;
11. Phase-B denominator mismatch fails before candidate evaluation;
12. one viewed attack flip fails closed and zero flips has the exact no-positive-evidence label;
13. no scientific verdict after engineering failure;
14. atomic outputs plus complete `SHA256SUMS` readback;
15. Python 3.9 AST parse and execution of the full contract suite.

## 8. Outputs

Phase A outputs only:

- input and boundary audit JSON;
- legal select certificate rows/summary;
- mechanical clause table;
- candidate marker or `NO_CERTIFICATE` verdict;
- validation report and `SHA256SUMS`.

Phase B, if authorized and reachable, outputs only:

- Phase-A marker verification;
- exact viewed sentinel audit;
- frozen-candidate flip summary, including per-role and per-family counts for diagnosis only;
- kill-only verdict, validation report, and `SHA256SUMS`.

No row-level FINAL data, credentials, model weights, new thresholds, or fitted parameters may be
written.

## 9. Authorization boundary

This DRAFT authorizes nothing.  Independent review is required before FROZEN generation.

Even after freeze:

- Phase A implementation and execution require explicit user authorization;
- Phase B requires a separate explicit user authorization after Phase-A artifacts are reviewed;
- formal CKDA D1 HPC replay remains a separate obligation and cannot reuse localwin checkpoints;
- FINAL remains sealed and CKDB remains closed.
