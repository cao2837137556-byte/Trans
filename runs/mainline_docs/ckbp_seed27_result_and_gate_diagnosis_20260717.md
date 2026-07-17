# CKBP seed-27 formal result and gate-degeneracy diagnosis

Date: 2026-07-17

Canonical job: AMD `151835`

Experiment commit: `af9366a340b7348e0ace389f1f13fce639c4e61a`

Pullback SHA-256: `0bfe9ffc55967ebeca15ac46c5919f2e0826eff390287493e3908e53d40212f8`

## Bottom line

The formal job is operationally valid and all registered data-use contracts pass, but the primary `M2-CappedSourceConformal` result is **protocol-degenerate and cannot be interpreted as open-world generalization evidence**.

The apparently excellent OOD hard rates—stream `2.1333%`, ip-camera-street `2.1333%`, predictive-maintenance `10.6667%`, and hydraulic `8.1667%`—are explained almost exactly by the 64-event fail-closed cold-start window. The selected verifier threshold is `1.0`; every warmed reliable conformal score is mathematically smaller than `1.0`. Consequently, after burn-in the gate suppresses essentially every event, including attacks. Overall attack hard recall collapses from C1 `91.2997%` to `0.1451%` (`-91.1547 pp`).

This document therefore supersedes any preliminary interpretation that the CKBP M2 OOD numbers were a real positive generalization result.

## What is valid

- Slurm job `151835` completed `0:0` on AMD in 574 seconds; MaxRSS was `4,171,492K` under a 16 GB request.
- The pullback archive checksum passes.
- The recorded commit and environment match the registered run: Python `3.9.25`, NumPy `2.0.1`, pandas `2.3.3`, scikit-learn `1.6.1`.
- The original strict 1M split and frozen T0 manifests were not modified.
- `385` support-train rows and `69` support-val rows are fully accounted for.
- Report-only sources have zero fit/select use; permanent canaries remain excluded from fit/select; cooler remains sealed.
- Target alignment and report-source coverage are complete; review is exactly `0`.
- The registered result is correctly classified as `NO_GO`; seeds 37/47 must not run.

These checks establish execution and data-contract integrity. They do not rescue the scientific interpretation of the M2 gate.

## Registered performance

### Attack preservation

| Candidate | Overall | Same-file | Future | Sealed | Domotic | Combined | Delta vs C1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| M0-C1 | 91.2997% | 63.5157% | 86.8340% | 97.2508% | 88.8667% | 71.1216% | 0.0000 pp |
| M1-GlobalNormalConformal | 82.2499% | 55.0282% | 70.4264% | 96.9629% | 79.7333% | 61.7626% | -9.0498 pp |
| M2-CappedSourceConformal | 0.1451% | 0.0000% | 0.1682% | 0.0581% | 2.0667% | 1.0197% | -91.1547 pp |

Support-val recall is reported as `100%` for M2, but this is not preservation evidence: all 69 support-val rows are still inside the 64-row-per-source cold-start window and receive the fail-closed score `1.0`.

### Strict Level-2 OOD hard rates

| Held family | M0-C1 | M1 global | M2 capped source | M2 cold-start rows | M2 observed hard rows |
|---|---:|---:|---:|---:|---:|
| ip-camera-street | 100.0000% | 5.4667% | 2.1333% | 64 / 3,000 | 64 / 3,000 |
| predictive-maintenance | 100.0000% | 55.4889% | 10.6667% | 960 / 9,000 | 960 / 9,000 |
| stream-consumer | 100.0000% | 26.9000% | 2.1333% | 64 / 3,000 | 64 / 3,000 |
| hydraulic-system | 72.3667% | 42.8333% | 8.1667% | 320 / 3,000 | 245 / 3,000 |

Hydraulic has 320 cold-start rows across five sources, but the final hard decision is `C1_candidate AND verifier`; only 245 of those cold rows pass C1. This explains its observed count without invoking learned source adaptation.

## Deterministic failure mechanism

### 1. Warmed scores cannot reach the selected threshold

`empirical_normal_p()` uses the finite-sample rank

```text
p = (1 + number_of_reference_values_at_least_as_extreme) / (N + 1)
```

so `p >= 1/(N+1)`. The warmed attack score is `1 - p`, therefore it is always strictly less than `1.0`.

