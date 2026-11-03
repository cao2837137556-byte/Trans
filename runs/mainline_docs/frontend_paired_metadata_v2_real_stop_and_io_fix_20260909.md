# V2 真实元数据尝试中止与 V3 文件写入修复

日期：2026-09-09。用户明确授权一次 V2 真实 B 元数据读取与名单封存。
执行前分支 codex/exp-mainline、HEAD 4b28747b09480471e2bac1beb3a9badf27280efb，
V2 封存/就绪核验通过，目标目录不存在。启动 controller PID 25232。

## 真实结果

终态 `INPUT_OR_EXECUTION_STOP`，CLOSED，监督封存已核验，controller 已退出。
耗时 1.046 秒，聚合峰值上界 142,278,656 字节，worker_count=1、restarts=0。
worker_exit_code=0 表示 worker 成功写出了失败终态，不表示科研或读取成功。

`worker_terminal.json` 的 traceback 定位到原 runner 第 113 行：在
`HASHING_INPUT_IDENTITY` 状态首次强制更新进度时，`os.replace(progress.json.tmp,
progress.json)` 抛出 `PermissionError [WinError 5]`。原始路径的尺寸已 stat，
但尚未调用容器内容 SHA 读取；raw_container_hash_bytes/files、decoder_calls、
project_packets_decoded、B_descriptors、model_forwards、optimizer_steps 均为 0。
没有名单、训练或新能力结果。真实目录 `runs/frontend_paired_metadata_v2_20260909/`
及遗留临时文件均保持原样，具体 seal 与快照见修复证据 v2_snapshot.json。

这次错误发生在写入者的原子替换，区别于 V1 监测器两次 stat 之间的文件消失。
Windows 中不允许删除共享的打开句柄可造成此错误；生成文件实验已复现这一
故障机制。实际尝试中哪个进程占用了文件没有被记录，不能断言是状态读取、
监测器或杀毒软件。现有证据不支持任何流量或模型能力失败结论。

## V3 修复与验证

V1/V2 源码、实现包、真实失败目录及此前冻结配方全部保留。新增 V3 IO helper、
runner/controller 副本、启动/状态脚本，使用局部 namespace 接入新写入器，
不修改共享 V1 模块全局状态。runner 除注入写入器外与 V1 完全相同。

JSON 仍先写临时文件并 flush/fsync，仅在 os.replace 遇到 Windows 错误
5/32/33 时，每 25 ms 再尝试替换一次，最多 21 次调用、20 次等待，累计
请求等待不超过 0.5 秒。持续拒绝仍抛错、停止；非上述错误和写入/fsync
错误立即失败。不会重新生成数据、读取原始容器、启动 decoder 或重启 worker。
这是有界文件写入恢复，实验重试仍为零；资源限额与科学规则不变。

本次 23/23 生成检查通过，含真实 Windows 文件句柄占用的旧问题复现、短暂
占用释放后成功、持续占用保留旧文件并停止、错误分类/次数上限、只写一次、
runner Progress 接入、V1 namespace 隔离，以及绑定 V3 的 controller 测试
（授权拒绝、禁止重启、原子写入、超时/输出限制、子进程清理和终态封存）。
两个 V3 PowerShell 脚本解析通过。没有重跑历史科学实验或真实资源试验。
原 V1 45 项和 V2 22 项仅作保留历史证据，不声称全部重新在 V3 执行。

修复证据：`runs/frontend_paired_metadata_io_fix_v3_20260909/`。
可运行封存包：`runs/frontend_paired_metadata_implementation_v3_20260909/`。
只读就绪、runtime pins、旧 seal、无关修改完整性核验见 final_verification.json。
V3 真实命名空间保持不存在；合成成功不能保证所有外部文件占用都已消除。

## 当前边界

V2 一次真实授权已经消耗，没有自动重试。下一次真实读取须另行明确授权 V3，
仍是 6,737 B 目标 / 22 成员 / 最多 8,207,642 包，3,600 秒、聚合 8 GiB、
输出 64 MiB、零实验重试，包含不透明容器身份校验。没有训练、K、HPC 或
新设备入网实验授权。真实名单资格未完成，攻击能力继承仍未证明。

启动：`scripts/start_frontend_paired_metadata_local_v3.ps1 -AuthorizeBMetadataRead`。
查看：`scripts/show_frontend_paired_metadata_status_v3.ps1`（可加 `-Once`）。
