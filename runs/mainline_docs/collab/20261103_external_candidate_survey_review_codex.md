# 外部测试 2 候选调研复核（Codex）

结论：SHARP、BCCC、ACI 均保留为待核候选；本轮没有第二个数据集通过完整 S1–S6。
影响：候选稿的大方向可用，但有几处规模、标签及获取方式必须纠正；不能据网页摘要启动大包下载。
下一步：优先核对合法 DataPort 权益下的 SHARP 文档与 ACI 时间表，BCCC 先补设备/时序/标签小资料；本轮无需用户下载原包。

2026-11-03（America/Los_Angeles）。逐项回应 [Claude 候选稿](20261102_external_candidate_survey_claude.md) 第 4 节。依据 [统一范围条件](../../external_scope_review_codex_20261103/SCOPE_CRITERIA.json)，只看资料与原始采集事实，不看模型输出。本文的 Codex 子代理复核不是 Claude/Antigravity 的新回复。

## 1. 第 2 节事实与出处核对

|候选|可证实的事实|需要修正或保留未知|
|---|---|---|
|SHARP|当前 [官方页](https://ieee-dataport.org/documents/sharp-smart-home-attacks-across-residential-multi-protocols) 确认 Cardiff 三位作者、CC BY 4.0、2026-09-20 创建；正常 2025-06-20 至 07-05，受控活动 08-13；1,677 = 512 路由器/IP + 779 Wi-Fi + 386 Zigbee；完整包标示 172.24 GB。|36 条是 **attacks and tests**，不是 36 个成功 IP 攻击。核心说明中 22 包是全量中的子集，不等于已找到可单独下载的小包。IP 攻击种类、逐设备时长与实际方向仍未知；“没有配套论文”本轮未证实。|
|BCCC|[官网](https://www.yorku.ca/research/bccc/ucs-technical/cybersecurity-datasets-cds/large-scale-iot-zwave-intrusion-detection-dataset-bccc-iot-ids-zwave-2025/) 确认五个月、20 TB、超过 110 台设备、88 个攻击场景及五类数据源。Shafi/Lashkari，*Internet of Things* 34，DOI [10.1016/j.iot.2025.101747](https://doi.org/10.1016/j.iot.2025.101747)，书目信息一致。|官网是 **81 IP network traffic classes、24 Z-Wave classes**，不能写“88 场景中 81 个 IP 攻击”。十亿多源 records 不等于十亿 IP 包；五个月不等于每设备连续正常。|
|ACI|[官方页](https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023) 确认 PCAP 32.27 GB、时间表 2.5 KB；采集作者原论文为 Nack/McKenzie/Bastian，MILCOM 2024，DOI [10.1109/MILCOM61039.2024.10773916](https://doi.org/10.1109/MILCOM61039.2024.10773916)。原论文摘要的索引支持物理设备与五天采集。|**约 30 台、800 万“包”、正常 5%** 未从本轮作者材料确认，800 万的计量单位也未知。即便比例日后属实，也不能由正常占比推断是否满足 7200 秒，不能据此降低优先级。|

SHARP 另有实质身份核查项：[DataCite 的同 DOI 记录](https://api.datacite.org/dois/10.21227/ray1-ag27) 当前题名写成 `"TON-IoT"`、URL 指向 `/documents/ton-iot` 且摘要有占位文字；作者/DOI/年份却与 SHARP 相符，而 DOI 实际解析到 SHARP。已保留两份快照。**不能忽略此冲突，也不能凭它认定与项目 ToN 血缘重叠**；获取时须核 release manifest 与实际内容身份。

## 2. 小文件准确名称与“能否单取”

|候选|已看见的确切名称或内部路径|获取结论|
|---|---|---|
|SHARP|`researcher_documentation/DEVICE_GUIDE.md`、`researcher_documentation/ATTACK_GUIDE.md`、`researcher_documentation/LABELS_AND_ATTACKS.md`|官网说明给出路径；三个公开相对链接实测 404。未取得内容，不能承诺已可单独下载。|
|SHARP|`researcher_documentation/QUICK_START.md`、`SCRIPT_GUIDE.md`、`TELEMETRY_SCHEMA.md`、`ZWAVE_GUIDE.md`；`metadata/FILE_MANIFEST.csv`|内部路径可证，订阅后的独立成员访问尚未核实。|
|SHARP|`02_PUBLIC_RESEARCHER_DOCUMENTATION`|官网文字提到独立文档 archive，但扩展名、大小与单独下载 URL 未列；不能补写成某个 `.zip`。攻击台账/设备 inventory/映射表的确切成员名仍未知。|
|SHARP|`v1.0.0.zip`，172.24 GB；受限树标识 `v1.0.0_zip`|这是匿名页面实际可见的大包列表，**不应先下载它找小文档**。核心 22 包并未单列。|
|ACI|显示名 `Attack Timesheets`（2.5 KB），受限树标识 `Timesheets_zip`|顶层小项确实单列；匿名链接是登录弹层。归档扩展名、内含文件名与有权益后的可下载性未实测。|
|ACI|`ACI-IoT-2023-README`|只证实 README 标题，扩展名/路径未知，没有独立公开链接。设备映射表和原包成员目录仍需取得。|

两个 DataPort 页均标 `Subscription Required`；普通 IEEE 免费账号不等于文件权益。有同一项有效 DataPort 订阅可能覆盖两者，但本轮没有核验用户或学校权限，不能承诺“一次账号必定全解锁”。本轮未登录、填表、购买或绕过门控。

## 3. BCCC 开放论文、时序与标签

已检索出版社、Crossref、OpenAlex、作者中心 publications 与有限 arXiv 记录。出版社与 Crossref 支持 **CC BY-NC 开放发表**，公开 coredata 显示 `openaccessArticle=true` / `openaccessType=Full`。本次访问受阻，403 本身不能定位原因，**不能说论文必须付费**。

但没有取得可读全文：ScienceDirect 403，公开 API 只给元数据，全文 view 返回 401；作者页仍链接出版社，有限仓储检索未得到正文。不能把“没有找到”写成“没有开放版本”。S3 的实际日期/事前正常与后段正常、S4 的方向/时间到包的标签规则、本次仍未知。

官网申请入口尚未给公开成员表；本轮没有提交个人信息或申请。下一份具体需要的是设备 MAC/IP/角色表、带日期的正常与攻击目录、攻击账本及标签规则。S6 应按真实 MAC/来源排查：共同作者、曾任 CIC 主任、改用 York 名称都不能单独证明重叠或独立。

## 4. 有没有遗漏候选

可补充 **MQTTset（Vaccari 等，Sensors 2020，DOI [10.3390/s20226578](https://doi.org/10.3390/s20226578)）**为元数据备查。已取得的 [作者开放正文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7698741/) §3 写明正常 PCAP 一周、11,915,716 包/1,093,676,216 字节，Mosquitto 1.6.2 broker `10.16.100.73:1883`；另有五类攻击捕获，作者入口为 [Kaggle MQTTset](https://www.kaggle.com/cnrieiit/mqttset)。

但传感器由 IoT-Flock 模拟，broker 的物理身份/MAC、正常与攻击真实先后、合法方向标签和 S6 尚未闭合。不能把模拟传感器数写成多真实受害者；畸形载荷类也不能自动算入 S5。因此只是补一项待核候选，没有授权下载其原包。

另查 MQTT-IoT-IDS2020 的作者接受稿，明确全 VM 模拟网络，当前不提升为补足多真实目标的主确认线。Edge 的其他场景仍属同一测试床，不单独计第二个独立数据集。其余已经排查过的候选不在本轮重新下载。

## 5. 下一材料与交付

优先取得 SHARP 文档/成员清单以查清 IP 攻击与身份冲突，并取 ACI 已单列的小时间表；BCCC 可并行准备申请所需的小资料清单，由用户决定真实信息提交。该顺序依据可核资料及访问成本，**不依据预计模型效果**。现在不要求用户再手动下载任何大包。

完整逐条来源、HTTP 状态、摘录和 SHA 证据位于 `runs/external_scope_review_codex_20261103/sharp_aci/` 与 `bccc_candidates/` 的 `REVIEW.md`、`EVIDENCE.json`。公开网页/小论文已留本地快照；没有新增原始捕获、模型评价、训练、云端任务或对外消息。通过统一资格的候选仍须全部评价并报告，不按后来的成绩择优。
