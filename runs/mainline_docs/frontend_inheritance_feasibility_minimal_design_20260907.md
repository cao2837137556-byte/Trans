# Information inheritance feasibility and minimal discrimination design

Date: 2026-09-07. Status: `DESIGN_READY_FOR_REVIEW_NOT_EXECUTION_AUTHORIZED`.
Base checkout: `codex/exp-mainline`, `4b28747b09480471e2bac1beb3a9badf27280efb`.
The user's continuation authorizes this short design and source/document review.
It does not authorize implementation, numeric diagnostics, re-decoding, a new
partition, training, K, downloads or HPC. This is not a new FROZEN training protocol.

## Decision and evidence

Keep one shared A+B encoder and student head as the intended system. The old
system remains the incumbent. F5 already used its own head; its failure cannot
be explained as forcing new coordinates through frozen P2. A two-detector
fallback, a 768D clone, and a larger network are not selected by this design.

The next proposed action is N0: a bounded metadata-only inventory of existing
legal-fit coverage and input-contract readiness. It does not rerun F1 D0/F4 or
answer inheritance through another learning attempt. Three separate accounts:

| Account | Question | Evidence boundary |
|---|---|---|
| Joint fit and retention | Can the same weights retain attacks and protected normal decisions together? | Full predefined legal training set; fitting success is not generalization |
| Same-behavior holdout inheritance | Does behavior transfer to separate lawful groups with relevant training coverage? | Source/member/session dependencies and exposure history must be explicit |
| Unseen-source generalization | Does it work on a source absent from training? | Separate question; exposed development is never untouched confirmation |

F5 epoch 2 had 0 A training attack flips and 288 protected A benign flips;
epoch 5 had 6 and 0. The final five training attacks were correct in epochs
1/2; the three A validation attacks were correct in epochs 1/2/18. None of the
20 checkpoints met the joint gates. These facts establish loss of correct
behavior, not joint feasibility or impossible separability. No epoch is rescued.

The zero-ToN-benign statement applies only to F5 nested-train. Existing project
fit includes 4,000 `normal_1` benign targets; these are now exposed F5 validation.
`normal_2` is select. Another independent lawful ToN-normal source has not been
confirmed by this review. Original F1 legal fit is 18,266 targets/12,889 contexts;
its 4,400-row validation is also exposed, not a new untouched reserve.

## Input contract before network choice

Each candidate item must record producer -> tokenizer/collator -> actual model
argument, presence semantics, history cutoff and artifact identity. Construction,
model consumption and decision necessity are three different claims.

| Old item | Current F4/F5 preservation | Common A+B candidate and unresolved evidence |
|---|---|---|
| IP header length, TOS/traffic class, IP length, flags, TTL/hop limit | Not retained as the same fields; frame length is not IP length | Reuse deterministic parsing with IPv4/IPv6 applicability; no-IP remains representable; verify availability before adding anything |
| TCP flags, window, relative seq/ack, urgent pointer | Flags retained; other named fields absent | Optional TCP fields in one schema; non-TCP is not applicable, never discarded; relative bases need an explicit causal rule |
| UDP length | F4 transport length already uses udp.length | Reuse it; do not duplicate it or confuse it with TCP tcp.len |
| Direction and protocol | Present; old session and new context direction bases need comparison | Past-only orientation; source/owner/labels and raw endpoint values remain outside learned features |
| Early burst headers, burst bytes/counts and IAT | Current context events do not reconstruct old retained history | Reuse bounded-state ideas and exact unit conversions; no claim of identical history without cutoff-level evidence |
| flow_duration | Constructed and collated by old code, but omitted from actual E3 forward | Correct prior review: not an established missing model input; no addition justified by this argument |
| State boundary | F5 resets after 256 events, >60 s idle or >300 s span; old history follows its session | Any carry across contexts is a new contract, not concatenation of saved contexts |
| Pretrained knowledge | Not a field; old netFound and newly initialized GRU differ | Separate learning/coverage issue; copying fields does not copy pretrained knowledge |

