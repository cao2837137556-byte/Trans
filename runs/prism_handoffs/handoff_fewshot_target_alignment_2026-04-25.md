# Prism Handoff: Few-Shot Target Alignment Paper Package

Date: 2026-04-25

Canonical purpose:
- This file is a paper-facing handoff for Prism.
- It is not an experiment log.
- It summarizes the current convergence-first paper center, the data/split/budget口径, and the writable evidence around few-shot target alignment, original100 official control, and source_rich hard-holdout auditability.

Primary source assets:
- Mainline map: `runs/mainline_docs/mainline_experiment_map.md`
- Original100 official control: `runs/original100_fewshot_official_control_2026-04-22/`
- Source-rich v7.2 fairness validation: `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/frontend_f2_v7_2_fairness_validation_2026-04-22/`
- Source-rich v7.3 DA fairness comparison: `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/frontend_f2_v7_3_da_fairness_comparison_2026-04-22/`
- Source-rich v7.4 paired holdout fairness: `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/frontend_f2_v7_4_paired_holdout_fairness_2026-04-22/`
- Paper-facing source-rich assets: `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/`

Generated structured tables:
- `runs/prism_handoffs/fewshot_dataset_split_budget_summary_2026-04-25.csv`
- `runs/prism_handoffs/fewshot_paper_main_table_2026-04-25.csv`

---

## 1. Current Paper Center

Current paper center:
- `strict low-OOD-alarm operating region`
- `unsupervised detection collapse`
- `few-shot target-aligned detector`

中文口径：

开放世界 IoT 异常检测的关键难点，不是普通 AUC 排名，而是在 stronger benign OOD 条件下，检测器是否能在严格低 OOD 误报区间仍保持攻击检出能力。传统 unsupervised detector 在这个区间容易出现 detection collapse；few-shot target alignment 用极少量 high-purity attack positives 修正训练目标与部署目标错配。

论文主线应写成：
- 无监督异常分数在低 OOD 误报 operating point 下会出现目标错配和检出塌陷。
- few-shot target-aligned logistic head 使用少量高纯攻击正样本，将训练目标直接对齐到部署时的 low-OOD-alarm 检测目标。
- original100 few-shot 是 official control，证明主要杠杆是 target alignment。
- source_rich 的价值不是平均性能全面胜出，而是在特定 hard holdout 上更稳，并且能提供 family / scale / feature 级解释。

---

## 2. Dataset / Split / Budget Summary

### 2.1 Split Table

| data role | train rows | validation rows | calibration rows | eval rows | train candidate pool rows | holdout rows / segments | notes |
|---|---:|---:|---:|---:|---:|---|---|
| ID benign | 8000 | 2000 | 5000 | 35000 | N/A | N/A | ID eval is final-only and unused by threshold selection |
| OOD benign | 8000 | 2000 | N/A | 10000 | N/A | N/A | OOD validation can be used by guarded threshold selection; final OOD eval is held out |
| high-purity attack | N/A | 1374 | N/A | 1375 | 4122 | v7.4 uses 9 attack-window holdout specs; eval rows range 426 to 3426 by holdout | 16/32-shot samples are drawn from the train candidate pool only |

Source of split rows:
- original100 manifest: `runs/original100_fewshot_official_control_2026-04-22/official_control_manifest.json`
- v7.2/v7.3 metadata: frontend-f2 run metadata files
- v7.4 metadata: `frontend_f2_v7_4_paired_holdout_metadata.json`

### 2.2 Few-Shot Budget口径

- `16-shot` / `32-shot` only means the number of high-purity attack positive samples used to train the logistic head.
- It is not the whole evaluation set size.
- Negatives still come from ID benign + OOD benign train partitions.
- Final OOD eval is never used for threshold selection.
- Positive sampling uses multiple seeds: `42,43,44,45,46`.
- Reported metrics are computed on held-out OOD benign and held-out high-purity attack eval rows.

### 2.3 Holdout / Fairness口径

Original100 few-shot official control:
- representation: original frontend flat100
- model: L2 `LogisticRegression`, balanced class weights, `C=1.0`
- budgets: `16`, `32`
- seeds: `42,43,44,45,46`
- threshold rules: `fixed_id_calib_q99`, `guarded_id_calib_and_ood_val_target1pct`
- final OOD eval does not participate in threshold selection

Source-rich v7.2 / v7.3:
- representation: `source_rich_v1`, flattened to 260D
- model: L2 `LogisticRegression`, balanced class weights
- budgets include `16`, `32`, `64`; paper-facing focus should stay on 16/32 for comparability
- seeds: `42,43,44,45,46`
- threshold rules: `fixed_id_calib_q99`, `guarded_id_calib_and_ood_val_target1pct`
- final OOD eval does not participate in threshold selection

