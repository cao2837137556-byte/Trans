# Frontend-F2 Deep Research Brief

Date: 2026-04-21  
Branch: `codex/frontend-f2`  
Purpose: handoff material for a deep diagnosis of why frontend-f2 has not surpassed the DA baseline and what frontend redesign path is still worth trying.

## 1. Current Goal

The target is not just to improve AUC. The target is to beat the DA model under the project operating condition:

- benign OOD alarm should be close to or below `1%`
- high-purity attack detection should rise substantially, ideally toward the DA-level target
- frontend representation should help the model separate attack from benign OOD tail, not merely separate ID from OOD

Current best frontend-f2 results do not satisfy this.

## 2. Core Evaluation Protocol

Use the existing frontend-f2 smoke protocol when comparing runs:

- data:
  - ID benign: IoT23 `7-6`
  - OOD benign: IoT23 `4-1`
  - attack: IoT23 `34-1`
- stage2 manifest:
  - `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage2_2026-04-01\attack_manifest_stage2.json`
- main policy:
  - `id_budget_calibrated_target1pct`
- main score rows:
  - `transformer + family_short_focus + mi_dir_mean`
  - `transformer + family_short_focus + mi_hphp_short_mean`
  - `hphp_mean feasible` as a reference, not as the main target

## 3. Best Known Anchor: v3 fix3

Run:

- `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3/`

Key results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `transformer + family_short_focus + mi_dir_mean` | 0.8105 | 0.0445 | 0.4411 | False |
| `transformer + family_short_focus + mi_hphp_short_mean` | 0.8377 | 0.0647 | 0.4603 | False |
| `transformer + family_short_focus + hphp_mean` | 0.5357 | 0.0093 | 0.1332 | True |

Interpretation:

- v3 has meaningful attack-vs-OOD ranking.
- It fails low-alarm calibration: the strong scorers have too much benign OOD alarm.
- `hphp_mean` proves a feasible low-alarm point exists, but detection is too low.

## 4. Failed / Negative Routes So Far

### 4.1 v4a hard masking

Run:

- `runs/frontend_f2_expression_v4a_tokenizer_v1_smoke_2026-04-17/`

Idea:

- keep v3
- hard-mask HH / HH_jit channels 0,1,3,4

Main results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `mi_dir_mean` | 0.7586 | 0.0433 | 0.2723 | False |
| `mi_hphp_short_mean` | 0.7758 | 0.0650 | 0.3385 | False |
| `hphp_mean` | 0.5830 | 0.0190 | 0.0923 | False |

Conclusion:

- Hard masking damaged discriminative signal.
- Treat as a strategy-level negative result.

### 4.2 v4b HH soft stabilization

Run:

- `runs/frontend_f2_expression_v4b_tokenizer_v1_smoke_2026-04-20/`

Idea:

- stabilize HH / HH_jit using relative, centered, and short-long ratio channels
- keep MI_dir / HpHp unchanged from v3

Main results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `mi_dir_mean` | 0.6649 | 0.0377 | 0.0793 | False |
| `mi_hphp_short_mean` | 0.7180 | 0.0138 | 0.1853 | False |
| `hphp_mean` | 0.4989 | 0.0089 | 0.1303 | True |

Conclusion:

- Soft stabilization reduced some alarm but lost too much ranking/detection.
- HH/HH_jit local patching is not enough.

### 4.3 source_rich_v1 audit and v5_compact_v1

Audit run:

- `runs/frontend_f2_source_rich_audit_2026-04-20/`

source_rich_v1 channels:

- raw: `logw_raw, mean_slog_raw, std_slog_raw, cv_slog_raw, cov_slog_raw, pcc_slog_raw`
- family-relative: `mean_rel_family, std_rel_family, logw_centered_family, cov_rel_family, pcc_centered_family`
- cross-scale: `mean_short_long_ratio, cv_short_long_ratio`

Audit-recommended v5 compact channels:

- `mean_slog_raw`
- `cv_slog_raw`
- `logw_centered_family`
- `mean_rel_family`
- `std_slog_raw`
- `logw_raw`
- `std_rel_family`
- `pcc_centered_family`