New optional values must distinguish valid zero, not applicable, missing/invalid,
and unknown relative base. All H1-H4 events remain in the declared interface;
do not reuse netFound's TCP/UDP acceptance rule as an event filter for B.
Preserve F0's causal timestamp-regression clamp and audit count, without sorting
events or adopting old E3's permanent session-unencodable rule.
No field is automatically added because the old parser reads it. Conversely,
proving every omitted field irrelevant is not a prerequisite that could never close.

Two implementation obligations precede any proposed real input construction:

1. Old first-ACK fallback can change earlier relative tokens once packet 2 enters
   a target prefix. It is target-level causal, not immutable event tokenization.
   Compare bounded prefix reconstruction with a declared non-equivalent streaming
   rule; never rewrite already committed past outputs using later information.
2. The old 144-retained-row per-session bound is not a total deployment memory
   bound. Specify active-entity cap, deterministic eviction and incomplete-history
   state. Offline last-selected-target release is not an online lifecycle rule.
   Any shared history must be isolated by source/member/role and cutoff; unknown
   session joins stop the affected feasibility claim. No state may cross fit/val.

## N0: the first proposed executable scope

Purpose: identify usable existing fit evidence and missing contract artifacts,
not change membership or open model values. Proposed inputs, relative to checkout:

- `runs/frontend_f1_d0_census_v1_20260902_local_r2/SHA256SUMS` and its
  `f1_d0_uid_context_phase_owner_conservation.csv.gz` (25,467 mixed metadata rows).
- `runs/frontend_f4_fieldwise_input_feasibility_v1_20260905/f4_target_audit.csv.gz`,
  `f4_context_index.csv`, `f4_nested_split_census.csv`, `f4_schema.json` and hashes.
- F5 `preflight/uid_scope.csv`, `preflight/census.json`, `preflight/identities.json`;
  original F1/F5 frozen source lists; pinned producer/tokenizer source text/config.

Mixed-table access must be explicit in an N0 authorization: selector columns
`uid,phase,legal_fit,cross_phase_context` may be read for all 25,467 rows, including
select gate metadata. Only phase=fit, legal_fit=true, cross_phase_context=false
rows may supply owner/label_kind/role/source/family/context/tier/event-count data.
Use structured column/row projection, a synthetic access-boundary check and
separate counters for decompressed bytes, selector rows and retained metadata.
Never claim the container was unopened. If that restricted reader cannot be
established, return `N0_NEEDS_GOVERNED_EXPORT`; do not fall back to full-table load.
Do not call old D0 runners, F5 load_parent, np.load or a semantic-corpus reader.

Conserve the existing lineage, not recreate splits: 18,398 original fit minus
132 excluded fit rows = 18,266 legal-fit rows; 13,866 F5 parent + 4,400 exposed
F1 validation = 18,266. Preserve the existing 19 crossing-context exclusions.
Export source/member-if-known/context x label/owner/family/tier counts and an
exposure column (F5 train, F5 validation, F1 validation). Context counts do not
assert independence. Unknown physical-device/session/earlier-history membership
must stay unknown. A protocol/label pair alone is not proof of the same behavior.

Per proposed use, report `IDENTIFIED`, `INSUFFICIENT` or `UNKNOWN` with a reason.
No numeric source-count minimum can manufacture statistical independence. The
inventory may support later exposed-development reallocation only under a new
pre-registration and authorization; it performs no such reallocation itself.
Do not seek normal_2, other select/report/FINAL sources or new datasets to fill gaps.

Budget proposal: one local process, one metadata scan per table, <=600 s wall,
<=1 GiB RAM, <=50 MiB new output. Zero model/teacher forward, backward, optimizer,
feature/representation decoding, PCAP and network. No resource pilot or retry
for a better result. Exceeding limits or identity/schema/role drift stops N0.
Write a new namespace with identity/access receipts, coverage table, contract
gap table and SHA256SUMS; never modify sealed F5/F4 outputs.

