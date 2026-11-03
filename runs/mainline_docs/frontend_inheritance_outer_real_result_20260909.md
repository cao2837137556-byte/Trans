# Fixed N3 outer-development comparison: one real result

Date: 2026-09-09. User authorization: ONE bounded input preparation plus ONE
fixed-N3 complete-pool comparison after implementation acceptance.
Execution status: OUTER_COMPARISON_COMPLETE; verified supervisor final seal.
Scientific result: A_retention=REGRESSION_ON_THIS_POOL.
B_utility=POSITIVE_IN_BOTH_REPRESENTED_GROUPS. Attempt CLOSED; no retry.

## Complete observed outcomes

| Population | Targets | Candidate correct | Candidate errors | Interpretation |
|---|---:|---:|---:|---|
| Old-detected A reconnaissance attacks | 2,000 | 1,995 | 5 | Attack retention requirement fails; recall 99.75% |
| Old-correct A benign | 1,174 | 1,174 | 0 | No newly hard protected benign targets |
| Old-wrong A benign | 2 | 2 | 0 | Both exposed old false alarms corrected |
| B benign | 1,224 | 1,224 | 0 | All formerly unavailable benign targets released |
| All benign | 2,400 | 2,400 | 0 | No benign errors in this pool |

All 4,400 targets / 3,582 contexts were evaluated. No subset was excluded after
observing the outcome. Five old-correct attacks became wrong; two old-wrong A
benign targets became correct. A negative-flip count/rate is 5/3,176; conditional
loss among old-correct A is 5/3,174. Do not conflate these denominators.

| B group | Normal targets / all | All-evaluated-B-benign-normal contexts / all |
|---|---:|---:|
| iotsim-combined-cycle | 998 / 998 | 844 / 844 |
| iotsim-domotic-monitor | 226 / 226 | 50 / 50 |
| Total | 1,224 / 1,224 | 894 / 894 |

The B reference is missing-hard by convention, not a learned no-B control.
This establishes useful B decisions on this exposed development pool, not
causal benefit of including B in training or B attack detection.

## Five remaining attack errors

All five are H1 ToN-reconnaissance_scan targets from normal_scanning1.pcap,
each in a distinct semantic context. Their fixed zero-threshold logits are
negative; there are no decision ties.

| UID | Raw zero-based position | Causal prefix events | Candidate logit |
|---|---:|---:|---:|
| ton:ckbt_01dad899cff4388f69a7 | 565301 | 2 | -0.8313260078430176 |
| ton:ckbt_03cee2b1ee1f725a3cc7 | 28202 | 28 | -0.10206660628318787 |
| ton:ckbt_19e37a0b5749f3b0755c | 25461 | 2 | -0.7296832203865051 |
| ton:ckbt_2430e72b8306da7ee37a | 526086 | 29 | -0.096453458070755 |
| ton:ckbt_31ba7d482a97ce8eb9d6 | 24252 | 49 | -0.028434842824935913 |

A UID-only comparison with the sealed historical F1 five-error file
(SHA256 3adb43c349b59bc85a66024ef2533796081cca935a0f92ccd88cee008e7ca3be)
shows four shared UIDs, one historical error now correct and one different
current error. The sets are NOT identical. No old model forward or historical
logit computation was performed. Equal error counts do not establish equal
failure mechanisms, and this set comparison is not a causal diagnosis.

## Execution, preparation and identity

Supervisor elapsed 77.266 seconds; one worker exited 0, zero restarts.
Controller PID 17024 and worker PID 42184 are confirmed exited.
Peak aggregate job committed memory: 772,657,152 bytes. Worker-recorded output:
9,492,123 bytes before terminal/control receipts. All ceilings passed.

Opaque hashing verified two input containers / 24,442,596,676 bytes. Exactly
five selected members / 628,903 packet records were decoded, preserving the
specified inclusive cutoffs. There were zero old-L0 prefix mismatches.
Prepared 5,164 context events / 2,705,936 float32 feature bytes; one full pass,
112 batches, 3,582 contexts, 4,400 targets and 18,808 padded slots.

Prepared feature SHA256:
18c2533d2a91839cb17dbc35579fb96cb3050449d5badeeff2ac47d98158bd91.

One restricted checkpoint load, head decode and assembly; no optimizer,
backward, LP, teacher forward, calibration, historical model replay or retry.
The loader used the declared projection and indexed zero epoch-ledger values.
Only selected F1 validation signatures were deserialized for prefix comparison;
other known-container signature text was lexically scanned, not materialized
as feature arrays. Whole-container identity hashing is disclosed separately
from selected-member packet decoding.

N3 candidate state before and after the sole pass:
ff41638339604d4270ff5eef616885ef4b25bb075e8d1cd89dcb565ed10df3f9.
Non-head and installed head identities match the accepted N3 witness.
No model, frozen rule, input denominator or threshold was changed.

Real namespace: runs/frontend_inheritance_outer_comparison_v1_20260909/.
All 14 result/control manifest members verified.
SHA256SUMS SHA256:
5801d8d3bb364489f10bda363cb13919f37004aaab8cc9516593fdd904876666.
Supervisor terminal SHA256:
4cc8ce401fb3018f2530c48976d854e1b090d846c5da4fd8f05e3e3f864fe878.
Comparison JSON SHA256:
2c4d641bdda78550d620ee5346fa4b580f06b95f33a385507a2bb13e761bcee3.

## Scientific consequence and next boundary

This was a successfully completed experiment with a failed attack-protection
requirement, not an engineering stop. B gains and correct benign decisions
cannot compensate for the five new misses under the unchanged zero-regression
rule. The N3 finite-set repair remains valid and preserved, but full old
capability inheritance is not established.

The next appropriate work is a separately authorized targeted diagnostic/design
for these observed misses, using provenance and comparable evidence to decide
a repair. Do not automatically fit these five labels, change the threshold,
discard/retrain the encoder, repeat this attempt or proceed to new devices.
The five outcomes bound the error set in THIS pool, not all remaining project
difficulty. Existing literature-first research preferences continue to apply.

This pool was already exposed in F1 validation/frontend design. It supplies
development evidence only; session/pretraining/device independence and broader
behavior coverage remain unresolved. No comparison with the old global
97.3698% attack-recall denominator is valid here.

broader_inheritance=NOT_PROVED; F5_eligible=false; deployment=false;
K=NOT_AUTHORIZED; new_device=NOT_EVALUATED; causal_B_training_benefit=NOT_TESTED.
F5 remains NO_ELIGIBLE_CHECKPOINT. N1/N2/N3 and this attempt remain CLOSED.

Post-run checks matched 26 accepted source/script pins, eight runtime pins,
seven pinned documents and all eight unrelated modified-file starting hashes.
HEAD remains 4b28747b09480471e2bac1beb3a9badf27280efb on codex/exp-mainline.
No branch/worktree/reset/commit/push or historical artifact rewrite occurred.
