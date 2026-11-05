# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **已验收**：head_training_v2九头与源CAL校准PASS；各40轮/96,560更新，总869,040。九头累计94分54秒，最大内存约3.22GiB，校准182392用时22秒。
2. **当前结果**：集成源CAL加权FPR：REFIT782 0.974305%、STATS8 0.977863%、FUSION790 0.999757%；这是校准成绩，A/B与Edge新检出结果尚无。
3. **方法/复现**：冻结768编码器，原FIT/CAL/权重不变；8维仅FIT归一化。REFIT782三种子阈值/尺度及集成阈值与原记录精确一致，不声称逐参数全部一致。
4. **证据/进度**：[验收报告](collab/20261105_device_context_training_acceptance_codex.md) · [复核回执](../device_context_head_training_v2_20261105/COMPLETION_AUDIT.json) · [进度页](http://127.0.0.1:18806/)。九头和校准均结束，当前无训练作业运行。
5. **接续/存储**：按已有授权做OLD782锚点与三新组A/B防退化、C5安全性/裕量及Edge诊断（STATS8只RAW）；评价尚未提交。模型/分数/数组留超算head_training_v2同名目录，仅小回执/SHA回本地。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
