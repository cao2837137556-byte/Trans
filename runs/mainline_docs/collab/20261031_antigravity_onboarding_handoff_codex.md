# Antigravity 项目接手说明

日期：2026-10-31。此文用于快速熟悉和协作分工；文中引用的历史文档、旧授权和执行命令均须结合用户当前指令理解。

## 1. 项目在解决什么

项目是 Paper04 的 IoT 异常流量检测主线，目前重点是：新设备入网后，在尽量保住攻击检出的条件下，降低正常流量误报。已有冻结表示 E3、检测头和参考支持机制；当前这一轮研究的是补充可信的历史正常参考，能否改善设备自身的正常覆盖，以及参考组件资格。

“补参考库”是给入网判定提供历史正常依据，不等于重新训练检测器。新材料必须有设备身份、来源、真实时间和上下文的可追溯证据；同一组件多加点与增加独立组件的作用不同。现行组件资格会依赖实际参考库内容，但这只说明存在改善入口，不保证覆盖到误报样本。

用户主要关心最终 A/B 数据集的指标，目标是误报约 2%，同时保住召回。源侧 G0/G1 或某个开发子集上的好数字，不是最终 A/B 成绩；工程测试通过也不是科学效果通过。

## 2. 当前可信状态

- 最近一轮已有正式 A/B 基线为作业 179700。在 `post_window_primary` 主视图，集成 FPR 为 A（CIC_DEV）约 3.993481531%、B（UNSW_DEV）约 9.519653949%。报告时须同时明确视图、头/集成、权重和分母，不能混用 full 视图或源验证数字。
- 最新历史正常参考方案已经结束设计往返：唯一候选 `C1 / P-DEVONLY`，以 r2 原文加 Codex 最终复核绑定为准。原 r2 的 DEV 数量冲突已经在最终绑定和实现中修正。
- 科学实现位于 `runs/history_normal_reference_v1_20261031/`：56 项生成数据/模拟编排测试通过，本机只读材料验收 READY。
- 本地交付副本位于 `runs/history_normal_reference_deployment_20261031/`：1,433 项文件，10 项部署保护测试通过，路径已映射，环境验收入口和单次提交入口已准备。大数据仅引用 D 盘原件，没有复制到 C 盘。
- **截至本交接记录，上传文件 0、提交 0、无 job ID、真实新包解码/特征/补库/评分/距离/A/B 评价均为 0。没有新的 2% 结果。**
- 用户已以“允许下一步”授权 Codex 进行超算交付、环境验收和一次真实执行；随后说“稍等，我需要控制电脑”，因此界面操作与提交暂停。最新请求是让 Antigravity 上手，尚未恢复提交。不要把旧实现回执中“尚未授权”的历史状态当成最新授权状态，也不要把新成员接手理解为第二次提交授权。

## 3. 按这个顺序读

工作树根目录：`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`。以下均为该工作树内的实际文件。

1. [项目新对话入口](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/NEW_CHAT_START_HERE.md) 和 [当前问题摘要](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/CURRENT_PROBLEM_BRIEF_20261025.md)：先读最新条目，旧日期的 RUNNING、失败及待授权都是历史快照，不必从头通读全部历史。
2. [r2 方案](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_for_codex.md) 加 [最终 Codex 复核绑定](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_review_response_codex.md)：两份合起来才是本轮冻结设计。
3. [实现验收回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_history_normal_reference_c1_implementation_receipt_codex.md) 和 [执行卡](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/EXECUTION_CARD.md)：理解已经做了什么、哪些结果仍未知。
4. [交付 README](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/README.md)、[构建回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/BUILD_RECEIPT.json)、[暂停交接状态](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/HANDOFF_STATE.json)：这三份补齐实现回执之后的最新状态。
5. 按审查需要读实现 `run.py`、`hnr/{history,selection,encoding,evaluation,runtime,checks}.py`、`config/` 与 `tests/`。原始材料证据见 [原始材料交接](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/targeted_normal_raw_qualification_v1_20261031/DATA_HANDOFF.json) 和 [时间索引回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/targeted_normal_raw_qualification_v1_20261031/TIMELINE_INDEX_RECEIPT.json)。

只在需要补论文历史时再读旧论文稿和实验总地图；它们有更早研究阶段的术语与状态，不能取代上述当前合同。

