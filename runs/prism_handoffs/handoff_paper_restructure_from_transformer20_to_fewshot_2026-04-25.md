# Prism Handoff: From Transformer 20 Draft to Few-Shot Target Alignment Mainline

Date: 2026-04-25  
Target reader: Prism  
Purpose: provide a controlled restructuring package before rewriting the manuscript. This is not a paper draft and must not be treated as permission to freely invent claims.

---

## 0. Source Materials and Parsing Boundary

This handoff integrates the current project truth from the following assets:

| Asset | Path | Role |
|---|---|---|
| Mainline convergence-first map | `runs/mainline_docs/mainline_experiment_map.md` | Canonical current paper center, evidence layering, archived-route boundary |
| Few-shot target alignment handoff | `runs/prism_handoffs/handoff_fewshot_target_alignment_2026-04-25.md` | Paper-facing few-shot protocol, dataset/split/budget explanation, main table |
| Dataset/split/budget summary | `runs/prism_handoffs/fewshot_dataset_split_budget_summary_2026-04-25.csv` | Structured evidence that 16/32-shot means positive training budget, not eval size |
| Few-shot paper main table | `runs/prism_handoffs/fewshot_paper_main_table_2026-04-25.csv` | dA reference, original100 official control, source_rich evidence summary |
| Collapse sanity audit handoff | `runs/prism_handoffs/handoff_collapse_sanity_audit_2026-04-25.md` | Paper-facing collapse sanity statement |
| Collapse sanity audit run | `runs/collapse_sanity_audit_2026-04-25/` | Cache/index/score-direction/threshold-leakage audit artifacts |
| Source-rich hard-holdout case cards | `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/paper_facing_hard_holdout_cases.md` | Paper-facing hard-holdout cases |
| Source-rich boundary table | `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_original100_boundary_table.csv` | Role split between original100 and source_rich |
| Source-rich boundary table, markdown | `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_original100_boundary_table.md` | Human-readable boundary table |
| Source-rich auditability summary | `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_auditability_summary.md` | Family / scale / feature explanation assets |
| frontend-f2 handoff | `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/frontend_f2_handoff.md` | Branch-level source_rich status and boundaries |
| Old manuscript PDF | `D:/study/paper/anomaly_detection/paper04/Transformer 20.pdf` | Current old draft to restructure away from Transformer ensemble center |

PDF parsing note: `Transformer 20.pdf` is locally accessible. Text extraction is partially garbled because of PDF encoding, but the visible section skeleton and numerical tables are sufficient to identify the old manuscript center: covariance-aware Transformer ensemble / ID-only operating-region improvement. The restructuring decisions below are anchored primarily in the current mainline map and paper-facing evidence packages, not in a full reliable PDF text parse.

---

## 1. Current New Paper Center

当前新版论文中心不是“Transformer ensemble 全面击败 dA”，而是：

> 在 `strict low-OOD-alarm operating region` 下，无监督 anomaly detector 会出现 `operating-point detection collapse`；`few-shot target alignment` 用极少量 `high-purity attack positives` 修正训练目标与部署目标错配，从而恢复低误报区间的 attack detection。`source_rich` 的价值是 `hard-holdout robustness + auditability`，而不是平均性能全面胜出。

This center must appear before any discussion of the old Transformer ensemble. The old manuscript should be mined for motivation, protocol vocabulary, operating-point analysis, baseline-failure framing, and limitation style, but its method hero must be retired.

Current canonical roles:

| Component | Current role | Must not be overstated as |
|---|---|---|
| dA | `unsupervised reference` | Same-supervision competitor to few-shot models |
| original100 few-shot logistic | `official control` for target alignment | A new frontend or a new deep model |
| source_rich few-shot | `hard-holdout robustness + auditability` asset | Universal average-performance winner |
| A-line second-environment | `negative evidence / limitation / external-validity boundary` | Positive support for the current mainline |
| old stronger OOD / calibration / TailReg | Historical mechanism assets | Current sole paper center |

---

## 2. New Contribution Set

### 2.1 Problem Definition Contribution

The paper should shift from generic AUC ranking or detector leaderboard framing to deployment usability under a `strict low-OOD-alarm operating region`.

Required formulation:

| Point | Paper-facing wording |
|---|---|
| Main challenge | Open-world IoT IDS must keep benign OOD alarms low while still detecting high-purity attacks. |
| Evaluation boundary | ID benign, OOD benign, and high-purity attack must be separated. |
| Threshold boundary | Final OOD eval and attack eval must not participate in threshold selection. |
| Metric emphasis | AUC is diagnostic, but operating-point detection under low OOD alarm is the central deployability question. |

