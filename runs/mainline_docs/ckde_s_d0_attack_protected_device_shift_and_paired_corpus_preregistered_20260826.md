# CKDE-S D0 — attack-protected device-shift and paired-corpus feasibility (FROZEN)

**Date:** 2026-08-26
**Status:** FROZEN; NON-EXECUTABLE pending independent SHA/diff verification and separate Lane G/Lane M authorizations
**Route:** one remaining capability attempt after CKDE-Q scalar calibration closure and
CKDE-R state-A identifiability stop

## 1. Decision question

CKDE-S preserves the operational premise that a newly enrolled device may provide a short,
explicitly benign commissioning prefix.  It does **not** move the scalar P2 threshold and does
not fit a new detector.  It asks whether the frozen E3/P2 system can remove only a stable,
low-rank device-nuisance shift while protecting directions to which the frozen attack head is
sensitive.

This D0 answers two independent questions before any new bulk-data download or method run:

1. **Internal geometry:** do the 15 legal fit-benign devices identify a stable removable device
   subspace, and do the 4,385 legal fit attacks identify a non-degenerate attack-protection
   space without silently treating device shift as attack evidence?
2. **External evidence:** does one bounded public candidate preserve the exact same-device
   structure needed to evaluate benign-prefix commissioning on later benign and attack traffic?

CKDE-R state A is interpreted as a data-identifiability result, not as evidence that
representation commissioning is ineffective.  CKDE-Q remains closed: its threshold-level
calibration has zero safe score margin and is not reopened by CKDE-S.

## 2. Fixed scope and non-goals

### 2.1 Fixed detector

- frozen E3/netFound representation width: 768;
- frozen P2 head, preprocessing, session construction, and zero-shot decision semantics;
- no E3 fine-tuning, P2 retraining, threshold movement, per-device hyperparameter search, or
  family/source routing;
- no reuse of localwin checkpoints in formal HPC replay.

### 2.2 Explicit non-goals

- no generic full-dimensional CORAL or 768-coordinate diagonal affine adapter;
- no scalar z-score, conformal alarm, threshold shift, M7 veto, or renamed AND/OR fusion;
- no hydraulic-specific rule;
- no search beyond the two preregistered public candidates;
- no claim of broad unseen-industrial-device generalization from one external corpus;
- no report/FINAL access, no new training, and no bulk download in D0.

## 3. Pinned existing evidence

The executable FROZEN version must pin the byte identities of all inputs before implementation.
The draft fixes the semantic identities below:

| Input | Frozen fact |
|---|---:|
| `ckda_d1_fit_select_embeddings.npz` | 25,467 rows x 768 dimensions |
| matching embedding metadata | exact UID join; role/device/session/family provenance |
| CKDE D0 device census | 15 legal fit-benign devices |
| legal fit attack slice | 4,385 rows, 5 devices, 12 family/stratum labels |
| CKDE-R Audit-0 result | no same-device prior benign center; no 2x2 cycle |
| CKDE-Q Stage A result | 23/23 primary devices and 123/123 computable arms fell back |

The current known embedding identities are inherited from CKDE-R D0:

```text
runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/
  ckda_d1_fit_select_embeddings.npz
  ckda_d1_fit_select_embeddings.npz.metadata.csv.gz
```

No implementation may infer an alternative embedding file by glob or newest timestamp.

## 4. D0 execution order and isolation

Two lanes may run independently but must emit separate verdicts:

```text
Lane G: existing fit-only geometry audit
  G0 identity/schema/role gate
  G1 count-only rank materialization
  G2 benign device-subspace estimability
  G3 attack-direction contamination and protection-space audit
  G4 removable-subspace verdict

Lane M: metadata-only paired-corpus reconnaissance
  M0 fixed candidate order and official-source allowlist
  M1 N-BaIoT metadata audit
  M1R hash and seal candidate-1 terminal verdict plus literal reason codes
  M1K blocking independent Kimi review of the sealed candidate-1 verdict
  M2 CICIoT2023 metadata audit only after an explicit M1K PROCEED ruling
  M3 paired-corpus verdict

Joint state = mechanical combination of Lane G and Lane M.
```

Lane M may not read outcome scores.  Lane G may not make any network request.  Neither lane may
open report/FINAL artifacts.  Candidate-2 metadata may not be opened after candidate 1 passes.
Candidate-2 retrieval is also forbidden after candidate-1 failure until the candidate-1 verdict,
reason codes, and digest have been independently reviewed by Kimi and an explicit `PROCEED_CANDIDATE_2`
ruling has been recorded.  Failure to obtain that ruling leaves Lane M terminally paused; it does
not authorize an automatic fallback.

