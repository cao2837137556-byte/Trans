# N2 fixed-witness development check and inheritance decision protocol

Date: 2026-09-08. Status: `N2_DESIGN_FROZEN_IMPLEMENTATION_AND_REAL_CHECK_NOT_AUTHORIZED`.
Base: codex/exp-mainline, 4b28747b09480471e2bac1beb3a9badf27280efb.
The user authorized next-stage design and review after N1. This document does
not authorize implementation, synthetic numerical tests or real N2 evaluation.
Those are subsequent stages. No new fitting or evaluation occurred in this design.

## 1. Decision and value of the next observation

Keep the N1 witness fixed and perform one prospective, separately authorized
check on the existing 5,206-row F5 exposed-development validation set. N2 asks
whether the repaired fixed model's joint training decisions extend to these
particular development inputs, and measures the original B-benign release gates.
It does not fit a head, change an input, calibrate a threshold or select a model.

N1 established exact/float32 protected joint fit for 6,914 training targets;
all 8,660 original training targets were float32-correct. It did not evaluate
the development pool. Check this fixed candidate before deciding whether a
coverage intervention is needed. Successful extrapolation does not require
retroactively manufacturing normal training coverage; failure identifies a
specific next question but does not uniquely identify its cause.

This is a new diagnostic of the N1 witness, not a retry, selected-checkpoint
rescue or reopening of F5 K. F5 remains NO_ELIGIBLE_CHECKPOINT under every N2
outcome. N1 stays closed. The shared A+B GRU and its own student head remain
the research object; the old system stays the deployment incumbent. No old
P2/E3 model is called or installed as the new representation's inference head.

## 2. Evidence map and the unresolved inheritance question

Read the sealed N0 aggregate coverage tables; do not repeat its raw inventory.
The current catalog distinguishes these evidence accounts:

| Account | Existing evidence | Limit |
|---|---|---|
| Joint training fit | N1: all 8,660 training judgments correct; 6,914 also exact-verified | Finite-set evidence only |
| Retention during N2 | Identical model, input semantics and numerical runtime; no parameter update | No claim of retention under future learning |
| F5 development A attacks | 3 targets / 1 context, Ingress Tool Transfer | Already exposed; recorded family absent from F5 train |
| F5 development B attacks | 3 targets / 2 contexts, File Download | Already exposed; recorded family absent from F5 train |
| Old F1 development attacks | 2,000 targets / 2,000 contexts, ToN-reconnaissance_scan | Already exposed, outside F4 parent and outside N2; recorded family absent from F5 train |
| ToN benign coverage | normal_1: 4,000 targets / 3,667 contexts, all F5 exposed validation | Zero F5 training targets; no second lawful source identified by N0 |
| Same-behavior inheritance confirmation | No qualifying reserve identified in this catalog | Behavior match, parameter-fit exclusion and dependency separation remain unresolved |

F5 training has nine recorded attack-family names: ToN-credential_bruteforce,
Merlin TCP Flooding, Merlin UDP Flooding, Mirai TCP Flooding, Mirai UDP Flooding,
Merlin ICMP Flooding, Mirai GRE Flooding, Mirai C&C Communication and Merlin
C&C Communication. Neither F5 nor old F1 development attack-family names
intersect that list. This is a literal metadata observation, not a proof that
all underlying behavioral mechanisms are unrelated. Do not rename families or
treat every attack label as a matching inherited behavior.

The original inheritance objective still includes old-system capabilities that
the GRU's training coverage may not represent. It is not reduced to memorizing
the original training labels. N2 attacks are useful transfer counterexamples
or successes, but six exposed targets cannot close this broader objective.
Passing F5-style numerical gates is not sufficient evidence for general
inheritance, B-family detection, new-device success or a population risk bound.

Source groups, artifact members and semantic contexts are not certified
independent physical devices or old sessions. Neither re-splitting a source nor
holding it out only after the encoder has fitted it creates a clean holdout.
Previously inspected validation remains development data even when renamed.

## 3. Sole candidate and preservation by identity

The companion `frontend_inheritance_n2_input_and_evidence_pins_20260908.json`
defines immutable input, evidence and runtime identities. Verify both design
sidecars, the complete inherited pin bundle, selected additional pins and their
manifest agreement before corresponding access. Follow only explicitly named
members; a manifest entry does not itself authorize opening its payload.
The pinned N1 implementation receipt must report its accepted 36-test/two-script
state, with nine matching code identities and seven matching runtime identities;
all overlapping pin values must agree. This is historical provenance, not N2
implementation acceptance.

