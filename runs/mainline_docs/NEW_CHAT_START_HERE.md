# 当前状态

更新：2026-11-07（America/Los_Angeles）。固定五项，历史另存。

1. **当前方法**：FUSION790＋完整历史参考＋C5_3D_OLD论文版本冻结；主权重、阈值、参考和部署不改。
2. **当前作业**：182719，基线复现一致性与第二批真实预检，1CPU/8GiB/2小时；71材料/17依赖通过，Linux结果待验收。18806六阶段进度，大工件留超算。
3. **重要更正**：首批TabM平均logit与作者概率集成不等价，v2改两类CE/概率平均；旧记录不删除，不用于正式TabM排名。新增TabR、SLAD及ModernNCA全源FIT池推断门。
4. **科学边界/下一步**：L1来源、L2语义、L3工程分开于L4作者任务成绩复现和L5充分训练；L4/L5仍待做。12候选不等于完成基线，不按输赢筛选，A/B与Edge已消费角色不变。
5. **交付入口**：[启动回执](collab/20261107_baseline_fidelity_second_batch_launch_codex.md)、[复现审计](../baseline_fidelity_v2_20261107/REPRODUCTION_AUDIT.md)、[执行卡](../baseline_fidelity_v2_20261107/EXECUTION_CARD.md)、[论文结果包](../paper_results_freeze_v1_20261107/PAPER_RESULTS.md)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