The provisional cold/unreliable branch instead assigns `attack_score = 1.0`.

### 2. All support-val attack rows are cold

The 69 support-val rows occur in three sources with `23`, `6`, and `40` rows. Each source is reset and each count is below burn-in `64`, so every support-val score is exactly `1.0`.

The exact gate frontier is built from support-val attack scores. It consequently selects verifier threshold `1.0`, records support-val hard recall `100%`, and appears to satisfy the attack-preservation constraint.

### 3. The gate keeps only the provisional window

The final non-C1 decision is `verifier_score >= threshold`; fused candidates additionally require C1. With threshold `1.0`, warmed reliable events cannot pass. Thus:

- the first 64 rows of each source are fail-closed hard candidates;
- nearly all later rows are suppressed regardless of whether they are benign or attacks;
- M2, unbounded-source, and local-robust ablations become numerically identical on all four held families and on overall attack recall.

The equality of three supposedly different source-adaptation candidates is an additional falsification check: the endpoint gate erases their mechanism differences.

## State-population problem

The report state is built from `frozen_scored_target_rows_only`; there are zero memory-only/background events. Under global attack preservation, the report history contains `243,981` attack events and zero benign events across six sources. Under held OOD protocols, report history contains only benign OOD rows.

This does not read raw labels during the update, but the event population is class-conditioned by construction. It is not a deployment-equivalent unlabeled stream. A stable attack cohort can therefore become its own apparent source-local normal history.

For M2, every report source clips the bounded shift at the registered upper bound `0.367552` on every post-burn-in row. Across global attack report rows, `274,924 / 277,326` history updates are accepted (`99.13%`) and only `0.87%` are rejected. This is saturated adaptation, not evidence of a calibrated transferable source normalizer.

## The one interpretable positive signal

`M1-GlobalNormalConformal` does not use the cold-start sentinel and remains interpretable as a static normal-evidence control:

- stream OOD hard falls from `100%` to `26.9%`;
- ip-camera-street falls to `5.4667%`;
- predictive-maintenance falls to `55.4889%`;
- hydraulic falls from `72.3667%` to `42.8333%`.

This is evidence that raw AfterImage115 plus a benign-only global conformal score contains cross-family normality signal. It is not a solution: overall attack recall drops `9.0498 pp`, with future attack recall down `16.4075 pp`. Sealed attack is much less affected (`-0.2879 pp`), so the remaining attack conflict is strongly source/role dependent rather than uniform.

## Scientific classification

- **Execution/data contracts:** valid.
- **Registered M2 scientific decision:** `NO_GO`.
- **M2 OOD generalization claim:** invalid due to deterministic gate degeneracy.
- **M1 static normal-evidence control:** valid negative/diagnostic result with real OOD ranking signal but unacceptable attack loss.
- **Stream solved:** no.
- **Run seeds 37/47:** no.
- **Repeat CKBP unchanged:** no.

## Required repair before another result job

1. Separate the scientific evidence score from the operational fail-closed state. Cold/unreliable status must be an explicit mask and must never be encoded as the maximum verifier score used for threshold selection.
2. Reject any selected gate at or above the maximum attainable warmed score, and require post-burn legal attack examples in gate validation.
3. Redesign support selection or burn-in so legal support-val contains warmed attack evidence. The current `23 + 6 + 40` lineage cannot certify a 64-row history gate.
4. Populate state from the same label-free, past-only full-stream background for attack and OOD protocols, then score target rows. Do not adapt on class-conditioned target-only cohorts.
5. Export record-level or source/time-bin diagnostics: C1 score, base nonconformity, adapted score, cold/reliable flags, update acceptance, threshold, and final hard decision. The current pullback cannot reconstruct a non-degenerate threshold offline.
6. Add a deterministic pre-submit test proving that warmed far-from-normal attacks can still cross the selected gate. The existing contract smoke did not test the score-range/threshold coupling.
7. Retain M1 global normal evidence as a control, but do not treat source-local adaptation as established until it beats M1 under a non-degenerate gate and a deployment-equivalent state stream.

The next experiment should answer one narrow question: whether normal-evidence calibration still reduces unseen-family false alarms after the cold-start artifact is removed **while preserving C1 attacks**. It should not add another model family until this protocol question is resolved.
