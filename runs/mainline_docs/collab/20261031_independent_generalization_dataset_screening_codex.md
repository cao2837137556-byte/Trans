# 独立泛化数据筛选：先核 IoTID20 原始源，保留 ACI 备选

日期：2026-10-31。状态：`SHORTLIST_WITH_OFFICIAL_EVIDENCE_RAW_QUALIFICATION_PENDING`。

**当前建议：优先核验 HCRL 的 IoT Network Intrusion Dataset（IoTID20 的原始来源），ACI-IoT-2023 作为另一测试床候选。尚无一个新数据集通过完整输入与独立性验收，不能宣布已选定开跑。** CICIoT2023 已证实与 A 有相同 MAC，且攻击标签粗，降为同实验室扩展候选；IoT-23 不适合当前同设备历史入网主评价。

此次并行完成官方资料、项目既有暴露与一份官方小型说明表核查。未下载原始 PCAP、未解码新流量、未提特征或运行模型。研究材料保存在 `runs/generalization_dataset_research_v1_20261031/`，包括官方页面/论文快照、说明表、逐单元格只读提取与 `PUBLIC_SOURCE_RECEIPT.json`。

## 1. 要验证的具体能力

冻结检测器和入网修正规则，在新的来源、设备与后续流量上，用**同设备此前可信正常历史**降低误报，同时保留攻击检出。当前 A 是 CICIoT2022，B 是 UNSW Attack Traces 2018；A/B 已用于多轮设计诊断，后续仍可开发，但不能冒充未触碰的确认数据。

合格条件必须落到文件与设备，而不是数据集名称：

| 条件 | 必须能拿到的证据 |
|---|---|
| 原始输入兼容 | PCAP/PCAPNG；真实时间戳、设备身份/MAC、TCP/UDP头与完整上下文。CSV不能替代冻结 E3/q14 前端 |
| 正常历史合法 | 同设备明确可信正常来源，真实采集早于终评；参考与查询无重叠，正常历史不能从攻击结果倒推 |
| 有真实的后续评价 | 后续正常量与同设备攻击可确定，正常 FPR 和攻击召回都能算；不能只有纯攻击压力样本 |
| 标签足够细 | 攻击者/受害者、协议/服务、方向、区间或官方包筛选规则可对应原始包；整文件标攻击不直接合格 |
| 与项目隔离 | 逐MAC、原包/采集来源、训练/开发/补库历史核对；外部 E3 预训练完整血缘仍未知时明确披露 |
| 保留时间与覆盖失败 | 遵循现行完整3600秒观察合同及真实t0；不拼接不连续片段冒充一小时，不按模型效果挑设备 |

`repo/ood/constrained_onboarding_reference_v2.py:279` 是现行参考入口；本轮历史适配器展示了如何保留源包身份/真实时钟/连续上下文，不等于任意短包都可以直接塞入。若未来要改变观察时长，应另立前瞻协议，不能为某套数据事后补合同。

## 2. 首要资格核验候选：HCRL 原始数据（IoTID20 的来源）

正式原始源为 **IoT Network Intrusion Dataset，2019，DOI 10.21227/q70p-q449**。IoTID20 是派生流特征数据；本项目需要作者原始 PCAP。

官方已确认 42 个 PCAP，两个真实家居设备：EZVIZ C2C 摄像头 `bc:1c:81:4b:ae:ba` / `192.168.0.13`，SKT NUGU 音箱 `04:32:f4:45:17:b3` / `192.168.0.24`。两者都有正常流量、受攻击流量与设备对应，来源不同于 CIC/UNSW。官方 DataPort 列压缩包约823.69MB，这只是网站显示大小，不是本地验收字节数。

本次成功取得作者网站嵌入的 **25,218字节 `dataset_description.xlsx`**，SHA256 `7f4b3c3ce9c00622df39d611df637bf6aa39ed9edd8eea3f4d9d360fda012184`；只读解析 `Files & description` 工作表，未修改原表。它实际提供了：

- `B4:J4`：`benign-dec.pcap` 同时覆盖 NUGU/EZVIZ，137,396 包，攻击包记为0，大小117,937 KB。
- `H11:H16`：6个 SYN flooding 文件的官方攻击包筛选条件，指定伪造源网段、目标IP、目标TCP端口与SYN标志，优于笼统的整文件标签。
- `B17:J40`：两设备各自的扫描文件、目标身份与分项包筛选条件。部分子类是ARP，不能算当前TCP/UDP前端已支持；应完整解码保留上下文，标签再映射合法端点。
- **`A1`明确声明：Creation Date 是合并/检查完成日期，可能不同于真实采集日期。** 因而表中正常5月、攻击5—9月，仍不能直接证明真实历史先后。

