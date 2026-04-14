# A-tier Paper Readiness Handoff (2026-04-08)

This document freezes the current experimental storyline for paper preparation. It is not paper prose. It is a technical handoff for choosing claims, figures, tables, and supplement material.

## 1. Fixed Experimental Setting

- Data line: `original-frontend 100D`.
- Evaluation: stronger OOD benign false-alarm evaluation + stage2 high-purity attack detection.
- Threshold families used throughout:
  - `fixed_id_q99`: threshold from ID benign calibration only.
  - `fixed_id_q995` and stricter ID quantiles: also ID-only operating points, no OOD/attack leakage.
  - `naive calibrated`: OOD-budget target 1%, known to collapse detection.
  - `det50`: detection-constrained operating point used for trade-off analysis, not the main deployment fixed point.
- Main deployment target: reduce OOD benign alarm while retaining high-purity attack detection.

## 2. Current Main Candidate

Current strongest candidate:

`Transformer 3-seed covariance ensemble, raw Mahalanobis q=0.999, fixed_id_q0.995`

Source run:
- `runs/frontend100_final_candidate_audit_2026-04-08/`

Key numbers:

| Method | OOD alarm | high-purity detection | ID alarm | Notes |
|---|---:|---:|---:|---|
| dA q99 | 0.1322 | 0.8014 | 0.0100 | formal dA reference |
| dA q995 | 0.1045 | 0.7690 | 0.0050 | same ID-alarm reference |
| Transformer 3-seed ensemble q995 | 0.1261 | 0.8444 | 0.0050 | current main candidate |
| Transformer 3-seed ensemble rawq0.9995/q995 | 0.1231 | 0.8245 | 0.0050 | lower-alarm candidate |
| Transformer 3-seed ensemble rawq0.998/q997 | 0.1199 | 0.8188 | 0.0030 | conservative ID-q997 candidate |

Claim boundary:
- Safe claim: covariance-aware Transformer ensemble reaches a higher-detection ID-only operating region under stronger OOD evaluation.
- Do not claim: single Transformer q99 unconditionally beats dA.
- Do not claim: the method is cheaper than dA. It uses 3 Transformer checkpoints in the main candidate.

## 3. Cost / Complexity

Source:
- `runs/frontend100_final_candidate_audit_2026-04-08/final_candidate_cost_table.csv`

| Object | Checkpoints | Relative forward passes | Checkpoint bytes | Torch params | Notes |
|---|---:|---:|---:|---:|---|
| dA single seed | 1 | 1x | 147625 | N/A | numpy AE params |
| Transformer latent single seed | 1 | 1x | 794317 | 18947 | latent contrastive |
| Transformer latent 3-seed ensemble | 3 | 3x | 2382951 | 56841 | current main candidate |

Paper handling:
- Put this in a cost/complexity paragraph or appendix table.
- Frame ensemble as stability-oriented covariance tail aggregation.

## 4. Why This Became the Main Candidate

Important chain of evidence:

1. Original Transformer under fixed q99 had weaker detection than dA and higher OOD alarm.
2. MAE / uncertainty / compactness mostly reduced alarm but damaged detection.
3. Latent contrastive with `latent_swap_spike_mix` was the first line to raise detection substantially.
4. Offline scorer benchmark showed Mahalanobis had high ranking signal but raw Mahalanobis created high OOD alarm.
5. Diagonal loading improved fixed behavior but single scorer could not meet both alarm and detection targets.
6. Two-branch covariance gate achieved a strong seed42 point but failed formal multiseed due to seed-specific latent tails.
7. Seed ensemble and stricter ID-only operating point stabilized the candidate.
8. External and recurrent baselines did not solve the stronger OOD fixed-alarm problem.

## 5. Pretty Results That Can Go Into Supplement

Use these as diagnostic/supplementary evidence, not as main final claims unless carefully qualified.

### 5.1 Mahalanobis high-detection signal

Raw Mahalanobis showed very high detection but high alarm:

- no-compact + raw Mahalanobis: alarm about 0.5842, detection about 0.9476.
- covreg_v1 + raw Mahalanobis: alarm about 0.6649, detection about 0.9536.

Interpretation:
- Latent representation contains strong attack signal.
- Raw covariance scoring is too tail-sensitive for deployment.

Best use:
- Supplementary figure/table explaining why covariance-aware scoring was explored.

### 5.2 Diagonal loading rescue

Source:
- `runs/frontend100_mahalanobis_rescue_2026-04-07/`

Key covreg_v1 rescue:
- covreg_v1 best + LedoitWolf diagload f0.2: alarm about 0.2246, detection about 0.8919.

Interpretation:
- Full covariance diagonal loading significantly reduced alarm while retaining high detection.
- Simple per-dim diagonal floor was too conservative.

Best use:
- Supplementary diagnostic for scorer stabilization.

### 5.3 Seed42 covariance gate discovery

Source:
- `runs/frontend100_diagload_gate_rescue_2026-04-08/`

Key single-seed point:
- `diag_f0p5_q99_OR_raw_q0p9995`: alarm 0.1203, detection 0.8373.
- `diag_f0p5_q99_OR_raw_q0p999`: alarm 0.1273, detection 0.8751.

