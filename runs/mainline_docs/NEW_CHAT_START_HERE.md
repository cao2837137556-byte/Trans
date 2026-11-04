# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：Edge封存正常/HTTP/UDP各20,000查询+原4,124参考；正常17,025组件全部覆盖；Linux候选包1.127GiB已逐成员验SHA。
4. **下一步与分工**：用户指定本次由实验11 Codex复核、下次交小anti。独立复核为CHANGES_REQUESTED：先修依赖身份、父子资源监督、当前轮次终态和超时scratch清理，再复验并申请1CPU/8GiB/2小时Linux验证；正式预算未锁、不自动重投。
5. **最新证据**：[实验11独立复核](collab/20261103_edge_formal_independent_review_experiment11_codex.md)（原63项测试与元数据核验通过，1项P1/3项P2待修） · [181418验收](../edge_preflight_io_repair_v1_20261103/FINAL_ACCEPTANCE.json)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
