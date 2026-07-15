# CKBO seed-27 mature AfterImage transfer result

Date: 2026-07-15

Experiment: `issue27ckbo_mature_afterimage_transfer_v1`

Formal job: AMD `151780`

Experiment commit: `6d69b84ef3f5eb3f0c691bf13ee001a4cde552ae`

Registered primary: `M3-AfterImageContrast-Aux`

Decision: `NO_GO`

## Executive result

CKBO completed successfully and is a valid single-seed negative scientific
result, not an execution failure.  The mature AfterImage frontend and legal
source-disjoint normal extension do contain useful suppression signal for some
unseen normal families, but the effect is not transferable enough and the
primary verifier suppresses too many attacks.

The primary `M3-AfterImageContrast-Aux` result is:

- stream-consumer hard false alarms: `100.000% -> 99.733%`;
- hydraulic-system: `72.367% -> 42.533%`;
- ip-camera-street: `100.000% -> 99.767%`;
- predictive-maintenance: `100.000% -> 73.011%`;
- overall attack hard recall: `91.300% -> 85.208%`, a `-6.091 pp` loss;
- review: `0`.

It therefore fails the registered stream, legal multi-held, overall attack,
and major attack-family gates.  Seeds 37/47 must not be launched and the sealed
cooler-motor family remains unopened.

## Candidate ablation

Hard OOD rates are lower-is-better; attack recall is higher-is-better.

| Candidate | IP-camera | Predictive | Stream | Hydraulic | Attack recall | Attack delta |
|---|---:|---:|---:|---:|---:|---:|
| M0-C1 | 100.000% | 100.000% | 100.000% | 72.367% | 91.300% | 0.000 pp |
| M1-AfterImage115-NoAux | 99.767% | 66.100% | 99.733% | 39.367% | 89.925% | -1.375 pp |
| M2-AfterImage115-Aux | 99.767% | 56.611% | 99.667% | 30.400% | 88.100% | -3.199 pp |
| M3-AfterImageContrast-Aux | 99.767% | 73.011% | 99.733% | 42.533% | 85.208% | -6.091 pp |
| A1-AfterImageContrast-NoAux | 99.767% | 76.089% | 99.733% | 46.900% | 85.897% | -5.403 pp |

Three conclusions follow directly from the ablations.

1. **Mature AfterImage115 has real but family-dependent normal-process
   signal.** Even without the auxiliary normal extension, M1 reduces
   predictive and hydraulic hard rates by about 33 percentage points.  This is
   not a universal solution because it changes stream and IP-camera by less
   than 0.3 pp.
2. **Legal auxiliary normal diversity helps only part of the frontier.** M2
   improves predictive by another `9.489 pp` and hydraulic by `8.967 pp`
   relative to M1, but costs another `1.825 pp` of overall attack recall and
   still leaves stream at `99.667%`.  The auxiliary fit pool contains eleven
   sources drawn mainly from combined-cycle, domotic-monitor, and one
   building-monitor source; it does not establish broad open-world normal
   coverage.
3. **The deterministic multiscale contrast must be rejected.** M2
   (`raw115 + Aux`) has no worse hard OOD rate on any of the four held families
   and has higher overall attack recall than M3 (`contrast115 + Aux`).  In the
   tested frontier, M2 strictly dominates the preregistered primary.  The
   contrast transformation is therefore not a novelty candidate and should
   not receive more seeds or threshold tuning.

All four learned candidates fail the attack-preservation gate, so none is a
deployable fallback.  M1 is the least damaging learned variant, but its
`-1.375 pp` attack loss still exceeds the allowed `-0.5 pp` and its stream
result remains effectively unchanged.

## Attack-preservation diagnosis

The primary model retains the 69 legal support-val attacks at `100%`, yet its
report attack recall falls by `6.091 pp` over 244,050 rows.  The source-cluster
bootstrap interval for the delta is `[-11.555, -0.148] pp` over eight sources.
This is evidence that the small support-val gate does not transfer to future
attack histories and families, not merely a loss-curve or NaN failure.

The main report-role losses are:

| Metric | C1 | M3 | Delta |
|---|---:|---:|---:|
| Future attack | 86.834% | 75.525% | -11.309 pp |
| Sealed attack | 97.251% | 97.244% | -0.006 pp |
| Domotic attack | 88.867% | 87.100% | -1.767 pp |
| Combined attack | 71.122% | 67.480% | -3.642 pp |

Major attack-family regressions include Merlin TCP Flooding `-32.573 pp`,
Reporting `-10.778 pp`, TCP Scan `-9.526 pp`, C&C Communication `-8.939 pp`,
and Telnet Brute Force `-5.001 pp`.  The failure is concentrated rather than a
uniform minor recall shift.  CoAP Amplification, Mirai C&C, and UDP Scan also
already have very low C1 recall; CKBO does not repair those baseline attack
holes.

## Gate and training audit

