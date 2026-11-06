# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前完成**：源分数锚定v2三个头各40轮/96,560更新，源CAL集成182521完成；六阶段COMPLETED/0:0。正式训练44:48，成功链51:52，峰值3.307GiB。本轮无新评价作业。
2. **已验证变化**：27/127/227的FIT尺度相对旧头偏差+0.472%/+0.059%/−0.249%；127阈值从前版−23.315回到−20.400（旧−19.737）。只说明源尺度/阈值变化，不证明域外稳定。
3. **验收边界**：源CAL集成加权正常误报0.9788%，目标≤1%已满足；A/B/Edge本版成绩尚未产生，UDP收益、HTTP撤警和127误报仍待评价。源CAL达标不是泛化证据。
4. **固定下一步**：使用三个固定40轮端点、源CAL阈值、自身FIT尺度，统一评价A/B/Edge三种子和集成、RAW/C5；复用原四组对照。不凭Edge挑头/调参，保留用户接受的旧A/B取舍和旧FAIL。
5. **交接/存储**：见[训练验收](collab/20261105_fusion_score_anchor_training_acceptance_codex.md)与`runs/fusion_score_anchor_v2_20261105/FINAL_TRAINING_ACCEPTANCE.json`；120份逐轮头与所有大数组留超算，小回执和SHA本地封存。Edge已消费，仍属诊断评价。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
