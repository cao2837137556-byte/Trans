# DAD 本地正常回检与后续配对口径

**结果**　DAD 本地预检使用完整的 1,264 条周一 TCP 参考（16 个组件），在周一 23 条、周日 35 条真实查询上通过。冻结三种子集成的 RAW、原 CCNR、CCNR＋相对握手分别报 29、0、0 条。58 条查询的两种支持度均与独立冻结实现一致。

**进度**　正式回检已在 D 盘批次 `normal_20261125_7c8e71ae` 启动。只读取周一、周日各自的抓包和标签，复用预检编码。逐日保留完整双向帧前缀，严格沿用 CIC 源阈值，以原库截止帧 1,304 和首条查询帧 1,305 为界。周一建档后的 8,448 条与周日正常的 9,325 条查询的 UID 顺序已分别复现。最终表须同时复现原冻结系统每个种子与集成的 RAW、CCNR 计数，并另报相对握手引起的增减。全量结果以本批正式回执为准。[预检小表](../../p4_dad_normal_h60_local_v1_20261125/launch_receipts/PREFLIGHT_METRICS.csv) · [预检回执](../../p4_dad_normal_h60_local_v1_20261125/launch_receipts/PREFLIGHT.json) · [D 盘进度页](D:/study/paper/anomaly_detection/paper04/data_external/dad_normal_h60/normal_20261125_7c8e71ae/PROGRESS.html)

**同端点登录**　11 月 25 日复核时，本机登录目录 21 份抓包与上轮资格清单一致，均来自正常采集；项目外部数据目录未发现新的同端点候选。沿用独立留出三组各 5/1,000 的日常误报结果。攻击侧待该端点可复用的独立场景真值、双向抓包和请求级认证日志，以连接内最高合格 POST 分比较两套封存阈值的实际检出。[已验收的工作点](20261124_paper04_same_service_rank5_acceptance_codex.md)

## 表 15 的参考库

按完整参考 UID 顺序的 SHA-256 核对。表 15 的开发对照库为 P4_MAIN，上次相对握手回放的 CIC 与 UNSW 采用统一主库 P4_UNIFIED_HIST_K8192_V1。表中数量单位为条。[开发对照库资产](../../p4_head_transfer_followup_v1_20261115/HEAD_ASSETS.json) · [完整摘要](../../p4_dad_normal_h60_local_v1_20261125/launch_receipts/BANK_ALIGNMENT.json)

| 测试床 | 表 15 | 已验收的相对握手回放 | 迁移时的处理 |
| --- | ---: | ---: | --- |
| CIC | 8,863 | 9,538 | 以表 15 库的参考行重建握手值并重新匹配 |
| UNSW | 66,082 | 90,658 | 以表 15 库的参考行重建握手值并重新匹配 |
| Edge | 4,124 | 4,124 | 参考 UID 及顺序一致，核对查询 UID、几何与时间资格后可复用握手结果 |

三种子 MLP、TabM、CatBoost 和 SLAD 分别沿用原头的源阈值与扣分尺度。Win10 回放单列同次采集跨主机诊断，r1 曾使用 .152 和 .190 训练。三组在同一批查询上分别计算 Win10 的净增检出、原漏检队列中救回的连接，以及 CIC、UNSW、Edge 的新增正常误报与原泛洪变化；根据这些配对取舍选择论文主版本。[r1 来源和回归结果](../../p4_password_aug_v1_20261120/received/r1/RESULTS_FOR_PAPER.md)

## 给 anti 的两处合稿核对

- v14 表 M3 的“新正常连接 0/93”混入了 Win10 的 1 条跨文件连接。统一到“首次见于第二份正常抓包、按旁路外带数据帧判警”，三台主机为 28＋16＋48＝92 条连接，545 条查询，CCNR 误报 0/92 条连接。改为任一合格入站包判警时是 29＋16＋48＝93 条连接、1,025 条查询，其中有 2 次查询误报。连接级分子需按连接去重。原版与相对握手在三机正常侧的逐查询新增告警均为 0。[边界分层原表](../../p4_ton_password_frozen_v12_20261118/received/NORMAL_BOUNDARY.csv) · [相对握手配对](../../p4_ccnr_relative_handshake_v1_20261121/received/PAIRED.csv)
- v14 预合稿和图 7 的脚本、SVG、PNG、PDF 已在本机。v13 第 639 行 arXiv 编号正确。当前所列的八位作者与题名 *netFound: Principled Design for Network Foundation Models* 对应 2026 年 5 月 12 日修订的 v5。若保留 2023 首发年份，可同时标明所引版本和修订年。[2023 首版](https://arxiv.org/abs/2310.17025v1) · [现行 v5](https://arxiv.org/abs/2310.17025v5)
