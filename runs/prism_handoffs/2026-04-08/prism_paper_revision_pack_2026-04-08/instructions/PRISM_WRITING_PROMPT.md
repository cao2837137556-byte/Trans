# Prism Writing Instruction Prompt (2026-04-08)

You are revising the paper draft `inputs/Transformer_current_draft_2026-04-08.pdf` using the experimental evidence in this folder.

## Goal

Prepare the manuscript for an A-tier security-paper style narrative. Do not fabricate results. Use the exact numbers from the supplied CSV/MD evidence. The current goal is not to claim a free single-model Transformer victory, but to present a careful, defensible operating-region improvement under a stronger OOD deployment evaluation.

## Main Claim Boundary

Use this as the central claim:

> Under a stricter stronger-OOD deployment evaluation, a covariance-aware Transformer ensemble reaches a higher-detection ID-only operating region than the dA q99 reference, while generic unsupervised and recurrent deep baselines fail to control false alarms. The improvement comes at a 3-checkpoint / 3-forward-pass inference cost.

Do **not** claim:
- A single Transformer model unconditionally beats dA at the exact same q99 fixed threshold.
- OOD evaluation is fully original. Safer: stricter deployment-oriented stronger OOD protocol.
- RandomForest is a fair unsupervised deployment baseline. It is a supervised upper-bound / sanity check.
- seed42 gate discovery is the final result. It failed formal multiseed and should be supplementary/discovery evidence only.

## Required Main Result Table

Use `tables/final_candidate_main_table.csv` as the core results table.

The critical rows are:
- dA q99: alarm 0.1322, detection 0.8014, ID alarm 0.0100.
- dA q995: alarm 0.1045, detection 0.7690, ID alarm 0.0050.
- Transformer 3-seed ensemble rawq0.999/fixed_id_q0.995: alarm 0.1261, detection 0.8444, ID alarm 0.0050.
- Transformer 3-seed ensemble rawq0.9995/fixed_id_q0.995: alarm 0.1231, detection 0.8245, ID alarm 0.0050.
- Transformer 3-seed ensemble rawq0.998/fixed_id_q0.997: alarm 0.1199, detection 0.8188, ID alarm 0.0030.

Suggested interpretation:
- Compared with dA q99, the main Transformer ensemble candidate has slightly lower OOD alarm and higher attack detection.
- Compared with dA at the same q995 ID-alarm point, the Transformer ensemble has higher detection but also higher OOD alarm.
- Therefore frame it as an ID-only operating-region improvement, not an unconditional same-threshold win.

## Required Cost Table

Use `tables/final_candidate_cost_table.csv`.

You must explicitly mention:
- dA single seed: 1 checkpoint, 1x forward pass, about 147625 bytes.
- Transformer latent single seed: 1 checkpoint, 1x forward pass, about 794317 bytes, 18947 Torch parameters.
- Transformer 3-seed ensemble: 3 checkpoints, 3x forward passes, about 2382951 bytes, 56841 Torch parameters.

This cost discussion is required for deployment credibility.

## Required Figures

Recommended main figures:
- `figures/fig_main_tradeoff_final_candidate.png`
- `figures/fig_transformer_ensemble_score_distribution.png`
- `figures/fig_da_score_distribution_q99.png`

Recommended supplement figures:
- `figures/fig_idq_sweep_tradeoff.png`
- `figures/fig_ensemble_cost_tradeoff.png`
- `figures/fig_recurrent_deep_baselines.png`
- `figures/fig_external_baselines.png`
- `figures/fig_mahalanobis_rescue.png`
- `figures/fig_seed42_gate_rescue.png`

## Method Description to Add or Revise

Describe the final method as:

- Base representation: Transformer latent contrastive model with `latent_swap_spike_mix` synthetic negatives.
- Scoring: covariance-aware Mahalanobis-style latent scoring with diagonal loading and raw high-tail branch.
- Stabilization: 3-seed ensemble averages normalized covariance-gate scores.
- Threshold: ID-only fixed quantile (`fixed_id_q0.995` for the main candidate). Emphasize no OOD/attack labels are used to set this threshold.

Suggested concise notation:

`S(x) = mean_s max( diagload_s(x) / q99_ID(diagload_s), raw_s(x) / q999_ID(raw_s) )`

Main decision:

`S(x) > q995_ID(S)`

Do not overspecify implementation beyond what is in the evidence unless the source code is available.

## Baseline Section Guidance

Use the baseline evidence to show the evaluation is not trivially solved:

- External simple baselines: `tables/external_baseline_aggregate.csv`.
- Recurrent deep baselines: `tables/recurrent_deep_baseline_aggregate.csv`.

Important baseline interpretation:
- LSTM-AE / GRU-AE can get high detection but have high OOD false alarms.
- IsolationForest / OCSVM / LOF do not solve the fixed stronger OOD problem.
- RandomForest is supervised upper-bound only and should be labeled as such.

## Supplement Guidance

Put these in supplement or ablation sections:

1. Raw Mahalanobis high detection but high alarm.
2. Diagonal loading rescue.
3. seed42 gate discovery.
4. formal multiseed gate failure and conditional gate failure.
5. temporal frontend v1 failure.
6. MAE / uncertainty / compactness negative results only if space allows.

## Tone / Framing

Use precise, conservative wording:
- "higher-detection operating region"
- "ID-only threshold"
- "stronger OOD deployment evaluation"
- "covariance tail stabilization"
- "3-checkpoint ensemble cost"

Avoid:
- "dramatically outperforms"
- "unconditionally beats"
- "first OOD evaluation"
- "free deployment improvement"

## Immediate Writing Tasks

1. Read the current draft PDF.
2. Identify where the paper currently claims Transformer beats dA or discusses results.
3. Replace outdated claims with the operating-region claim above.
4. Insert/update a main results table from `tables/final_candidate_main_table.csv`.
5. Insert/update a cost table or cost paragraph from `tables/final_candidate_cost_table.csv`.
6. Add a baseline paragraph using external and recurrent baseline results.
7. Add a limitations/deployment paragraph acknowledging the 3x inference cost and q995 operating point.
8. Place seed42 gate and Mahalanobis rescue as supplementary/diagnostic evidence, not main proof.
