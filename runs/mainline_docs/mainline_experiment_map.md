# Mainline Experiment Map

Canonical path: `runs/mainline_docs/mainline_experiment_map.md`

> 版本：v3 convergence-first（2026-04-23）
> 用途：作为汇合后的主线总地图，优先呈现当前真实 paper center、证据分层、下一阶段最小实验包，并将旧路线下沉为历史资产/归档。

---

## 0. 文档用途与维护规则

Maintenance rule:
- Keep this as the single living mainline experiment map.
- Update this file continuously as mainline experiments advance.
- Do not create dated copies for the mainline map.
- This v3 map supersedes the old unsupervised-first v2 ordering.
- Historical runs and old planning are preserved below, but archived sections no longer define the current paper center.

What this file should answer first:
- What is the current paper center?
- Which evidence is primary, diagnostic, negative, or archived?
- Which minimal experiments remain necessary under the convergence-first storyline?
- Which old routes are preserved only as historical assets?

---

## 1. 当前项目重定性

### 1.1 Current Paper Center

当前论文中心已经从旧的“stronger OOD + calibration + TailReg / unsupervised mainline”切换为：
- `strict low-OOD-alarm operating region`
- `unsupervised detection collapse`
- `few-shot target-aligned detector`

一句话口径：严格低 OOD 误报部署区间揭示了无监督网络异常检测的目标错配；在 frozen benign representation 上，仅用极少量 high-purity attack positives 的 target-aligned linear head，就能显著恢复低误报区间的检测能力。

### 1.2 四个当前定位

- `original100 few-shot official control` 是主线官方控制组，用来固定 target alignment 这个主要杠杆。
- `source_rich` 的角色经 v7.4 paired verification 后，可狭义写成 `hard-holdout robustness + auditability`，但不是平均性能全面压过 original100 的主英雄。
- `A-line second-environment` 已封口为 `negative evidence / limitation / external-validity boundary`，不再扩跑、不再救线、不进入正向主证据。
- old mainline 的 stronger OOD、calibration、TailReg 资产仍然重要，但现在是背景机制资产与历史证据，不再单独定义当前 paper center。

### 1.3 已退场的旧叙事

当前地图不再支持以下表述：
- “无监督 frontend-f2 已经翻盘。”
- “source_rich_v1 是击败 dA 的唯一原因。”
- “第二数据集正在逐步支持旧主线。”
- “继续修 tokenizer / AE / scorer 是当前主线最优先事项。”
- “TailReg 是当前论文唯一或最高层方法中心。”

---

## 2. 当前论文中心与创新点

### 2.1 立脚点

开放世界 IoT 异常检测的难点不是一般性的 AUC 排名，而是在 stronger benign OOD 条件下，模型必须在严格 low-OOD-alarm operating region 内仍保持 attack detection。传统 unsupervised detector 在这个区间容易出现 detection collapse；few-shot target alignment 用很少的 high-purity attack labels 修正了训练目标与部署目标的不一致。

### 2.2 创新点 1：问题定义重写

把评估核心从“整体 AUC/平均分数更高”重写为：
- fixed 或 guarded low-OOD-alarm operating point 下是否可用；
- final OOD eval 不参与阈值选择；
- ID benign、OOD benign、high-purity attack 的角色必须清楚分离。

### 2.3 创新点 2：机制发现

系统实验说明：
- stronger benign OOD 会放大误报与阈值失配；
- 压低 OOD alarm 后，无监督 score 的 attack detection 可能同时塌陷；
- 这不是单个模型弱，而是 objective 与 deployment target 不一致。

### 2.4 创新点 3：方法杠杆

few-shot target-aligned detector 是当前方法中心：
- positives = stage2 high-purity attack；
- negatives = ID benign + OOD benign；
- model first = L2 `LogisticRegression` with balanced class weights；
- budgets 至少包括 16-shot 与 32-shot；
- 多 positive-sampling seed 输出 mean / min / max；
- operating points 包括 `fixed_id_calib_q99` 与 `guarded_id_calib_and_ood_val_target1pct`。

### 2.5 Source-Rich 的克制定位

`source_rich` 只能在证据支持范围内写成：
- narrow hard-holdout robustness evidence on specific paired holdouts；
- auditability / family-scale-feature explanation layer；
- 对 objective mismatch 的机制诊断资产。

不能写成：
- source-rich 平均性能全面强于 original100；
- frontend 重构本身已经无监督翻盘；
- source-rich 是 few-shot 成功的唯一原因。

---

## 3. 当前证据分层地图

### 3.1 主证据

| Evidence | Current role | Paper use | Boundary |
|---|---|---|---|
| original100 few-shot official control (`runs/original100_fewshot_official_control_2026-04-22/`) | official control | 主文或主附录核心表 | 证明 target alignment 是主要杠杆，不证明 source-rich 胜出 |
| frontend-f2 v7.2 / v7.3 few-shot | target-aligned positive evidence | 主文或主附录 | 必须和 original100 同口径比较 |
| frontend-f2 v7.4 paired holdout fairness | narrow hard-holdout robustness evidence | 主文解释段或主附录 | 只支持特定 hard holdout，更不支持平均性能全面胜出 |
| stronger benign OOD + calibration old mainline | problem/mechanism evidence | 主文背景和机制段 | 不再单独作为 paper center |
| unsupervised baselines under low-OOD-alarm | collapse evidence | 主文机制段 | 不写成“模型差”，写成目标错配 |

### 3.2 机制诊断资产

| Evidence | Use |
|---|---|
| TailReg / calibration / stronger OOD 历史结果 | 解释低误报区间、阈值选择、尾部分布失配 |
| frontend-f2 early tokenizer / AE / temporal / contrast negative lines | 说明“不是没有信号，而是无监督 objective 不对齐” |
| TON threshold-sensitivity + coupling probe | 说明 threshold/operator bug 被排除，模型-表达耦合真实存在 |
| source-rich feature/family/scale analysis | 支撑 auditability 和 hard-holdout case study |
| collapse sanity audit (`runs/collapse_sanity_audit_2026-04-25/`) | 已完成；结论为 `collapse_likely_real_operating_point_effect`，当前 dA official cache 未发现 row-order / index / threshold 泄漏问题，旧 transformer raw cache 仅作 legacy auxiliary evidence |
| Prism collapse sanity handoff (`runs/prism_handoffs/handoff_collapse_sanity_audit_2026-04-25.md`) | paper-facing 段落已生成；用于把 collapse sanity audit 写成保守正文资产 |
| issue02 original normal-vs-attack sanity (`runs/issue02_original_da_normal_attack_sanity_run_2026-05-08/`) | 已完成；clean115 原始 normal-vs-attack 下 dA 很强（AUC `0.9340`, PR-AUC `0.9487`, q99 attack detection `0.8642`, benign false alarm `0.0107`），few-shot LR 在该原始 setting 下波动大。用途是支持“low-OOD collapse 更像 deployment working-point 问题”，不是证明 LR 全面优于 dA |

### 3.3 负结果资产

| Evidence | Use |
|---|---|
| BoT-IoT split-feasibility failure | negative evidence；说明 formal split 支撑不足 |
| TON-IoT fixed operating point failure | negative evidence；说明 current formal protocol 不外推 |
| FT fixed zero-detection on TON | detection collapse / coupling evidence |
| old unsupervised frontend-f2 patches | 负结果资产；支撑 objective mismatch 解释 |

### 3.4 Limitation / Archive

| Asset | Status |
|---|---|
| A-line second-environment | closed limitation / external-validity boundary |
| “source_rich 平均性能全面优于 original100” | archived old tendency, not current claim |
| “无监督 frontend-f2 超越 dA” | archived old route, not current claim |
| old must-do second-dataset rescue line | archived planning, not active |
| broad unsupervised tokenizer / AE patch expansion | archived planning, not active |

---

## 4. 旧实验如何吸收

### 4.1 Stronger OOD / Calibration / TailReg

吸收方式：
- 作为 low-OOD-alarm operating region 的问题定义与机制背景；
- 作为 unsupervised detector 在部署阈值下失配的历史证据；
- 作为论文前半段的 motivation / mechanism，不再作为当前唯一方法主线。

保留边界：
- TailReg 可以作为模型层补充资产，但不应压过 few-shot target alignment。
- calibration 是重要机制杠杆，但当前方法中心不是“只调阈值”。

### 4.2 Original100 Few-Shot Official Control

吸收方式：
- 作为主线官方控制组；
- 必须进入主文或主附录核心表；
- 固定 few-shot target-aligned protocol 的口径和边界。

已固定结果：
- 16-shot fixed: AUC mean/min/max `0.990672 / 0.958007 / 0.999974`, OOD alarm max `0.009500`, det min `0.914182`。
- 16-shot guarded: AUC mean/min/max `0.990672 / 0.958007 / 0.999974`, OOD alarm max `0.009200`, det min `0.914182`。
- 32-shot fixed/guarded: AUC mean/min/max `0.984615 / 0.967632 / 0.999910`, OOD alarm max `0.009800`, det min `0.920727`。
- dA reference remains unsupervised and not in the same label-information setting。

### 4.3 Frontend-F2 v7.2 / v7.3 / v7.4

吸收方式：
- v7.2 / v7.3：作为 few-shot target-aligned positive evidence，并与 original100 official control 同口径比较。
- v7.4：已完成 paired verification，可狭义写为 `source_rich_hard_holdout_robustness_supported`，但边界必须保持很窄：
  - paired integrity 已确认：
    - same holdout specs
    - same label budgets
    - same seed set
    - same threshold rules
    - final OOD eval does not participate in threshold selection
  - `original100` 仍是平均性能控制组，按 `det_mean` 赢 `7/9` holdouts，不能忽略。
  - `source_rich` 的可写价值是：
    - 在特定 hard holdout 上比 original100 更稳；
    - 更适合做 family / scale / feature 级别审计；
    - 不是 universal cross-window winner。
  - 当前最强可写 case：
    - `chrono_late_train_early_eval`, 32-shot, guarded:
      - `source_rich`: `AUC_min=0.9494`, `det_min=0.8549`, `alarm_max=0.0099`, `feasible_rate=1.0`
      - `original100`: `AUC_min=0.7030`, `det_min=0.6824`, `alarm_max=0.0029`, `feasible_rate=1.0`
    - `holdout_bin_2`, 16/32-shot, guarded:
      - `original100` segment-collapse is severe;
      - `source_rich` keeps useful detection, but alarm is only near-target rather than fully stable.
  - paper-facing asset bundle 已生成于：
    - `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/paper_facing_hard_holdout_cases.md`
    - `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_original100_boundary_table.csv`
    - `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_auditability_summary.md`
- early frontend-f2 tokenizer / AE / temporal / contrast lines：作为机制诊断资产和旧路线负结果，不再作为当前 paper center。

### 4.4 Second-Environment

吸收方式：
- BoT-IoT 与 TON-IoT 只写成 limitation / external-validity boundary；
- 不再作为主证据；
- 不继续扩跑、调参或救线；
- 若未来要重新打开，必须新日期、新 protocol、新 run_tag。

---

## 5. 后续最小实验包

当前只保留三类后续实验包。任何新实验必须直接服务这三类之一。

### 5.1 Few-Shot 主发现支持包

目的：证明 target-aligned few-shot 不是 lucky split / lucky seed。

最小内容：
- cross-window / alternate attack segment / hard holdout 验证；
- 16-shot、32-shot、多 seed 的 mean/min/max 表；
- fixed 与 guarded operating points；
- final OOD eval 不参与阈值选择；
- paper-facing operating-point 图和核心表。

### 5.2 Source-Rich 独特价值支持包

目的：证明 source-rich 的合理定位是 hard-holdout robustness + auditability。

最小内容：
- 基于已核验的 v7.4 做 paper-facing hard-holdout case analysis；
- 固定保留 original100 paired control，不允许删掉对照；
- 把 narrow robustness claim 与 average-performance non-win 边界同时写清；
- family / scale / feature 级别 auditability 分析；
- 与 original100 的适用边界图或案例表。
- 当前已落地的 paper-facing 资产包位于 frontend handoff 目录，可直接供论文正文 / 附录引用。

### 5.3 部署意义支持包

目的：证明 few-shot target alignment 不是不可部署的“监督作弊”。

最小内容：
- high-purity attack positives 的标签预算说明；
- 训练成本和推理成本；
- 与 dA / unsupervised baselines 的 low-OOD-alarm operating-region 对照；
- 对“监督当然赢”的审稿攻击给出 label-efficiency + fairness protocol 防御。

当前 paper-facing 写作包：
- `runs/prism_handoffs/handoff_fewshot_target_alignment_2026-04-25.md`
- `runs/prism_handoffs/fewshot_dataset_split_budget_summary_2026-04-25.csv`
- `runs/prism_handoffs/fewshot_paper_main_table_2026-04-25.csv`
- `runs/prism_handoffs/handoff_paper_restructure_from_transformer20_to_fewshot_2026-04-25.md`：已生成；用于 Prism 将旧 Transformer ensemble 稿重构为 few-shot target alignment 新主线，不改变 v3 convergence-first paper center。
- `runs/prism_handoffs/paper_restructure_section_decision_table_2026-04-25.csv`：旧稿章节处理裁决表，供 Prism 重排标题、摘要、方法、结果、讨论与结论。

用途：
- 交给 Prism 写 few-shot target alignment 正文；
- 回答 dataset / split / budget 口径问题；
- 明确 `16-shot` / `32-shot` 是训练 high-purity attack positives 的预算，不是评估集规模；
- 固定 dA 为 unsupervised reference，original100 为 official control，source_rich 为 hard-holdout robustness + auditability 资产。

### 5.4 Next Phase: Base-Detector-Agnostic Guarded Few-Shot Adapter

Status:
- This is a candidate next phase, not a completed experiment.
- It upgrades the narrative from "replace dA with few-shot LR" to "use few-shot target alignment as a guarded deployment adapter on top of base detectors".
- The current paper center remains `strict low-OOD-alarm operating region` + `detection collapse` + `few-shot target alignment`.

2026-05-08 strategy update:
- dA remains a classic lightweight cold-start unsupervised detector.
- Transformer should be treated as a possible modern contextual base detector, but the project still needs evidence retrieval before claiming ordinary-setting strength.
- L2 `LogisticRegression` remains the minimal target-alignment baseline; it is not automatically the final adapter head.
- Candidate names include `Guarded Few-shot Adapter (GFA)`, `Base-Detector-Agnostic Guarded Few-shot Adapter`, and `Guarded Deviation Adapter (GDA)`.

Candidate adapter inputs:
- base representation: `original100` or future Transformer hidden representation;
- base detector score: dA RMSE or Transformer anomaly score;
- few-shot high-purity attack positives;
- ID benign + OOD benign negatives.

Candidate adapter output:
- attack-oriented score;
- evaluated under `guarded_id_calib_and_ood_val_target1pct`;
- final OOD eval and attack eval remain excluded from threshold/model selection.

| item | current_status | evidence_status | role_in_paper | next_action | risk |
|---|---|---|---|---|---|
| dA only | completed reference baseline | strong in original normal-vs-attack issue02 sanity; collapses under guarded low-OOD main protocol | classic cold-start detector and unsupervised reference | keep as reference; do not frame as invalid detector | writing dA as "failed model" would misstate the evidence |
| Transformer only | historical exploratory line | stronger-OOD evidence exists; no formal ordinary normal-vs-attack proof stronger than dA found in this update | possible modern base detector, not current paper center | perform Transformer evidence retrieval before any claim | historical results may be non-comparable or not reproducible |
| LR original100 minimal baseline | completed mainline control | strong guarded few-shot control on primary split; original normal-vs-attack LR is seed-sensitive | minimal target-alignment baseline | keep as baseline for adapter comparisons | confusing minimal baseline with final method |
| dA-assisted adapter | proposed feasibility direction | not yet run under current guarded paired protocol | candidate lifecycle story: dA cold-start plus few-shot adaptation | first run score-alignment inventory, then paired feasibility if aligned | dA score may add no stable value beyond original100 |
| Transformer-assisted adapter | proposed feasibility direction | needs Transformer base evidence and aligned scores/representations | candidate modern-detector adapter | retrieve Transformer ordinary-setting and low-OOD score evidence first | cannot support detector-agnostic framing without clean Transformer evidence |
| detector-agnostic GFA/GDA | proposed next-phase framework | not yet completed; requires at least two base detectors | future method framing candidate, not current claim | define shared adapter protocol after dA/Transformer evidence gates | detector-agnostic claim requires multiple base detectors |
| prototype adapter | future optional head | not run | possible nonlinear target-alignment head | only compare after LR baseline and detector-score adapters are fixed | model-capacity gains may obscure target-alignment contribution |
| cost-sensitive / low-OOD-aware adapter | future optional head | not run | possible low-alarm-aware adapter variant | pre-register a small fixed weighting set; no final-eval tuning | large sweep could become uncontrolled method search |
| second-environment validation | closed limitation under current protocol | BoT-IoT/TON-IoT sealed as negative evidence / boundary | limitation and external-validity boundary | reopen only with new dated same-protocol manifest | forcing dirty external data would weaken credibility |
| modern unsupervised baseline comparison | partial historical evidence | Deep SVDD, FT, other baselines exist mainly as collapse/negative evidence | reviewer attack-surface reduction, not paper center | keep as archived support unless a targeted gap remains | turning into model zoo would dilute the main story |

