# Q/R 一次真实 P→T→E 授权

2026-09-12。用户在上一条明确说明“下一步是真实P预检→Q/R双臂训练→一次终点评价，可一次授权整条流程，异常停止、不重试”后回复：**“可以。授权下一步”**。

本次授权覆盖当前封存实现的一次完整条件链，不需要在正常阶段转换时再次询问：

1. P：核对已有合法9379条TRAIN教师缓存和guard，派生并封存margin/固定尺度。无新教师或学生前向，无优化器。
2. 仅P完成并通过验证后，T：Q/R从相同封存A分别训练20×197步，共7880更新；固定15073条A+B直接监督，不换seed、模型、损失、分母或预算。
3. 仅两臂终点全部封存且T完成后，E：每臂一次train/check/expanded评价，共560632目标；旧模型只复用封存分数。

任何阶段异常即STOP并封存原因，后续阶段不启动，零自动重试。科学结果差仍按配方报告，不换阈值、挑checkpoint或自动加训。禁止新下载、HPC、旧实验重跑、F4重做、未授权select/viewed/report/FINAL和LLM轮询；新设备入网不在本次范围。

封存身份：

- 分支 `codex/exp-mainline`；HEAD `4b28747b09480471e2bac1beb3a9badf27280efb`。
- Q/R配方SHA：`540c2e4d71ce9621965f981d47b4e5f68eb5f148cfd13b4c5d59fa4b2b725702`。
- 实现包SHA256SUMS SHA：`1b6a30f52137ca8ca6b9451d8d2facdb0778bcd1a2510df346fc8c85fdfde00e`。
- 42/42合成验收已通过。本次入口复核返回IMPLEMENTATION_READY_NO_REAL_EXECUTION，启动前P/T/E均NOT_STARTED。

本授权更新的是执行许可，不修改冻结设计中作为历史快照保留的authorization字段。使用已有`start_frontend_task_aligned_transfer_v1.ps1`显式启用Preparation、Training、Evaluation三项，Stage=PTE。持久本地监督程序负责条件转换、资源限制、状态和封存；无需定时LLM监控。

状态入口：`scripts/show_frontend_task_aligned_transfer_v1.ps1`。本文件是授权记录，不是启动、完成或科学成功证明；实际进度/终态与seal核验优先。
