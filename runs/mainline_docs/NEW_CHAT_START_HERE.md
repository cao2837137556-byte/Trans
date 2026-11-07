# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **四组统一评价已提交**：作业182628，启动快照PREFLIGHT_RUNNING；真实预检→A/B→Edge，当前无最终新成绩。
2. **固定模型**：原FUSION790＋均匀/分层/受限三轮小试，三种子及集成全报；保持原阈值、尺度、输入与C5，不训练、不筛种子，旧源侧NO_GO保留。
3. **最终目标直观展示**：普通/加权FPR<2%、检出≥99.9%分列；Edge HTTP/UDP分别报告，HT单列。RAW与C5分别评价，保留原科学安全门。
4. **自动门与资源**：27项远端依赖、本地15项回归PASS；真实Linux门通过才完整评价。1CPU/8GiB、30＋45＋45分钟；工程失败停止，效果失败照报，不自动重试或训练。
5. **证据与存储**：[执行卡](collab/20261106_pilot_transfer_evaluation_design_codex.md)、[启动回执](collab/20261106_pilot_transfer_evaluation_launch_codex.md)；大文件留超算，[进度页](http://127.0.0.1:18806/)随数据集完成更新成绩。A/B/Edge均为开发泛化诊断。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
