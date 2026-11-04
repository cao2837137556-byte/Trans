# Edge v2 Linux工程验证181645启动

结果：用户授权的唯一工程作业181645已提交并运行；启动读回为RAW_PREFIX_REPLAY/NORMAL，当前attempt身份与授权卡一致。
影响：按1CPU、8GiB、02:00:00执行；不重训、不生成正式外部检测成绩、不自动延期或重投。v1及v2封存科学源码、原包、模型和旧失败证据保持。
下一步：普通程序持续更新进度，并在调度结束后取回小回执、校验当前attempt与工程接受门；无需AI持续监测。最终Linux工程验收目前PENDING。

## 启动证据

[STARTUP.json](../../edge_formal_gate_deployment_v2_20261103/STARTUP.json)记录启动观测；[调度与worker读回](../../edge_formal_gate_deployment_v2_20261103/STARTUP_READBACK.json)显示`181645|RUNNING|0:0|00:01:17||1|8G|02:00:00`。这是运行中快照，不是完成或验收通过。

[提交回执](../../edge_formal_gate_deployment_v2_20261103/SUBMIT_RECEIPT.json)确认唯一作业号181645；准备阶段`sbatch --test-only`输出的181644只是预测编号，不是已提交作业。授权卡SHA为`54ad4848a9fe66864ba3fd0c6db489dc7461ed33985b6d66372509ca5692882f`，引用用户原话的[授权记录](../../edge_formal_gate_deployment_v2_20261103/AUTHORIZATION.json)已绑定该卡。

原863件基包及117件交付成员在远端核验，冻结运行时身份与v2卡一致；模型和PCAP没有重传。新checkout只读硬链接冻结资产，工程输出使用独立目录。新增交付/站点适配10项本地测试通过；既有v2的82项科学及恢复工程检查未被这些新测试替代。

## 本次发现并关闭的站点适配问题

amd分区`sinfo -h -p amd -o '%P %c %m %d %t'`返回`amd* 128+ 386268+ 0 mix`，即Slurm未登记可请求的TmpDisk容量。最初包含`#SBATCH --tmp=32768`的test-only被拒绝，此时远端SUBMIT_ATTEMPT与SUBMIT_RECEIPT均不存在。

修复只在包外创建适配slurm，删除这一条不受支持的字段；原脚本和失败证据保留。1CPU、8192MiB、02:00:00、no-requeue以及worker入口逐字节保持；适配脚本SHA为`5f510c7f78c0c0dda6dbc54a632f4aad7d85726793b75d2e4a1e988607909e54`，再次test-only通过后才实际提交181645。

节点/tmp必须通过本地文件系统、与共享输出不同设备、至少32GiB实际空闲检查；scratch/output各24GiB使用守卫保留。**没有Slurm临时盘预留保证**，32GiB是实际节点空闲准入条件。见[准备回执](../../edge_formal_gate_deployment_v2_20261103/PREPARE_RECEIPT.json)及repair_history/tmpdisk_zero。本次修复发生在提交前，不是失败作业的自动重投。

## 进度与后续读取

进度页：[Edge v2 Linux工程验证](http://127.0.0.1:18793/)。已向当前Codex对话右侧发送打开请求；打开工具返回queued，返回该对话时显示。页面只读，普通程序每15秒读远端、页面每4秒刷新；持续连接由用户已建立的VS Code隧道提供，未启动VPN或新SSH认证。

普通程序最长观察4小时，排队另计，计算作业墙钟仍为2小时；4小时是本地读取/取回窗口，不是额外计算授权。若连接中断，页面明确显示，不把未知状态当成功，不自行重新登录或重投。大spool、E3及数据库保留超算，仅取回小型JSON回执、日志和SHA清单。

最终只认FINAL_ACCEPTANCE.json及其绑定的调度终态、CURRENT_ENGINEERING_ATTEMPT、候选SHA、冻结Linux身份、73形状、64,124逻辑端点、真实恢复字节一致性和资源/清理门；RUNNING或调度器COMPLETED单独都不算PASS。此次无已知启动故障，完成交付记录后结束当前轮次。