Assemble exactly one model from the original F5 terminal resume.pt plus N1's
260-byte candidate_head.f32le. The latter is 65 little-endian float32 values:
first 64 weights in the existing Linear(64,1), then its bias. Copy these exact
bits without another float64 cast, clipping, rescaling, bias repair or selection
from candidate_head.json. That JSON is provenance to hash, not another numeric
candidate source.

Before installing the N1 head, the complete loaded terminal state must have
F5 tensor_hash `131d15e7a586a6fb105995ecb25d56f8217351c03b60495c56d6e1b723db1bcc`.
All state entries other than head_output must retain tensor_hash
`29328fc616ef5b0197d1dcc8c564d89865201eb08b540d826847e233932dbe67`.
These include semantic_head. Head bytes must hash to
`e6ac6c418253595b46308f654d339f8dfa16be971572fa282c9588c5c43f497e`.
Architecture, activations and forward semantics come from the pinned F5 core.
Compute and seal the assembled complete-state hash before development feature
decoding; require that complete-state hash unchanged after the one forward.

Check the sealed N1 supervisor verdict, worker counts/access summary, exact
check and all-category outcome summary. The required historical state is
N1_JOINT_HEAD_WITNESS, one LP/two passes, no new validation numeric access, exact
protected PASS and zero candidate errors in all five training categories.
Do not numerically open N1 target64 arrays or re-forward training inputs.
Preservation of N1's prior result is by verified identity, not a new training
test. No full-model deployment checkpoint is produced or promoted by N2.

## 4. Exact development membership and metadata access

Use the literal original F4/P `internal_val` selector, without reallocation:

| Category | Targets | Rule |
|---|---:|---|
| A1C | 3 | All attack |
| A0C | 1,478 | All normal |
| B1N | 3 | All attack |
| A0W | 2 | Report outcomes, not a protected-normal gate |
| B0N | 3,720 | Original per-key B utility accounting |

There are 1,484 protected targets, 3,722 accompanying targets, 5,206 targets
total and 4,323 contexts. Attack support is six targets / three contexts.
Four source groups are fixed:

| Literal source_group | Targets | Contexts |
|---|---:|---:|
| iotsim-combined-cycle-6_0-0_to_OpenvSwitch-13_6-0 | 600 | 464 |
| iotsim-domotic-monitor-3_0-0_to_OpenvSwitch-23_3-0 | 600 | 189 |
| normal_1.pcap | 4,000 | 3,667 |
| processed/iotsim-combined-cycle-10.csv | 6 | 3 |

Within normal_1, A0C has 843 targets / 672 contexts, and B0N has 3,157 targets /
2,995 contexts. Other protected A benign targets number 635. Preserve exact
device-family strings, including combined-cycle versus iotsim-combined-cycle;
do not normalize them into one key. Derive other group context unions from the
authorized metadata; do not sum overlapping target-category counts.

Allowed parser projections in a future real N2 authorization:

- F4 context index: all five declared columns on all 9,307 rows, to verify
  source/split membership, contiguous offsets and 205,470 stored events.
- F4 target audit: uid,nested_split,context_key selectors on all 13,866 rows;
  event_index,prefix_events,source_group,owner,label,teacher_kind,device_family,
  attack_family,feature_prefix_sha256,finite,roundtrip_exact,feature_width only
  on the 5,206 internal_val rows. Do not read l1_prefix_sha256 or old_all_unk.
- P uid_scope: uid,split,context selectors on all 13,866 rows; source,owner
  only on internal_val. Require exact selector and selected-payload UID joins.
- F3/P identity/source metadata, P category census, N0 sealed aggregate coverage
  and N1 declared identity/result summaries may be parsed. They do not authorize
  traversing referenced raw inputs, old teachers or earlier trial outputs.

CSV/JSON parsing transiently materializes mixed metadata containers. Disclose
tokenized cells, selector accesses, selected payload and retained evidence.
Training target payload columns and training feature bytes are not numerically
read in N2. Existing N1 result summaries remain identified historical evidence.
No old F1 mixed corpus, normal_2, select/viewed/report/FINAL or kill-only payload
is an N2 input. No PCAP, source download, teacher vector/probe or teacher.csv.

## 5. Restricted model-container and development feature access

