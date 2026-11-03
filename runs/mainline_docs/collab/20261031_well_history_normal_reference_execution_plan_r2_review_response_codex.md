# Codex → well：历史正常参考方案 r2 只读复核

日期：2026-10-31。状态：`R2_REVIEW_COMPLETE_IMPLEMENTATION_WITH_EXPLICIT_BINDINGS_NOT_RUN`。

已核验 r2 SHA256 为 `dc566523f91256de7616391634bcfc348d1434e3a4227b0f8414122984a9dbf0`，旁侧校验文件一致，原稿未改。用户本轮只授权复核。本次读取源码、旧结果 JSON、已有包时间索引并做计数/时间边界核查；没有读取原始包内容或解码，没有补库、特征提取、编码、前向、距离/support、训练、A/B 新评价或远端操作。

**结论：r2 主体设计已连贯，可以按 r2 加本回复的明确绑定进入后续实现；无需再循环原则稿。原文仍有一处 DEV 数量冲突，且新历史数据不能直接喂给旧编码入口。这两点都有具体修法。另须把 PASS 固定在179700原观察期后主视图：三个未补设备在主视图均≤2%，全量视图却不是。** 本结论是技术复核，不是已经实现，更不是运行授权或2%性能保证。

本轮延续的主路径仅为 `P-DEVONLY / C1`。`P-ATTN` 作为将来科学修订保留，不编入自动分支，不因发现候选攻击材料而扩张本轮工作。

## Q1：新 capture_id / UID 与现行组件、编码回执的兼容边界

**组件规则兼容，前提是保留实际 owner、canonical key 的格式与精确设备/分区身份；不能保证跨年所有组件 digest 相等，也不需要所有组件相等才能支持查询。**

实际身份规则为：

```text
canonical_key = (protocol, *sorted(((src_ip, src_port), (dst_ip, dst_port))))
component_id  = digest([owner, canonical_key])
session_id    = digest([owner, capture_id, canonical_key])
uid           = digest([source_sha256, frame, owner])
```

`component_id` 不含 capture_id、日期或 source SHA。保持小写 owner MAC、协议整数、端口整数、原 IP 字符串以及同一 canonical 排序和 digest 序列化，**相同 owner/key 必然得到相同组件 ID**；换 capture_id 只改变 session namespace。跨年 IP/端口实际变化会产生新组件，这是原组件定义的正常结果，不能为了“对齐”强行映射成旧组件。

B 原查询元数据生产器也使用 `component_id=prep.digest([owner, namespace[2]])`，与新参考入口的定义一致。某些旧 B 元数据未保留 canonical tuple，不能从一个哈希字符串反推或伪造五元组。新候选必须由真实事件产生 canonical key。

同设备 own 查询按 `(partition, device, protocol)` 找参考库；2C资格统计参考中合法的不同组件，并不要求查询组件 ID 与每个参考相同。因此“新历史组件不同于旧查询组件”本身不是不兼容。相反，补第二组件正是其中一个作用入口。

设备桥接必须使用原查询身份：A 为 `partition=DEV, device=HeimVision Camera`；B 为 `partition=EXTERNAL_ARCHIVAL_EVALUATION, device=unsw-attack-traces-2018:<原小写MAC>`，不能把 B 的 display_name 当成 device 主键。新历史来源另存 origin 字段，不把 B 的评价设备重命名成 `unsw-iotraffic-2025:...`。

证据：[原 B 身份生产，第37行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/legacy_unsw_archival_data_v1.py:37)、[参考身份校验，第77行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_reference_v2.py:77)、[own 库选择，第286行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_core_v3.py:286)。

### 确实存在的入口假设，必须纳入实现

新字符串 capture_id 没有被当作 E3 数值特征；tokenizer 消费 flow 字段，owner/capture/UID用于来源与连接范围校验。但**现有生产入口对清单、快照和选点回执有严格约束**：

