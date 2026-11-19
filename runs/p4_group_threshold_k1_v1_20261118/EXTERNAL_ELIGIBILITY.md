# ACI 与 SHARP 资料资格核查

两项公开目录均可读取，IEEE DataPort 显示本次访问未登录，文件访问需要订阅。项目内可用材料为公开说明与此前保存的目录，未取得可验证的订阅文件权益。两项资格均为**证据不足，待补件**。本轮外部模型打分为 0 次。
对研究判断影响最大的是同一目标的事前正常窗、后段正常查询和有方向的非泛洪攻击标签，现有资料不足以验证这三点。
供负责人选择的最小补件列于表后。核查时间为 2026 年 11 月 18 日（洛杉矶），网页响应及 SHA 见 [访问记录](EXTERNAL_ACCESS.json)。

| 已登记条件 | ACI-IoT-2023 | SHARP |
|---|---|---|
| S1 目标及身份 | 作者描述家庭 IoT 环境。缺受害设备角色及 MAC／IP 与采集文件的对应表。 | 有实际住宅、设备清单及标识映射的说明。缺指定 IP 受保护设备与采集接口的逐项映射。 |
| S2 原始包时钟 | 发布者列有原始 PCAP。包的实际时钟、时区和连续性待小清单或时间元数据核定。 | 发布者列出 512 份路由器 IP 捕获，另有空口和 Zigbee 捕获。文件级首末包时刻与实际时钟待核。 |
| S3 同一目标事前建档及后段正常 | 多天采集不足以证明某台设备在攻击评价前连续具有 7,200 秒可信正常观测，或其后还有正常查询。 | 正常阶段为 2025-06-20 至 07-05，受控活动在 08-13。具体设备的两小时窗口、后段正常查询及中断待核。 |
| S4 攻击标签与方向 | 目录单列时间表及带标签的流记录。缺时区、目标及方向到原始包的匹配依据。 | 有 36 项攻击及测试的台账。说明区分时间段标记与观察结果；需以台账、来源和目标核实 IP 包标签。 |
| S5 网络侧可见性 | 原始网络流量存在。需确认具体非泛洪场景在目标网络接口上留有可判定的包。 | 路由器侧存在网络记录。需将具体活动对应到 IP 捕获，分清仅在设备遥测或非 IP 无线链路可见的活动。 |
| S6 来源独立性 | 发布机构与采集说明可追溯。仍缺设备及采集清单，无法排除与既有源、两项外测及历史库的重叠。 | Cardiff 住宅采集说明可追溯。同一 DOI 的 DataCite 当前仍列题名 “TON-IoT”，需用发布清单、设备映射和来源解决版本身份。 |

**非泛洪且不命中旁路的攻击场景。** 两项均未核实。确认需要同一事件的标签、目标、方向和协议证据，能区分 TCP SYN 无 ACK 与其他合法查询。当前没有证据足以按某一必要条款直接判定这两个数据集失败。[资格规则](../external_scope_review_codex_20261103/SCOPE_CRITERIA.json)

**ACI 的最小补件。** 目录明确单列 `Attack Timesheets`（2.5 KB，树标识 `Timesheets_zip`），并给出说明标题 `ACI-IoT-2023-README`。另需目标设备映射、每份捕获的前后时刻及正常时段说明。映射文件的精确成员名尚未知。公开目录列出 32.27 GB 的 PCAP，此次获取止于文件权限门槛。[发布目录](https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023) · [采集作者论文](https://ieeexplore.ieee.org/abstract/document/10773916)

**SHARP 的最小补件。** 需 `researcher_documentation/` 下的 `DEVICE_GUIDE.md`、`ATTACK_GUIDE.md` 和 `LABELS_AND_ATTACKS.md`，另需 `metadata/FILE_MANIFEST.csv` 及其指向的 IP 设备映射和一项可核事件。发布页提到 `02_PUBLIC_RESEARCHER_DOCUMENTATION` 文档归档，独立访问权益仍未知。核查至此停止。[发布目录](https://ieee-dataport.org/documents/sharp-smart-home-attacks-across-residential-multi-protocols) · [DataCite 身份记录](https://api.datacite.org/dois/10.21227/ray1-ag27)
