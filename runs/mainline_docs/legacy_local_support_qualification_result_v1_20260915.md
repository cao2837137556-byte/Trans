# 旧系统增强：本地材料资格核对结果

日期：2026-09-15。状态：`LOCAL_SUPPORT_QUALIFICATION_COMPLETE / JOINT_TRAINING_NOT_READY`。

用户授权“动手下一步吧”后，完成上一轮明确的本地标注来源、原始包对应和角色元数据核对。没有训练、评分、历史重跑或下载。

## 1. 决定

**现有已审查材料不足以支撑选定的联合增强机制。结束对这批本地候选的重复资格核查，下一步准备最小规模的新增正常／攻击原始支持包。**

原因已由一般的 UNKNOWN 落实为具体缺项：七份 reserve 缺对应本地 PCAP；现有带正常标签的表缺唯一时间/连接身份；若干攻击事件表存在时间覆盖缺口和重复文件。它们不能靠改损失或拼接文件名修复。

这不等于所有本地数据无用，更不等于模型能力已到上限。旧 E3/P2 及其合法训练材料继续保留。原 `normal_1.pcap` 的同源覆盖诊断可以另有价值，但不再作为本次条件机制的默认前置步骤。

主线顺序保持：**增强旧有效系统 → 新设备入网 → 独立验证与论文完善**。统一前端/GRU路线继续 DEFERRED。新材料首先服务基础检测能力增强，不自动切换为先做入网。

## 2. 七份 reserve：原始输入缺口已查清

对限定的 `D:/study/paper/anomaly_detection/paper04/datasets/external/ton_iot_raw_network/` 树做文件名清单核对；其中只有六份 PCAP，均在 `raw_pcap_pilot_v1/`：

| 现有原始文件 | 历史角色 |
|---|---|
| normal_1.pcap | 正常 fit |
| normal_2.pcap | 正常 select，仍排除训练 |
| normal_scanning1.pcap | 攻击 fit |
| password_normal1.pcap | 攻击 fit |
| injection_normal1.pcap | reserved internal report，仍不启用 |
| MITM_normal1.pcap | reserved internal report，仍不启用 |

还只读了该树中三个 ZIP 的 central directory：`raw/Network_dataset_Bro.zip` 928 项、`raw/SecurityEvents_Network_datasets (1).zip` 18 项、`raw/OneDrive_1_2026-7-9.zip` 31 项。PCAP 成员数及嵌套压缩成员数均为 0，没有解包或读取日志/数据成员内容。

因此，七份 reserve 的 conn.log 虽然存在，却**没有对应的本地原始包资产或已验证映射**。此结论限定于上述目录、其三个压缩包和现有映射记录，不声称搜索过用户所有磁盘。

根据既有 conn/GT 聚合时间区间，完成全部 18 份 GT 的候选区间核对：

| reserve | GT 时间区间候选 | 资格结论 |
|---|---|---|
| normal_scanning3 | GT4 | 仅有时间候选；无原始 PCAP、无逐连接精确关联 |
| normal_scanning4 | GT4/5/6/7 | 跨分片，不能指定单一 GT |
| normal_scanning5 | GT7/8 | 跨分片；旧 top-8 候选列表不是完整对应表 |
| normal_scanning6 | GT7/8 | 跨分片 |
| password_normal2 | 无 | 现有 GT 时间覆盖缺口 |
| password_normal3 | 无 | 现有 GT 时间覆盖缺口 |
| password_normal5 | GT15/16 | 两份 GT 字节相同，去重后仅一份候选；仍无精确关联或原始包 |

password2/3 的记录区间位于 GT14 结束 `1556295451` 与 GT15 开始 `1556323577` 之间。GT15/16 的相同 SHA 来自已封存 file_inventory：`d1d4cb491cb6edda3523f7424d24ea1afd4496a933e60b3ec357286f7f0f542f`。本轮没有重读或重 hash GT 数据体。

时间重叠不是标签验证；时间未覆盖也不是正常性证据。对角色相关文档、manifest/source/index/contract/identity/metadata 的限定检索未找到七份 reserve 后来启用的记录；仍不将此扩大为“绝对从未使用”或 fresh final。

## 3. 正常标注来源：已有标签，但身份桥接缺失

本地 `worktrees/data/Train_Test_Network_dataset/train_test_network.csv` 只读取第一行 header：共 44 列，有端点、协议、成熟连接统计及 label/type；**没有 ts/timestamp、UID、capture/source 或原始行标识**。

因此，不能仅按五元组或相似统计值，把它的正常标签贴回另一个 conn/PCAP：连接可重复、统计相似不构成唯一身份。禁止近似匹配后当作已证训练标签。它曾参与旧第二环境 smoke/precheck/evaluation，暴露与角色事实保持不变；本轮未读取数据行。

本地官方说明文件补充了关键区分：

- `ReadMe.pdf` 说明 processed 从 raw 生成并标注，Train_Test 为其选取样本；标签依据攻击主机地址和时间。该说明不能被外推为“本地 GT 未覆盖即正常”，攻击主机身份也不进入部署特征。
- `Network Features-Description.pdf` 的官方字段包含 ts、label（0 正常、1 攻击）与 type，说明完整官方材料原则上有可用标注字段；本地 44 列表不保留同样的时间字段。
- 官方 `Statistics of Network Records.pdf` 记录 Train_Test 正常 300,000；本地旧结果记录正常 50,000。二者不能未经身份核验当作同一完整文件，不能从当前表猜回裁剪前行号。
- 既有 CKAK inventory 中 298 个 CSV 身份分解为 280 个 Bro 导出和 18 个 GT；没有另一个已经认定的完整带时标 processed 网络标注表。这里是清单身份核对，未扫描这 298 个文件的数据行。