### 2.2 Mechanism Discovery Contribution

Unsupervised detectors can retain nontrivial ranking ability while collapsing at the required operating point.

Evidence anchor:

| Evidence | Conservative interpretation |
|---|---|
| dA official reference AUC about `0.806` | The score contains attack-vs-OOD ranking signal. |
| dA guarded 1% detection about `0.0029` | Signal is not usable at the strict guarded low-OOD-alarm point. |
| dA 10% OOD alarm detection about `0.6516` | Collapse is mainly operating-point trade-off, not complete score invalidity. |
| Cache/index/direction/leakage audit | Current dA collapse is unlikely to be caused by row-order, index, score-direction, or threshold-leakage bugs. |

Prism must phrase this as an evidence-backed operating-point effect, not as a universal theorem over every anomaly detector.

### 2.3 Method Lever Contribution

The method lever is `few-shot target-aligned LogisticRegression`, not a new Transformer ensemble.

Protocol:

| Element | Current definition |
|---|---|
| Model | L2 `LogisticRegression` linear head on frozen representation |
| Positives | stage2 high-purity attack |
| Negatives | ID benign + OOD benign |
| Budgets | `16-shot` and `32-shot` high-purity attack positives for training |
| Important clarification | `16-shot` / `32-shot` is not the evaluation-set size |
| Seeds | Positive sampling uses multiple seeds; report mean / min / max |
| Thresholds | `fixed_id_calib_q99` and `guarded_id_calib_and_ood_val_target1pct` |
| Fairness | Final OOD eval and attack eval do not tune thresholds |

Why runs are fast: the experiments train a lightweight linear head on frozen low-dimensional representations (`original100` is 100D; `source_rich` flatten is 260D). Fast execution does not imply small evaluation data.

### 2.4 Source-Rich Supplemental Contribution

`source_rich` should be written as a specific robustness and auditability asset:

| Finding | Allowed wording |
|---|---|
| original100 wins by average `det_mean` on most paired holdouts | original100 remains the official control and strong default target-aligned representation. |
| source_rich stabilizes specific hard holdouts | source_rich provides hard-holdout robustness evidence under paired fairness. |
| `chrono_late_train_early_eval, 32-shot, guarded` | Cleanest main-text case for source_rich. |
| `holdout_bin_2, 16/32-shot, guarded` | Supplementary / appendix cases because alarm is near-target rather than fully stable. |
| family / scale / feature signals | Source-rich is more auditable than flat original100 in hard cases. |

Do not write that source_rich is the average-performance winner.

---

## 3. Old PDF Section Decision Table

| 旧稿部分 | 当前裁决 | 新稿处理方式 | 原因 / 对应资产 |
|---|---|---|---|
| 标题 | `major_rewrite` | 从 Transformer ensemble 标题改为 low-OOD-alarm collapse + few-shot target alignment 方向。 | 当前 paper center 已切换；见 `runs/mainline_docs/mainline_experiment_map.md`。 |
| 摘要 | `major_rewrite` | 重写问题、方法、结果和边界；Transformer ensemble 不再作为摘要主方法。 | 新中心是 few-shot target alignment；见 few-shot handoff 与 collapse handoff。 |
| 引言 | `major_rewrite` | 保留 open-world IoT 和 benign OOD 动机，重写成 strict low-OOD-alarm deployability 问题。 | old motivation 可吸收，但旧主线不再定义 paper center。 |
| 贡献列表 | `major_rewrite` | 改成四项：问题定义、collapse 机制发现、few-shot target alignment、source_rich hard-holdout/auditability。 | 见本 handoff 第 2 节。 |
| 问题设定与评测边界 | `keep_with_minor_rewrite` | 保留 ID benign / OOD benign / high-purity attack 边界，强化 final OOD eval 不参与阈值选择。 | 与 current few-shot protocol 兼容。 |
| 方法章节 | `major_rewrite` | 主方法改为 frozen representation + L2 LogisticRegression target-aligned head；Transformer ensemble 下沉。 | current method lever 不再是 covariance-aware Transformer ensemble。 |
| baseline 设置 | `major_rewrite` | 明确 dA 是 unsupervised reference，few-shot 是 label-efficient target-aligned detector；不得混成同标签公平比较。 | 见 `handoff_fewshot_target_alignment_2026-04-25.md`。 |
| 主结果 Transformer ensemble 部分 | `downgrade_to_background_or_appendix` | 作为历史机制资产或旧稿背景，不作为主结果中心。 | old result 不支持当前 few-shot 主线；legacy transformer cache 也不是 current official split 主证据。 |
| baseline failure 部分 | `keep_with_minor_rewrite` | 保留 baseline failure 逻辑，但改写为 low-OOD-alarm collapse / objective mismatch 证据。 | collapse sanity audit 支持 dA official reference 的 operating-point effect。 |
| 分数分布 / operating point 解释 | `keep_with_minor_rewrite` | 保留 operating-point 解释框架，并用 dA sweep 的 1% collapse / 10% recovery 更新。 | 见 `handoff_collapse_sanity_audit_2026-04-25.md`。 |
| 部署成本部分 | `downgrade_to_background_or_appendix` | 旧 Transformer ensemble cost table 降级；新版部署讨论应聚焦 label cost、linear head、threshold fairness。 | few-shot logistic runs are lightweight; source_rich cost not current universal winner claim. |
| 讨论与局限 | `keep_with_minor_rewrite` | 保留克制语气，加入 second-environment negative evidence、source_rich 非全面赢家、collapse scope 边界。 | 见 mainline map limitation / archive sections。 |
| 结论 | `major_rewrite` | 从 Transformer ensemble 收束改为 few-shot target alignment 恢复 low-alarm detection 的克制结论。 | 当前主线不允许把 Transformer ensemble 写成最终主方法。 |

