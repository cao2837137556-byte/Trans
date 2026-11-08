# 当前状态

1. **范围**：用户移除ModernNCA，最终六基线；仅推进TabM/TabR/Disent-AD，主模型冻结、无搜索、大工件留超算。
2. **现有结果**：CatBoost与SLAD完成；DTE182778第三种子仍训练，未重新训练旧模型。
3. **本轮执行**：共享真实预检182796 RUNNING，8CPU/24GiB/2h；通过后各方法GPU整轮门独立放行三种子训练/CAL/A-B-Edge评价，尚不称全部资源通过。
4. **参数边界**：TabM/TabR源整组验证早停后全FIT重训；TabR全候选CPU FAISS精确检索+GPU网络；Disent最低训练loss100轮；三方法本地跨进程恢复精确通过。
5. **进度与接续**：客户端35108、新接收端18878、进度页18806；新包baseline_remaining_three_v1_20261108。见[启动回执](collab/20261108_remaining_three_baseline_launch_codex.md)，先查询该包PROGRESS/STOP/QUALIFY/RELEASE再判断阶段。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
