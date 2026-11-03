# Post-N3 whole-pool comparison design

Date: 2026-09-08.
Status: DESIGN_COMPLETE_INPUT_QUALIFICATION_PENDING.
Authority this turn: literature research, existing document/source/aggregate
metadata review, and design documentation only. This is not an executable
frozen protocol and grants no implementation, raw replay, inference or fitting.

## Decision and project purpose

Preserve the successful N3 candidate and next prepare a single comparison on
the COMPLETE original F1 internal-validation pool: 4,400 targets / 3,582 semantic
contexts. Compare this fixed candidate with the incumbent's existing decisions
on identical target UIDs. Do not train another model merely to obtain this test.

The user's priorities are (1) retain the old attack capability with the common
frontend and (2) establish benefit from formerly unsupported B traffic.
New-device commissioning remains downstream. Two kinds of B benefit must be
distinguished: useful decisions on B, and benefit CAUSED by including B in
training. The proposed comparison measures the first; matched training controls
would be needed for the second.

N3 already established a concrete finite-set repair: one final 65-parameter
head satisfies all 12,711 declared constraints on the unchanged representation,
retaining prior training judgments and B releases. Its success is reusable.
All six F5 development attacks entered N3 fitting, so that success alone cannot
answer whether other old-detectable attacks remain detectable.

The literature rationale and the methods deliberately not adopted are in
frontend_inheritance_post_n3_literature_review_20260908.md. The companion
frontend_inheritance_post_n3_design_evidence_20260908.json records source hashes.

## Candidate and reference

Only the sealed N3 witness is proposed, assembled from the same restricted F5
terminal model state with the N3 candidate_head.f32le replacing the final
Linear(64, 1). The current N3 runner documents the assembly semantics; do not
execute that historical runner again or accidentally install the N1 head.

| Identity | Existing recorded SHA-256 |
|---|---|
| N3 head bytes | e26bf80e8a45f605b806ed559afef0f3029f949a4c3cff00cf4aa6b7ef8d8d5a |
| N3 assembled tensor state | ff41638339604d4270ff5eef616885ef4b25bb075e8d1cd89dcb565ed10df3f9 |
| Fixed non-head tensor state | 29328fc616ef5b0197d1dcc8c564d89865201eb08b540d826847e233932dbe67 |
| N3 real output manifest | 5ef2be5e6f7f93626d12fd87e38efbdac33967a0e4a14bb11a59cd55c9795e43 |

These candidate identities are inherited from sealed records, not a new model
load in this design. Future assembly must reproduce them before inference and
remain unchanged afterward. Use the existing float32 CPU evaluation semantics,
whole causal contexts, fixed event indices, and hard = (logit >= 0).
No fitting, calibration, threshold adjustment, ensemble, candidate selection,
old-teacher forward, or F5/N1/N2/N3 replay is part of this proposal.

The incumbent is the old netFound/E3 + P2 detector. Reuse authorized, pinned
per-UID categorical decisions attached to the original F1 corpus; qualify their
provenance before use. A rows have an actual available incumbent decision.
For B, record the original missing-hard policy as an availability fallback,
not as a learned prediction or an invented teacher score.

The historical P2 97.3698% attack recall and 96.6786% future-query recall belong
to the old, different benchmark and remain unchanged. Never compare N3's 100%
fit success or this pool's rates against those percentages as an improvement.
The historical aggregate review also records CKDA_D1_WEAK_ONLY / GO_D2=false;
the earlier OOD problem is not resolved by this plan.

## Complete prospective population

Use the original F1 split identity internal_val, not the nested F5 internal_val
split and not an error-selected subset. No source re-splitting is proposed.

| Population | Targets | Contexts | Existing reference |
|---|---:|---:|---|
| A attack, ToN-reconnaissance_scan | 2,000 | 2,000 | All 2,000 incumbent hard |
| A benign | 1,176 | 688 | 1,174 incumbent normal; 2 incumbent hard |
| B benign | 1,224 | 894 | Missing-hard fallback; no B attacks |
| Complete pool | 4,400 | 3,582 | Five source groups / five members |

Source counts come from N0 sealed aggregate coverage and F1 materialization/
training-result documents. A0W = 1,176 - 1,174 = 2. Source/owner context counts
are aggregate census expectations, not a substitute for exact membership joins.

| Source group | A benign | B benign | A attack |
|---|---:|---:|---:|
| iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0 | 271 | 329 | 0 |
| iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0 | 266 | 334 | 0 |
| iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0 | 265 | 335 | 0 |
| iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0 | 374 | 226 | 0 |
| normal_scanning1.pcap | 0 | 0 | 2,000 |

B grouped denominators are iotsim-combined-cycle 998 targets / 844 contexts,
and iotsim-domotic-monitor 226 targets / 50 contexts. Preserve the actual
source and tier detail. There is no ToN benign group in this pool; the original
three-key F5 B floors cannot be declared passed on these two groups.

