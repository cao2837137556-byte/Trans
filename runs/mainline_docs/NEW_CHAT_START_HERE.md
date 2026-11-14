# 当前状态

1. **同资料阈值对照已完成**：183937 COMPLETED/0:0，4:26，峰值约 1.48 GiB。79,069 条参考、388,202 条查询、1,472 项基准指标、27 个回传文件验收通过。
2. **主要比较**：同款 SYN 保护下，CIC p4/重校准为 18/43 条误报、79,050/79,056 条攻击告警；UNSW 为 130/1,561 条误报、攻击均 72,543。
3. **Edge**：p4/重校准为 0/27 条误报，HTTP 19,958/14,972，UDP 19,732/0。结论限定于固定 1% 校准规则与本批查询，完整库 p4 继续作为主结果。
4. **结果入口**：[论文结果](../same_information_recalibration_v1_20261113/received/RESULTS_FOR_PAPER.md) · [本地验收](../same_information_recalibration_v1_20261113/LOCAL_RESULT_AUDIT.json)。上一轮 D/M/C0/C1 [结果](../reference_evidence_round1_v1_20261112/received/RESULTS_FOR_PAPER.md)保留。
5. **接续边界**：新增实验另定范围；只读结果使用接口和本地文件。超算连接由用户手动建立，启动命令优先交用户粘贴，避免屏幕捕获引发光标问题。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
