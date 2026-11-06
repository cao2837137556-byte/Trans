# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：固定五组A/B/Edge评价真实预检182554运行，1CPU/8GiB；通过后自动AB→EDGE。未宣称预检或新效果通过。
2. **固定模型**：ANCHOR790三种子27/127/227第40轮端点、源CAL阈值、自身FIT尺度全部固定；编码器/归一化/因果8维/C5规则不变。无训练、无选头或调参。
3. **完整对照**：OLD782、REFIT782、STATS8、前版FUSION790、新ANCHOR790；三种子及集成，RAW/C5（STATS8仅RAW）。原四组须复算分数/判定与封存数组一致。
4. **验收重点**：正常误报、127稳定性、UDP检出、HTTP撤警/裕量；保留原A/B分母/权重与全部科学门。已接受旧A/B取舍，仍不自动放宽新结果；Edge为已消费诊断评价。
5. **交接/存储**：见[评价执行卡](collab/20261105_fusion_anchor_evaluation_launch_codex.md)及`runs/fusion_anchor_evaluation_v1_20261105/CHAIN_STATE.json`；工程失败停止，科学失败继续报告。大数组留超算、小结果自动取回，[实时进度](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