Issue02 evidence routing:
- Run: `runs/issue02_original_da_normal_attack_sanity_run_2026-05-08/`.
- Data: clean115, `200000` rows, `115` dimensions; benign `121621`, attack `78379`.
- dA original normal-vs-attack: ROC-AUC `0.9340`, PR-AUC `0.9487`, q99 attack detection `0.8642`, benign false alarm `0.0107`.
- few-shot LR original normal-vs-attack is seed-sensitive and should not be written as a dA replacement.
- Recommended use: appendix sanity comparison.
- Non-use: do not put it in the main-text core result, and do not claim LR is generally stronger than dA in the original setting.

Transformer evidence retrieval note:
- Search found clean115 `trans115_min` / `da115_min`, but they are ID-only minimal checks with no attack metrics.
- Search found stronger-OOD Transformer/FT/ensemble evidence, but that is not ordinary closed-set normal-vs-attack evidence.
- Current status: `needs evidence retrieval`.

### 5.5 当前不再推进的实验包

- second-environment rescue / expansion；
- 新一轮无监督 tokenizer / AE patch；
- 大范围 baseline 家族扩张；
- 以 TailReg 或 calibration 重新抢回唯一主线中心；
- 即使 v7.4 已核验，也不能写 source-rich 的稳定平均胜出结论。

---

## 6. 历史路线归档区

以下内容为 v2 旧地图与历史追加内容的原文归档，保留 run 名、裁决、边界和操作书，供追溯与论文附录取材使用。

Archive rule:
- Archived content is evidence inventory, not the active paper-center ordering.
- If archived text conflicts with Sections 1-5, Sections 1-5 are authoritative.
- Do not delete archived evidence unless a separate cleanup task explicitly requests deduplication.

### 一、项目总目标（作者视角）

这篇论文的核心目标已经明确为：在 **original-frontend 100维** 的可信输入链上，研究 stronger OOD（更强分布外）场景下异常检测的**低误报稳健性机制**。因此它不是“换一个 detector 看分数高低”的小模型对比，而是“协议强度 + 阈值机制 + 模型补充修正”的系统问题：先坐实 stronger OOD 的误报放大现象，再证明 calibration（校准）是主要杠杆，最后用 TailReg（尾部正则）给出模型层的定向补充改进。

---

### 二、实验总框架（总表）

| 模块 | 当前状态 | 论文作用 |
|---|---|---|
| 1) 历史链 detector 比较（clean115） | 已完成基础版 | 后端比较与历史对照 |
| 2) stronger OOD 主线现象（frontend100） | 已完成并稳定 | 主结果现象证据 |
| 3) calibration 机制实验 | 已完成并稳定 | 主线机制证据（核心） |
| 4) TailReg 方法实验 | 已完成阶段稳定版 | 模型层补充贡献 |
| 5) 扩展验证（更多 capture/能力约束/效率） | 进行中（已完成 Transformer fixed-vs-dA 自检） | A区完整性与泛化增强 |

---

### 三、当前已完成实验（按“支撑什么主张”整理）

#### A. 动机证据

**1) 已完成实验**
- `runs/ood_probe_stage1_2026-03-21`
- `runs/ood_probe_stage1_stability_2026-03-21`
- `runs/ood_probe_2026-03-21`

**2) 核心结果**
- 在 adapter/映射链路下观察到非常强的 OOD benign 误报（含接近灾难级现象）。

**3) 论文作用**
- 用于说明“开放世界误报失稳值得研究”，即问题发现与研究动机。

**4) 边界说明**
- 该链路存在 schema 映射与输入一致性问题，只能做动机证据，不能当正式主结论。

---

#### B. 输入链纠错证据

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23`（dirty116 -> clean115）
- `runs/kitsune_frontend_stage1_2026-03-22`（原版前端最小接入）

**2) 核心结果**
- 证实 `Mirai_dataset.csv / my_gold_mirai.csv` 的 116 维含索引样首列污染；清洗后得到 clean115。
- 原版前端链成功产出稳定 100维特征缓存（不再依赖 adapter）。

**3) 论文作用**
- 解决“输入空间不一致/污染”这一可信度前提问题，为主线结论提供可辩护输入基础。

**4) 边界说明**
- clean115 与 original-frontend 100 是两条并行输入轨道，不能混写成同一主线结果。

---

#### C. 历史链 detector 比较证据（clean115）

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23/trans115_min`
- `runs/csv_input_clean_stage1_2026-03-23/da115_min`
- 同配置 dirty116 对照：`trans116_dirty_min` / `da116_dirty_min`

**2) 核心结果**
- clean115 与 dirty116 的分数统计显著不同，确认索引列污染会扭曲 detector 行为。
- 在 clean115 下已完成 Transformer 与 dA 的可复现实验入口。

**3) 论文作用**
- 承担“历史链输入纠错后后端比较”的对照角色，支撑方法选择的历史合理性。

**4) 边界说明**
- 不用于 stronger OOD 主结论；该链路不等价于原版前端 100维主线。

---

#### D. stronger OOD 主线证据（frontend100）

**1) 已完成实验**
- 同 capture 分段（较弱 OOD）：`runs/frontend100_ood_stage1_2026-03-23`
- cross-capture stage1（更强 OOD）：`runs/frontend100_crosscapture_stage1_2026-03-25`
- cross-capture 多 seed 稳定：`runs/frontend100_crosscapture_stability_2026-03-25`

**2) 核心结果**
- 同 capture 分段下报警率低（Transformer 0.00610，dA 0.01085）。
- cross-capture 后 fixed 报警显著升高（stage1：Transformer 0.44175，dA 0.12580；多 seed 稳定维持高误报趋势）。

**3) 论文作用**
- 直接支撑“stronger OOD 问题真实存在”，并完成从弱协议到强协议的递进证据链。

**4) 边界说明**
- 当前 strongest 组合主要是 7-6 -> 4-1；跨更多 benign capture 的泛化还需补。

---

#### E. calibration 机制证据（主线核心）

**1) 已完成实验**
- 阈值基线：`runs/frontend100_crosscapture_threshold_2026-03-25`
- 校准扫描：`runs/frontend100_crosscapture_calibration_scan_2026-03-25`
- 关键设置多 seed 稳定：`runs/frontend100_crosscapture_calib_stability_local_2026-03-30`

**2) 核心结果**
- Fixed OOD alarm ratio（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - da：`0.1378 ± 0.0050`
- Calibrated（budget=5000,target=1%）：  
  - transformer：`0.01549 ± 0.00068`  
  - da：`0.01516 ± 0.00003`
- gap：`0.316983 -> 0.000333`，缩小约 `99.9%`。

**3) 论文作用**
- 形成当前最强机制结论：**threshold layer 是主要杠杆**。

**4) 边界说明**
- 该结论成立于“无监督 OOD 校准可用”的设置；预算更小、场景更换时的鲁棒性仍需补。

---

#### F. TailReg 方法证据（阶段性方法贡献）

**1) 已完成实验**
- 方法首轮：`runs/frontend100_tailreg_stage1_2026-03-27`
- 超参扫描：`runs/frontend100_tailreg_hparam_scan_2026-03-28`
- 最优配置多 seed 稳定：`runs/frontend100_tailreg_bestcfg_stability_2026-03-28`

**2) 核心结果**
- 最优配置：`lambda=0.2, k=1.0, warmup=256, ema_alpha=0.01`
- fixed OOD alarm（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - transformer_tailreg：`0.1393 ± 0.0911`  
  - da：`0.1378 ± 0.0050`
- calibrated 后 transformer 与 tailreg 基本重合（约 `0.01549`）。

**3) 论文作用**
- 支撑“模型层可补 fixed-threshold 脆弱性”的阶段性方法贡献。

**4) 边界说明**
- TailReg 不是 calibration 替代方案；当前不支持“全面提升 Transformer”的表述。

---

### 四、当前论文已经“写得动”的结论

#### 可写（阶段性稳定结论）
- stronger OOD（cross-capture）下误报问题真实存在。
- fixed threshold 会显著放大 detector 间误报差距。
- calibration 是当前误报控制的主要杠杆。
- TailReg 主要改善 fixed-threshold 下 Transformer 的尾部敏感性。

#### 不可写（禁止过度主张）
- “Transformer 全面优于 dA”。
- “TailReg 在所有评估条件下都优于 baseline 和 dA”。
- “calibration 已彻底解决开放世界低误报问题”。
- 把 clean115 或 adapter 链结果写成 stronger OOD 主结论。

---

### 五、后续必须完成的实验（优先级）

#### A. 必须做

1) **扩展 benign cross-capture 组合（至少再补 2 组）**  
- 为什么：当前 strongest 结论主要基于 7-6 -> 4-1，外推范围仍窄。  
- 支撑主张：stronger OOD 误报放大是否具有场景普适性。  
- 论文位置：Main Results + Robustness subsection。