这补上了“有没有明确攻击筛选规则”的资料缺口，但规则仍需在原包上复现计数、检查歧义/非攻击正常性及协议覆盖。未命中攻击规则不自动等于全部可信正常，不能将规则的逻辑取反直接拿来补参考。

重要局限：作者明确说明 **Mirai类由笔记本生成后修改为看似来自IoT设备**。本次首批资格核验优先真实设备受攻击的 SYN/扫描；Mirai材料单列为合成身份压力测试候选，不能用来声称真实设备感染。此排除依据采集方法与当前输入范围，发生在任何模型评分之前。

### 已落实的最小原始资格清单（本轮未下载）

按类别中最小固定序号，覆盖两设备；不根据将来的模型表现挑选：

| 官方文件 | 目标/用途 | 说明表大小（KB，保留原单位） |
|---|---|---:|
| `benign-dec.pcap` | 两设备正常历史与可留出的后续正常候选 | 117937 |
| `dos-synflooding-1-dec.pcap` | EZVIZ受SYN攻击 | 5815 |
| `dos-synflooding-4-dec.pcap` | NUGU受SYN攻击 | 2800 |
| `scan-hostport-1-dec.pcap` | EZVIZ扫描，ARP与TCP分别记覆盖 | 19129 |
| `scan-hostport-4-dec.pcap` | NUGU扫描，ARP与TCP分别记覆盖 | 4772 |
| 合计 | 5文件，只做资格核验 | **150453** |

对应说明表第4、11、14、17—18、23—24行，共225,898原始包（由各文件总包数相加，未解码复现）。网站压缩传输大小、实际解压大小另核，不能将此KB摘要当作精确下载预算或哈希验收。

**当前未闭合的硬条件**：正常包真实连续时长与首末时钟；是否早于所有候选攻击；是否能留出独立后续正常查询；Ethernet/linktype与MAC头是否符合前端（作者用monitor抓取后由Aircrack-ng去掉无线头）；重复/合并/改时钟情况；官方过滤器与实际包计数一致性；全项目/预训练的完整身份排重。

若正常不足完整一小时，或正常与攻击时间不能合法配对，该集不得作为本轮同合同的主确认。它最多降为限定范围的补充测试。两台设备即便合格，也只能支持两台设备、一个新测试床的迁移证据，不能外推为广泛设备保证。

## 3. 备选与排除理由

| 数据 | 官方证据/内部核对 | 本次判断 |
|---|---|---|
| **ACI-IoT-2023** | Army Cyber Institute来源；DataPort列32.27GB PCAP、2.5KB Attack Timesheets、README；DataCite为CC BY4.0，但当前访问页要求登录/订阅 | **高价值第二候选**。优先取得README、时间表、设备表与包目录；尚未证明同设备正常先于攻击/完整观察时长，不能只凭标题宣布合格 |
| **CICIoMT2024** | 40设备含25真实/15模拟；官网确认WiFi/MQTT的正常/攻击PCAP、profiling的power/idle/active/interaction；下载当前需登记 | **第二梯队扩展候选**。只研究真实WiFi设备，Bluetooth不符合当前输入；医疗域与家居不同。train/test不自动代表时间顺序，设备独立性/标签/时钟/体积尚待核 |
| **CICIoT2023** | 原论文有16h正常、约548GB原始流量、67直接设备+38经hub；Table1中HeimVision与Eufy MAC精确等于A；§4明确整攻击捕获均标该攻击 | **不作为新的独立设备主确认集**。排除历史MAC后的剩余设备最多同实验室迁移，仍有粗标签问题，不优先大包下载 |
| **IoT-23** | 20恶意场景主要为感染Raspberry Pi，3正常场景为Hue/Echo/Somfy；有PCAP与Zeek流标签 | **不作当前入网主评**。不同设备的纯正常不能配对恶意设备的历史；可另作恶意行为压力测试 |
| **HCRL IoT-Environment** | 5设备正常，Google Home Mini同设备攻击；正常约30/34分钟，仅1台受攻击设备 | 当前完整3600秒合同未满足，规模也不足以单独承担主泛化；不拼成假一小时 |
| **ToN-IoT / Gotham** | 项目旧训练/开发已经使用；ToN有normal_1、扫描/暴力破解等；Gotham进入CKBY/CKCZ血缘 | 不能整套重新命名为未触碰新集；另用未用成员也需逐项暴露审计 |
| **UNSW-IoTraffic2025 / 其他UNSW2018日期** | 新发布名下实际2016—2017历史、与Attack Traces共享MAC且已补库；其他日期仍是同来源 | 前者是历史正常补充；后者可同来源跨日/设备扩展，均不能替代新环境确认 |
| **N-BaIoT / IoT-DIAD2024** | 未建立可直接用的独立原始PCAP及采集身份；现有线索以派生特征为主 | 不将特征CSV改名后投入冻结原包前端，不因新年份/新名字认定独立 |