N0 may conclude `READY_FOR_SCOPED_DIAGNOSTIC_DESIGN`, `COVERAGE_INSUFFICIENT`,
`HISTORY_MEMBERSHIP_UNRESOLVED`, `NEEDS_GOVERNED_EXPORT`, or an engineering/resource
stop. None means inheritance PASS. A gap does not close the shared-model family.
Only prerequisites for the affected contrast must pass, not every future claim.

## Minimal contrasts, conditional on N0

These are alternatives to justify, not a batch of jobs or executable permission.
Before any numeric branch, freeze exact input/UID/weight/code hashes, intervention,
metric, one finite budget and a decision consequence; unresolved items mean zero
execution allowance. No model architecture or optimizer is chosen here.

| Mechanism | Smallest meaningful contrast | What it can establish / what it cannot |
|---|---|---|
| Information versus history | If existing legal caches permit it, fixed teacher and fixed A train UIDs: unaltered input versus one declared field restriction OR one history restriction; keep the other factor fixed | Sensitivity/counterexample to an equivalence claim; altered inputs may be out of distribution, so neither outcome proves deployment safety or student recoverability |
| Training coverage | N0 first determines which questions have lawful, dependency-separated coverage. Any later learning contrast changes coverage only, keeping representation/update/measurement fixed | Association with the predeclared coverage change; source variation remains a confound unless controlled. Exposed rows cannot become fresh confirmation |
| Update interference/joint retention | Existing ledger is sufficient for historical forgetting. If a specific unresolved local question matters, use the sealed terminal state for read-only forward/autograd diagnostics with zero optimizer steps | Local component conflict only; terminal gradients cannot reconstruct epoch 3 or prove that a particular Adam update caused it |

For any future numeric proposal: request at most one contrast (reference plus
one intervention), never combine field/history, data and update changes in one
attribution claim. Ceiling per diagnostic proposal: <=1,800 s local wall,
<=8 GiB RAM, <=100 MiB outputs, zero optimizer steps. Exact forward/backward/UID
caps must be supplied before approval; if not feasible, stop that diagnostic.
These ceilings do not authorize a training-based coverage or retention trial.
Such a trial would require its own complete frozen learning protocol and authority.

Any eventual retention mechanism must cover the predefined legal set jointly:
F5 reference counts are 2,179 A attacks, 4,667 protected A normal and 68 B attacks
(6,914 protected targets), with all other A/B rows still accounted for. No special
rule for five failures. A replay/guard proposal must specify initial feasibility
or restoration, all-set checking cost, infeasible-update stop and limits to the
finite checked set. Soft penalties, clipping or gradient cosine alone do not
guarantee zero regression; no guarantee extends automatically to unseen data.

## Review and provenance

Three parallel read-only reviews checked the input contract, fit catalog and
identification logic. Final input-contract and adversarial reviews returned no
must-fix findings; this is document review, not scientific acceptance. The main
agent verified the duration correction against the actual caller and vendor
source. No third-party scientific certification is claimed. The same-name
`.sha256` sidecar identifies this reviewed design only, not a frozen execution
protocol. This design and prior P/T reports remain local, uncommitted/unpushed work.

Source anchors: `frontend_f5_failure_mechanism_review_20260907.md` and sealed
forensics; `ckbw_tail_margin_dual_control_preregistered_20260803.md` section 3;
`frontend_f1_d1_numerical_addendum_frozen_20260902.md` section 2;
`issue27frontend_f1_d0_census_v1.py:422`; `issue27ckda_d0_resource_pilot_v1.py:328`;
`issue27frontend_f0_zero_training_semantics_v1.py:455`;
`issue27ckda_d1_e3_embed_v1.py:38`; `issue27ckda_d1_representation_probe_v1.py:844`.
Vendor location is pinned by `scripts/issue27ckda_d1_local_contingency.ps1`:
`../../supercompute_transfer/issue27ckda_d0_representation_compatibility_20260811_r2/payload/vendor/netFound/src/modules/`;
inspect `netFoundTokenizer.py:175`, `netFoundDataCollator.py:190`,
`netFoundEmbeddings.py:20`. Source inspection is not a new model evaluation.