2) **补“低误报不以漏检为代价”验证（恶意检测能力约束）**  
- 为什么：只看 benign 误报不足以完成检测器评价闭环。  
- 支撑主张：calibration/TailReg 降误报后仍保持检测能力（TPR/PR-AUC 不明显掉）。  
- 论文位置：Results 主表（误报-检出联合结果）。
- 2026-04-02 进展：已完成 `runs/frontend100_transformer_self_audit_2026-04-02/` 自检，确认 fixed 下 transformer 攻击分数存在更大阈下质量，当前差距更偏向“分布-阈值交互”而非实现口径错误。
- 2026-04-02 进展：已完成 `runs/frontend100_threshold_tradeoff_constrained_2026-04-02/`（score-only 阈值扫描 + detection-constrained 规则）。结论：naive calibration（budget=5000,target=1%）会将三种 detector 检出压到近0；引入 detection-floor 规则后可在约 7%~8% OOD 报警水平恢复约 50% 高纯攻击检出，显示 decision rule 层存在可用 operating region。
- 2026-04-03 进展：已完成 `runs/frontend100_constrained_rule_multiseed_2026-04-03/` 最小必要多 seed 复验（seed=101/202/303，detector=transformer/transformer_tailreg/da，规则=fixed/naive/det50/det60，附 alarm<=5% 弱基线）。结论：naive 在多 seed 下稳定近零检出；detection-floor 可稳定恢复到目标检出层，但 transformer 系列在 constrained 点的 OOD alarm 方差仍偏高，da 在 constrained 区域更稳。
- 2026-04-03 进展：已完成 `runs/frontend100_mae_v1_2026-04-03/`（Transformer-MAE-v1 单seed最小扫描，mask_ratio=0.3/0.4/0.5，比较 transformer/transformer_mae_v1/da，含 fixed+naive+det50）。结论：MAE 在 fixed 下可显著降低 OOD alarm（约 0.446 -> 约 0.071），但 attack detection 明显下降（约 0.634 -> 0.228~0.336）；m0.3 为当前检测保留最佳，MAE 单线尚不足反超 dA，建议下一步转入 MAE+TailReg 并做最小多 seed 复验。
- 2026-04-03 进展：已完成 `runs/frontend100_mae_tailreg_v1_2026-04-03/`（single-seed MAE+TailReg-v1，mask=0.3/0.4，比较 transformer/transformer_tailreg/transformer_mae_v1/transformer_mae_tailreg_v1/da，含 fixed+naive+det50）。结论：MAE+TailReg 在 mask=0.4 下相对 MAE-v1 可小幅修回 fixed detection（+0.0309）且基本保住低 alarm，但 detection 仍明显低于 transformer 与 dA，当前可作为“继续验证候选”而非已完成修复。
- 2026-04-04 进展：已完成 `runs/frontend100_uncertainty_v1_2026-04-04/`（Transformer-Uncertainty-v1，单seed，稳定版 `log_var` + clamp + Gaussian NLL，比较 `error-only / uncertainty-only / combined_nll`，并与 `transformer/da` 同口径对照，含 fixed+naive+det50）。结论：数值稳定性正常（NaN/Inf=0），但 `log_var` 下界触碰 clamp（-8.0）；`combined_nll` 固定阈值下可将 OOD alarm 降至约 0.0747，但 high-purity detection 仅约 0.4439；分离度上 `combined_nll` 略劣于 `error-only`（AUC 约 0.573 vs 0.602），表明 uncertainty v1 当前更像“降误报方向”而非直接提升检出。
- 2026-04-04 进展：已完成 `runs/frontend100_latent_contrastive_v1_2026-04-04/`（Transformer-LatentContrastive-v1，single-seed，margin∈{1,5}、lambda∈{0.1,0.5}，比较 transformer/transformer_tailreg/transformer_latent_contrastive_v1/da，含 fixed+naive+det50，附 latent distance 分析）。结论：fixed 下可见“提检出”趋势（最佳点 detection 最高达约 0.754），但伴随明显 alarm 反弹（最高约 0.55），尚未满足“提检出且不炸误报”；较稳健点（m=5, l=0.5）可将 alarm 压至约 0.094 但 detection 仍低于原始 transformer。说明该线已体现分离塑形潜力，但负样本构造与损失权重仍需继续收敛。
- 2026-04-04 进展：已完成 `runs/frontend100_latent_contrastive_compact_v2_2026-04-04/`（Transformer-LatentContrastive-Compact-v2，single-seed，固定 `m=5, lambda_margin=0.5`，扫描 `lambda_compact∈{0.01,0.05,0.1}`，引入 Cross-window Swap + EMA-detach center compactness + warm-up，比较 transformer/transformer_tailreg/latent_v1_best/latent_compact_v2/da，含 fixed+naive+det50 与 latent spread 分析）。结论：v2 在低 `lambda_compact` 下可进一步压低 fixed alarm（约 0.0747），但 detection 下降到约 0.494；高 `lambda_compact` 可把 detection 拉到约 0.679，但 alarm 反弹至约 0.501。当前尚未实现“比 v1 更优的 detection-alarm 同时改进”，但已明确 compactness 强度与 trade-off 的方向性约束。
- 2026-04-05 进展：已完成 `runs/frontend100_negative_semantics_ablation_2026-04-05/`（latent 主线 synthetic negative semantics ablation，single-seed，固定 `m=5, lambda_margin=0.5`，对 `cross-window swap / local permutation / mild spike` 做单类型与双类型组合消融，比较 transformer/transformer_tailreg/latent_v1_best/latent_compact_v2_lc0.01/da，含 fixed+naive+det50、四类分布图与 OOD-Negative overlap 指标）。结论：negative 语义对 detection-alarm trade-off 影响显著；`swap_only` 为当前最稳 utility 点（低于原始 transformer 的 alarm 但 detection 未超过 v1_best），`swap+spike` 检出最高但 alarm 明显反弹；目前未出现对 v1_best 的严格 fixed 支配配方，说明下一步应在最佳语义配方上做最小多 seed/轻量叠加，而非继续盲扫 compactness。
- 2026-04-05 进展：已完成 `runs/frontend100_negative_recipe_rescoring_2026-04-05/`（关键 latent recipe 严格离线重评分；不训练、不改 checkpoint；比较 RMSE / Latent-L2 / Latent-Cosine / Hybrid-L2 / Hybrid-Cosine，覆盖 fixed+naive+det50，并补 attack_high vs OOD_eval ROC-AUC、分布图与相关性分析）。结论：存在显著 scoring mismatch 迹象；`latent_swap_spike_mix` 在 RMSE 下呈“高检出高报警”，换到 latent/hybrid（当前以 `hybrid_cosine` 最优）后可在保持较高检出的同时明显降低报警，支持下一步以“最佳 recipe + 最佳 score”做最小多 seed 复验。
- 2026-04-05 进展：已完成 `runs/frontend100_latent_compact_v3_smoketest_2026-04-05/` 本地最小自检与 `runs/frontend100_latent_compact_v3_2026-04-05/` 超算协议准备（`compact_v3` 代码路径、`hybrid_cosine` 锁定评估、`lambda_compact={0.01,0.05,0.1,0.5}` 运行定义、`job.slurm`/`upload_bundle.zip`/`upload_manifest.txt`）。当前阻塞点为本 shell 环境对 `school-hpc` 非交互认证未打通，待凭据可用后执行正式 HPC 训练与打包回传。
- 2026-04-05 进展：已切换为本地正式运行 `runs/frontend100_latent_compact_v3_2026-04-05_local_full/`（single-seed，全量 `lambda_compact={0.01,0.05,0.1,0.5}`，`hybrid_cosine` 评估锁定），后台进程已启动，待跑完后回填最终结果与结论。
- 2026-04-05 进展：已完成 `runs/frontend100_latent_compact_v3_2026-04-05_local_live/`（Transformer-LatentContrastive-Compact-v3，single-seed，negative=`latent_swap_spike_mix`，`m=5.0`、`lambda_margin=0.5`，扫描 `lambda_compact={0.01,0.05,0.1,0.5}`，评估锁定 `hybrid_cosine`）。结论：`lc=0.01` 为 v3 最优，但相对 no-compact（latent_swap_spike_mix）在 fixed 点仍呈 `alarm +0.0115 / detection -0.0460`，未形成“降 alarm 且保 detection”的净外移；相对 transformer_tailreg 则表现为“更高 detection 但更高 alarm”。
- 2026-04-05 进展：已完成 `runs/frontend100_score_postprocessing_2026-04-05/`（锁定 `latent_swap_spike_mix` 做强化版离线 score-postprocessing；不训练、不改 checkpoint；在 `hybrid_cosine` 基础上比较 weighted hybrid、`log-transform + z-score`、`MAD` 稳健标准化，并重点检查 pure cosine，统计量严格来自 ID benign eval）。结论：评分器确实是当前主矛盾的一部分；最佳 fixed 点为 `log_weighted_z_rmse0.5_cos1.0`，相对默认 `hybrid_cosine` 将 OOD alarm 从约 `0.3261` 压到 `0.1857`，同时 high-purity detection 从约 `0.8955` 降到 `0.8233`。说明“降 RMSE 权重 + log 化”可明显改善 trade-off，但 pure cosine 虽 alarm 极低（约 `0.0368`）却 detection 明显不足（约 `0.4095`），MAD 版本也未优于 log 版本；当前更像 score-combination 问题而非纯模型崩坏，仍不足直接进入多 seed。
- 2026-04-06 进展：已完成 `runs/frontend100_locked_candidate_multiseed_2026-04-06/`（正式 seed=`101/202/303` 的最小必要多 seed 验证；锁定 recipe=`latent_swap_spike_mix`，比较旧评分 `hybrid_cosine_default` 与候选新评分 `log_weighted_z_rmse0.5_cos1.0`，并与 `transformer / transformer_tailreg / da` 官方口径对照，统一报告 fixed+naive+det50）。结论：新评分在多 seed 下**未稳定优于**同 recipe 旧评分器，fixed 均值仅从 `alarm 0.2220 -> 0.2161` 小幅下降，同时 `detection 0.6558 -> 0.6353` 回落；但相对 `transformer_tailreg`，该 latent 主候选在 fixed 下呈“更高检出、更高报警”，在 det50 下则能以更低 alarm 达到近同等 detection。相对 `da` 仍未进入全面可竞争区间（fixed 下同时更高 alarm、更低 detection），naive calibration 也继续在多 seed 下稳定塌检出。当前证据支持其作为“Transformer 家族的强候选之一”，但**不足以直接锁定为正式最强主候选**。
- 2026-04-06 进展：已完成 `runs/frontend100_mae_latent_v1_2026-04-06/`（Transformer-MAE-LatentContrastive-v1，single-seed，固定 negative=`latent_swap_spike_mix`、`m=5.0`、`lambda_margin=0.5`，扫描 `mask_ratio={0.3,0.4}`，primary score 回退为 `hybrid_cosine_default`，比较 transformer/transformer_tailreg/latent no-compact/mae+latent/da，统一报告 fixed+naive+det50，并附 trade-off、分布与局部 attack 响应图）。结论：融合线未实现预期的“降 alarm 且不明显伤 detection”；`mask=0.4` 为本轮较优点，fixed 下将 OOD alarm 从 no-compact 的约 `0.3261` 压到 `0.1201`，但 high-purity detection 同时从约 `0.8955` 降到 `0.5174`；`mask=0.3` 则同时表现为高报警（约 `0.4475`）与低检出（约 `0.5188`）。相对 `transformer_tailreg`，`mask=0.4` 虽 fixed alarm 更低，但 detection 更差，det50 下也未形成更优 trade-off；相对 `da` 则仅在 fixed alarm 上接近持平，但 detection 仍明显落后。当前证据**不支持**将 MAE+Latent 融合线直接推进为下一轮多 seed 主候选，更像是 MAE mask 机制削弱了 latent separation 与 attack 响应。
- 2026-04-06 进展：已完成 `runs/frontend100_latent_scorer_benchmark_2026-04-06/`（latent scorer benchmark 离线总决赛；不训练、不改 checkpoint；主 checkpoint 锁定 `latent_swap_spike_mix_no_compact`，比较旧单中心 hybrid、全局 single-center latent、双中心方向 `score_dir`、`LedoitWolf/OAS` 马氏距离及轻量 hybrid，统计与阈值严格只来自 ID benign train/calibration，补相关性矩阵与 benign latent 协方差主方向分析）。结论：当前瓶颈**不只是 scorer 粗糙**。旧 best scorer `log_weighted_z_rmse0.5_cos1.0_old` 仍是最佳 fixed 点（约 `alarm 0.1857 / det 0.8233`）；双中心方向 scorer 明显失败（`score_dir_cosine` fixed 仅约 `0.2734 / 0.0963`），说明“攻击原型方向打分”在当前表示上并未成立。`mahalanobis_ledoitwolf` 虽 fixed 下报警过高（约 `0.5843`），但 AUC 最强（约 `0.8991`），并在 det50 点把 OOD alarm 压到约 `0.0516`、同时保持约 `0.5015` detection，且 naive calibration 也不再完全塌到近零检出（约 `0.1175`）。这表明 covariance-aware scorer 有真实信号，但尚不足支持“只换 scorer 就能让当前 latent 线在 fixed 下反超 dA”；若继续推进，更值得押注 covariance-aware 方向，而不是直接进入双中心 prototype 训练线。

3) **在 stronger OOD 上补一个轻量传统 baseline（非重模型）**  
- 为什么：目前主比较集中在 Transformer 与 dA，需要最低限度外部参照。  
- 支撑主张：当前机制结论不是“双模型偶然”。  
- 论文位置：Results 对比段（附表或补充表）。

4) **补效率与代价（训练/推理/校准开销）**  
- 为什么：A区评审会问“效果是否靠高成本换来”。  
- 支撑主张：方案具备工程可行性（尤其校准预算/延迟）。  
- 论文位置：Discussion 或 Deployment Consideration。

---

#### B. 强烈建议做

1) **小预算 calibration 稳定性（多 seed，多组合）**  
- 为什么：当前最佳结果依赖 budget=5000，需评估资源敏感性。  
- 支撑主张：阈值层杠杆在受限预算下是否仍有效。  
- 论文位置：Calibration Analysis 扩展小节。

2) **TailReg 方差收敛与稳定性分析（固定最优附近）**  
- 为什么：TailReg 的 fixed 误报 std 仍明显高于 dA。  
- 支撑主张：TailReg 不仅降均值，还能降波动。  
- 论文位置：TailReg Results/Analysis。

3) **统计显著性/置信区间补充**  
- 为什么：主结论基于多 seed，加入显著性可提高审稿说服力。  
- 支撑主张：gap 收缩与 fixed 改善不是随机波动。  
- 论文位置：Results footnote 或附录统计说明。

---

#### C. 可选增强

1) **更强 OOD 强度梯度（跨更多设备/时段/协议域）**  
- 为什么：进一步放大挑战，验证结论边界。  
- 支撑主张：结论的适用范围与失效边界。  
- 论文位置：Discussion / Limitations。

2) **不确定性或分数校准高级方案（轻量）**  
- 为什么：在“阈值层主导”已成立后，可探索更稳阈值机制。  
- 支撑主张：机制深化，不改变主线框架。  
- 论文位置：Future Work 或附加实验。

3) **可解释性可视化增强（尾部样本画像）**  
- 为什么：帮助解释 TailReg 为什么主要作用于 fixed 场景。  
- 支撑主张：机制可解释性提升。  
- 论文位置：Analysis 图补充。

---

### 六、后续方法改进主线（修 Transformer 路线图）

基于现有证据，后续“修 Transformer”应坚持 **阈值层优先、模型层补充**，而不是回到大模型替换：

1) **目标 1：固定阈值下更低误报均值 + 更低方差**  
- 继续围绕 normal score tail 设计轻量约束（TailReg 家族），重点降低 seed 间波动。

2) **目标 2：小预算校准友好性（calibration efficiency）**  
- 让模型分数分布更“可校准”：在 500~2000 budget 下也能稳定逼近目标报警率。

3) **目标 3：误报-检出联合优化**  
- 任何降误报改动必须同时报告检测能力不塌陷（TPR/PR-AUC 或召回约束）。

4) **目标 4：保持工程成本可控**  
- 不引入重模型；优先维持与当前流程兼容的轻量正则/后处理改动。

建议的方法线表述：  
**“先用 calibration 解决主矛盾，再用 TailReg 类模型约束降低 fixed-threshold 脆弱性与波动，并验证在低预算校准与检测能力约束下仍成立。”**

---

### 七、论文-实验映射表

| 论文部分 | 对应实验模块 | 当前状态 |
|---|---|---|
| Introduction（stronger OOD 动机） | 动机证据 + stronger OOD 递进（A+D） | 已可写 |
| Data/Input Reliability | 输入链纠错（B） | 已可写 |
| Main Results（stronger OOD） | D（同capture->cross-capture->多seed） | 已可写 |
| Calibration Analysis | E（threshold baseline + scan + local stability） | 已可写（核心） |
| TailReg 方法与结果 | F（stage1 + hparam + bestcfg stability） | 已可写（阶段性） |
| Discussion / Limitations | 边界与待补实验（A/C/D/E/F 边界 + 五） | 已可写，待增强 |

---

### 八、作者执行建议（下一步最稳推进顺序）

建议按下面顺序推进，避免再次“实验散点化”：

1) **先补“必须做”中的 1 + 2**（更多 cross-capture + 检测能力约束）。  
2) 同步补 **必须做 4**（效率/代价），确保主线结果可工程化表达。  
3) 再做 **强烈建议 1**（小预算 calibration 稳定性），强化“阈值层主杠杆”的适用范围。  
4) 最后再决定是否推进 **强烈建议 2/可选增强**，用于冲击更高说服力版本。  

以后每个新实验立项前先回答三件事：  
- 它属于本地图哪一模块？  
- 它要支撑哪一句论文主张？  
- 它完成后进入正文哪一节？  

如果这三点回答不清，就先不做，避免新增“无法入稿的实验”。

- `frontend100_covariance_regularized_v1_2026-04-07`: Transformer-CovarianceRegularized-v1 single-seed minimal experiment; two-sided variance hinge + off-diagonal decorrelation, old-best and Mahalanobis scoring. Path: `runs/frontend100_covariance_regularized_v1_2026-04-07/`.
- `frontend100_mahalanobis_rescue_2026-04-07`: Mahalanobis epsilon-floor rescue offline rescoring; no retraining. Path: `runs/frontend100_mahalanobis_rescue_2026-04-07/`.

- `frontend100_covariance_regularized_v2_2026-04-07`: Transformer-CovarianceRegularized-v2 single-seed minimal experiment; EMA covariance, Cholesky diagonal-loading score proxy, tail-aligned loss. Path: `runs/frontend100_covariance_regularized_v2_2026-04-07/`.

- `frontend100_diagload_sweep_no_compact_2026-04-08`: Offline no-compact latent Mahalanobis diagonal-loading sweep; no retraining. Path: `runs/frontend100_diagload_sweep_no_compact_2026-04-08/`.

- `frontend100_diagload_overlap_analysis_2026-04-08`: Offline lost-attack vs false-alarm overlap analysis for no-compact latent diagload; no retraining. Path: `runs/frontend100_diagload_overlap_analysis_2026-04-08/`.

- `frontend100_diagload_gate_rescue_2026-04-08`: Offline two-threshold diagload+raw-Mahalanobis gate rescue for no-compact latent; no retraining. Path: `runs/frontend100_diagload_gate_rescue_2026-04-08/`.
- `research_log/a_tier_experiment_progress_log.md`: Living paper-level experiment logic log for A-tier direction; maintained across future experiments. Path: `runs/research_log/a_tier_experiment_progress_log.md`.
- `frontend100_diagload_gate_multiseed_2026-04-08`: Multi-seed offline validation of no-compact latent covariance gate (`diag_f0.5 q99 OR raw Mahalanobis high-tail`); no retraining. Path: `runs/frontend100_diagload_gate_multiseed_2026-04-08/`.
- `frontend100_latent_tail_seed_diagnostics_2026-04-08`: Offline latent covariance-tail seed diagnostics for no-compact latent gate instability; no retraining. Path: `runs/frontend100_latent_tail_seed_diagnostics_2026-04-08/`.
- `frontend100_conditional_gate_multiseed_2026-04-08`: Conditional covariance gate multi-seed offline validation (`diag_q99 OR (raw_q AND diag_guard_q)`); no retraining. Path: `runs/frontend100_conditional_gate_multiseed_2026-04-08/`.
- `frontend100_external_baselines_2026-04-08`: Minimal external baselines on original-frontend 100D stronger OOD (`IsolationForest`, `OneClassSVM`, `LOF`, RF mixed-attack upper-bound); path: `runs/frontend100_external_baselines_2026-04-08/`.
- `frontend100_temporal_frontend_v1_2026-04-08`: Transformer TemporalFrontend-v1 single-seed minimal experiment on stacked original 100D windows; path: `runs/frontend100_temporal_frontend_v1_2026-04-08/`.
- `frontend100_latent_seed_ensemble_2026-04-08`: Offline seed-ensemble test for latent covariance tail instability; no retraining; uses formal seeds 101/202/303 cached latents. Path: `runs/frontend100_latent_seed_ensemble_2026-04-08/`.
- `frontend100_latent_seed_ensemble_idq_sweep_2026-04-08`: ID-only fixed quantile sweep for latent seed-ensemble scalar scores; no retraining. Path: `runs/frontend100_latent_seed_ensemble_idq_sweep_2026-04-08/`.
- `frontend100_recurrent_deep_baselines_2026-04-08`: Multi-seed LSTM-AE/GRU-AE deep sequence baselines on stacked original 100D windows; path: `runs/frontend100_recurrent_deep_baselines_2026-04-08/`.
- `frontend100_latent_ensemble_cost_ablation_2026-04-08`: 1/2/3-seed ensemble cost-effect ablation for covariance gate; no retraining. Path: `runs/frontend100_latent_ensemble_cost_ablation_2026-04-08/`.
- `frontend100_final_candidate_audit_2026-04-08`: Final candidate audit for covariance-aware Transformer ensemble vs dA/recurrent/external baselines; includes main table, cost table, score distributions. Path: `runs/frontend100_final_candidate_audit_2026-04-08/`.
- `paper_handoffs/2026-04-08/a_tier_paper_readiness_handoff_2026-04-08.md`: paper-readiness consolidation of main candidate, supplement-worthy results, overclaim boundaries, figure/table checklist.

- `prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08`: Prism paper revision pack based on current draft PDF and final experimental evidence; includes Prism prompt, copied draft PDF, main tables, figures, evidence summaries, and zip bundle. Path: `runs/prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08/`.

