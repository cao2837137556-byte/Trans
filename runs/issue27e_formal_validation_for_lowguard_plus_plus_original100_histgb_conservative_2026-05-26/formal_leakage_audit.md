# Formal Leakage Audit

## Verdict

`candidate_config_not_recoverable_needs_debug`

No issue27e final-eval leakage occurred because the formal locked validation was not run after the candidate freeze blocker was found.

## Main risk

The main risk is not final-eval leakage inside issue27e; it is candidate-freeze ambiguity inherited from issue27d. The smoke candidate is a `selection-policy / aggregate` candidate, not yet a single frozen method instance.

## Required fix

Before formal validation, issue27f must freeze one of the following without using final OOD eval or attack eval:

| config_id | selected_count | validation_target_values | mean_ood_val_alarm | mean_support_val_detection |
|---|---|---|---|---|
| histgb_d2_lr003_l2p0_ood4_sup2_t0100 | 7 | 0.01 | 0.002357 | 0.892857 |
| histgb_d2_lr005_l2p1_ood4_sup4_t0050 | 5 | 0.005 | 0.000000 | 1.000000 |


The freeze rule may use only issue27d support-validation / OOD-validation traces, simplicity, and pre-registered low-alert constraints.