v5 run:

- `runs/frontend_f2_expression_v5_compact_tokenizer_v1_smoke_2026-04-20/`

Main results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `mi_dir_mean` | 0.8286 | 0.0125 | 0.1578 | False |
| `mi_hphp_short_mean` | 0.8083 | 0.0027 | 0.1691 | True |
| `hphp_mean` | 0.6793 | 0.0000 | 0.0000 | True |

Conclusion:

- v5 is healthier than v4a/v4b.
- It still does not recover v3-level detection.
- It suggests source-level audit can find stable channels, but the AE/scoring objective is still not aligned enough.

### 4.4 v6_input_aligned_v1

Run:

- `runs/frontend_f2_expression_v6_input_aligned_tokenizer_v1_smoke_2026-04-20/`

Idea:

- keep only short scales: `1s / 0.1s / 0.01s`
- output `[N,12,8]`
- replace HH/HH_jit raw absolute channels with relative variants

Main results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `mi_dir_mean` | 0.7871 | 0.0136 | 0.0413 | False |
| `mi_hphp_short_mean` | 0.6689 | 0.0047 | 0.0124 | True |
| `hphp_mean` | 0.3888 | 0.0000 | 0.0000 | True |

Conclusion:

- Aggressive token geometry change collapsed detection.
- Avoid further short-token collapse without stronger evidence.

### 4.5 F2.5 temporal causal predictor

Run:

- `runs/frontend_f2_5_temporal_smoke_2026-04-21/`

Idea:

- use expression_v3
- causal history window `K=5` predicts current frame
- current frame is not input to the encoder

Main family_short_focus results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `mi_dir_mean` | 0.4216 | 0.0095 | 0.0028 | True |
| `mi_hphp_short_mean` | 0.5900 | 0.0099 | 0.0320 | True |
| `hphp_mean` | 0.5796 | 0.0085 | 0.0707 | True |

Best point:

- `uniform + hphp_mean`: `AUC=0.6944`, `alarm=0.0098`, `det=0.1367`

Conclusion:

- Temporal prediction mainly becomes conservative.
- It does not improve the main attack separation.

### 4.6 F2.6 innovation tensor

Run:

- `runs/frontend_f2_6_innovation_smoke_2026-04-21/`

Idea:

- use expression_v3
- compute explicit current-vs-history feature:
  - `innovation = (x_t - mean(x_{t-K:t-1})) / std(x_{t-K:t-1})`
  - `K=5`, clip `[-8,8]`
- keep `[20,8]` geometry

Main family_short_focus results:

| scorer | AUC | calibrated_alarm | calibrated_det | feasible |
|---|---:|---:|---:|---|
| `mi_dir_mean` | 0.4029 | 0.0254 | 0.0167 | False |
| `mi_hphp_short_mean` | 0.4034 | 0.0459 | 0.0004 | False |
| `hphp_mean` | 0.4195 | 0.0583 | 0.0092 | False |

Best point:

- `token_mlp + uniform + mi_hphp_mean`: `AUC=0.4951`, `alarm=0.1026`, `det=0.0881`

Conclusion:

- Explicit short-history innovation is negative.
- It destroys v3's useful attack-vs-OOD ranking.

## 5. Current High-Level Diagnosis

The branch has likely exhausted simple frontend reshaping:

- old 100D rearrangement is not enough
- HH/HH_jit local patching is not enough
- source-rich compact selection helps stability but not low-alarm detection enough
- aggressive token geometry changes collapse detection
- temporal prediction and innovation do not recover the missing signal

The likely bottleneck is objective mismatch:

- AE reconstruction learns ID normality.
- The real target is not just ID-vs-non-ID.
- The target is: keep ID and benign OOD close while pushing high-purity attack away.

In other words, the frontend should be DA-aligned or target-aware, not just a better unsupervised reconstruction input.

## 6. Suggested Deep Research Questions

Ask GPT to answer these with reasoning grounded in the artifacts above:

1. Is there still a credible unsupervised frontend-expression path after the v3/v5/v6/F2.5/F2.6 failures?

