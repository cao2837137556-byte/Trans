# CKBL full-source seed-27 formal result

## Decision

AMD job `151564` completed in `00:11:43` with exit code `0:0`.  The formal
validator passed with no errors.  `OBSERVABILITY_NO_GO` is the scientific
verdict, not an execution failure.

The complete experiment changes the diagnosis:

- portable current/flow features contain strong attack-versus-benign ranking
  information under fit-only unseen-source and unseen-family folds;
- the 207D C1 upper bound improves mean unseen-family AUROC over exact TGN9
  from `0.7941` to `0.9176`;
- ordered 69D temporal history does not beat its genuinely changed
  within-source history-permuted control;
- most importantly, high AUROC does not transfer to a stable
  attack-preserving hard threshold.  The active blocker is now cross-source
  and cross-family score calibration, not absence of frontend information.

This result does not evaluate stream-consumer, hydraulic-system, or the sealed
final family.  It therefore does not establish report OOD suppression or a
finished detector.

## Run identity and integrity

- experiment commit: `cdd22972eeb068127328ccbf4a40d1a15a36b843`;
- partition/job: `amd/151564`;
- seed: `27`;
- environment: Python `3.9.25`, NumPy `2.0.1`, pandas `2.3.3`,
  scikit-learn `1.6.1`;
- selected fit rows: `8,671` = `385` attack support + `8,286` benign;
- sources: `8`; attack families: `10`;
- outer folds: `25`; model/fold metric rows: `125`;
- all `8,671` target alignments passed;
- raw label column read: `false`;
- selected target state update allowed: `8,671/8,671`;
- known non-selected target rows blocked from fit state: `198,173`;
- outer source overlap and test-label fit/threshold use: `0`;
- stream-consumer, hydraulic-system, and cooler-motor model use: `0`;
- review: `0`; sealed-final model use: `0`.

The independently recomputed aggregate matches the saved aggregate at
`1e-12` tolerance.  All 18 data/metric checks in
`independent_validation.json` pass.

## Threshold-free representation results

| Protocol | Bundle | Mean AUROC | Worst-fold AUROC | Mean AP |
| --- | --- | ---: | ---: | ---: |
| unseen source pair | TGN9 exact | 0.9976 | 0.9824 | 0.9688 |
| unseen source pair | Current20 | 0.9880 | 0.9433 | 0.9652 |
| unseen source pair | CompactProcess69 | 0.9978 | 0.9766 | 0.9924 |
| unseen source pair | history-permuted 69D control | 0.9979 | 0.9769 | 0.9936 |
| unseen source pair | C1 207D upper bound | 0.9927 | 0.9605 | 0.9862 |
| unseen attack-family origin | TGN9 exact | 0.7941 | 0.4568 | 0.5264 |
| unseen attack-family origin | Current20 | 0.7782 | 0.4787 | 0.5421 |
| unseen attack-family origin | CompactProcess69 | 0.8895 | 0.6776 | 0.6807 |
| unseen attack-family origin | history-permuted 69D control | 0.8989 | 0.7879 | 0.7253 |
| unseen attack-family origin | C1 207D upper bound | 0.9176 | 0.7095 | 0.7156 |

The permuted control changed `96.97%` to `100%` of rows and `52.54%` to
`69.64%` of history cells per source.  Its parity or improvement is therefore
not caused by a no-op permutation.  CKBL supplies no evidence that ordered
history is the transferable mechanism.

## Operational threshold failure

Thresholds were selected from inner source-held-out fit data under the frozen
attack-preservation constraints.  They were not selected from an outer fold or
report label.

