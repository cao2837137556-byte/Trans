# 当前状态

更新：2026-11-04（用户时区America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5（p=3）冻结；正式外部效果尚未确认，正式评价未授权。
2. **旧轮封存**：181699在1:57:37触发EDGE_REPLAY_DEADLINE；UDP最后98.59%，上下文随scratch清理。旧结果与诊断保留。
3. **本次修复**：独立v4新增持久帧级上下文检查点及跨作业恢复；NORMAL/HTTP完整产物逐块审计后复用，本次UDP重建。109+15本地测试通过，独立复核USER_WAIVED。
4. **当前运行**：真实78端点＋UDP中断恢复预检181854已PASS（6分51秒）；完整门181856已RUNNING，1CPU/8GiB/2小时。最新状态见进度；无自动重投/延期。
5. **最新证据**：[v4修复续跑](collab/20261104_edge_v4_durable_resume_codex.md) · [启动回执](../edge_formal_gate_deployment_v4_20261104/STARTUP_GATE_REMOTE_READBACK.json) · [实时进度](http://127.0.0.1:18795/)。完整门最终验收仍待完成，不将启动计为通过。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