2. Should the next step stop extractor formula changes and instead change the learning objective to one of:
   - supervised contrastive / one-vs-benign-OOD objective
   - domain-adversarial capture-invariant representation
   - positive-unlabeled or weak-supervised high-purity attack objective
   - calibrated ranker on top of v3/source_rich tokens

3. What is the most likely reason DA is stronger:
   - better input fields?
   - better handling of benign OOD shift?
   - supervised target alignment?
   - calibration/scoring advantage?
   - feature selection over capture-stable signals?

4. What concrete `v7` should be tried next, with the smallest experiment that can falsify it?

5. What should be stopped permanently to avoid wasting more cycles?

## 7. Recommended Next Experiment Candidates

The next experiment should be one of these, not another local channel formula patch:

### Candidate A: DA-aligned diagnostic ranker

- Input: existing `source_rich_v1` or `v5_compact_v1`
- Train a simple supervised/ranking model using:
  - ID benign as normal
  - OOD benign as normal or near-normal
  - high-purity attack as anomalous
- Goal: estimate whether the existing frontend contains enough information if the objective is aligned.
- If this fails, extractor information is probably insufficient.

### Candidate B: domain-invariant frontend AE

- Input: v3 or source_rich
- Objective:
  - reconstruct ID
  - penalize representation/domain separability between ID and benign OOD
  - preserve high-purity attack separation through auxiliary term
- More complex than Candidate A, so do only after A shows signal.

### Candidate C: DA-vs-frontend error analysis

- Need DA outputs/scores and frontend-f2 scores on the same rows.
- Compare which attack rows DA catches and frontend-f2 misses.
- Analyze whether misses correspond to specific families/scales/channels.
- Use this to decide if frontend extraction lacks a signal or just uses it poorly.

## 8. Files GPT Should Inspect

Primary handoff:

- `runs/branch_handoffs/frontend_f2/frontend_f2_handoff.md`

Key code:

- `repo/ood/kitsune_frontend_original_extract.py`
- `repo/ood/frontend_f2_expression_v3_tokenizer_v1.py`
- `repo/ood/frontend_f2_source_rich_audit.py`
- `repo/ood/frontend_f2_5_temporal_tokenizer.py`
- `repo/ood/frontend_f2_6_innovation_tokenizer_v1.py`

Key run summaries:

- `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3/summary.md`
- `runs/frontend_f2_source_rich_audit_2026-04-20/source_rich_recommendation.md`
- `runs/frontend_f2_expression_v5_compact_tokenizer_v1_smoke_2026-04-20/summary.md`
- `runs/frontend_f2_expression_v6_input_aligned_tokenizer_v1_smoke_2026-04-20/summary.md`
- `runs/frontend_f2_5_temporal_smoke_2026-04-21/summary.md`
- `runs/frontend_f2_6_innovation_smoke_2026-04-21/summary.md`

Key CSVs:

- `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3/frontend_f2_expression_v3_combined.csv`
- `runs/frontend_f2_expression_v5_compact_tokenizer_v1_smoke_2026-04-20/frontend_f2_expression_v5_compact_combined.csv`
- `runs/frontend_f2_5_temporal_smoke_2026-04-21/frontend_f2_5_temporal_combined.csv`
- `runs/frontend_f2_6_innovation_smoke_2026-04-21/frontend_f2_6_innovation_combined.csv`

## 9. Constraints For GPT's Proposal

Any proposed next step should obey:

- do not continue v4/v5/v6 local patch variants unless there is a new falsifiable reason
- do not change multiple axes at once
- keep one minimal local smoke before any supercomputer run
- output must be comparable under the existing frontend-f2 calibration protocol
- if using supervision, state exactly what labels are used and why this is acceptable for the project
- if proposing DA alignment, specify what DA artifacts are needed

## 10. Current Preferred Ask

Ask for one concrete next experiment, not a list of ten ideas.

The answer should include:

- hypothesis
- why it addresses the observed failures
- exact input artifacts
- exact labels/splits
- model/objective
- expected success/failure signal
- stopping rule
- minimal implementation plan