Interpretation:
- The gate idea is valid at the single-seed level.
- It cannot be main claim alone because formal multiseed gate was unstable.

Best use:
- Ablation/discovery story, not final result.

### 5.4 Conditional gate failure

Source:
- `runs/frontend100_conditional_gate_multiseed_2026-04-08/`

Key result:
- Conditional guard improved alarm somewhat but remained far above dA.

Best use:
- Supplementary negative result showing decision-layer tweaks were insufficient.

### 5.5 Temporal frontend v1 failure

Source:
- `runs/frontend100_temporal_frontend_v1_2026-04-08/`

Key result:
- Naive temporal stacking gave very high detection but OOD alarm near 1.0.

Best use:
- Supplementary: simply exposing temporal context through reconstruction is not enough.

### 5.6 Recurrent AE baselines

Source:
- `runs/frontend100_recurrent_deep_baselines_2026-04-08/`

Key results:
- GRU-AE L4 last: alarm 0.6341, detection 0.7451.
- LSTM-AE L4 last: alarm 0.6730, detection 0.8311.

Best use:
- Baseline table: generic deep sequence AE baselines fail to control stronger OOD false alarms.

### 5.7 External baselines

Source:
- `runs/frontend100_external_baselines_2026-04-08/`

Key results:
- IsolationForest: alarm 0.4069, detection 0.5750.
- OneClassSVM: alarm 0.8979, detection 0.9706.
- LOF: alarm 0.9741, detection 0.8759.
- RandomForest upper-bound: alarm 0.9996, detection 1.0, but supervised and not deployment-fair.

Best use:
- Main or supplementary baseline table, with RandomForest explicitly labeled supervised upper bound / sanity check.

## 6. Results to Avoid Overclaiming

Avoid using these as headline claims:

- Single seed42 gate as final proof. It failed formal multiseed.
- covreg_v2 as success. It was numerically stable but fixed alarm remained high and collapse worsened.
- MAE fusion as success. It reduced alarm but damaged detection.
- naive temporal stacking as success. It gave near-total OOD alarms.
- RandomForest as a fair baseline. It used attack labels and should be upper-bound only.
- ?OOD evaluation is fully original.? Safer phrasing: stricter deployment-oriented stronger OOD protocol.

## 7. Recommended Main Figures and Tables

Main paper candidates:

1. Main trade-off figure:
   - Use `runs/frontend100_final_candidate_audit_2026-04-08/final_candidate_audit_plots/final_candidate_main_tradeoff.png`.
   - Show dA q99/q995 and Transformer ensemble candidate variants.

2. Main table:
   - Use `runs/frontend100_final_candidate_audit_2026-04-08/final_candidate_main_table.csv`.
   - Include dA q99/q995, Transformer ensemble q995, recurrent AEs, and external baselines.

3. Score distribution figure:
   - Use `transformer_ensemble_score_distribution.png` and `da_score_distribution_q99.png`.
   - Supports why threshold/operating point matters.

4. Cost table:
   - Use `final_candidate_cost_table.csv`.
   - Necessary for A-tier deployment discussion.

Supplement candidates:

- Mahalanobis rescue figures.
- Gate single-seed vs multiseed comparison.
- Conditional gate failure.
- Temporal frontend failure.
- Recurrent AE aggregate table.

## 8. Paper Storyline Draft (Technical, Not Prose)

Recommended narrative:

1. Stronger OOD evaluation exposes that attack-only reconstruction metrics can be misleading.
2. dA is strong under the original 100D handcrafted frontend because the frontend is architecture-aligned with small autoencoders.
3. Naive Transformer reconstruction and generic deep sequence AEs do not control benign OOD alarms.
4. Latent contrastive training reveals strong attack separation, but single-seed covariance tails are unstable.
5. Covariance-aware scoring with diagonal loading reveals high ranking signal but needs tail stabilization.
6. A multi-seed covariance-aware Transformer ensemble stabilizes latent tail geometry and reaches a higher-detection ID-only operating region than dA q99, with explicit 3x inference cost.
7. The method is not sold as a free single-model replacement; it is a stability/operating-region improvement under stricter OOD deployment evaluation.

## 9. Immediate Next Writing/Validation Tasks

Before paper drafting:

1. Decide whether main candidate is:
   - `rawq0.999/idq0.995` (higher detection, alarm 0.1261), or
   - `rawq0.9995/idq0.995` (lower alarm 0.1231, detection 0.8245), or
   - `rawq0.998/idq0.997` (alarm 0.1199, detection 0.8188).

2. If time allows, run one final consistency check:
   - Verify no OOD/attack statistics are used in ensemble thresholds.
   - Verify the `q0.995` threshold is described as ID-only, not calibrated on OOD.

3. Write cost discussion before claims.

4. Use ?operating region? language consistently.

## 10. Current Bottom Line

The project now has an A-tier-credible experimental angle, but the claim must be narrow:

> Under a stricter stronger-OOD deployment evaluation, a covariance-aware Transformer ensemble reaches a higher-detection ID-only operating region than the dA q99 reference, while generic unsupervised and recurrent deep baselines fail to control false alarms. The improvement comes at a 3-checkpoint / 3-forward-pass inference cost.

Do not write this as a single Transformer model unconditionally beating dA at the exact same q99 point.
