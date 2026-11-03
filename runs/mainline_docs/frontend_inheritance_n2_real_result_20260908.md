# N2 real fixed-witness development result

Date: 2026-09-08.
Final status: N2_DEV_ATTACK_GATE_FAILURE.
The user authorized proceeding after sealed N2 implementation acceptance.
The ONE authorized real attempt completed and is now closed. Do not restart it.

## Outcome

The sole fixed N1 witness was evaluated on all 5,206 original exposed-development
targets / 4,323 contexts. This was a complete scientific gate failure, not an
engineering stop. A-side development attacks still failed; B-side development
attacks passed. The protected benign gate also failed. Raw B utility floors
passed for each key, but usable joint utility is false because protection failed.

| Category | Targets | Contexts | Errors | Hard predictions |
|---|---:|---:|---:|---:|
| A1C, protected attacks | 3 | 1 | 3 | 0 |
| B1N, protected attacks | 3 | 2 | 0 | 3 |
| A0C, protected benign | 1,478 | 993 | 843 | 843 |
| A0W, report-only benign | 2 | 2 | 0 | 0 |
| B0N, utility benign | 3,720 | 3,327 | 1,153 | 1,153 |

Category context counts can overlap and must not be summed as independent
contexts. The complete context union is 4,323.

All 843 normal_1 A0C targets / 672 contexts remain hard. All other 635 A0C
targets / 321 contexts are normal. normal_1 B0N has 2,004 normal targets out
of 3,157; its remaining 1,153 targets are hard. These A and B groups have
different membership, so their difference is not a controlled causal comparison.

The protected historical comparison reconciles exactly to the same 846 UIDs:
three A1C targets and all 843 normal_1 A0C targets. Newly wrong: zero. Newly
correct: zero. No old model forward was used for this comparison. The reference
is the authorized final F5 development violation list, not a new baseline run.
No unprotected per-UID or per-key F5 baseline is available or inferred.

## Six development attack targets

| UID | Category | Recorded family | Float32 logit | Decision |
|---|---|---|---:|---|
| support_train:fit:15 | A1C | Ingress Tool Transfer | -1.6083431243896484 | Miss |
| support_train:fit:17 | A1C | Ingress Tool Transfer | -1.5384957790374756 | Miss |
| support_train:fit:28 | A1C | Ingress Tool Transfer | -2.275953769683838 | Miss |
| support_train:fit:0 | B1N | File Download | 24.54951286315918 | Detect |
| support_train:fit:12 | B1N | File Download | 60.90198516845703 | Detect |
| support_train:fit:9 | B1N | File Download | 57.81782913208008 | Detect |

All six belong to source `processed/iotsim-combined-cycle-10.csv`, device-family
literal `combined-cycle`. They have three semantic contexts: one A context and
two B contexts, fully recorded in development_measurements.json. The historical
UID prefix `support_train:fit` does not change their actual F4/P `internal_val`
membership. No membership was inferred from a UID name.

The A logits are strictly below zero, not numerical ties. There is no threshold
adjustment or second-candidate check. As frozen before N2, neither recorded
development attack-family name appears in the F5 training family-name list.
That metadata fact does not by itself identify the cause of these misses or
prove that all underlying behaviors differ.

## Raw B utility

The baseline is the frozen incumbent-missing hard-by-convention rule. These are
not changes relative to old F5 per-key predictions.

| Literal key | Normal targets / total | Target floor | All-B-benign-normal contexts / total | Context floor | Raw gate |
|---|---:|---:|---:|---:|---|
| iotsim-combined-cycle | 333 / 333 | 34 | 282 / 282 | 29 | PASS |
| iotsim-domotic-monitor | 230 / 230 | 23 | 50 / 50 | 5 | PASS |
| ton-iot-external | 2,004 / 3,157 | 316 | 1,906 / 2,995 | 300 | PASS |
| Total | 2,567 / 3,720 | 373 | 2,238 / 3,327 | 334 | All keys pass |

An accepted context has every B-benign target normal, not necessarily every
event or target of every label normal. Raw B release is measurable here, but
protection failure prevents a usable joint-success claim. Coarse keys are not
independent physical-device counts, and these floors are not CE gates.

## Execution, identity and access

Output: `runs/frontend_inheritance_n2_fixed_witness_development_v1_20260908/`.
The controller ran once, with one worker, exit code 0 and no restart. Both
controller PID 33844 and worker PID 55052 were confirmed absent after completion.
The status viewer reports FINAL with verified supervisor seal.

