# Issue27e Formal LOW-GUARD++ Validation Summary

## Verdict

- primary_verdict: `candidate_config_not_recoverable_needs_debug`
- formal_locked_validation_executed: `false`
- recommended_next_action: `issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative`

## 1. Candidate config recovery

The issue27d candidate config was not uniquely recoverable. The original100 HistGB-Conservative smoke selected `2` configs across locked bins `5/6/7/8` and seeds `42/43/44`.

| config_id | selected_count | selected_holdouts | selected_seeds | validation_target_values | mean_ood_val_alarm | max_ood_val_alarm | mean_support_val_detection | mean_support_val_margin |
|---|---|---|---|---|---|---|---|---|
| histgb_d2_lr003_l2p0_ood4_sup2_t0100 | 7 | holdout_bin_5;holdout_bin_6;holdout_bin_7;holdout_bin_8 | 42;43;44 | 0.01 | 0.002357 | 0.006500 | 0.892857 | 0.998459 |
| histgb_d2_lr005_l2p1_ood4_sup4_t0050 | 5 | holdout_bin_5;holdout_bin_6;holdout_bin_7;holdout_bin_8 | 43;44 | 0.005 | 0.000000 | 0.000000 | 1.000000 | 0.995148 |


## 2. Full locked seed validation

Not executed. The Stage A rule requires stopping when a unique frozen candidate config cannot be recovered.

## 3. LOW-GUARD++ formal locked mean / min / OOD max

`NA / NA / NA` because formal validation was blocked before final-eval reporting.

## 4. Comparison with LOW-GUARD-LR

Not formally evaluated in issue27e. issue27d smoke remains the only source of the original100 HistGB candidate result, while LOW-GUARD-LR remains the demonstrated stable reference.

## 5. OOD <= 1%

Not formally evaluated in issue27e. issue27d smoke candidate had OOD max `0.005100`, but this cannot be upgraded to a formal result.

## 6. Single seed / bin collapse

Not evaluated in full seeds because the run stopped at candidate-freeze audit.

## 7. Leakage / artifact risk

No issue27e final-eval leakage occurred. The main artifact risk is candidate-freeze ambiguity. Representation leakage remains `unknown` until a full original100 provenance audit is included in issue27f.

## 8. Threshold target robustness

Not executed. Running target robustness before freezing the candidate could blur the config/target boundary.

## 9. Reproducibility of original100 + HistGB advantage

Promising but not formally validated.

## 10. Upgrade to LOW-GUARD++

No. The candidate must first be frozen and validated.

## 11. Paper mainline

Do not change the paper mainline yet. The correct current story is: LOW-GUARD-LR remains the demonstrated minimal instance; original100 + HistGB-Conservative is a serious performance-instance candidate requiring issue27f.

## 12. Slurm

Not needed for this audit. A future full locked-seed HistGB validation is likely local-feasible.
