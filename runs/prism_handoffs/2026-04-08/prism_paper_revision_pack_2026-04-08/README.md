# Prism Paper Revision Pack (2026-04-08)

Created: 2026-04-08T17:37:05

This folder is prepared for Prism to revise the paper draft without rerunning experiments.

## Contents

- `inputs/Transformer_current_draft_2026-04-08.pdf`: current paper draft copied from `D:/study/paper/anomaly_detection/paper04/Transformer.pdf`.
- `instructions/PRISM_WRITING_PROMPT.md`: copy this prompt into Prism.
- `tables/`: CSV tables for main results, cost, baselines, and operating-region sweeps.
- `figures/`: selected main and supplementary figures.
- `evidence_summaries/`: technical handoff and run summaries.

## Main Candidate

`Transformer 3-seed covariance ensemble, rawq=0.999, fixed_id_q0.995`

Key numbers:
- dA q99: alarm `0.1322`, high-purity detection `0.8014`, ID alarm `0.0100`.
- dA q995: alarm `0.1045`, high-purity detection `0.7690`, ID alarm `0.0050`.
- Transformer ensemble q995: alarm `0.1261`, high-purity detection `0.8444`, ID alarm `0.0050`.

Claim boundary:
- Use as ID-only operating-region improvement.
- Do not claim single-model unconditional q99 victory.

## Recommended First File for Prism

Read `instructions/PRISM_WRITING_PROMPT.md` first.