Structured CSV version: `runs/prism_handoffs/paper_restructure_section_decision_table_2026-04-25.csv`.

---

## 4. Recommended New Paper Structure

| Section | Goal | Use these assets | Avoid these overclaims |
|---|---|---|---|
| 1. Introduction | Establish open-world IoT IDS deployability under strict low-OOD-alarm constraints; introduce objective mismatch. | Mainline map sections 1-2; old PDF motivation; collapse handoff. | Do not introduce Transformer ensemble as current hero. |
| 2. Problem Setup and Low-OOD-Alarm Evaluation | Define ID benign, OOD benign, high-purity attack, threshold rules, final OOD eval exclusion, and 16/32-shot budget meaning. | Few-shot handoff; dataset/split/budget CSV. | Do not imply 16/32-shot is the whole evaluation size. |
| 3. Unsupervised Detection Collapse | Show dA and legacy unsupervised evidence under guarded low-OOD-alarm; explain operating-point collapse. | Collapse sanity audit handoff and run outputs; old baseline-failure material. | Do not claim collapse is a universal law for all models/datasets. |
| 4. Few-Shot Target Alignment | Present L2 LogisticRegression head on frozen representations; define positives, negatives, budgets, seeds, thresholds. | Few-shot handoff; original100 official control results. | Do not frame as large-scale supervised classifier. |
| 5. Main Results: Restoring Detection under Low-OOD Alarm | Report dA reference vs original100 few-shot official control and source_rich main few-shot evidence under correct information conditions. | Few-shot paper main table CSV. | Do not compare dA and few-shot as same-label-setting models. |
| 6. Source-Rich Hard-Holdout Robustness and Auditability | Present source_rich as hard-holdout + interpretability asset, with role split against original100. | frontend-f2 hard-holdout case cards, boundary table, auditability summary. | Do not write source_rich universally beats original100. |
| 7. Deployment Meaning, Label Cost, and Fairness Boundary | Defend few-shot supervision fairness, high-purity positive sources, low label cost, and threshold leakage prevention. | Few-shot handoff sections on label-cost defense; dataset/split/budget summary. | Do not claim few-shot completely solves open-world IDS. |
| 8. Discussion and Limitations | State second-environment failure as external-validity boundary, source_rich boundary, legacy evidence scope, and future work. | Mainline map limitation/archive sections; A-line failure closure; source_rich boundary assets. | Do not convert negative second-environment evidence into positive support. |
| 9. Conclusion | Conclude that strict low-OOD-alarm evaluation exposes objective mismatch and few-shot target alignment is a practical remedy under this protocol. | All paper-facing handoffs. | Do not resurrect Transformer ensemble as the final method. |

---

## 5. How to Absorb Old Experiments

### 5.1 Directly Keep / Keep With Minor Rewrite

| Old asset | New role |
|---|---|
| Open-world IoT and benign OOD false-alarm motivation | Introduction and problem setup motivation |
| ID benign / OOD benign / high-purity attack evaluation boundary | Core protocol definition |
| Some baseline failure evidence | Mechanism section for low-OOD-alarm collapse |
| Conservative limitation writing style | Discussion and limitations |

