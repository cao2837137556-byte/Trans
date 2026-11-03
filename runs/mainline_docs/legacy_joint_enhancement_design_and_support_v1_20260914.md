# 旧 E3/P2 联合增强：材料落点与机制决策

日期：2026-09-14。状态：`DESIGN_AND_SUPPORT_REVIEW_COMPLETE / TRAINING_NOT_READY`。

用户在“落实能区分环境变化和攻击行为的训练证据”建议后授权“可以。动手”。本轮完成旧实现、已披露证据及候选元数据核对，并选择一个有条件的增强机制。没有启动实现或真实训练，没有重跑历史实验。

## 1. 本轮决定

继续以旧有效 E3/P2 为基线，优先争取攻击与正常 OOD 的共同改善，再做新设备入网。统一 GRU/全覆盖前端继续 DEFERRED。

优先候选：固定旧 E3、旧预处理，从 P2 权重的独立副本出发，利用有可靠标签和环境对应的正常—攻击对照，增加**同环境攻击分数高于正常的排序学习**。与同数据、同初始化、同预算的普通监督训练比较。现阶段不添加新投影头、教师蒸馏、正常否决门或全局设备子空间。

这是一项待验证的机制选择，**不是已冻结、可立即运行的配方**。决定性缺口是有效正常对照的标注依据、因果输入映射及独立来源支持；不能用一个损失公式代替这些材料。已有证据尚不足以认定新训练集、行数、配对数、学习率或损失权重。

本轮实际推进：定位到具体本地候选，核实七份保留连接日志现在确实存在，并查明为什么不能直接把它们转换成联合增强训练。下一节点是限定本地候选的标注来源和原始输入身份核对；不是重做 F4、旧设备配对普查，也不是先去登记下载 CIC。

## 2. 旧模型究竟是什么

源码：`repo/ood/issue27ckda_d1_representation_probe_v1.py`。

- E3 输出经 attention-mask mean pooling 后保存 768 维向量。
- P2 是 `769 → 128 ReLU → Dropout(0.1) → 1` 的 MLP，共 98,689 参数；多出的维度是输入缺失标志。
- 历史训练为类别均衡逐目标 BCE，AdamW，50 epochs；它已是神经网络检测头。
- 旧 normalizer 及 P2 已接触后来新路线 CHECK 的部分目标；不能将新模型继承旧权重后仍描述为只见过新路线 TRAIN。
- 保持历史数值语义：float64 标准化，完整特征转 float32，再进入原 P2。候选另存，旧基线不覆盖。
- 更细粒度 token/burst 输出在 forward 中产生，但未保存为现成缓存。改变读出需要重新计算合法因果前缀，不是本轮的零成本选项；mean pooling 也不等于所有时序信息都已丢失。

旧输入范围仍是有合法会话、时间和包头条件的 TCP/UDP。按输入事实预先限定范围，不按模型结果删困难样本；范围外默认报警不计为学习到的攻击能力。
每个目标只用判定时可得的因果前缀；未来训练、校准和检查必须考虑全部旧 fit 接触及会话/上下文依赖，不能只按新行号拆分。标签、角色和教师正确性不进入输入或缺失掩码；旧 normalizer 不利用新查询重新拟合。

## 3. 本地训练材料已经落实到哪里

以下是既有统计和元数据的接续，不是本轮重新扫描标签或计算模型分数。

| 材料 | 已证事实 | 对本次增强的意义 |
|---|---|---|
| 旧 P2 fit | 18,398：14,013 正常、4,385 攻击；其中 ToN 正常 4,000、攻击合计 4,000（两个攻击来源各 2,000），combined-cycle 也有 33 攻击 | 可作为历史监督与能力保持的起点；不能说旧所有环境都只有一种标签 |
| 旧训练中的混淆 | 4,000/4,385 攻击来自 ToN；排除 ToN 后，按粗域多数标签预测可达 99.68% | 说明来源捷径具有强数据基础；不是其已被证明为全部性能瓶颈 |
| 两个原 ToN 攻击 fit 来源 | `normal_scanning1.pcap`、`password_normal1.pcap` 各 2,000 个历史目标 | 有已有原始输入映射经验；未选连接仍需重新认定目标身份、角色和依赖 |
| CKBT 未选连接 | 扫描经 hash modulus=4 抽样后 9,511 exact joins，密码经 modulus=16 后 5,561；各选 2,000 | 15,072 不是完整总体，差额 11,072 不是已合格的 E3 新训练目标 |
| 七个 ToN reserve | 历史清单为 `reserved_not_used`、used_rows=0；本轮只做文件 stat，7/7 当前存在 | 可具体追溯后续使用和原始包映射；历史 zero-use 不等于本轮已证明从未使用或 fresh final |
| ToN `normal_1.pcap` | 旧正常 fit 原始来源，存在已有输入资格限制 | 不能把多抽正常记录等同多得到有效 E3 正常行为；也不增加独立环境 |
| Gotham 原始 69,492 support 候选 | 已有候选池，只选 512→385 train+127 val；其余有未启用政策 | 数据存在不等于自动可训练。新角色、标签预算和依赖隔离未定；不得继续冒称原 few-shot 预算 |
| Gotham 后加 160 | 历史认定与旧 query 的时间关系不合法 | 继续隔离，不能与上述原始 support 余量混为一谈 |
| CKDD 的 4,986 困难正常 | 六个 select 来源；62 个划分无合法独立 split | 不是新训练增量；不得把它们搬入 TRAIN 来制造进展 |

