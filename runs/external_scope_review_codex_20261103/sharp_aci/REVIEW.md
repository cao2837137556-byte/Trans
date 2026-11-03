# SHARP 与 ACI 公开材料独立复核

结论：保留两个元数据候选；尚未确认任一满足 S1–S6，不能开模型评价或先下大包。
影响：SHARP 的纸面结构确实合适，但存在 DOI 元数据不一致；ACI 的“30 台、800 万包、正常 5%”尚不能升级为事实。
下一步：经合法文件权益取得设备/攻击小文档与成员清单后，先核查身份、攻击范围、逐设备实际时序；不要求现在购买订阅。

## SHARP：官方页可证与需修正之处

[当前官方页](https://ieee-dataport.org/documents/sharp-smart-home-attacks-across-residential-multi-protocols)与 DOI 解析页本轮均返回 200。它确认 Cardiff 的 Alosaimi / Rana / Perera、CC BY 4.0、2026-09-20 创建、有人居住的两居室公寓；正常家庭运行期为 2025-06-20 至 07-05，受控活动日期为 2025-08-13。日期先后是候选证据，不能替代每台设备的连续 7200 秒观察与后段正常查询。

规模数字一致：完整包组件为 **1,677 = 512 路由器/IP + 779 Wi-Fi 空口 + 386 Zigbee**。说明中的核心组件包含其中 22 个捕获，另含全部观察表和 17 个原生 Z-Wave 日志。当前匿名可见文件列表却只有 **`v1.0.0.zip`（标示 172.24 GB）**及受限成员树 `v1.0.0_zip`；不能将“核心 22 包”误读为已经发现一个公开的小下载。

台账是 **36 个 attacks and tests**（A001–A035、A038），有时间、来源、目标和分别记录的结果判断；不是已证明 36 个成功 IP 攻击。IP/非 IP 分类、源目标规则粒度及 ACK/UDP 情况仍需台账正文。`not_assessed` 指攻击日的逐遥测观察，`attack_context` 只表明落在注册时间段，不是包级真值。不能据此直接判 S4 合格。“没有配套论文”也尚未证实，只能写本页未给出、本轮未发现。

**新的身份核查项：** [DataCite 同 DOI 记录](https://api.datacite.org/dois/10.21227/ray1-ag27)的题名却为 `"TON-IoT"`，URL 指向 `/documents/ton-iot`，摘要含临时占位文字；作者、DOI 和 2026 年份仍匹配上述三人。另一方面 `doi.org/10.21227/ray1-ag27` 实际解析到 SHARP 页面。两份正式来源存在差异，须保留两者快照并在获取清单时核对 release manifest。**这不是 SHARP 与项目 ToN 数据血缘重叠的证据，不能凭题名冲突直接判 S6 失败；也不能静默忽略冲突。**

## 小文件：确切名称与访问状态

| 候选 | 已能确认的名称 | 本轮能否独立取得 |
|---|---|---|
| SHARP | `researcher_documentation/DEVICE_GUIDE.md` | 官网可见内部路径；按公开相对链接请求返回 404，尚未取得正文 |
| SHARP | `researcher_documentation/ATTACK_GUIDE.md`、`LABELS_AND_ATTACKS.md` | 同上，两项链接均为 404 |
| SHARP | `researcher_documentation/QUICK_START.md`、`SCRIPT_GUIDE.md`、`TELEMETRY_SCHEMA.md`、`ZWAVE_GUIDE.md` | 官网明确内部路径；未证明订阅后独立文件获取方式 |
| SHARP | `metadata/FILE_MANIFEST.csv` | 官网明确内部路径，无独立公开下载链接 |
| SHARP | `02_PUBLIC_RESEARCHER_DOCUMENTATION` | 官方提到一个独立文档 archive；未列扩展名、大小或单独下载地址 |
| SHARP | 攻击台账、设备 inventory、标识映射、README | 用途明确，确切文件名/成员路径尚不可见，不能杜撰 |
| ACI | `Attack Timesheets`，2.5 KB；受限树标识 `Timesheets_zip` | 已是单独顶层文件项，但匿名链接为 `#` 登录弹层；实际 archive/member 文件名与订阅下载尚未核验 |
| ACI | `ACI-IoT-2023-README` | 只是官方给出的 README 标题，扩展名与成员路径未知，无独立公开链接 |

两页都写 `Subscription Required`。普通 IEEE 免费账号不等于 DataPort 文件权益。两者可能由同一有效 DataPort 订阅覆盖，但本轮没有账户权益证据，不保证机构权限已解锁每项。SHARP 页面提到 AWS 与受限成员树，这是可查的获取途径，不能据匿名页承诺“无需整包就一定可下载全部小文件”。下一步应先查看合法账户下的文档目录/归档成员清单；**不先取 172 GB zip**。ACI 时间表已单列，可优先请求该小项，仍不先取 32.27 GB PCAP。

## ACI：五天有摘要支持，其余规模数保留为未知

作者原始论文是 **Emily A. Nack / Morgan C. McKenzie / Nathaniel D. Bastian，MILCOM 2024，DOI [10.1109/MILCOM61039.2024.10773916](https://doi.org/10.1109/MILCOM61039.2024.10773916)**。当前 OpenAlex 对该原论文的摘要索引支持物理设备、有线/无线、五天采集与正常/攻击混合；索引不是本轮取得的论文正文。此前已有 Crossref 作者题名证据，与本轮一致。

本轮官方 DataPort 页、该摘要均未确认 **30 台、约 800 万“包”、正常 5%**；尤其没有确认 800 万究竟是包还是导出特征记录。因此这三项只能写“第三方说法，未核”。检索没有找到能支撑它们的作者全文，不能以检索失败断言它们是错的。即使将来确认“正常 5%”，比例也不能推出正常时长不足；应按每台设备的真实时钟核查 S3，不能据此降低候选资格。

DataPort 当前列 32.27 GB PCAP、596.91 MB labeled netflow、5.15 GB labeled payload 和 2.5 KB 时间表。五天总时长及标签导出文件存在，都不能证明合法事前观察窗、同一设备、方向标签或直接 ACK/UDP 攻击成立。

## 本轮证据与限制

`EVIDENCE.json` 保存逐条判定、源 URL、访问状态、小文件清单与关键文件 SHA256。公开页面、DataCite/OpenAlex JSON 和 404 响应均保存在本隔离目录。Google 返回 JavaScript 跳转壳；Bing 精确查询返回无关 ACI 结果，均未当事实依据。未登录、填表、发信、购买或下载原始捕获；没有模型输出或距离介入。
