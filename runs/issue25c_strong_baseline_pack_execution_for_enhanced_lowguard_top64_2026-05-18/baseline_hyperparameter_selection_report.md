# Baseline Hyperparameter Selection Report

Hyperparameter selection did not use final OOD eval or final attack eval.

- Fixed baselines used pre-registered single configurations.
- HistGB used a two-configuration shallow tree grid.
- DevNet-like MLP used a fixed lightweight configuration to avoid broad neural sweep.
- DeepSAD-like center-distance used lambda candidates selected by support-holdout and OOD validation.
- Unsupervised baselines used fixed conservative configurations and no attack labels for model fitting.

All selected configurations are listed in `baseline_selected_configs.csv`; all searched configurations are listed in `baseline_search_space.csv`.
