# Continuous input core repair v2：运行前版本化修订

2026-09-28。依据双方已对齐的 `collab/20260928_continuous_repair_v1_reply_claude.md`，由 Codex 实现；本文件只修订下列明确内容，其余遵循 v1。父合同 SHA256：`1d56d61a6207608d58994e3d33f160f21c2c7146981385b763eeb41812c37eda`。机器合同位于 `runs/legacy_continuous_input_core_repair_design_v2_20260928/design_contract.json`，用其最终 SHA 绑定执行器。v1 文档、合同、代码及归档保留，不原地修改。

授权范围是版本化修订、实现、合成验证、封包和已有结果的 D1 复算；没有真实 PCAP 解码、真实 E3 前向、优化器、校准、评估或远程动作。真实 P/T/K 链未启动；本轮工程通过不能代表真实预检通过或模型能力恢复。

## B1：按连接隔离时间倒退

始终按连续 frame 顺序处理，不排序或重编号。单调性以 owner/capture/canonical 5-tuple namespace 内的整数纳秒时间为准。键内倒退后，该 namespace 永久 poison 到 capture 结束；60 秒空闲重置和物理状态回收都不能解除。此前已输出的合法快照不可回溯修改。跨键或范围外的捕获级倒退只分类记录。

任何异常帧或 poison 后帧若属于固定 reference/FIT/CAL/DEV UID，立即 STOP，不删行、不替换、不改分母。P 中使用原 `ScopedPrefixes` 和原 `BoundedNetfoundPrefix` 同帧重放旧 float 资格，逐帧比较 namespace、NEW_TIMESTAMP_REGRESSION、POISONED_PREFIX、INCOMPLETE_TARGET。旧回执只有聚合计数，不能冒充已有帧级证据。新增整数纳秒倒退即使被旧 float 舍入隐藏，也保存证据后 STOP，不迁就计数。

每个异常记录包含 frame、namespace、新旧分类、时间、cap_len/frame_len、缺失字段名及固定目标 UID。先行和主重建两次异常流、目标身份流的摘要必须完全一致，计数相同不够。frame 流摘要与源 SHA 联合固定身份。

## B2：查询资格与上下文资格分离

旧实现先 append，再判 headers_complete/cap_len；因此“旧查询无效”不等于“旧上下文没有该帧”。v2 分别处理：

- 仅 payload 截断、所有必要头字段完整：更新最近头部上下文和 state26，不作查询。若该帧竟在固定目标中，STOP。
- 必要头字段缺失：不填默认值，不添加 token，不更新 state26。namespace 被标记为历史不完整，其后的固定目标在 P 停止。不能仅因缺失帧已离开保留的 72 包就解除，因为指数衰减状态还有更长历史。
- 只有在相邻合法作用域事件之间出现严格大于 60 秒的间隔时，才能证明整个历史应已重置，从全空状态解除“缺失头历史”标记。恰好 60 秒不可解除；这不解除 B1 的永久 poison。
- 若必要地址/端口缺失，无法可靠识别 namespace，直接停止并记录；不能使用旧解析器的默认零端口制造一个看似无关的连接。

后续普通事件在历史不完整期间也不更新不可信状态；一旦存在固定目标就停止。没有固定目标受影响且出现上述可证明完整重置时，才允许后续恢复。先前合法快照保持不变。

## P 的顺序和成本

先核对封存元数据/UID、权重、原始文件身份、Bank 全部边界时间、参考唯一性和错误参考 donor；再单独依次验证 `active-00`、`active-01`、`unsw-benign-20180528`、`unsw-mixed-20180601`，不进 E3。四个捕获只做异常与固定目标依赖验证，目标必须逐个存在且身份相同。全部通过后，正式重建仍按原 capture_id 排序，所有捕获同时审计；完成封存后才允许 E3。

本轮选中源捕获 **217** 个、外部 **2** 个；302 是完整 catalogue 条目数，不是本轮选中的源捕获数。静态回执及 SHA 清单见 `anomaly_receipts.json` / `anomaly_receipt_pins.json`。active-00 的倒退/poison 为 1/346，active-01 为 2/7424，UNSW 不完整查询为 14/2；这不是对真实 B2 类型的预判，分类仍须在授权后的 P 实测。

额外成本为上述四个捕获的一次解码，不是全量再扫描一遍。全部核验和解码耗时计入原 70 小时程序上限。12 小时 T+K 储备只是预算，不是训练/评估用时保证；内存上界也不是实测结果。超限或异常停止、零自动重试，不缩分母。有限状态的物理回收与 >60 秒的语义重置分别处理，namespace 顺序记录仍有一百万上限。

## D1：加权主门槛与历史对照

两池主攻击门槛使用原 metadata 中 `1/label_metric_weight_denominator`：ensemble 池级 ≥99%，ensemble 设备级 ≥97%，每个 seed 池级 ≥97%。未加权 TP/总数/召回并列保留。CIC 与旧 Q 的 79045/79056 比较继续用未加权召回，最大下降 0.1 个百分点。正常加权 FPR、逐 UID 零新增攻击漏检、适配收益门槛不变，所有 gate 常数读取封存合同。

每设备/速率组报告 TP/总数及加权、未加权召回，展示小支撑组的不稳定性，不新增门槛。缺少 attack_rate 的 CIC 标记 NOT_AVAILABLE，不虚构速率组。

已有 Q 的 D1 复算已完成：

| CIC DEV Q | TP/攻击数 | 未加权召回 | 原权重召回 |
|---|---:|---:|---:|
| ensemble | 79045/79056 | 99.986086% | **99.938458%** |
| seed 27 | 79046/79056 | 99.987351% | 99.944053% |
| seed 127 | 79045/79056 | 99.986086% | 99.942579% |
| seed 227 | 79047/79056 | 99.988616% | 99.949648% |

ensemble 设备级：Eufy 加权 100%，HeimVision 加权 99.876916%。因此本次不存在旧基线无法达到加权 99% 的冲突；这仅是历史基线可行性，不保证 v2 通过。即使旧基线不达标，也只能说明旧基线未达标，不能逻辑上推出新训练必不可能通过。

复算脚本 `check_d1.py` 验证历史 evaluation_DEV 文件封存、179886 个 UID 的顺序、原 manifest SHA 与 UID SHA、攻击权重与旧层级权重一致，读取保存的 Q 决策/概率和原阈值，不运行模型。完整结果、逐设备/seed 和输入 pins 见 `D1_weighted_feasibility.json`。

## 其他报告与验证修订

zero-vector 分别给出 CAL/CIC/UNSW 阶段增量及累计调用行数；查询/参考可能重复调用，不能解释为唯一样本数。添加手算 TCP/UDP header、双向 seq/ack oracle，与当前包 token/张量一致性验证并行。

UNSW 的 WEMO Motion Sensor（`ec:1a:59:83:28:11`）和 Samsung Camera（`00:16:6c:ab:6b:88`），各取固定攻击 UID 中按 timestamp/frame/uid 排序的前 6 条，保存 P 阶段当前包证明及 K 阶段各臂分数、决策、阈值和新增漏检。只作描述性诊断，不设专用阈值、不追加训练。RECENT 与 RECENT_STATE 的逐设备/速率组比较仍按原臂设置，不能将统计增益自动解释为 E3 内容泛化。

没有更换 E3、模型、损失、seed、训练轮数、学习率、样本或分母。1,095,200 个新特征行、12 个 head、三个 seed、40 epochs 不变；source FIT/CAL 与 consumed CIC/UNSW DEV 身份不变。独立 ID 仍 NOT_RUN，外部 DEV 已使用，不是独立确认。论文继续暂停。
