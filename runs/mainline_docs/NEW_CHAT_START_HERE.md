# 当前状态

更新：2026-11-04 UTC。后续只覆盖本区块，历史另存。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **181645终态**：1小时57分37秒触发重放时间守卫，工程验收STOP；峰值约3.31GiB，临时目录清理成功。NORMAL/HTTP完整产物校验通过，UDP部分角色不可复用。
4. **已完成/下一步**：独立v3进度I/O优化已集成封存；93项本地检查、6万查询元数据核验通过。默认新输出全量重放，不隐式迁移v2；待小anti独立复核和真实Linux门，未提交新作业。
5. **最新证据**：[停止与v3交付](collab/20261104_edge_181645_stop_and_v3_package_codex.md) · [v3复核清单](../edge_formal_execution_v3_20261104/REVIEW_REQUEST.md) · [进度/终态页](http://127.0.0.1:18793/)。正式评价未启动，无自动延期或重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