| Protocol | Bundle | Evaluable folds | Attack recall | Worst-family recall | Mean benign FPR |
| --- | --- | ---: | ---: | ---: | ---: |
| unseen source pair | TGN9 exact | 15/15 | 1.0000 | 1.0000 | 0.4940 |
| unseen source pair | Current20 | 15/15 | 1.0000 | 1.0000 | 0.9800 |
| unseen source pair | CompactProcess69 | 15/15 | 0.9969 | 0.5556 | 0.3310 |
| unseen source pair | history-permuted control | 15/15 | 1.0000 | 1.0000 | 0.3066 |
| unseen source pair | C1 207D upper bound | 15/15 | 1.0000 | 1.0000 | 0.4858 |
| unseen family origin | TGN9 exact | 4/10 | 1.0000 | 1.0000 | 0.7967 |
| unseen family origin | Current20 | 4/10 | 1.0000 | 1.0000 | 0.9609 |
| unseen family origin | CompactProcess69 | 4/10 | 1.0000 | 1.0000 | 0.2986 |
| unseen family origin | history-permuted control | 4/10 | 1.0000 | 1.0000 | 0.7584 |
| unseen family origin | C1 207D upper bound | 4/10 | 1.0000 | 1.0000 | 1.0000 |

The six other unseen-family folds lack complete inner source-held-out scores,
so no legal hard threshold is reported for them.  Threshold-free AUROC remains
valid for all ten folds, but it must not be presented as deployment-level
false-alarm performance.

The Compact69 worst-family recall of `0.5556` occurs when the held attack
source is `ip-camera-museum-1` and the held benign source is
`building-monitor-3`.  Source-pair benign FPR also ranges from about `0.033`
to `1.0`.  This large between-source threshold shift explains why near-perfect
rank metrics coexist with unusable hard decisions.

## Family heterogeneity

No single feature view dominates every unseen family:

- C1 207D is strong for Merlin ICMP and Mirai GRE/TCP, but its worst unseen
  family is Merlin TCP (`0.7095`) and Mirai UDP is `0.7122`;
- exact TGN9 reaches `1.0` on Merlin TCP and Mirai TCP, but is near chance on
  Merlin UDP (`0.4568`) and several ICMP/GRE/UDP folds;
- Compact69 reaches `1.0` on Merlin ICMP but falls to `0.6776` on Merlin TCP;
- the permuted control improves several TCP/UDP folds, further rejecting a
  claim that the ordering mechanism caused the transfer.

This heterogeneity is evidence for complementary observable fields, not
permission to add scores or tune a family-specific route on report labels.

## Reviewer-safe route decision

1. Do not run seeds 37/47 for CKBL; the preregistered mechanism gate failed.
2. Do not repair and resubmit the same TGN/GraphMixer information path.
3. Keep C1 as the attack-candidate anchor and retain the portable feature views
   as audited inputs, but do not claim that their global probability threshold
   generalizes.
4. The next result experiment must target calibration transfer directly.  It
   should start from a mature calibration/conformal or source-normalization
   implementation, permit only label-free past-only source-local adaptation at
   report time, and compare against the unchanged global-threshold baseline.
5. That experiment must again output actual attack-preservation and report OOD
   hard-alarm metrics, including stream, hydraulic, and IP-camera.  No route
   decision or threshold may use those report labels.

This is the narrowest evidence-supported next step: preserve the frontend rank
signal, solve the unstable decision scale, and avoid another expensive backend
whose mechanism has already failed its control.

## Resources and saved evidence

The completed job used MaxRSS `19,942,468 KiB` (about `19.0 GiB`).  A repeat of
this exact workload would need no more than a `32 GiB` request with safety
margin; no repeat is authorized by this result.

The complete result directory is
`runs/issue27ckbl_frontend_observability_audit_v1_2026-07-14_fullsource_seed27_amd_151564`.
Primary evidence is `fold_metrics.csv`, `aggregate_metrics.csv`,
`fold_contract_audit.csv`, `frontend_alignment_audit.csv`, `decision.json`,
`formal_validation.json`, and `independent_validation.json`.

## Handoff markers

- solved: full-source CKBL observability gate completed and independently validated;
- changed_mainline: yes;
- active_blocker: cross-source/family score calibration and hard-threshold transfer;
- frozen: C1 attack anchor, strict fit/select/report isolation, review=0, sealed final unopened;
- superseded: ordered-history/TGN-first backend promotion under the current feature/task realization;
- next_action: preregister one mature calibration-transfer result experiment before implementation.
