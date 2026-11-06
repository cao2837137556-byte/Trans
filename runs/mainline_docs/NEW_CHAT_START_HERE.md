# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **工程完成**：evaluation_v1 四阶段182427/182429/182430/182431全部PASS；总10分35秒，峰值1.662GiB。112行重编码、合法参考距离误差0；旧头全量评分复现。
2. **检出改善**：Edge集成固定样本，融合C5的UDP 0→98.66%，HTTP 31.195%→94.995%；OLD与REFIT所有已报告指标一致。
3. **科学未过门**：Edge融合C5正常FPR0.475%→5.79%；三种子0.735%/25.235%/0.255%，不可择优。HTTP仍撤警967条，设备级C5安全门失败；A/B RAW正常误报退化，源CAL通过。
4. **证据/口径**：[验收报告](collab/20261105_device_context_evaluation_acceptance_codex.md) · [复核回执](../device_context_evaluation_v1_20261105/COMPLETION_AUDIT.json)。A/B融合C5仍较好，不能将RAW与C5混报；全部组/种子保留，Edge为已消耗诊断集。
5. **下一步/存储**：先用已有超算工件归因正常误报、种子127失稳及尺度/分数变化，再定源域约束修复；本轮无新训练。大模型/数组/分数留超算，小汇总/SHA/裕量图已本地封存。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