## 5. Lane G — count-only device-subspace definition

### 5.1 Session unit and eligible devices

The independent unit is one complete causal session embedding, never one record.  A fit-benign
device is eligible only if it has at least 64 complete legal fit-benign sessions.  Every output
reports devices, independent sessions, and records.

Device centers use the coordinatewise median of session embeddings.  The global benign center
is the equal-device coordinatewise median of eligible device centers.  Record count never gives
a device extra weight.

### 5.2 Rank rule frozen before any embedding statistic

Let `D` be the count of eligible fit-benign devices after metadata-only eligibility checks.

```text
r_count = min(4, floor((D - 1) / 3))
```

Requirements:

- `D >= 9` and `r_count >= 2`; otherwise Lane G stops with
  `NO_IDENTIFIABLE_DEVICE_SUBSPACE_BY_COUNT` before opening embeddings;
- with the currently expected `D=15`, the unique count-only rank is `r_count=4`;
- no eigengap, explained variance, benign FPR, attack score, or downstream outcome may choose
  the rank;
- failure of rank-4 stability does not authorize trying ranks 3/2/1.  A lower-rank method would
  require a new preregistration, not an in-run downgrade.

This deliberately gives CKDE-S one candidate rather than a hidden rank sweep.

## 6. Lane G — benign device-subspace estimability

Let `c_d` be each eligible device center and `c_g` the equal-device global center.  Stack
`c_d-c_g` as rows and obtain the top `r_count` right singular vectors `U`.

### 6.1 Deterministic leave-one-device-out stability

For every eligible device `d`, refit `U_-d` without `d`.  Report:

- normalized projection-matrix distance
  `dist(U,U_-d) = ||P_U-P_U-d||_F / sqrt(2*r_count)`;
- largest principal angle;
- per-device and worst-device values.

Proposed literal gate for review:

```text
median projection distance <= 0.20
AND worst-device projection distance <= 0.35
AND median largest principal angle <= 20 degrees
AND worst-device largest principal angle <= 35 degrees
```

### 6.2 Between-device signal versus within-device drift

Each eligible device is split causally into early and late session halves.  Define:

- `B_d = ||P_U(c_d-c_g)||_2`, the modeled between-device displacement;
- `W_d = ||P_U(c_d_early-c_d_late)||_2`, projected temporal drift;
- `R_d = B_d / max(W_d, 1e-12)`.

Proposed gate for review:

```text
median R_d >= 2.0
AND at least 80% of devices have R_d >= 1.0
AND no device has non-finite values
```

The complete distributions are reported.  Macro summaries may not conceal the worst device.

Failure of either §6.1 or §6.2 yields `UNSTABLE_OR_TEMPORAL_DEVICE_SUBSPACE` and stops Lane G.

## 7. Lane G — attack-protection space and decontamination audit

The attack-protection space is defined from the **frozen P2 sensitivity**, not only from an
attack-mean-minus-benign-mean contrast.  This avoids silently equating the five attack devices'
unobserved domain shifts with attack evidence.

### 7.1 Frozen gradient construction

For every legal fit-attack embedding `z`, compute the gradient of the frozen P2 attack logit with
respect to `z`.  Gradients are normalized per row before aggregation.  For each eligible exact
family with at least 15 independent attack sessions, form one equal-session robust median
gradient `g_f`.  Let `V_raw` be the orthonormal span of these family directions after a literal
SVD tolerance fixed in the FROZEN version.

The fit-attack labels select only the already-frozen exact family strata; they may not select a
model, rank, threshold, or device rule.

### 7.2 Contrast audit and contamination accounting

For each eligible family, also compute the descriptive contrast

```text
a_f = median(family attack embeddings) - c_g
```

and report:

```text
rho_f = ||P_U a_f|| / max(||a_f||, 1e-12)
residual_f = ||(I-P_U)a_f|| / max(||a_f||, 1e-12)
```

These values audit how much a naive attack contrast would be contaminated by the benign-learned
device subspace.  They do **not** weaken the protected gradient space.  The assumption that the
benign-device subspace spans nuisance movement on the five attack devices is named
`BENIGN_SUBSPACE_TRANSPORTS_TO_ATTACK_DEVICES` and remains unproven until paired external data.

Proposed residual identifiability gate for review:

```text
every eligible major family has residual_f >= 0.50
AND at least 80% of all eligible families have residual_f >= 0.65
```

