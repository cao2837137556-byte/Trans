# Edge v2 Linux工程验证交付

结果：用户已明确授权一次1CPU、8GiB、2小时工程验证；具体启动状态见STARTUP.json，实时状态见PROGRESS.json。
影响：只运行v2工程门，不启动正式外部质量评价。原模型、原包和封存科学源码复用；v2使用新checkout与输出目录，v1证据保留。
下一步：普通程序自动更新进度、单次提交、取回小型回执并验收；出现失败不自动重投，不延长计算预算。

进度页：<http://127.0.0.1:18793/>。已请求在当前Codex对话右侧打开；页面只读，每4秒刷新。普通程序每15秒读取远端状态，最长观察4小时，排队时间不计入作业2小时墙钟预算。无需AI持续监测。

## 授权与执行约束

- ENGINEERING_CARD.json由已验收v2草案晋级，科学输入、完整依赖pin与计算预算保持一致。AUTHORIZATION.json记录用户原话、卡SHA和最多一次提交。
- CPU=1，Slurm内存8192MiB，墙钟02:00:00，no-requeue；程序无自动重投/延期。正式评价仍未授权。
- 节点临时盘必须是与共享输出不同设备的本地文件系统，启动时空闲不少于32GiB，应用scratch守卫24GiB，输出守卫24GiB。
- 站点amd分区的Slurm TmpDisk登记为0；原始`--tmp=32768`在test-only阶段被拒绝，未提交作业。修复仅移除这一条无法匹配的调度字段，实际节点32GiB空闲门和24GiB使用守卫保留，**没有调度器磁盘预留保证**。原slurm保留，适配脚本逐字节核验和SHA见PREPARE_RECEIPT.json/site_adapter。
- 只复用用户手工建立的SOCKS隧道，不启动VPN、SSH认证或恢复登录。私有通道配置和bootstrap命令不进Git。

## 本地入口

`progress_server.py`仅提供本地只读页面。`pipeline.py`负责传输、核验、持久化提交意图、读取调度状态和下载小回执；缺少提交确认时只读核对，不再次sbatch。正式作业号必须以SUBMIT_RECEIPT.json为准，sbatch --test-only打印的预测编号不是已提交作业。

远端remote_receiver.py及站点修复实例在项目个人目录监听loopback18821，4小时后关闭。其安装和启动已通过用户现有远程Linux终端完成。prepare_delivery.py用于初次生成材料，**不要对已启动的部署再次执行**，它会重新生成私有通道配置。

从已完成的863件基包构建隔离checkout，原资产只读硬链接；增量117件逐项验大小和SHA。完整raw继续在原远端路径使用，不重传模型或原PCAP。完整spool和恢复编码批次不下载，仅导出JSON回执、小日志及其清单。

只有调度器COMPLETED/0:0、当前attempt及候选回执SHA、冻结Linux身份、73形状、64,124逻辑端点、恢复字节一致性、资源限制与清理均通过，才写FINAL_ACCEPTANCE.json/PASS。进度中RUNNING或调度器COMPLETED本身均不代表验收通过。

## 故障与工程验证

新增10项交付检查覆盖资源合同、分块SHA/偏移、路径范围、远端及本地不重复提交、丢失响应的只读核对、卡晋级不改科学绑定、站点适配只改TmpDisk及适配后资源篡改拒绝。

首轮test-only拒绝及当时源码/本地状态保存在repair_history/tmpdisk_zero。修复接收器前已从远端确认SUBMIT_ATTEMPT和SUBMIT_RECEIPT都不存在；修复只恢复准备阶段，不是作业重投。远端原接收器文件和失败日志也保留，新的站点适配实例另名启动。
