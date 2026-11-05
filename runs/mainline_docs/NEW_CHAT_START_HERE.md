# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5 p=3保持冻结，外部固定NORMAL/HTTP/UDP各20k评价已完成，不据结果改参数或挑选候选。
2. **工程验收**：预检182071、正式182089均PASS；182089 COMPLETED/0:0、1小时53分、1CPU/8GiB，复用42,428条旧编码，完整64,124条编码/60,000查询。
3. **效果结论**：ensemble样本误报84.03%→0.475%，HTTP关联召回66.33%→31.195%；p3及p1全部种子/ensemble安全门FAIL，UDP所有方法均0。
4. **存储/证据**：大数组和完整快照留超算；本地重要结果已核验。[结果交接](collab/20261104_edge_182089_formal_results_codex.md) · [验收](../edge_formal_evaluation_resume_v2_20261104/VERIFIED_ACCEPTANCE.json) · [结果页](http://127.0.0.1:18799/)。
5. **下一步**：只读诊断UDP基线盲区与HTTP PSH_ACK撤警，区分工程PASS与科学安全FAIL；尚未提交新实验，未新增独立审查。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
