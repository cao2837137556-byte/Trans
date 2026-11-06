# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **源域小试已启动**：v2；作业182577, 182578，当前TRAIN_PREFLIGHT_RUNNING。1CPU/8GiB，三阶段总预算2小时；尚未科学验收。
2. **固定方法**：原融合790起步，正常高分尾部风险＋攻击分数单侧保护＋正向8维贡献保护；冻结编码器、归一化及原阈值。每种子16,384行、5轮/320更新，27/127/227全报。
3. **自动门**：真实编码距离评价→三种子各8批训练/保存重读/源评价/预算→固定小试。45项远端依赖提交前PASS；失败停止，不自动全量训练或外部评价。
4. **失败与修复**：v1作业182576在3秒内因误列本地验收脚本失败，训练0。v2使用已交付依赖清单并提前核验；方法与worker字节不变，负例回归PASS。
5. **证据/存储**：[设计卡](collab/20261106_source_risk_preservation_pilot_design_codex.md)、[启动回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)，`runs/source_risk_preservation_pilot_v2_20261106`；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