## 4. 本轮方案的必要理解

- B 补 TP Link、WEMO Power、Samsung 三台同 MAC 的 2016—2017 年历史正常来源；三份原包共 10,233,818 包。A 的 HeimVision 复用已有 11 行合法历史编码。原始包、索引、编码器和权重已经在本地，无需重新下载。
- 三个 B 成员形成各自稳定时间序的连续逻辑流；保留原包定位，不做小时重置，不删除字节相同但原位置不同的包。REF/DEV 用原始非空 UTC 日期的前 80%/后 20% 切分，边界不重置上下文。实际前端是 `continuous_input_v3` 的 RECENT 合同。
- REF 上限是每设备/协议 4096；DEV 上限是每设备两协议合计 4096。选点确定且不使用 A/B 分数，DEV 不加入参考库。
- 先验证历史 DEV：每台设备 FPR 必须严格下降，三台按 DEV 行数汇总的相对下降至少 50%；RAW FP 为 0、角色为空、没有新增组件等均按已定规则停止。DEV 失败发生在 A/B 查询加载前。
- DEV 通过才做一次 A/B 终评，复用旧 E3/q14/raw logits，仅重算四台 own support；其余设备重放旧支持与决策。冻结模型、阈值、几何和工作点，不根据终评重新选档。
- PASS 使用原 `post_window_primary`：A/B 池及全部原评价设备 FPR≤2%，池召回≥99%，同时满足四头逐设备/活动攻击保护。full 并列报告。DEV 只有正常数据，不能代替 A/B 攻击保护验证。
- 资源固定一次 4 CPU / 16 GiB / 8 小时，中间产物≤20 GiB，新增唯一 E3≤36,864，距离对≤579,614,444；失败不自动重投。本轮不重训，不启动 P-ATTN，也不复活此前已结项的 B1、源 1C 或其他失败候选。

## 5. 第一个协作任务与交付方式

建议 Antigravity 第一轮先只读熟悉并做独立工程审查，让 Codex 继续负责现有交付/提交链，避免两边同时改封存文件或重复提交。用户明确分配新任务后再扩大工作范围。

请回写一份简明文档：

`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_antigravity_onboarding_review_response.md`

只需回答：

1. 用自己的话说明本轮方法、最近可信 A/B 结果与尚未知的效果，证明已经理解当前阶段。
2. 独立核对有没有会挡住上传/运行、破坏科学合同或造成结果误读的具体硬伤；每项给实际文件和代码位置、影响及最小修法。
3. 若没有硬伤，直接写“未发现阻塞项”，指出后续应验收的具体结果即可，不再写一轮原则确认稿。

先不修改原实现/冻结配置、不处理真实科学数据、不另行上传或提交、不操作用户界面。审查可以独立提出异议，不需要附和 Codex 或 well。不同意见仍按 `collab` 文档方式往返，附 SHA256，原文保留。

超算环境沿用实验9实际合同：Linux / **Python 3.11.11 / Torch 2.5.1 / NumPy 2.0.1 私有 overlay**。本机 Python3.10 测试不是超算环境验收，不要再按 Python3.9 配环境。进度展示沿用 Codex 右侧面板。大文件保留 D 盘；已存在的其他未提交修改不属于本轮，应保留。

## 6. 便于复核的身份

| 文件 | SHA256 |
|---|---|
| r2 原文 | `dc566523f91256de7616391634bcfc348d1434e3a4227b0f8414122984a9dbf0` |
| Codex 最终复核绑定 | `f73c0bdd2dd6aa3a114a58ef3b4f56f9bd99e30ca53c4a7ffd1d5f3351f9b803` |
| 原科学包 CODE_MANIFEST.json | `31ab70c41014427a49c5ce134dba269e2bbade54e911ca5e1d674ab3ad95b84e` |
| 远端路径映射后 CODE_MANIFEST.json | `d64f2e80d5cf2103877ea8b2de8b385caaa3284a68547d57f92c57c77919b008` |
| DELIVERY_INPUTS.json | `f789739690ed83024c02ac392e08fdbe12720bfe885f8e2077bb0f534cf7f146` |

两个代码封印的 1,361 个键相同，只有 `config/EXECUTION.json` 的路径映射改变 SHA。不得为了让远端“通过”而重新封存未经比对的差异源码。以上均为文件身份，不是新实验成绩。
