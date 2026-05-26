# Issue27c LOW-GUARD Mechanism Falsification And Head Specificity Audit Summary

## Total-control critique

- issue27b 后直接转 deployment robustness 是过早收口。
- 只做 DevNet near-miss rescue 也太窄。
- 当前最重要问题是：LOW-GUARD 是 general protocol，还是 LR-specific method。
- 如果只有 LR 被救回，必须诚实收缩 claim。
- 不能因为 LR 当前最好就直接假设协议具有广泛迁移性。
- 不能因为非 LR 没赢就直接放弃审计实现和设置问题。

## Verdict

- primary_verdict: `lowguard_lr_success_mechanistically_supported`
- secondary_verdicts: `representation_linearization_explains_lr_advantage`, `lowguard_effect_head_specific_lr_only_so_far`, `non_lr_results_inconclusive_due_to_proxy_implementation`

## 1. Why does LOW-GUARD clearly rescue LR?

LR has the cleanest P0/P1/P2/P3 mechanism pattern: raw LR detects attacks but badly violates OOD alarm; threshold-only LR controls OOD by collapsing detection; OOD-guarded training preserves attack detection while suppressing OOD tail; P3 adds the validation safety gate.

## 2. Mechanism evidence or accident?

The LR result is unlikely to be pure accident because the mechanism pattern repeats across locked bins and seeds, and LOW-GUARD-LR P3 remains `0.949705` / `0.882629` / `0.004500`. However, broad protocol transfer remains unproven.

## 3. Non-LR failure: real model failure or proxy/implementation issue?

Both are plausible. DevNet-like is a lightweight proxy, DeepSAD-like is a center-distance proxy, and HistGB does not optimize a low-alert tail objective. Therefore non-LR failures should not be written as general defeats of DevNet, Deep SAD, or nonlinear adapters.

## 4. Does top64 bias toward LR?

Possibly. top64 selection uses support-vs-OOD/ID effect and tail-margin criteria that can expose a linear attack-separating direction. This supports LOW-GUARD-LR but makes head-agnostic claims risky without original100/top64 representation controls.

## 5. Training guard vs threshold guard for LR

Training guard is the decisive recovery mechanism. Threshold guard is the safety gate. Threshold-only LR is not sufficient because it collapses attack detection.

## 6. Did non-LR heads actually consume OOD guard?

Yes. P2/P3 variants used OOD_train guard. The issue is score-tail behavior, proxy objectives, and low-alert calibration, not absence of OOD guard.

## 7. Implementation bug or protocol inequivalence risk?

No direct bug or final-eval leakage was found. But protocol-equivalence risk remains because DevNet-like and DeepSAD-like are proxies rather than full methods.

## 8. Can LOW-GUARD still be written as framework?

Only cautiously. It can be framed as a guarded adaptation protocol, but positive empirical claims should center on LOW-GUARD-LR unless issue27d finds broader transfer.

## 9. Should claims shrink to LOW-GUARD-LR?

Yes for performance claims. The framework language may remain as motivation/protocol, but the demonstrated instance is LOW-GUARD-LR.

## 10. Issue27d next step

`issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity`.

## 11. Slurm

Not needed for this audit or the recommended bounded issue27d controls.

## 12. Final eval leakage

No final eval leakage was found. Final OOD and attack eval were used only for report-only metrics.

## Key head-specific rows

| head_id | p3_detection | p3_detection_min | p3_ood_max | p3_feasible_rate | response_label |
|---|---|---|---|---|---|
| DeepSAD_like_center | 0.037650 | 0.002805 | 0.013400 | 0.250000 | nonresponsive_or_collapsed |
| DevNet_like_MLP | 0.947497 | 0.895305 | 0.010100 | 0.975000 | detection_high_ood_tail_uncontrolled |
| HistGB_shallow | 0.755626 | 0.230047 | 0.013900 | 0.675000 | partial_response |
| LOW_GUARD_LR_reference | 0.949705 | 0.882629 | 0.004500 | 1.000000 | full_lowguard_success |
| Prototype_metric_LR | 0.219025 | 0.042254 | 0.010900 | 0.750000 | training_guard_response_not_low_alert_feasible |
| RFF_Logistic | 0.162554 | 0.103756 | 0.012600 | 0.700000 | training_guard_response_not_low_alert_feasible |


## Threshold curve snapshot

| head_id | head_family | ood_val_target | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | id_calib_alarm_mean | ood_val_alarm_mean | threshold_source | selection_used_final_eval | threshold_uses_final_eval |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LOW_GUARD_LR_reference | lr | 0.010000 | 0.949705 | 0.882629 | 0.004500 | 1.000000 | 0.010000 | 0.000750 | id_calib_plus_ood_val_guarded | False | False |
| DevNet_like_MLP | devnet_like_mlp | 0.010000 | 0.947497 | 0.895305 | 0.010100 | 0.975000 | 0.009935 | 0.002188 | id_calib_plus_ood_val_guarded | False | False |
| HistGB_shallow | histgb | 0.010000 | 0.755626 | 0.230047 | 0.013900 | 0.675000 | 0.006565 | 0.007437 | id_calib_plus_ood_val_guarded | False | False |
| DeepSAD_like_center | deepsad_like_center | 0.010000 | 0.037650 | 0.002805 | 0.013400 | 0.250000 | 0.002240 | 0.009962 | id_calib_plus_ood_val_guarded | False | False |
| LOW_GUARD_LR_reference | lr | 0.005000 | 0.949119 | 0.880282 | 0.003700 | 1.000000 | 0.004900 | 0.000625 | id_calib_plus_ood_val_guarded | False | False |
| DevNet_like_MLP | devnet_like_mlp | 0.005000 | 0.943188 | 0.887324 | 0.007400 | 0.500000 | 0.004950 | 0.001162 | id_calib_plus_ood_val_guarded | False | False |
| HistGB_shallow | histgb | 0.005000 | 0.750575 | 0.224413 | 0.008200 | 0.925000 | 0.002465 | 0.002213 | id_calib_plus_ood_val_guarded | False | False |
| DeepSAD_like_center | deepsad_like_center | 0.005000 | 0.016822 | 0.001052 | 0.007700 | 0.500000 | 0.000875 | 0.004562 | id_calib_plus_ood_val_guarded | False | False |
