# Source-Rich Hard-Holdout Case Cards

Source package:
- verification source: `runs/frontend_f2_v7_4_paired_holdout_fairness_2026-04-22/`
- protocol: paired fairness, same holdout specs, same budgets, same seeds, same threshold rules, final OOD eval not used for threshold selection
- detector type: few-shot / supervised target-aligned logistic head

Interpretation boundary:
- These case cards do not support a claim that `source_rich` is the average-performance winner.
- They only support a narrower claim:
  - on specific hard holdouts, `source_rich` is materially more robust than `original100`;
  - `source_rich` also exposes more interpretable family / scale / feature structure.

## Case 1: `holdout_bin_2`, 16-shot, guarded

Setting:
- holdout: `holdout_bin_2`
- budget: `16-shot`
- threshold rule: `guarded_id_calib_and_ood_val_target1pct`

Core metrics:

| representation | AUC_min | det_min | alarm_max | feasible_rate |
|---|---:|---:|---:|---:|
| `original100` | 0.2404 | 0.1736 | 0.0029 | 1.0000 |
| `source_rich` | 0.8490 | 0.7129 | 0.0109 | 0.8000 |

How `original100` fails:
- It keeps final OOD alarm very low, but it does so by pushing this held-out attack window to the benign side.
- Across seeds, the mean attack-vs-OOD score gap is strongly negative: `~ -21.09`.
- The attack median remains far below the selected threshold: `median - threshold ~ -24.35`.
- This is a true held-out segment collapse, not a threshold-selection leak.

How `source_rich` stays useful:
- Detection remains high even on the unseen segment: `det_min=0.7129`.
- Separation remains usable: `AUC_min=0.8490`.
- Alarm is close to the low-OOD-alarm target, but not fully all-seed stable: `alarm_max=0.0109`.

Main `source_rich` signals:
- families:
  - `HH_jit`
  - `MI_dir`
  - `HH`
- scales:
  - `0.01s`
  - `3s`
  - `5s`
- features:
  - `logw_centered_family`
  - `logw_raw`
  - `mean_slog_raw`
  - `std_slog_raw`
  - `cv_short_long_ratio`

Alarm judgment:
- near-target

Conservative paper sentence:
- On `holdout_bin_2` under 16-shot guarded selection, `original100` collapses despite very low OOD alarm, whereas `source_rich` preserves useful detection near the 1% alarm boundary, supporting a narrow hard-holdout robustness claim on this unseen attack segment.

## Case 2: `holdout_bin_2`, 32-shot, guarded

Setting:
- holdout: `holdout_bin_2`
- budget: `32-shot`
- threshold rule: `guarded_id_calib_and_ood_val_target1pct`

Core metrics:

| representation | AUC_min | det_min | alarm_max | feasible_rate |
|---|---:|---:|---:|---:|
| `original100` | 0.3158 | 0.2329 | 0.0035 | 1.0000 |
| `source_rich` | 0.9079 | 0.7530 | 0.0123 | 0.6000 |

How `original100` fails:
- Increasing the positive budget does not rescue the held-out segment.
- The mean attack-vs-OOD score gap stays negative: `~ -14.40`.
- The attack median still remains below the selected threshold: `median - threshold ~ -15.01`.
- This means the failure is not just label scarcity; the representation remains misaligned on this hard window.

How `source_rich` stays useful:
- `source_rich` keeps strong separation and materially higher detection:
  - `AUC_min=0.9079`
  - `det_min=0.7530`
- It still does not fully close the alarm problem:
  - `alarm_max=0.0123`
  - `feasible_rate=0.6000`

Main `source_rich` signals:
- families:
  - `HH_jit`
  - `MI_dir`
  - `HH`
- scales:
  - `0.01s`
  - `3s`
  - `5s`
- features:
  - `logw_centered_family`
  - `logw_raw`
  - `std_slog_raw`
  - `cv_short_long_ratio`
  - `mean_rel_family`

Alarm judgment:
- near-target, not stable enough for a broad deployment claim

Conservative paper sentence:
- Even at 32-shot, `original100` does not recover on `holdout_bin_2`, while `source_rich` remains substantially more robust; however, the resulting alarm is only near-target rather than fully stable, so the claim should remain case-based rather than universal.

## Case 3: `chrono_late_train_early_eval`, 32-shot, guarded

Setting:
- holdout: `chrono_late_train_early_eval`
- budget: `32-shot`
- threshold rule: `guarded_id_calib_and_ood_val_target1pct`

Core metrics:

| representation | AUC_min | det_min | alarm_max | feasible_rate |
|---|---:|---:|---:|---:|
| `original100` | 0.7030 | 0.6824 | 0.0029 | 1.0000 |
| `source_rich` | 0.9494 | 0.8549 | 0.0099 | 1.0000 |

How `original100` fails:
- This is not a total collapse to zero, but it leaves a large miss-prone attack tail under reverse chronology.
- The attack median is above threshold, yet the lower attack tail remains far below threshold:
  - `q10 - threshold ~ -53.13`
- So the detector misses a nontrivial hard subset even though aggregate alarm remains low.

How `source_rich` stays useful:
- It preserves both strong detection and valid low-OOD-alarm feasibility:
  - `AUC_min=0.9494`
  - `det_min=0.8549`
  - `alarm_max=0.0099`
  - `feasible_rate=1.0000`
- This is the cleanest v7.4 paper-facing robustness case.

Main `source_rich` signals:
- families:
  - `MI_dir`
  - `HH`
  - `HH_jit`
- scales:
  - `0.01s`
  - `3s`
  - `1s`
- features:
  - `logw_centered_family`
  - `cv_short_long_ratio`
  - `logw_raw`
  - `mean_rel_family`
  - `cv_slog_raw`

Alarm judgment:
- satisfies the 1% target

Conservative paper sentence:
- Under reverse chronology (`late-train -> early-eval`), `source_rich` retains both strong detection and guarded low-OOD-alarm feasibility, while `original100` leaves a substantial miss-prone attack tail, supporting a narrow but positive hard-holdout robustness claim for `source_rich`.

## Bottom Line

- `source_rich` is not the average-performance winner in v7.4.
- `original100` remains the mandatory control and wins most holdouts by `det_mean`.
- The paper-safe role for `source_rich` is:
  - hard-holdout robustness on specific paired cases
  - auditability / family-scale-feature interpretation
  - not universal cross-window dominance
