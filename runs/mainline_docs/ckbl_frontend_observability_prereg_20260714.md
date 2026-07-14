# CKBL frontend observability preregistration

## Question

Before another temporal backend is promoted, determine whether the legal fit
data contains transferable evidence for both sides of the open-world problem:

1. an unseen benign source should not be called attack merely because its
   device/process is novel;
2. an unseen attack family and its source should still receive higher attack
   evidence than an unseen benign source.

This is the feature-information gate for the next method. It is not a repair
targeted at stream-consumer or hydraulic-system and it is not a final IDS run.

## Frozen data boundary

Only these rows are eligible:

- `support_train/fit`: attack;
- `id_calib/fit`: benign;
- `ood_val/fit`: benign.

The following device families have zero feature, fit, threshold, hard-pair,
and decision use:

- `iotsim-stream-consumer` (development canary);
- `iotsim-hydraulic-system` (development canary);
- `iotsim-cooler-motor` (sealed final holdout).

No select, query, future, sealed, or report row is eligible. Source/device and
attack-family metadata define outer groups and audits only; they are not model
features. Raw processed labels are not read by the frontend.

## Mature components and fixed probes

CKBL reuses the existing label-free canonical-time frontend and sklearn
`HistGradientBoostingClassifier`. HistGB is only an information probe; CKBL
does not claim it as the final backend.

The feature bundles are fixed before results:

| bundle | dimension | role |
|---|---:|---|
| `TGN9_exact` | 9 | exact portable CKBE message baseline |
| `Current20` | 20 | current packet/protocol evidence only |
| `CompactProcess69` | 69 | causal current + pair/biflow process statistics |
| `CompactProcess69_history_permuted` | 69 | noncausal negative control; never a candidate |
| `C1_207_upper_bound` | 207 | existing CICFlow-style engineered upper bound |

The compact process schema uses current fields plus duration, recent/mean IAT,
packet/byte rate, mean length, SYN/ACK/RST/FIN rates for pair and biflow at
windows 16 and 128, bidirectional balance, and short/long activity ratios. It
is a narrow adapter over the existing frontend rather than a new parser.

## Strict outer protocols

### Unseen source pair

For every legal benign-source/attack-source pair, remove both complete sources
from training and evaluate them together. This directly tests source transfer
on both classes.

### Unseen attack family plus origin

For every legal attack family, remove that family, every source containing the
family, and one rotating benign source. Evaluate only the held attack family
and held benign source. This prevents a nominal family holdout from retaining
the same source distribution in training.

When remaining source diversity permits it, thresholds are selected from
inner leave-one-source-out predictions under attack-preservation constraints.
Outer test labels never select thresholds. AUROC is primary because CKBL is an
observability audit rather than the final C1 hard-candidate gate.

Training weights give equal total mass to attack and benign; benign sources are
balanced within benign, and attack families are balanced within attack.

## Registered interpretation gate

A complete run requires full-source chronological replay, all 385 legal
support rows, all 10 attack labels, and all 8 permitted sources. A compact
process signal requires all of:

- unseen-source macro AUROC at least 0.75;
- unseen-family-origin macro AUROC at least 0.70;
- compact process exceeds exact 9D by at least 0.03 in both protocols;
- ordered compact process exceeds its history-permuted control by at least
  0.02 in both protocols.

The C1 207D upper bound determines what to do after this gate:

- 207D strong, 69D weak: the information exists but the portable adapter is
  insufficient;
- both weak: another TGN/GraphMixer head cannot manufacture the missing
  cross-family information, so inputs/data contract must change;
- 69D strong with an order-control gap: a mature sequence backend is justified;
- ordered and permuted similar: any gain is not credible temporal evidence.

A bounded prefix run is allowed only as local real-data implementation evidence
and is always reported as truncated/non-formal. No result in CKBL opens or
tunes against the development canaries or sealed final holdout.

## Pre-formal passive-state hardening addendum

This addendum was frozen before the complete full-source run and after the
bounded implementation result. It does not use any report-canary score.

For a selected fit target, the frontend may consume unassigned, label-free raw
events that are earlier in actual timestamp order. However, every raw row that
is explicitly known through role metadata as a non-selected target is blocked
from updating fit-time state. This includes support-val, select, same-file,
future, sealed, report, and locally capped-out targets. Selected fit targets
remain allowed and are scored before their own state update.

The complete plan contains 198,173 distinct known non-selected target rows to
block across the eight relevant sources. The block list has zero intersection
with the 8,671 selected fit rows. The output must include the role/phase block
lineage and selected-target `state_update_allowed=true` evidence.

This hardening prevents an interleaved select/report target from becoming
fit-history context merely because its recorded row occurs earlier in canonical
time. Unassigned raw events remain label-free passive context; they are not
self-supervised examples and provide no gradient, threshold, or target label.
