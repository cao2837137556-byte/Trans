# CKDC D0-F Phase A implementation and result

**Date:** 2026-08-25

**FROZEN contract:** `ckdc_d0f_m7_certificate_provenance_preregistered_20260825.md`

**Execution:** local, read-only, legal select only; no training, PCAP, report, or FINAL access

## 1. Implementation validation

Implementation commit: `e51398e`.

The contract suite passed **35/35** tests. In addition to unit boundaries, it performed one full
real-input end-to-end rehearsal into a temporary directory and verified every generated member
against the resulting `SHA256SUMS`. Python 3.9 grammar tests cover both executable and suite.

The implementation has no Phase-B CLI input. It pins all FROZEN identities before reading rows,
reproduces the 7,069-row role plan and the four D0 quadrant sentinels, proves CKBW duplicate-view
invariance, performs exact UID joins, and reproduces P2 decisions from the frozen threshold.

## 2. Formal execution identity

Output directory:

`runs/issue27ckdc_d0f_certificate_phase_a_v1_2026-08-25_local/`

The output `SHA256SUMS` has SHA-256:

`9b6ce02882a8be2f4efbab8d970f134ee087be598a5d9336024612486b0ed407`

Independent readback verified **7/7** listed output members. No engineering-failure marker exists.

## 3. Mechanical Phase-A result

Engineering validation status: `PASS`.

Scientific status:

`CKDC_D0F_NO_CERTIFICATE`

The ten conjunctive clauses resolved as follows:

| clause | result | observed |
|---|---|---:|
| literal frozen formula | PASS | exact |
| covered benign conflicts >=300 | FAIL | 0 |
| covered fraction >=5% | FAIL | 0.0% |
| covered source groups >=3 | FAIL | 0 |
| maximum covered-source share <=80% | FAIL | undefined because coverage is zero |
| support attacks preserved | PASS | 69/69 |
| changed benign conflicts >=300 | FAIL | 0 |
| not equivalent to `P2 AND M7` | PASS | differs on 4,986 rows |
| certificate not equivalent to M7 normal | PASS | differs on 7,000 rows |
| forbidden operations | PASS | 0 |

## 4. Failure mechanism

There are exactly 4,986 legal benign `P2 hard / M7 normal` conflicts. Their component evidence is:

| component | rows true |
|---|---:|
| `tail_normal` | 4,983 |
| `c1_normal` | **0** |
| `ckbq_normal` | 4,983 |
| full normality certificate | **0** |

The tail and CKBQ components nearly cover the entire benign-conflict set, but C1 is hard on every
one of those rows. Therefore the pre-existing Option-A conjunction cannot certify a single benign
conflict. This is a structural incompatibility, not a near-threshold miss and not a concentration
failure.

All 69 legal `support_val` attacks remain hard, but attack preservation alone cannot rescue a
candidate that changes zero benign decisions.

## 5. Scientific decision and boundary

Per the immutable protocol, Phase B is forbidden and was not launched. No inequality, threshold,
missing-value rule, feature, exception, or replacement candidate may be introduced after this
result. The narrow Option-A certificate route—and therefore CKDC fusion under this preregistered
candidate—closes cleanly.

This result does not weaken the observed CKDA attack-side signal, does not validate a new system,
does not authorize FINAL access, and does not replace the outstanding formal CKDA D1 HPC replay.
