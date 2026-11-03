# 外部候选复筛：下一步建议查 Edge-IIoTset 三包，ACI 保留

2026-11-02（America/Los_Angeles）。状态：`METADATA_RESCREEN_COMPLETE_BOUNDED_RAW_CARD_READY_NOT_EXECUTED`。

**建议将 Edge-IIoTset 作为下一次有界原包资格对象；ACI-IoT-2023 作为另一条保留线。当前没有新数据集通过完整外部资格，不能开始模型评价。** 本轮已完成官方小资料筛查及三个 Codex 本地子代理的独立工作；这些不是 Antigravity/Claude 的回复。本稿可按既有文档方式转给他们复核。

本轮授权为其他候选的官方元数据、小说明与获取规划。本轮实际只取得网页、目录、README、注册元数据与一份相关作者论文；未下载新PCAP/CSV、编码、计算距离、训练、提交云端任务、移动或删除旧数据。C5 p=3 和 A/B 开发冻结保持，冻结JSON哈希仍为 `ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7`。

## 1. 候选比较

|候选|本轮已核实|尚缺的决定性证据|当前处理|
|---|---|---|---|
|**Edge-IIoTset**|作者官方目录52文件，其中10正常PCAP、14攻击PCAP，原包目录总2,205,925,238字节；7,348字节README已得；作者论文给edge/sensor/AP IP和采集方法|同物理目标跨包、实际先后/完整7200秒及后段正常、直接ACK/UDP攻击标签/方向、设备/事件独立量|**下一次有界资格对象**；未判合格，不盲下全包|
|**ACI-IoT-2023**|官方列32.27GB PCAP与2.5KB时间表；真作者论文DOI已核，摘要支持物理IoT与五天采集|时间表/README未取得，DataPort订阅门控；正常事前7200秒、身份、ACK/UDP仍未知|保留；有合法访问时只先取小表，不先取32GB|
|**MedBIoT**|83个真实+模拟混合设备，三种真实设备类型；公开原PCAP，正常标为部署恶意软件时的leg流量|真实物理受害者、可信事前正常、完整上下文、7200秒与攻击向ACK/UDP|暂不下载；不把83当83台真实受害设备|
|**CIC IoT-DIAD2024**|官网公开两类派生CSV及README，引用CICIoT2023|独立原始PCAP与采集血缘未建立|当前公开包不适配冻结原包前端；不按新年份算新独立集|
|IoT-NID / IoT-DS-2 相似名称|有限搜索未绑定唯一官方语料|精确DOI/作者/机构/数据源身份都未建立|不作为可执行下载目标；不宣称不存在|

HCRL五分钟正常、IoT-23不同设备正常历史、已暴露ToN/Gotham及CIC2023名单重叠的旧限制保留，不重复下载。CICIoMT2024仅暂停**当前已得正常/攻击组合**；本轮没有淘汰整个CICIoMT2024或删除已得原包。

## 2. Edge-IIoTset 论文补证为何有用

作者官方 Kaggle 的单文件 API 返回仅含论文的ZIP；成功传输5,119,317字节，解压论文5,445,952字节、CRC/目录大小吻合，SHA256 `8c21d1339ecdc4dfa59ffbec408c6c8ff3b148a255c53e67fe3c5ad1a1397a39`。root对这一份已知大小论文使用6MiB上限；此前子代理5MiB限制只是本地探索预算，不是用户禁止读取论文。旧初筛回执保留；root另建 `edge_paper_check/` 补证，不覆盖旧SHA。

- §IV-A-3/4（PDF11–12页）：正常与攻击在2021-11-21至2022-01-10不同日期/小时产生，正常明确**不连续**，一次捕获**最多3小时**。这使两小时窗口有核验价值，**仍不能证明实际任何文件≥2小时、更不能当51天连续正常**。
- Table VI（PDF13页）：首行温湿度场景的edge `192.168.0.128`、sensor `192.168.0.101`、AP `192.168.0.1`，其他场景也有IP表。缺MAC/序列号，跨文件相同IP不等于同物理设备；9个不同edge IP也不等于9台不同硬件。
- Fig.1和§III-F（PDF6/9页）：物理传感器、Raspberry Pi MQTT edge和虚拟化应用都存在。须分清实际攻击对象，不能把打到边缘服务器/VM的攻击全部写成物理传感终端受攻击。
- Table V与§IV-B（PDF11–13页）：有HTTP/UDP攻击工具、来源IP，但不是完整逐事件victim/时间表或逐包真值。HTTP、C&C之类名称不证明直接ACK攻击，反向响应不能代替。UDP伪造源需按文档与实际方向核实。