七份候选来自：
`runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/reserved_toniot_conn_sources.csv`。

它们在 `D:/study/paper/anomaly_detection/paper04/datasets/external/ton_iot_raw_network/extracted/` 下的相对路径为：

| 相对路径 | 本轮存在 | 文件字节数（仅 stat） |
|---|---|---:|
| Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning3/conn.log | yes | 74,133,985 |
| Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning4/conn.log | yes | 443,592,404 |
| Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning5/conn.log | yes | 34,298,214 |
| Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning6/conn.log | yes | 22,928,180 |
| Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal2/conn.log | yes | 50,505,172 |
| Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal3/conn.log | yes | 50,379,296 |
| Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal5/conn.log | yes | 36,617,959 |

这些是 conn 日志的存在和大小，**不是对应 PCAP 已存在、正常配对成立或可用样本数**。

## 4. 新发现的关键限制：攻击事件表没有提供正常标签

已封存的 `runs/issue27ckam_toniot_bro_groundtruth_schema_audit_v1_2026-07-09/groundtruth_schema_time_label_audit.csv` 记录了 18 份 GroundTruth 表：

`ts | src_ip | src_port | dst_ip | dst_port | proto | type`

没有额外二元 label 列；记录的 type_counts_json 均为命名攻击类型，没有显式 normal。GT1 是 scanning；GT14 同时含 ddos 和 password。因此：

- **没有匹配上攻击事件表，不等于已证明正常。** 不能用补集制造同采集正常负例。
- 文件名中的 `normal` 不能替代标签；同一编号也不能自动证明 conn、GT 和 PCAP 一一对应。
- 这不证明整个混合捕获都是攻击，也不证明 ToN 的所有官方数据都没有正常标签。
- 同环境对照可以来自有独立正常性依据的另一捕获，只要设备、业务、采集条件的可比性有来源证据；不强加“必须同一文件”或入网阶段的严格前后时序作为所有基础增强的前提。

另有一条已定位的正常标注线索：历史 2026-04-20 intake 记录
`D:/study/paper/anomaly_detection/paper04/worktrees/data/Train_Test_Network_dataset/train_test_network.csv`，明确 `label=0/type=normal` 50,000、攻击 161,043。本轮仅确认该文件仍存在，**未打开数据行**。它已参与旧第二环境 smoke/precheck/evaluation，因此不是新确认集，也不能自动变成当前 TRAIN。只能先从已有 schema/provenance 记录核对能否提供独立标注依据及 raw 身份桥接；其原角色和已暴露事实不可抹去。

不要再重复统计上述 18 份 GT 是否有正常类。真正待查的是：是否有可追溯的正常标注/正常采集说明，与允许使用的原始目标对应。

## 5. 条件机制与最小比较

设 `s(x)` 为旧 P2 结构候选头输出的攻击 logit，`P_e` 为有真实环境对应的训练正常—攻击对。候选方向为：

`L_candidate = L_BCE + lambda * mean_e mean_(a,b in P_e) softplus(-(s(a)-s(b)))`

这只是明确学习作用的候选表达，lambda、环境权重、配对预算和训练预算尚未冻结。第一版不以所有正常向量聚到一个中心为目标，也不额外引入跨环境“同名攻击必等价”的一致性项。来源身份仅用于合法训练关系构建，不输入部署头、不路由阈值。

成对项意在让模型在环境相近时仍能区分行为。**它本身不消除环境偏置**：同环境两分数同时加常数，差值不变。因此它既不保证跨环境全局阈值可用，也不能直接宣称学得因果不变性；全局监督和独立环境上的低误报检查仍然必要。

| 比较对象 | 用途 |
|---|---|
| R：固定旧 E3/P2/normalizer/原阈值 | 保留真实旧能力参照，不重训历史模型 |
| B：旧 P2 副本，旧合法监督＋合格新增监督，普通 BCE | 判断补充有效训练材料本身带来多少能力 |
| C：与 B 相同，只增加上面的真实条件对照项 | 判断该学习关系是否有额外收益 |

B/C 必须匹配 E3、normalizer、初始 P2、旧监督重放、行呈现、标签信息和训练预算。B 也拿到 C 使用的全部训练行；配对注释成本单独披露。不能用 C 多看标签或更多旧攻击保护样本解释成机制优势。
普通 BCE 基线同样采用这些环境分组和相同抽样产生的行权重、重复呈现次数，避免把环境均衡或重采样收益归因于排序项。

未来候选阈值只能按预先定义的合法校准规则产生；B/C 使用同一规则，R 保留原阈值。也比较匹配误报条件下的攻击排序，不通过读取开发报告尾部反向选训练对或部署阈值。

