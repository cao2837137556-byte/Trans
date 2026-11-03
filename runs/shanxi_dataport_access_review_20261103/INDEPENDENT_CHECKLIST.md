# 山西大学 IEEE DataPort 权益核查清单

结果：既有材料只能证明 SHARP/ACI 文件访问有 DataPort 权益门，不能证明山西大学已订或未订。
影响：应分别核对学校订阅、当前账号/网络的实际权益、所需小文件能否单独获取。
下一步：主 agent 查学校官方目录与校外访问入口；没有公开证据时保留“未确认”，不先购买或下载整包。

2026-11-03。独立只读复核本地既有资料；未浏览主 agent 的页面，未联系他人、提交表单、购买、下载原包或运行模型。

## 判定证据

| 判断 | 最少需要的证据 | 不能替代的材料 |
|---|---|---|
| 学校已订/正在试用 | 山西大学（Shanxi University）图书馆明确列出 **IEEE DataPort**，并有当前有效期/访问说明；或图书馆/平台直接确认 | IEEE、IEL、IEEE Xplore 论文库条目；学校有 IEEE 论文下载权限 |
| 目前具备文件权益 | 经学校官方许可的 IP/远程访问或已有合法账户，DataPort 实际显示有效机构权益且小文件可访问 | 未登录的 Subscription Required 弹层；VPN 已连通；有普通免费 IEEE 账号 |
| 不具备当前权益 | 明确的机构未订确认，或已正确走官方认证后得到适用于当前账户/机构的明确无权结果 | 公开目录搜索无结果、官网暂时打不开、搜索引擎无命中、匿名页面需登录 |
| 可按最小材料推进 | 有权益后的实际文件树/下载结果显示所需小说明文件可单独取回，核对内容与版本 | 说明正文提到某 archive/内部路径；只显示大 ZIP 的页面 |

公开目录未命中时应写 `NO_PUBLIC_SUBSCRIPTION_EVIDENCE_FOUND`，不要写 `CONFIRMED_NO_SUBSCRIPTION`。山西大学是 **Shanxi University**，不可混用陕西高校的 Shaanxi 域名或目录。

## 当前最小需求与替代顺序

1. **优先现有合法权益**：学校 DataPort 机构订阅/有效试用；若用户本就有有效的相关 IEEE Society 权益，也可核实其实际 DataPort entitlement。既有匿名页面声称 subscribers 包含 Society members，但这不是“普通 IEEE 免费账户都可下载”的证明，也不据此建议新付费。
2. **SHARP 只取支持文档**：`researcher_documentation/DEVICE_GUIDE.md`、`ATTACK_GUIDE.md`、`LABELS_AND_ATTACKS.md`、`metadata/FILE_MANIFEST.csv`，以及确切名称待确认的设备映射/攻击台账。官网文字提到 `02_PUBLIC_RESEARCHER_DOCUMENTATION`，但独立 URL、扩展名、大小尚未证实。三个公开相对 guide 链接此前实测 404，不能猜 URL 兜圈或触发 172.24 GB 整包。
3. **ACI 只取时间表及 README**：页面单列 `Attack Timesheets` 2.5 KB，受限树标识 `Timesheets_zip`；README 显示名 `ACI-IoT-2023-README`。归档扩展名和实际成员仍待登录后核实。不取 32.27 GB PCAP 来代替这些未知项。
4. **无学校权益证据时**：先把准确询问内容交给用户，或经用户明确授权后联系图书馆/作者请求上述小文档的合法获取途径；本清单不授权发送。BCCC 可准备元数据申请草稿，但不自动提交个人资料、接受条款或把它当已合格测试 2。

小材料到手后仍须按统一 S1–S6 核验真实目标、7200 秒正常窗、攻击时间/方向、标签与血缘。订阅成功只解决获取，不解决实验资格。

## 可转发的图书馆询问草稿（未发送）

> 您好，请问山西大学目前是否订购或试用 IEEE DataPort 数据平台（不是 IEEE Xplore/IEL 论文库）？如有，校外师生应通过哪个官方入口认证，是否支持下载 Standard Dataset 文件？我们目前只需 SHARP 数据集的研究者说明/设备与攻击台账，以及 ACI-IoT-2023 的 Attack Timesheets（约 2.5 KB）和 README；希望先取得这些小资料，不下载整套大型 PCAP。烦请提供当前有效的访问方式或可咨询部门，谢谢。

## 本轮依据

- [既有候选复核](../mainline_docs/collab/20261103_external_candidate_survey_review_codex.md)
- [既有 DataPort 访问检查](../edge_external_test1_engineering_v1_20261103/DATAPORT_ACCESS_REVIEW.md)
- [SHARP 官方页](https://ieee-dataport.org/documents/sharp-smart-home-attacks-across-residential-multi-protocols)
- [ACI 官方页](https://ieee-dataport.org/documents/aci-iot-network-traffic-dataset-2023)
- [DataPort 机构订阅介绍](https://ieee-dataport.org/institutional-subscriptions)

本文件只制定证据判别与最小获取清单，不报告本轮实时学校目录查询结果；该结果由主 agent 的独立浏览器检查另行回写。