root完整读相关页并查看拓扑/表格渲染；同一子代理随后独立读取这些新增页面，支持有界三包资格对象选择，仍判未合格，见 `edge_paper_check/INDEPENDENT_REVIEW.md`。

## 3. 已准备的具体原包卡：本轮未执行

草案：`runs/external_dataset_rescreen_v1_20261102/RAW_QUALIFICATION_CARD_DRAFT.json`。预先固定官方三文件，不按检测分数或最小包大小选设备：

|官方相对路径|目录未压缩字节|目的|
|---|---:|---|
|`Edge-IIoTset dataset/Attack traffic/DDoS HTTP Flood Attacks.pcap`|28,307,602|核实直接非守卫TCP攻击候选、实际受害目标和方向|
|`Edge-IIoTset dataset/Attack traffic/DDoS UDP Flood Attacks.pcap`|247,560,012|核实直接UDP攻击候选、实际受害目标和方向|
|`Edge-IIoTset dataset/Normal traffic/Temperature_and_Humidity/Temperature_and_Humidity.pcap`|345,868,816|Table VI第一行明确角色的正常场景；检验同目标可信历史及完整两小时|
|总上限|**621,736,430（约621.74MB / 592.93MiB）**|仅资格核验，不是外部评价人口|

顺序是先两攻击候选，再匹配这一份固定正常场景。若攻击角色明确不对应该场景/物理目标，则停止，不继续下载正常、不自动换另一台。IP对应只是候选线索，最终还需MAC/官方角色/真实时钟，不能靠同网段凑配对。

核查只读容器、时间、缺口、链路/MAC/IP、上下文与重复、协议位和官方标签方向、正常SYN分布及同协议合法组件覆盖；不跑E3、分数、support或距离。合法标注无法分出攻击向ACK/UDP则如实失败/未解决，不用反向ACK或“攻击文件内所有包”充数。同协议参考不可用时保留RAW回退事实，不能把未启用修正模块的零撤警称为保护验证。

只准这3个单文件获取；网络累计草案上限700,000,000字节，D盘受控目录及解压临时峰值1.3GB，不碰C盘Downloads，不取全量zip。失败下载计入预算，未通过不扩大、不平移/拼接时钟、不追加模型实验。原包实际SHA、完整性与真时间只有拿到后才能填。用户若批准下一阶段，则按此卡实施；**本次只有卡，没有下载**。

## 4. ACI 的具体下一材料

官方页 <https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023> 仍需DataPort订阅；普通IEEE账号不自动等于文件权益。取得合法访问后先拿2.5KB Attack Timesheets、README、设备MAC/IP/角色表和归档成员目录。

真正作者论文为 Nack / McKenzie / Bastian，MILCOM2024，DOI `10.1109/MILCOM61039.2024.10773916`。物理设备与五天采集目前来自二级索引收录的作者摘要，未取得论文全文/实际时间表，不能写成原包证明。公开页另引 `10.1016/j.jiixd.2024.09.001` 是第三方检测论文，不是采集作者论文，已纠正引用。

没有学校/个人订阅权益证据时不要求购买，也不假称已有文件访问；本轮不绕过登录、不联系作者或第三方。

## 5. 交付和下一步

完整资料位于 `runs/external_dataset_rescreen_v1_20261102/`：

- `aci/README.md`、`ACI_QUALIFICATION_FACTS.json`、来源及SHA：ACI作者/访问/缺口。
- `edgeiiot/README.md`、`QUALIFICATION_FACTS.json`、`OFFICIAL_FILE_MANIFEST.json`：取得论文前的原目录审计快照。
- `edge_paper_check/README.md`、`PAPER_FACTS.json`、论文、相关页文本/渲染及独立复核：当前补证。
- `medbiot/README.md`、`FACTS.json`；`secondary/README.md`、`FACTS.json`：次级排除边界。
- `RESULT.json`、`VERIFICATION.json`、`RAW_QUALIFICATION_CARD_DRAFT.json`、`PROGRESS.md`：本轮综合与下一阶段卡。

下一步是**有界原包资格查验**，不是训练或正式外部评价；外部适配器、权重、强基线与一次性执行卡仍待资格通过后接线封存。若下一阶段原包也不满足合同，应记录失败，不以改观察窗或改p迁就。原有大文件全部保留，没有自动清理，也没有持续AI监测。