The primary verifier threshold is `0.4055266678`.  It was selected only from
69 legal support-val attacks and 3,000 source-disjoint auxiliary select rows.
Support-val recall is `100%`; auxiliary-select hard rate is `0.0333%`; report
rows used for selection are zero.  This clean select result coexists with a
large future-attack loss, which exposes a calibration-transfer problem rather
than a gate-implementation bug.

Training itself completed normally:

- 32 epochs per learned candidate and protocol;
- every legal support row used at least once in every epoch;
- 385 unique support rows in each of 20 candidate/protocol fits;
- family-balanced support visits: 1,920 visits for each of ten attack families
  per global candidate;
- finite losses throughout, no support-val early stopping;
- primary global loss `0.342070 -> 0.004318`, with minimum `0.000333`;
- zero sampled/ghost negatives because CKBO is explicit supervised
  attack-versus-benign training, not link-prediction SSL.

The very small training loss alongside poor held-family and report-attack
transfer is consistent with over-specialization to the legal fit/select
support, not under-training.

## Data and leakage validation

The local pullback was independently rechecked against the registered outputs.
The result package SHA-256 is
`5adb7437fed9a992ba16e658353ac60b271f4d3731860476d37108b12e8af21d`.

The following contracts passed:

- original strict 1M split unchanged;
- base 26-source T0 manifest unchanged at
  `b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67`;
- 385 support-train and 69 legal support-val rows preserved;
- support-val lineage: 512 sidecar rows = 385 support-train + 127 original
  support-val; 58 fit-phase rows excluded, leaving 69 legal select rows;
- report extensions used zero times in fit, preprocessing, or selection;
- current held-family auxiliary fit/select use is zero in every protocol;
- stream-consumer, hydraulic-system, and cooler-motor fit/select use is zero;
- report gradient and threshold updates are zero;
- target-alignment gaps and missing-feature zero fills are zero;
- review is zero;
- cooler-motor has zero fit/select/report/metric-label use and remains sealed.

The frontend used mature AfterImage current-packet-inclusive statistics with a
fresh reset for each auxiliary source, no future packet, and no raw-label state
input.  The official TabM v0.0.3 implementation was used at upstream commit
`a507095893d784c5702059d737ddfbd1299c41dd` under Apache-2.0.

Runtime was about 16 minutes 41 seconds.  Batch MaxRSS was `4,666,136 KiB`
(about 4.45 GiB), confirming that later jobs should request measured rather
than oversized memory.

## Scientific interpretation and claim boundary

CKBO is useful because it separates three questions that were previously
mixed together:

- **Frontend information:** AfterImage115 contains transferable normal-process
  evidence for predictive and hydraulic.
- **Normal diversity:** additional legal normal sources improve those two
  families but do not generalize to stream or IP-camera.
- **Decision transfer:** a verifier that is perfect on 69 support-val attacks
  can still suppress future attacks heavily, so attack preservation cannot be
  certified from that small gate alone.

This result does not prove that raw traffic lacks a general solution, and it
does not justify family-specific tuning on stream or IP-camera.  It does reject
the current combination of finite AfterImage115 statistics, limited auxiliary
normal diversity, deterministic multiscale contrast, and a symmetric TabM
attack-versus-benign verifier.

The result is paper-usable as a single-seed development ablation and failure
analysis.  It is not positive final evidence: stream and IP-camera each have
only one source, the canaries are already-used development probes, only seed 27
was run, and the sealed cooler final is intentionally unopened.

## Next action

Do not run CKBO seeds 37/47, do not tune on stream/hydraulic/IP-camera report
labels, and do not repeat the contrast representation.

The next result-producing route should preserve raw AfterImage115 as the mature
process frontend control and replace the symmetric attack-versus-benign
verifier with a one-sided, source-held-out calibrated normal-evidence test.
Its fit/select protocol must broaden legal normal-family coverage and select
calibration by held-out source/family, while C1 remains the high-recall attack
anchor.  It must include a raw115/no-aux control and must fail closed to `hard`
when normal evidence is not confidently transferable.  Only a result that
improves multiple legal unseen families and preserves future/major-family
attack recall can open more seeds or the sealed final family.

```text
solved: CKBO seed 27 completed and decomposed mature AfterImage representation, legal normal diversity, and contrast effects.
changed_mainline: yes; deterministic contrast and the symmetric TabM verifier are rejected, while raw AfterImage115 remains a useful mature frontend control.
active_blocker: source/family-transferable one-sided normal evidence with future-attack preservation is not yet demonstrated.
frozen: strict 1M/T0 manifests, 385/69 support roles, permanent canary zero use, cooler sealed, review=0, source/episode inference units, and C1 attack-anchor semantics.
superseded: CKBO seeds 37/47, multiscale-contrast promotion, symmetric attack-vs-benign verifier scaling, and report-family threshold tuning.
next_action: preregister one source-held-out normal-evidence calibration experiment using mature components and raw AfterImage115 control, then run one result-producing seed-27 dual-partition job.
```
