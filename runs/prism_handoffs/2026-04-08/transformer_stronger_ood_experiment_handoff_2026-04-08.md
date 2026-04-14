# Transformer Stronger-OOD Experiment Handoff

Generated: 2026-04-08
Workspace: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`
Role: experiment engineering execution only. Do not edit paper prose.

## 1. Project Goal

This project is the experiment track for anomaly detection on the current stronger-OOD mainline.
The target is to make a Transformer-family detector outperform the dA baseline under the formal evaluation protocol.

The user specifically wants the next conversation to continue searching for a Transformer win. Do not propose "accept dA is stronger" as an action item. Still report factual comparisons honestly.

## 2. Fixed Mainline / Data Protocol

Use the same current formal mainline unless explicitly changed:

- Feature frontend: `original-frontend 100D`
- ID benign: formal frontend100 ID benign split
- OOD benign: formal stronger-OOD benign split
- Attack evaluation: Stage2 high-purity attack is the primary attack metric; boundary/mixed can be retained as secondary.
- Evaluation policies:
  - `fixed_id_q99` / formal fixed threshold
  - `naive_calibrated_budget5000_target1pct`
  - `det_floor_50pct_min_alarm`
- Required metrics:
  - OOD benign alarm ratio
  - high-purity attack detection
  - boundary/mixed attack detection when available
  - mean +/- std only when running multi-seed

Important rule: all calibration / z-score / robust-scaling statistics must come only from ID benign training/calibration data. Never use OOD benign or attack to fit scalers, centers, thresholds, covariance, etc.

## 3. Execution Rules

- Worktree is fixed: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`
- Put new experiment outputs under `runs/<run_tag>/` on D:.
- Do not modify paper text.
- Each experiment round must produce:
  - `summary.md`
  - `config.json`
  - `command.txt`
  - key CSV result file(s)
  - at least one plot
  - update `runs/master_experiment_map_v1.md`
- Prefer local dry-run/smoke test before full run.
- If a run is expected to be long, local code + smoke first, then HPC is acceptable. In recent rounds the user chose local foreground execution.

## 4. Current Code Areas

Main files modified by the experiment track:

- `repo/Trans.py`
  - Transformer detector implementation.
  - Contains MAE, TailReg, uncertainty, latent contrastive, compactness, covreg_v1, covreg_v2 paths.
- `repo/KitNET.py`
  - Detector backend dispatch and checkpoint serialization.
- `repo/ood/stage1_probe.py`
  - Training/scoring entrypoint with CLI args.
- `repo/ood/frontend100_*_experiment.py`
  - Experiment drivers.

Current important new script:

- `repo/ood/frontend100_covariance_regularized_v2_experiment.py`

## 5. What Has Been Learned

### Threshold / calibration track

Naive calibration repeatedly collapses attack detection to near zero. Detection-constrained threshold rules are necessary but do not fully fix Transformer representation quality.

Key lesson:
- The problem is not just threshold selection.
- A healthy operating region must jointly control OOD benign alarm and attack detection.

### MAE / MAE+TailReg / uncertainty tracks

These lines generally lower OOD alarm but damage attack detection.

Examples:
- `frontend100_mae_tailreg_v1_2026-04-03`
  - MAE+TailReg mask=0.4 fixed: alarm about 0.0709, detection about 0.3208.
  - dA fixed in same comparison: detection about 0.7896.
- `frontend100_mae_latent_v1_2026-04-06`
  - best fusion mask=0.4 fixed: alarm=0.1201, detection=0.5174.
  - dA fixed: alarm=0.1209, detection=0.7896.

Decision:
- Do not continue plain MAE, MAE+TailReg, uncertainty, or MAE+latent fusion as the main path unless a new targeted mechanism is defined.
- These approaches tend to suppress scores globally rather than improve attack separation.

### Latent contrastive track

This is the only line that clearly raised attack detection.

Important checkpoint/recipe:
- `latent_swap_spike_mix_no_compact`
- Negative recipe: `latent_swap_spike_mix` (cross-window swap + mild spike/scale mix)
- It can produce high detection but often with high OOD alarm.

Key rescoring/postprocessing results:

- `frontend100_negative_recipe_rescoring_2026-04-05`
  - `latent_swap_spike_mix` under RMSE fixed: alarm about 0.4610, detection about 0.8582.
  - Switching to `hybrid_cosine` fixed improved to alarm about 0.3261, detection about 0.8955.
  - This proved a scoring mismatch existed.

- `frontend100_score_postprocessing_2026-04-05`
  - Best single-seed postprocessing score: `log_weighted_z_rmse0.5_cos1.0`
  - fixed: alarm=0.1857, detection=0.8233.
  - It improved over default hybrid on the discovery seed, but was not stable enough under multi-seed.

- `frontend100_locked_candidate_multiseed_2026-04-06`
  - Locked candidate: `latent_swap_spike_mix + log_weighted_z_rmse0.5_cos1.0`
  - fixed new score: alarm=0.2161 +/- 0.0549, detection=0.6353 +/- 0.1175.
  - fixed old score: alarm=0.2220 +/- 0.0701, detection=0.6558 +/- 0.0909.
  - Conclusion: the log-weighted score was not a stable multi-seed win over the old scorer.

Decision:
- Keep latent contrastive as the main promising Transformer family.
- But pure score postprocessing did not fully solve the stability problem.

### Latent scorer benchmark

Run: `frontend100_latent_scorer_benchmark_2026-04-06`

Key result:
- Direction/prototype scorer failed:
  - `score_dir_cosine` fixed: alarm=0.2734, detection=0.0963.
- Mahalanobis scorer had strong ranking signal but bad fixed alarm:
  - `mahalanobis_ledoitwolf` fixed: alarm=0.5843, detection=0.9476.
  - AUC about 0.8991.
  - det50 was healthy: alarm=0.0516, detection=0.5015.

Decision:
- Do not prioritize double-center / prototype direction next.
- Covariance-aware geometry is the more promising signal.

## 6. Covariance-Regularized Track

### covreg_v1

Run: `frontend100_covariance_regularized_v1_2026-04-07`

Mechanism:
- latent contrastive with `latent_swap_spike_mix`
- two-sided variance hinge on benign latent
- off-diagonal decorrelation

Best old-best fixed row:
- `covreg_vm0p2_vx2p0_lv0p5_lc0p05`
- fixed old-best scorer: alarm=0.3550, detection=0.8874.

Comparison:
- no_compact old-best: alarm=0.1857, detection=0.8233.
- dA fixed: alarm=0.1209, detection=0.7896.

Diagnostics:
- no NaN/Inf.
- collapse dims remained around 9-13.

Decision:
- covreg_v1 raised detection but alarm was too high.
- It did not form a healthy fixed trade-off by itself.

### Mahalanobis epsilon-floor rescue

Run: `frontend100_mahalanobis_rescue_2026-04-07`

Purpose:
- No retraining. Offline rescoring only.
- Test whether fixed Mahalanobis alarm explosion came from small-variance / ill-conditioned covariance directions.

Key result:
- covreg_v1 original Mahalanobis fixed: alarm=0.6649, detection=0.9536.
- covreg_v1 + full covariance diagonal loading f0.2: alarm=0.2246, detection=0.8919.
- simple per-dim diagonal floor failed: alarm low but detection collapsed.

Decision:
- Full covariance diagonal loading is useful.
- Simple diagonal variance floor is not enough.
- This motivated covreg_v2.

### covreg_v2

Run: `frontend100_covariance_regularized_v2_2026-04-07`

Mechanism:
- EMA benign mean/covariance buffer.
- Full covariance diagonal loading in training-time score proxy.
- Cholesky solve only. No `torch.inverse`.
- Jitter fallback for Cholesky.
- Tail-aligned benign score loss.
- Synthetic negative push-out.
- Weak anti-collapse floor.

Stability:
- Cholesky failures=0.
- NaN/Inf events=0.

Best v2 fixed row:
- `covregv2_as0p1_lt0p5` + `ledoitwolf_diagload_f0p1`
- alarm=0.5003, detection=0.8569.

Comparison:
- covreg_v1 + diagload_f0p2 rescue: alarm=0.2246, detection=0.8919.
- no_compact old-best: alarm=0.1857, detection=0.8233.
- dA fixed: alarm=0.1209, detection=0.7896.

