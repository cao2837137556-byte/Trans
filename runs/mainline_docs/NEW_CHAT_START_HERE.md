# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **已验收**：head_training_v2 九头与源 CAL 校准 PASS；总 869,040 次更新。训练累计 94分54秒，最大约 3.22 GiB。
2. **当前运行**：用户“允许运行。”后，evaluation_v1 真实预检 182427 已运行；自动顺序为 PREFLIGHT → CONTEXT → AB → EDGE。当前未宣称真实门或效果通过。
3. **冻结口径**：OLD782 与 REFIT782/STATS8/FUSION790，三种子及集成；源阈值/尺度固定。STATS8 只 RAW，其余 RAW/C5。报告全部注册组，科学 FAIL 不筛选或调参。
4. **证据/进度**：[启动回执](collab/20261105_device_context_evaluation_launch_codex.md) · [进度页](http://127.0.0.1:18806/)。1 CPU/8 GiB 顺序运行；预检/统计各30分钟，A/B/Edge各60分钟上限。
5. **接续/存储**：完成后先核验执行完整性，再解读 A/B 防退化、Edge RAW/C5 与裕量。模型/数组/分数留超算同名目录，小汇总/SHA 自动回本地；Edge 是已消耗诊断集。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