The original resume.pt remains a full 1,712,912-byte container. Use one
receipt-verified restricted torch.load(..., map_location="cpu", weights_only=True)
with only these literal safe globals: numpy._core.multiarray._reconstruct,
numpy.ndarray, numpy.dtype, numpy.dtypes.UInt32DType. Exclude ambient additional
safe globals during loading. No automatic allowlist discovery or unrestricted
pickle fallback. Incompatibility gives N2_NEEDS_GOVERNED_MODEL_EXPORT.

Retain model and identities plus the minimal terminal reference: progress
epoch/cursor/order/steps/stop state, selection best_epoch/last_epoch and only
the last epoch ledger's epoch, val_violations and val-prefixed gate_counts.
Check progress 21/0/[]/3120/stopped, no selected epoch, last epoch 20. No earlier
epoch values may be inspected or used for alternative candidates. Other ledger
contents, optimizer and RNG are incidentally materialized then discarded without
use. Do not instantiate an optimizer, restore RNG or execute a training loss.
Unlike N1, this explicitly authorizes projection of the final old development
reference in the future N2 real stage; it is not a fresh N2 measurement.

The historical protected development violation list must reconcile to 846 UIDs:
3 A attacks plus 843 A0C normal_1 targets and zero B attacks. Check UID/category
membership and final gate target/flip counts. Use this saved list to report
protected newly-wrong/newly-correct UIDs. It does not supply per-UID baseline
predictions for unprotected rows; do not invent those or run the old head again.

Hash the whole 107,666,280-byte F4 feature binary opaquely. Before decoding,
seal the exact selected UID/context/range attachment and selected event count.
Seek/read only each internal_val context's prefix ending at its last selected
target, with byte offset = event_offset * 131 * 4 and byte length = prefix * 131 * 4.
Require finite little-endian float32 values, exact length and original target
prefix hashes SHA256(b"F4_INPUT_V1\0" + pack("<II", prefix,131) + prefix_bytes).
Do not load/memmap the full parent or decode any train interval.
This verifies identity; it does not repeat F4's fieldwise experiment.

## 6. One canonical forward, no parameter fitting

Use the inherited Python 3.9.13, NumPy 2.0.2, torch 2.8.0+cpu runtime and pinned
files. Preserve PYTHONHASHSEED=2705, OMP_NUM_THREADS=4, MKL_NUM_THREADS=4,
torch intra-op 4/interop 1 and deterministic algorithms. Construction seed 2705
does not define another candidate; all model parameters are overwritten by
the fixed assembly. No package upgrade or alternate-runtime attempt.

Run the unchanged F5 Student in model.eval() under literal torch.no_grad().
Sort all selected contexts lexically and batch 32: exactly 136 batches. Preserve
the original (-length,key) internal sort, packed GRU, per-context zero state,
GELU approximate="none" and full-context Linear invocation. The unchanged
forward computes unused semantic outputs and hidden states; do not inspect,
cache or use them for a new representation, teacher comparison or fit.

Extract each authorized target logit from its full-context output, without a
target-only GEMM. The only hard decision is actual float32 q>=0 for attack,
q<0 for normal. No sigmoid-derived comparison, margin tolerance, ROC threshold,
device threshold, normalization, probability calibration or loss-based selection.
Record finite logits, hard judgments and signed margins for all 5,206 targets.
These are prescribed evaluation outputs, never an N2 fitting input.

Only this assembled N1 candidate is evaluated. There is no old-terminal forward,
training replay, second candidate, extra exact arithmetic sweep or solver call.
Complete the full set even when a scientific gate fails early, unless an
integrity/access/resource stop prevents completion. Partial outputs cannot pass.

## 7. Fixed measurements and outcome priority

Report all five category counts, errors, target/context/source counts and signed
margin summaries. Report each of the six attack UIDs and its literal recorded
family, context and source. Separately report normal_1 A/B and other A0C errors.
The broad group summary must not hide attack failures behind benign accuracy.

Protected development check: all 3 A attacks and 3 B attacks hard, and all
1,478 A0C targets normal. The two A0W rows have no added protection requirement.
N1 training protection is cited only through its unchanged identity evidence.

For B benign, retain the original F5 numerical floors, relative to the documented
incumbent-missing hard-by-convention baseline. No old B score is opened/invented.

| Literal device_family | Targets | Contexts | Minimum normal targets | Minimum all-B-benign-normal contexts |
|---|---:|---:|---:|---:|
| iotsim-combined-cycle | 333 | 282 | 34 | 29 |
| iotsim-domotic-monitor | 230 | 50 | 23 | 5 |
| ton-iot-external | 3,157 | 2,995 | 316 | 300 |

