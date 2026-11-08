# 当前状态

1. **范围**：用户明确固定7个基线，不再扩至8–10；主模型冻结、作者推荐/默认、无搜索、大工件留超算。
2. **已获结果**：CatBoost与SLAD三种子训练评价已完成，效果已向用户报告；DTE最近查询仍训练。此轮未重新查询运行状态。
3. **本次审查**：TabM/TabR/Disent-AD/ModernNCA本地小张量构造/反传通过，仅审查证据，非Linux全量资格。未启动新作业。
4. **具体发现**：Disent保存最低训练loss，不能采用控制台最佳测试AP；NCA默认周期拼接单张量float32约139.91GiB，30.89GiB不是总峰值；TabR历史dropout改名证据尚未核实。
5. **后续**：补TabM源组隔离早停及合适硬件整轮、TabR参数绑定与检索资源、Disent固定适配资源、NCA可用内存；进度客户端34636保持既有首批流程。见[审查回执](collab/20261108_remaining_four_baseline_audit_codex.md)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
