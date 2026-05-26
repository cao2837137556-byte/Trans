# Issue27b Guarded Protocol Transfer And Adapter Recovery Summary

## Verdict

- primary_verdict: `nonlinear_detection_gain_not_low_alert_feasible`
- next_action: `issue27c_deployment_robustness_simulation_for_lowguard_lr`

## 1. Does LOW-GUARD transfer to non-LR heads?

Transfer evidence is `not strongly supported`. The matrix evaluated LR, DevNet-like MLP, HistGB, DeepSAD-like center, Prototype/metric LR, and optional RFF Logistic under P0/P1/P2/P3 protocol variants on locked bins 5/6/7/8.

## 2. Did it rescue collapsed models?

`No clean non-LR collapse rescue was found.` Collapse rescue is defined as raw P0 locked detection below 0.20 and full P3 detection at or above 0.80 while meeting the 1% OOD budget.

## 3. Did it convert near-LR but OOD-over-budget models to feasible?

`No robust conversion was found for a near-LR non-LR model.`

## 4. LOW-GUARD++ candidate

`No adapter met the LOW-GUARD++ dominance rule.` A candidate must beat LOW-GUARD-LR locked mean, match or exceed locked min, keep locked OOD max <= 1%, and keep feasibility rate near the LR reference.

## 5. Reference LOW-GUARD-LR reproduction

- issue27b LOW-GUARD-LR P3 locked mean/min/OOD max: `0.949705` / `0.882629` / `0.004500`.
- issue25c reference locked mean/min/OOD max: `0.949705` / `0.882629` / `0.004500`.
- delta: `0.000000e+00` / `0.000000e+00` / `0.000000e+00`.

## 6. Best non-LR full LOW-GUARD head

- head: `DevNet_like_MLP`
- locked mean/min/OOD max: `0.947497` / `0.895305` / `0.010100`.
- feasible_rate: `0.975000`.

## 7. Does LOW-GUARD-LR remain the strongest feasible minimal instance?

`Yes.` Under this issue's locked matrix, no final eval was used for model, config, or threshold selection.

## 8. Training guard vs threshold guard

For LOW-GUARD-LR, the training-side OOD guard is the decisive recovery mechanism: raw LR has high detection but severe OOD over-budget, while threshold-only raw LR becomes feasible only by collapsing attack detection. The threshold guard is still necessary as the deployment safety gate because it enforces the ID+OOD validation alarm budget. For nonlinear heads, training guard often preserves attack separation, but it did not consistently pull final OOD alarm below 1%.

## 9. Issue27c need

`No immediate LOW-GUARD++ formal validation is justified; deployment robustness simulation should be next.`

## 10. Slurm

Not needed. This was a local lightweight adapter/head matrix; no dA, Transformer, large model, temporal validation, or cross-dataset execution was run.

## 11. Leakage audit

No final OOD eval or attack eval was used for threshold, hyperparameter, feature, support, or model selection in this run. Final OOD and attack eval are report-only.

## 12. Deployment robustness

Yes, deployment robustness simulation remains necessary. issue27b tests adapter transfer, not support-noise, OOD contamination, label delay, or online update safety.

## Top Full LOW-GUARD Rows

| head_id | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | promising_for_lowguard_plus_plus | recovery_mode |
|---|---|---|---|---|---|---|
| LOW_GUARD_LR_reference | 0.949705 | 0.882629 | 0.004500 | 1.000000 | False | training_guard_recovers_detection |
| DevNet_like_MLP | 0.947497 | 0.895305 | 0.010100 | 0.975000 | False | no_recovery |
| Prototype_metric_LR | 0.219025 | 0.042254 | 0.010900 | 0.750000 | False | detection_gain_not_feasible |
| RFF_Logistic | 0.162554 | 0.103756 | 0.012600 | 0.700000 | False | detection_gain_not_feasible |
| HistGB_shallow | 0.755626 | 0.230047 | 0.013900 | 0.675000 | False | no_recovery |
| DeepSAD_like_center | 0.037650 | 0.002805 | 0.013400 | 0.250000 | False | no_recovery |