Failure yields `ATTACK_DIRECTION_NOT_IDENTIFIABLE`.

### 7.3 Removable subspace

Orthogonalize the benign device basis against `V_raw`:

```text
U_remove = orth((I - P_Vraw) U)
```

The candidate is non-degenerate only if:

```text
rank(U_remove) >= 1
AND ||P_Uremove P_Vraw||_2 <= orthogonality_tolerance
AND at least 25% of median between-device energy remains in U_remove
```

The exact SVD and orthogonality tolerances must be literals in the FROZEN version.  If the
protected attack space consumes the entire device subspace, CKDE-S stops with
`NO_ATTACK_ORTHOGONAL_DEVICE_NUISANCE` rather than relaxing protection.

## 8. Reserved D1 mechanism — not authorized by D0

If both D0 lanes pass, a later preregistration may define exactly one primary transformation:

```text
v_d = robust center(prefix sessions) - c_g
beta_d = globally frozen shrinkage estimator of P_Uremove v_d
z_adapted = z - lambda * U_remove * beta_d
```

Only the **estimator formula**, session budget, shrinkage constant, coefficient norm cap, and
global `lambda` are frozen in advance.  The numerical `beta_d` for a new device is legitimately
computed from that device's benign prefix; it is not a per-device tuned hyperparameter.

The frozen E3 and P2 remain unchanged.  A later D1 must include zero-shot, center-only
attack-protected projection, contamination stress, and exact fallback.  No full CORAL arm is
implicitly authorized.

## 9. Lane M — bounded paired-corpus reconnaissance

### 9.1 Fixed order and hard stop

1. **N-BaIoT** — primary metadata candidate;
2. **CICIoT2023** — backup metadata candidate, audited only after N-BaIoT fails **and** the
   blocking review below authorizes candidate 2.

The first candidate satisfying every acceptance condition ends the search.  If candidate 1
passes, candidate 2 is never opened.  If candidate 1 fails, its terminal verdict and literal
reason codes are written atomically, hashed, and sealed before any candidate-2 request.  That
sealed artifact is delivered to Kimi for an independent blocking review.  Candidate 2 may start
only after a committed review records the exact candidate-1 digest and an explicit
`PROCEED_CANDIDATE_2` ruling.  A missing, mismatched, or non-proceed ruling is fail-closed and
leaves candidate 2 unopened.

The review may verify protocol compliance and decide whether the preregistered fallback is still
scientifically admissible; it may not alter candidate-2 acceptance conditions in response to the
candidate-1 failure reason.  The candidate-1 reason cannot be used to relax, reinterpret, or add
candidate-2 criteria.  If both candidates fail, CKDE-S external commissioning is moved to future
work.  No third dataset may be searched under this route.

### 9.2 Official-source boundary

Only publisher, repository-owner, DOI landing-page, and original-paper sources are admissible.
Search-engine snippets, mirrors, Kaggle copies, derived CSV repositories, and third-party
repackagings cannot establish eligibility.

Metadata retrieval may read HTML, README, checksums, manifests, licenses, and published file
inventories.  It may not download PCAP archives, ZIP/TAR package bodies, model weights, or large
feature tables.

### 9.3 Mechanical corpus acceptance conditions

A candidate passes only if all are established before bulk download:

1. a stable physical-device key exists and is recoverable without labels derived from outcomes;
2. the same device key has an explicitly benign population and an explicitly attacked
   population;
3. benign chronology supports a causal commissioning prefix followed by a disjoint benign
   suffix;
4. attack traffic is attributable to that same physical device and reserved as a suffix/outcome,
   never adaptation input;
5. ordered raw PCAP or an equivalent packet sequence with timestamps, directions, protocol and
   packet lengths is downloadable; a 115D/flow-feature-only release fails;
6. at least 6 physical devices meet conditions 1-5;
7. at least 3 of those devices have at least 2 attack families each, unless the original corpus
   contains only one family by construction, in which case the candidate fails rather than
   weakening the gate;
8. license permits academic use and reproducible derived artifacts;
9. pretraining/source overlap with E3/netFound and the current fit/select/report corpus is
   classifiable as `KNOWN_DISJOINT`, `POSSIBLE_OVERLAP`, or `KNOWN_OVERLAP`;
10. total bytes, extracted-size estimate, target volume, and cleanup plan are known before any
    download authorization.

`POSSIBLE_OVERLAP` cannot support a clean external-generalization claim. `KNOWN_OVERLAP` fails
the candidate for positive external confirmation.

