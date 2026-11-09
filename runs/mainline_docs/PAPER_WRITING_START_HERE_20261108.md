# 论文写作新对话框：共同接手入口

本文件面向新建的Codex论文写作对话与Antigravity（小anti）审查对话。2026-11-08根据当前仓库与在线状态整理；作业状态会变化，事实以原始回执和当前验收为准。本文是导航，不替代冻结清单或原始指标。

## 1. 当前要写什么

工作根目录：`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`。先读本仓库AGENTS.md。

当前论文比较版本为 `FUSION790_FULL_HISTORY_C5_3D_OLD`，冻结标识见 `runs/paper_results_freeze_v1_20261107/METHOD_FREEZE.json`，accepted_commit=002524d。输入由E3_768、q14、context_8组成，共790维；源域分类头固定，结合合法正常参考与三空间支持做单向分数修正。OLD指封存旧源扣分尺度，不是换回旧782分类器。具体公式、归一化、聚合键、参考资格和回退规则须逐项对照冻结代码，不凭早期聊天补全。

可以从“固定阈值下正常误报与攻击保持的折中，以及上下文和正常参考覆盖如何影响这种折中”组织问题。此为可检验的叙事方向，不是已获普适理论证明，不预先宣布新颖性或全面优于现有方法。

特别避坑：
- `论文/paper_draft_fewshot_mainline.md` 是旧few-shot LogisticRegression/original100叙事，不能当作当前方法稿直接扩写，不覆盖用户已有文件。
- `runs/mainline_docs/paper_skeleton_zh_20260726.md` 是旧骨架，含115维、旧数据角色及过强结构性结论。只能参考章节组织，不能沿用事实、贡献或数字。
- 2026-11-07 EXPERIMENT_ROADMAP中基线候选清单已被后续六方法方案更新；其统计、外部确认和运行代价的证据缺口仍有参考价值。

## 2. 最短阅读路径

以下路径均相对工作根目录，按顺序读，先不要遍历所有历史实验。

1. `AGENTS.md`、`runs/mainline_docs/NEW_CHAT_START_HERE.md`；`mainline_handoff.md`只先读最近相关条目。
2. `runs/paper_results_freeze_v1_20261107/PAPER_RESULTS.md`：当前方法、结果包及主张限制的总入口。
3. 同目录 `METHOD_FREEZE.json`：先查看schema/method/heads/ensemble/correction/geometry与数据角色等字段，巨大参考UID清单按需读，不能只靠文件名前缀猜方法。
4. 同目录 `T1_MAIN.md`、`T2_GEOMETRY_SCALE_ABLATION.md`、`T3_FRONTEND_RAW.md`、`T4_REFERENCE_COVERAGE.md`、`S1_FULL_AND_SEEDS.md`、`S2_DEVICE_BREAKDOWN.md`。有对应.tex，尚未在目标模板编译。
5. 同目录 `ALL_METRICS.json`、`FRONTEND_RAW_METRICS.json`、`SOURCE_PINS.json`、`BUILD_VALIDATION.json`、`build_results.py`：仅按写作中引用的指标追溯字段、分子分母、视图、头、权重与源文件，不盲扫大工件。
6. `runs/mainline_docs/collab/20261107_same_bank_context_acceptance_codex.md`：同库三维几何验收。方法演变有必要时再读相应context/three_layer诊断及anti复核，不把历史候选自动当受控消融。
7. `runs/mainline_docs/collab/20261108_baseline_author_defaults_decision_codex.md`、`runs/baseline_remaining_three_v2_20261108/EXECUTION_CARD.md`、`runs/baseline_tabr_seed_jobs_v1_20261108/EXECUTION_CARD.md`：当前基线规则和适配披露。
8. 最后读 `runs/paper_results_freeze_v1_20261107/EXPERIMENT_ROADMAP.md` 的非基线证据缺口。未完成项目记待办，不自动启动实验。

## 3. 证据优先级与写作边界

权威顺序：用户最新决定及适用AGENTS → 冻结方法/输入身份 → 原始指标、验收回执和校验 → 生成表 → 讨论稿/聊天。冲突必须定位来源后说明，不能让行文顺畅覆盖事实。

