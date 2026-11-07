# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：四项只读归因与三维C5离线验证v2；真实预检182645通过（1:20），完整182646已运行，最终结果待验收。
2. **固定方案**：原FUSION790、原阈值、三种子及集成；源正常校准rho_c，二维/三维×当前/旧源尺度，无新训练。
3. **已修工程问题**：182644失败90秒，A/B两小时库误与历史扩充库混比。v2分列现行C5与候选同库对照，严格复现门已通过；不热改旧包。
4. **下一步**：验收RAW漏检物理分组、STATS8贡献、1158正常误报/967HTTP撤警及A/B/Edge直接成绩，再决定后处理或训练路线。减分C5不能突破RAW检出上限。
5. **证据/进度**：[执行卡](collab/20261106_context_geometry_attribution_design_codex.md)、[启动回执](collab/20261106_context_geometry_attribution_launch_codex.md)、[进度页](http://127.0.0.1:18806/)；完整保守估算81分钟、上限88分钟。大文件留超算，后台自动取摘要并生成runtime回执；旧NO_GO保留。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