### 9.4 Candidate-specific failure checks

For N-BaIoT, verify that the publicly accessible artifact contains raw ordered captures per
device, not only the released 115-feature tables.  For CICIoT2023, verify that experiment-level
captures preserve same-physical-device victim identity and a defensible benign-before-attack
chronology; aggregate scenario PCAP alone is insufficient.

### 9.5 Reserved zero-shot challenge-relevance gate

Metadata eligibility alone cannot make a corpus positive evidence for commissioning.  Before any
external E3/P2 score is opened, the later paired-data execution protocol must freeze an exact
numeric, device-level zero-shot benign-shift challenge criterion, its aggregation unit, minimum
support, confidence procedure, and terminal reason code.  The exact numeric form is intentionally
reserved for that later protocol because D0 opens no external scores, but the following principle
is frozen now:

- the criterion is frozen from metadata/count evidence before score access and before any adapter
  output;
- development and wholly untouched devices are fixed by deterministic hash before evaluation;
- the gate is **kill-only**: it may disqualify a corpus from positive method evidence but may not
  select a transform, rank, constant, fallback, or alternate corpus;
- if the zero-shot detector already lacks a material benign-shift problem on the external corpus,
  the corpus cannot be promoted as evidence that CKDE-S repaired device shift.  It may be reported
  only as the negative diagnostic `NO_ZERO_SHOT_BENIGN_SHIFT_TO_REMOVE`;
- a relevance-gate failure does not authorize searching another dataset or revising the gate.

This gate prevents an easy external corpus from manufacturing a positive commissioning result.

## 10. External split reserved for the later data protocol

Metadata D0 does not create the split, but it must prove that the following can be frozen without
opening model outcomes:

- physical devices are the split unit;
- deterministic hash split with at least 2 wholly untouched devices;
- development devices may provide benign prefix/suffix and attack suffix;
- untouched devices' attack suffix remains sealed until the transform and all constants are
  frozen;
- attack suffix never enters subspace learning, commissioning, coefficient estimation, fallback,
  thresholding, or model choice.

One passing corpus supports a bounded external mechanism-validation claim, not broad industrial
generality.

## 11. D0 verdict state machine

Lane G:

1. `G0_NO_IDENTIFIABLE_DEVICE_SUBSPACE_BY_COUNT`
2. `G1_UNSTABLE_OR_TEMPORAL_DEVICE_SUBSPACE`
3. `G2_ATTACK_DIRECTION_NOT_IDENTIFIABLE`
4. `G3_NO_ATTACK_ORTHOGONAL_DEVICE_NUISANCE`
5. `G4_INTERNAL_GEOMETRY_FEASIBLE`

Lane M:

1. `M0_NBAIOT_METADATA_ELIGIBLE`
2. `M1_NBAIOT_FAILED_PENDING_KIMI_REVIEW`
3. `M2_CICIOT2023_METADATA_ELIGIBLE`
4. `M3_NO_IDENTIFIABLE_PAIRED_RAW_CORPUS`

`M1_NBAIOT_FAILED_PENDING_KIMI_REVIEW` is a real blocking state.  It cannot transition to
candidate 2 without a digest-matched `PROCEED_CANDIDATE_2` ruling.  A candidate-1 PASS is
terminal and never enters M1.

Joint:

```text
if Lane G != G4:
    CKDE_S_NO_GO_INTERNAL_GEOMETRY
elif Lane M == M1:
    CKDE_S_PAUSED_FOR_INDEPENDENT_CANDIDATE_REVIEW
elif Lane M == M3:
    CKDE_S_FUTURE_WORK_NO_PAIRED_CORPUS
else:
    CKDE_S_READY_FOR_PAIRED_DATA_PROTOCOL_DRAFT
```

No D0 verdict authorizes bulk download, adapter execution, training, score evaluation, HPC, or
FINAL access.

## 12. Required outputs

Lane G:

```text
ckde_s_d0_input_identity.json
ckde_s_d0_count_rank.json
ckde_s_d0_device_subspace_stability.csv
ckde_s_d0_between_within_by_device.csv
ckde_s_d0_attack_gradient_by_family.csv
ckde_s_d0_attack_contrast_contamination.csv
ckde_s_d0_removable_subspace_audit.json
ckde_s_d0_role_open_audit.json
ckde_s_d0_geometry_verdict.json
```

Lane M:

