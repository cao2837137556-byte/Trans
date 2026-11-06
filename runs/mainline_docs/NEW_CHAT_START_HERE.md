# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **覆盖诊断已提交**：v1，作业182585，启动快照PREFLIGHT_RUNNING；1CPU/8GiB，预检30＋完整60分钟。尚未完成解释验收。
2. **回答的问题**：源FIT缺语义支持、实际小试遗漏/低覆盖，还是已覆盖仍有误报与攻击分数下降；先查原因，再改训练。
3. **固定对照/边界**：原每类8192行、同样本数层级加权抽样、均匀每类16384行；只由FIT构造成员。三种子及集成全报；训练更新0，CAL仅描述，不做新外部评价。
4. **前序小试结论**：源攻击召回100%、8维总体贡献保留；CAL加权误报仅相对降4.91%，攻击p01下降略超门，科学NO_GO。原融合790仍保留。
5. **证据/执行**：[设计卡](collab/20261106_source_coverage_audit_design_codex.md)、[启动回执](collab/20261106_source_coverage_audit_launch_codex.md)；52项远端依赖PASS，真实预检通过后自动诊断、失败停止。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