| 位置 | 约束 | 实现处理 |
|---|---|---|
| `continuous_features_v3.spool` 第57行起、第89行起 | 按 capture_id/frame 查固定查询，强校验 source SHA、session、UID、时间与参考/查询角色 | 新流清单与快照必须共用同一个规范 capture_id 和 source 身份；不能只改元数据名称而复用旧快照 |
| `constrained_onboarding_reference_v2.encode_selected` 第621行起 | 重新调用 `plan_banks(..., t0, policy)`，检查旧 B0/B1/B2 census/选点结果完全一致 | 历史“全部合法端点＋4096轮转”不满足旧入口的选点回放，**不能伪装为B2回执直接调用** |
| 同文件第644行 | 对每行调用 `reference_descriptor`，要求 `use=REFERENCE,label=0` | HIST-DEV 是查询，需走 `query_descriptor`；不能改成REFERENCE骗过编码校验 |
| 同文件第114行起、第165行起 | provenance 的 namespace、query_frame/time、body source 与行身份一致；参考帧界/截止合法 | 旁路原包号表不能替代这些强校验；需要新历史入口保留同等约束 |

**实现绑定：新建历史准备/编码入口，复用冻结 `Contexts/RecentState`、`reference_descriptor`/`query_descriptor`、tokenizer、形状分组批次校验及 E3 runtime；为历史选点建立独立版本的回执及确定性回放。** 旧 B0/B1/B2 入口保持原合同。分别输出 HIST-REF 与 HIST-DEV 的 UID、q14、E3和角色清单；A11行保留原UID与当前已存编码。新来源标识必须绑定真实派生对象或规范清单及原包定位，不用任意 hash 冒充原文件 SHA。

这是本次实现工作中的接口扩展，已有冻结数学与表示可复用；它不是需要先做科学试跑才能解决的问题。实现验收应证明清单回放、两类descriptor校验、原包定位及token/shape身份一致，不能只看“能生成768维向量”。

另须保留179700全量视图的旧参考重放处理：[matrix.py第234行](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_ab_stage_candidate_v1_20261028/src/matrix.py:234)原本设置 `allow_prebank_history=True`，核心仍逐行验证合法历史重放并令其支持为0。不能直接使用默认构造参数导致 `QUERY_IS_REFERENCE`，也不能据此允许新的 HIST-REF/DEV UID重叠；新历史角色仍严格隔离。

## Q2：历史参考完成截止取什么，字段绑定到哪里？

**建议取 HIST-REF 最后一个非空 UTC 日期的真实末包时间，采用该日期全部原包的末端，不取“最后一个选中参考点”的时间。** 同时绑定连续时间序中的原始前缀帧界。这里说的是事件时间的库可用截止，不是电脑完成预处理的墙钟时间。

r2前80%日期按“原始包实际出现的非空UTC日期”计数，排序后取 `floor(4*N/5)`；不先按协议/前端资格过滤，不把无包日补成日期。这使角色与前端可用位置的多少解耦。三台目前均有足够日期，REF/DEV都非空。

本轮直接读已存 `packet_index.npy` 和 `chronological_order.npy`，核验其 SHA 与原回执一致，再按上述规则汇总，得到以下**可用于实现的建议绑定值，尚未激活数据角色**：

| 设备 | 总非空日数 → REF / DEV | HIST-REF 完成截止（UTC） | HIST-DEV 首包（UTC） | REF连续前缀末帧 |
|---|---:|---|---|---:|
| TP Link | 32 → 25 / 7 | 2016-12-04 12:58:53.261023 | 2017-02-06 05:04:06.065969 | 66,004 |
| WEMO Power | 105 → 84 / 21 | 2017-01-10 23:59:59.863312 | 2017-01-11 00:00:51.673414 | 3,430,150 |
| Samsung | 119 → 95 / 24 | 2017-03-20 23:59:56.682107 | 2017-03-21 00:00:01.482691 | 4,419,000 |

对应 `reference_end_us` 为 **1480856333261023 / 1484092799863312 / 1490054396682107**。保存整数微秒作为审计主值，给当前核心的 `reference_end` 使用对应秒值；角色比较优先用整数时间。

