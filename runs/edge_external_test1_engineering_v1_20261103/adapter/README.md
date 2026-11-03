# Edge 外部测试 1：适配器与人口封存

结果：全部 5,074,623 个原始记录已按原顺序完成资格清点；正常合法查询 1,334,562，HTTP 直接场景 152,352，UDP 直接场景 2,898,830。正式参考选点为 4,124 行。未做全量编码、距离或外部效果评价。

影响：正常头部候选中的 296 行因原有同 namespace 时间回退规则不可评分，必须单列为未评分；它们没有变成正确阴性，也没有悄悄修复时钟。完整视图仍包含早期 commissioning 正常查询（包括最终入选参考的同一 UID），其判定强制精确 RAW。

下一步：消费已锁定的小切片完成实际编码、距离、决策与回执的工程预检；全量运行仍需执行卡、同运行时门与用户评价授权。

## 接口

`edge_adapter.py` 直接导入 repo 的冻结 `continuous_input_v3`。`selected_snapshots(role, frames, working_directory, reference_frames=())` 消费完整未过滤前序，输出 `uid / row / body / q14 / info`。`body` 保留 frozen `flow / state / provenance`。每次 replay 在前后核对 raw SHA256、大小与 mtime。工作目录须不存在。

`row.frame`、provenance 的帧号以及 UID 都使用原始物理帧。正常间隙仅建立新的 capture namespace，并把新实例的连续帧检查计数器初始化为该段首帧减一；所有数值状态、poison/taint/last_seen ledger 均重新开始。`logical_frame` 是映射审计字段，不参与数值输入或 UID。

`prebank_query_for_reference(entry)` 将同一物理参考观察作为完整视图早期 QUERY 重用：不改 UID，不重编码，服从原 `require_prebank_history` 合同，支持度必须为零。

## 全量人口与参考

`population_v1/POPULATION.json` 是无数值状态的资格清点回执。它调用原 frozen `Contexts.append`，状态值存储替换为禁止 snapshot 的资格专用 sink；owner、协议、完整头部、last_seen、永久 poison、taint 与 idle-reset 分支仍由原函数执行。

`population_sealed_v1/POPULATION_SEAL.json` 将原清点与精确协议/flag 计数、实际编码可用量、场景元数据和最终参考文件绑定。这个后续封存没有改写原清点，也未改变 UID、参考选点或资格。

人口通过每原始记录两个字节的掩码封存，共 10,149,246 字节。首字节表示正常早期/正常后窗/HTTP 直接/UDP 直接/场景外；次字节表示合法或明确不可评分原因。UID 有序摘要与原包、映射、代码一起绑定。没有保存数 GB 的 JSONL 查询人口或 token。

正常主视图合法人口为 TCP 1,217,724 加 UDP 2,402；早期合法人口为 TCP 114,408 加 UDP 28。全部 296 条不可评分均为后窗 TCP。

参考按原 B2 全量 last-per-component census 先选 64 个 anchors（TCP 52 / UDP 12），再调用原 dense planner，获得 TCP 4,096 / UDP 28。新域实际已有编码行数为 **0**；planner 内的 encoded-UID 输入只表示计划先编码的 anchors 优先级，不是编码完成证明。全部 4,124 行成功编码且按 UID 对齐后，完整 bank 才能生效。

## 验证及边界

- `test_edge_adapter.py`：10 项通过，包括同 key 永久 poison、跨 key 回退、缺头 taint 与真实 idle reset、缺 namespace 硬失败、帧偏移数值等价、跨段清空、原包被改时拒绝、early reference 同 UID RAW 查询。
- `real_parity_v2/PARITY.json`：三个真实原包各前 4,096 条未过滤记录，资格 sink 对完整冻结数值 Contexts 的逐行 allowed/reason/events 与 namespace/poison/taint ledger 完全相同。这是人口资格门，不等同 encoder 或完整 E2E 门。
- `preflight_plan_r2_stratified/SLICE_FRAME_PLAN.json`：在任何新域模型输出前锁定的 65 个工程逻辑观察。normal TCP/UDP 参考与查询、HTTP SYN/PSH+ACK/ACK-only、UDP 直接攻击均有覆盖；参考子集仅用于工程预检，不能当作正式 4,124 行 bank。
- 原包均保留原 SHA、时间与顺序；没有排序、拼接或从攻击/后窗查询补参考。
- 全量 UDP 有 2,898,538 个 namespace。完整数值状态与全量 E3 输出的磁盘开销必须在正式预算中单独计入，不能把本次 10 MB 资格掩码当作完整运行存储量。

本文不宣称 source E3 逐位一致、HPC Python 3.11 同运行时 E2E 通过或任何外部误报/召回成绩；这些由工程集成回执分别报告。
