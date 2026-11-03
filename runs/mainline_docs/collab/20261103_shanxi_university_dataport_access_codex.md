# 山西大学 IEEE DataPort 访问核查

结果：已确认山西大学订购 IEEE IEL；未找到公开的 IEEE DataPort 订阅证据，结论为 `NO_PUBLIC_SUBSCRIPTION_EVIDENCE_FOUND`，不是“确认未订”。
影响：目前不能承诺通过学校取得 SHARP / ACI 的受限小文档；无需先购买个人订阅或下载大型原包。
下一步：在学校许可的访问环境下核实 DataPort 实际权益，或由图书馆明确答复；Edge 工程准备不依赖这一步。

核查时间：2026-11-03，官方页面读取于约 11:37 UTC。通过内置浏览器只读查看；没有登录校园门户、发送咨询、提交申请或下载原包。

## 官方证据

| 页面 | 实际可见信息 | 可得结论 |
|---|---|---|
| [图书馆数据库目录：DataPort](https://lib.sxu.edu.cn/databaseguide/web_dataBaseHome2?sorttype=1&pageIndex=1&keywords=DataPort) | “检索到 0 条结果” | 公开目录未列出 DataPort；不能据此断言未订 |
| [图书馆数据库目录：IEEE](https://lib.sxu.edu.cn/databaseguide/web_dataBaseHome2?sorttype=1&pageIndex=1&keywords=IEEE) | 2 条结果，其中一条为 IEEE Electronic Library，另一条为描述中含 IEEE 的专利平台 | 未见单列 DataPort |
| [IEEE IEL 订购详情](https://lib.sxu.edu.cn/databaseguide/web_dataBaseDetail?databaseid=ieeejournal) | “采购类型：订购”；资源为标准、期刊、会议；访问地址为 `https://ieeexplore.ieee.org/` | 已确认 IEL/Xplore 订阅；该页没有 DataPort 权益说明 |
| [官方校外访问](https://lib.sxu.edu.cn/navigation/web_detailspage1?id=BJ1uj6KDipFBAiWK&c_id=P4%5E26Jzz38DeDCb&cataID=BFCc6Jz0kYCYJGh) | 提供 [WebVPN](https://webvpn.sxu.edu.cn/) 与 [EasyConnect](https://vpn.sxu.edu.cn/)；说明使用信息门户的用户名、密码 | 已找到校外认证入口；VPN 本身不证明 DataPort 权益 |

## 最小后续动作

用户目前在外，无需立即操作。待已有校园访问环境可用，先检查 DataPort 的机构权益及 SHARP/ACI 小文件树；若仍没有明确权益，由图书馆确认是否订购/试用 DataPort（须明确不是 IEL/Xplore），以及是否覆盖 Standard Dataset 下载。

已有独立核查清单提供了未发送的询问草稿：[INDEPENDENT_CHECKLIST.md](../../shanxi_dataport_access_review_20261103/INDEPENDENT_CHECKLIST.md)，SHA256 `05dedb6de24cf00f99360659e0ae594d40f242a9a55fc94b4432b69cc7e35da7`。

最小获取范围不变：SHARP 的设备/攻击说明及文件清单，ACI 的 Attack Timesheets（页面标称约 2.5 KB）和 README。即使取得权益，也须先确认小文件可以单独获取，并完成既定数据资格核验；不以取得订阅代替数据合格。

Edge 外部测试 1 仍处于工程准备阶段：需 Linux Python 3.11 同切片严格一致性预检、全量续跑 worker 与实际预算，执行卡尚未冻结，尚无正式外部评价结果。详见[现有工程回执](20261103_edge_engineering_progress_and_dataport_codex.md)。
