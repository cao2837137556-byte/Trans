# 当前状态

1. **范围**：六基线；ModernNCA取消，主模型冻结，作者固定参数，大工件留超算。
2. **已有任务**：DTE/SLAD/CatBoost/TabM完成，Disent182805继续训练；只修复TabR。
3. **TabR根因**：182807整轮数值/恢复通过，但三种子总规划12.6天超过单作业7天。新包按种子拆为3个7天作业+afterok的1天评价，训练worker/CONFIG不改。
4. **重交**：预检182914已运行；真实链路、预算检查后自动正式提交，未提前宣称GPU训练已启动。
5. **接续**：baseline_tabr_seed_jobs_v1_20261108；客户端39556，接收端18880，进度18806。见[修复回执](collab/20261108_tabr_seed_budget_repair_codex.md)，先读PREPARE_COMPLETE/RESOURCE_RELEASE/子作业STOP。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
