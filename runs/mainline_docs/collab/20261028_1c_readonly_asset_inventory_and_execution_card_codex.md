# Codex 回传：只读资产盘点完成，固定 1C 下一卡已缩小

2026-10-28。依据用户“可以动手下一步”，已完成 [well r1](20261028_well_next_direction_after_p1_r1_after_codex.md) 与 [r1 复核](20261028_well_next_direction_after_p1_r1_review_response_codex.md)建议的只读资产/角色/分母盘点，并写好独立执行卡草案。

**盘点 PASS，没有运行新候选，也没有新的 A/B 指标。** 详细证据见[中文结果](../../one_component_readonly_inventory_v1_20261028/RESULT_REVIEW.md)、[总验收](../../one_component_readonly_inventory_v1_20261028/INVENTORY_ACCEPTANCE.json)、[独立 1C 卡草案](../../one_component_readonly_inventory_v1_20261028/CARD_DRAFT_NOT_AUTHORIZED.md)。

## 本轮实际结果

1. **766,727 条源记录已逐 UID 明确角色。** G0 HELD=509,233 原 FIT＋122,470 原 CAL；G1 HELD=108,675 原 FIT＋26,349 原 CAL。原 CAL 分别占完整 HELD 攻击权重 21.563746%/20.058333%，不能整批回流规则设计。导出保留原角色、评分头、时间/组件和分母，子集不重写原 HELD 权重。
2. **12 个已有分数端点、32 份旧报告复现通过。** 计数精确、加权指标误差≤1e-12。只导出原 RAW margin，未选新 cut。源盘点56.448秒、峰值约0.918GiB、73输入SHA前后不变；主头58文件hash/header/metadata盘点4.922秒、36历史SHA匹配，含原P2的26输入。
3. **允许开发的原 FIT 部分确有困难攻击材料。** G0 BASE ensemble 的 HELD∩原FIT 中，TCP_OTHER 原TP最小margin约0.002471；同头CAL最小为31.020047。此为RAW材料盘点，尚无相应DENSE支持、margin或candidate cap，不能写保护PASS；不混用原CAL，也不恢复独立验证身份。
4. **主头固定 1C 输入已齐，实际支持仍未知。** 完整源库4728行，仅Atomi TCP符合12位置/1组件。既有102813个合法攻击/donor对中，9643对q14已证零支持，93170对等待实际joint计算；本轮未补算。主头原logits、normalizer、半径、scale、cut、λ=.25全部已核对。
5. **发现并避免一种资产误用。** 已有 `source_actual_trace.npz` 的 corrected字段属于旧稀疏参考；不是完整密源D0。两折own-FIT logits、合法DENSE基线与逐UID修正仍缺，不能从原P1或主头直接移植。

## 下一卡为何只需一个小差分

独立卡选择主头源CAL上的固定1C机制审计：仅改变Atomi TCP donor的12个位置。原2C在该单组件donor上严格support=0，所以**受影响分支D0=RAW**；未改变donor继承经核验的179602全攻击零撤回证据。正常仅计算合法own差分，全量正常结果若输出则标为“保存D0汇总＋精确差分”，不伪造逐条密源trace。

建议停止预算：2CPU、0GPU、2GiB RSS、30分钟、1GiB输出；最多148819×12个距离对、256query分块。预算不是实测时长，执行runner尚未实现/运行。无需新训练、前向、编码、两折D0重建或A/B输入。

该卡允许“机制审计完成、迁移保护证据不足”结项。真实q14上界早已证明当前源CAL四suffix零撤回，计算support不能把这个无边界压力的集合变成未见设备安全证据。不会自动登记1C、扩大λ或启动两折/A/B/P2/P3。

本轮新前向、训练、编码、距离/support、阈值选择、A/B输入、远端任务均为0。方向稿与原结果保持；完整证据包入口为[README](../../one_component_readonly_inventory_v1_20261028/README.md)。
