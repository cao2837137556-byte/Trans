# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：Edge封存正常/HTTP/UDP各20,000查询+原4,124参考；正常17,025组件全部覆盖；Linux候选包1.127GiB已逐成员验SHA。
4. **下一步与分工**：181403已在上下文重放阶段超时（564s、CPU83.9s），未进入模型编码，Linux门未过。已取回失败回执和只读元数据；共享盘SQLite为主要性能嫌疑。先补吞吐、临时盘等价性与帧级可诊断性，不自动重投，不持续监测。
5. **最新证据**：[超时诊断](collab/20261103_edge_preflight_181403_timeout_diagnosis_codex.md) · [网页进度](http://127.0.0.1:18793/) · [最终失败回执](../edge_linux_preflight_deployment_v1_20261103/FINAL_ACCEPTANCE_181403.json)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