这关闭了“直接拿现有 44 列表给七份日志补正常标签”的方案。正常标签本身并非不存在，缺的是允许使用且可唯一对应原始目标的标签来源。

## 4. Gotham 候选余量：只增加攻击，另有一处来源冲突

读取现成 source_chunk、taxonomy、region 三张元数据表：69,492 个候选覆盖 16 个 chunk、10 个攻击标签、3 个设备组，preferred capture 为 6 个；正常候选为 0。未选行仍保持 `pending_forbidden_until_explicit_issue`，没有激活为 TRAIN。

另核实一处不能静默修正的来源冲突：chunk13 / ip-camera-museum / Mirai C&C / 250 行，region 表写 `raw/malicious/mirai-dos/...`，source_chunk 表写 `raw/malicious/mirai-infection/...`。

源码说明两字段来路不同：`region_manifest.pcap_path` 来自 materialized sidecar 的 `pcap_member`，而 `source_chunk_manifest.pcap_member` 来自计划中的 `preferred_pcap_candidate`。**不能宣布计划字段必定比 sidecar 正确，也不能因攻击名称相似就选路径。** 若未来启用这部分候选，需要其真实物化 provenance 核验；本轮没有读取逐目标 sidecar、表示或标签数组，也没有改写旧表或旧结果。

原始 69,492 候选与后来被隔离的 160 行是不同对象，后者继续隔离。这批攻击余量不提供当前缺失的正常监督，不能据此宣布联合增强数据就绪。

## 5. 为什么不继续默认普查 normal_1

旧 `normal_1.pcap` 是已有正常 fit 来源，其历史角色不撤销。N0 的完整旧目标口径为 4,000，其中旧 A 843、B 3,157；某个历史 terminal 子集的 29/3,186 不能替代全源比例，更不能外推整份原始捕获。

更多同源包或会话可能增加正常训练覆盖，但不会自动提供新独立环境或同设备/业务的可靠正常—攻击对应。目前没有证据足以把一次新的单源普查列为本机制的必要下一阶段。将其保留为可选覆盖诊断，**不再用它延续本地资格循环**。此取舍已由两位独立审查代理核对。

没有据此否定所有基于旧数据的微调；只是当前拟验证的条件学习机制还缺所需监督，不能先训练再补解释。

## 6. 下一项具体交付：最小新增支持包

下一项应落实**一批有原始包、正常与攻击标签、可核实环境关系的数据对象**，而非再写一份模型路线图。先取得对象清单与标注结构，列清最小获取范围和字节预算，再进行经授权的数据获取与资格检查。

| 必须取得的材料 | 必须回答的问题 |
|---|---|
| 原始 PCAP/PCAPNG 对象身份、发布路径、大小、校验依据 | 旧前端是否有真实可处理输入；不能只取得成熟连接特征表 |
| 完整带时标标签或明确正常捕获／攻击捕获说明 | 正常性如何证明；如何唯一对应目标；未匹配是否只是未知 |
| 捕获、设备、业务及攻击场景的关系 | 正常与攻击是否有实际可比环境；编号相同不构成对应 |
| 训练与独立开发检查的来源及依赖关系 | 能否分开验证；新确认与旧暴露池不得混称 |
| 旧输入范围内的前瞻纳入规则 | 只按合法 TCP/UDP、头字段、会话和时间条件纳入；不按预测结果删样本 |

可先接续已经调研的 CIC IoT2022 正常工作捕获／受害设备攻击捕获的目录与标注证据，目标服务旧系统增强。该候选仍停在成员身份未取得的状态；不声称已配对、兼容或能提升，也不提前承诺具体下载文件/字节数。取得 ToN 的完整带时标标注与确切对应原始包同样可解决材料缺项，但七份现有日志不能替代这些缺失对象。

这一记录不授权登记、下载、解封、HPC 或训练。新材料若缺关键对应，则停止该候选；不自动转回前端重建或在同一批旧标签上继续换损失。原数据的冻结角色、分母、seed、模型、损失、门槛与历史科学判定不变。

## 7. 本轮验证与边界

完成两项并行独立核对：标注/文档身份与原始包/GT对应；主代理核对 Gotham 元数据、来源字段语义及研究取舍。9月14日两份输入侧车和18项来源 pin 均匹配。

仅使用现成元数据、代码、本地官方说明文档、文件名清单、ZIP central directory 和一行 CSV header。未读 conn/GT/PCAP 数据记录、未读旧评估数据行、无模型加载/推理/训练、无网络下载或 HPC。本轮结果是材料资格结论，不是检测能力结果。

结果 JSON 保存本轮结论、关键来源身份及访问方式；本文和 JSON 配 SHA256 侧车。HEAD/分支保持不变，8项既有无关修改保护不变。

solved: 七reserve的原始输入缺口、GT范围/重复、44列表桥接失败、Gotham纯攻击余量及来源冲突均已具体化。
changed_mainline: no（旧系统增强优先；结束本地候选重复核对，准备新增监督材料）。
active_blocker: 尚无已合格的新增正常—攻击原始支持包；不是科学训练失败。
frozen: 旧系统、既有协议/结果、原角色及无关修改；当前候选机制仍未具备可执行配方。
superseded: 再次普查七reserve或将normal_1单源普查作为默认主线门槛；未覆盖GT推正常；以preferred路径直接替代真实provenance。
next_action: 落实最小新增支持包的对象清单、标签/原始身份与获取范围；不再重复同一轮本地资格审计。
