# A-Tier Experiment Progress Log

> Living document. Maintained during experiments.
> Project: stronger OOD anomaly detection on original-frontend 100D.
> Fixed worktree: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`.
> Last updated: 2026-04-08.

---

## 1. Why This Document Exists

This file is the main research-progress log for the A-tier paper attempt.
It is not a raw run index. The raw run index is `runs/master_experiment_map_v1.md`.

This file records:
- the current paper-level objective;
- the experimental logic from the beginning to now;
- which routes are still alive;
- which routes should be deprioritized;
- key numeric evidence;
- why each major decision was made;
- what to do next.

Maintenance rule:
- after every major experiment, update this file in addition to the run-level `summary.md` and `master_experiment_map_v1.md`;
- keep paper-useful facts and delete or compress dead-end operational details;
- do not turn this into a full run dump.

---

## 2. Current Paper Goal

The practical target is to make the Transformer-side method beat or at least clearly challenge `dA` under the current stronger OOD setting.

Current strongest framing:

> Stronger OOD benign traffic exposes a deployment failure mode of reconstruction-based anomaly detectors. A covariance-aware latent decision rule can recover high attack detection while keeping benign OOD alarms near the dA fixed-threshold level.

Do not frame the paper as merely "Transformer is a newer model than dA". That is too weak.
The paper needs a deployment-oriented story:
- ID benign calibration;
- OOD benign false-alarm stress test;
- high-purity attack detection;
- fixed threshold vs naive calibration vs constrained/gated decision rule;
- why score geometry matters.

---

## 3. Fixed Experimental Setting

Mainline data/protocol:
- feature frontend: original Kitsune frontend, 100D;
- stronger OOD: cross-capture benign OOD evaluation;
- ID benign: formal ID benign calibration/eval split;
- attack evaluation: stage2 high-purity attack set, with boundary/mixed retained when useful;
- default policies:
  - fixed threshold: ID benign q99 / formal fixed口径;
  - naive calibrated: budget=5000, target=1%;
  - constrained: det_floor=50% when used;
- all scoring statistics must come from ID benign train/calibration only. No OOD/attack leakage.

Current dA reference, single-seed seed42 formal fixed:
- fixed OOD alarm: `0.1209`;
- high-purity attack detection: `0.7896`.

This is the hard target we are trying to beat.

---

## 4. Important High-Level Lessons So Far

1. The original Transformer is not simply better than dA under fixed threshold.
   It often has higher alarm and unstable OOD behavior.

2. Naive calibration can suppress alarms but collapses attack detection.
   This is not acceptable as a deployment rule by itself.

3. Detection-constrained thresholding is necessary, but thresholding alone does not fix the Transformer representation.

4. MAE, uncertainty, and compactness mostly lower alarm by suppressing sensitivity.
   They often damage attack detection, so they are not the current main route.

5. Latent contrastive learning with `latent_swap_spike_mix` is the first route that truly raises attack detection potential.

6. The main bottleneck became scoring/decision geometry, not just training loss.
   Mahalanobis revealed very high attack-detection potential but also high OOD benign alarm.

7. The current breakthrough is a two-threshold covariance gate:

   `diagload Mahalanobis low-alarm branch OR raw Mahalanobis high-tail branch`

   This is the first single-seed decision rule that beats dA on both fixed alarm and detection.

---

## 5. Main Timeline and Decisions

### 5.1 Input Reliability and Stronger OOD Setup

Early experiments established that feature/input consistency matters.
We moved away from contaminated or adapter-dependent historical chains and fixed the mainline on original-frontend 100D.

Key role:
- creates a credible input chain;
- avoids mixing clean115/dirty116/adapted results into the stronger OOD mainline.

Important map file:
- `runs/master_experiment_map_v1.md`.

### 5.2 Transformer Self-Audit

Run:
- `runs/frontend100_transformer_self_audit_2026-04-02/`

Conclusion:
- fixed-threshold Transformer underperforms dA because of score distribution and threshold interaction;
- no obvious input/implementation mismatch was found as the dominant explanation;
- attack scores have meaningful signal but threshold placement is unfavorable.

Decision:
- do not blindly rewrite the model;
- inspect score distributions and decision rules.

### 5.3 Detection-Constrained Thresholding

Runs:
- `runs/frontend100_threshold_tradeoff_constrained_2026-04-02/`
- `runs/frontend100_constrained_rule_multiseed_2026-04-03/`

Conclusion:
- naive calibration drives attack detection near zero across detectors;
- detection-floor rules recover meaningful detection;
- multi-seed result shows constrained thresholding is useful, but Transformer still lacks stable fixed-threshold advantage over dA.

Decision:
- decision rules matter;
- still need a stronger Transformer-side signal.

### 5.4 MAE / MAE+TailReg / Uncertainty Lines

Runs:
- `runs/frontend100_mae_v1_2026-04-03/`
- `runs/frontend100_mae_tailreg_v1_2026-04-03/`
- `runs/frontend100_uncertainty_v1_2026-04-04/`

Conclusions:
- MAE lowers OOD alarm but hurts attack detection;
- MAE+TailReg only partially recovers detection and remains far behind dA detection;
- uncertainty/NLL mainly lowers alarm and does not improve separation enough.

Decision:
- deprioritize these lines for the A-tier main route.

### 5.5 Latent Contrastive and Negative Semantics

Runs:
- `runs/frontend100_latent_contrastive_v1_2026-04-04/`
- `runs/frontend100_latent_contrastive_compact_v2_2026-04-04/`
- `runs/frontend100_negative_semantics_ablation_2026-04-05/`

Conclusions:
- latent contrastive learning is the first model-side route that can raise detection;
- `latent_swap_spike_mix` gives high detection potential but also high OOD alarm;
- compactness lowers alarm but often kills detection;
- negative semantics matter, but no single semantic recipe strictly solved the fixed trade-off.

Decision:
- keep `latent_swap_spike_mix` as the main latent checkpoint family;
- stop broad compactness scans.

### 5.6 Offline Scoring and Postprocessing

Runs:
- `runs/frontend100_negative_recipe_rescoring_2026-04-05/`
- `runs/frontend100_score_postprocessing_2026-04-05/`
- `runs/frontend100_locked_candidate_multiseed_2026-04-06/`

Key single-seed result:
- `latent_swap_spike_mix + log_weighted_z_rmse0.5_cos1.0`:
  - fixed alarm: `0.1857`;
  - fixed detection: `0.8233`.

Multi-seed locked candidate result:
- new log-weighted score did not stably beat the old same-recipe score;
- fixed new: alarm `0.2161 ± 0.0549`, det `0.6353 ± 0.1175`;
- fixed old: alarm `0.2220 ± 0.0701`, det `0.6558 ± 0.0909`.

Decision:
- this was not enough to lock as final main candidate;
- need deeper geometry-aware scoring.

### 5.7 Latent Scorer Benchmark and Mahalanobis Direction

Run:
- `runs/frontend100_latent_scorer_benchmark_2026-04-06/`

Key result:
- raw `mahalanobis_ledoitwolf` on no-compact latent:
  - fixed alarm: `0.5843`;
  - fixed detection: `0.9476`;
  - AUC: about `0.8991`.

Interpretation:
- raw Mahalanobis contains very strong attack signal;
- but fixed alarm explodes because benign OOD tail is also amplified.

Decision:
- covariance-aware geometry is important;
- direct prototype/double-center direction scorer failed and should not be the main route.

### 5.8 Covariance-Regularized Training Attempts

Runs:
- `runs/frontend100_covariance_regularized_v1_2026-04-07/`
- `runs/frontend100_mahalanobis_rescue_2026-04-07/`
- `runs/frontend100_covariance_regularized_v2_2026-04-07/`

v1 result:
- covariance-aware training raised detection but did not control fixed alarm.

Rescue result:
- `covreg_v1 best + LedoitWolf diagload f0.2`:
  - fixed alarm: `0.2246`;
  - fixed detection: `0.8919`.

v2 result:
- EMA covariance / tail-aligned loss did not work;
- collapse dimensions worsened;
- fixed alarm remained too high or detection dropped.

Decision:
- do not continue covreg_v2 as currently designed;
- do not assume training covariance directly will solve it.

### 5.9 Systematic Diagload Sweep on No-Compact Latent

Run:
- `runs/frontend100_diagload_sweep_no_compact_2026-04-08/`

Key table:

| scorer | fixed alarm | fixed detection |
|---|---:|---:|
| dA default | `0.1209` | `0.7896` |
| no_compact old-best | `0.1857` | `0.8233` |
| raw Mahalanobis | `0.5842` | `0.9476` |
| diagload `f=0.15` | `0.2151` | `0.8351` |
| diagload `f=0.2` | `0.1812` | `0.7698` |
| diagload `f=0.3` | `0.1469` | `0.6779` |
| diagload `f=0.4` | `0.1251` | `0.6249` |
| diagload `f=0.5` | `0.1091` | `0.5939` |

Conclusion:
- a single diagload factor is not enough;
- when alarm reaches dA level, detection drops too fast.

Decision:
- inspect which attacks are lost and which OOD false alarms are reduced.

### 5.10 Lost-Attack vs False-Alarm Overlap Analysis

Run:
- `runs/frontend100_diagload_overlap_analysis_2026-04-08/`

Key result:
- at `f=0.4`, diagload loses `1557` old-best high-purity detections and reduces `1704` OOD false alarms;
- these two groups are separable by raw Mahalanobis with AUC `0.8808`.

Interpretation:
- the failures are not fully overlapping;
- a composite/gated covariance decision rule is plausible.

Decision:
- test a narrow two-threshold gate before any new training.

### 5.11 Current Breakthrough: Two-Threshold Covariance Gate

Run:
- `runs/frontend100_diagload_gate_rescue_2026-04-08/`

Rule:

`predict anomaly if diagload_f > q99_ID(diagload_f) OR raw_maha > q_ID(raw_maha)`

All thresholds are computed from ID benign only.

Best deployment-like point:
- `diag_f0p5_q99_OR_raw_q0p9995`:
  - fixed OOD alarm: `0.1203`;
  - high-purity attack detection: `0.8373`;
  - ID alarm: `0.0100`.

More detection-oriented point:
- `diag_f0p5_q99_OR_raw_q0p999`:
  - fixed OOD alarm: `0.1273`;
  - high-purity attack detection: `0.8751`.

More aggressive point:
- `diag_f0p5_q99_OR_raw_q0p998`:
  - fixed OOD alarm: `0.1409`;
  - high-purity attack detection: `0.8997`.

Reference:
- dA fixed: alarm `0.1209`, detection `0.7896`.

Current interpretation:
- this is the first single-seed Transformer-side rule that beats dA on both fixed alarm and detection;
- it is still an offline discovery and must be validated across seeds before being treated as a stable result.

---


### 5.12 Gate Multi-Seed Validation

### 5.12 Gate Multi-Seed Validation

Run:
- `runs/frontend100_diagload_gate_multiseed_2026-04-08/`

Purpose:
- Validate the covariance gate discovered on seed42 without retraining or changing checkpoints.
- Gate rules: `diag_f0.5 > q99_ID` OR `raw_maha > q_ID`, with `q?{0.9995,0.999,0.998}`.

Aggregate result:
- `q0.9995`: alarm `0.3816 ? 0.2371`, detection `0.7966 ? 0.1364`;
- `q0.999`: alarm `0.4001 ? 0.2538`, detection `0.8044 ? 0.1314`;
- `q0.998`: alarm `0.4627 ? 0.2972`, detection `0.8832 ? 0.0768`;
- dA reference over the same formal seeds: alarm `0.1322 ? 0.0051`, detection `0.8014 ? 0.0167`.

Interpretation:
- the seed42 covariance gate does not hold under formal multi-seed validation;
- seed 101 has high alarm already in the diagload branch (`diag_ood_alarm?0.4489`), while seed 303 has high alarm in the raw Mahalanobis branch (`raw_ood_alarm?0.5285` at q0.9995);
- therefore this is not just a q-threshold tuning problem. The remaining bottleneck is seed-specific latent tail instability.

Decision:
- do not lock the gate as the final A-tier candidate yet;
- keep the seed42 gate as a diagnostic clue;
- next work should target stabilizing latent covariance tails or add external baselines while keeping the gate result as an ablation.


Run:
- `runs/frontend100_diagload_gate_multiseed_2026-04-08/`

Purpose:
- Validate the covariance gate discovered on seed42 without retraining or changing checkpoints.
- Gate rules: `diag_f0.5 > q99_ID` OR `raw_maha > q_ID`, with `q∈{0.9995,0.999,0.998}`.

Key aggregate results will be read from the run summary. This section should be refined if the gate is promoted to the paper mainline.

Current immediate interpretation:
- if `q0.9995` is stable, it becomes the deployment-like candidate;
- if only `q0.999`/`q0.998` is strong, use it as high-detection operating region but keep alarm discussion explicit.



### 5.13 Latent Tail Seed Diagnostics

Run:
- `runs/frontend100_latent_tail_seed_diagnostics_2026-04-08/`

Purpose:
- Diagnose why the covariance gate discovered on seed42 failed under formal seeds.
- Compare seed42, seed101, seed202, and seed303 covariance tails, raw Mahalanobis tails, and diagload branch behavior.

Initial interpretation:
- seed101 failure is driven mainly by high alarm in the diagload branch;
- seed303 failure is driven mainly by high alarm in the raw Mahalanobis branch;
- seed202 behaves closest to the desired seed42-like pattern.

Implication:
- do not fix this by blindly sweeping global `raw_q`; the bottleneck is seed-specific latent covariance tail instability.

### 5.14 Conditional Covariance Gate Multi-Seed

Run:
- `runs/frontend100_conditional_gate_multiseed_2026-04-08/`

Purpose:
- Test a guarded raw Mahalanobis rescue rule after the unguarded OR gate failed multi-seed.
- Rule: `diag_f0.5 > q99_ID OR (raw_maha > raw_q_ID AND diag_f0.5 > diag_guard_q_ID)`.
- No retraining; all thresholds still come from ID benign only.

Key results:
- Best high-detection conditional point: `cond_gate_f0p5_raw_q0p998_guard_q0p98`, alarm `0.3190 +/- 0.2215`, detection `0.8416 +/- 0.0879`.
- Best low-alarm conditional points around `guard_q0p98` still have alarm around `0.291-0.319`, far above dA alarm `0.1322 +/- 0.0051`.
- q9995 guard98: alarm `0.2913 +/- 0.1881`, detection `0.7883 +/- 0.1341`.
- q999 guard98: alarm `0.2953 +/- 0.1907`, detection `0.7944 +/- 0.1296`.

Interpretation:
- The guard partially fixes seed303's raw-branch explosion, but not enough.
- seed101 remains high alarm because the diagload branch itself is already unstable.
- Decision-layer gating alone is not enough to create a stable A-tier main result.
- The next step should not be another blind q sweep. The next useful choices are external baselines for paper risk control and/or a targeted training-side latent-tail stability fix.

### 5.15 Minimal External Baselines

Run:
- `runs/frontend100_external_baselines_2026-04-08/`

Purpose:
- Add minimal external baselines for A-tier risk control under the same original-frontend 100D + stronger OOD protocol.
- Methods: IsolationForest, OneClassSVM, LOF, and RandomForest as a mixed-attack supervised upper-bound reference.

Key fixed-q99 results:
- dA: alarm `0.1322 +/- 0.0051`, detection `0.8014 +/- 0.0167`.
- IsolationForest: alarm `0.4069 +/- 0.1343`, detection `0.5750 +/- 0.0533`.
- OneClassSVM: alarm `0.8979`, detection `0.9706`.
- LOF novelty: alarm `0.9741`, detection `0.8759`.
- RandomForest mixed-attack upper-bound: alarm `0.9996`, detection `1.0000`, AUC `0.9998`.

Interpretation:
- Simple unsupervised baselines do not solve the stronger OOD fixed-threshold setting; they either under-detect or alarm on most OOD benign traffic.
- RandomForest shows that supervised attack labels can rank high-purity attacks very strongly, but it is not a fair unsupervised deployment baseline and fixed q99 still over-alarms.
- This improves paper risk control: the stronger OOD protocol is nontrivial beyond dA/Kitsune.
- It does not solve the Transformer objective; Transformer still needs latent tail stability if we want it to beat dA stably.


### 5.16 Temporal Frontend v1

Run:
- `runs/frontend100_temporal_frontend_v1_2026-04-08/`

- Minimal temporal stacking experiment: original 100D features are unchanged, but Transformer sees short `[L,100D]` sequences.
- Includes flatten AE temporal control to test whether gains come from temporal context alone or Transformer sequence bias.



### 5.17 Latent Seed Ensemble Stability Check

Run:
- `runs/frontend100_latent_seed_ensemble_2026-04-08/`

Purpose:
- Test whether seed-specific latent covariance tail failures can be stabilized without new training by ensembling formal seeds `101/202/303`.
- This is a diagnostic/upper-bound style experiment, not yet a deployment-simple final model.

Current result:
- No ensemble rule beats dA alarm/det simultaneously; lowest-alarm candidate `ensemble_vote3_gate_q0p9995` has alarm=0.1079, det=0.6539.

Interpretation:
- If ensemble stabilizes alarm while preserving detection, the main problem is seed-specific tail geometry and a training-side stability loss should mimic the ensemble effect.
- If ensemble does not stabilize the trade-off, the issue is deeper than seed-specific threshold tails.



### 5.18 Seed Ensemble ID-Quantile Sweep

Run:
- `runs/frontend100_latent_seed_ensemble_idq_sweep_2026-04-08/`

Purpose:
- Check whether the seed-ensemble scalar scorer only needs a stricter ID-only fixed threshold than q99.
- No OOD/attack statistics are used to define thresholds; ID quantiles only.

Current result:
- A-target hit versus dA q99 reference: `mean_gate_rawq0p999` fixed_id_q0p995 has alarm=0.1261, det=0.8444. Same-quantile dA q995 is alarm=0.1045, det=0.7690, so this should be framed as an operating-region trade-off, not an unconditional q99 fixed win.

Interpretation:
- If this sweep reaches dA-level alarm with higher detection, the deployment rule can be framed as a stricter ID-quantile fixed threshold.
- If not, the remaining issue is not merely q99 threshold anchoring.



### 5.19 Recurrent Deep Sequence Baselines

Run:
- `runs/frontend100_recurrent_deep_baselines_2026-04-08/`

Purpose:
- Add a minimal deep sequence baseline layer for A-tier comparison risk: `LSTM-AE` and `GRU-AE` on stacked original 100D windows.
- This is an unsupervised ID-benign-only baseline, not a Transformer modification.

Current result:
- No recurrent AE baseline beats dA fixed region; lowest-alarm `gru_ae_L4_last` has alarm=0.6341, det=0.7451.

Interpretation:
- If recurrent AEs fail under stronger OOD fixed q99, the evaluation setting is not trivially solved by generic sequence autoencoders.
- If they beat dA, they become required baselines for the paper and Transformer claims must be positioned accordingly.



### 5.20 Ensemble Cost / Seed-Count Ablation

Run:
- `runs/frontend100_latent_ensemble_cost_ablation_2026-04-08/`

Purpose:
- Quantify whether the covariance gate result requires three Transformer checkpoints or can be approximated by 1/2-seed subsets.
- This is a cost/complexity ablation for A-tier deployment discussion; no retraining.

Current result:
- Smallest A-target subset `mean_gate_n2_rawq0p999_idq0p995` subset=202+303: alarm=0.1296, det=0.9013, relative_cost=2.

Interpretation:
- If 2-seed subsets are unstable, the 3-seed ensemble should be framed as a stability/cost trade-off rather than a simple single-model replacement.



### 5.21 Final Candidate Audit Package

Run:
- `runs/frontend100_final_candidate_audit_2026-04-08/`

Purpose:
- Consolidate the current A-tier candidate evidence: covariance-aware Transformer ensemble operating region, dA q99/q995 references, external/deep baseline checks, and cost/complexity table.

Current result:
- 3-seed Transformer ensemble rawq0.999/idq0.995 has alarm=0.1261 and detection=0.8444; dA q99 has alarm=0.1322 and detection=0.8014; dA q995 has alarm=0.1045 and detection=0.7690.

Interpretation:
- Use this as the current decision package before any new model-side work. The claim should remain an operating-region claim, not an unconditional single-model q99 win.



### 5.22 Paper Readiness Handoff

Run/document:
- `runs/paper_handoffs/2026-04-08/a_tier_paper_readiness_handoff_2026-04-08.md`

Purpose:
- Freeze the current paper-facing experimental logic: main candidate, supplement-worthy results, cost table, overclaim boundaries, and figure/table checklist.

Current claim boundary:
- Main claim should be an ID-only operating-region result for a 3-seed covariance-aware Transformer ensemble, not a single-model unconditional q99 win.


## 6. Current Candidate Ranking

### Rank 1: dA Reference Remains the Stability Target

Status:
- dA is not the desired final contribution, but it is still the most stable fixed-threshold reference in the current evidence.
- Multiseed dA fixed: alarm `0.1322 +/- 0.0051`, detection `0.8014 +/- 0.0167`.

Use:
- Treat dA as the deployment-stability bar that Transformer must beat.
- Do not frame this as accepting dA as the final answer; use it as the target to exceed.

### Rank 2: No-Compact Latent + Covariance Gate

Candidate:
- seed42 discovery: `diag_f0p5_q99_OR_raw_q0p9995` reached alarm `0.1203`, detection `0.8373`.

Why kept:
- It was the first single-seed Transformer-side fixed point that matched dA alarm and exceeded dA detection.
- It exposed a real mechanism: diagload controls alarm while raw Mahalanobis rescues lost attacks.

Why not locked:
- Formal seeds did not hold: q9995 gate alarm `0.3816 +/- 0.2371`, detection `0.7966 +/- 0.1364`.
- Conditional guard did not fix it: best guard98 variants still have alarm around `0.29+`.
- This remains a diagnostic signal and possible design seed, not a stable main result.

### Rank 3: Old-Best Log-Weighted Score

Candidate:
- `latent_swap_spike_mix + log_weighted_z_rmse0.5_cos1.0`.

Single-seed:
- alarm `0.1857`, detection `0.8233`.

Multi-seed:
- alarm `0.2161 +/- 0.0549`, detection `0.6353 +/- 0.1175`.

Why kept:
- simple scalar score;
- useful reference for latent recipe behavior.

Why not main:
- detection drops under formal multi-seed;
- alarm remains above dA.

### Rank 4: Raw Mahalanobis / Mahalanobis + Diagload

Why kept:
- raw Mahalanobis has very high detection and strong separation signal;
- diagload gives a clear alarm/detection trade-off and helped discover the gate mechanism.

Why not standalone:
- raw Mahalanobis alarm explodes;
- single diagload smooths too aggressively and loses detection as alarm approaches dA.

### Deprioritized Lines

- MAE / MAE+TailReg: lowers alarm but kills detection.
- Uncertainty: numerically stable but not better separation.
- Compactness v2/v3: does not achieve stable detection-alarm improvement.
- Prototype/double-center scorer: failed in current latent space.
- covreg_v2: training objective misaligned, collapse worsened.

---

## 7. A-Tier Readiness Assessment

Current state:
- not yet enough for a stable A-tier claim;
- seed42 gate result is promising but failed formal multi-seed stability;
- the strongest paper-useful contribution so far is the diagnosis of stronger-OOD failure modes and covariance-tail instability, not a locked final model.

Main weakness:
- fixed-threshold Transformer behavior is not stable across seeds.
- additional baselines beyond Kitsune/dA are still needed for A-tier credibility.

What is still missing:
1. a stable Transformer-side method that beats dA under fixed deployment-like thresholds;
2. additional baselines beyond Kitsune/dA;
3. clearer positioning of stronger OOD protocol as deployment-oriented evaluation, not as an invented OOD concept;
4. proof that threshold/gate parameters are not tuned on OOD/attack.

A-tier risk:
- if only compared to dA/Kitsune, reviewers may say the baseline set is too old or too narrow;
- if only seed42 gate is shown, reviewers will reject it as seed-specific tuning.

Recommended baselines:
- unsupervised: IsolationForest, OneClassSVM, maybe LOF;
- deep sequence: LSTM-AE or GRU-AE if time allows;
- supervised upper-bound: RandomForest / XGBoost-style tree model, clearly labeled as supervised and not directly comparable deployment setting.

---

## 8. Immediate Next Plan

### Step 1: Minimal External Baselines

Run at least:
- IsolationForest;
- OneClassSVM;
- RandomForest as supervised upper-bound.

If time permits:
- LSTM-AE / GRU-AE.

All should use the same original-frontend 100D data and same OOD/attack evaluation protocol.

Purpose:
- determine whether stronger OOD is genuinely hard for common methods;
- reduce paper risk from relying only on Kitsune/dA;
- establish whether Transformer is close to a meaningful frontier or still far behind other baselines.

### Step 2: Tail-Stability Fix Only If Needed

Do not continue broad model search.
If returning to Transformer training, target the observed failure directly:
- seed101: diagload branch high OOD alarm;
- seed303: raw Mahalanobis branch high OOD alarm;
- objective should stabilize latent covariance tails, not merely raise detection.

### Step 3: Paper Framing Update

Current framing should be:
- stronger OOD evaluation exposes a hidden deployment failure mode;
- Transformer latent covariance contains strong attack signal but unstable benign OOD tails;
- covariance-aware gating works on a discovery seed but does not yet have stable multi-seed support;
- additional baseline and tail-stability work is required before claiming A-tier-level superiority.

---

## 9. Short Paper-Useful Narrative

The project started by verifying a stronger OOD failure mode under a reliable original-frontend 100D input chain. The original Transformer did not reliably beat dA under fixed thresholds, and naive calibration reduced alarms by collapsing attack detection. Model-side attempts such as MAE, uncertainty, compactness, and covariance regularization mostly either lowered alarms at the cost of detection or failed to stabilize fixed-threshold behavior.

The key useful signal came from the latent contrastive `latent_swap_spike_mix` checkpoint. It exposed strong attack-detection potential but also high benign OOD alarm. Offline scorer analysis showed that raw Mahalanobis distance has high attack separation but is too sensitive to benign OOD tails, while diagonal loading controls alarms but suppresses attack detection. A lost-attack/false-alarm overlap analysis then revealed that attacks lost by diagonal loading are still separable from reduced OOD false alarms using raw Mahalanobis. This led to a two-threshold covariance gate that combines a low-alarm diagload branch with a high-tail raw Mahalanobis rescue branch.

The gate achieved a strong seed42 result, but formal multi-seed validation and a conditional guard variant both failed to stabilize it. The current bottleneck is seed-specific latent covariance tail instability. The next decisive work is to add external baselines for A-tier credibility and, if continuing Transformer-side improvement, to target covariance-tail stability directly rather than tuning more thresholds.

---

## 10. Update Checklist for Future Experiments

When a new experiment finishes, update these sections:
- Section 5: timeline, if it changes the logic;
- Section 6: candidate ranking;
- Section 7: A-tier readiness;
- Section 8: immediate next plan;
- add exact run path and key numbers.

Do not add every plot or minor command here. Keep this file as the paper-level memory.
