# Source-Rich vs Original100 Boundary Table

Interpretation rule:
- This is a role-split table, not a winner-takes-all scoreboard.
- `original100` remains the average-performance control.
- `source_rich` only earns a performance claim on specific hard holdouts.

| holdout_name | source_rich det_mean wins | original100 det_mean wins | role_split | boundary note |
|---|---:|---:|---|---|
| `chrono_early_train_late_eval` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | `original100` is stronger by average det_mean; `source_rich` is only competitive here and should not be used for a robustness claim. |
| `chrono_late_train_early_eval` | 4 / 4 | 0 / 4 | `source_rich_hard_case_more_robust` | `source_rich` is materially more robust on this reverse-chronology hard holdout; guarded 32-shot also satisfies the 1% alarm target. |
| `holdout_bin_2` | 4 / 4 | 0 / 4 | `source_rich_hard_case_more_robust` | `original100` segment-collapse is severe; `source_rich` keeps useful detection but alarm is near-target rather than fully stable. |
| `holdout_bin_3` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | `original100` is clearly stronger by average det_mean; this holdout does not support a `source_rich` robustness claim. |
| `holdout_bin_4` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | `original100` dominates by mean detection; `source_rich` remains interpretable but not performance-advantaged. |
| `holdout_bin_5` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | `original100` is stronger across all paired settings; `source_rich` should not be framed as superior here. |
| `holdout_bin_6` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | Near-parity on some settings, but `original100` still wins every paired setting by mean detection. |
| `holdout_bin_7` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | `source_rich` can have cleaner alarm on some settings, but `original100` remains the average detection winner. |
| `holdout_bin_8` | 0 / 4 | 4 / 4 | `original100_average_det_mean_stronger` | `original100` remains stronger by mean detection; `source_rich` does not earn a separate robustness claim on this holdout. |

## Paper-safe summary

- `original100` wins most holdouts by average `det_mean`.
- `source_rich` should not be claimed as the average-performance winner.
- The only paper-safe role split is:
  - `original100` = performance control
  - `source_rich` = hard-holdout robustness on specific cases + auditability
