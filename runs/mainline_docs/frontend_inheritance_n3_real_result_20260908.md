# N3 one real conservative joint repair result

Date: 2026-09-08. User authorization: ONE real N3 attempt after the sealed
implementation acceptance. Status: N3_CONSERVATIVE_JOINT_REPAIR_WITNESS.
Fit descriptor: JOINT_EXACT_FLOAT32_FIT. Supervisor final seal verified.

## Observed result

All 12,711 frozen fitting constraints passed both independent exact dyadic
judgments and actual float32 full-context model replay. All 13,866 original
train/development targets were reported. No candidate/solver retry occurred.

| Population | N2/reference errors | N3 errors | Interpretation |
|---|---:|---:|---|
| Original train, 8,660 | 0 (N1 reference) | 0 | All training judgments retained |
| Development A1C attacks, 3 | 3 | 0 | Three fitted attack targets repaired |
| Development B1N attacks, 3 | 0 | 0 | Three fitted attack targets retained |
| Development A0C benign, 1,478 | 843 | 0 | All protected benign targets correct |
| Development A0W benign, 2 | 0 | 0 | Exposed report-only outcomes |
| Development B0N benign, 3,720 | 1,153 | 853 | 300 additional normal releases |

The 2,567 historically normal B target UIDs and 2,238 all-B-benign-normal
context members were all retained, with zero lost members. Additional releases
are allowed by the frozen inclusion rule. B normal totals increased to 2,867
targets and 2,501 all-B-benign-normal contexts. All three original per-key floors
passed independently.

| B key | N3 normal targets | N3 normal contexts | Added targets/contexts |
|---|---:|---:|---|
| iotsim-combined-cycle | 333 | 282 | 0 / 0 |
| iotsim-domotic-monitor | 230 | 50 | 0 / 0 |
| ton-iot-external | 2,304 | 2,169 | 300 / 263 |

All 1,155 exposed report-only targets were reported: 302 correct, 853 wrong.
Their labels did not enter the LP. They are not independent holdout evidence.
The six development attacks still represent only three contexts. Individual
UID/context/family/logit records remain in the sealed joint measurements.

Solver status 0, 1,641 iterations; sole LP gamma 0.001089047157449257.
Gamma alone did not select or certify the candidate. Exact minimum signed
margin and benign slack were both
321352901161177307 / 295147905179352825856, strictly positive, with no attack
zero ties or wrong UIDs. Actual float32 minimum constrained margin was
0.0010880529880523682. The negative certificate branch was correctly skipped
after exact threshold success; no negative solve/system was attempted.

## Execution and identity

One worker exited 0, no restarts. Supervisor elapsed 25.203 seconds, peak
memory 1,038,102,528 bytes, output before final seal 52,476,703 bytes.
One checkpoint load, old-head decode, training-cache decode, baseline assembly,
LP, candidate cast and candidate installation. Three split passes, 428 batches,
13,630 context evaluations, 19,072 target evaluations, 205,470 decoded events,
377,635 forward event occurrences, 1,763,388 padded slots. All global and
phase-specific caps/counts passed. No optimizer, backward, teacher, baseline
train pass, old-terminal pass, threshold fit, pilot, HPC or K occurred.

The fixed N1 baseline reproduced all N2 development logits bitwise before
fitting. Every candidate train target64 row and full-context pre-head hash
matched N1's sealed cache evidence; development matched the new baseline.
Non-head state including semantic_head remained unchanged, and the baseline
and candidate full states were unchanged across their prescribed forwards.
All selected train/development prefixes cover the stored parent; no claim of
numerically unopened parent events is made.

Candidate full state:
ff41638339604d4270ff5eef616885ef4b25bb075e8d1cd89dcb565ed10df3f9

Fixed non-head state:
29328fc616ef5b0197d1dcc8c564d89865201eb08b540d826847e233932dbe67

Candidate head bytes SHA256:
e26bf80e8a45f605b806ed559afef0f3029f949a4c3cff00cf4aa6b7ef8d8d5a

Real output namespace:
runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908/

Supervisor terminal SHA256:
a832293aa8a32ee8a88fb2cb51088471d81f83705c9fe710a32b6c2279af71cd

SHA256SUMS file SHA256:
5ef2be5e6f7f93626d12fd87e38efbdac33967a0e4a14bb11a59cd55c9795e43

## What this changes

N1 established a training witness, and N2 showed that witness failed exposed
development protections. N3 explicitly added development fitting constraints
and found a single last-layer head that simultaneously satisfies the declared
training, protection and B-retention requirements on the fixed representation.
This is positive finite-set repair evidence. It shows a front-end replacement
is not necessary to repair these particular observations. It does not establish
the historical failure cause or success on other traffic.

This was development fitting: 4,051 original development targets were fitted,
including all six attacks. Their successful outcomes cannot be described as
unseen attack-family transfer or independent confirmation. The 1,155 residual
targets are exposed and may share contexts/prefixes with fit targets. Missing
same-behavior correspondence, exclusion from fitting of every learned component,
and source/session dependency evidence still limit broader inheritance claims.

broader_inheritance=NOT_PROVED; F5_eligible=false; deployment=false;
K=NOT_AUTHORIZED; new_device=NOT_EVALUATED. F5 remains NO_ELIGIBLE_CHECKPOINT.
The incumbent and N1/N2 historical outcomes are unchanged. N3 is now closed;
do not restart, add a candidate or reinterpret this witness as a deployment model.

## Next interaction and research preference

The user requested a plain-language explanation of the current project and
repair logic after this attempt. Next is that explanation and clarification of
the remaining evidence gap, not another automatically authorized experiment.
When a hard research problem or a substantial method/architecture change calls
for a new design, first search current frontier literature and suitable existing
methods, assess their project-specific assumptions and develop targeted
innovation. This user preference is also recorded in the authoritative handoff.
No new architecture selection or literature-based claim is made in this run.

HEAD remains 4b28747b09480471e2bac1beb3a9badf27280efb on codex/exp-mainline.
No accepted implementation/frozen protocol was edited, no unrelated change was
reverted, and no worktree/branch/reset/commit/push operation occurred.