- Total supervisor time including verification and sealing: 9.016 seconds.
- Worker time: 8.641 seconds; measured peak memory: 568,057,856 bytes.
- Final output directory: 8,687,839 bytes, below 100 MiB.
- One restricted checkpoint load, one 65-value head decode, one assembly.
- One canonical forward, 136 batches, 4,323 contexts, 5,206 targets.
- 172,165 selected development prefix events decoded/evaluated; 826,290 padded
  slots. Both are within frozen caps. No training events or targets evaluated.
- Zero LP, optimizer, backward, teacher, threshold-fitting, retry, resource-pilot,
  HPC or K operations. No full model or feature-cache export.

The original terminal full-state hash is
`131d15e7a586a6fb105995ecb25d56f8217351c03b60495c56d6e1b723db1bcc`;
the unchanged non-head state, including semantic_head, is
`29328fc616ef5b0197d1dcc8c564d89865201eb08b540d826847e233932dbe67`.
The exact N1 head-byte hash is
`e6ac6c418253595b46308f654d339f8dfa16be971572fa282c9588c5c43f497e`.
The assembled full-state hash was sealed before decoding and is unchanged after
the sole forward:
`386ab128a57dbcb9eb284468f39fd47697b7c82bd41c84c9cd3bc0e61f28bfd8`.
N1 training evidence is retained by this identity chain, without training replay.

The whole feature parent was hashed opaquely, then only the sealed internal_val
prefix ranges were decoded and checked against their original F4 prefix hashes.
Mixed CSV tokenization is disclosed: index 46,535 cells; target audit 235,722;
scope 69,330. Target payload was accessed for exactly 5,206 development rows;
target excluded incidental cells were 131,652 and scope excluded cells 17,320.
Neither l1_prefix_sha256 nor old_all_unk was accessed as a target payload field.
Training selectors were joined without reading their numeric payload.

The restricted weights-only loader used exactly the four frozen safe globals,
temporarily excluding ambient globals. It retained the model/identities and
minimal terminal/final-development reference. Optimizer, RNG and earlier ledger
contents were incidentally materialized and discarded without use. No loading
fallback occurred. The generic input helper lists candidate_head.f32le among
containers read; its actual numerical access is the separately counted single
head decode, not metadata-only access.

## Post-run verification

All 15 manifest members independently matched their hashes. Saved predictions
were separately checked for 5,206 unique UIDs / 4,323 contexts, all five category
summaries, all three B target/context summaries, and exact equality of the 846
protected error UIDs with the saved historical reference. This post-run check
read saved outputs only and computed no new model predictions.

| Artifact | SHA-256 |
|---|---|
| SHA256SUMS | 88c829c8edcf2c679955752cdaa7030a492b37e96482929ca34fb00ebd70a6ab |
| supervisor_terminal.json | 65bdd92cbffd0b8444eb688158837443cc2bcd8d09d2b0cf55c378d94e904a50 |
| worker_terminal.json | 6051c0a2701a1400a6ad6085e9d5ea38c6f3b19b64514a7c126b1b2a945fd6fb |
| development_measurements.json | 1cfe7836c667c76f49596b9b2268a39bc260ccb011ddc9bbfcf2ed89c817837a |

Frozen design, code, runtime and implementation acceptance identities still
verify. The existing unrelated issue27by directory hashes match their pre-run
snapshot. Branch and HEAD remain codex/exp-mainline and
4b28747b09480471e2bac1beb3a9badf27280efb. No commit, push or workspace reset.

## Meaning and next gate

N1's finite training-set head repair did not repair the exposed-development
protected failures. This does not invalidate its sealed training witness and
does not establish that this backbone, all alternative heads, or the scientific
project are infeasible. No parameter update occurred in N2, so it is not a new
forgetting event. Joint inheritance remains unresolved.

The frozen attack-failure branch applies: next design/review should prioritize
the scoped attack-coverage and input/history question, with these three A
misses as a concrete counterexample. Coverage mismatch, information/history
limits and unconstrained head extrapolation are hypotheses, not established
causes. A benign-only normal_1 intervention is not the selected next branch,
even though normal_1 also remains problematic.

The next proposal must preserve the N1 witness and explicitly account for all
8,660 original training judgments and the development protections. Any future
learning reuse of development inputs must be declared as fitting, not validation.
No new head search, extra forward, larger encoder, revised history or data
reallocation is authorized by this result. Next-stage design/review requires
its own user instruction; implementation/real execution follow its frozen scope.

F5 remains NO_ELIGIBLE_CHECKPOINT, N1 and N2 are closed, and the old deployment
remains unchanged. These six exposed attack targets do not prove general
same-behavior inheritance, new-device commissioning, universal OOD, untouched
holdout performance or K eligibility.