三台截止都严格早于第一条 DEV 原包，因此也早于后续选中的合法 DEV 查询。Power 的两侧间隔只有 **51.810102秒**，Samsung 只有 **4.800584秒**；**到 REF/DEV 边界不得重置 Contexts**，它们可能仍有跨角色边界的合法近期上下文。DEV 查询可以因果地看到过去 REF 包，REF 快照不能反向看到 DEV 包。

现有 [时间索引回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/targeted_normal_raw_qualification_v1_20261031/TIMELINE_INDEX_RECEIPT.json) 的 `devices[i].packet_index`、`chronological_order` 和各自 SHA 是输入绑定路径；其中**没有已登记的 HIST-REF 完成截止**，因为原始准备阶段没有分配实验角色。不能复用现有2018 B2截止或整个历史成员的最终 EOF 来替代它。

建议未来历史准备回执固定这些字段（此处是字段规格，不是已生成的实验清单）：

```text
history_role_binding.devices[device].observed_utc_dates
history_role_binding.devices[device].ref_dates / dev_dates
history_role_binding.devices[device].reference_end_us
history_role_binding.devices[device].bank_end_frame
history_role_binding.devices[device].first_dev_time_us
history_role_binding.devices[device].first_dev_frame
history_role_binding.devices[device].raw_sha256
history_role_binding.devices[device].packet_index_sha256 / chronological_order_sha256
```

`HIST_DEV_BANK` 同设备、两协议的所有参考行使用这个统一截止和该历史 capture 的统一帧界，不能按各协议或被抽中的末行分别设截止。`AB_BANK` 仍使用该池原 B2 完整时间截止；其历史 capture 的帧界仍是 HIST-REF 前缀末帧，原 B2 capture 保留原帧界。两视图分别校验一致性，不能把2018 cutoff回填到DEV使用的历史视图。来源原始时间另存，不覆盖。

## Q3：P-ATTN 是否需要短修订？

**需要先把科学规则写成可审阅、可冻结的短修订；不能只在实现回执里写“与旧 FIT 禁区同构”就直接实现。** 可以是现方案的一段正式附录，也可以是独立短文件，不需要再起原则确认稿。

理由很具体：V1 的逐目标 FIT/攻击禁区在当时没有对应数据，参数并未形成有效冻结公式。新的 Nmap 或 UNSW 06-05 攻击通过身份/标签/输入资格验收，只证明这些点可以使用；**不自动给出 r_atk、距离定义、中心选择和对参考点的处理规则**。至少一台验收通过也不能替其余设备取得开发攻击保护。

短修订至少固定：实际资产/UID及与A/B的依赖隔离；中心选择与距离/半径来源；按设备/协议应用范围；过滤后组件不足和DEV门如何处理；工作量和停止条件。不能根据最终A/B结果再定半径。实现回执随后记录具体执行与校验结果。

当前 `P-DEVONLY` 不依赖这项未来修订，不需要为了进入C1实现而先下载或验收攻击候选。本轮没有启动它们。

## Q4：未补设备的179700 ensemble FPR是否已≤2%？

**在原主口径 `post_window_primary`，三台全部已≤2%，因此不能据它们判定本方案主视图PASS不可达。** 但 full 视图的答案不同，必须列清：

| 未补设备 | 观察期后主视图加权FPR | 全量视图加权FPR | 主视图≤2% |
|---|---:|---:|---|
| WEMO Motion Sensor | **1.187678421%** | 2.165410491% | 是 |
| Netatmo Camera | **1.012557277%** | 1.517006557% | 是 |
| Eufy Home Base | **0.000231911%** | 3.772558592% | 是 |

读取路径为已有各池 `RESULT.json` 的：

```text
arms["R-DENSE"]["0.1"].views[view].reports["ensemble"]
    .groups.device[*].corrected.normal.weighted_rate × 100
```

这两个既有结果均登记 `primary_view=post_window_primary`、`selected_lambda=0.25`。以上直接读取已保存的分组结果，仅把比例换成百分数；未按FP条数重建权重，未重跑预测。

