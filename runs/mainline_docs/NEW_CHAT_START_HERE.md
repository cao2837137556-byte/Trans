# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：原 C5 p3 不变；Edge 既有科学安全门 FAIL，尚无修复模型训练或检测性能结果。
2. **最新验收**：流式预检 182314/完整门 182315 均 COMPLETED/0:0，20秒/2分7秒；112个真实查询及83个恢复查询零差异，FINAL_ACCEPTANCE=PASS。
3. **资源/限制**：1CPU/8GiB；UDP解码+统计8.44万帧/秒，压力流12.77万事件/秒、267.7MiB；NORMAL逻辑时钟最大超前854.643ms，须披露，112端点D0/D1相同不等于全局等价。
4. **封存/证据**：[训练规格](../device_context_stream_gate_v1_20261105/TRAINING_SPEC_FROZEN.json) · [最终验收](../device_context_stream_gate_v1_20261105/FINAL_ACCEPTANCE.json) · [报告](collab/20261105_device_context_stream_gate_codex.md) · [进度](http://127.0.0.1:18805/)。大工件留超算。
5. **下一步**：源原包/设备映射/完整特征UID及权重准入，真实训练与校准小切片；之后按OLD782/REFIT782/STATS8/FUSION790封存对照训练。每个新头计划1CPU/8GiB/30分钟，实际训练尚未提交。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
