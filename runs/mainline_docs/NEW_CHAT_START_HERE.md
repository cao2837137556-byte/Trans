# 当前状态

1. **结果已本地取回**：183551六项p4控制完成；183558恢复TabM p3评价并完成p4衔接，统一小回执验收PASS。原183549失败现场保留，183552失效依赖已替换。
2. **正式入口**：runs/p4_tabm_acceptance_v1_20261111/FORMAL_ACCEPTANCE.json；controls、tabm_p3、tabm_p4各含指标JSON/CSV、配对与主表。大分数、模型、UID gzip仍留超算。
3. **论文回传**：见[最新回传说明](paper_writing_v1/experiment_results_p4_and_tabm_codex_20261112.md)。完整库MLP p4仍是选定主结果，TabM未自动晋升；所有种子/视图/加权/HT和代价保留。
4. **参考压缩**：发现4936条严格等价历史冗余候选，未删库、未验证压缩性能；来源展示字段asset_key已在派生回执纠正，指标不改。
5. **长期停止约束**：提交正常且进度可用后立即结束，无新要求不轮询/验收。2026-11-12光标恢复已由用户确认，退出清理规则补入AGENTS；结果读取优先本地/既有通道，不再开界面捕获。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
