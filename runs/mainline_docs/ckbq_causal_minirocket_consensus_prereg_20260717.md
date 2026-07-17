# CKBQ causal MiniRocket consensus preregistration

Date: 2026-07-17

First seed: 27 only

## Question and route boundary

CKBQ is a result-producing test of one specific hypothesis left open by CKBP:

> Can mature short-range temporal pattern evidence recover the attack
> preservation lost by the static normal-only signal, while retaining that
> signal's transferable reduction of unseen-normal hard alarms?

This is not another TGN repair. It does not train a dynamic graph, invent a
new packet encoder, add review, or tune on stream/hydraulic labels. It combines
three already motivated, separately auditable channels:

1. the frozen C1 flow-level attack anchor;
2. CKBP's global normal-only conformal score from mature AfterImage115;
3. a mature `MiniRocketMultivariate` transform over a 32-event causal window,
   followed by a weighted `RidgeClassifier`.

The 9-dimensional event message is only the temporal sequence channel. It is
not asked to replace the richer flow and AfterImage frontends.

## Why MiniRocket and what is reused

MiniRocket is a mature, published time-series transform with fixed length-nine
kernels, dilation diversity, multivariate channel subsets, bias quantiles, and
PPV pooling. It is appropriate here because sources have few anonymous nodes,
highly repeated edges, short process motifs, and far more reliable event order
than graph topology diversity.

The frozen HPC environment does not contain a certified Numba/sktime runtime,
and dependency installation is forbidden. CKBQ therefore includes a narrow
PyTorch execution port of `sktime/sktime v0.24.1`'s BSD-3-Clause
`MiniRocketMultivariate` implementation. The port retains:

- all 84 fixed length-nine kernels;
- upstream dilation allocation;
- upstream log-uniform channel-combination sampling and RNG order;
- upstream golden-ratio bias quantiles;
- one bias-fit instance per dilation/kernel combination;
- upstream alternating padded/unpadded PPV transform;
- no learned convolution weights.

Only the Numba convolution backend and estimator shell are replaced by batched
CPU `torch.conv1d`. Provenance and license are stored under
`repo/ood/vendor/sktime_minirocket_v0_24_1/`.

## Frozen data boundaries

- The strict 1M split is read-only and unchanged.
- The frozen 26-source CKBE T0 manifest and 4-source CKBI report-only extension
  are read-only and unchanged.
- CKBO's 31-source benign AfterImage extension is reused with its frozen
  11 fit / 5 select / 15 predictive-report source split and manifest SHA-256
  `d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f`.
- A label-free 9D temporal cache is materialized for those same 31 sources from
  the same raw PCAP streams. This changes no role and reads no raw label.
- Stream-consumer, hydraulic-system, and cooler-motor have zero fit,
  normalization, gate, or model-choice use.
- Cooler-motor remains sealed and is not scored.
- Review is fixed to zero.

Each strict held-family protocol excludes the held family from C1 fitting,
normal-model fitting, MiniRocket bias fitting, Ridge supervision,
standardization, threshold selection, and all auxiliary fit/select sources.

## Causal temporal construction

For every frozen target record, the temporal input is the last 32 portable
events ending at the current event. The event channels are:

1. log packet length;
2. TCP indicator;
3. UDP indicator;
4. ICMP indicator;
5. destination-port bucket;
6. TCP SYN;
7. TCP ACK;
8. TCP RST;
9. TCP FIN.

No endpoint identity, source identity, device identity, label, or future event
is a feature. A target is scored from a fixed prefix; there is no mutable
cross-source state. Histories shorter than nine events are unreliable and
fail closed to the original C1 hard decision. They never receive a constant
normal/suppress score.

The implementation rejects any frozen target ordering in which a report target
precedes a fit target, or a report target precedes a select target, within the
same source. This makes the use of causal raw prefixes auditable rather than an
unstated chronological assumption.

Auxiliary temporal sources contain 256 label-free warm-up events plus 600
frozen target events. Every source is independently parsed and aligned; the
manifest stores raw source path, role, schema, target offset, deterministic
event-content hash, target-position hash, and `raw_label_column_read=false`.

## Training

For each protocol:

1. Cap each legal normal fit source at 600 deterministically ordered rows.
2. Fit MiniRocket biases on legal normal fit windows only.
3. Transform the legal normal rows and every legal `support_train` attack row.
4. Fit `StandardScaler` on those transformed fit rows only, with source-
   balanced normal weights and attack-family-balanced attack weights.
5. Fit `RidgeClassifier(alpha=1.0)` using the same fit-only weights.