Diagnostics:
- collapse_dims=48-64, worse than v1's 9-13.

Decision:
- v2 as implemented is not a multi-seed candidate.
- Numerical linear algebra is stable; the failure is not Cholesky instability.
- Main bottleneck: latent main loss and covariance score proxy are not aligned.
- Secondary risk: `tau_ref` / negative push-out is too strong and distorts latent geometry.
- Weak floor does not prevent collapse.

## 7. Current Best Facts To Preserve

Do not lose these anchors:

- dA fixed reference: alarm about 0.1209, detection about 0.7896.
- no_compact old-best (`latent_swap_spike_mix + log_weighted_z_rmse0.5_cos1.0_old`) fixed: alarm=0.1857, detection=0.8233.
- covreg_v1 + diagload_f0p2 offline rescue fixed: alarm=0.2246, detection=0.8919.
- covreg_v2 best fixed: alarm=0.5003, detection=0.8569; not good enough.
- naive calibration remains a detection-collapse failure mode across many detectors.

## 8. Recommended Next Direction

Do not continue covreg_v2 exactly as-is.

Most plausible next engineering directions:

1. Rework covariance training alignment:
   - Reduce or redesign negative push-out.
   - Make `tau_ref` less unstable and less aggressive.
   - Add a stronger but safer anti-collapse mechanism before covariance score loss activates.
   - Consider staged training: latent main loss first, then covariance proxy after the latent geometry is stable.

2. Use offline rescue as a benchmark target:
   - The target behavior is closer to `covreg_v1 + diagload_f0p2` (alarm=0.2246, det=0.8919), but with lower alarm.
   - Any training version must not degrade into v2's collapse_dims=48-64.

3. Avoid returning to low-yield lines unless there is a new mechanism:
   - Plain MAE
   - MAE+TailReg
   - uncertainty-only
   - double-center / prototype direction
   - compactness-only variants

4. If doing a new experiment, define a narrow single-seed mechanism test first, with explicit pass/fail criteria against:
   - no_compact old-best
   - covreg_v1 + diagload_f0p2 rescue
   - dA fixed reference

## 9. Important Run Directories

- `runs/frontend100_score_postprocessing_2026-04-05/`
- `runs/frontend100_locked_candidate_multiseed_2026-04-06/`
- `runs/frontend100_latent_scorer_benchmark_2026-04-06/`
- `runs/frontend100_covariance_regularized_v1_2026-04-07/`
- `runs/frontend100_mahalanobis_rescue_2026-04-07/`
- `runs/frontend100_covariance_regularized_v2_2026-04-07/`

Latest summary to read first:
- `runs/frontend100_covariance_regularized_v2_2026-04-07/summary.md`

Then read:
- `runs/frontend100_mahalanobis_rescue_2026-04-07/summary.md`
- `runs/frontend100_latent_scorer_benchmark_2026-04-06/summary.md`
- `runs/frontend100_locked_candidate_multiseed_2026-04-06/summary.md`

## 10. How To Answer The User

The user wants pragmatic experiment execution and cares about making Transformer win over dA.

Communication preferences:
- Be factual and concise.
- Do not over-celebrate weak single-seed points.
- Do not suggest stopping with dA as final answer.
- It is okay to say a Transformer experiment failed, but frame next steps around improving Transformer.
- Always separate:
  - implementation/scoring issue
  - model representation issue
  - threshold/calibration issue

## 11. Current State In One Paragraph

The project is trying to make a Transformer-family anomaly detector beat dA on original-frontend 100D stronger-OOD evaluation. Threshold-only fixes proved necessary but insufficient. MAE/uncertainty/compactness-style routes mostly reduce alarm while hurting detection. The most promising family is latent contrastive with `latent_swap_spike_mix`, which raises attack detection but creates OOD benign alarm. Scorer diagnostics showed covariance-aware Mahalanobis geometry has strong ranking signal, and full covariance diagonal loading can rescue fixed alarm offline. covreg_v1 had high detection but too much alarm; covreg_v2 made Cholesky/EMA covariance training stable but did not improve trade-off and caused more latent collapse. Next work should target better alignment between latent main loss and covariance-aware scorer, with stronger anti-collapse and less aggressive negative/tail objectives.