```text
ckde_s_d0_candidate_retrieval_plan.json
ckde_s_d0_candidate_metadata_evidence.csv
ckde_s_d0_candidate_device_pairing_inventory.csv
ckde_s_d0_license_and_lineage_audit.csv
ckde_s_d0_storage_plan.csv
ckde_s_d0_candidate1_terminal_verdict.json              # candidate-1 failure only
ckde_s_d0_candidate1_terminal_verdict.json.sha256       # candidate-1 failure only
ckde_s_d0_candidate2_activation_review.json             # M1-to-M2 transition only
ckde_s_d0_corpus_verdict.json
```

Joint:

```text
ckde_s_d0_joint_verdict.json
ckde_s_d0_validation_report.json
SHA256SUMS
```

Engineering failure removes all scientific verdict files and emits only an engineering-failure
record plus preserved diagnostic evidence.

## 13. Contract-test requirements

The FROZEN version must require tests for at least:

1. exact pinned-input identity and schema;
2. role/device/session joins and duplicate rejection;
3. count-only rank selection before embedding open;
4. `D<9` and `r<2` fail-closed branches;
5. equal-device rather than record-weighted centers;
6. deterministic causal early/late session split;
7. leave-one-device-out subspace stability formulas;
8. between/within temporal-drift formulas and worst-device guards;
9. frozen P2 identity and correct attack-logit gradient;
10. per-session normalized gradients and equal-family aggregation;
11. attack contrast contamination/residual formulas;
12. removable-subspace rank and orthogonality checks;
13. no post-result rank downgrade or alternate candidate;
14. official-source host allowlist and redirect closure;
15. metadata byte caps and bulk-body rejection;
16. N-BaIoT raw-PCAP versus feature-table distinction;
17. CICIoT physical-victim identity and chronology requirement;
18. first-pass candidate stops backup retrieval;
19. no third-candidate path;
20. license and lineage state semantics;
21. deterministic device-hash split feasibility without outcome access;
22. attack suffix excluded from every adaptation input;
23. no report/FINAL/PCAP/training access in Lane G;
24. no embedding/score access in Lane M;
25. verdict priority, atomic writes, readback, and complete hashes;
26. engineering failure has no scientific verdict;
27. Python 3.9 grammar, runtime API, and historical regression gates;
28. candidate-1 terminal verdict and literal reason codes are atomic, hashed, and read back;
29. candidate 2 is unopened until a digest-matched explicit Kimi `PROCEED_CANDIDATE_2` ruling,
    while candidate-1 PASS permanently blocks candidate 2;
30. the later paired-data protocol cannot open external scores before freezing the exact
    zero-shot challenge-relevance criterion;
31. a corpus with no material zero-shot benign-shift problem yields only
    `NO_ZERO_SHOT_BENIGN_SHIFT_TO_REMOVE`, never positive method evidence or a new corpus search.

## 14. Claim boundary

Even a D0 PASS means only that one low-rank attack-protected transform is identifiable enough to
preregister and one external corpus appears capable of evaluating it.  It does not show benign
FPR improvement, attack preservation, contamination robustness, unseen-family generalization,
or deployability.

A later positive claim requires a fully frozen paired-device experiment and untouched-device
one-shot evidence.  It also requires the preregistered zero-shot challenge-relevance gate to
establish that there was a material benign-shift problem to repair.  Passing metadata eligibility
or obtaining good zero-shot performance is not positive CKDE-S evidence.  FINAL remains
separately sealed.

## 15. Normative review rulings

The eight draft questions are closed as follows:

1. rank rule `min(4, floor((D-1)/3))`: accepted without in-run downgrade;
2. leave-one-device-out stability constants: accepted with worst-device guards;
3. between/within gates: accepted as drafted;
4. frozen-head gradients are the primary attack-protection space; mean contrasts remain
   diagnostic only;
5. residual-fraction gates 0.50/0.65 and 25% removable-energy floor: accepted;
6. external minimum of six paired devices and three dual-family devices: accepted;
7. candidate-1 failure enters a digest-pinned blocking Kimi review; candidate 2 never starts
   automatically and cannot inherit relaxed criteria;
8. a zero-shot challenge-relevance gate is mandatory and kill-only; its exact numeric form must
   be frozen in the later external execution protocol before any external score is opened.

## 16. Authorization boundary

This FROZEN protocol authorizes no implementation or execution.  After independent SHA/diff
verification, Lane G implementation/execution and Lane M implementation/execution each require
separate explicit user authorization.  Embedding opening, network metadata retrieval, bulk
download, training, adapter execution, score opening, HPC, report, and FINAL remain separately
unauthorized unless a later gate explicitly permits the bounded action.