- A/B是已消费开发评价；Edge未参与开发，用于跨数据集外部评价。这是论文统一的数据角色定义。
- 目标设备的合法正常建档/历史参考属于系统可访问的信息，不能宣称完全零目标接触。主系统完整C5与共享790 RAW基线的数据访问差异须分开呈现；无监督/监督方法的标签权限也要写清。
- 当前上下文窗口实际是当前包计入的 `(t-W,t]`，不是早期anti建议的 `[t-W,t)`。B历史沿封存索引逻辑时间序前缀重放，A跨capture重置；不得写成所有数据都按原PCAP物理块序处理。
- 召回分母是攻击关联查询，不能写成独立攻击事件检出率。普通率、层级加权率和Edge HT点估计分开，不混成一个百分比。full与post-window primary分开；三种子与ensemble分开，ensemble不是第四个独立种子。
- 当前并未全口径达到“FPR<2%、检测≥99.9%”。冻结表中Edge集成普通HTTP为99.79%、UDP为98.66%；主文必须同时交代全视图/逐设备/seed127的例外，精确数字从表中核对。
- 旧共同阈值审计能证明被审计分数/工作点不可达，不能推出“所有单分数分类器理论上都不可能”。统计显著性、最优性、SOTA需相应证据，不能凭数值差异写出。
- 缓存离线回放耗时不能当作原始PCAP到告警在线延迟/边缘设备吞吐；未测全链路前收窄实时、轻量主张。查询相关性不能当独立伯努利样本生成漂亮置信区间。
- 必须公平报告基线，包括优于本方法的项目；不以预期成绩决定保留方法。六个够用，ModernNCA已取消，不自行补回，也不下载作者论文数据集复现其榜单。实现和适配需准确可追溯。

## 4. 基线快照与结果使用

2026-11-08本入口建立时在线核对：DTE-C、SLAD、CatBoost、TabM已COMPLETE；Disent-AD182805仍训练。TabR修复预检182914之后已实际提交三个种子182915/182916/182917，当前排队；统一评价182918依赖三个训练afterok，尚无最终成绩。此快照不要当永久状态。

结果入口：
- DTE-C/CatBoost：`runs/baseline_author_defaults_v1_20261108/`。
- SLAD：训练权重在上目录，修复后评价回执在 `runs/baseline_slad_eval_repair_v1_20261108/`，不能使用失败旧评价。
- TabM/Disent-AD：`runs/baseline_remaining_three_v2_20261108/`。
- TabR：`runs/baseline_tabr_seed_jobs_v1_20261108/`，旧182807是预算门停止，不是正式训练成绩。

COMPLETE不自动等于已完成论文最终验收。使用指标前应核对对应COMPLETE/EVALUATE或正式验收、模型/分数SHA、行身份、阈值来源及普通/加权口径。若本地缺汇总，列明需要的文件，由实验对话取回；不要擅自连接登录、下载原包或占用正在运行作业。

## 5. 两个新对话框如何分工

建议Codex论文对话负责正文整合、符号表、证据映射与表格引用；anti负责独立方法审查、数据角色/公平性审查、相关工作证据与审稿问题。两者可不同意彼此，但须给文件/字段/代码依据。本实验对话继续负责工程、运行和验收。此分工是写作建议，不授权互发消息或修改运行系统。

建议新文件区域：`runs/mainline_docs/paper_writing_v1/`，先各写自己的文件，避免并发覆盖。
- Codex：`paper_blueprint_codex.md`、`claim_evidence_codex.md`、`method_draft_codex.md`。
- anti：`independent_review_antigravity.md`、`related_work_evidence_antigravity.md`、`open_questions_antigravity.md`。
- 新正式正文路径/目标期刊模板/中英文初稿优先级若尚未确认，先用中文方法草稿与LaTeX表片段推进，再集中提出必要问题。不要把旧骨架中的投稿目标当用户当前确认。
- 两边都不覆盖现有论文草稿、不改冻结模型/阈值/评价脚本、不代替实验对话重交作业、不全库git add、不碰对方未提交修改。完成文档后按仓库规则明确文件清单提交；保留别人工作。

## 6. 第一轮应该交付什么

先交付“接手理解”，不要一上来生成整篇论文：
1. 用通俗中文说明：问题是什么，系统各部分做什么，为什么最终选择这个组合，当前证据支持什么/不支持什么。
2. 一页论文提纲、2–3条有证据支持的候选贡献，标明哪些仍待验证。
3. 主张—证据表：主张、源文件/JSON字段或代码位置、模型/数据视图/头/权重、适用限制、已证实/待核验/缺实验。
4. 方法符号和数据角色核对表，特别检查782/790、当前包窗口、旧源尺度、双独立组件支持、守卫、参考资格、源FIT/CAL。
5. 缺口按“阻塞当前结论”“只阻塞更强主张”“可选增强”排序。不要把愿望清单变成无限追加实验。

之后可立即写实验设置与方法章节、已有主结果及受控消融；基线最终表和结论强度等验收后补齐。引言可先写问题，不预写稳赢结论。文献论断需查原论文/官方实现，记录标题、年份、来源链接与支持内容；不虚构引文和指标。

## 7. 用户协作偏好

用简洁中文解释“为什么做、做了什么、结果意味着什么”；技术细节为理解服务。认真独立判断，不机械接受另一方建议。常规已授权工作直接推进，不反复请求确认；真正缺失的用户选择集中提问。长任务给简明进度，普通进度程序运行后不用AI守候。大文件留超算，只取小型重要汇总。先写好证据明确的部分，不以等待全部基线为理由停写，也不为论文叙事偷改实验。
