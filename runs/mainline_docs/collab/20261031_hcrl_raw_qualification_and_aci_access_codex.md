# Codex → Antigravity：HCRL 五包实测不满足两小时合同，ACI 访问仍待解决

日期：2026-10-31。状态：`HCRL_REJECT_SAME_CONTRACT_INSUFFICIENT_NORMAL_HISTORY`。

用户已允许两条有界任务，并明确继续。本轮只执行五个原始包的格式、时长、身份和规则核验，以及 ACI 公开说明访问检查。未提取模型特征、训练、跑外部模型评价或加入当前 A/B 参考库。主线 D2 单独记账。

## 结论

HCRL 的 `benign-dec.pcap` 实际只有 **301.089296 秒（约五分钟）**，137,396 个包，时间顺序正常；两小时之后正常包数为 **0**。EZVIZ 所见跨度301.089296秒、NUGU298.855053秒。因此不能满足当前 A/B 的 `7200s` 入网观察加独立后续正常评价，不能作为同口径主泛化验证集。不得把五分钟拉伸到两小时、重复播放、缩短主合同或将攻击包的 `!rule` 自动充作正常历史。当前五包资格核验在此结项，不扩大下载。

它可留作另行声明的短窗口辅助诊断材料，但本轮不因此创建新实验。不能把“这批材料不合格”写成“跨数据集泛化无效”。后续数据筛选应先取得足够正常历史的捕获证据，再进入原包获取。

## 获取与实测

从 HCRL 官方网站指向的 Dropbox ZIP 读取中央目录，再仅获取五个选定成员的压缩字节范围。官方整包863,725,990字节未整体下载；成功获取这五包的请求共传输67,333,618字节（另有先前小规模目录/连通探测），解压后154,060,143字节。每个成员的ZIP CRC、未压缩长度均匹配，并记录本地SHA256。CRC不是官方独立发布的SHA认证。

原始文件位于 `D:/study/paper/anomaly_detection/paper04/data_external/hcrl_iot_network_intrusion_2019/raw_selected/`。全部为 Ethernet pcap；Wireshark 4.6.6的`capinfos`和`tshark`按实际包时间测量。表中为包数，绝非模型评价行数。

| 文件 | 实际跨度/秒 | 全包数 | 原规则并集 | 反向TCP四元组匹配候选 |
|---|---:|---:|---:|---:|
| benign-dec.pcap | 301.089296 | 137396 | 0 | 不适用 |
| dos-synflooding-1-dec.pcap | 43.761697 | 40788 | 18704 | 17417 |
| dos-synflooding-4-dec.pcap | 48.224856 | 10561 | 4692 | 3516 |
| scan-hostport-1-dec.pcap | 74.188566 | 29352 | 1490 | 1015 |
| scan-hostport-4-dec.pcap | 45.350095 | 7801 | 1707 | 1257 |

五包全包数全部匹配官方说明。Scan同时执行Host Discovery与Port Scanning两条原规则，不能只取文件名所在行。EZVIZ SYN官方表列18703，当前原样规则实得18704，相差1包，保留差异，不擅自删包对齐；其余规则计数一致。

反向候选定义为：原规则匹配的攻击TCP包反转IP/端口四元组，在未匹配原规则包中找对应包；它不是将全部反向流自动定为恶意。更宽的“受害端向攻击地址/攻击网段响应”审计层，四个攻击包分别为17772、3640、1039、1261包。两者有包含关系，不相加，不合并成正常分母。

还有两项质量事实需保留：所有包的`frame.cap_len`都比`frame.len`短，差值为25/44/48/52字节；五包分别有11/20/5/8/9个Wireshark malformed标记。当前证据不能区分封装转换保留原长度与真实载荷截断，不能直接声称数据完整或全部载荷丢失。主设备MAC存在，但有少量异常IP解析；正常历史时长已构成独立淘汰条件，本轮不额外进行修复、改包或模型接入。

## ACI-IoT-2023

重新读取官方页面 `https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023`，HTTP200。页面仍明确显示`Subscription Required`、`LOGIN TO ACCESS DATASET FILES`。Attack Timesheets标为2.5KB，但可见链接为`#`，不是可下载文件URL；README只有说明文字，没有独立公开文件链接。页面提到的正常历史时长仍未通过原文件核验。

因此状态是 `PUBLIC_METADATA_READ_PAYLOAD_ACCESS_GATED`，不能登记“时间表已拿到”或“ACI已通过两小时合同”。本轮未注册、订阅、付费或下载32.27GB PCAP，也不尝试绕过访问条件。

## 证据

`runs/generalization_hcrl_qualification_v1_20261031/`：

- `ZIP_DIRECTORY.json`、`DOWNLOAD_RECEIPT.json`：官方来源、成员范围、传输字节、CRC和SHA。
- `QUALIFICATION.json`：实际时间、设备计数、逐条规则、反向响应审计。
- `*.pcap.capinfos.txt`、`CAPTURE_LENGTH_AUDIT.json`：格式/长度/解析质量。
- `ACI_CURRENT_PAGE.html`、`ACI_ACCESS_RECEIPT.json`：本次官方访问证据。
- `fetch_selected.py`、`qualify.py`：定向获取和只读核验实现。

以上不产生新FPR/召回率。后续主线仍是180435的真实邻居证据，而非依靠更换评价集证明当前方案合格。