### 5.2 Keep After Rewriting

| Old asset | Rewrite direction |
|---|---|
| stronger OOD / calibration / TailReg | Historical mechanism assets for threshold and distribution-tail mismatch |
| Score distribution and operating-point analysis | Update with dA official collapse sweep and guarded threshold evidence |
| dA reference explanation | Recast as unsupervised reference, not same-supervision competitor |

### 5.3 Downgrade to Background / Appendix / Historical Mechanism Asset

| Old asset | New placement |
|---|---|
| covariance-aware Transformer ensemble | Background or appendix as historical mechanism exploration |
| three-seed ensemble | Appendix / archived method asset |
| raw/diag Mahalanobis scorer | Archived scorer evidence |
| old deployment cost table for Transformer ensemble | Appendix or removed unless needed for historical context |
| older MAE / TailReg / covreg / tokenizer negative lines | Historical negative-route evidence |

### 5.4 Not in the New Main-Core Claim

These claims must not appear as current main claims:

| Claim | Required treatment |
|---|---|
| “Transformer ensemble is the final main method.” | Remove from main claim. |
| “source_rich average performance fully beats original100.” | Reject; replace with role split / hard-holdout wording. |
| “second-environment supports the mainline.” | Reject; write as negative evidence / limitation / external-validity boundary. |
| “unsupervised frontend-f2 flipped the problem.” | Reject; frontend-f2 value is source_rich hard-holdout robustness + auditability under few-shot target alignment. |

---

## 6. Prism Writing Boundaries

### 6.1 Prism Must Not Write

| Forbidden claim | Reason |
|---|---|
| Transformer / source_rich 全面击败 dA | Current evidence does not support a universal win. |
| `source_rich universally beats original100` | Boundary table says original100 wins most holdouts by average `det_mean`. |
| few-shot completely solves open-world IDS | Evidence supports a protocol-specific remedy, not a complete solution. |
| dA and few-shot are fair same-label-information competitors | dA is unsupervised; few-shot uses target positives. |
| 16/32-shot is the full evaluation size | It is only positive training budget for logistic head. |
| collapse is a universal law for all models | Audit officially anchors current dA reference; legacy transformer/tailreg are auxiliary sanity evidence. |
| second-environment supports the positive main conclusion | It is closed as negative evidence / limitation. |

### 6.2 Prism Must Write

| Required statement | Evidence source |
|---|---|
| dA is an `unsupervised reference`. | Few-shot handoff and main table. |
| original100 few-shot is the `official control`. | Mainline map and few-shot handoff. |
| source_rich is `hard-holdout robustness + auditability`. | frontend-f2 hard-holdout assets and boundary table. |
| collapse sanity audit only formally anchors the current dA official reference. | Collapse sanity handoff. |
| legacy transformer / tailreg raw caches are auxiliary sanity evidence only. | Collapse sanity handoff. |
| final OOD eval does not participate in threshold selection. | Few-shot handoff and dataset/split/budget summary. |

---

## 7. Prism Execution Guidance

Prism should not immediately rewrite the whole paper from free-form intuition. Use this staged flow:

1. First rewrite the outline around the nine-section structure in Section 4.
2. Then rewrite title, abstract, and contribution list so that the new paper center appears in the first screen.
3. Then rewrite setup and method using the few-shot target alignment protocol.
4. Then rebuild results tables from the prepared CSV and handoff assets.
5. Then add source_rich case study and auditability as a bounded supplemental contribution.
6. Finally rewrite discussion and limitations to include second-environment negative evidence and source_rich boundary.

If Prism needs to use a claim not listed in this handoff, it must point to a specific asset path. If no asset path exists, the claim should not enter the manuscript.

---

## 8. One-Screen Summary for Prism

| Question | Answer |
|---|---|
| What is the new paper about? | Strict low-OOD-alarm evaluation exposes unsupervised detection collapse; few-shot target alignment restores detection under low false-alarm constraints. |
| What is the main method? | L2 LogisticRegression linear head on frozen representation with 16/32 high-purity attack positives and ID+OOD benign negatives. |
| What is the official control? | original100 few-shot logistic. |
| What is dA? | Unsupervised reference. |
| What is source_rich? | Hard-holdout robustness + auditability asset, not universal winner. |
| What happens to old Transformer ensemble? | Downgrade to historical mechanism/background/appendix asset; remove from current main claim. |
| What happens to second-environment? | Closed negative evidence / limitation / external-validity boundary. |
| What must not leak into threshold selection? | Final OOD eval and attack eval. |

