# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：v2四项修复、82项检查通过；用户授权的Linux工程作业181645已提交并进入NORMAL因果重放，正式外部评价未启动。
4. **当前执行**：1CPU/8GiB/2小时；[进度页](http://127.0.0.1:18793/)由普通程序更新并取回验收，无AI持续监测、无自动重投。TmpDisk=0已作提交前适配，节点32GiB实际空闲门/24GiB守卫保留；下次独立复核交小anti。
5. **最新证据**：[181645启动](collab/20261103_edge_v2_linux_gate_181645_start_codex.md) · [v2修复验收](collab/20261103_edge_formal_v2_repair_acceptance_codex.md)。当前仅启动验证通过，最终Linux工程验收PENDING，正式预算待后续实测。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
