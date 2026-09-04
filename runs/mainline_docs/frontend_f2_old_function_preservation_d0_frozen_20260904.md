# Frontend-F2 old-function preservation D0 (FROZEN)

Date: 2026-09-04

Status: FROZEN before any additional incumbent score is opened.

## 1. Question and stop rule

Frontend-F1 produced no eligible checkpoint because its new representation
flipped five of 2,000 protected A-side internal-validation attacks. A narrow
audit established that the incumbent P2 scores for those five rows were all
at least 0.999067. This does not prove that attack semantics disappeared from
the GRU; it proves that the new representation failed to preserve the frozen
P2 decision function.

This D0 asks whether the original **training side only** contains an
identifiable continuous incumbent-teacher envelope strong enough to define one
mechanistically new Frontend-F2 attempt. It does not train or resume a model.

If D0 passes, one numerical training protocol may be drafted. If that single
Frontend-F2 attempt later fails the unchanged zero-flip A guard, the route
"new encoder directly reuses frozen P2" closes; no lambda, seed, architecture,
or threshold retry is allowed.

## 2. Frozen data boundary

The source-group split from Frontend-F1 remains immutable. These five sources
are internal validation and may not contribute a score, quantile, constant, or
training term in D0:

```text
normal_scanning1.pcap
iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0
iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0
iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0
iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0
```

The exact authorized universe is every D0 census row satisfying:

```text
legal_fit = true
owner = A
source_group not in the five frozen internal-validation sources
```

Required conservation is:

| label | rows |
|---|---:|
| benign | 6,171 |
| attack | 2,182 |
| total | 8,353 |
| semantic contexts | 4,994 |

The 4,400-row internal-validation split, all select data, viewed/report data,
and FINAL remain closed. In particular, the already diagnosed five-row
internal-validation file is not an input to this D0 and may not determine a
constant.

## 3. Pinned inputs

| input | SHA-256 |
|---|---|
| Frontend-F1 D1 numerical contract | `7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860` |
| D0 UID/context/phase/owner census | `c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9` |
| F1 fit-context corpus | `623d4e0bbec6ddfad4e98c08a9fc90df137e51e7692ff3453ac7f38c5e84097e` |
| teacher-benign UID verdicts | `f7deceac0ac76fb25e577714f7a94da047e15ed77cb9bee19a9ea9c2954c493b` |
| incumbent fit/select embeddings | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| incumbent probe state | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |
| incumbent threshold marker | `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |

The P2 threshold is `theta_0 = 0.065159872174263`, with
`score >= theta_0` hard, and
`z_0 = -2.6635317063752599`.

## 4. Physically selective access

The embedding NPZ UID and missing arrays may be opened for identity. The
`representation.npy` member must be streamed row by row as fixed-width opaque
bytes. Only the 8,353 authorized training-A rows may be converted to numeric
arrays. Required counters are:

```text
representation_container_rows_streamed_as_opaque_bytes = 25467
representation_rows_numeric_decoded = 8353
nonauthorized_representation_rows_numeric_decoded = 0
```

Every authorized row must have `missing=false`. The full representation array
may not be instantiated. No old select-score file may be opened.

Apply the pinned old normalizer and P2 using the previously audited float64
matrix computation. This D0 may compute and persist incumbent logits/scores
for the authorized 8,353 rows only.

## 5. Teacher correctness and non-cloning boundary

Classify each authorized row using its true fit label and incumbent decision:

- correct attack: label attack and old hard;
- correct benign: label benign and old normal;
- teacher-wrong benign: label benign and old hard;
- teacher-wrong attack: label attack and old normal.

The existing teacher-benign verdict file must agree row for row. The expected
training-A benign split is 6,145 old-normal and 26 old-hard. Any
teacher-wrong attack or count mismatch is
`F2_D0_TEACHER_IDENTITY_OR_SCOPE_FAILURE`.

Teacher-wrong benign rows may participate in ordinary supervised learning in a
future protocol but are permanently excluded from old-function preservation.
B rows never receive an incumbent teacher value.

## 6. Predeclared continuous-envelope derivation

All quantiles below use only the authorized training-A rows. Quantiles use
NumPy's deterministic order-statistic methods: `lower` for attack 5th
percentile and `higher` for benign 95th percentile.

Let:

```text
z_p99 = logit(0.99) =  4.595119850134589
z_p01 = logit(0.01) = -4.59511985013459

q_attack_05 = Q_lower(0.05, old logits of correct attacks)
q_benign_95 = Q_higher(0.95, old logits of correct benign)

c_attack = min(z_p99, q_attack_05)
c_benign = max(z_p01, q_benign_95)
```

For a future model, the per-row teacher violations are defined now as:

```text
correct attack:
  target_i = min(z_old_i, c_attack)
  v_i = ReLU(target_i - z_new_i) / (c_attack - z_0)

correct benign:
  target_i = max(z_old_i, c_benign)
  v_i = ReLU(z_new_i - target_i) / (z_0 - c_benign)
```

This is label-aware, one-sided, and clipped. It preserves incumbent evidence
without penalizing a new model for becoming more correct in the label-consistent
direction; it is not symmetric feature or logit cloning.

D0 passes the envelope-feasibility gate only if:

```text
c_attack > z_0 + 0.5
c_benign < z_0 - 0.25
both normalizers are finite and strictly positive
```

Otherwise the scientific state is
`F2_D0_NO_IDENTIFIABLE_CONTINUOUS_TEACHER_ENVELOPE` and no F2 training
protocol may be drafted.

## 7. Aggregation mismatch repair

Frontend-F1 used context-equal mean losses while acceptance required zero
protected-A flips. A mean-only continuous loss could again ignore a small
failure tail. A future F2 protocol therefore must include both:

```text
L_teacher_mean = mean_context(mean_eligible_target(v_i))
L_attack_worst = max_context(max_correct_attack_target(v_i))
```

`L_attack_worst` is a safety term, not a tunable mining fraction. No top-k,
CVaR fraction, family weight, source weight, or special five-row weight may be
introduced. Exact total-loss weights remain unopened until D0 has produced the
two normalization constants; they must then be frozen before any training.

## 8. Durable outputs

The result package must contain:

1. `f2_d0_train_a_incumbent_logits.csv.gz` with UID, context, source, device,
   family, label, old logit, old score, threshold margin, and teacher class;
2. `f2_d0_teacher_distribution.csv` with count/min/Q01/Q05/Q25/Q50/Q75/Q95/
   Q99/max by label and teacher class;
3. `f2_d0_source_family_distribution.csv` with all source/family counts and
   logit summaries, without suppression;
4. `f2_d0_envelope_constants.json` containing the exact order statistics,
   derived constants, normalizers, and feasibility predicates;
5. `f2_d0_scope_and_boundary_audit.json`;
6. `f2_d0_verdict.json`;
7. `SHA256SUMS`.

Raw values and per-source/family distributions are descriptive fit evidence.
They may not weaken the formulas or gates in this document.

## 9. Required zero counters

```text
internal_validation_representation_rows_decoded = 0
internal_validation_scores_computed = 0
select_scores_opened = 0
viewed_opened = 0
report_opened = 0
final_opened = 0
pcap_opened = 0
new_model_opened = 0
parameters_fitted = 0
optimizer_steps = 0
training_or_resume_started = 0
```

## 10. Authorization boundary

The user's 2026-09-04 instruction authorizes this training-side D0 audit and,
only if it passes, drafting the one-shot F2 numerical protocol. It does not
authorize F2 implementation/training, any second seed or fallback, threshold
changes, internal-validation continuous-score inspection, select/viewed/
report/FINAL access, or deployment.
