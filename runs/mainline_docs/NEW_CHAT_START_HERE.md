# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **授权/方法**：已授权真实训练/校准/耗时门后自动对照；训练规格501aea9c…方法不变。用户先前明确允许不足时增时，独立资源v2正式每头改60分钟，仍1CPU/8GiB/40轮。
2. **前置/旧STOP**：源特征182332通过；v1预检182342完成Linux一致性及9个真实小训练/校准，在30分钟预算门STOP（最大预测39.93分钟），正式头0。
3. **当前运行**：v2真实预检182344，1CPU/8GiB/30分钟；全部门及≤60分钟预测通过后自动串行九头，再集成CAL校准。尚未声明v2预检通过。
4. **证据/进度**：[资源修订](collab/20261105_device_context_training_resource_v2_codex.md) · [启动回执](../device_context_head_training_v2_20261105/STARTUP_RECEIPT.json) · [进度页](http://127.0.0.1:18806/)。普通程序运行，禁止AI守候。
5. **接续/存储**：自动链止于训练与源校准验收；随后按已有授权做OLD782锚点、A/B防退化、C5及Edge诊断。大数组/模型留超算head_training_v2同名目录，小回执取回；失败STOP无自动重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