Each key independently needs >=10% of targets and >=10% of contexts. A counted
context must have all of its B-benign target rows normal; this is not a claim
that every event or every target of every label in that context is normal.
Totals are 3,720 targets / 3,327 eligible contexts, with floor sums 373 / 334.
Aggregate pass cannot compensate for a failed key. These are coarse families,
not three independent physical devices, and they do not replace any CE gate.
Compute and retain raw B metrics even when protection fails, but mark usable
joint utility false in that case. The permitted old F5 reference does not supply
per-key B outcomes; do not report per-key B changes relative to F5 terminal.
The prescribed baseline for these floors is the incumbent convention.

| Primary status, in priority order | Condition |
|---|---|
| N2_ENGINEERING_STOP / N2_NEEDS_GOVERNED_MODEL_EXPORT | Any identity, incomplete set, nonfinite, access, runtime, serialization or resource failure |
| N2_DEV_ATTACK_GATE_FAILURE | Complete valid run with any A1C or B1N miss |
| N2_DEV_PROTECTED_BENIGN_FAILURE | All six attacks pass but at least one A0C target is hard |
| N2_DEV_B_UTILITY_INSUFFICIENT | All protected development targets pass but at least one B per-key floor fails |
| N2_EXPOSED_DEV_GATES_PASS | All protected development targets and all B per-key floors pass |

Always retain every gate's counts, not just the primary status. These statuses
describe this single exposed-development check. None means F5 eligible,
inheritance complete, CE PASS, untouched holdout PASS, K permission or deployment.
N2 contains no criterion that chooses another candidate or launches a retry.

## 8. Finite execution budget and implementation gate

The future real attempt has one worker, <=1,800 seconds total (including
verification and sealing), <=8 GiB peak process memory and <=100 MiB total
new output. Reserve 1 MiB within that output limit for terminal/stop receipts.
Use the accepted Windows job-object pattern for one process, process-memory
limit and kill-on-supervisor-exit; external polling and bounded cooperative
checks cover wall/output limits. Ensure both working-set and committed-memory
peaks are accounted for. Do not depend on the worker returning from native code.

Hard numerical action ceilings: one restricted checkpoint load, one 65-value
head decode, one candidate assembly, one forward pass, 136 batches, 4,323
context evaluations, 5,206 target evaluations, <=205,470 unpadded authorized
event occurrences and <=1,106,688 padded projection slots (=4,323*256).
The exact selected event/range count is sealed from metadata before decoding.
Train feature decoding/evaluations, optimizer/backward/teacher/LP calls,
threshold fits, alternative candidates, pilot runs, retries and HPC jobs are zero.

Implementation is a separately authorized new N2 controller/selective reader
and synthetic gate. Keep N1/F5 sources and accepted packages immutable. Reuse
their inert model definition and appropriate pure helpers; do not call historical
real entry points, N1 diagnose/solve/real_worker or F5 load_parent/load_preflight/
load_checkpoint/evaluate launchers. Update the new N2 audit vocabulary for its
explicit development access; do not mislabel it as train-only or zero validation.

Required synthetic acceptance covers mixed-selector sentinels; wrong hashes,
joins, source/group counts and ranges; exact head byte assembly and unchanged
non-head/full-state hashes; restricted checkpoint globals and final-epoch-only
projection; canonical sorting/full-context shapes/zero-state/no-grad; attack
ties and benign-zero rejection; all per-key utility ceilings and context unions;
protected UID baseline reconstruction without invented unprotected values;
status priority and incomplete-output rejection; prohibited fit/retry calls;
resource caps, abnormal exit, startup failure and provisional/final seals.
Use generated fixtures only. No numerical real-input pilot or historical test
rerun is needed. Seal N2 code/test/runtime acceptance before real authorization.

Use exclusive namespaces such as
`runs/frontend_inheritance_n2_implementation_v1_20260908/` and
`runs/frontend_inheritance_n2_fixed_witness_development_v1_20260908/`.
The real namespace must be absent; an interrupted or failed attempt cannot be
restarted. Output identity/runtime/access receipts, selected metadata/ranges,
assembled-state hashes, all target predictions, exact count/gate tables,
historical protected-reference comparison, resource/terminal receipts and
SHA256SUMS. Do not export a new feature cache, fitted head or deployment model.
The status viewer must identify provisional results and favor the final sealed
supervisor status. No automatic K or follow-on job is allowed.

