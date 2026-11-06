# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：8维贡献/锚定冲突诊断真实预检182560运行；通过且梯度预算门通过后自动CONTRIBUTION→GRADIENT。1CPU/8GiB，总计算上限2小时，无重试。
2. **输入干预**：A/B/Edge固定查询，FUSION790与ANCHOR790三个第40轮头及集成；真实8维、归一化置零、同设备同协议内两次固定置换，不改阈值。
3. **目标诊断**：仅源FIT，固定64×256查询与原TAIL采样；拆开正常/攻击BCE、TAIL和锚定。原融合40轮与锚定0/1/5/10/20/40轮共21点，不更新参数、不选轮次。
4. **结论边界**：本轮尚无机制结论。上轮锚定误报降低但UDP归零，科学FAIL保留；梯度近零不解释夹角，干预率不作部署成绩，源诊断不重建Adam历史。
5. **证据与存储**：[执行卡](collab/20261105_context_anchor_diagnosis_launch_codex.md)，`runs/context_anchor_diagnosis_v1_20261105/CHAIN_STATE.json`；大数组/逐批明细留超算，小汇总自动取回，[实时进度](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
