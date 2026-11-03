# 独立集成审计（源基线子任务）

结果：工程准备方向与冻结方法一致；第一轮发现的 kNN 误套 C5 门和数组缺少 ordered UID 检查已由主 agent 修复，本审计再次读源码确认接通。其余正式 worker 与同运行时交付事项仍待完成，不能据小切片 PASS 直接称全量外部执行就绪。
影响：未发现需要改 p、λ、银行选择或攻击定义的科学理由；问题集中在工程合同和回执真实性。
下一步：由各文件负责人修复下面的接口，再冻结执行卡；本审计没有运行模型、距离、训练或云任务，没有修改其他人的文件。

## 必须修复或在正式 worker 中明确接通

1. **已修复：独立 kNN 不再走 C5 单调安全断言。** `evaluation.report_view` 新增 `independent_methods`，标准 kNN 允许新增 RAW 阴性告警，仅报告独立检测器的撤回/新增数，不强制经过 suppression-only 门，并明确只有一个距离分数。C5/p3 不能被放进 independent_methods，p1/p3 保持原配对门。
2. **真实攻击行缺少 scenario。** `adapter.metadata` 输出 `source_role=HTTP/UDP`、`activity=UNKNOWN`，却没有 `scenario`；评价加权和安全函数要求它非空。应显式映射为预登记捕获场景，不能用 UNKNOWN 假造独立事件。
3. **预检解码需重新绑定实际原包 SHA。** `selected_snapshots` 直接按路径解码并用卡中的 SHA 生成 UID，`run_preflight` 只在 INPUT_PINS 核了校准和模型等资产。人口盘点曾验过原包，不代表随后预检所读字节仍相同。须在本次真实切片实际读取前验 raw SHA/size，并在结束后确认未变。
4. **完整视图包含 commissioning 中被选作参考的原始查询 UID。** 人口盘点保留这些合法原包行是正确的；冻结 core 默认不允许 reference UID 同时进入 query 距离入口。正式 worker 必须给整个 pre-bank 窗口走确定性的 RAW 路径，或使用现有合法 prebank-history 合同，完整视图不能把这些行丢掉。当前预检特意 reference/query UID 不交叉，因此并未覆盖这个全量风险。
5. **已修复：评价数组强制 ordered UID 连接。** `report_view` 新增必传的 `raw_uids`、`prediction_uids`，每个方法须与 metadata 行完全同序；主 agent 另新增反向 UID 但相同 shape 的拒绝回归。

## 执行卡和回执需保留的限制

- 预检只输出运行、有限值、形状、协议、算术和身份结果；未输出个体外部决策或外部 FPR/召回，符合工程范围。
- `engine.source_parity` 如实限定为首 16 条保存源 E3/q14 经冻结头的比较；本地 score 有浮点差异、四工作点决策相同，不能称 raw→E3 源逐位相同。最终 Linux/Python3.11 同交付门尚需实际通过。
- `execution_gate` 的卡内预检字段、真正预检产物 status（`SAME_RUNTIME_REAL_SLICE_E2E_PASS`）、runtime identity 和哈希应由明确构造步骤绑定，不能人工把本地 PASS 换成同运行时 PASS。
- 最终距离预算要合计 C5 支持距离与独立 kNN 距离；p1/p3 应复用同一支持，不能漏计 kNN 或重复计 p1/p3。当前 fixture 的 `distance_pairs_reserved` 仅是 C5 次数，另有 kNN 字段。
- 当前代码展示的是正整数预算和授权阻断门；正式 worker 仍须真正执行 CPU/RSS/磁盘/编码行/距离对/墙钟上限及不自动重投，不可把字段有值称为已执行资源限制。
- **正式全量 worker 尚未实现。** 当前交付可以封存工程准备成果和待完成项，不可标记为整个正式实验已就绪；执行卡的 READY 状态必须在上述完整人口、回退、资源与最终同运行时门全部接通后才设置。
- EligibilityOnlyStore 不能输出任何数值快照，实际执行冻结 append 的 owner/poison/taint/last_seen 资格逻辑；选中帧重放重新执行完整数值 Contexts，保持原包顺序，边界重置且没有用角色过滤上下文。这个设计未发现数值状态被伪造成模型输入的问题。
- kNN 使用 E3 信息子集但没有额外数据，属于同信息预算的独立标准对照；应表述为使用相同冻结表征，不应说它也使用 q14。p1 仍是机制消融，不能替代独立基线。

本次只读复核未重新执行主 agent 的九项评价测试；该通过数来自主 agent 回报。本审计独立确认了新增分支与 UID 断言的源码，未新跑模型或距离。其余模块若后续修复，应以新的检查回执覆盖对应待办，不能把本稿当成修复后仍全部存在的缺陷清单。