## 9. Retention and coverage design after this observation

N2 cannot forget through learning because it never updates parameters. Future
learning is different: preserve the N1 research witness as an immutable rollback
reference and predeclare all original 8,660 training judgments as the recommended
retention acceptance set, not only five formerly failed targets. That strengthens
a future acceptance condition beyond N1's 6,914 LP constraints; it does not
retroactively change N1/F5 rules or claim exact checks on the other 1,746 rows.
Carry the six development-attack requirements and 1,478 A0C judgments into the
next proposal's acceptance accounting as well. Any of those rows reused for
learning becomes a fit check, not validation. A requirement already failing in
N2 remains an unresolved requirement, not a successfully retained decision.

A future proposal must state its candidate-generation mechanism, initial
feasibility/restoration, complete-set verification cost and stop on any protected
regression. A soft loss or replay sampling alone is not a guarantee. Rejecting
a failed candidate preserves the research reference; it does not guarantee that
a useful feasible update exists or that unseen inputs are safe. Nothing is
promoted to deployment under this policy.

The prospective decision branches are:

1. If any development attack fails, prioritize a scoped attack-coverage and
   input/history question before a benign-only intervention. The family mismatch
   and prior information-contract gaps are hypotheses to distinguish, not a
   preselected justification for a larger encoder or changed history.
2. If attacks pass and remaining protection/utility failures are confined to
   normal_1, design a separate exposed-development coverage intervention. Its
   prospective population is the complete 4,000-row source, 843 A + 3,157 B,
   not just observed errors or a new random row split. With original 8,660
   training targets this would be 12,660 development targets across the two
   declared roles. Explicit authorization for new development-learning roles
   and a complete fitting protocol would be needed. The original F5 partition
   remains unchanged; the reused normal_1 rows cannot also validate that fit.
3. If failures extend to other benign sources/keys, design a question covering
   that pattern before assuming a ToN-only coverage repair. Preserve all attack
   and original-training protections in any proposed candidate acceptance.
4. If exposed development gates pass, do not fit normal_1 merely to populate a
   coverage table. Proceed to the evidence contract needed for broader inherited
   behavior, with no claim that the existing catalog already supplies it.

Even branch 2 would establish at most augmented finite-set feasibility unless
separate evidence is supplied. Its fitting objective/constraint set, solver or
optimizer, new input access, numerical limits and residual evaluation scope
are deliberately not an executable N3 protocol here. Strengthening retention
and adding coverage together is not a single-factor causal attribution to
ToN coverage. Do not run a sequence of head searches under this roadmap.

For a meaningful same-behavior inheritance test, a future evidence contract
must establish behavior correspondence to the old capability, absence from
all fitting of the candidate including its encoder, source/member/session
dependencies and exposure history. Previously exposed but fit-excluded
same-behavior data could support an explicitly labeled development test; it
would not become untouched confirmation. No qualifying same-behavior reserve
was identified in the current catalog. Re-splitting data already fitted by this
encoder cannot supply such an exclusion. Missing evidence limits the claim rather
than
authorizing select/report/FINAL access or an unrequested data download.

New-device commissioning remains downstream, with a causal trustworthy benign
prefix assumption to be designed separately. It does not substitute for old
attack inheritance and is not universal zero-shot OOD detection.

## 10. Design-stage access and review record

This stage read current handoff/results, frozen protocols and source as text,
sealed N0 aggregate coverage tables and N1 identity/result metadata. It checked
opaque document/manifest hashes. It did not open real feature/head bytes as
numbers, load checkpoint tensors, construct a model, run synthetic tests,
compute new logits, solve, train, reassign data, decode captures or start HPC.
The frozen originals and all unrelated modifications are preserved.

Final source/contract review is complete with no remaining blocking design
findings. It checked the model identity chain, selector projections, final-ledger
scope, denominators/utility rounding, status priority, retention accounting and
evidence/authority boundaries. Static checks reconciled 12 selected manifest
entries and nine historical code hashes. They verified the inherited bundle
identity and its 17 repository/seven runtime entry counts, and validated 18
additional pin formats. No real feature/head tensor or checkpoint was opened
numerically for those checks. The review is by the primary agent;
no independent-agent review is claimed. The design and companion JSON are sealed
by separate SHA-256 sidecars. Next is explicit N2 implementation/synthetic
authorization, then separate authorization for the one real development check.
No N2 result exists yet. This design and subsequent local reports are not
claimed committed or pushed.