- rontend100_deep_svdd_baseline_2026-04-09: Multi-seed Deep SVDD baseline on original-frontend 100D stronger OOD; ID-benign-only training with AE pretrain and center-distance scoring. Path: 
uns/frontend100_deep_svdd_baseline_2026-04-09/.
- `frontend100_additional_ood_setting_smoketest_2026-04-09_b`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_b/`.
- `frontend100_additional_ood_setting_smoketest_2026-04-09_c`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_c/`.
- `frontend100_runtime_benchmark_smoketest_2026-04-09_b`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/frontend100_runtime_benchmark_smoketest_2026-04-09_b/`.
- `frontend100_runtime_benchmark_2026-04-09`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/frontend100_runtime_benchmark_2026-04-09/`.

- `paper_handoffs/2026-04-09/paper_asset_manifest_2026-04-09.md`: Frozen main/supplement paper asset manifest after runtime and Deep SVDD updates; use this file to choose paper figures/tables without re-reading raw runs.
- `paper_handoffs/2026-04-09/paper_asset_manifest_2026-04-09.csv`: Structured asset inventory for main paper and supplement.
- `paper_handoffs/2026-04-09/PRISM_UPDATE_PROMPT_2026-04-09.md`: Direct Prism instruction for updating the draft using the latest frozen evidence.

---

### 九、外部改进建议分流（Gemini 报告处理原则）

来源：
- `D:\study\paper\anomaly_detection\paper04\论文实验改进与提升建议-gemini报告.pdf`

总原则：
- 该报告可作为“长期升级蓝图”，不能直接当作“当前论文全部待办清单”。
- 当前论文已经接近收口，后续只吸收那些**能显著增强现有主线可信度、但不会改写问题定义**的建议。
- 任何新实验若会把论文从“stronger OOD + covariance-aware operating region”改写成“多数据集/多模态/对抗鲁棒/图模型大综述”，则默认不进入当前主线。

#### A. 当前论文必须吸收的部分

1) **问题驱动而非唯指标驱动**
- 继续把主线写成：stronger OOD 暴露 benign OOD false alarm 瓶颈；Transformer 的问题是 latent covariance tail instability；最终 remedy 是 covariance-aware ensemble operating region。

2) **统计防御与部署防御**
- 继续补强 paired delta、seed-level scatter / CI、runtime/cost caveat。
- 所有 threshold 与 quantile 必须继续强调：只来自 ID benign，不使用 OOD/attack。

3) **baseline 完整性**
- Gemini 报告强调 baseline 现代性，这一点方向正确。
- 当前论文已用 `IF / OCSVM / LOF / LSTM-AE / GRU-AE / Deep SVDD / RF upper-bound` 基本补到足够水平；除非出现明显缺口，不再无边界扩 baseline 家族。

#### B. 可选补强，但必须服从主线

1) **额外 OOD / cross-capture setting**
- 只有在它能增强当前主线时才进入正文。
- 若结果只会削弱主结论，则保留为内部诊断或 supplement 备选，不强行写进主文。

2) **单个现代 deep anomaly baseline**
- 仅在发现审稿风险仍集中于“baseline 太旧”时再补一个同口径、低工程风险的现代 baseline。
- 当前已有 `Deep SVDD`，因此这项暂不升级为必须做。

#### C. 明确放入 Future Work，不进入当前论文主线

1) **多公开数据集全面迁移**
- 如 `BoT-IoT / TON-IoT / UNSW-NB15 / DataSense` 等。
- 这类工作量大，且会把当前论文从“固定 stronger OOD 设定下的机制论文”改成“新 benchmark / 大型泛化论文”。

2) **多模态 / foundation model / raw packet 级输入**
- 如原始流量、多模态融合、foundation model 方向。
- 这是下一阶段课题，不属于当前 paper 的必要收口内容。

3) **Mamba / FT-Transformer / GNN / 联邦框架 / 大型现代系统对照**
- 这类对照会大幅扩张工程面和问题边界，当前论文不吸收。

4) **对抗鲁棒性评测（FGSM/PGD/投毒/黑盒注入）**
- 这是一条新的安全问题线。
- 除非论文主问题改成“adaptive adversary robustness”，否则不进入当前主线。

5) **因果解释 / SHAP / root-cause attribution**
- 有价值，但属于下一篇或扩展工作。
- 当前论文主问题仍是 stricter evaluation + covariance-tail failure analysis + remedy。

#### D. 执行规则

以后若参考外部报告新增实验，先回答三件事：
- 它是否直接增强当前主主张？
- 它是否会改变当前论文的问题定义？
- 它是否会显著拖慢收口节奏？

若答案分别不是：
- **是 / 否 / 否**  
则默认不进入当前论文主线。

---

### 十、阶段重定性（2026-04-12）

#### A. 当前项目不再按“收口稿”理解

截至 2026-04-12，这个项目应被正式重定性为：

- **Phase 1 已完成**：我们已经完成问题定义、病理定位、主候选筛选、外部基线补充与一轮部署侧诊断。
- **当前进入 A 区增强阶段**：目标不再是“尽快把现稿修到能投”，而是把这条线扩成一篇真正具备顶级安全论文说服力的系统工作。

#### B. Phase 1 已经完成的核心资产

1. **问题定义已经成立**
- stronger benign OOD 下，fixed / ID-only operating region 会暴露出真实的 benign false alarm 瓶颈。
- 这不是单纯“谁的 AUC 更高”的问题，而是“在部署阈值下谁还能稳定工作”的问题。

2. **病理定位已经成立**
- Transformer 主问题不是完全没学到攻击分离，而是 **latent covariance tail instability**。
- covariance-aware scorer / ensemble / diagload 之所以有效，是因为它抓到了这部分几何病灶。

3. **主线证据已经成形**
- original-frontend 100D stronger OOD 主线已跑通。
- dA、TailReg、latent scorer benchmark、runtime/cost、recurrent deep baseline、Deep SVDD baseline 已形成一组可写入论文的正反证据。

4. **负结果资产已经成形**
- MAE、prototype、covreg v1/v2、离线 rescoring 补救、distillation v1 都是可用的失败诊断材料，不再视作“废实验”。

#### C. 当前距离 A 区仍缺的四个硬缺口

1. **更现代、更有代表性的 baseline 还不够完整**
2. **第二数据集 / 第二设置的跨环境自证还不够**
3. **adaptive adversary / adversarial robustness 评估缺失**
4. **deployability 闭环仍未真正完成，单模型替代 ensemble 尚未成立**

---

### 十一、2026-04-09 至 2026-04-11 新证据裁决

#### A. Deep SVDD baseline：现代 deep one-class 并不能自动解决 fixed 问题

对应运行：
- `runs/frontend100_deep_svdd_baseline_2026-04-09/`

结论：
- fixed q99 下，Deep SVDD 达到 `alarm=0.7034, det=0.9459`。
- 它证明“现代深度 one-class 模型可以把 detection 顶得很高，但在 stronger benign OOD 下 fixed false alarm 会严重失控”。
- 这条结果应保留在论文与地图中，作为“现代深度模型同样会在 fixed 部署区间翻车”的强证据。

裁决：
- **保留为关键外部 baseline 证据，不发展为主线方法。**

#### B. Ensemble Distillation v1：bulk score imitation 不足以复制 teacher 的 fixed 行为

对应运行：
- `runs/frontend100_ensemble_distillation_v1_2026-04-11/`

结论：
- teacher `q99`: `alarm=0.2307, det=0.9202`
- single-seed gate `q99`: `alarm=0.1129, det=0.7731`
- distilled head `q99`: `alarm=0.1064, det=0.4510`
- teacher-student Pearson 相关性虽高，但 fixed 检出明显崩塌。

解释：
- v1 学到了 bulk score 结构，但没有学到 teacher 在 benign tail / attack tail 上的关键 operating-point 行为。

裁决：
- **Distillation v1 不能晋升主候选。**
- 若继续此线，只能进入 **tail-aware distillation v2**，不能再做普通回归式蒸馏。

---

### 十二、A 区增强阶段总原则

#### A. 研究目标

后续实验不再服务“把当前论文补到差不多”，而是服务下面这件事：

- 把当前 stronger OOD + covariance-aware operating region 工作，升级为一篇兼具
  - **系统安全问题定义**
  - **更强实验完整性**
  - **对抗与部署视角**
  - **可被顶会审稿人正面评价的主创新闭环**
  的 A 区候选论文。

#### B. 顶级论文参照方式

以后参考顶级论文，不是机械模仿模型名，而是看它们在四个维度上如何建立说服力：

1. **问题是否真是安全问题，而不是单纯刷指标**
2. **评估是否覆盖真实部署痛点**
3. **是否考虑 adaptive adversary**
4. **是否有清楚的系统代价与边界说明**

#### C. 立项前强制三问

每个新实验立项前必须先回答：

1. 它补的是哪一个 A 区硬缺口？
2. 它支持的是哪一句最终论文主张？
3. 它失败后是否也能形成可写的负结果？

三问答不清，就先不做。

---

### 十三、Stop-Doing List（立即生效）

以下方向从现在起默认停止，不再作为主线优先级：

1. **停止继续开 MAE / prototype / compactness / covreg 新支线**
- 除非未来明确作为第二篇论文，否则不再投入主线算力。

2. **停止继续扫零散 scorer 小超参**
- 纯 scorer 微调已经不再是主矛盾。

3. **停止把“单模型翻盘审美”当成主目标**
- 单模型只在一个前提下继续：它能解决 deployability 闭环。

4. **停止为了“看起来像 A 区”而无边界扩 baseline**
- baseline 必须服务审稿风险，不是越多越好。

5. **停止把论文润色动作当成实验推进**
- 后续地图优先记录“增加硬实力”的实验，不记录纯文字修订。

---

### 十四、Tier 1：必须完成的实验包

这一层不做完，不讨论 A 区 ready。

#### A. baseline 补强包

目标：
- 用少量但真正有代表性的现代 baseline，封住“只在打旧模型”的审稿攻击。

最小方案：
1. **保留 dA**
- 作为高部署性经典 reference baseline。

2. **保留 Deep SVDD**
- 作为现代 deep one-class reference baseline。

3. **补一个现代 tabular/feature transformer 类 baseline**
- 优先：FT-Transformer 路线或同类低工程风险强 baseline。
- 原因：当前输入是 100D network statistics，这类 baseline 最对口。

4. **如工程可控，再补一个现代 SSL/novelty baseline**
- 仅在它能同协议复现且不会拖死项目时进入。

成功标准：
- 形成一张“dA / Deep SVDD / modern tabular baseline / 当前主系统”的统一比较表。
- 所有模型统一使用同一 stronger OOD 协议与同一 fixed 口径。

#### B. 第二数据集 / 第二环境自证包

目标：
- 证明当前主结论不是单一 100D 前端设置的偶然产物。

优先级：
1. **首选 BoT-IoT**
- 更贴近 IoT botnet 与网络流量异常检测，适合做最小迁移验证。

2. **备选 TON-IoT**
- 异构性更强，但工程成本也更高。

执行原则：
- 第一轮不复制所有主线实验。
- 只跑最小验证包：`dA + 当前 strongest candidate + 一个现代 baseline`。

成功标准：
- 趋势一致即可，不要求所有数值与主数据集完全对齐。
- 只要再次观察到 stronger benign OOD 下 fixed false alarm 的关键矛盾，就足以成立“跨环境复现”。

#### C. 对抗鲁棒性评估包

目标：
- 把系统从“自然漂移评估”提升到“面对 adaptive adversary 的安全评估”。

最小方案：
1. **白盒 FGSM**
2. **白盒 PGD**
3. **黑盒受限扰动 / padding-style 规避**

统一要求：
- 扰动必须施加在当前可操作的 feature space 上。
- 扰动预算、特征合法性、扰动方向必须显式记录。
- 必须同时报告 detection 下降与 false alarm 变化。

成功标准：
- 至少形成一组扰动强度曲线，比较
  - dA
  - single-seed Transformer
  - covariance-aware ensemble
- 若 ensemble 明显更稳，这将是 A 区级别的重要加分项。

#### D. deployability / cost 闭环包

目标：
- 回答“你的 strongest system 真实能不能落地”。

必须比较：
1. dA
2. single-seed Transformer
3. 3-seed covariance-aware ensemble
4. 若后续成功，再加 distilled single model

指标：
- 参数量
- CPU latency
- throughput
- memory footprint
- training cost

成功标准：
- 形成一张正式 deployment table。
- 若 ensemble 是最终 strongest candidate，也要能证明它的代价是可解释、可接受的。

---

### 十五、Tier 2：主创新收口线

当前只保留一条方法主线：

#### Tail-aware Ensemble Distillation v2

为什么是它：
- 现在 strongest system 依赖 3-seed ensemble。
- deployability 的核心矛盾不是“teacher 不强”，而是“单模型学不会 teacher 的 fixed tail 行为”。
- distillation v1 已经说明普通 bulk regression 不够。

v2 的唯一正确方向：
1. **benign high-tail weighting**
2. **synthetic negative / attack high-score weighting**
3. **pairwise ranking or margin alignment**
4. **operating-point imitation，而不是只回归平均分数**

成功标准：
- 单模型 fixed 区间进入 dA 竞争区，或明显接近 teacher 的 q995 工作区间。
- 至少满足下面之一：
  - `alarm <= 0.14` 且 `det >= 0.80`
  - 或在 alarm 不恶化的前提下，显著缩小 single-seed 与 teacher 的 fixed gap

止损标准：
- 若两周内仍然只能学到 bulk correlation，而 fixed detection 继续明显塌陷，则停止这一线。
- 停止后把 v1/v2 共同写成“为什么 ensemble 不易被廉价压缩”的部署讨论与负结果资产。

---

### 十六、Tier 3：未来高风险高收益探索

这些方向有价值，但不进入当前第一优先级：

1. hyperspherical / unit-sphere representation
2. information bottleneck / input bottleneck
3. orthogonal subspace disentanglement
4. root-cause attribution / causal explanation
5. multimodal / raw packet / foundation-style modeling

执行原则：
- 只有在 Tier 1 基本完成、Tier 2 明确止损或完成后，才允许重启。

---

### 十七、后续执行顺序（2026-04-12 起生效）

建议固定按下面顺序推进：

1. **baseline 补强包**
2. **第二数据集最小自证包**
3. **对抗鲁棒性评估包**
4. **deployability / cost 闭环包**
5. **tail-aware distillation v2**

原因：
- 前四项决定论文是否具备 A 区合法性。
- distillation v2 决定论文是否具备更漂亮的部署闭环。
- 如果前四项不做完，单做一个更优雅模型也不足以扭转整体说服力。

---

### 十八、Tier 1 执行设计（2026-04-12 版）

#### A. baseline 补强包：只补“现代且低工程风险”的强参考

##### 设计原则
- 不追逐大而全的 2025-2026 模型清单。
- 只补能够直接回应“你是不是只在打旧 baseline”的模型。
- 新 baseline 必须能沿用当前 `ID benign fit -> fixed / calibrated / constrained` 评估协议。

##### 具体配置
1. **FT-Transformer（主补强 baseline）**
- 定位：现代 tabular deep baseline。
- 理由：当前输入本质是 `100D network statistics`，FT-Transformer 与当前数据形态最匹配。
- 角色：证明在更现代的 tabular deep baseline 下，stronger OOD fixed 问题仍然真实存在。

2. **RTDL-ResNet / tabular ResNet（备选或配对 baseline）**
- 定位：与 FT-Transformer 同论文体系的强 MLP-like baseline。
- 理由：如果只补 FT-Transformer，审稿人仍可能认为“你在拿一个 Transformer 打另一个 Transformer”。
- 角色：提供一个非注意力、但同样现代且强的 tabular deep 参考。

3. **保留当前已有 baseline，不再扩大家族**
- `dA`
- `Deep SVDD`
- `IF / OCSVM / LOF`
- `LSTM-AE / GRU-AE`
- `RF upper-bound`

##### 执行顺序
1. 先补 `FT-Transformer`
2. 若复现稳定，再补 `RTDL-ResNet`
3. 若 FT 已足够回应 baseline 风险，则 ResNet 可降为可选

##### 产物要求
- `frontend100_modern_tabular_baselines_<date>/`
- 统一主表：`fixed / naive calibrated / det50 constrained`
- 统一成本表：参数量、训练时长、CPU 推理时延
- 统一 summary：只回答“现代 baseline 是否真正威胁当前主线”

