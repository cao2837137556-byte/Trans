# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **当前执行**：同库历史参考三维C5 v6，真实预检182658运行；最终成绩待验收。
2. **最近故障**：v5存储schema已通过，供体oracle跨批次比较失败。原版自身960/120查询可复现1条供体差；v6同批同序完整预检oracle，本地真实960行数值差0/供体差0，56项检查通过。
3. **固定口径**：A289/B52835历史参考＋dense；时间索引因果重放；C2/C3/C4存储schema全行核验、排除0，原几何另存；供体严格一致，四头分数/判决门保留，无训练或阈值改动。
4. **下一步**：真实门和预算门通过自动完整对照，1CPU/8GiB、30+90分钟，失败保存具体UID并停止；旧NO_GO与Edge非双99.9%边界保留。
5. **证据/存储**：[修复回执](collab/20261106_same_bank_context_batch_parity_repair_codex.md)、[执行卡](../same_bank_context_v6_20261106/EXECUTION_CARD.md)、[右侧进度页](http://127.0.0.1:18806/)；大工件留超算，后台回收摘要。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
