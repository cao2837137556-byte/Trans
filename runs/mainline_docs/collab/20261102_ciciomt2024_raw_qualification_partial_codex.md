# CICIoMT2024 原包资格查验：正常文件已核，攻击材料尚缺

2026-11-02，America/Los_Angeles。状态：`NORMAL_HEADER_CHECK_COMPLETE_ATTACK_ACQUISITION_BLOCKED`。用户已授权必要原包定向获取及查验，要求查验后再与其他agent讨论；本稿不声称外部数据资格通过。

## 已完成的真实原包工作

通过已登记的内置浏览器定向获取 `Idle.pcap` 和 `Active.pcap`，共479,778,175字节（约457.55MiB），共1,369,566帧。下载目录原件保留，已将SHA256一致的受控副本保存到：

`D:/study/paper/anomaly_detection/paper04/data_external/ciciomt2024/qualification/`

|文件|字节|完整帧数|SHA256|
|---|---:|---:|---|
|Idle.pcap|73,715,235|328,923|`10749d98ec698db1273d2cdf65ec9c2a408d1161da55b028fb46b4b0e2861b4e`|
|Active.pcap|406,062,940|1,040,643|`a6030136b9dd80ce439b2bdab8df8a7bf7a2918478daf2cf3c509512a5fc19fb`|

完整TShark流式扫描与独立dpkt容器扫描均已完成，两份 `SCANNER_VERIFICATION.json` 均为PASS；没有把部分扫描当全量。0个截断帧。容器完整/本地哈希不是发布者提供的哈希认证，仍如实保存下载来源与本地身份。

工具与产物：

- [工具说明](../../ciciomt_raw_qualification_v1_20261102/README.md)
- [Idle头部事实](../../ciciomt_raw_qualification_v1_20261102/idle_first_scan/HEADER_FACTS.json)、[独立时序](../../ciciomt_raw_qualification_v1_20261102/idle_first_scan/CHRONOLOGY_REFINEMENT.json)、[守恒核验](../../ciciomt_raw_qualification_v1_20261102/idle_first_scan/SCANNER_VERIFICATION.json)
- [Active头部事实](../../ciciomt_raw_qualification_v1_20261102/active_first_scan/HEADER_FACTS.json)、[独立时序](../../ciciomt_raw_qualification_v1_20261102/active_first_scan/CHRONOLOGY_REFINEMENT.json)、[守恒核验](../../ciciomt_raw_qualification_v1_20261102/active_first_scan/SCANNER_VERIFICATION.json)
- [跨正常文件逐MAC事实](../../ciciomt_raw_qualification_v1_20261102/NORMAL_HEADER_CROSSCHECK.json)

## 时间条件：已有实证支持，不能误报为全条件通过

Idle实际为两个捕获片段（UTC）：

1. 2023-11-01 21:00:00.205632 → 11-02 10:00:00.352792，163,999帧，约13小时。
2. 2023-11-02 21:00:02.534706 → 11-03 09:59:59.764645，164,924帧，约13小时。

两段之间约11小时没有捕获。整个文件约37小时跨度不等于连续37小时；本轮没有拼接或平移时戳。唯一包序倒退为第260,059帧的1微秒。

Active实际有9个按原始记录中大于1小时空洞分出的观察片段，日期为UTC 11月6、7、8、9、15、16、22、23、24日；每段跨度约7,501—20,054秒。这个分段阈值是描述性时间盘点，尚未作为参考/入网/评价分割规则。第一段虽然长于7200秒，但全网只余约301秒后段，不能仅凭跨度宣称正常评价量充足。唯一倒退为第87,459帧的3微秒。

Idle全部早于Active，真实历史先后已观察到。两文件共有13个可见单播MAC，其中含网关、控制器或模拟端，不能称为13台真实目标。多数共有MAC在各Active片段都具备7200秒跨度和后段包，具体量在机器交叉表中；目标身份和最终人口仍须闭合。IPv6、非IP和模拟MQTT也不能直接并入我们可检测的真实目标人口。

正常文件内的ACK、PSH+ACK、UDP只证明正常行为覆盖，不能证明直接ACK/UDP攻击资格。文件包含正常SYN发起，适合继续检查C2守卫的正常代价，但本轮没有计算检测分数或误报。

## 攻击原包尚未完成获取

当前必要候选仍是已观察到的官方test目录内：

- `TCP_IP-DoS-TCP_test.pcap`
- `TCP_IP-DoS-UDP_test.pcap`

专用文件下载接口多次等待超时，TCP最后一次请求180秒但接口实际仍在120秒超时；没有新完整文件。普通链接导航显示“此页面已被ChatGPT屏蔽／ERR_BLOCKED_BY_CLIENT”，未提供更细的拒绝理由。没有通过修改代理、安全配置、导出会话或其它绕过方式继续。

Downloads保留一个283,035,192字节的未完成 `.crdownload`，未生成已核验的攻击原包身份，后续观察未增长。不能称它仍在正常传输、完整攻击文件或可恢复已验证分片；本轮不据其推导总体攻击分布，也未删除它。

已请求用户在自己已登记的Chrome中取得上述两个文件，保存到默认Downloads；这是一项具体工具阻塞的手动交接，不是重复申请原包或实验授权。页面入口仍为：

`https://cicresearch.ca/IOTDataset/CICIoMT2024/browse.php?p=WiFI_and_MQTT%2Fattacks%2FPCAP%2Ftest`

## 后续顺序

1. 两份攻击原包到达后，先验证完整性，流式统计TCP flags、UDP、事件时间和端点方向，不给全包一律攻击标签。
2. 结合原包可见设备身份线索、已有LEARN/A/B登记与官方来源，闭合真实目标/网关/控制器/攻击端；私网IP相同不代表同一设备，OUI也不能唯一命名。
3. 明确直接攻击、反向响应、背景与未知，并核对所需的直接ACK=1/SYN=0以及UDP攻击资格。若首个TCP候选没有所需证据，再根据已封存候选目录有界补充，不能根据模型表现选攻击。
4. 查验完成后再按用户要求，将完整证据交给其他agent独立讨论适用性、足量性、因果角色和存储预算，继续文档方式回写。当前状态为 `DISCUSSION_PENDING_QUALIFICATION`，没有提前宣布通过或提交外部模型评价。

C5 p=3与A/B开发冻结保持；本轮模型/编码/距离/训练/云端作业均0。无持续AI监测，当前没有成功启动的攻击下载或外部实验后台任务。
