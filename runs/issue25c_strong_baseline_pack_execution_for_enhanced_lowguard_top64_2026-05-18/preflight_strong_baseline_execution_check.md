# Preflight Strong Baseline Execution Check

1. issue25b protocol read: yes.
2. Main method frozen as source_rich_top64 + kcenter32 + fixed OOD guard LR: yes.
3. No topK/support/adapter/threshold retuning: yes.
4. Required baselines executable on locked bins 5/6/7/8: yes.
5. Consistency checks available for primary_lowood, holdout_bin_2, chrono_late: yes.
6. Hyperparameters use train/cal/val or support-holdout only: yes.
7. final eval report-only: yes.
8. Seed-level metrics output: yes.
9. Low-FPR metrics output: yes.
10. Required / optional / design-only categories preserved: yes.