##### 成功判据
- 即使现代 tabular baseline 比老浅层模型更强，也不能轻易同时做到：
  - `低 fixed alarm`
  - `高 high-purity detection`
- 只要它们没有压过当前主系统，就足以显著降低 baseline 风险。

#### B. 第二数据集 / 第二环境自证包：先做最小可复现，不做大迁移

##### 设计原则
- 目标是“趋势复现”，不是“完全复制当前主线的所有细节”。
- 这一步是外部自证，不是重建另一篇论文。
- 必须明确区分：
  - **主数据集主结论**
  - **外部公开数据集趋势验证**

##### 数据集优先级
1. **首选 BoT-IoT 5% flow CSV**
- 理由：官方提供 5% 子集，工程成本相对可控。
- 适合先验证“公开 IoT 数据下也会出现 benign OOD / fixed operating-point tension”。

2. **备选 TON-IoT network subset**
- 理由：异构性更强，更接近“更广泛的 IoT/IIoT 现实”。
- 风险：工程面更大，正常流量划分与协议重建更复杂。

##### 第二数据集上的问题定义
- 不强求复刻 `original-frontend 100D`
- 明确改写为：
  - **在公开 IoT flow benchmark 上，构造 analogous ID-train / OOD-benign / attack split，检验 fixed-threshold 部署张力是否复现**

##### 最小实验对象
1. `dA`
2. `current strongest candidate`（按可迁移实现决定是 single-seed covariance gate 还是 ensemble 版本）
3. `FT-Transformer`（若已完成）

##### 成功判据
- 只要再次观察到：
  - benign OOD 会显著放大 fixed false alarm
  - 协方差感知 / operating-region 方案相比 naive deep baseline 更稳
- 就算完成“外部趋势自证”。

##### 2026-04-17 进展
- 已完成 `runs/second_environment_botiot_feasibility_2026-04-17/` 本地 feasibility 节点，新增 `repo/ood/second_environment_feasibility.py` 用于 `BoT-IoT first` 入口核查。
- 当前结论不是模型或协议阻塞，而是**数据入口阻塞**：
  - `BoT-IoT` 官方项目页可访问，但官方 SharePoint 数据链接在当前环境下会落入 Microsoft 登录流程，不能直接当作无凭据自动下载源；
  - 本机 `D:\study` 下没有现成 `BoT-IoT` 本地副本；
  - 本机也没有 `TON-IoT` 本地副本，因此 fallback 目前同样不能立即开 smoke。
- 这一步的意义是把第二环境主线的真实起点固定下来：先拿到本地数据副本，再做最小 smoke，而不是在没有数据的情况下空转训练脚本或提前占用 HPC。

##### 2026-04-20 进展
- 已确认本地 `BoT-IoT 5%` 数据落地于 `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%`。
- 已完成新一轮 feasibility：`runs/second_environment_botiot_feasibility_2026-04-20/`，结论从“数据缺失”更新为 `bot_iot_local_ready_for_smoke`。
- 已完成第一轮本地 second-environment smoke：`runs/second_environment_botiot_smoke_2026-04-20/`，并新增 `repo/ood/second_environment_botiot_smoke.py`。
- 当前 smoke 采用 `BoT-IoT` 10-best 训练/测试切分，numeric-only 快速评估，固定三类策略（`fixed_id_q99` / `naive_calibrated_budget500_target1pct` / `det_floor_50pct_min_alarm`）。
- 关键烟雾测试规模：
  - `id_benign_train=370`
  - `ood_benign_test=107`
  - `attack_test=100000`（本地 smoke 上限）
  - `feature_count=11`
- 该节点定位是“可运行性里程碑”，不是正式外部自证结论；主要风险是 benign 样本规模偏小，后续必须继续收敛成可辩护的正式 split 与正式对象对比包。
- 已完成 split 收敛判定节点：`runs/second_environment_botiot_split_gate_2026-04-20/`，新增 `repo/ood/second_environment_botiot_split_gate.py`。
- split gate 结论：
  - `BoT-IoT 5%` 在当前标签定义下 benign 总量仅 `477`（10-best train/test 为 `370/107`）；
  - 所有候选 split 都无法满足主线固定要求 `naive_calibrated_budget5000`（即 OOD benign 至少 `5000`）；
  - 因此 BoT-IoT 不能作为当前主线“正式第二环境闭环”，只能作为约束/负结果证据。
- 据此，第二环境正式包应按既定规则切换到 `TON-IoT` fallback 路线。
- 2026-04-20 fallback intake 进展：
  - 已新增 `repo/ood/second_environment_toniot_intake.py` 并执行 `runs/second_environment_toniot_intake_2026-04-20/`；
  - 对 `D:\study\paper\anomaly_detection\paper04\worktrees\data` 的扫描结果显示仅有 BoT-IoT 5%相关文件，TON-like candidate 数为 `0`；
  - 当前 verdict 为 `blocked_missing_toniot_files`，因此 TON 正式路线尚未进入 smoke 阶段。
- 2026-04-20 fallback intake 更新：
  - 已定位 TON 子目录 `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset` 并重跑 intake（`runs/second_environment_toniot_intake_2026-04-20_b/`）；
  - 新 verdict 为 `toniot_intake_ready_for_smoke`，fallback 数据入口已打通。
- 已完成首个 TON 本地 smoke 节点：`runs/second_environment_toniot_smoke_2026-04-20/`，新增 `repo/ood/second_environment_toniot_smoke.py`。
- smoke 设置（fallback readiness 口径）：
  - 文件：`train_test_network.csv`
  - 标签：`label`（`0=normal`, `1=attack`）
  - split：ID benign `30000` / OOD benign `20000` / attack `100000`
  - policy：`fixed_id_q99`、`naive_calibrated_budget5000_target1pct`、`det_floor_50pct_min_alarm`
  - baseline：`IsolationForest`、`OneClassSVM`
- 当前 smoke 结果用于“fallback 跑通”而非正式结论；该 split 上 baseline 分离度偏弱（AUC < 0.5），后续正式包需进一步收敛 split/feature 设定并跑主线必选对象（`dA + strongest candidate + FT`）。
- 已完成 TON 正式前 precheck 节点：`runs/second_environment_toniot_precheck_2026-04-20/`，新增 `repo/ood/second_environment_toniot_precheck.py`。
- precheck 固化了 `split_manifest.json`（ID=30000 / OOD=20000 / attack=100000）并执行 score polarity gate。
- polarity gate 结论：
  - `isolation_forest` 采用 `raw_decision` 时 AUC `0.752998`（另一方向 `0.247002`）；
  - `oneclass_svm` 采用 `raw_decision` 时 AUC `0.816051`（另一方向 `0.183949`）；
  - 先前 smoke 的低 AUC 主要来自方向性口径错误，而非标签定义反转。
- 当前节点结论为 `polarity_checked_ready_for_formal_object_runs`，下一步可进入主线必选对象在 TON fallback 上的同口径正式运行准备。
- 已完成 TON 主线对象包本地预跑：`runs/second_environment_toniot_object_prerun_2026-04-20_b/`，新增 `repo/ood/second_environment_toniot_object_prerun.py`。
- 该节点在统一脚本下跑通了主线必选对象：
  - `dA`
  - `strongest_candidate_transformer_covreg_v2_seed101`
  - `ft_transformer_ae`
- 口径固定：读取 precheck `split_manifest.json`，执行同一 policy family（`fixed_id_q99` / `naive_calibrated_budget5000_target1pct` / `det_floor_50pct_min_alarm`），并做统一 polarity gate。
- 本地预跑规模（用于快速可比和稳定性检查）：
  - `ID train=8000`、`ID eval=4000`、`OOD eval=8000`、`attack eval=12000`。
- 当前结果说明：
  - 对象包可运行性已打通，但 fixed/naive operating point 下总体信号偏弱；
  - `strongest_candidate` 在本地预跑中出现一次 `NaN/Inf` execute-path 提示，需先做稳定性修复再考虑正式 HPC 提交。
- 2026-04-21 工程/口径排查进展：
  - 已升级 `repo/ood/second_environment_toniot_object_prerun.py`，新增非有限值计数、分数落盘与有限值硬校验；
  - 新增显式 gate 脚本 `repo/ood/second_environment_toniot_engineering_gate.py`；
  - 已完成工程 smoke：`runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/`；
  - gate 结论为 `engineering_gate_pass`，并生成：
    - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/summary.md`
    - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/engineering_gate_report.json`
  - 本轮排查结论：当前主要矛盾已从“工程/口径不确定”收敛为“方法在 second environment 下的性能问题”。
- 2026-04-21 同规模稳定复跑进展：
  - 已完成：`runs/second_environment_toniot_object_prerun_2026-04-21_stability/`；
  - 已执行 gate：`runs/second_environment_toniot_object_prerun_2026-04-21_stability/engineering_gate/`，结论 `engineering_gate_pass`；
  - 同规模对比 `..._2026-04-20_b` 显示：
    - `dA` 三策略指标完全复现（稳定锚点成立）；
    - `strongest_candidate` fixed 点仍弱（`attack_det=0.0033`）；
    - `ft_transformer_ae` fixed 点仍为 `attack_det=0.0000`；
    - `ft_transformer_ae` naive detection 有回升（`0.1260`），但 `id_alarm=0.3953`，不可作为可部署改进。
  - 当前可判定：TON second-environment 的主要问题是方法性能而非工程口径；在 fixed low-alarm operating point 下，主线对象尚未形成可辩护外部泛化优势。
- 2026-04-21 阈值敏感性与耦合验证进展：
  - 已新增并执行阈值敏感性审计：
    - `repo/ood/second_environment_toniot_threshold_sensitivity.py`
    - `runs/second_environment_toniot_threshold_sensitivity_2026-04-21/`
  - 结论：`FT fixed=0` 在当前 chosen orientation 下对 `>` / `>=` 都成立，不是简单比较符错误；ID tie 影响 alarm 计数，但不能解释 attack detection 为零。
  - 已新增并执行耦合探针：
    - `repo/ood/second_environment_toniot_coupling_probe.py`
    - `runs/second_environment_toniot_coupling_probe_2026-04-21/`
  - 探针结论（`dA + FT`, fixed split）：
    - `FT` 对表达方式高度敏感：`signed_log1p_zscore` 可把 fixed detection 从 `0` 拉到 `0.1452`，但 fixed OOD alarm 同时升到 `0.0990`；
    - 当前证据支持“模型 + 前端表达耦合”假设成立，但尚未得到可部署低告警 operating point。

#### C. 对抗鲁棒性评估包：分成神经白盒与统一黑盒两层

##### 设计原则
- 不做“图像领域式”的形式主义攻击演示。
- 必须围绕当前论文的真实判定规则：
  - fixed threshold
  - anomaly score crossing
  - deployment operating point

##### 攻击目标
- 把高纯攻击样本的异常分数拉低到 fixed threshold 以下，形成 evasion。

##### 评估分层
1. **R1：神经模型白盒一阶攻击**
- 对象：
  - single-seed Transformer latent gate
  - 3-seed Transformer ensemble
  - FT-Transformer / modern deep baseline（若已实现）
- 方法：
  - FGSM
  - PGD
- 输出：
  - `epsilon -> detection drop`
  - `epsilon -> evasion success rate`

2. **R2：统一黑盒约束攻击**
- 对象：
  - dA
  - single-seed Transformer
  - 3-seed ensemble
- 方法：
  - 坐标扰动 / sign-free search / padding-style constrained attack
- 输出：
  - 相同预算下，不同模型的规避难度比较

##### 特征合法性约束
- 非负特征保持非负
- 比率 / bounded 特征裁剪到观测范围
- 近似离散特征可选 round/clamp
- 扰动预算同时报告 `L_inf` 与平均相对改变量

##### 成功判据
- 只要能够展示：
  - naive/single deep model 更易被规避
  - covariance-aware ensemble 在相同预算下更稳
- 这一包就足够进入论文主文或强 supplement。

#### D. deployability / cost 闭环包：不再只说“3x cost”

##### 设计原则
- 部署讨论必须和 strongest candidate 绑定，不做泛泛而谈。
- 成本不是弱点隐藏区，而是系统论文必须正面给出的事实。

##### 必测对象
1. `dA`
2. `single-seed Transformer latent gate`
3. `3-seed covariance-aware ensemble`
4. `distillation v2`（若后续成功）

##### 必测指标
- CPU `ms/sample`
- throughput
- checkpoint size
- torch / non-torch parameter count
- peak memory（若可稳定测）
- 训练总时长
- 校准/阈值额外开销

##### 成功判据
- 形成一张能直接进入论文的 deployment table
- 对 strongest candidate 给出一句能站住的系统表述：
  - “higher-cost but still deployable remedy”
  - 或 “single-model distilled variant approaching teacher”

#### E. Tier 1 预计推进顺序

1. `FT-Transformer` 补强
2. 第二数据集最小 feasibility（BoT-IoT first）
3. 对抗协议实现与小规模白盒验证
4. 统一 deployment/cost 主表

说明：
- 若第 2 步 feasibility 显示 BoT-IoT 无法构造干净的 benign OOD split，则立即切 TON-IoT network subset，不在 BoT-IoT 上硬耗。
- 若第 1 步已经证明现代 baseline 风险显著下降，则不再继续扩大 baseline 家族。

#### F. A 线正式超算任务固定操作书（2026-04-17 固化）

##### 使用原则
- 先本地 smoke，再上超算。
- 超算只跑正式任务，不拿来修路径、修脚本、修 bundle。
- 适合上超算的任务包括：正式训练、多 seed、sweep、多配置、第二数据集或第二环境验证、正式 baseline 复现、长时间 CPU/GPU 作业。
- 不适合上超算的任务包括：本地 smoke、修路径、修脚本、修打包、离线 rescoring、画图、整理表格、是否值得正式跑仍未判断清楚的任务。

##### 命名规则
- 每次正式任务都必须新建 `run_tag`。
- `run_tag` 固定格式：`任务名_YYYY-MM-DD`。
- 正式 rerun 必须更换新日期。
- 本地正式目录固定为 `runs/<run_tag>/`。
- 远端项目根目录必须带日期，例如 `/public/home/<user>/work/<project-mainline>_YYYY-MM-DD`。
- 远端标准运行目录固定为 `<remote_project_root>/runs/<run_tag>/`。
- 回传包固定路径为 `package/<run_tag>_bundle.tar.gz`。

##### 提交前冻结清单
- 正式提交前，`runs/<run_tag>/` 下必须固定：
- `command.txt`
- `config.json`
- `run_spec.json`
- `job.slurm`
- `upload_bundle.tar.gz`
- 明确写定的回传 bundle 路径
- 如果这些还没冻结，就不允许上超算。

##### 固定执行流程
1. `ssh` 创建远端目录
2. `scp` 上传 `upload_bundle.tar.gz`
3. `ssh` 到远端解包
4. 在远端 `run_dir` 下执行 `sbatch job.slurm`
5. 自动建立 `latest_slurm.out`、`latest_slurm.err`、`last_job_id.txt`
6. 作业完成后 `scp` 拉回 `package/<run_tag>_bundle.tar.gz`
7. 本地解包并先检查结果完整性

##### 日志规则
- 远端 `run_dir` 下必须能直接打开：
- `latest_slurm.out`
- `latest_slurm.err`
- `stdout.log`
- `stderr.log`
- 默认通过远端文件树直接查看 `latest_slurm.out` / `latest_slurm.err`，不依赖每次手动 `tail -f`。
- 程序输出必须同时镜像到 Slurm 输出文件与 `stdout.log` / `stderr.log`。
- 提交后必须自动记录 `last_job_id.txt`、`latest_slurm.out`、`latest_slurm.err`。
- 建议额外生成 `job_info.json` 或同类 manifest，记录 `job_id`、`job_name`、`node_list`、`submit_dir`、`python_bin`、`stdout_log`、`stderr_log`。

##### `job.slurm` 最小元信息
- `job.slurm` 至少输出：
- `[start]`
- `[run_dir]`
- `[python]`
- `[command]`
- `[command_exit]`
- `[bundle]`
- `[finish]`
- 这样失败时可以快速区分：提交失败、环境失败、导入失败、路径失败、训练中途失败。

