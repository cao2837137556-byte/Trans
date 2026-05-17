# Missing Row-Level Score Report

Issue16c does not recompute models or train new models. Issue16b saved seed-level metrics, thresholds, support provenance, and threshold provenance, but it did not save per-sample score arrays for the v7.4 harder holdouts.

Therefore score distribution and margin-to-threshold diagnostics cannot be computed honestly for `chrono_late_train_early_eval` or `holdout_bin_2` without rerunning or extending the issue16b scorer to persist row-level scores. This is a provenance gap, not a negative result.
