# 固定A同池扩大评估：执行约定

2026-09-11。用户明确授权：“行，动手吧，我授权，我睡午觉去了。希望起来能看到a模型结果好嘛。”
执行一次固定A评估，异常停止、零自动重试。沿用已授权262,050目标，不扩大数据角色。

A模型是已训练40轮的candidate_A.pt，文件SHA
`1dd82c0162ab9ae3db8acb7d11560bd52fc17e8d9beb05a2d74a939f79e77093`，
tensor-state SHA `8d11b770ab98c401e4d05359e34328d8c7fa4e56b4242c2e7211e53535e457a4`。
复用原模型类、CPU float32、seed2705、4/1线程、batch32、logit>=0。
复用AB扩大评估封存的40成员、57,686上下文、548,389事件、287,355,836特征字节，
上下文排序、批次及目标前缀与AB评估相同。只加载A一次、1803次批前向；不重训、
不重新解码PCAP、不载入AB或旧P2、不重新评分AB、不调整阈值或候选。

读取并验证原AB完整输出SHA封存；新A预测逐UID附加到原AB预测记录，不改原字段。
输出旧P2→A、旧P2→AB及A→AB三组同目标指标，保留各攻击族、来源、池与旧输入
可用性分层。监督器独立重连AB记录、验证hard规则、核对模型状态并重算全部指标。
执行成功只代表得到可靠比较，不改变旧严格继承FAIL，不预设性能结论。

新实现9项生成数据测试通过：三组指标、序列化、AB字段保护、零阈值/非有限拒绝、
真实模型类的合成输入前向、前缀/目标错位拒绝、A/AB报告列、失败停止与重复目录拒绝。
两个PowerShell脚本语法通过。沿用此前23项冻结输入语义测试，不重跑历史审计。
真实启动前另在相同两进程Job内验证完整封存就绪入口；直接调用已固定Git本体。

新监督预算30分钟、8GiB聚合内存、512MiB新输出；这是本次短评估上限，不是预计耗时。
Windows Job约束、先gate后worker、持久进度、失败原因、终态封存均保留。
实现封存：`runs/frontend_a_expanded_eval_implementation_v1_20260911/`。
唯一真实输出：`runs/frontend_a_expanded_eval_v1_20260911/`。
启动：`scripts/start_frontend_a_expanded_eval_local.ps1`。
状态：`scripts/show_frontend_a_expanded_eval_status.ps1`及真实目录status.md/status.html。
终态：supervisor_terminal.json与完整SHA256SUMS；成功结果result.md/comparison.json。

全部为已暴露开发复评，无新ID测试、独立确认或新设备入网证据。
true FINAL、其他select/viewed、数据下载、HPC继续关闭。旧系统/旧实验产物不修改。
这些限制不要求对本次已授权的逐文件准备、核验或一次推理再次索取许可。
