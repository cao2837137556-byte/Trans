# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：Edge封存正常/HTTP/UDP各20,000查询+原4,124参考；正常17,025组件全部覆盖；Linux候选包1.127GiB已逐成员验SHA。
4. **下一步与分工**：正式worker/恢复/统计已实现，本地无模型检查通过；小anti复核新执行卡后，申请1CPU/8GiB/2小时的新worker Linux工程验证，再锁正式预算。20k条件估算16.77h、带裕量39.79h，均非承诺；不持续监测、不自动重投。
5. **最新证据**：[工程与预算复核请求](collab/20261103_edge_formal_worker_and_budget_review_request_codex.md) · [网页进度](http://127.0.0.1:18793/) · [181418验收](../edge_preflight_io_repair_v1_20261103/FINAL_ACCEPTANCE.json)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