All 4,400 outcomes must be retained, including failures. The five F1 attack
failures previously used in frontend diagnosis are included through the full
membership rule and identified as previously error-selected exposure. They
must not become the only test or be removed from its denominator.

## Prospective measurements and interpretation

First require exact membership, input lineage, finite values, model identity
and complete execution. A preparation or numerical-integrity failure yields
INPUT_OR_EXECUTION_STOP, not a scientific failure or a partial-pool success.

For every target retain UID, source/member, semantic context and event index,
original split, A/B availability, label and literal behavior provenance,
incumbent categorical decision or missing reason, candidate logit and decision,
and paired correctness transition. Labels/reference decisions are reporting
metadata, never features or model-adaptation inputs.

1. Attack protection: count missed attacks among all 2,000 old-detected targets.
   Complete retention in this pool requires zero misses. Report recall and every
   failure; B gains cannot compensate for a new missed attack.
2. Benign protection: count new hard decisions among the 1,174 old-correct A
   benign targets. Complete retention requires zero new hard decisions.
   Separately report the two old-wrong A benign outcomes and full A benign FPR.
3. Paired A transitions: report old-correct/new-wrong and old-wrong/new-correct
   counts separately, stratified by attack/benign and source. If F is the
   old-correct/new-wrong count, A negative-flip rate is F / 3,176; conditional
   loss among old-correct A is F / 3,174. Do not interchange these denominators.
4. B observed utility: report normal target counts / 1,224, and contexts whose
   EVERY evaluated B benign target is normal / 894, plus per-key 998/844 and
   226/50 fractions and per-source/tier counts. The context metric concerns
   evaluated B targets, not every causal event or an entire physical device.
   Relative to missing-hard, these are avoided hard decisions and associated
   context releases. They do not establish B attack detection or causal training
   contribution. Do not invent scores for unavailable incumbent inputs.

This design sets no new 10% material-benefit floor and changes no old F5 gate.
B magnitude is descriptive. "Positive in both represented B groups" means
at least one all-evaluated-B-benign-normal context in EACH group; even that
statement is only an observation, not a material-benefit or deployment gate.

After integrity passes, report two separate result fields:
- A_retention = COMPLETE_ON_THIS_POOL or REGRESSION_ON_THIS_POOL, requiring both
  attack and benign protection for COMPLETE.