Source-rich v7.4 paired holdout:
- same holdout specs
- same label budgets
- same seed set
- same threshold rules
- final OOD eval does not participate in threshold selection
- compared representations: `source_rich_v1_flat260` vs `original_frontend_flat100`

### 2.4 Why These Runs Are Fast

These runs are fast because they are not retraining a large neural detector. The representation is frozen, and the experiment only trains an L2 LogisticRegression linear head on low-dimensional inputs: original100 is 100D, and source_rich is 260D after flattening. The model is light, the feature dimension is small, and the positive budget is intentionally tiny. This speed does not mean the evaluation set contains only 16 or 32 samples, and it does not imply insufficient data scale. The 16/32-shot budget only controls the number of labeled high-purity attack positives used for target alignment; evaluation still uses held-out OOD benign and held-out high-purity attack partitions.

---

## 3. Paper-Facing Main Evidence Table

| evidence group | method / case | role | input | labels used | budget | policy | AUC mean/min | OOD alarm max | det mean/min | feasible rate | paper use |
|---|---|---|---|---|---:|---|---|---:|---|---:|---|
| unsupervised reference | dA score, fixed q99 | unsupervised reference | original100 | no attack labels | N/A | fixed_id_calib_q99 | 0.8064 / 0.8064 | 0.1286 | 0.6865 / 0.6865 | 0.0000 | reference only; not same label setting |
| unsupervised reference | dA score, guarded | unsupervised reference | original100 | no attack labels | N/A | guarded_id_calib_and_ood_val_target1pct | 0.8064 / 0.8064 | 0.0108 | 0.0029 / 0.0029 | 0.0000 | collapse example under low-OOD-alarm |
| official control | original100 few-shot | target-aligned official control | original100 | high-purity attack positives | 16 | guarded | 0.9907 / 0.9580 | 0.0092 | 0.9676 / 0.9142 | 1.0000 | shows target alignment is the main lever |
| official control | original100 few-shot | target-aligned official control | original100 | high-purity attack positives | 32 | guarded | 0.9846 / 0.9676 | 0.0098 | 0.9407 / 0.9207 | 1.0000 | confirms label-efficient control |
| source-rich current split | source_rich v7.2 few-shot | target-aligned evidence | source_rich 260D | high-purity attack positives | 16 | guarded | 0.9776 / 0.9646 | 0.0088 | 0.9487 / 0.9273 | 1.0000 | positive source_rich current-split evidence |
| source-rich current split | source_rich v7.2 few-shot | target-aligned evidence | source_rich 260D | high-purity attack positives | 32 | guarded | 0.9776 / 0.9682 | 0.0109 | 0.9587 / 0.9476 | 0.8000 | high detection but not all-seed alarm stable |
| source-rich comparison | source_rich v7.3 few-shot | DA comparison evidence | source_rich 260D | high-purity attack positives | 16 | guarded | 0.9776 / 0.9646 | 0.0088 | 0.9487 / 0.9273 | 1.0000 | confirms few-shot beats DA reference under low-alarm protocol |
| v7.4 hard case | chrono_late_train_early_eval, source_rich | hard-holdout robustness | source_rich 260D | high-purity attack positives | 32 | guarded | 0.9644 / 0.9494 | 0.0099 | 0.8966 / 0.8549 | 1.0000 | cleanest main-text source_rich case |
| v7.4 paired control | chrono_late_train_early_eval, original100 | paired hard-holdout control | original100 | high-purity attack positives | 32 | guarded | 0.7178 / 0.7030 | 0.0029 | 0.6913 / 0.6824 | 1.0000 | shows original100 miss-prone tail under reverse chronology |
| v7.4 appendix case | holdout_bin_2, source_rich | hard-holdout robustness near target | source_rich 260D | high-purity attack positives | 16 | guarded | 0.9342 / 0.8490 | 0.0109 | 0.8586 / 0.7129 | 0.8000 | appendix case; alarm near-target |
| v7.4 appendix case | holdout_bin_2, original100 | paired collapse case | original100 | high-purity attack positives | 16 | guarded | 0.3450 / 0.2404 | 0.0029 | 0.2838 / 0.1736 | 1.0000 | severe segment collapse despite low alarm |
| v7.4 appendix case | holdout_bin_2, source_rich | hard-holdout robustness near target | source_rich 260D | high-purity attack positives | 32 | guarded | 0.9631 / 0.9079 | 0.0123 | 0.8680 / 0.7530 | 0.6000 | appendix case; alarm near-target only |
| v7.4 appendix case | holdout_bin_2, original100 | paired collapse case | original100 | high-purity attack positives | 32 | guarded | 0.3971 / 0.3158 | 0.0035 | 0.3231 / 0.2329 | 1.0000 | more positives do not rescue original100 on this segment |

