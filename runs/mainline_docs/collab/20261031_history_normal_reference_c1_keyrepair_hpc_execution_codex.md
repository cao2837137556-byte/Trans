# 历史正常参考 C1 技术修复与超算提交

2026-10-31 15:59（北京时间）已提交独立修复作业 **180435 / node185 / amd**。Slurm和真实worker均已确认RUNNING。当前尚无新DEV/A/B指标，2%目标效果未知。用户要求“修复问题，然后提交；提交”，本轮直接落实已有授权；确认启动后结束AI跟踪，不创建自动跟踪任务。普通只读进度程序继续更新[Codex右侧进度页](http://127.0.0.1:18787/)。

## 原故障与修复边界

原作业180433在14:43:26至15:33:38运行50m12s，Samsung ENDPOINT_CENSUS时抛出MISSING_NAMESPACE_HEADERS并以1:0失败。已编码24163行、距离对0、DEV与A/B均未评价。技术失败不能解释为误报方案失败。

原始Samsung逻辑帧255553（原始序号255553，时间1475636074.743651）是IPv4/UDP分片，IP对192.168.1.249→192.168.1.208、偏移185、无UDP端口。随后部分首分片在冻结TShark解码中同样无端口。窄区间8192包中282行缺失端口，已直接验证旧前端于对应帧停止。

新历史专用适配器hnr/contexts.py不补零、不推断端口、不预过滤报文。未知端口污染相同owner、IP版本、协议和无向IP对内全部既有/后续会话；每个兼容报文延长污染，仅真实相邻间隔>60s后清除受影响状态。last_seen与永久毒化保留；缺IP、组时间回退及账本超限继续停止。不同IP/协议和普通完整输入与冻结前端逐字节一致。两遍完整解码使用同一规则。该处理可能减少历史可用点，未放松科学保护门。

新包和输出独立，原包/输出/锁完整保留；全部三成员重新处理，不采用旧作业部分编码。冻结模型、参考选点、SALT、阈值、C1/P-DEVONLY、历史双截止、DEV先门及一次A/B标准不变。

## 验证与提交证据

- 本地及超算各64项测试通过，新增8项覆盖分片缺端口、同IP异端口/反向污染、隔离、持续流量、恰好60s及>60s、缺IP、回退/永久毒化、双遍及SQLite换页一致性。
- 实际故障附近8192包两遍回放均完成，合法端点5943、快照摘要和原因计数一致；无E3前向或A/B评价。诊断只证明此故障修复，不能证明全量流量无其他未知异常。
- Linux Python3.11.11 / NumPy2.0.1 / Torch2.5.1通过超算验收，输入READY；1435项身份与封印核验通过。本次上传736605字节，1393份相同文件复用，未复制大数据。
- 固定4CPU /16GiB /8h /20GiB、no-requeue；无自动科学重试。DEV失败即停止，只有通过后才评价一次A/B；无训练。
- sbatch返回180435，提交UTC 2026-10-31T07:59:16.350999+00:00；worker启动UTC 2026-10-31T07:59:29.969155+00:00。最新观察到TP Link完整两遍读取79773包，已保存11875个选点快照。

机器回执：[STARTUP_ACCEPTANCE.json](../../history_normal_reference_keyrepair_deployment_20261031/runtime/STARTUP_ACCEPTANCE.json)；[原始启动读回](../../history_normal_reference_keyrepair_deployment_20261031/runtime/STARTUP_REMOTE_READBACK.json)；[实际区间回放](../../history_normal_reference_keyrepair_diagnosis_20261031/RAW_REPLAY_RECEIPT.json)。修复包位于runs/history_normal_reference_keyrepair_v1_20261031，交付位于runs/history_normal_reference_keyrepair_deployment_20261031。

关键SHA256：本地代码封印bff596c6b13e5f706e469e02c321b51972260caea6b1469bef8613f7eba54f0f；远端仅路径迁移封印a1cefa8f473f40afac7a91055cf69329939c87156ab9a4c4dc7f0fa454473b3d；交付清单78800092b87ddb79103212eca27ee279ac3eb56ef0be1dd4bf1945529cf5240a。旧包封印31ab70c41014427a49c5ce134dba269e2bbade54e911ca5e1d674ab3ad95b84e保持。
