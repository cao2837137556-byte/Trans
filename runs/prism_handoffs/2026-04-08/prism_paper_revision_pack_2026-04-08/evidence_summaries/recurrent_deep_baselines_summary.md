# Recurrent Deep Sequence Baseline Summary

- Models: `LSTM-AE` and `GRU-AE`.
- Seeds: `[101, 202, 303]`; lengths: `[4, 8]`; epochs: `12`.
- Training uses ID benign only; evaluation uses the same stronger OOD/high-purity attack protocol.
- No recurrent AE baseline beats dA fixed region; lowest-alarm `gru_ae_L4_last` has alarm=0.6341, det=0.7451.

## Fixed q99 Aggregate
| object_label | detector_family | score_label | L | ood_alarm_ratio_eval_mean | ood_alarm_ratio_eval_std | attack_detection_high_purity_mean | attack_detection_high_purity_std | roc_auc_attack_high_vs_ood_eval_mean |
|---|---|---|---|---|---|---|---|---|
| gru_ae_L4_last | gru_ae | rmse_last_window | 4 | 0.634149 | 0.025744 | 0.745112 | 0.051629 | 0.638412 |
| lstm_ae_L4_last | lstm_ae | rmse_last_window | 4 | 0.673046 | 0.040398 | 0.831126 | 0.008474 | 0.714129 |
| lstm_ae_L8_last | lstm_ae | rmse_last_window | 8 | 0.679250 | 0.191481 | 0.832048 | 0.065309 | 0.708592 |
| gru_ae_L8_last | gru_ae | rmse_last_window | 8 | 0.795260 | 0.191272 | 0.667491 | 0.075310 | 0.442837 |
| lstm_ae_L4_full | lstm_ae | rmse_full_sequence | 4 | 0.810807 | 0.083249 | 0.910057 | 0.019528 | 0.703461 |
| gru_ae_L4_full | gru_ae | rmse_full_sequence | 4 | 0.862795 | 0.101779 | 0.863824 | 0.008169 | 0.634123 |
| lstm_ae_L8_full | lstm_ae | rmse_full_sequence | 8 | 0.980458 | 0.031905 | 0.992286 | 0.013109 | 0.717530 |
| gru_ae_L8_full | gru_ae | rmse_full_sequence | 8 | 0.992419 | 0.006568 | 0.884345 | 0.023790 | 0.501503 |


## Interpretation
- This is a baseline-risk check for A-tier framing. It should not be used as a Transformer improvement unless it beats both dA and the current covariance ensemble operating region.
