# BCCC 事实、开放论文与补充候选复核

结论：BCCC 的规模与来源描述基本成立，但“88 场景中 81 个是 IP 攻击”须更正；尚无新增候选通过 S1–S6。
影响：BCCC 可保留元数据资格候选，不能凭五个月采集或有标签文件就认定具备合法两小时正常历史与逐包攻击标签。
下一步：合法取得设备身份表、原包目录、采集日期/事件账本和标注规则后再作资格；本轮不申请、不下载原包、不评价模型。

复核日期：2026-11-03（America/Los_Angeles）。对应 Claude 候选稿第 2.2、第 4.3–4.4；全部推断只依据采集资料，不按检测表现选择。

## BCCC：哪些事实已核实

官网确实写明五个月、20 TB、超过 110 台设备、超过十亿条多源记录、88 个攻击场景。五类数据源为 IP 流量、Z-Wave 通信、设备活动日志、MQTT 流量、MQTT 消息日志；宣称发布原始包、CSV、元数据和标签文件。

**关键口径纠正：官网原文是 `81 IP network traffic classes` 与 `24 Z-Wave classes`，不是“88 个攻击场景中有 81 个 IP 攻击”。** 类别是否包含正常、与攻击场景如何映射，当前均未知。“十亿 records”也不能换成十亿 IP 包；五个月实验周期不能换成任何设备五个月连续正常。

论文题名、作者 MohammadMoein Shafi / Arash Habibi Lashkari、*Internet of Things* 34（November 2025）、DOI `10.1016/j.iot.2025.101747` 得到官网与 Crossref 一致支持。可访问官网：https://www.yorku.ca/research/bccc/ucs-technical/cybersecurity-datasets-cds/large-scale-iot-zwave-intrusion-detection-dataset-bccc-iot-ids-zwave-2025/ 。

## 开放版本检索与尚未闭合的条件

Crossref 出版社许可记录是 CC BY-NC 4.0；OpenAlex 标为 hybrid OA；Elsevier 自己的公开 coredata 明确 `openaccessArticle=true`、`openaccessType=Full`。所以它是开放发表的论文，**403 只是本次访问受阻，不能写成必须购买论文**。但本轮并没有拿到可读全文：ScienceDirect 403，公开 API 只返回元数据，`view=FULL` 返回 401。作者中心 publications 页面仍指向出版社；有限 arXiv 题名/作者检索未发现版本，OpenAlex 也未列出仓储全文。未绕过访问控制，也未借摘要补写正文。

因此 S3 的具体日期、逐目标 7200 秒可信正常及后段正常，S4 的攻击者/目标/端口/时间到包的标注方法，均保持未知。官网的 Request Dataset 指向申请入口，当前没有公开成员表或可执行小包获取清单，不能承诺可直接下载某个子集。没有提交申请。

S1/S2 在网页上有测试床/原包承诺，但物理身份、MAC、实际格式和时钟仍待小资料与原包证明。S5 仅可确认宣称有网络层威胁，不能将全部 88 场景自动纳入。S6 不能凭共同作者或作者曾任 CIC 主任判定重叠，也不能凭 York 名称判定独立；须比对真实 MAC、采集来源及项目既有血缘。此时不合格和已知不合格须区分。

## 新增候选：MQTTset 仅列元数据备查

作者开放全文 DOI `10.3390/s20226578`（https://pmc.ncbi.nlm.nih.gov/articles/PMC7698741/ ）§3 说明 MQTTset 由 IoT-Flock 生成传感器流量，捕获位于 Eclipse Mosquitto 1.6.2 broker，IP `10.16.100.73`、端口 `1883`。作者描述正常生成 PCAP 覆盖一周（周五 11:40 到下周五 11:45），11,915,716 包、1,093,676,216 字节。§3.1 另列五类攻击 PCAP：洪水 DoS、MQTT Publish flood、SlowITe、畸形数据、认证暴力破解。§6 作者数据入口是 https://www.kaggle.com/cnrieiit/mqttset 。

这是原清单未提、且值得进一步取小资料的一个候选，**不是本轮新合格数据**：尚未核实真实 broker/边缘设备身份与 MAC、原始时钟的正常先后/连续性、直接攻击标签和 S6。IoT-Flock 的模拟传感器不能算成多台真实受攻击终端；若实际目标只有 broker，结论也只能是一台 broker。畸形载荷类不属于冻结前端能据此验证的 S5。当前不因为一周正常就直接下载原包。

另读了 Hindy 等 MQTT-IoT-IDS2020 作者接受稿（DOI `10.1007/978-3-030-64758-2_6`，Abertay 开放版本见证据）。§2 明确“Virtual machines are used to simulate the network devices”，12 传感器和相机流均是模拟；它不补足多真实目标确认，因此不提升为主候选。即使有 PCAP 与四类攻击，也不等于 S1/S3 通过。

本轮未找到一个新数据集已可证明全部 S1–S6；不把暂时找不到写成“再无选择”。BCCC/SHARP/ACI 的资料缺口仍应先解决。来源摘录、SHA、可核事实与未知项见 `EVIDENCE.json`。仅获取公开网页/元数据/小论文，没有原包获取、表单提交、登录、付费、模型或云端任务。
