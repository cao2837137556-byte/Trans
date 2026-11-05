# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3不变；Edge正式评价182089工程PASS，p3/p1所有头安全门FAIL，UDP各方法均0。
2. **三层诊断**：182245 COMPLETED/0:0，3分19秒、1CPU/8GiB；A/B全池及Edge 60,000查询的资产、对齐、判决和汇总核验PASS。
3. **主要原因**：Edge UDP已存输入20k同指纹、单包上下文；HTTP RAW样本AUROC 0.225，C5又撤警7,027条。A的多包UDP及B全SYN攻击覆盖未暴露这些问题。
4. **证据/存储**：大快照与数组留超算；[三层报告](collab/20261104_ab_edge_three_layer_diagnosis_codex.md) · [验收与SHA](../ab_edge_diagnosis_v1_20261104/FINAL_ACCEPTANCE.json) · [结果页](http://127.0.0.1:18801/)。
5. **下一步/边界**：建议独立小切片核对UDP原包→快照，排除合法上下文漏保留后再决定新方法；本轮未重解码/编码/训练/调参，未新增小anti审查。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