In the global protocol, all 385 `support_train` rows enter supervised Ridge
fitting exactly once. They do not enter the normal-only AfterImage model.
There is no episode pooling, negative sampling, link-prediction loss, or report
gradient update.

The 69 `support_val` rows are not future-attack test evidence. They are a small
select-only attack gate: they choose thresholds while report roles such as
future/sealed attack remain untouched evaluation. Because 69 rows cannot
statistically prove a population loss below 0.5 percentage point, CKBQ reports
the gate as empirical route evidence only.

## Candidates and registered fusion

The formal result reports:

1. `M0-C1`: unchanged attack anchor.
2. `A0-GlobalNormalConformal`: CKBP's static normal-only control.
3. `M1-ShieldedStatic`: C1 high-confidence shield plus static evidence.
4. `M2-ShieldedTemporal`: C1 high-confidence shield plus temporal evidence.
5. `M3-StaticTemporalConsensus`: preregistered primary.

The primary does not add scores:

```text
C1 below candidate threshold
  -> non-hard

C1 high-confidence shield
  -> hard

remaining C1 candidate with cold/unreliable temporal history
  -> hard

remaining C1 candidate with static abnormal OR temporal abnormal evidence
  -> hard

remaining C1 candidate with static normal AND temporal normal evidence
  -> suppress
```

Thus only joint normal consensus can suppress. Disagreement protects the attack
anchor.

## Threshold selection

Threshold candidates use only legal `support_val` attacks and legal
source-disjoint benign select rows. Report rows contribute zero candidates.

1. Retain only gates that preserve every C1 hard hit on legal support-val rows;
   this is stricter than allowing one miss in the 69-row gate.
2. Enforce the per-family 2 percentage-point empirical constraint.
3. Among eligible gates, minimize legal benign-select hard rate.
4. Break exact ties conservatively: lower C1 shield threshold first, then lower
   evidence thresholds so more rows remain hard.

Every held-family protocol refits and reselects using only its legal non-held
fit/select data. Stream, hydraulic, predictive report, ip-camera report, future
attack, sealed attack, and cooler-motor contribute no threshold information.

## Formal protocols and metrics

The single seed-27 job runs exactly:

1. global attack preservation;
2. strict `iotsim-ip-camera-street`;
3. strict `iotsim-predictive-maintenance`;
4. report-only `iotsim-stream-consumer` development canary;
5. report-only `iotsim-hydraulic-system` development canary.

Attack outputs include overall, support-val, same-file, future, sealed,
domotic, combined, every attack family, worst-family recall, source/episode
bootstrap intervals, and deltas from C1. Strict Level-2 outputs include every
held-family hard rate and C1 delta. Packet rows are not treated as independent
replicates for significance.

The output also includes all 385 support visits, family-weight totals, finite
training loss, causal-window coverage, cold counts, target-order audit,
fit/select/report counts, manifest hashes, model hashes, record-level
predictions, seed, commit, environment, wall time, and Slurm MaxRSS snapshot.

## Seed-27 go/no-go

`M3-StaticTemporalConsensus` is a `GO_SIGNAL` only if all hold:

- overall attack hard recall decreases by no more than 0.5 percentage point;
- no attack family with at least 15 report rows decreases by more than 2 points;
- stream, hydraulic, ip-camera-street, and predictive-maintenance each improve
  by at least 5 points from their protocol-matched C1 baseline and finish at or
  below 90% hard rate (the stream condition therefore implies at least a
  10-point improvement from its current 100% baseline);
- all 385 global support rows are used exactly once;
- all target alignments and temporal phase-order checks pass;
- every cold C1 candidate remains hard;
- no held/report/sealed row enters fit or select;
- review remains zero.

`NO_GO` stops this exact fusion. It does not authorize family-specific tuning,
another seed, or opening cooler-motor. Seeds 37/47 and a new final held source
or second dataset are allowed only after a real seed-27 signal.

## Resources and dual-partition safety

CKBP used 4.0 GiB MaxRSS and 9.6 minutes on AMD with 8 CPUs. A local
MiniRocket microbenchmark transformed 512 x 9 x 32 windows into 3,360 features
in about 0.23 seconds with 8 CPU threads. CKBQ adds five protocol-specific
MiniRocket/Ridge fits plus one label-free pass over the auxiliary PCAPs.

Each independent AMD/Intel copy requests 8 CPUs, 16 GiB, and 4 hours. The
request is based on measured predecessor usage, not maximum availability.
Partition and job ID are present in logs, run roots, auxiliary caches,
archives, and SHA files, so both copies may finish without corrupting or
overwriting one another.