##### PowerShell 规则
- Windows PowerShell 下生成的 `ssh` / `scp` / `sbatch` 命令必须可直接复制执行。
- 不允许要求手动再改 quoting。
- 不允许生成会在 PowerShell 本地被错误展开变量的命令。

##### 回传包要求与回传后动作
- 回传包至少必须包含：
- `summary`
- `results`
- `diagnostics`
- `config`
- `stdout.log`
- `stderr.log`
- `job_info` 或同类运行 manifest
- 回传后固定顺序是：
1. 先检查 `summary`、`results`、`diagnostics`、logs 是否完整
2. 再更新 handoff
3. 再更新主线实验表
4. 最后 `commit + push`
- 如果结果无效，则必须记录失败原因、修复点、以及是否需要新日期 rerun。

##### 总原则
- 超算不是调试器。
- 超算只负责正式训练、正式验证、正式多 seed、正式 sweep。
- 凡是路径、脚本、bundle、命名、日志规则没有固定好的任务，一律先留在本地解决。
- `frontend100_timescale_tokenizer_v1_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1 single-seed minimal experiment with header-aware 5x20 regrouping; path: `runs/frontend100_timescale_tokenizer_v1_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_1_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.1 single-seed scoring refinement with header-aware 5x20 regrouping and short-scale aware aggregations; path: `runs/frontend100_timescale_tokenizer_v1_1_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_2_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.2 adds scale-contrast scorers on top of header-aware 5x20 regrouping; path: `runs/frontend100_timescale_tokenizer_v1_2_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.3 adds short-focused weighted reconstruction training plus timescale-contrast scoring; path: `runs/frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13/`.
- `frontend100_structured_frontend_v1_smoke_2026-04-13`: Frontend100 StructuredFrontend-v1 with 20 semantic tokens (`4 families x 5 scales`), dual family/scale embeddings, and contrast scorers on top of the original 100D source; local smoke indicates semantic re-layout of the same 100D is **not enough** by itself: best structured Transformer fixed point is about `0.0121 / 0.2464`, still below the older 5-token line and below flat-AE+contrast control. This supports the next step being **upstream frontend redesign**, not just richer reshaping of the same compressed 100D. Path: `runs/frontend100_structured_frontend_v1_smoke_2026-04-13/`.

---

### 八、Frontend-F2 受控重构入口（2026-04-13 固化）

#### 为什么现在切到 frontend

- `timescale_tokenizer` 与 `structured_frontend_v1` 已经把“同一份 original-frontend 100D 的后端重组空间”基本试穿。
- 结论一致：
  - scorer 可以改变 fixed trade-off，但不足以形成主线翻盘；
  - token 重组能产生局部机制信号，但仍明显打不过 dA，也未超过同源 flat 控制；
  - `4 families x 5 scales` 的 semantic token 化仍然不够，说明瓶颈不只在 token 排列，而在**上游表达生成时就被压扁了**。

#### 当前判断

- 当前 100D 对 dA 很友好，但对 Transformer 并不原生。
- 若继续在同一份 100D 上做更复杂后端重排，收益大概率已经接近上限。
- 因此下一阶段最值得投入的是：**沿着 Kitsune 原始提取链上移一层，做 upstream frontend expression 的受控重构。**

#### F2 的纪律

- 不引入外部黑盒 frontend 作为第一版主实现。
- 不破坏当前 `original-frontend 100D` 主线，必须保留 flat 100D 输出，确保历史实验与论文主干完全可复现。
- 第一轮只在 `kitsune_frontend_original_extract.py` 增加“结构化缓存输出”，不修改底层增量统计公式。

#### F2 第一轮目标

- 在原始 frontend 抽取阶段同步输出：
  - 原有 `100D flat npy`
  - `family x scale x stat-slot` 的结构化缓存
  - 语义 schema 与 token 映射元数据
- 先做本地 smoke，确认结构化缓存数值可逆、与 flat 100D 严格一致，再决定是否进入新的训练线。

#### 当前结论

- 如果要真正追求超越 dA 的新突破，最值得投入的是**重新构造前端表达**，而不是继续挤压同一份 100D 的重排空间。
- `Frontend-F2` 已成为下一阶段最合理的高价值探索入口。
- `kitsune_frontend_f2_smoke_2026-04-13`: Frontend-F2 extractor smoke. `kitsune_frontend_original_extract.py` now emits both flat 100D cache and structured semantic cache (`family_scale_tokens [N,4,5,7]`, `token_matrix [N,20,7]`, schema json). Local smoke on first 2000 packets passed with exact flat reconstruction (`max_abs_diff = 0.0`). Path: `runs/kitsune_frontend_f2_smoke_2026-04-13/`.
- `frontend_f2_crosscapture_source_smoke_2026-04-13`: Frontend-F2 source-prep smoke. Added `prepare_frontend_f2_crosscapture_sources.py` to slice structured caches into reusable ID/OOD source bundles while preserving flat csv/npy compatibility and shared schema. Smoke passed on same-source cache wiring. Path: `runs/frontend_f2_crosscapture_source_smoke_2026-04-13/`.
- `frontend100_modern_tabular_baselines_ft_smoke_2026-04-13`: FT-Transformer AE local smoke on original-frontend 100D stronger OOD. Single-seed (`101`) result confirms the modern baseline script works, but fixed performance remains weak (`q99 ~ 0.4935 / 0.8064`, `q995 ~ 0.2667 / 0.6970`), so this line does not threaten the current strongest paper candidate. Path: `runs/frontend100_modern_tabular_baselines_ft_smoke_2026-04-13/`.
- `frontend_f2_extract_id_7_6_2026-04-13`: Real benign ID Frontend-F2 extraction on `7-6` using the existing TSV from crosscapture stage1. Structured cache generated successfully with exact flat reconstruction. Path: `runs/frontend_f2_extract_id_7_6_2026-04-13/`.
- `frontend_f2_extract_ood_4_1_2026-04-13`: Real benign OOD Frontend-F2 extraction on `4-1` using the existing TSV from crosscapture stage1. Structured cache generated successfully with exact flat reconstruction. Path: `runs/frontend_f2_extract_ood_4_1_2026-04-13/`.
- `frontend_f2_extract_attack_34_1_2026-04-13`: Real attack Frontend-F2 extraction on `34-1` using the existing joint-eval TSV. Structured cache generated successfully with exact flat reconstruction, enabling aligned attack-side evaluation under the new frontend. Path: `runs/frontend_f2_extract_attack_34_1_2026-04-13/`.
- `frontend_f2_crosscapture_stage1_2026-04-13`: Real Frontend-F2 cross-capture source bundle built from `7-6` ID and `4-1` OOD structured caches; outputs both structured `.npz` sources and flat compatibility csv/npy. Path: `runs/frontend_f2_crosscapture_stage1_2026-04-13/`.
- `frontend_f2_attack_source_2026-04-13`: Real Frontend-F2 attack source bundle aligned to stage2 manifest (`use_first_n=10000`), producing reusable structured attack source plus flat compatibility outputs. Path: `runs/frontend_f2_attack_source_2026-04-13/`.
- `frontend_f2_structured_tokenizer_v1_smoke_2026-04-13`: First real-data smoke of `frontend_f2_structured_tokenizer_v1.py` using `7-6` ID, `4-1` OOD, and `34-1` attack structured caches, with token family/scale embeddings and short-vs-long contrast scoring. Local smoke runs successfully, but fixed detection remains low (best structured transformer about `0.0120 / 0.2043`), so Frontend-F2 is now a real exploratory branch but not yet a mainline challenger. Path: `runs/frontend_f2_structured_tokenizer_v1_smoke_2026-04-13/`.

- `frontend_f2_structured_tokenizer_v1_smoke_2026-04-13`: Frontend-F2 structured tokenizer v1 on real structured caches (`7-6` ID, `4-1` OOD, `34-1` attack), using token family/scale embeddings and short-vs-long contrast scoring; path: `runs/frontend_f2_structured_tokenizer_v1_smoke_2026-04-13/`.

- `frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14`: Frontend-F2 contrast-token v1 derives short-vs-long anomaly-increment tokens directly from structured caches and evaluates transformer/token-MLP backends on real `7-6/4-1/34-1` data; path: `runs/frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14/`.

---

### 九、2026-04-22 主线状态修订：A 线失败封口与 original100 few-shot 官方控制组

#### A 线 second-environment 失败封口包

状态：
- `BoT-IoT` 与 `TON-IoT` second-environment 不再作为继续扩跑、继续优化、继续救活的主线活线。
- 该线正式沉淀为：
- negative evidence
- limitation
- external-validity boundary
- second-environment 当前不进入主证据。

裁决依据：
- `BoT-IoT`：当前本地可用 benign 支撑不足，无法满足 formal mainline split/calibration/eval 口径；因此不进入正式主证据。
- `TON-IoT`：工程门、split 门、finite 值门已基本排除，但模型结果仍不支持主线：
- `dA` fixed reference: `AUC=0.679894`, `attack_det=0.076667`
- `strongest_candidate_transformer_covreg_v2_seed101` fixed: `AUC=0.690065`, `attack_det=0.003333`
- `ft_transformer_ae` fixed: `AUC=0.570755`, `attack_det=0.000000`
- threshold-sensitivity probe 证明 `FT fixed=0` 不是简单 `>` / `>=` 或方向选择 bug。
- coupling probe 证明模型 + 表达耦合存在，但当前没有形成可部署 low-alarm operating point。

写作边界：
- 可以写成当前 protocol 的外部有效性边界与限制。
- 不应写成主线正证据。
- 不再安排 second-environment 扩跑或调参，除非未来明确开启新日期、新 protocol。

#### original100 few-shot official control package

Run:
- script: `repo/ood/original100_fewshot_official_control.py`
- run path: `runs/original100_fewshot_official_control_2026-04-22/`
- task type: few-shot / supervised target-aligned detector
- representation: original frontend flat 100D
- model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`

Protocol:
- negatives = ID benign + OOD benign
- positives = stage2 high-purity attack
- positive budgets = `16`, `32`
- positive sampling seeds = `42,43,44,45,46`
- final OOD eval does not participate in threshold selection
- operating points:
- `fixed_id_calib_q99`
- `guarded_id_calib_and_ood_val_target1pct`
- outputs include mean/min/max summaries

Package integrity:
- `command.txt`, `config.json`, `run_spec.json`, `official_control_manifest.json`, `diagnostics.json`, `results.csv`, summary/focus CSVs, `summary.md`, `stdout.log`, `stderr.log` all present locally.
- `results.csv` has 22 rows.
- aggregate summary has 6 rows.

Official control results:
- `original100_fewshot_logistic`, 16-shot, fixed:
- `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`
- `OOD alarm mean/min/max = 0.004500 / 0.001200 / 0.009500`
- `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`
- `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 16-shot, guarded:
- `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`
- `OOD alarm mean/min/max = 0.004440 / 0.001200 / 0.009200`
- `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`
- `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 32-shot, fixed:
- `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`
- `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`
- `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`
- `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 32-shot, guarded:
- `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`
- `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`
- `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`
- `feasible_rate = 1.000000`

Reference baseline boundary:
- `da_unsupervised_score_seed42` remains a reference baseline only, not the same label-information setting.
- fixed ID q99: `AUC=0.806365`, `OOD alarm=0.128600`, `attack det=0.686545`
- guarded: `AUC=0.806365`, `OOD alarm=0.010800`, `attack det=0.002909`

Interpretation boundary:
- `original100_fewshot_logistic` is now the mainline official control for the v7 target-aligned methodology port.
- This package does not claim source-rich superiority and does not replace the A-line second-environment failure closure.

---

### 十、2026-04-23 主线-frontend-f2 叙事汇合地图

#### 汇合性质

这次汇合是论文叙事、证据结构和实验资产的汇合，不是直接把 frontend-f2 旧 tokenizer / AE 代码并入主线。

主线职责保持：
- 主线仍维护 `runs/mainline_docs/mainline_handoff.md` 与 `runs/mainline_docs/mainline_experiment_map.md` 两份活文档。
- A 线 second-environment 继续保持失败封口状态，不再扩跑救线。
- original100 few-shot official control 是主线官方控制组。
- frontend-f2 的价值重新定位为 source-rich 表示的 hard-holdout robustness 与 auditability 资产，而不是“无监督前端重构已经全面翻盘”。

#### 新论文中心

推荐中心主张：
- 严格 low-OOD-alarm operating region 揭示了传统 unsupervised detector 的 detection collapse。
- 少量 high-purity attack positives 形成的 target-aligned linear head 可以显著恢复低误报区间的检测能力。
- original100 few-shot control 证明主要杠杆是 target alignment。
- source-rich 的独特价值应写成困难 holdout 下的稳健性、可审计性和机制解释，而不是平均性能全面压过 original100。

#### 证据路由表

| 证据块 | 当前角色 | 论文去向 | 边界 |
|---|---|---|---|
| stronger benign OOD + calibration 旧主线 | 问题定义与机制背景 | 主文 | 用来证明 low-OOD-alarm 区间才是真部署痛点 |
| dA / Deep SVDD / FT 等 baseline 失败模式 | unsupervised collapse 证据 | 主文或主附录 | 不写成“模型弱”，写成 objective 与 deployment target 失配 |
| A 线 BoT-IoT / TON-IoT | negative evidence / limitation / external-validity boundary | limitation 或附录 | 不进入正向主证据，不再扩跑 |
| original100 few-shot logistic | official control | 主文或主附录核心表 | 证明 target alignment 是主要杠杆 |
| frontend-f2 v7.2 / v7.3 few-shot | target-aligned positive evidence | 主文或主附录 | 需和 original100 同口径比较，不能单独宣称 source-rich 胜出 |
| frontend-f2 v7.4 paired holdout | 待核验的 hard-holdout fairness 证据 | 待确认后决定主文/附录 | 当前主线不得未核验就写成稳定结论 |
| frontend-f2 早期 tokenizer / AE / temporal / contrast 负结果 | 机制诊断资产 | 附录或方法动机 | 支持“不是没信号，而是 objective 不对齐” |
| source-rich feature/family/scale 分析 | auditability 资产 | 主文解释图或附录 | 卖点是可审计与困难窗口解释，不是平均性能英雄 |

#### 主文叙事骨架

建议主文顺序：
1. 定义问题：开放世界 stronger benign OOD 下，AUC 不足以代表部署可用性，关键是 low-OOD-alarm operating region。
2. 展示失败机制：传统 unsupervised detector 在低误报区间出现 detection collapse。
3. 引入 target alignment：few-shot supervised linear head 使用极少量 high-purity attack positives 修正目标错配。
4. 固定公平控制：original100 few-shot official control 与 dA reference baseline 给出标签信息边界。
5. 接入 frontend-f2：source-rich 不是平均性能主英雄，而是 hard-holdout robustness 与 auditability 的表示层资产。
6. 明确限制：second-environment 当前封口为 external-validity boundary，后续外部验证需要新 protocol。

#### 后续最小补强包

优先级 1：
- 核验 frontend-f2 v7.4 paired holdout fairness 是否已经稳定。
- 若稳定，把它登记为 source-rich hard-holdout robustness 证据。
- 若不稳定，只保留为边界和负结果，不强行汇入正证据。

优先级 2：
- 为 original100 few-shot official control 生成 paper-facing 表格和 operating-point 图。
- 表格必须保留 16/32-shot、multi-seed mean/min/max、fixed 与 guarded 两个 operating points。

优先级 3：
- 做 source-rich auditability 资产整理。
- 至少包括 feature/family/scale 级别解释、困难 holdout 案例、与 original100 的边界说明。

优先级 4：
- 整理标签代价和部署成本。
- 说明 high-purity attack positives 的获取预算、训练成本、推理成本。

#### 当前禁止推进项

- 不再继续 second-environment 扩跑、调参或救线。
- 不再新增无监督 tokenizer / AE patch 作为主线中心。
- 不再写 `source_rich` 平均性能全面优于 `original100`。
- 不再把 dA reference 与 few-shot supervised detector 写成同标签信息口径的公平胜负。
- 不在未核验 v7.4 前把 paired holdout 写成主线稳定结论。

#### 当前决策

主线与 frontend-f2 可以汇合，但汇合后的主张应是：
- paper center = low-OOD-alarm detection collapse + few-shot target alignment。
- official control = original100 few-shot logistic。
- source-rich role = hard-holdout robustness + auditability。
- closed limitation = A-line second-environment failure package。

## 6. Problem-Driven Reframing and Evidence Roadmap