- B_utility = ZERO, PARTIAL (target releases or only one group's context release),
  or POSITIVE_IN_BOTH_REPRESENTED_GROUPS, always accompanied by exact counts.

Only complete A retention together with positive B observations in both groups
permits the phrase "scoped exposed-development retention and B utility evidence."
A regression ends this candidate test; preserve the full outcome and diagnose
before any separately designed intervention. Complete A retention with zero or
partial B utility identifies a remaining B problem. Neither branch permits
automatic refitting, relaxing gates, selecting a subset or repeating the run.

All outcomes retain broader_inheritance=NOT_PROVED, F5_eligible=false,
deployment=false, K=NOT_AUTHORIZED, and new_device=NOT_EVALUATED.
Do not label this comparison a rerun or reversal of the historical F5 outcome.

## Exposure and dependence limits

N0's catalog places these 4,400 targets outside the 13,866 F5 parent and thus
outside N3's declared fitting targets. Exact UID/context/source and learned-
component exposure joins still need qualification; aggregate counts do not
certify complete fit exclusion. If a proposed exclusion is contradicted, stop
and explain before changing this design or the population.

This pool was used in F1 validation/model-selection and later frontend
diagnosis. Therefore it is exposed development evidence even if all F5/N3
learned-component training exclusions are verified. Splitting it again would
not create an untouched holdout. Report direct fit, selection, representation
design, causal-prefix, and uncertain pretraining exposure separately.

The 2,000 attacks come from ONE source/member and have the literal reconnaissance
behavior. F5's 2,000 ToN training targets are credential-bruteforce. This is a
bounded comparison of an old-detectable behavior outside the declared F5/N3
target fit; it is not proof of matched-behavior transfer. Shared attack labels
or protocols do not fill that gap.

Physical-device identity, old sessions and earlier-history overlap remain
UNKNOWN in N0. Semantic context count is not independent-device count. Even
zero misses in 2,000 rows does not warrant an iid binomial population bound.
Report finite counts; no bootstrap or confidence interval that treats targets
or contexts as established independent units. Broader inheritance still needs
appropriate behavior coverage, fit/exposure provenance and independent units.
No suitable untouched confirmation reserve is claimed here.

## Input qualification and minimum implementation

The original F1 cache contains L0 signatures. The full 4,400-pool L1/F4 input
is not present in the current F4 parent; only five old kill prefixes were added
to the 13,866 parent. L0 must never be relabeled or padded into F4's 19-field L1.
F4's fieldwise mapping already passed and is reused unchanged at width 131.
This is missing input materialization, not a new frontend or repeat F4 audit.

The next implementation package should contain a metadata-only qualifier, a
bounded input-preparation worker, a fixed-candidate comparison worker, a
supervisor/status viewer and focused generated contract tests. Do not invoke
historical training/audit entrypoints for convenience.

Before any real replay/inference, qualify and seal:
- Exact 4,400 UID / 3,582 context membership, five container/member identities,
  original categorical teacher provenance and flags, including report=false
  and final=false; do not traverse other evaluation partitions.
- A field allowlist for existing fit metadata projection: identity, split,
  source/member/context/event position, labels/teacher category and provenance.
  Do not decode feature/signature arrays, score columns or model tensors during
  metadata qualification. Physical scanning of a known container is not a
  claim that its other bytes were never accessed; record parser projections.
- Exact exclusion joins with F5 train/development, N3 roles and relevant causal
  prefixes; inherited and unknown pretraining/session dependencies explicitly.
- Per-member raw path/hash and inclusive maximum packet position; decoder,
  endpoint/semantic engine and F3 L1/F4 pure mapping identities. Construct target
  descriptors from metadata, including expected context and event index.
- Replay semantics equivalent to the existing causal semantic engine: process
  each allowed member only through its last authorized cutoff, retain only
  required contexts/prefixes, verify target UID/context/index and available L0
  signature equality, then apply the unchanged L1-to-F4 mapping. No future
  target information may enter a causal prefix. Do not use F3's historical
  train-plus-five selection function for the whole validation pool.
- Exact decoded-packet count, stored context events, maximum prefix lengths,
  padded forward slots, batch plan, output-byte and worker resource ceilings;
  package and runtime pins plus a fail-closed supervisor. Aggregate maximum
  target prefix length is 49, not the raw scan-packet budget.

The exact raw cutoffs, new input digest and resource bounds are NOT established
by this design. Do not invent them from the old 829.7-second / 24-member F1
materialization or repeat a resource pilot. Derive bounds from qualified
metadata and existing runtime evidence. If they cannot be bounded, return the
specific gap before a launch proposal. Freeze executable rules before observing
new candidate predictions. Metadata qualification may stop on genuine identity/
semantic contradictions; routine coding choices do not require redesign.

Proposed execution envelope after implementation acceptance: one worker,
one bounded preparation of the five-member inputs, one restricted candidate
load/assembly, and one complete fixed-candidate comparison. Zero optimizer,
LP, backward, calibration, historical model reruns, retries or candidate changes.
Exact numerical resource caps remain a required implementation attachment.
Preparation and comparison have separate receipts and failure states; a single
explicit authorization may cover both once their concrete bounds are reviewable.
Current design authorization covers neither real operation.

The viewer should show NOT_STARTED, PREPARING_INPUTS, EVALUATING, COMPLETED or
STOPPED, progress denominators, last update and stop reason. Mark scientific
results complete only after the supervisor seal verifies, preserving the user's
ability to check completion without asking in chat. A design-complete status
must not look like a running or completed experiment.

## What proving the value of B training would require

N1/N2 used the F5 encoder already learned from A+B, including auxiliary and
causal-prefix exposure. Removing B from only the last-layer constraints is
not a no-B training arm. Comparing N3 against missing-hard measures system
availability/utility, not the causal effect of B learning.

If the fixed candidate first preserves A capability, a later contribution
study needs a prospectively matched A-only and A+B training pair from a common
pre-B initialization. Match A data/teacher evidence, algorithm, model capacity,
seed policy, stopping/selection and declared compute comparison. Exclude B from
EVERY learned component in the no-B arm, including normalization, auxiliary
losses and prefix exposure, according to a declared intervention.

Mixed A/B causal contexts require a precise estimand. Keeping B prefix events
while dropping B target losses measures B-supervision contribution only;
removing B events also changes A input histories. Choose and justify a common
support/context intervention before claiming total B-data benefit, and never
silently rewrite old membership or benchmarks. Freeze evaluation exposure and
behavior/source grouping for both arms before any training.

N3 cannot stand in for a matched A+B arm when its fitting algorithm and exposure
differ. Two new trainings may be required for causal attribution, but are not
the immediate next experiment or authorized here. The completed repair and
the proposed fixed-candidate check decide whether that expense is justified.

## Design completion record

Research consulted primary arXiv records and selected HTML sections; two
August/September 2026 papers are preprints, not independently validated methods.
No new architecture is proposed. A self-review checked paired denominators,
source dependence, B-control contamination, missing L1 inputs, zero-tie
semantics, candidate identity and separation of scientific versus input stops.
This is not a claim of independent external or subagent review.

Only documentation is changed in this stage. No raw-capture replay, model
tensor load, logits, optimization, historical experiment, resource pilot,
dataset/checkpoint download, HPC or locked evaluation access was performed.
The eight pre-existing unrelated tracked modifications remain protected.