Interpretation:
- dA is an unsupervised reference, not a same-label-information competitor.
- original100 few-shot is the official control and should be treated as the central proof that target alignment is the primary lever.
- source_rich should be used for hard-holdout robustness and auditability, not as a universal average-performance winner.

---

## 4. Boundary Paragraph Draft for Prism

当前结果说明，few-shot target alignment 是主线中最稳定的性能杠杆。original100 few-shot official control 在 16-shot 和 32-shot 下已经能在 guarded low-OOD-alarm protocol 中保持高 AUC、高检出率和全 seed 可行性，因此论文不能把增益简单归因于 source-rich 前端本身。更准确的写法是：少量 high-purity attack positives 将线性检测头的目标从无监督重构/异常分数校正为面向部署的 attack-vs-benign decision boundary，从而显著缓解低 OOD 误报区间的 detection collapse。source_rich 不能写成平均性能全面优于 original100；v7.4 显示 original100 仍按 det_mean 赢多数 holdout。source_rich 的可写价值应限定为特定 hard holdout 上更稳，并提供 family / scale / feature 级可审计解释。其中 `chrono_late_train_early_eval, 32-shot, guarded` 是最干净的主文案例，因为 source_rich 同时满足 1% OOD alarm 约束并保持更高 det_min；`holdout_bin_2` 的 16-shot 和 32-shot 可放在补充材料中，说明 original100 的 segment collapse 与 source_rich 的近目标稳定性，但需要明确其 alarm only near-target。

---

## 5. Auditability Paragraph Draft for Prism

source_rich 的主要论文价值不应写成全局平均性能优势，而应写成 hard-holdout 行为的可审计表示。在已核验的 v7.4 case analysis 中，source_rich 反复暴露出 family-centered、short-timescale、variance-sensitive 的信号结构：family 层面以 `HH_jit`、`MI_dir`、`HH` 为主，scale 层面以 `0.01s`、`3s`、`1s/5s` 为主，feature 层面以 `logw_centered_family`、`logw_raw`、`cv_short_long_ratio`、`std_slog_raw`、`mean_rel_family` 为主。这些信号比 flat original100 更适合解释为什么某些 hard holdout 中检测器会保留或丢失攻击区分能力。在 `chrono_late_train_early_eval` 中，source_rich 同时利用短时突发、家族归一化和中尺度相对变化，使其在 guarded 32-shot 下保持 `alarm_max=0.0099` 与更高 `det_min`。在 `holdout_bin_2` 中，original100 将 held-out attack segment 推向 benign 一侧，而 source_rich 仍能保留明显分离；但这两个 bin-2 case 的 alarm 只是接近 1% 目标而非全 seed 稳定，因此更适合作为 supplementary / appendix evidence。

---

## 6. Supervision Fairness / Label-Cost Defense Draft

few-shot target alignment 不是把问题偷换成大规模监督分类。本文的 few-shot setting 只使用 16 或 32 个 high-purity attack positives 来训练一个线性 logistic head，负类仍来自 ID benign 与 OOD benign，评估仍在 held-out OOD benign 和 held-out high-purity attack 上完成。合理的正样本来源假设包括：已经确认的攻击事件片段、安全运营复核后的少量高置信样本、以及历史告警中人工确认的攻击流量。这些来源符合实际安全运营中少量高置信攻击样本可获得、但大规模逐包标注不可获得的设定。

公平性上，final OOD eval 不参与阈值选择，降低了将最终测试分布泄漏到 operating point 选择中的风险。`fixed_id_calib_q99` 只用 ID calibration 设阈值，`guarded_id_calib_and_ood_val_target1pct` 只用 ID calibration 与 OOD validation 选择阈值。dA 必须写成 unsupervised reference，因为它不使用 attack labels；few-shot logistic 必须写成 label-efficient target-aligned detector，因为它使用少量 high-purity positives。二者可以用于说明低误报部署区间中的目标错配与修正效果，但不应被描述为同监督信息条件下的公平同类模型比较。

---

## 7. Prism Writing Rules

Use:
- "few-shot target-aligned detector"
- "label-efficient target alignment"
- "unsupervised detection collapse under strict low-OOD-alarm operating region"
- "original100 official control"
- "source_rich hard-holdout robustness and auditability"

Avoid:
- "source_rich universally beats original100"
- "dA and few-shot are same-setting models"
- "16/32-shot is the whole dataset size"
- "few-shot fully solves open-world anomaly detection"
- "second-environment strengthens the main evidence"

