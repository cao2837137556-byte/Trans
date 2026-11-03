# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：Edge封存正常/HTTP/UDP各20,000查询+原4,124参考；正常17,025组件全部覆盖；Linux候选包1.127GiB已逐成员验SHA。
4. **下一步与分工**：后续仅Codex和小anti协作；预检候选包交小anti独立复核，不再等Claude。Linux真实预检、完整流式续跑/恢复门和预算未闭合，正式卡未冻结；不持续监测。
5. **最新证据**：[选取收敛回执](collab/20261103_edge_query_selection_convergence_reply_codex.md) · [进度](../edge_query_selection_v1_20261103/PROGRESS.md) · [预检包说明](../edge_linux_preflight_package_v1_20261103/README.md)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