如果 B 已共同改善且 C 无可靠增益，应采用 B；额外机制不是必须保留。若两者仍权衡，不能把下一动作默认为调 lambda、换 seed 或更长训练。

## 6. 怎样认定有实质进展

- 分别报告已见攻击、future 查询、各攻击族、ID 正常接受率和各正常 OOD 池；future 不冒称全新未见攻击族。
- 关注匹配误报水平下检出率，以及 1%/0.1% 误报区间；这些是设计关注点，本轮未新建冻结门槛或重算分数。
- 保留 street/stream 的旧低误报优势，不能只报告 hydraulic/predictive 的改善；总体均值不能掩盖最差正常环境或隐蔽攻击。
- 补入训练的正常环境只能支持“已覆盖正常环境”的说法；留出的新设备/环境才承担泛化证据。旧 expanded 始终是已暴露开发参照。
- P2 原始总体 97.37% 含范围外默认报警，不是纯已见攻击检出率；新路线小 CHECK 99.76% 也不是独立旧系统能力证明。
- 外部 E3 预训练完整排重未证；当前 CHECK 接触、标签预算增加和旧模型训练经历全部披露。99% 是目标，不是本轮新增无限前置门槛。

## 7. 历史与文献如何约束本次设计

| 证据 | 本次采用的结论 |
|---|---|
| CKDA P1→P2 | 同 E3 下曾有攻击与 OOD 共同改善，联合提高并非必然零和；只是开发证据 |
| CKBW | 来源/攻击族平衡、困难尾部 margin 已实际尝试，低 OOD 误报未保住 future；不能换名重试 |
| CKDD | 停在训练与验证支持不可辨识，尚未训练；不等于所有 E3 头增强都失败 |
| CKDC/Q/S | 不能把正常分支 veto、标量阈值移动、固定 rank4 去设备子空间当未试突破；这些失败也不穷尽所有学习机制 |
| MatchDG，ICML 2021 作者摘要 | 标签相同不足以证明语义匹配；不能由同名攻击构造虚假的跨环境因果对 |
| CLAD，2026 原文 | 对比学习可利用正常与已知攻击，但单正常中心不自动适合本项目多种正常模式；跨网络泛化仍属其未来工作 |
| pAUC/DRO，ICML 2022 官方摘要 | 支持关注低误报排序；不提供本项目跨环境保证，也不能补齐正常监督 |

文献入口：
- https://www.microsoft.com/en-us/research/publication/domain-generalization-using-causal-matching/
- https://arxiv.org/html/2601.09902v1
- https://proceedings.mlr.press/v162/zhu22g.html

这里的排序项不是新损失的发明。只有真实条件监督在同数据对照下带来可重复的能力增益，才值得进一步讨论方法贡献。

## 8. 接下来的具体工作与停止条件

下一项是**限定本地材料的标注与原始身份核对**，输出唯一可审查的候选表；其元数据范围见同名 support_scope JSON。

1. 接续已有 ToN loader/schema/intake 元数据，核对可靠正常标注来源、原 fit 的原始目标身份和七 reserve 的后续角色。已完成的文件存在核对、GT 类型普查和旧设备普查不重跑。
2. 明确能否建立合法正常—攻击环境对应；没有独立正常性依据时，不把未匹配 GT 当正常。已暴露 train_test 表不直接用作新 TRAIN 或确认集。
3. 只有上述身份足以支持具体对象，才提出一次有限的训练侧标签/原始映射核查；逐目标特征生成、真实训练和评估另有明确范围，不能借“动手设计”自动执行。
4. 若本地支持只有更多攻击，记录为攻击侧增量候选，不能称联合增强已就绪。当前没有自动外部下载、CIC 登记、HPC、扩大前端或另开模型搜索的 fallback。

原始 conn/GT/PCAP、模型权重与数值缓存本轮未打开；未解封 select/viewed/report/FINAL 数值。读取范围为代码、已披露文档、现成聚合/schema/来源元数据以及指定文件 stat。没有旧模型性能新结果。

独立静态审查已完成：确认环境偏置限制、未就绪状态和旧 fit 口径；按审查澄清 ToN 正常/攻击数量，并补充普通基线的抽样与权重匹配。本记录和 support_scope JSON 均有 SHA256 侧车，JSON 保存 18 项来源身份；未为文档变化运行模型测试。

solved: 定位真实本地增量线索，区分攻击余量与正常监督缺口；明确旧 P2 结构及一个条件机制与同数据比较。
changed_mainline: no（保持旧系统增强优先，入网随后；具体候选方向已明确）。
active_blocker: 可用正常标注、原始输入映射、环境对应与独立角色尚未认定；不是已证模型能力上限。
frozen: 旧资产、历史门槛/分母/seed/结果、八项无关修改、输入与访问边界。
superseded: 由候选 conn 数直接推算 E3 新训练量、由 GT 未命中认定正常、由更复杂头保证提升的推断；未改写任何旧冻结结果。
next_action: 有限本地标注来源/原始身份核对；形成可落地训练支持后再冻结执行配方。
