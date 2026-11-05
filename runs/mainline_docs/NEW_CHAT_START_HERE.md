# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3 不变；Edge 正式评价工程 PASS、科学安全门 FAIL。尚未训练或验收修复模型。
2. **诊断验收**：182279 预检 PASS；182280 COMPLETED/0:0、21分09秒、1CPU/8GiB。200条配对消融、Edge 60k跨连接统计通过，原始E3误差0，72个真实窗口暴力核对一致。
3. **关键结论**：A UDP攻击截单包仍64/64检出，不能以更长连接历史解释该切片优势；Edge 1s包速率AUROC：UDP 0.999986、HTTP 0.999214，仅为描述性可分性。
4. **证据/存储**：[验收报告与修复建议](collab/20261105_context_separability_acceptance_codex.md) · [验收/SHA](../context_separability_v1_20261104/FINAL_ACCEPTANCE.json)。大数组与逐条结果留超算，本地仅摘要。
5. **下一步/边界**：优先验证设备×协议因果8维统计；建议782/8/790维受控比较，先RAW再检查C5撤警。Edge已消费为诊断；新训练尚未启动，未新增小anti复核。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
