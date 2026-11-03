# CICIoMT2024 登记后目录与官方说明获取回执

2026-11-02（America/Los_Angeles）。状态：`DIRECTORY_AND_READMES_ACQUIRED_RAW_QUALIFICATION_PENDING`。

## 本轮已完成

用户在 Codex 内置浏览器完成真实信息登记后，复用该合法会话读取官方目录并下载说明文件。此前 Chrome 原生控制的网址识别失败，不影响本轮内置浏览器读取成功；没有把网站 403 当作 VPN 故障结论，也没有导出登记信息、Cookie 或会话凭证。

- 官方目录入口：`https://cicresearch.ca/IOTDataset/CICIoMT2024/`。
- 逐页读取并整理 19 个目录页面，已观察范围内共 113 个 PCAP 链接：profiling 的 Idle/Active、7 个 Power 文件和7设备32个交互文件，共41个；攻击 test 21个、train 51个，共72个。这里只是清单，113个原包尚未下载。
- 下载并校验三份原始 PDF，共 7,203,702 字节（约6.87 MiB）。已保存在项目内；Downloads 原件保留。
- 全部6页说明已渲染检查。攻击说明采用轮廓字，不能因文本提取为空白而误判无内容；已独立视觉核对。
- C5 p=3 与 A/B 开发冻结保持；无原包解码、模型推理、距离计算、检测评价或云端作业。

机器清单：[REGISTERED_DIRECTORY_MANIFEST.json](../../c5_external_test_preparation_codex_20261102/acquired_direct/REGISTERED_DIRECTORY_MANIFEST.json)。它是公开可见目录项的规范化转录，保存实际文件名及官方链接；不声称是原始 HTML 或下载字节。

## 已取得的官方说明

|文件|字节|SHA256|
|---|---:|---|
|README.pdf|6,992,913|`0ad5283fdc7086d03588c1cdc87f3d430e2ef32969985da51ba538eabc3b68af`|
|README_Wifi_and_MQTT_attacks.pdf|138,278|`fa88de1fcdc39c845e638f91c9b43a12f4341b24aa61e453897d76336c3a34a8`|
|README_profiling.pdf|72,511|`a6646e3a2e0f8a274a7537972f46441a6fa9b3a0b075b73dd90af9d61ad7b42d`|

保存目录：`runs/c5_external_test_preparation_codex_20261102/acquired_direct/readmes/`。独立全文/视觉复核见 [README_REVIEW.md](../../c5_external_test_preparation_codex_20261102/acquired_direct/review/README_REVIEW.md)；其 SHA256 为 `724d1f49a692970378954a484bc08391342eb046924dee2602ab9f66f531d3bc`。

总说明拓扑证实7台真实 Wi-Fi 设备；profiling 说明证实 Active 包同时含模拟 MQTT，并包括摄像头 motion detection 的被动活跃。三份说明均没有完整 MAC/IP 表、精确捕获时间、攻击时序、TCP flags 或生成命令。作者预印本的“两个13小时 idle／累计26小时 active”仍只是文献事实，不能替代实际原包时长及逐设备在线核验。

## 原始文件定位已闭合，资格与大小未闭合

真实大小写为 **`WiFI_and_MQTT`**，不能沿用旧草案 `WiFi_and_MQTT` 的大小写猜测。

|角色|官方已观察到的相对路径|当前状态|
|---|---|---|
|长正常／真实时序|`WiFI_and_MQTT/profiling/PCAP/Idle/Idle.pcap`|文件存在；时长、每设备覆盖、历史与入网/后段角色待核|
|正常活动／行为覆盖|`WiFI_and_MQTT/profiling/PCAP/Active/Active.pcap`|文件存在；真实设备和模拟流量必须分开|
|直接非守卫 ACK 攻击候选|`WiFI_and_MQTT/attacks/PCAP/test/TCP_IP-DoS-TCP_test.pcap`、`TCP_IP-DDoS-TCP_test.pcap`|名称是TCP攻击，尚不能证明直接 ACK=1、SYN=0|
|直接 UDP 攻击候选|同目录 `TCP_IP-DoS-UDP_test.pcap`、`TCP_IP-DDoS-UDP1_test.pcap`、`TCP_IP-DDoS-UDP2_test.pcap`|仍须核实事件、目标和方向|
|补足正常交互（若需要）|`profiling/PCAP/Interactions/` 下7设备的32个文件|已完整登记；是否补取按来源/行为覆盖决定，不看模型分数|

上表7个核心候选的实际 URL 见 [RAW_QUALIFICATION_CANDIDATES.json](../../c5_external_test_preparation_codex_20261102/acquired_direct/RAW_QUALIFICATION_CANDIDATES.json)。它不是“已选定最小字节组合”，更不是全部合格确认集；四种角色不等于四个文件。

目录页面没有显示文件大小。对已观察到的 Idle 官方下载 URL 做独立 HEAD 仍返回403，说明该请求没有浏览器的登记会话；这不是原包不可下载的证明。本轮三个 PDF 都通过合法浏览器下载成功。原包字节数、断点续传能力及总量仍记 null，不编造容量/速度，也不把最小候选清单称为已验证最小下载集。

作者 train/test 分区是发布分区，不是我们的正常参考/入网/查询合同，也不证明时间先后。M1T交互目录的 `M1T_Camera_LAN_PRECORDING.pcap` 拼写已按官网原样保存，不改成推测的名称。

## 下一阶段的具体工作

1. 先确定核心正常/TCP/UDP候选原包的可恢复下载方式、真实大小和存储目的地；再按四角色覆盖、总字节和规范化路径顺序决定最小资格包集合。大文件仍优先考虑已核配额的超算个人存储，不能仅凭目录存在就当配额足够。
2. 原包到齐后，只核对包头、实际时戳、设备与控制/攻击端、直接与反向流量、背景/未知、物理包重复和独立事件数。正常需同设备真实7200秒入网窗及独立后段，历史参考必须满足真实因果顺序。
3. 直接ACK须为已标明事件中攻击向 `ACK=1,SYN=0`，细分ACK-only、PSH+ACK等。受害者响应、SYN+ACK及模拟MQTT不能替代。UDP同样不能全包一律标恶意。
4. 资格证据及外部人口、角色分割、权重 schema、预算、适配器在首次评分前封存。若关键资格不能成立，记录缺口并补材料/换候选，不能先跑模型看好坏。

登记会话已保留在内置浏览器，后续在合法会话内继续；不承诺服务端会话永久有效。不增加持续AI监测。旧获取草案与HTTP失败回执保留为历史，本回执替代“尚未取得登记后目录”的当前状态。
