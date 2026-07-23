# CKBU unified causal process rescue — preregistered seed-27 experiment

## Status entering CKBU

CKBQ is a valid `NO_GO`, not an adequate detector and not a generalization
breakthrough.  Its primary reduced four held OOD hard rates, but overall attack
hard recall fell from `91.300%` (C1) to `84.354%` (`-6.945 pp`).  CKBU therefore
tests whether new observable process information can preserve the OOD signal
while recovering attack evidence.  It does not tune CKBQ thresholds after the
fact and does not reinterpret the CKBQ result as success.

## One frontend contract

Both Gotham and ToN-IoT raw captures are decoded by the HPC-provided mature
`TShark 4.6.6`.  A single 51-dimensional causal schema is computed in this
order:

1. decode the current packet;
2. emit current-packet plus source-local past-state features;
3. record `feature_available_time`;
4. update state with the current packet.

Every physical capture starts from fresh anonymous node/flow state.  The input
contains no source identity, dataset identity, device identity, label, attack
name, raw IP address, or numeric stream identity.  Connection-final duration,
final state, and total future packet/byte counts are not model inputs.
Retransmission and loss indicators are TShark's online dissection at the current
packet.  Raw labels are never requested from TShark and never update state.

Gotham processed rows are read only to align immutable recorded targets by
timestamp and packet fingerprint; their label column is not read.  ToN Zeek
connection metadata is used offline only to locate legal fit targets in raw
PCAP.  The model row is the last uniquely aligned packet prefix at or before
that fit connection's completion; Zeek duration and connection-final values do
not enter the feature vector.  Multiple targets collapsing onto one packet are
rejected.

## Frozen roles

- Original Gotham strict 1M roles, the 26-source CKBE manifest, and their
  hashes are unchanged.
- Four CKBI sources remain `report-only`; they contribute zero fit,
  preprocessing, threshold, or model-selection rows.
- CKBO auxiliary Gotham sources retain their frozen `11 fit / 5 select / 15
  predictive-maintenance report` source split.
- ToN `normal_1` is benign fit; `normal_2` is source-disjoint benign select.
- ToN Scan capture 1 and Password capture 1 contribute 2,000 causal fit rows
  each, reconstructed from the frozen CKBT manifest and checked against its
  exact Zeek-row hashes.
- ToN Injection and MITM are reserved with `model_use=0`.  They cannot be
  opened for this seed-27 route decision.
- Stream-consumer and hydraulic-system remain used development canaries, not
  untouched final sets.  Cooler-motor remains sealed.

For each strict held protocol, the held family is absent from C1 fit and
calibration, process-head fitting and preprocessing, legal select/gate data,
and all hard-pair construction.  Report processing is fixed-weight,
no-gradient, and label-free until metric calculation.

## Shared head, not family patches

There is one process head over the same 51 features, not one expert per attack.
All 385 legal Gotham `support_train` rows participate in every epoch.  The fit
set also includes the legal Gotham benign fit rows, the frozen CKBO auxiliary
benign fit sources, and ToN process/normal fit rows.  Attack families and benign
sources receive group-balanced sample weights while every row is visited.

Two mature heads are compared:

- `ExtraTrees` as a strong low-variance tabular control;
- the vendored official `TabM v0.0.3` component as the registered primary
  process head.

No TGN, new dynamic GNN, per-family expert, score addition, review queue, DANN,
Fishr, prototype bank, or report-specific rule is introduced.

## Legal gate and asymmetric decision

For each head, the exact threshold frontier consists only of legal
`support_val` attack scores plus a below-minimum sentinel.  Eligibility first
requires process-head attack recall to preserve C1 support recall within
`0.5 pp` and every support family with at least three rows within `2 pp`.
Among eligible points, the selected point minimizes process hard rate on legal
benign select rows (original legal select, frozen auxiliary select, and ToN
`normal_2`).  No report score or label is consulted.

The primary decision is:

```text
frozen CKBQ hard
OR strong shared-process attack evidence
-> hard attack
```

This is not a score sum.  It permits the process head to rescue both CKBQ
suppressions and attacks missed by C1.  The frozen CKBQ branch retains its
normal-process suppression when the process head does not produce strong attack
evidence.  Review is exactly zero.

## Seed-27 outputs and stop rule

The paired AMD/Intel jobs are identical and fully output-isolated.  Either or
both may finish safely; neither job auto-cancels the other.  Only seed 27 runs.
The result emits C1, frozen CKBQ, ExtraTrees, and TabM comparisons for:

- overall/support/same-file/future/sealed/domotic/combined attack recall;
- every attack family and worst-family recall;
- IP-camera-street, predictive-maintenance, stream-consumer, and hydraulic
  strict OOD hard rates;
- full support usage, group weights, preprocessing, role exclusion, feature
  coverage, loss curves, hashes, environment, wall time, and Slurm identity.

`GO_SIGNAL` requires all of the following at seed 27:

- overall attack delta versus C1 is at least `-0.5 pp`;
- no attack family with at least 15 report rows drops more than `2 pp` versus
  C1;
- every required held OOD family improves at least `5 pp` versus C1 and has
  hard rate at most `90%`;
- all 385 support rows are used, every gate satisfies its legal attack
  constraint, report/held leakage is zero, alignment is complete, and
  `review=0`.

A single-seed `GO_SIGNAL` only authorizes seeds 37/47 and a new final held
family/source.  It is not the final paper claim.  `NO_GO` ends this process-head
route without adding family-specific patches.
