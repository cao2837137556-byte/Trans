# C3 进度写入故障修复与评价恢复

- 日期：2026-11-01，北京时间。
- 本回执状态：`TECHNICAL_RECOVERY_STARTED__NO_NEW_AB_RESULT_YET`，记录恢复启动时的状态。
- 用户明确指令：**“修复然后重新提交。”**
- 科学候选仍是 `C3_ADMITTED_SMALL_BANK_COMPLETE`；模型、参考点、λ、阈值、C2 守卫、查询人口、权重、接受/回退条件均不变。

## 已完成的超算工作与故障位置

唯一超算编码作业 **180460** 已 `COMPLETED / 0:0`。278 个新参考点全部完成编码；编码进程用时 220.345 秒，峰值内存 3,349,520,384 bytes。编码结果已完整取回并通过 SHA256 校验，无须再提交编码作业。

随后首次本地评价在进度更新处中断：`common.progress → write → Path.replace` 将 `STATUS.json.tmp` 替换为 `STATUS.json` 时出现 **`PermissionError: [WinError 5]`**。这是显示文件被占用时的 Windows 共享限制；尚未识别当时持有文件的具体进程，不将其归因于模型、数据或超算失败。

首次评价进程用时 **109.375 秒**、峰值内存 **2,783,694,848 bytes**，最后成功写出的进度为 **32,768 / 61,459** 查询、**82,660,367** 距离对。失败发生在下一次进度写入，这个数不能当成实际最终计算量。原目录只有 `AB_ATTEMPT.json`、`DEV_GATE.json`、`PAIR_PLAN.json`，没有候选 A/B 判决数组或结果文件。

原目录、日志、尝试锁、执行卡和全部科学源码保持原样；没有清锁重跑，没有根据未产生的成绩挑点或改参数。

## 修复范围

独立目录：`runs/history_normal_reference_c3_progress_repair_v1_20261101/`。

1. 进度 JSON/Markdown 写入遇到文件系统异常时，将告警写入运行日志，下一次自然进度更新继续尝试。显示写入失败不再中断科学计算；科学结果文件仍严格写入，异常仍使任务失败。
2. 逐字节复用已有准备材料和超算编码，共 18 个文件；通过原执行卡和请求哈希绑定来源。新增编码、训练、参考选点、超算提交均为 **0**。
3. 保留全部原科学验收门。新增恢复记录与累计资源预算核对，不放宽已有规则。
4. 这是**第 2 次评价进程尝试**；若完成，将是本候选**第一次完整 A/B 评价**。恢复不自动再次重试。

已通过 **19 项检查**：原 14 项工程测试，加 5 项修复测试。修复测试包括实际 Windows 文件句柄禁止重命名场景、Markdown 占用、科学写入错误仍致命、累计距离预算，以及选点/指标/接受门函数与原版 AST 一致。

修复执行卡 SHA256：`53a3c2b3835710b3f8328aee5dd41c97e078e8900eb7899f5dc404afaec3820a`。

## 累计预算与停止条件

保守地给失败尝试计入原计划**全部 161,101,561 距离对**，而不是仅按最后日志计数。恢复最多再使用 161,101,561 对，累计上界 **322,203,122 < 400,000,000**。本地评价累计墙钟上限仍为 7,200 秒，扣除首尝试 109.375 秒；CPU 4、RSS 8 GiB 上限不变。

所有 full/主视图、四头攻击保护门通过，正常误报不增加且 HeimVision 主集成加权 FPR 严格改善，才冻结 C3；否则冻结 C2。无论结果如何，不再依据 A/B 提出新变体。A/B 仍是 `CONSUMED_DEVELOPMENT_ONLY`；本回执不是 C3 效果结论。

## 文件入口

- 修复代码与执行卡：`runs/history_normal_reference_c3_progress_repair_v1_20261101/`。
- 检查：`IMPLEMENTATION_CHECK.json`、`TESTS.log`。
- 本地实时进度：`PROGRESS.md`、`STATUS.json`；已请求在 Codex 右侧打开。
- 首次失败现场：`runs/history_normal_reference_c3_small_bank_v1_20261101/EVALUATE.log`、`EVALUATE_RUNTIME.json`。
- 超算取回回执：`runs/history_normal_reference_c3_deployment_20261101/RETRIEVAL_RECEIPT.json`。

后续以独立验收和最终冻结回执为准，勿把本启动快照当作最终结果。