Date: 2026-05-17

This section records the post-survey reframing from few-shot LR repair to **Low-Alert Intrusion Detection under Benign-OOD Drift**. The current recommended route is **Problem B / balanced hybrid paper**.

### 6.1 New Evidence Map

| Evidence level | Items | Paper role |
|---|---|---|
| A-level | low-OOD collapse; fixed OOD guard; original100 fixed guard / LOW-GUARD-minimal; clean support and threshold provenance | Can support main claims if harder-holdout and baseline gaps are handled. |
| B-level | source_rich useful but unstable; Transformer hidden integration feasible; mode-gated arbitration as deployment policy; bounded review as safety net | Auxiliary and system-context evidence. |
| C-level / negative | scalar score fusion; hidden-only failure; source_rich as stable main gain | Boundary evidence and appendix / negative-result record. |
| Missing | formal harder holdout; second environment; DevNet / Deep SAD / RoSAS-like baselines; OOD target sensitivity; shot sensitivity; runtime / efficiency; threshold transfer | Must be addressed before strong submission claims. |

### 6.2 Experiment Priority

| Priority | Experiments | Purpose |
|---|---|---|
| S-level | formal harder holdout validation; few-shot anomaly baseline comparison; OOD target sensitivity 0.5 / 1 / 2; shot sensitivity 8 / 16 / 32 / 64; threshold/provenance audit preserved | Defend the main problem definition and prevent reviewer collapse into "cost-sensitive LR on one split." |
| A-level | second environment pilot; modern unsupervised baselines; efficiency / runtime; calibration transfer | Strengthen external validity and deployment credibility. |
| B-level | adapter upgrade such as margin-GDA / deviation-GDA / prototype-GDA; Transformer hidden improvement; explainability / feature attribution | Only after S-level gaps are addressed. |
| C-level | further source_rich tinkering as main route; large neural model upgrade before generalization evidence; more score-level fusion | Do not prioritize as mainline. |

### 6.3 Current Stop Rule

- Do not continue source_rich as the main route.
- Do not continue Transformer hidden as the main route.
- Do not optimize review queue as an added attack-detection contribution.
- Do not perform complex adapter upgrades before harder-holdout and baseline recovery.
- Do not reopen score-level fusion unless a new, pre-registered reason exists.

### 6.4 Current Naming

Use `LOW-GUARD-minimal` for the current implementation:

`original100 representation + fixed OOD-benign guard + few-shot LR adapter`.

Avoid writing that full GDA, detector-agnostic adaptation, source_rich superiority, or Transformer-hidden improvement has already been proven.

### 6.5 Issue26a Within-Dataset Temporal Feasibility Inventory

Date: 2026-05-22

Run:
- `runs/issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22/`

Scope:
- within-dataset temporal / data-scale feasibility;
- evidence inventory;
- temporal candidate matrix;
- leakage audit;
- issue26b planning.

Not in scope:
- formal temporal validation;
- second environment;
- topK/support/adapter/threshold tuning;
- dA or Transformer training;
- routing, promotion, or frontend-f2 reopening.

Key result:
- issue25c remains `strong_baseline_positive` for frozen Enhanced LOW-GUARD+ top64.
- No clean P0/P1 temporal candidate with low leakage risk was found.
- `chrono_early_train_late_eval` is the best partial candidate, but it overlaps issue23/25c locked eval bins `6/7/8`; it cannot be written as clean new temporal proof without metadata recovery and purge/embargo design.
- Existing `primary_lowood`, `holdout_bin_2`, and `chrono_late_train_early_eval` remain consistency/discovery evidence.
- Existing locked bins `5/6/7/8` remain same-dataset locked evidence, but repeated locked-bin analysis risk must be stated.
- No optional minimal temporal validation was run.

Current claim boundary:
- Allowed: issue26a inventories within-dataset temporal/data-scale evidence and audits leakage risk.
- Not allowed: issue26a proves temporal generalization, proves external generalization, or replaces second-environment validation.

Next:
- Unique next action: `issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22`.
- Do local metadata recovery and split-manifest construction first.
- Use Slurm only after local smoke passes and the formal temporal protocol is frozen.
- Keep second-environment validation as issue27-level work.

### 6.6 Issue26b Split Metadata Recovery And Temporal Asset Build

Date: 2026-05-22

Run:
- `runs/issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22/`

Scope:
- split metadata recovery;
- known-setting provenance reconstruction;
- temporal candidate rebuild;
- purge/embargo planning;
- metadata-only split smoke.

Not in scope:
- formal temporal validation;
- second environment;
- new method development;
- topK/support/adapter/threshold tuning;
- dA or Transformer training;
- routing, promotion, or frontend-f2 reopening.

Key result:
- Bin-level provenance was recovered for primary, discovery, locked, and partial temporal settings.
- Support provenance and threshold provenance remain clean in the inspected artifacts: support selection does not use attack eval / final OOD eval, and threshold selection uses ID calibration + OOD validation.
- Raw timestamp, packet-order, capture/session boundary, window_start/window_end, and bin-to-clock-time metadata were not recovered.
- No clean formal temporal candidate is ready.
- `earlier-to-later` is still the best partial temporal direction, but it overlaps issue23/25c locked eval bins `6/7/8` and needs purge/embargo metadata before any formal claim.
- No formal validation result was produced.

Current claim boundary:
- Allowed: issue26b documents metadata/provenance recovery and identifies the concrete asset gap blocking clean temporal validation.
- Not allowed: issue26b proves temporal generalization, completes formal temporal validation, or replaces second-environment evidence.

Next:
- Unique next action: `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.
- Recover raw temporal metadata or unused future-window assets before any formal issue26c validation.
- If raw metadata remains unavailable, avoid dressing locked-bin reuse as temporal proof and move toward a scoped second-environment feasibility path.

### 6.7 Issue27a Deployment Feasibility And Guarded Training Protocol Audit

Date: 2026-05-22

Run:
- `runs/issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22/`

Scope:
- deployment assumption inventory;
- guarded training pipeline design;
- alert-budget workload interpretation;
- label-budget and contamination robustness plan;
- LR-vs-framework positioning;
- deployment reviewer defense.

Not in scope:
- model training;
- temporal validation;
- cross-dataset validation;
- topK/support/adapter/threshold tuning;
- autonomous online learning;
- manuscript edit.

Key result:
- Primary verdict: `deployment_protocol_plausible_needs_robustness_simulation`.
- Secondary verdict: `lowguard_should_be_framed_as_guarded_adaptation_protocol`.
- LOW-GUARD is better framed as a guarded few-shot adaptation protocol, while the current LR head is `LOW-GUARD-LR`, a minimal deployable instance.
- Current main method locked OOD max is `0.0045`, about 45 alarms per 10k OOD events, under the official 1% low-alert budget.
- DevNet-like and random32 are detection-competitive in places but exceed 1% locked OOD alarm, making them deployment-risky under the official low-alert constraint.
- Deployment assumptions are plausible only with explicit support provenance, benign-OOD guard provenance, delayed confirmation, no self-training, and rollback controls.

Current claim boundary:
- Allowed: LOW-GUARD protocol is deployment-plausible under explicit support/guard assumptions and needs robustness simulation.
- Not allowed: live SOC deployment is proven, 32 supports are always available, OOD benign labels are always clean, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27b_deployment_robustness_simulation_for_lowguard_top64_2026-05-22`.
- Run shot sensitivity, support-noise, OOD contamination, support-source, update, and shadow-mode workload simulations before adapter upgrades.

### 6.8 Issue27b Guarded Protocol Transfer And Adapter Recovery

Date: 2026-05-26

Run:
- `runs/issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26/`

Scope:
- frozen locked-bin protocol-transfer matrix;
- LR / DevNet-like / HistGB / DeepSAD-like / Prototype-metric / RFF adapter-head comparison;
- P0/P1/P2/P3 training-guard and threshold-guard ablation;
- LOW-GUARD++ candidate check;
- final-eval leakage audit through selection trace.

Not in scope:
- temporal validation;
- cross-dataset validation;
- topK/support/adapter/threshold tuning beyond the pre-registered head configs;
- dA or Transformer training;
- deployment robustness simulation;
- manuscript edit.

Key result:
- Primary verdict: `nonlinear_detection_gain_not_low_alert_feasible`.
- LOW-GUARD-LR P3 reproduces issue25c exactly: locked mean/min/OOD max `0.949705 / 0.882629 / 0.004500`.
- Best non-LR full LOW-GUARD head: DevNet-like MLP with locked mean/min/OOD max `0.947497 / 0.895305 / 0.010100`, feasible rate `0.975000`.
- No LOW-GUARD++ candidate was found.
- DevNet-like is near LR on detection and stronger on locked min, but its OOD max remains just above the official 1% budget.
- HistGB, DeepSAD-like, Prototype/metric LR, and RFF Logistic do not threaten LOW-GUARD-LR as the current feasible minimal instance.

Current claim boundary:
- Allowed: LOW-GUARD-LR remains the strongest feasible minimal instance under the locked low-alert protocol.
- Allowed: nonlinear heads can be detection-competitive but are not automatically low-alert feasible.
- Not allowed: LOW-GUARD transfers cleanly to all adapters, LOW-GUARD++ is proven, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27c_deployment_robustness_simulation_for_lowguard_lr`.
- Run shot sensitivity, support-noise, OOD-benign contamination, support-source, and shadow-mode workload simulations.
- Do not widen the adapter space unless deployment robustness exposes a concrete failure mode.

### 6.9 Issue27c LOW-GUARD Mechanism Falsification And Head Specificity Audit

Date: 2026-05-26

Run:
- `runs/issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26/`

Scope:
- LR rescue mechanism audit;
- head-specificity audit;
- score distribution and OOD-tail audit;
- stricter OOD validation target curve;
- top64 linearity / representation-bias audit;
- implementation-gap audit for proxy heads.

Not in scope:
- deployment robustness simulation;
- temporal validation;
- cross-dataset validation;
- new method development;
- topK/support/threshold tuning;
- manuscript edit.

Key result:
- Primary verdict: `lowguard_lr_success_mechanistically_supported`.
- Secondary verdicts: `representation_linearization_explains_lr_advantage`, `lowguard_effect_head_specific_lr_only_so_far`, `non_lr_results_inconclusive_due_to_proxy_implementation`.
- LR recovery is mechanistically interpretable: raw LR has high detection but severe OOD alarm; threshold-only LR collapses detection; OOD-guarded training preserves detection and suppresses OOD tail; full LOW-GUARD adds validation safety.
- Non-LR heads did receive OOD_train guard, so the near-miss/failure is not explained by missing guard exposure.
- DevNet-like remains detection-competitive but has insufficient OOD-tail safety margin.
- DeepSAD-like and DevNet-like are proxy implementations; do not write their failure as full method defeat.
- No direct implementation bug or final-eval leakage was found.

Current claim boundary:
- Allowed: LOW-GUARD-LR is the strongest feasible demonstrated instance and has a supported rescue mechanism.
- Allowed: broader head-agnostic transfer is not established.
- Not allowed: LOW-GUARD works for all heads, nonlinear adapters are useless, DevNet/DeepSAD are defeated, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity`.
- Run a small original100-vs-top64 control over LR / DevNet-like / HistGB before returning to deployment robustness.
- Keep the matrix bounded and do not open a model zoo.

### 6.10 Issue27d LOW-GUARD Adapter Interface And Model-Specific Objective Smoke

Date: 2026-05-26

Run:
- `runs/issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26/`

Scope:
- common LOW-GUARD adapter interface;
- Stage A interface, score-direction, data-usage, and leakage checks;
- bounded model-specific-lite objective smoke;
- representation control: `source_rich_top64` vs `original100`;
- locked bins `5/6/7/8`, seeds `42/43/44`.

Not in scope:
- formal issue27e validation;
- temporal validation;
- cross-dataset validation;
- deployment robustness simulation;
- dA or Transformer training;
- topK/support/threshold tuning;
- manuscript edit.

Key result:
- Primary verdict: `lowguard_plus_plus_candidate_found_with_model_specific_objective`.
- Stage A interface preflight passed with no final-eval selection or support/eval overlap.
- LOW-GUARD-LR top64 reproduced issue25c: locked mean/min/OOD max `0.949705 / 0.882629 / 0.004500`.
- No non-LR head dominated LOW-GUARD-LR on frozen `source_rich_top64`.
- `LOW_GUARD_HistGB_Conservative` on `original100` is a representation-control LOW-GUARD++ candidate: `0.994261 / 0.978091 / 0.005100`, feasible rate `1.000000`.
- Best non-LR on top64 was `LOW_GUARD_HistGB_Conservative`: `0.659751 / 0.040689 / 0.006600`.

Current claim boundary:
- Allowed: issue27d found a candidate worth formal issue27e validation and strengthened the adapter-interface evidence.
- Allowed: LOW-GUARD-LR remains the strongest demonstrated top64 minimal instance.
- Not allowed: the main method is replaced, LOW-GUARD++ is proven, LOW-GUARD is head-agnostic, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27e_formal_validation_for_lowguard_plus_plus`.
- Validate the `original100 + LOW_GUARD_HistGB_Conservative` candidate under full locked seeds and unchanged final-eval exclusion before changing any paper claim.

### 6.11 Issue27e Formal LOW-GUARD++ Validation Gate

Date: 2026-05-27

Run:
- `runs/issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26/`

Scope:
- candidate config freeze recovery for `original100 + LOW_GUARD_HistGB_Conservative`;
- audit of issue27d selection trace and leakage evidence;
- formal-validation go/no-go decision.

Not in scope:
- full locked-seed final-eval run after config ambiguity was found;
- temporal validation;
- cross-dataset validation;
- deployment robustness simulation;
- representation search;
- new model search;
- manuscript edit.

Key result:
- Primary verdict: `candidate_config_not_recoverable_needs_debug`.
- The issue27d candidate was not one unique frozen config:
  - `histgb_d2_lr003_l2p0_ood4_sup2_t0100` selected 7/12 smoke bin-seed combinations.
  - `histgb_d2_lr005_l2p1_ood4_sup4_t0050` selected 5/12 smoke bin-seed combinations.
- Full locked seed validation was not run, by design, because selecting one config after seeing the smoke aggregate could become hindsight model selection.
- No issue27e final-eval leakage occurred.

Current claim boundary:
- Allowed: issue27e identifies a candidate-freeze blocker and preserves claim hygiene.
- Allowed: original100 + HistGB-Conservative remains a serious LOW-GUARD++ candidate.
- Not allowed: LOW-GUARD++ is formally validated, the main method is replaced, HistGB universally dominates LR, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative`.
- Freeze one HistGB-Conservative config using support-validation / OOD-validation evidence only, then run full locked seeds.

### 6.12 Issue27f Config Freeze Then Formal LOW-GUARD++ Validation

Date: 2026-05-27

Run:
- `runs/issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27/`

Scope:
- train/cal/validation-side config freeze for `original100 + HistGB-Conservative`;
- full locked seed validation after config freeze;
- LOW-GUARD-LR top64 reference rerun in matched schema;
- threshold target robustness report;
- leakage and artifact audit.

Not in scope:
- deployment robustness simulation;
- temporal validation;
- cross-dataset validation;
- representation search;
- new model search;
- manuscript edit.

Key result:
- Primary verdict: `lowguard_plus_plus_formal_validated`.
- Frozen config: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`.
- LOW-GUARD++ formal locked mean/min/OOD max: `1.000000 / 1.000000 / 0.000100`.
- LOW-GUARD-LR top64 reference locked mean/min/OOD max: `0.949705 / 0.882629 / 0.004500`.
- LOW-GUARD++ dominates LOW-GUARD-LR on locked mean, locked min, and OOD max.
- Feasible rate: `1.000000`.
- Threshold robustness:
  - target `0.0050`: `1.000000 / 1.000000 / 0.000100`;
  - target `0.0075`: `1.000000 / 1.000000 / 0.000100`;
  - target `0.0100`: `1.000000 / 1.000000 / 0.008300`.
- No final-eval selection leakage was found.

Current claim boundary:
- Allowed: LOW-GUARD++ is formally validated as `original100 + HistGB-Conservative` under the locked low-alert protocol.
- Allowed: LOW-GUARD-LR remains the minimal stable instance under source-rich top64.
- Allowed: the method story can be framed as minimal instance + performance instance.
- Not allowed: HistGB universally dominates LR, LOW-GUARD works for all models, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27g_deployment_robustness_for_lowguard_lr_and_lowguard_plus_plus`.
- Stress-test both instances under support budget, support noise, OOD benign contamination, support source, and shadow-mode workload protocols.

