# issue27q Plan Summary

1. issue27q_plan completed: `true`.
2. primary_verdict: `issue27q_execution_plan_ready`.
3. DeepSADStyle_Lite largest risk: near seed-invariant high performance under a lite weighted-center implementation, which could be real signal or implementation/feature/row-order artifact.
4. DeepSADStyle_Lite minimal audit: score-direction replay, threshold replay, final-eval exclusion assertions, label permutation, support removal/shuffle, and feature/row-order artifact audit.
5. LOW-GUARD++ likely failure causes: seed-specific support coverage gap, anonymous-clean115 mismatch with old HistGB config, threshold/score-margin mismatch, OOD guard weight mismatch, and possible few-column dominance.
6. LOW-GUARD++ minimal diagnosis: seed-44 attack failure and seed-42 OOD violation score distributions, support coverage, feature importance, and validation-only threshold curves.
7. LOW-GUARD protocol universality proven: `false`.
8. Paired universality matrix: raw/support-only/OOD-train-only/threshold-only/full-guarded per head for LR, HistGB, DeepSAD-style, DevNet-style, and one traditional anomaly detector.
9. Baseline collapse experiments: use DevNet-style, DeepSAD-style, HistGB, LR, and one traditional detector; KitNET AE optional only if cheap and reliable.
10. Formal issue27q order: P0 sanity controls, P1 DeepSAD seed expansion/stratification, P2 LOW-GUARD++ failure diagnosis, P3 paired protocol matrix, P4 expensive baselines/external prep.
11. Slurm: recommended for seed expansion and paired matrix; P0 sanity can run locally.
12. Commit hash: pending.
