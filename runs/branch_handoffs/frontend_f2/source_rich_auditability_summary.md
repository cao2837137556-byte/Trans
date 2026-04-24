# Source-Rich Auditability Summary

Scope:
- derived from the already verified v7.4 paired holdout package
- no new training, no new model, no new experiment line
- aggregated over three paper-facing hard-holdout cases:
  - `holdout_bin_2`, 16-shot, guarded
  - `holdout_bin_2`, 32-shot, guarded
  - `chrono_late_train_early_eval`, 32-shot, guarded

Interpretation rule:
- The values below summarize signed contribution strength for attack-vs-OOD separation under the fitted `source_rich` logistic head.
- They are explanation assets, not claims of universal global importance.

## 1. Family-Level Summary

Recurring family signals across the three cases:

| family | mean contribution |
|---|---:|
| `HH_jit` | 6.2244 |
| `MI_dir` | 4.6819 |
| `HH` | 3.7646 |
| `HpHp` | 0.2624 |

Reading:
- `HH_jit` is the strongest recurring family on the `holdout_bin_2` collapse cases.
- `MI_dir` becomes especially important in the reverse-chronology case.
- `HH` is consistently present as a secondary stabilizing family.

## 2. Scale-Level Summary

Recurring scale signals across the three cases:

| scale | mean contribution |
|---|---:|
| `0.01s` | 5.0452 |
| `3s` | 3.1696 |
| `1s` | 2.7063 |
| `5s` | 2.4641 |
| `0.1s` | 1.5482 |

Reading:
- The shortest scale `0.01s` is the dominant recurring signal.
- `3s` is the most stable medium-timescale contributor.
- `1s` and `5s` both matter, but their importance depends on the holdout type.

## 3. Feature-Level Top Signals

Top recurring channels across the three cases:

| feature_channel | mean contribution |
|---|---:|
| `logw_centered_family` | 7.4626 |
| `logw_raw` | 4.2955 |
| `cv_short_long_ratio` | 2.0642 |
| `std_slog_raw` | 1.2432 |
| `mean_rel_family` | 0.9497 |
| `mean_slog_raw` | 0.7309 |
| `pcc_slog_raw` | 0.2611 |
| `pcc_centered_family` | 0.1181 |

Reading:
- The most important recurring source-rich signal is not a raw single statistic but a family-centered log-weight feature:
  - `logw_centered_family`
- Raw volume still matters:
  - `logw_raw`
- Relative cross-timescale instability also matters:
  - `cv_short_long_ratio`

## 4. Case-Coupled Explanation Notes

### `holdout_bin_2`, 16-shot, guarded

- dominant families:
  - `HH_jit`, `MI_dir`, `HH`
- dominant scales:
  - `0.01s`, `3s`, `5s`
- dominant features:
  - `logw_centered_family`, `logw_raw`, `mean_slog_raw`, `std_slog_raw`, `cv_short_long_ratio`

Interpretation:
- This case looks like a short-timescale, family-relative shift.
- `source_rich` seems to help because it exposes abrupt family-centered volume and variation patterns that the flat 100D control does not preserve robustly on this unseen attack segment.

### `holdout_bin_2`, 32-shot, guarded

- dominant families:
  - `HH_jit`, `MI_dir`, `HH`
- dominant scales:
  - `0.01s`, `3s`, `5s`
- dominant features:
  - `logw_centered_family`, `logw_raw`, `std_slog_raw`, `cv_short_long_ratio`, `mean_rel_family`

Interpretation:
- The same family/scale structure remains after increasing the positive budget.
- That consistency is useful for paper writing because it suggests the robustness gain is structural rather than a one-off seed artifact.

### `chrono_late_train_early_eval`, 32-shot, guarded

- dominant families:
  - `MI_dir`, `HH`, `HH_jit`
- dominant scales:
  - `0.01s`, `3s`, `1s`
- dominant features:
  - `logw_centered_family`, `cv_short_long_ratio`, `logw_raw`, `mean_rel_family`, `cv_slog_raw`

Interpretation:
- In the reverse-chronology case, `source_rich` is not just using the shortest burst signal.
- It also uses medium-timescale relative variation and family-level normalization, which is consistent with a more robust representation under temporal shift.

## 5. Paper-Safe Interpretation

The paper-safe auditability claim is:
- `source_rich` highlights a recurring family-centered, short-timescale, variance-sensitive signal structure on hard holdouts;
- this structure helps explain why `source_rich` can remain useful on specific holdouts where `original100` collapses or develops a large miss-prone tail;
- this does not imply that `source_rich` is the average-performance winner across all holdouts.
