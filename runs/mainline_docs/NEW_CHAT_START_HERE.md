# 当前状态

更新：2026-11-07（America/Los_Angeles）。固定五项，历史另存。

1. **当前方法**：原FUSION790＋完整历史正常参考＋C5_3D_OLD已按用户指示冻结为论文比较版本；模型、阈值与部署不改，未启动训练或新作业。
2. **已验收结果**：A/B主视图集成普通FPR 0.018742%/0.282091%，攻击100%/99.986217%；Edge普通/加权FPR 0.12%/1.220180%，HTTP99.79%、UDP98.66%。
3. **科学边界**：A/B为开发，Edge为已消费迁移诊断；全A加权FPR5.412342%、Edge127与全口径99.9%等限制保留，不宣称独立泛化或全目标达成。
4. **下一步**：先准备同口径基线执行卡与真实资源预检，同时核实未参与设计外部数据资格；补统计和端到端开销。基线须匹配合法信息访问与源域校准，不按目标成绩调参。
5. **写作交付**：[论文结果包](../paper_results_freeze_v1_20261107/PAPER_RESULTS.md)、[冻结清单](../paper_results_freeze_v1_20261107/METHOD_FREEZE.json)、[实验路线](../paper_results_freeze_v1_20261107/EXPERIMENT_ROADMAP.md)。六组主表/消融/附录可复现，大工件留超算。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