| issue27g | suspicious-perfect-score audit for LOW-GUARD++ | `lowguard_plus_plus_formal_result_passes_anomaly_audit` | Audits issue27f 1.0 result for final-eval leakage, split overlap, original100 leakage, negative controls, scratch recompute, and cache artifacts. Next: `issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade`. |

| issue27h | original100 feature provenance and LOW-GUARD++ claim gate | `lowguard_plus_plus_depends_on_high_risk_separators` | Maps separator features, runs frozen ablations, and blocks broad claim upgrade pending clean independent validation/provenance. Next: `issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus`. |

| issue27i | LOW-GUARD++ separator validation and data expansion feasibility | `lowguard_plus_plus_promising_needs_clean_independent_validation` | Characterizes separator stability and safer variants; keeps LOW-GUARD++ alive while blocking claim upgrade pending clean independent validation. Next: `issue27j_raw_provenance_recovery_and_clean_independent_split_construction`. |

| issue27j | raw provenance and clean split audit for LOW-GUARD++ | `clean_independent_validation_blocked_but_recoverable` | Recovered raw pcap/TSV/source-code provenance but found clean independent validation still blocked by insufficient unused future/capture split assets. Next: `issue27k_row_level_original100_rebuild_and_purged_split_construction`. |

| issue27k | row-level original100 rebuild and purged split construction | `row_manifest_recovered_but_clean_split_blocked` | Builds row-level sidecar and verifies feature alignment; clean/purged validation remains blocked by insufficient clean independent split assets. Next: `issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset`. |

| issue27l | clean eval asset and split-aware original100 rebuild gate | `clean_eval_asset_found_rebuild_eval_next` | Finds full Mirai/Botnet labeled assets and a sufficiently sized extended-segment candidate; blocks formal LOW-GUARD++ clean eval pending feature compatibility, split-aware rebuild, and prior-use/provenance audit. Next: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`. |

### issue27m full Mirai compatibility audit (2026-05-27)

| Run | Verdict | Role | Boundary | Next |
|---|---|---|---|---|
| `runs/issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27/` | `full_mirai_incompatible_needs_new_frontend_path` | Large-data compatibility and prior-use gate for LOW-GUARD++ | Full Mirai is not yet a clean validation result for frozen original100; it is a clean115/restored115 or re-extraction path | Recover restored115 mapping or re-extract original100 before evaluation |
| issue27n | full Mirai restored115 mapping and interface-smoke gate | `restored115_feature_mapping_blocked` | Defines clean115 from dirty116 but blocks smoke because feature mapping is unverified and strict prior-use exclusion removes all benign rows. Next: `issue27o_restored115_mapping_recovery_or_original100_reextraction_for_full_mirai`. |

| issue27o | full Mirai protocol reset spec | `full_mirai_protocol_reset_ready_with_anonymous_clean115` | Adopts full Mirai as within-dataset protocol-reset benchmark; old issues are exploration; restored115/common100 remain unmapped; baselines must be rerun. Next: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`. |

| issue27p | full Mirai anonymous clean115 reset benchmark | `baseline_dominates_needs_method_rethink` | Runs formal within-dataset reset benchmark with anonymous clean115; best current method `DeepSADStyle_Lite`; old results superseded for final claims. Next: `issue27q_protocol_reset_result_audit_and_seed_expansion`. |

| issue27q_plan | protocol reset result audit plan | `issue27q_execution_plan_ready` | Plan-only package: audit DeepSADStyle_Lite, diagnose LOW-GUARD++ failure, and design paired protocol-universality matrix. Next: P0/P1 audit before mainline decision. |

| issue27q_P0P1 | DeepSAD-lite replay/audit/seed expansion | `deepsad_lite_result_suspicious_needs_artifact_debug` | P0/P1 audit for the issue27p leader; checks replay, leakage, negative controls, feature artifact risk, and seed 42-51 stability. Next: `issue27r_deepsad_lite_artifact_debug_and_feature_provenance`. |

<!-- issue27r_map_entry -->

### issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28

- status: completed.
- primary_verdict: `attack_benign_artifact_risk`.
- outputs: `runs/issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28/`.
- role: benchmark semantic validity gate before model-line continuation.
- implication: pause DeepSAD mainline, LOW-GUARD++ repair, and universality claims until full Mirai raw provenance or second-dataset semantic validation resolves row-order/source/feature-semantics risk.

<!-- issue27s_map_entry -->

### issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28

- status: completed.
- primary_verdict: `dual_track_raw_rebuild_and_second_dataset_intake`.
- outputs: `runs/issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28/`.
- role: Data validity gate fork after issue27r semantic failure.
- implication: full Mirai anonymous_clean115 is not current main benchmark; proceed with raw provenance recovery and second-dataset intake before any model execution.

<!-- issue27t_map_entry -->

### issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28

- status: completed.
- primary_verdict: `second_dataset_candidates_need_manual_access_or_download_confirmation`.
- outputs: `runs/issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28/`.
- role: Data validity gate second-dataset candidate intake after full Mirai paired raw was confirmed missing.
- implication: no model execution; proceed to Gotham metadata intake, with ToN-IoT as fallback and local IoT-23 as auxiliary.

<!-- issue27u_map_entry -->

### issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28

- status: completed.
- primary_verdict: `gotham_ready_for_full_download_with_user_confirmation`.
- outputs: `runs/issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28/`.
- role: Gotham metadata-level Data Gate precheck.
- implication: Gotham is promising but requires user-confirmed 23.825GB decimal / 22.189GiB download and file-level split/label audit before any model execution.

<!-- issue27v_map_entry -->

### issue27v_gotham_download_and_file_level_data_gate_2026-05-28

- status: completed under user-approved download-only mode.
- primary_verdict: `gotham_file_level_gate_passed_ready_for_sample_data_gate`.
- outputs: `runs/issue27v_gotham_download_and_file_level_data_gate_2026-05-28/`.
- role: Gotham file-level Data Gate entry point after user-confirmed download permission.
- implication: Gotham passed file-level gate for raw PCAP + labelled processed CSV presence, but metadata is partial and sample-level Data Gate is still required before feature/interface work or any model execution.

<!-- issue27w_map_entry -->

### issue27w_gotham_sample_data_gate_2026-05-28

- status: completed.
- primary_verdict: `gotham_sample_gate_promising_needs_more_space_and_larger_sample`.
- outputs: `runs/issue27w_gotham_sample_data_gate_2026-05-28/`.
- role: Gotham sample-level Data validity gate before feature/interface work.
- implication: Gotham is promising but requires larger sample manifest/split validation before any model execution.

<!-- issue27x_map_entry -->

### issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28

- status: completed.
- primary_verdict: `gotham_larger_sample_promising_needs_full_manifest`.
- outputs: `runs/issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28/`.
- role: larger-sample Data validity gate for Gotham split construction.
- implication: Gotham remains promising, but Feature/interface gate is blocked until a fuller manifest and exact claim-safe split contract control file/device/time artifacts.

<!-- issue27y_map_entry -->

### issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28

- status: completed.
- primary_verdict: `gotham_data_contract_promising_needs_feature_pairing_or_full_manifest`.
- outputs: `runs/issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28/`.
- role: final-strengthening Data validity gate for all-CSV Gotham summaries and preregistered split-contract candidates.
- implication: Gotham has a promising device-disjoint data contract and adequate scale, but model experiments remain blocked until PCAP/CSV pairing and source-feature shortcut policy are strengthened.


<!-- issue27z_map_entry -->

### issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28

- status: completed.
- primary_verdict: `gotham_ready_for_feature_interface_diagnostic_only`.
- outputs: `runs/issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28/`.
- role: PCAP/CSV pairing strengthening and feature-source policy pre-gate.
- implication: Gotham may proceed only to Feature/interface gate work; model experiments remain disallowed.


<!-- issue27aa_map_entry -->

### issue27aa_gotham_strict_packet_feature_dataset_and_split_materialization_2026-06-01

- status: completed.
- primary_verdict: `gotham_strict_feature_dataset_ready_for_model_interface_smoke`.
- outputs: `runs/issue27aa_gotham_strict_packet_feature_dataset_and_split_materialization_2026-06-01/` plus external dataset artifacts under `datasets/gotham2025/derived/strict_packet_feature_dataset_v1/`.
- role: strict source-clean data asset construction and frozen split materialization.
- implication: proceed to interface smoke only; no formal model benchmark yet.

## issue27ab Gotham Kitsune115 frontend feasibility (2026-06-01)

- primary_verdict: `kitsune115_blocked_by_pcap_label_alignment`
- evidence role: Feature/interface pre-gate for the formal Gotham PCAP-derived 115D feature path.
- claim boundary: no model ranking, no external generalization, no deployment robustness; strict 8D is engineering-only.
- next action: issue27ac Gotham Kitsune115 attack-onset alignment and broader split-aware materialization before any model interface smoke.

<!-- issue27ac_map_entry -->

### issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-02

- status: completed.
- primary_verdict: `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`.
- outputs: `runs/issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-02/` plus tiny external probe artifacts under `datasets/gotham2025/derived/kitsune115_attack_onset_probe_v1/`.
- implication: attack-side alignment is tractable for a smoke expansion if PCAP scenario and onset timestamp are selected correctly; full-contract materialization still needs deeper scan for unresolved ip-camera attack files. No model benchmark yet.

<!-- issue27ad_map_entry -->

### issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_split_aware_smoke_dataset_ready_heavy_attack_deferred`.
- outputs: `runs/issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02/` plus external artifacts under `datasets/gotham2025/derived/kitsune115_split_aware_smoke_expansion_v1/`.
- implication: 115D smoke dataset construction is ready for a minimal model-interface shape smoke, not formal benchmarking; heavy ip-camera attack files need fast frontend/Slurm for larger materialization.

<!-- issue27ae_map_entry -->

### issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_model_interface_smoke_passed`.
- outputs: `runs/issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02/`.
- implication: backend adapters can consume fixed 115D smoke artifacts for shape checks only; no method claim.

<!-- issue27af_map_entry -->

### issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.
- outputs: `runs/issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02/` plus external medium artifacts under `datasets/gotham2025/derived/kitsune115_medium_materialization_v1/`.
- implication: medium data asset is ready for non-performance sanity checks; formal benchmark waits for full_contract or explicit preregistration.

<!-- issue27ag_map_entry -->

### issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_larger_asset_ready_with_full_contract_pending`.
- outputs: `runs/issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02/`.
- implication: medium 115D asset has a fixed loader and role-permission sanity gate; formal benchmark still waits on full_contract or explicit preregistration.

<!-- issue27ah_map_entry -->

### issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02

- status: completed.
- primary_verdict: `guarded_protocol_medium_dry_run_completed_diagnostic_only`.
- outputs: `runs/issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02/`.
- implication: medium 115D diagnostic behavior is available, but formal benchmark waits for full_contract or a documented exclusion policy.

<!-- issue27ai_map_entry -->

### issue27ai_medium_protocol_audit_then_diagnostic_2026-06-02

- status: completed.
- primary_verdict: `medium_protocol_audit_passed_diagnostic_completed`.
- outputs: `runs/issue27ai_medium_protocol_audit_then_diagnostic_2026-06-02/`.
- implication: protocol matrix diagnostics are available for debugging only; final claims wait for full/larger asset and frozen protocol.

## issue27aj - Protocol Lineage Recovery And Support Selector Audit

- Status: completed.
- Primary verdict: `recovered_kcenter_mainline_protocol_ready_for_gotham115_migration`.
- Key recovery: old mainline support selector is `kcenter32`, not issue27ai
  `fixed_first32`.
- Evidence: issue23 locked validation and issue25c strong baseline pack name
  the main candidate as `selected_source_rich_top64 + kcenter32 + fixed OOD
  guard LR`; executable code calls `issue19b.kcenter_support(...)` on the
  train-side attack pool only.
- Selector mechanics: selector-local `StandardScaler`, Euclidean farthest-first
  k-center, budget 32, no attack eval or final OOD eval access.
- Gotham migration: migrate selector/protocol permissions only to Gotham
  Kitsune115 medium diagnostics; do not migrate old frontend or old performance
  claims.
- Next: `issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.

<!-- issue27ak_map_entry -->

### issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic_2026-06-02

- status: completed.
- primary_verdict: `recovered_kcenter32_medium_diagnostic_completed`.
- outputs: `runs/issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic_2026-06-02/`.
- implication: recovered kcenter32 support can be diagnosed on medium Gotham115 only; final claims wait for full/larger asset and frozen protocol.

<!-- issue27am -->
## issue27am

- verdict: `medium_repair_insufficient_pause_feature_state_onset_audit`
- route: Gotham Kitsune115 medium bounded protocol repair validation.
- claim boundary: diagnostic only; formal full/larger benchmark remains gated.

<!-- issue27an -->
## issue27an

- verdict: `support_eval_distribution_mismatch_blocker_found`
- route: Gotham Kitsune115 medium failure attribution audit.
- claim boundary: diagnostic failure attribution only; no model ranking or formal benchmark.

<!-- issue27ao -->
## issue27ao

- verdict: `contract_v2_ready_for_medium_detection_retest`
- route: Gotham Kitsune115 medium support/eval contract v2 validation.
- claim boundary: contract-only diagnostic; no model performance claim.

<!-- issue27ap -->
## issue27ap

- verdict: `new_heldout_v2_diagnostic_signal_weak_support_shift_persists`
- route: new held-out heavy attack probe plus v2 diagnostic retest.
- claim boundary: diagnostic only.

<!-- issue27aq -->
## issue27aq - Model learning/domain-gap diagnosis

- Inputs: issue27af medium reset asset, issue27ao `file_balanced_v2`, issue27ap new heldout probe.
- Verdict: `zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal`.
- Model line remains diagnostic; full benchmark remains blocked until learning/calibration is repaired under role-safe rules.

<!-- issue27ar -->
## issue27ar - Old LOW-GUARD++ protocol fidelity migration

- verdict: `old_protocol_fidelity_mixed_needs_bounded_calibration_repair`
- purpose: determine whether current Gotham weak signal is partly due to protocol mismatch against old issue27f LOW-GUARD++.
- outputs: `runs/issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium_2026-06-03/`.

<!-- issue27as -->
## issue27as - Bounded calibration repair after old protocol fidelity

- verdict: `bounded_repair_suggests_feature_or_task_boundary`
- purpose: test whether bounded calibration/support-influence changes can rescue medium signal without using report-only roles.
- outputs: `runs/issue27as_old_protocol_bounded_calibration_and_coverage_repair_2026-06-03/`.

<!-- issue27at -->
## issue27at - Coverage hypothesis validation

- verdict: `coverage_hypothesis_partially_supported_needs_more_attack_pool`
- purpose: test whether support-query coverage explains medium/high vs heavy/low heldout behavior without tuning a new protocol.
- outputs: `runs/issue27at_coverage_hypothesis_validation_before_protocol_redesign_2026-06-03/`.

<!-- issue27au -->
## issue27au - Coverage-aware active labeling viability

- verdict: `active_labeling_viability_supported_but_ood_tail_blocked`
- purpose: test whether budgeted representative labels from uncovered incoming heavy stream can rescue dev-query detection without using final roles.
- outputs: `runs/issue27au_coverage_aware_active_labeling_viability_diagnostic_2026-06-04/`.

<!-- issue27av -->
## issue27av - Prototype-aware triage

- verdict: `ood_tail_needs_benign_prototype_veto`
- purpose: attribute final OOD tail alarms using ID/OOD/attack prototypes before OOD-safe gate repair.
- outputs: `runs/issue27av_prototype_aware_triage_and_ood_tail_attribution_2026-06-04/`.

<!-- issue27aw -->
## issue27aw - OOD-safe gate repair

- verdict: `benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged`
- purpose: test whether benign/OOD prototype veto can reduce OOD tail without using final roles for gate selection.
- outputs: `runs/issue27aw_ood_safe_gate_repair_with_benign_prototype_veto_2026-06-04/`.
