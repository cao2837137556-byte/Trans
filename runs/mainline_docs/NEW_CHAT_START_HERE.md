# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **受限更新小试已提交**：作业182592，快照DECODE_PREFLIGHT_RUNNING；1CPU/8GiB，30＋30＋60分钟总上限2小时，尚无新科学结论。
2. **固定算法**：分层样本/原损失保持；每轮64批后全FIT保护验收，lr倍率1/0.5/0.25/0.125，失败恢复模型/Adam/RNG，全部拒绝则回退。三种子固定5轮保留端点。
3. **角色/成本变化**：全部FIT参与更新判断；未抽中梯度FIT不是验证集。每头名义320步、实际最多1280步、保留≤320步分别记账。CAL不决定更新，原科学门不放宽。
4. **自动门**：61项远端依赖及本地29项回归PASS；真实工程→真实源提案/全源检查/强制拒绝恢复/最坏预算→小试。失败或无可行进展停止，不自动扩量或外部评价。
5. **证据/存储**：[执行卡](collab/20261106_source_guarded_pilot_design_codex.md)、[启动回执](collab/20261106_source_guarded_pilot_launch_codex.md)；前序分层小试仍NO_GO、原FUSION790保留，大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
