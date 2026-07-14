# CKBM Seed-27 Formal Result

Date: 2026-07-14

Experiment: `issue27ckbm_tabm_causal_source_calibration_v1`

Compute job: AMD `151583`

Scientific compute commit: `37b0fb4585d2634fa45fa2db31b1fead7bce886d`

Metadata-recovery commit: `1d25fc638691a58063087f86bac62caf9677d4c5`

Seed: `27`

## Verdict

CKBM is a validated **diagnostic `NO_GO`**. The recovered formal validator
passed with zero errors and no model retraining, but the registered candidate
`M3-TabM-CSR` did not solve the hard open-world case:

- stream-consumer hard OOD alarms changed only from `100.0%` to `99.6%`;
- hydraulic-system changed from `100.0%` to `45.33%`;
- overall attack hard recall changed from `99.9795%` to `99.5464%`
  (`-0.4331 pp`), while the source-bootstrap interval for the delta was
  `[-0.9670, -0.0286] pp`;
- UDP Scan recall fell from `100.0%` to `28.32%` (`-71.68 pp`);
- `review=0` throughout.

The registered `NO_GO` checks are `stream_signal_missing` and
`major_attack_family_drop_over_2pp`. Seeds 37 and 47 must not be launched.

This result is not eligible to be presented as a paper-grade strict held-out
benchmark result. Post-run audit found that the implementation enforced
exclusion of the *current* held family, but did not enforce the stronger
project rule that both previously used development canaries --
stream-consumer and hydraulic-system -- have zero use in every fit,
standardization, and select scope. The result remains useful as a negative
diagnostic because it rejects the tested route rather than supporting a
positive claim.

## Artifact integrity and execution

- Pullback archive SHA-256:
  `9c0c312788bfe39a60966f14a92f15e693959fcd32c3c941a1dd5aaccaa4fc77`.
- `formal_validation.json`: `status=PASS`, `errors=[]`.
- Job `151583` completed all scientific CSV computation, then failed only in
  the first metadata JSON write because the cluster Python rejected
  `Path.write_text(newline=...)`.
- Metadata recovery generated the decision and pullback without retraining:
  `models_retrained=false`.
- Runtime: `23m18s`, 8 allocated CPUs, `TotalCPU=02:01:44`, batch
  `MaxRSS=5,547,060 KiB` (about 5.3 GiB).
- All target alignments were complete; report extensions had zero recorded
  fit/select use; causal audits recorded score-before-update, source reset,
  label-free state updates, no gradients, and no phase-state crossing.
- All 385 legal `support_train` rows were used with family-balanced sampling.

The complete frozen result directory is
`runs/issue27ckbm_tabm_causal_source_calibration_v1_2026-07-14_seed27_amd_151583`.

## Attack preservation

| Candidate | Overall hard recall | Delta vs C1 | Main interpretation |
|---|---:|---:|---|
| M0-C1 | 99.9795% | 0.0000 pp | high-recall anchor |
| M1-ExtraTrees-Global | 79.3010% | -20.6785 pp | catastrophic suppression |
| M2-TabM-Global | 98.3290% | -1.6505 pp | fails overall retention |
| M3-TabM-CSR | 99.5464% | -0.4331 pp | point estimate passes overall gate, family gate fails |
| A1-ExtraTrees-CSR | 89.8738% | -10.1057 pp | catastrophic suppression |

For M3, future attack recall was `99.1575%` (`-0.8045 pp`) and combined
attack recall was `98.2520%` (`-1.7480 pp`). Support-val recall remained
`100%`, showing that the legal support-val gate did not protect all report
attack families.

The largest M3 family failures were:

| Attack family | Rows | C1 recall | M3 recall | Delta |
|---|---:|---:|---:|---:|
| UDP Scan | 113 | 100.00% | 28.32% | -71.68 pp |
| Mirai C&C Communication | 369 | 86.45% | 72.90% | -13.55 pp |
| Merlin C&C Communication | 9,926 | 100.00% | 91.81% | -8.19 pp |

