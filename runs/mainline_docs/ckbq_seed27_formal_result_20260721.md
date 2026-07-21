# CKBQ seed-27 formal result and score-space diagnosis

Date: 2026-07-21

Experiment: `issue27ckbq_causal_minirocket_consensus_v1`

Canonical run: AMD job `153037`, experiment commit
`7bb51cb087b54c99ffd1df248b3692336ce9637b`

Registered primary: `M3-StaticTemporalConsensus`

Scientific decision: `NO_GO`

## Execution and recovery

The formal Python program completed and emitted every registered result.  The
Slurm allocation was subsequently marked `FAILED 1:0` because the first
validator retained an incorrect auxiliary warm-up constant (`256` rather than
the frozen CKBO value `500`).  The first recovery attempt then conservatively
rejected every source because it reproduced only the array payload hash, while
CKBQ's contract hashes `dtype || shape || payload`.

Recovery commit `aecb2ca65f3c8536587efb7b0df385becb54b9b7` verifies the original
`CKBQ_FORMAL_COMPLETE` marker, the exact known terminal error, all 31 frozen
auxiliary source contracts, every cache and target-position hash, and every
formal output.  It does not retrain a model or change a score, gate, metric, or
decision.  The recovered validator reports `CKBQ_RESULT_VALID`.
The recovered pullback archive SHA-256 is
`f698f1a92097c32b205f4992f90e61f71eb2b4913be3d316ccdf31b1be19027e`.

## Primary result

Hard OOD rates are lower-is-better; attack recall is higher-is-better.

| Metric | C1 | M3 | Difference |
| --- | ---: | ---: | ---: |
| overall attack hard recall | 91.300% | 84.354% | -6.945 pp |
| future attack recall | 86.834% | 74.195% | -12.639 pp |
| same-file attack recall | 63.516% | 58.930% | -4.586 pp |
| sealed attack recall | 97.251% | 97.042% | -0.209 pp |
| support-val recall | 100.000% | 100.000% | 0.000 pp |
| IP-camera-street OOD hard | 100.000% | 8.100% | -91.900 pp |
| predictive-maintenance OOD hard | 100.000% | 57.589% | -42.411 pp |
| stream-consumer OOD hard | 100.000% | 29.700% | -70.300 pp |
| hydraulic-system OOD hard | 72.367% | 45.700% | -26.667 pp |

This is the first valid run on the current route with a large, simultaneous
four-held normal/OOD suppression signal that is not a cold-start artifact.
It is not a deployable result because the attack constraints fail badly.

## Candidate decomposition

| Candidate | Attack recall | IP camera | Predictive | Stream | Hydraulic |
| --- | ---: | ---: | ---: | ---: | ---: |
| M0-C1 | 91.300% | 100.000% | 100.000% | 100.000% | 72.367% |
| A0 global normal conformal | 82.250% | 5.467% | 55.489% | 26.900% | 42.833% |
| M1 shielded static | 84.339% | 8.100% | 57.589% | 29.700% | 43.433% |
| M2 shielded temporal | 91.268% | 100.000% | 43.089% | 99.967% | 72.367% |
| M3 static-temporal consensus | 84.354% | 8.100% | 57.589% | 29.700% | 45.700% |

The selected C1 shield boundary is `1.0000000000019147`, above every report
C1 score, so it protects no record.  At the selected M3 gate, the temporal
branch uniquely rescues only 37 attack rows and uniquely adds 68 hydraulic
false alarms.  M3 is therefore almost entirely the M1 static decision.  The
raw9 MiniRocket branch is not an efficient attack-preservation mechanism.

## Attack failure concentration

M3 suppresses 16,950 C1-detected attacks; 16,606 (`97.97%`) are future-query
attacks.  The largest aggregate family losses are:

| Attack family | Rows | Delta versus C1 |
| --- | ---: | ---: |
| Telnet Brute Force | 39,712 | -21.198 pp |
| Reporting | 167 | -18.563 pp |
| TCP Scan | 39,711 | -12.966 pp |
| Merlin C&C Communication | 9,926 | -9.299 pp |
| Merlin UDP Flooding | 10,298 | -8.837 pp |
| Ingress Tool Transfer | 10,069 | -4.499 pp |

The 385-row support-train bank contains ten families but no Telnet Brute Force,
TCP Scan, Reporting, C&C Communication, CoAP Amplification, or UDP Scan rows.
The dominant future failures are concentrated on air-quality-1 and
building-monitor-1.  Perfect recall on 69 support-val rows therefore does not
control unseen attack-family/source shift.

## Exact post-hoc score-space feasibility

`issue27ckbq_result_diagnosis_v1.py` uses report labels only after the formal
decision to test capability; its thresholds are forbidden for model or gate
selection.  For each of 890 exact static score boundaries, it computes the
least aggressive temporal boundary that achieves the preregistered weak held
signal (at least five percentage points of improvement and at most 90% hard)
for all four families.  It then checks the 0.5 pp overall and 2 pp major-family
attack constraints.

There are zero feasible boundaries.  The closest boundary still suppresses
5,902 attacks (`-2.418 pp` overall), against an allowance of 1,220, and exceeds
the Telnet and TCP-Scan family allowances by 2,781 and 1,419 rows.  Therefore
the current static/temporal score pair cannot be repaired by another threshold
choice.  The next experiment needs new transferable process evidence, not
report-tuned gate adjustment.

## Integrity and numerical audit

- 385 unique support rows; static and temporal supervised fit count exactly
  once per row;
- 69 legal support-val rows used for gate selection; report rows used zero;
- target-scope rows all pass; cross-phase duplicates and missing frozen target
  positions zero;
- future events, forbidden target events, and missing current events zero;
- permanent report-only fit/preprocessing/gate/model use zero;
- report gradient updates and threshold updates zero;
- review zero, NaN count zero, raw-label feature reads false;
- base T0 and auxiliary temporal manifest hashes match the frozen records;
- runtime about 610 seconds; batch MaxRSS about 8.30 GiB under a 16 GiB request.

Ridge emitted an ill-conditioned-matrix warning.  The learned parameters and
scores are finite and deterministic, so this did not cause the run failure,
but a future Ridge control should use a numerically stable solver or explicit
feature conditioning.  It is not a reason to repeat the rejected CKBQ route.

## Route decision

Do not run seeds 37/47, tune thresholds on the four report families, or repeat
the current raw9 MiniRocket consensus.  Retain the demonstrated static
normality signal as an ablation.  The active blocker is generic attack-process
evidence for unseen scan/brute-force and shifted future sources while keeping
the source-held normal/OOD suppression signal.

The next route must use mature flow/connection-process observables rather than
another backend over the same anonymous raw9 sequence, and it must retain the
same strict fit/select/report, sealed-family, past-only, and review-zero
contracts.
