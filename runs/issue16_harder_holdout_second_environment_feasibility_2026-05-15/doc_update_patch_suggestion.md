# Suggested Mainline Docs Update

Do not edit the manuscript for issue16. If updating mainline docs later, append:

## 2026-05-15 Issue16 harder-holdout / second-environment feasibility

Issue16 found that the nearest usable harder-holdout asset is the existing frontend-f2 v7.4 paired hard-holdout pack, especially `chrono_late_train_early_eval` and `holdout_bin_2`. However, it is not yet a zero-risk validation target for current GDA-minimal because current fixed-guard model/scaler/row-level score artifacts do not directly transfer. BoT-IoT and TON-IoT local assets exist but are not current-protocol-ready second environments. Recommended next step is issue16b fixed-config hard-holdout validation on v7.4, with no hyperparameter search and full support/threshold provenance.
