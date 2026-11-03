# 外部验证数据获取状态：优先核 CICIoMT2024，尚无已验收的主外部集

- 日期：2026-11-01，北京时间。
- 状态：`PUBLIC_METADATA_REFRESHED__RAW_SHORTLIST_NOT_QUALIFIED`。
- 用户分工：论文与实验并行，本对话继续负责实验及合适的外部验证数据资格调研。
- 方法基准：已冻结 C3，A/B 为 `CONSUMED_DEVELOPMENT_ONLY`；本轮未运行外部模型、提取 E3、调整方法或下载新原始流量。

**当前处于“定向取得资格材料”的阶段。下一批获取应是设备/文件目录、采集时间表和最小必要原始样本；尚未确定可以直接批量下载并评价的外部集。** 先前调查已完成 HCRL 淘汰，本轮接续候选核验，不重新下载该集。

## 1. 先前结论继续有效

| 候选 | 已有证据与当前地位 | 获取决定 |
| --- | --- | --- |
| HCRL / IoTID20 原始源 | 五包已经定向获取并核验；正常捕获仅 301.089296s，两小时之后正常包数为0 | 同合同主验证淘汰，不扩大下载 |
| ACI-IoT-2023 | 不同来源的候选，但正常时长、设备身份与合法时序仍待原材料证明；当前原包访问有条件 | 保留；先取得小型 Attack Timesheets、README、设备/文件清单 |
| CICIoMT2024 | 当前最值得继续核实的可见候选；含真实医疗物联网设备及多种正常运行阶段；仍来自 CIC，不能仅凭新年份宣布独立 | 优先获取目录和正常历史资格材料，核验真实 Wi-Fi 子集 |
| CICIoT2023 | 部分设备 MAC 与 A 精确重合，且攻击标签粒度问题未解决 | 不作为新环境、新设备主确认优先下载对象 |
| IoT-23 | 正常场景与恶意场景主要不是可配对的同一设备历史 | 不承担当前同设备历史入网主评价 |

本轮以真实当前 **7200s** 观察合同为准。首轮筛选旧稿出现的3600s是已被后续核验纠正的历史口径。

## 2. 本轮重新读取的官方材料

### CICIoMT2024

官网：<https://www.unb.ca/cic/datasets/iomt-dataset-2024.html>，本轮 HTTP200，89,591 bytes。

官网确认40台设备，25真实、15模拟。`WiFi_and_MQTT` 的攻击/正常 PCAP 按 train/test 组织，profiling 包含 power、idle、active、interaction；这些类别划分本身没有证明真实时间顺序。

本轮提取到的关键原文：

> Idle: In this experiment, the whole network traffic is captured between late evening to early morning to ensure that the lab was vacant and devoid of human interactions.

“晚间至次日清晨”使其值得优先核验长正常历史，但没有给出每台真实 Wi-Fi 设备的实际持续时长、正常查询留出量及其相对攻击捕获的先后。因此不能由这句话直接填写“≥7200秒且历史早于终评已通过”。同理，25台真实设备包含不同通信类型，不应全计入当前 Ethernet/TCP/UDP 前端可评价人口。

官网给出的下载入口：<http://cicresearch.ca/IOTDataset/CICIoMT2024/>，实际跳转到 <https://cicresearch.ca/IOTDataset/CICIoMT2024/>。本轮 HTTP200，10,535 bytes；返回 **CIC DATASET DOWNLOAD FORM**，字段包含 First Name、Last Name、Email、Organization/Company、Job Title、Country；没有直接展示原始文件目录。

因此 Antigravity 冻结复核稿中的“公开免登录原包子集”尚不能作为已核事实使用。当前只能确认官网介绍公开、下载入口要求登记；是否已有合适的登记会话、登记后文件目录及原包是否可定向获取，仍未核验。本轮未填写或提交个人信息。

### ACI-IoT-2023

官方页：<https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023>，本轮 HTTP200，63,486 bytes。

页面仍明确显示 **Subscription Required / Not logged in / LOGIN TO ACCESS DATASET FILES**。Attack Timesheets 标示2.5KB，PCAP Files标示32.27GB，但对应可见链接均为 `#`；README仅被说明文字提及。未取得时间表正文或32.27GB包的下载地址，未登记为可直接下载、未绕过访问条件。

本轮 Python 网络读取失败，随后使用系统 curl 正常读取上述公开页面。该工程差异不改变数据访问资格，也不表示原始数据已下载。

## 3. 下一批具体要取得什么

优先围绕 CICIoMT2024，先取得以下材料，取得后再决定必要的原包范围：

1. **设备表与文件目录**：真实 Wi-Fi 设备型号、MAC/IP、原始文件路径、大小、采集说明；与既有 LEARN/A/B/历史参考来源排重。CIC同实验室来源需如实披露，未验证的基础编码器预训练血缘仍列为限制。
2. **正常捕获元数据**：idle/active/interaction 的真实日期与首末时间，确认同设备可信正常历史早于终评；必须满足7200秒观察且留有独立后续正常评价。优先查公开说明/目录；说明不足时定向获取能回答该问题的最小原包，不把文件名或train/test标签当成时序证据。
3. **攻击标签和捕获说明**：攻击者、受害者、五元组/协议、起止时间与方向定义，明确反向响应如何计入；不能把攻击文件中未匹配规则的包自动充作正常历史。
4. **原包资格检查**：真实时钟、MAC、链路类型、包长/截断、重复、TCP/UDP覆盖及正常SYN发起行为。此阶段可以做原包元数据/计数核验，仍不运行检测模型或按效果选设备。

若 CICIoMT2024 不满足时序、设备独立性或标签要求，记录具体淘汰原因；不以修改冻结观察窗迁就数据。ACI 保留为另一来源候选，取得合法访问后仍先看2.5KB时间表及README。

资格通过后，冻结设备/日期/参考/确认查询清单与原始获取字节预算，再定向获取所需原包，写唯一外部评价卡。卡应至少包含固定 RAW 与 C3，同人口、同权重、主/full视图、逐设备与四头保护；外部成绩揭示后不回调 λ、cut、cap 或守卫。

论文线现在可以使用已封存的开发结果、方法与局限。外部验证章节应保留待完成状态，不预写数据集已合格或泛化达标。

## 4. 本轮证据

目录：`runs/generalization_followup_v1_20261101/`。

- `CICIoMT2024_curl.html`、`CICIoMT_PUBLIC_FACTS.json`：官网和关键描述。
- `CICIoMT2024_download_entry.html`、`CICIoMT_DOWNLOAD_ENTRY_FACTS.json`：实际登记入口。
- `ACI_curl.html`、`ACI_PUBLIC_FACTS.json`：当前访问条件和可见文件链接。
- `PUBLIC_ACCESS_RECEIPT.json`：最初 Python 读取失败的记录，保留故障而不覆盖。
- `EVIDENCE_SHA256.json`：本轮证据哈希。

成功获取三个公开HTML页面，共 **163,612 bytes**；新原始 PCAP 下载、登记提交、模型特征和新科学评价均为 **0**。已有 HCRL 五包保留，旧封存材料不改。
