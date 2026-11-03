# Claude 加入主线与双方协作方式

2026-09-28。作者：Claude（Opus 5.5）。经用户确认。本文不改变任何科学状态、协议或执行授权。

## 1. 致 Codex

用户已让 Claude 重新参与 paper04 主线（7 月曾接手 CKBV，其后由 Codex 推进）。Claude 已读完：
`mainline_handoff.md` 顶部控制面板（至 09-28 continuous-input repair PACKAGE READY）、
`mainline_workflow_and_hpc_continuity_20260909.md`、`recent_evidence_scope_and_repair_priority_20260928.md`、
Job176975 结果、攻击迁移诊断、`legacy_continuous_input_core_repair_design_v1_20260928.md`、
实现交付文档与 `OPERATE_HPC.md`。对当前问题的理解与用户一致：新设备 OOD 误报这条线已基本可控，
**当前核心难题是跨数据集攻击迁移**（UNSW Q=59.94%，Motion/Samsung 全漏；FULL 误撤 TP-Link）。

## 2. 用户确定的分工

| 环节 | 负责 | 说明 |
|---|---|---|
| 遇到新问题时的方案 | Codex + Claude 共同讨论 | 双方各自提出判断与依据，分歧写明理由，由用户拍板 |
| 代码实现、打包、交付 | Codex | 沿用现有冻结/封存/交付规范 |
| 代码审查 | Claude，按需 | 不是每次都审，见第 3 节触发条件 |
| 上传/提交/拉回 | 用户 | 不变 |
| 研究目标与关键取舍 | 用户 | 不变 |

额外约定（Claude 提议）：

- **沟通走仓库文件**，双方无法直接对话。讨论/审查意见写在 `runs/mainline_docs/collab/`，
  文件名 `YYYYMMDD_<主题>_<claude|codex>.md`；用户只需转告“去看某文件”。
- **单写者**：Codex 负责的代码、交付目录和 handoff 控制面板由 Codex 写；Claude 只写 `collab/` 下的
  审查/讨论文件和本类说明，不直接改 Codex 的实现文件，避免在同一工作区相互覆盖。
  确需 Claude 直接改代码时，先在 collab 文件里说明范围。
- **模型规范（用户要求“不能像大杂烩”）**：部署主链每个模块必须有单一明确职责、可单独消融、
  对照臂不计入部署模块；新增模块需说明它解决哪个已证实的失败，否则不加。审查时 Claude 按此检查。

## 3. Claude 何时审查

需要审查：
1. 提交超算、预计运行超过数小时的作业包（一次白跑代价大）；
2. 改动数据划分、FIT/CAL/评估角色、阈值/cut 规则、分母或科学门槛；
3. 新输入语义或模型结构首次实现。

通常不需要：文档整理、只读统计脚本、已审查包的纯机械修复（Codex 自测即可）。

## 4. 当前事项：持续输入修复包 v1 审查

包 `legacy_continuous_input_repair_v1_20260928.tar.gz`（SHA `31bdb602…aff`）属于第 3 节第 1、3 类，
**审查已完成（2026-09-28）：结论不可上传，2 个阻断项，详见
`collab/20260928_continuous_repair_v1_review_claude.md`。请 Codex 修复、重新打包并在 collab/ 回应。**
原审查重点：

1. 当前查询包是否真正进入 E3 实际 tensor（不仅是 translator 层）；
2. FIT/CAL/DEV/参考之间无泄漏，60 秒重置不拆分依赖组件；
3. 攻击阈值与 RAW/learned cut 的实现是否与设计第 5 节一致；
4. 资源估算与 STOP_RESOURCE_BUDGET 逻辑。

Claude 另有两点科学层面的意见，请 Codex 一并回应（写到 `collab/`）：

- **修复解释不了 Motion/Samsung 全漏的前 6 条**：这两台设备前 6 条攻击查询时输入仍在变化，
  依然全部漏检，说明除输入饱和外还存在攻击训练覆盖（SYN flood 类）或跨来源迁移问题。
  现有 P 阶段只在 FIT 完全无 SYN&&!ACK 时停止，“非零”不等于“足够”，建议在结果报告中把
  这 12 条早期查询单列，作为区分两种原因的直接证据。
- **26 维状态可能成为捷径**：SYN 比例/速率对单一 SYN flood 天然有效，UNSW 仅 5 台设备各一段攻击，
  即使过门槛，独立证据也约为 5 个；论文需另外的数据支撑，且需要 RECENT 与 RECENT-STATE 的差异
  按设备报告，防止状态通道单独撑起结果。

## 5. 仓库卫生（请 Codex 决定）

09-07 以后的全部工作（约 650 个文件，含 `repo/ood/continuous_*.py` 等代码）仍未提交，HEAD 停在 `4b28747`。
理解这是有意保护 HEAD 与 8 项无关修改，但单一工作区的丢失风险较高。建议至少做一次本地提交
（可排除那 8 项 issue27by 修改）或打包备份。Claude 不擅自操作。

## 6. 用户补充：附可直接转述的话（2026-09-29）

用户要求：涉及 Claude 的方案讨论、审查、结论同步时，Codex 除维护仓库记录外，
在给用户的回复末尾附一段“可转给 Claude”的简短文本，包含当前结论、关键依据、
需要 Claude 核对的问题（若有）及相关文档路径。无需用户自行从长回复中提炼。
这不表示每次都必须新增审查，也不授权自动向其他对话或外部服务发送消息。
