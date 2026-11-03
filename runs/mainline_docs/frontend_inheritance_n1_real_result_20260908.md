# N1 real fixed-terminal last-layer result

Date: 2026-09-08. Status: `N1_JOINT_HEAD_WITNESS`.
Branch/HEAD: codex/exp-mainline / 4b28747b09480471e2bac1beb3a9badf27280efb.
Attempt: `runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908/`.
Accepted implementation: `runs/frontend_inheritance_n1_implementation_v2_20260908/`.

## Result and scientific meaning

The user explicitly authorized the next real N1 stage after implementation
acceptance, including the disclosed restricted checkpoint-container access.
The sole attempt completed with a jointly verified exact/float32 head witness.
All 6,914 predefined protected training judgments pass. All 1,746 accompanying
training judgments also pass, giving zero errors across all 8,660 targets.

| Category | Targets | Terminal baseline errors | Candidate errors | Newly wrong |
|---|---:|---:|---:|---:|
| A1C: A attacks | 2,179 | 5 | 0 | 0 |
| A0C: protected A benign | 4,667 | 0 | 0 | 0 |
| B1N: B attacks | 68 | 0 | 0 | 0 |
| A0W: old-teacher-wrong A benign | 24 | 0 | 0 | 0 |
| B0N: B benign | 1,722 | 0 | 0 | 0 |

The five recovered UIDs are support_train:fit:197, :200, :201, :203 and :204.
The saved terminal training reference and fresh baseline agreed on that exact
five-UID set before the solver was called.

The fixed terminal representation and head_hidden therefore admit a last-layer
solution for these joint finite-set decisions. Repairing these five training
misses does not require changing the encoder for this dataset. This is a
constructive feasibility result, not an attribution of every F5 failure to its
optimizer or last layer, and not a claim about unseen inputs or later updates.

Inheritance remains `NOT_PROVED`; the original F5 remains
`NO_ELIGIBLE_CHECKPOINT`. The witness is a separately stored diagnostic head,
marked `NOT_DEPLOYMENT` and `NOT_F5_ELIGIBLE`. It is not promoted into F5 or K.
The old incumbent and all original scientific artifacts remain unchanged.
No new B utility, OOD or device-commissioning claim follows. The accompanying
B benign rows already had zero baseline errors, so they do not establish new
B utility in this run.

## Verification and provenance

The single fixed HiGHS dual-simplex solve reported status 0 (optimal), 91
iterations and no warnings. Its normalized margin was 0.007725847995289192.
There was exactly one float64-to-float32 candidate cast and no candidate repair.

Independent exact dyadic verification of the cast coefficients passed the
original attack >= 0 / benign < 0 rule. The minimum exact signed margin and
minimum benign slack are both 8698455968311 / 1125899906842624, approximately
0.007725780875765587. There were zero zero-margin attack ties.
Original full-context float32 forward verification also passed all protected
judgments. All 4,984 complete pre-head context hashes matched baseline, and the
worker's non-head parameter identity checks passed.

The negative-certificate branch was correctly
`SKIPPED_EXACT_THRESHOLD_WITNESS`; no negative reconstruction was needed.

Input pins passed 17/17. The completed attempt's `SHA256SUMS` was independently
checked after exit: 23/23 members match. A separate read-only reconciliation of
saved predictions verified the 8,660 UID set, unchanged metadata, all five
category denominators, 6,914 protected rows, original five baseline failures,
zero candidate/new errors and 4,984 matching context hashes. This reconciliation
did not reload model/feature tensors or perform another forward or solve.

Diagnostic candidate head SHA-256:
`e6ac6c418253595b46308f654d339f8dfa16be971572fa282c9588c5c43f497e`.
Target64 feature SHA-256:
`657a77b7e68e9b9cabbd0b944e4454e67437188331f8cd47101edbc171aef35d`.

## Execution and access accounting

Local launch: approximately 14:42:19 Asia/Shanghai; final seal approximately
14:42:31. Supervisor elapsed time was 11.828 seconds. Peak process memory was
758,267,904 bytes (approximately 723 MiB); sealed output is approximately 22 MiB.
One worker exited normally with code 0. Worker and supervisor are both absent
after completion; restarts are zero.

Actual work: one LP, two canonical passes, 312 batches, 9,968 context evaluations,
17,320 target evaluations, 66,610 unpadded input-event occurrences and 221,616
padded projection slots. All frozen resource/action ceilings were respected.

The train-only reader decoded 33,305 authorized prefix events from 4,984 ranges.
Validation feature events and new validation numeric computations were zero.
Whole-file opaque hashing did include the mixed F4 binary without interpreting
its excluded bytes. Mixed CSV/JSON metadata tokenization and selector accesses
are disclosed in the access receipts.

The restricted weights-only checkpoint was loaded once. Optimizer/RNG and old
validation ledger contents were incidentally materialized by container loading,
then discarded without use as authorized. No optimizer was instantiated or
restored. Backward steps, optimizer steps and teacher forwards were zero.
No select/viewed/report/FINAL/K numeric input, PCAP decoding, resource pilot,
download or HPC was used. Parameter fitting did occur through the one LP.

## Next decision

Close this N1 attempt permanently. Do not repeat the solve or train/evaluate the
candidate automatically. The evidence now supports designing inheritance
verification and retention from this joint-fit witness while addressing the
documented missing ToN-benign training coverage under a separately reviewed
scope. Previously exposed validation cannot silently become untouched evidence.
Coverage, same-behavior generalization and retention through any later updates
must be assessed before claiming inheritance complete or advancing to new-device
commissioning. No subsequent design execution, learning or K is authorized by
the completed N1 attempt. Files remain local; no commit or push is claimed.
