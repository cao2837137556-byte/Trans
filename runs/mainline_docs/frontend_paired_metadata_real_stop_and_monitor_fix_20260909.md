# B 元数据真实读取中止与监测修复

日期：2026-09-09。真实尝试状态：`INPUT_OR_EXECUTION_STOP`，CLOSED。
修复版状态：合成验证 22/22、PowerShell 解析 2/2；真实 V2 未启动。

## 发生了什么

用户授权的一次 B 包头元数据读取已经执行。约 217.234 秒时，监测器遍历输出
目录，先 `is_file()` 再 `stat()`。与此同时，worker 正常将 `progress.json.tmp`
原子替换为 `progress.json`；临时文件在两次查询之间消失，触发
`FileNotFoundError [WinError 2]`。监测器随后终止整个 Job，退出码 124。
这是本次监测实现的竞争条件，不是模型、流量或继承能力失败。

真实证据：`runs/frontend_paired_metadata_v1_20260909/`，其 SHA256SUMS：
`9754596fde836e9ac231341b74a02e899ee89fb19f233bd98b3f46345867499e`。
worker_count=1、restarts=0，聚合峰值上界 372,559,872 字节；没有达到资源上限。
原始容器身份校验完成 2 个文件、25,002,052,527 字节。

最后持久进度为 7,165,077/8,207,642 包、6,732/6,737 B 目标、21/22 成员。
这是最后观察量，不能当作停止瞬间的精确总量。全部描述符当时仍在内存，
目录只有 attempt/progress/worker_gate/supervisor_terminal/SHA256SUMS，
没有描述符、worker_terminal 或分组名单。因此不能从第 22 成员续接，
也不能声称“只需补最后 5 条”。这里的剩余 5 条不是攻击漏检数。

## 已完成的工程修复

保留全部 V1 源码、验收包和失败封存，新建 V2 controller/helper/scripts。
目录大小查询对每项只做一次 stat；临时文件消失时重新取完整目录快照，最多
三次。不吞掉持久文件消失，不返回不完整加总；持续不稳定则明确停止。
最后资源检查的异常也进入终态封存。三次仅是文件状态采样，不是实验/解码重试。

22 项本次生成测试包括：确定性复现旧竞争、完整重采样、第三次成功、三次
不稳定停止、持久文件消失、单次 stat、目录忽略、大文件不漏计、命名空间
隔离、生成原子写入的 supervisor 集成、终态异常封存；同时将原 controller
测试绑定 V2 重跑，覆盖授权拒绝、禁止重启、超时、输出超限、子进程清理、
成功/停止封存与状态篡改。两个 V2 PowerShell 脚本解析通过。

测试与快照证据：`runs/frontend_paired_metadata_monitor_fix_v2_20260909/`。
V2 可执行封存包：`runs/frontend_paired_metadata_implementation_v2_20260909/`。
原 45/45 验收保留为未改变解析/分组/解码代码的历史证据，未声称本次在 V2
重跑全部 45 项。本次 22 项才是新增运行证据；均为生成数据和可丢弃进程，
真实包解码与模型调用均为零。没有重复真实资源试验。

V2 复用 V1 runner 和分组核心，只隔离 package/real 输出命名空间，
不改变 seed、配方、解析字段、输入身份、分母、分组规则、覆盖门槛或资源限额。
V1 的源码/文档 pins 和 17 个 runtime pins 一并保留并重新核验。
只读就绪检查结果及完整性核验见 V2 包和修复证据中的 final_verification.json。

## 下一步与授权边界

本次一次真实授权已经消耗，未自动重读。下一步是另行明确授权一次 V2
真实 B 元数据读取与名单封存，从头进行身份校验和单遍包头读取：
6,737 B 目标、22 成员、最多 8,207,642 包、3,600 秒、聚合 8 GiB、
输出 64 MiB、零实验重试。启动入口为
`scripts/start_frontend_paired_metadata_local_v2.ps1 -AuthorizeBMetadataRead`；
查看入口为 `scripts/show_frontend_paired_metadata_status_v2.ps1`（可加 `-Once`）。

没有训练、特征重建、模型推理、新设备入网实验、K、HPC 或新增数据读取授权。
本次没有产生新科学结论，名单资格仍未得到验证，能力继承仍未证明。
只有名单资格完成后才推进配对训练执行器及分别授权的 A 与 A+B 实验。