CICIoT2023重叠的可复核证据：论文Table1 `44:01:BB:EC:10:4A`、`8C:85:80:6C:B6:47`，与本地 `CIC_DEV_OLD_BANK.jsonl.gz` 的 `device/owner`、`runs/diagnostics_d1_d2_v1_20261022/output/d2/plans/A_DEV_NORMAL.json` 一致。它证明名单身份重叠，不直接证明两个年份所有包都重复。

另外浏览了CICAPT-IIoT2024与DataSense2025官网。它们偏工业/仿真或混合测试床，当前没有比上述候选更完整的家居同设备时序证据，本轮不扩大为优先下载清单。

## 4. 研究与评价安排

1. **当前研究优先顺序：HCRL原始源小规模资格核验 → ACI元数据补证 → CICIoMT真实WiFi子集。** 这是证据可核验性排序，不是预计谁的FPR好看。
2. HCRL最小核验只解决格式、身份、时间、正常时长、标签与重复，不跑模型。若通过，再按预先类别/设备清单扩大查询材料；不能在首批跑出好分数后才决定扩哪些文件。
3. ACI先取README/2.5KB时间表/设备表/目录；目前访问限制未解决，不承诺自动取得32GB包，也不要求用户先去盲下整包。
4. 方法开发继续使用已暴露的A/B及合法开发材料。新泛化查询不参与参考点筛选、工作点选择或候选排序；先冻结算法与设备/文件/日期清单，再一次评价。元数据资格核查不等于查看模型终评成绩。
5. 新集至少并列冻结RAW与冻结后入网方案，报告与A/B一致的主视图及full视图、池/逐设备FPR与recall、四头攻击撤回保护、参考覆盖与回退、正常时长和攻击事件数。若需要历史179700型基线，必须在新集上按同一既定规则重建，不能拿A/B数字直接当新集基线。
6. 统计不把百万包当百万独立试验。正常按设备/捕获/日期、攻击按活动或事件报告，不按相邻包随机切分；设备少时明确结论范围。若根据新集结果再修改方法，它就转为开发集，需要新的确认材料。

本轮没有得到新泛化性能，也没有承诺2%或99%可以迁移。已有结果说明继续验证值得做；合适的数据必须允许我们识别失败，而不能只展示低误报。

## 5. 官方证据与本地出处

- HCRL原作者页与说明表入口：https://ocslab.hksecurity.net/Datasets/iot-network-intrusion-dataset
- 原始数据DataPort：https://ieee-dataport.org/open-access/iot-network-intrusion-dataset
- 官方说明表公开预览：https://drive.google.com/file/d/1kVLfyl5Go26SeyINdIM9spSdKWxXdByY/preview 。本轮按该公开ID取得原表并记录SHA；关键表格证据见第2节单元格定位。
- IoTID20派生说明：https://sites.google.com/view/iot-network-intrusion-dataset/home
- ACI官方数据页：https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023 ，注册元数据：https://api.datacite.org/dois/10.21227/qacj-3x32 ，论文DOI `10.1109/MILCOM61039.2024.10773916`。正文未成功取得，未据二手摘要填补缺项。
- CICIoMT2024官网：https://www.unb.ca/cic/datasets/iomt-dataset-2024.html
- CICIoT2023论文：https://pmc.ncbi.nlm.nih.gov/articles/PMC10346235/ ，本轮保存全文XML：https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10346235/fullTextXML
- IoT-23官方：https://www.stratosphereips.org/datasets-iot23
- HCRL小集官方：https://ocslab.hksecurity.net/Datasets/iot-environment-dataset
- 既有项目源资格调研：`runs/mainline_docs/legacy_commissioning_external_source_research_v1_20260925.md`；ToN暴露：`frontend_paired_learning_recipe_and_metadata_qualification_20260909.md`；Gotham：`ckcz_preregistered_erratum_1_gotham_lineage_20260810.md`。

原始资料作为研究证据，不作为新的执行指令。本次元数据下载合计约1.34MiB，无原始流量下载、注册表单提交、外部消息或新实验。