UDP Scan was absent from both `support_train` and `support_val`. The support
bank contains only ten attack families; support-val contains 69 rows from the
same ten-family set. Therefore a classifier trained to distinguish known
support attacks from fit benign traffic can legally pass its support gate yet
suppress an unseen attack family as benign. This is the main scientific
failure, not an execution error.

## Strict Level-2 diagnostic rates

| Candidate | Stream-consumer | Hydraulic-system | IP-camera-street |
|---|---:|---:|---:|
| M0-C1 | 100.00% | 100.00% | 1.87% |
| M1-ExtraTrees-Global | 99.53% | 0.00% | 0.00% |
| M2-TabM-Global | 99.93% | 46.97% | 0.00% |
| M3-TabM-CSR | 99.60% | 45.33% | 0.20% |
| A1-ExtraTrees-CSR | 97.93% | 0.00% | 0.00% |

ExtraTrees' hydraulic result is not usable because its attack preservation is
catastrophic. CSR improves hydraulic only modestly over global TabM and gives
no meaningful stream signal. IP-camera-street was already easy for C1.

Legal select benign hard rates were almost universally zero while the unseen
stream report hard rate remained approximately one. This is direct evidence
of cross-source/family calibration failure.

## Why training size was not the blocker

The global neural fits covered 12,385 unique rows: 12,000 benign rows plus all
385 attack support rows. TabM optimization converged strongly:

- global 207D TabM loss: about `0.2936 -> 0.000754`;
- global 415D CSR TabM loss: about `0.2741 -> 0.001523`;
- strict-stream CSR loss: about `0.3434 -> 0.000241`;
- strict-hydraulic CSR loss: about `0.2948 -> 0.000417`.

The model learned the training problem very well. The failure is that this
closed-set discrimination and its select-time threshold do not transfer to
new normal sources, and sparse attack-family supervision makes symmetric
suppression unsafe for unknown attacks. Larger versions of the same classifier
do not address that mismatch.

## Stronger canary-isolation contract violation

`ckbm_training_weight_audit.csv` records the following development-canary rows
inside benign fit scopes:

- `processed/iotsim-stream-consumer-1.csv`: 4,000 rows;
- hydraulic sources `-1`, `-10`, and `-11`: 1,353 + 869 + 856 = 3,078 rows.

The strict-stream protocol excludes stream itself but still fits on 3,078
hydraulic rows. The strict-hydraulic protocol excludes hydraulic itself but
still fits on 4,000 stream rows. Cross-canary select roles are also present.
Thus the implementation satisfies current-held exclusion, but violates the
project-wide rule that both used development canaries remain outside every
fit/select scope. The existing validator did not encode that stronger rule.

Before any future formal route, validation must fail if either canary has a
nonzero count in training, standardization, negative sampling, hard-pair
construction, or threshold/model selection, irrespective of which family is
currently held.

## Mainline implication

CKBM closes the "replace HistGB with a stronger symmetric backend" branch.
TabM is a useful maintained tabular component, and CSR features preserve
attacks better than global TabM, but neither solves stream. ExtraTrees reduces
some benign alarms only by suppressing large portions of attack traffic.

The next method should retain C1 as the high-recall candidate anchor and make
suppression one-sided: suppress only when a mature, source-held-out calibrated
normality model provides strong normal evidence; unknown or ambiguous process
evidence remains hard attack. Calibration must be selected without either
development canary and tested under source/episode-level uncertainty. This is
a route change, not another threshold sweep or a larger classifier.

## Close-out

```text
solved: CKBM seed-27 compute, metadata recovery, pullback integrity, and formal result diagnosis are complete.
changed_mainline: yes; symmetric TabM/ExtraTrees candidate suppression is rejected.
active_blocker: safe source-held-out normal-evidence calibration that transfers without suppressing unseen attack families.
frozen: seed 27 artifacts, validator PASS, diagnostic NO_GO, review=0, and no seeds 37/47.
superseded: the same TabM/ExtraTrees route, larger versions of it, and any positive strict claim from this run.
next_action: encode all-canary zero-use validation, then preregister one-sided normality suppression with C1 attack-preservation constraints.
```
