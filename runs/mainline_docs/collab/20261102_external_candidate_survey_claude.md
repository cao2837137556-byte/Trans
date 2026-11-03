# 外部测试 2 候选调研（Claude 初筛，请 Codex 复核）

2026-11-02。用户要求由 Claude 先调研、Codex 复核。筛选只依据 [范围条件 S1–S6](20261102_external_scope_criteria_and_edge_review_claude.md)，不看任何模型输出。本轮只读了公开网页和论文，没有下载数据、没有提交登记表、没有付费。下文的事实都来自网页摘要或论文文本，**尚未与原包核对**，请 Codex 逐条复核。

已经筛过、不再重复的数据集见 [10-31 筛选](20261031_independent_generalization_dataset_screening_codex.md) 和 [11-02 复筛](20261102_external_dataset_rescreen_and_next_acquisition_codex.md)：HCRL、CICIoT2023、IoT-23、ToN、Gotham、UNSW、N-BaIoT、DIAD、MedBIoT、CICIoMT2024 当前组合。

## 1. 结论

| 排序 | 候选 | 初判 | 需要谁做什么 |
|---|---|---|---|
| 1 | **SHARP**（Cardiff，2025 年采集，2026-09 发布） | 纸面上 S1–S5 结构最吻合 | 需要 IEEE DataPort 订阅（用户） |
| 2 | **BCCC-IoT-IDS-ZWave-2025**（York BCCC） | 规模最大，时间线和 S6 未知 | 需要用户填写申请表 |
| 3 | ACI-IoT-2023 | 已知候选，正常流量只占约 5% | **同一个 DataPort 订阅**即可访问 |
| — | Edge-IIoTset 其他场景 | 同一测试床扩展，**不算第二个独立数据集** | 可作为外部测试 1 的补充 |

建议：用户先确认学校有没有 IEEE DataPort 机构订阅，有的话 SHARP 和 ACI 一起解锁。拿到权限后，**先只取小文件**（设备指南、攻击台账、README），做元数据资格核验；BCCC 的申请可以并行提交。

## 2. 候选详情

### 2.1 SHARP: Smart Home Attacks across Residential Multi Protocols

- 来源：https://ieee-dataport.org/documents/sharp-smart-home-attacks-across-residential-multi-protocols ，DOI `10.21227/ray1-ag27`，CC BY 4.0，作者 Alosaimi / Rana / Perera（Cardiff University）。
- 场景：一套**有人居住的两居室公寓**，真实家庭设备，包含 Wi-Fi/以太网 IP、Zigbee、Z-Wave。
- **时序：正常家庭运行期是 2025-06-20 至 07-05，约两周；攻击活动集中在 2025-08-13。** 正常流量严格早于攻击，与 CICIoMT 的失败点相反。
- 数据：共 1,677 个 PCAP/PCAPNG，其中路由器口 512 个、Wi-Fi 空口 779 个、Zigbee 386 个；另有 Z-Wave 日志和遥测。整包 172.24GB，核心下载只含 22 个 PCAP。
- 标签：攻击台账有 36 条（A001–A035、A038），**记录了时间、来源、目标**和结果评估。标签按时间区间标注，不是逐包标注；攻击日的遥测标为 `not_assessed`。
- 对照范围条件：
  - S1：真实家庭设备，可能满足，需从设备指南核对 MAC；
  - S2：路由器口有 PCAP，满足；
  - S3：正常期约两周，很可能满足，需核对每台设备的实际时长与间隙；
  - S4：台账提供时间、来源和目标，可以组合成方向规则，**需看台账的粒度**；
  - S5：**关键未知**，36 条攻击中有多少是 IP 层攻击、多少是 Zigbee/Z-Wave 无线层攻击；
  - S6：Cardiff 测试床，与 A/B 来源不同，仍需逐 MAC 核对。
- 风险：访问需要订阅；数据发布刚两个月，没有配套论文；攻击可能主要针对非 IP 协议。

### 2.2 BCCC-IoT-IDS-ZWave-2025

- 来源：https://www.yorku.ca/research/bccc/ucs-technical/cybersecurity-datasets-cds/large-scale-iot-zwave-intrusion-detection-dataset-bccc-iot-ids-zwave-2025/ ；论文为 Shafi & Habibi Lashkari, *Internet of Things* 34 (2025)，doi `10.1016/j.iot.2025.101747`（ScienceDirect 对我返回 403，正文未读）。
- 规模：智能家居测试床，超过 110 台设备，采集五个月，约 20TB；数据源包括 IP 流量、Z-Wave、设备活动日志、MQTT。官网说明含原始包和标签文件。
- 攻击：88 个场景，其中 81 个是 IP 流量类别，涵盖网络层、设备层和服务层。
- 对照范围条件：
  - S1/S2：可能满足；
  - S3：**未知**，网页没有给出正常画像期和攻击期的先后与日期；
  - S4：标签方法未知；
  - S6：**需特别核对**。Lashkari 原任 CIC 主任，A 来自 CICIoT2022，测试床设备可能有重叠，请逐 MAC 排查。
- 风险：访问需填申请表（会提交个人信息，由用户本人提交）；20TB 只能按需取子集。

### 2.3 ACI-IoT-2023（已知候选，补充信息）

二手资料显示：约 30 台物理设备，采集 5 天，约 800 万包，**正常流量约占 5%**。S3 的风险较高，需要逐设备核实攻击前是否有 7200 秒正常流量。和 SHARP 是同一个 DataPort 订阅，拿到权限后先取约 2.5KB 的时间表。

## 3. 本轮排除

| 候选 | 不满足的条件 | 依据 |
|---|---|---|
| TII-SSRC-23 | S1、S3 | 论文第 465–494 行：受害者是 Ubuntu 笔记本，接入点是 Raspberry Pi；每类正常流量只采集一小时。 |
| Kitsune（NDSS 2018） | S3（大概率） | Mirai 抓包总长约 7,137 秒，且前段正常后段攻击，正常段不足 7200 秒。其余八个抓包是监控摄像头网络，正常前缀较短。Codex 可用 capinfos 低成本核实一次，只看时长。 |
| Gotham 2025 | S1、S6 | 设备为仿真；已进入项目血缘。 |
| IoT-Environment（HCRL） | S3 | 正常约 30 分钟（10-31 已记录）。 |

## 4. 请 Codex 复核的事项

1. 核实第 2 节每条事实的出处，修正我写错的地方。
2. SHARP 和 ACI 的 DataPort 小文件清单：设备指南、攻击台账、README 的确切文件名，以及能否单独下载，而不必取整个 172GB 的 zip。
3. BCCC：尝试找到论文的开放版本（作者主页、arXiv、预印本），核对时间线和标签方法。
4. 有没有我漏掉的、满足 S1–S6 的候选，可以补充进来。
5. 复核结论写入 `20261102_external_candidate_survey_review_codex.md` 或次日同名文件。
