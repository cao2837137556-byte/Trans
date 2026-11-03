# CICIoMT2024 官方说明独立复核

状态：METADATA_REVIEW_ONLY_RAW_QUALIFICATION_PENDING。仅读取三份官方PDF；未下载原包、未训练、未编码、未算支持度或评价指标。

## 读取完整性

- `README.pdf`：3页，全部渲染并检查。第1页正文与拓扑/攻击分类图；第2页是类别/样本数量柱图；第3页是CSV聚合特征表。第2/3页不是设备或攻击时间表。
- `README_profiling.pdf`：2页，逐页全文提取、渲染检查。
- `README_Wifi_and_MQTT_attacks.pdf`：1页，正文为轮廓字，pypdf几乎只抽到空白；已通过渲染读取，人工转录保存在同目录。Poppler报告Symbol/ArialUnicode显示字体警告，但正文渲染完整可读。

## 已证实事实

1. 总README第1页：40台IoMT设备，25真实、15模拟，18种攻击。拓扑中Wi-Fi真实设备为Sense-U Baby Monitor、SOS Multifunctional Pager、SINGCALL SOS Button、M1T Laxihub、Owltron、Blink Mini、Ecobee Camera，共7台。不能把25台全部当作本项目IP检测目标。
2. 总README第1页攻击表列DoS/DDoS的TCP、SYN、UDP、ICMP；没有明确ACK Flood类别。第3页有ack flag特征定义仅说明CSV提取特征，不能作为直接ACK攻击存在的证据。
3. Profiling第1页：Active涵盖人主动操作SOS按钮、佩戴baby sensor、App交互，以及摄像头motion detection的被动活跃；同时混入模拟MQTT流量。必须按真实设备映射过滤，不能全包一律归为真实设备正常流量。
4. Profiling第1页：Idle仅写隔夜静置，Power仅写开机再关机；本说明没有精确时长、日期或每设备在线情况。不能用“overnight”直接验收7200秒合同。
5. Profiling第1–2页：四摄像头Blink/Ecobee/M1T/Owltron的MIC、WATCH、PHOTO、RECORDING均有LAN/WAN模式；Pager有APP修改Home/Armed/Away及PHYSICAL触发；SenseU有EMERGENCY物理传感器朝向触发；Singcall有PHYSICAL触发。LAN表示App同网，WAN表示App在不同网络。
6. 攻击README第1页：目录保存Wi-Fi及MQTT原始PCAP，作者分train/test，CSV由TCPDUMP、DPKT提取。没有攻击者/受害者MAC或IP，没有攻击时间表，没有TCP flags/生成命令。作者train/test命名不能替代本项目可信正常/入网/外部查询角色划分。

## 下载角色与必须保留的未知

- 第一批资格原包应覆盖：可信历史正常+完整实际7200秒入网+独立后段正常；正常Active/interaction；直接非SYN守卫ACK攻击；直接UDP攻击。四种角色不必等于四个文件，具体选实际目录里能覆盖角色且总字节最小的组合，不看模型分数。
- 需要原包核实TCP攻击方向ACK=1,SYN=0，并单列ACK-only、PSH+ACK、其他组合；反向ACK响应和SYN+ACK不能冒充主确认ACK攻击。
- UDP也须按攻击者/目标/事件方向核实，背景、响应、未知单列，不能把整份攻击文件所有帧都标成攻击。
- 本次三份说明未提供：MAC/IP设备表、控制端和攻击端映射、精确日期/时长、攻击时序；这些仍需原包+其它官方说明/论文补齐。现有PDF自身不足以宣布7200秒、直接ACK或UDP方向资格通过。
- 最终外部确认要核算独立设备、日期/捕获、事件、会话以及正常/攻击数；一个洪泛事件的大量相邻包不能替代独立事件数量。资格包通过后再锁定最终获取范围。

## 方法边界

冻结的C5及A/B均未修改。这里只做资料获取资格分析；外部资料拿到并核验前，不进行检测评价。
