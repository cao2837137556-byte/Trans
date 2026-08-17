# CKDB domain-robust representation route — Codex round 1

Date: 2026-08-17  
Status: DESIGN DISCUSSION ONLY  
Parent evidence: CKDA D1 local emergency L2 (`CKDA_D1_WEAK_ONLY`)  
Authorization: no implementation, training, report reopening, FINAL access, or HPC submission

## 1. Decision first

CKDA D1 is closed under its frozen state machine: `GO_D2=false`. A domain-robust
learner cannot be launched as CKDA D2. If pursued, it must be a newly named and
newly preregistered route with fresh selection/evaluation boundaries.

The next-route hypothesis is physically plausible because E3/P2 contains strong
attack information but its benign transfer is device-domain dependent. The
current report may be used to diagnose that failure shape, not to choose a new
threshold or claim a repaired result on the same viewed pools.

## 2. Read-only failure decomposition

All values below were recomputed from the frozen CKDA D1 report scores. No model
was trained and no threshold was scanned.

### 2.1 Hydraulic failure is not missingness

| Pool | Rows | Missing | P2 hard rate | Hard rate among nonmissing rows |
|---|---:|---:|---:|---:|
| hydraulic-system | 3,000 | 0.87% | 76.30% | 76.09% |
| ip-camera-street | 3,000 | 0.00% | 0.07% | 0.07% |
| predictive-maintenance | 9,000 | 12.04% | 42.83% | 35.01% |
| stream-consumer | 3,000 | 0.00% | 0.33% | 0.33% |

The hydraulic error survives after excluding missing embeddings. Missingness is
therefore not its primary driver.

### 2.2 It is a family-wide domain shift, not one broken source

The five hydraulic sources each contain about 600 rows. Their P2 hard rates are
75.88%, 76.09%, 76.21%, 76.62%, and 76.71%. Median scores by source are
0.9578–0.9762 against the frozen P2 threshold 0.06516. The failure is uniform
across sources and strongly separated from the decision boundary.

Among P2's 2,289 hydraulic false alerts:

- 94.84% are also C1 hard;
- 59.90% are FrozenCKBQ hard;
- 0.00% are M7 hard.

This is consistent with a stable device-domain conflict: E3/P2 and C1 interpret
hydraulic traffic as attack-like, while M7 treats it as normal.

### 2.3 Boolean fusion cannot resolve the trade-off

These combinations are descriptive oracle checks only; they are not candidate
selection.

| Rule | Overall attack recall | Future-query recall | Four-pool OOD macro |
|---|---:|---:|---:|
| P2 | 97.37% | 96.68% | 29.88% |
| P2 AND M7 | 76.45% | 62.36% | 0.15% |
| P2 OR M7 | 98.63% | 97.51% | 29.88% |
| P2 AND FrozenCKBQ | 82.95% | 73.12% | 16.97% |
| P2 OR C1 | 99.40% | 98.92% | 94.08% |

AND returns to the low-recall normality-anchor ceiling; OR preserves the high
false-alert arm. The old logical-fusion trade-off remains. A new route must learn
a general domain-stable rescue rule or add genuinely new benign-domain evidence.

## 3. Assessment of proposed directions

### A. Domain-robust E3 head — accept for D0 design, not as current D2

This direction targets the observed cause. A legal candidate could combine a
frozen E3 embedding with a frozen M7 score, then train one global head with
worst-domain or invariance regularization across legal fit domains. Device/source
identity may define training groups but must not select a device-specific head or
appear as an inference-time patch.

The exact teacher loss cannot be approved until its mathematical definition is
available. The useful role for that loss is a global constraint on attack recall
plus worst-benign-domain risk, not post-hoc class/family weighting.

### B. Rescue I1 with more legally disjoint benign data — accept as strategic primary

I1 was never scientifically tested; its benign-only gate failed at 697,387 tokens
versus 10,000,000 required. Acquiring independent benign IoT/process traffic is
the cleanest way to test the domain-trained representation hypothesis and avoids
external-pretraining overlap uncertainty. This is slower but scientifically
stronger than adapting E3 on a viewed failure pool.

### C. Simple P2/M7 or P2/CKBQ fusion — reject

The diagnostic table above directly shows that fixed AND/OR logic cannot satisfy
both axes. Reopening it would repeat a closed information trade-off.

### D. Hydraulic-specific calibration or expert — reject

The viewed pool may be used for mechanism diagnosis only. A hydraulic threshold,
head, weight, or exception is a forbidden device patch and would invalidate the
open-world claim.

## 4. Required CKDB D0 before any code

1. **Fresh-evaluation audit:** locate at least one legally untouched benign device
   domain beyond the four viewed CKDA pools. The current pools cannot serve both
   as design evidence and an unbiased final test.
2. **Fit-domain audit:** verify whether the legal fit data contain enough benign
   device groups for leave-one-domain-out selection. Current CKDA fit/select has
   four IoTSIM benign families plus ToN external normal traffic, but class and
   domain are partly confounded and must be quantified.
3. **Loss-definition audit:** obtain the teacher's exact formula and map every
   term to legal fit/select data, causality, and inference-time inputs.
4. **Two-candidate maximum:** compare one global domain-robust E3+M7 head with one
   domain-trained I1 route if new benign data clear the precondition. Do not open
   a model zoo.
5. **Pre-freeze success gate:** retain attack/family requirements and replace
   report-driven device tuning with worst-unseen-domain evaluation on fresh data.

If no fresh benign evaluation domain and no additional disjoint benign corpus
exist, CKDB is not scientifically identifiable and should not be implemented.

## 5. Current routing recommendation

Start CKDB D0 as a data-and-loss feasibility audit only. In parallel, schedule
the unchanged CKDA HPC replay when the school cluster returns; that replay may
confirm the local result but must not be used to tune CKDB. Keep cooler-motor and
seeds 37/47 sealed until a genuinely final, fully frozen system exists.