来源：[A旧结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_ab_stage_dependency_repair_execution_20261028/result_retrieval_179700_20261028/unpacked/job_179700/science/matrix/CIC_DEV/RESULT.json)、[B旧结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_ab_stage_dependency_repair_execution_20261028/result_retrieval_179700_20261028/unpacked/job_179700/science/matrix/UNSW_DEV/RESULT.json)。

**实现绑定：PASS及IMPROVED_NOT_PASS使用179700原观察期后主视图；full按原权重并列报告，不能混写成绩。PASS要求主视图全部原评价设备FPR≤2%，不仅四台补库设备。** 如果另把“full也逐设备≤2%”加入硬门，在当前不补Eufy和Motion、固定工作点且own隔离的条件下，这个更强目标已被既有值排除；不能删除这两台或换分母规避。

## 还需明确的一处数量矛盾：DEV cap

r2 §0 R5、§1.5仍写每 `(设备,协议)` 各4,096，随后把DEV称为“同规则”且三台合计≤12,288。如果DEV也按每协议4,096，两协议三台上限是**24,576**，与保留的E3和距离预算不一致。这一处仍不能按原文直接实现。

**按 r1/r2 明确保留的预算，固定以下唯一解释：**

- HIST-REF：每 `(设备,协议)` 新增最多4,096；B三台合计最多24,576。
- HIST-DEV：每设备两个协议**合计**最多4,096；B三台总计最多12,288。
- DEV抽样在该设备全部合法DEV候选上执行一次有界组件轮转，component本身含protocol，使用r2盐；不再为两个协议各分配4,096。不用分数或标签选点。

为避免“确定的排序”仍留实现分歧，建议固定与现有 [subsample_dense](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_matrix_v1_20261027/src/binding.py:94) 同类的排序：点秩为 `(SHA256(salt+'|'+uid),uid)`；组件秩为该组件最小点秩；时间均匀目标及并列规则复用 `_uniform_time`。REF先在预算内给无旧锚点的新组件分配1个名额，然后用确定性轮转分配剩余名额；组件超预算也受同一排序和硬cap约束。DEV不借用“旧库锚点”优先级，直接对全部合法DEV组件分配总预算。

候选为空、一个角色无合法点时返回明确的输入/可评价性停止状态；RAW FP=0继续按r2的 `STOP_DEV_NO_ROOM`，不能把空集FPR填0或从三台门中静默删掉。以上是把已有单候选和预算落实为有限分支，不增加实验档位。

采用这个DEV cap后，先前静态上界仍成立：新增E3≤**36,864**，总距离对≤**579,614,444**。若改成每协议DEV各4,096，这两个上界就必须一起重写，不能沿用。本轮没有扩大预算。

## 实现交接判定

本轮未发现必须先换模型、修改组件定义或增加新数据才可实现C1的障碍。建议把 **Q1的新历史编码入口、Q2的双截止/连续上下文绑定、Q4的主视图PASS，以及DEV总cap修正** 作为 `r2 + Codex review bindings` 一起封入后续实现合同。旧编码器强制回放旧选点是需要新接口的原因；不能靠删断言或伪造B2回执绕过。

实现范围保持默认P-DEVONLY，不自动进入P-ATTN；A11行复用，无需为A重新解码。B的“10,233,818包”是输入包数量，不是自动保证仅一次读取：选身份后提取快照若采用两次顺序遍历，应如实计入墙钟/磁盘守卫。16GiB/8h仍是拟定运行合同，本轮不启动作业。

**可以结束本轮方案往返，下一项工作应是按上述绑定实现及工程验证；当前并未实施或验证真实效果。** 不承诺2%，也不把只读数据准备或本文的静态计数当作新实验。

[只读机器证据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_review_evidence_codex.json)记录已核输入SHA一致、原索引校验匹配、三台历史切分精确微秒/帧/原包号、两池既有主/全视图逐设备指标和明确建议绑定。没有激活新的参考/查询角色，原r2、原始数据和科学代码均未改。
