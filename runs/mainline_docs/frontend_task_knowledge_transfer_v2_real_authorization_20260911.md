# 任务知识迁移 V2：一次真实 T→E 授权

日期：2026-09-11。用户在修复报告和新 T→E 执行请求后明确回复：“下一步，我授权”。本条授权覆盖修复版一次连续 T→E；不需要在 T 完成时再次询问 E。

复用已成功封存的 P V1 教师数据，不重做 P。三臂从封存 A 独立初始化，在 V2 独立目录各训练一次；全部最终端点通过核验并封存后自动执行一次 E。异常停止、零自动重试。此前关于未来授权方式的讨论不构成本次允许故障重启的授权。

依据：`frontend_task_knowledge_transfer_t_v1_stop_and_io_fix_v2_20260911.md` 及 SHA 侧车。V2 实现包 SHA256SUMS SHA 为 `5490d9de933ffebe2d398501f1b3d64c61c915f91beea19d7777c1fda92bd895`；复用 P 的 SHA256SUMS SHA 为 `80019634c8b158e901678f55b369476fc488104b4bf1177193750432b83d567d`。

启动前封存代码、运行环境、教师产物及受保护修改的 readiness 核验通过；T/E 状态均为 NOT_STARTED。分支 `codex/exp-mainline`，HEAD `4b28747b09480471e2bac1beb3a9badf27280efb`。冻结的模型、损失、数据分母、seed、预算、末轮端点与阈值保持不变；保留 V1 STOP 和既有科学结论。

启动命令：

```powershell
./scripts/start_frontend_task_knowledge_transfer_v2.ps1 -Stage TE -AuthorizeNewTrainingAttempt -AuthorizeEndpointEvaluation
```

状态命令：`./scripts/show_frontend_task_knowledge_transfer_v2.ps1`。实际运行状态以 V2 T/E 目录的进度、终态及封存核验为准；授权记录不代表启动或完成。由持久本地监督器完成监测，不创建 LLM 定时任务。

本授权仅覆盖这一冻结方案的 V2 尝试；不覆盖改方案、扩大数据用途、超参搜索、下载、原始包解码、HPC 或失败后自动重启。已有教师暴露限制与开发证据定位保持不变。
