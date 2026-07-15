# CKBN stream separability diagnostic preregistration

Date: 2026-07-15  
Seed: 27

## Question

CKBN is a narrow diagnostic, not a new detector. It asks whether the persistent
`iotsim-stream-consumer` failure is primarily:

1. missing or entangled information in the current portable causal frontend;
2. transferable ranking signal that the current threshold/gate fails to use; or
3. a family-dependent mixture, especially confusion with UDP scan/flood traffic.

## Frozen model scope

- Fit rows: `support_train/fit`, `id_calib/fit`, and `ood_val/fit` only.
- Every one of the 385 legal `support_train` rows is retained.
- `iotsim-stream-consumer`, `iotsim-hydraulic-system`, and
  `iotsim-cooler-motor` are excluded from fit, source-OOF threshold selection,
  normalization, and feature selection.
- Thresholds are selected only from legal leave-one-source-out fit predictions,
  with the CKBL attack-preservation constraints.
- Source identity and device identity are audit fields, never model features.
- The raw processed label column is not read by the canonical frontend.

## Frozen report cohorts

- Stream: `ood_stress/select`, device family `iotsim-stream-consumer`, at most
  3,000 rows selected by a stable hash of source and recorded index.
- Hydraulic control: `ood_val/select`, device family
  `iotsim-hydraulic-system`, at most 3,000 rows by the same rule.
- Attacks: `future_query/all`, at most 2,000 rows per attack family, selected by
  the same stable hash. Attack labels are used only to define report strata
  after the fit protocol has been frozen.

The report cohorts contribute zero gradient, zero standardization statistics,
zero threshold candidates, and zero feature/model selection decisions. Results
are diagnostic evidence only and cannot promote a candidate.

## Frozen representations and probe

Reuse CKBL without inventing another backend:

- exact CKBE event message (`TGN9_exact`, 9D);
- current portable fields (`Current20`, 20D);
- compact causal process fields (`CompactProcess69`, 69D);
- current C1 CICFlow-style block (`C1_207_upper_bound`, 207D).

The probe is CKBL's group-balanced sklearn HistGradientBoosting classifier. All
report features are causal, source-local, score-before-update, and based on
label-free past events.

The formal result run reads every raw source in full and replays timestamp
ascending with recorded-index tie breaking. Prefix reading is permitted only
for local engineering and is not eligible for the CKBN scientific diagnosis.

## Interpretation rule

For each representation, report pairwise AUROC between each benign canary and
every future attack family, plus hard rates at the frozen legal threshold.
Packet rows are not treated as independent replicates; per-source results and
family-macro summaries are reported without packet-level significance claims.

The primary stream diagnosis uses `C1_207_upper_bound`:

- `TRANSFERABLE_RANK_SIGNAL_WITH_GATE_FAILURE` when family-macro AUROC is at
  least 0.75 and stream-vs-UDP-Scan AUROC is at least 0.70 while stream hard
  rate remains at least 0.90;
- `CURRENT_FRONTEND_ENTANGLED_OR_INSUFFICIENT` when family-macro AUROC is below
  0.60 or stream-vs-UDP-Scan AUROC is below 0.55;
- `MIXED_FAMILY_DEPENDENT_SIGNAL` otherwise.

If C1 has transferable signal but `CompactProcess69` does not reach 0.70 macro
AUROC and 0.65 against UDP Scan, the secondary interpretation is
`COMPACT_PROCESS_ADAPTER_INSUFFICIENT`.

These boundaries classify the known failure. They are not go/no-go thresholds
for a future detector and must not be optimized on stream or hydraulic.
