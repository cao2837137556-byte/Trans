# UDP 进度 I/O 瓶颈诊断与候选补丁

结果：181645 的真实 UDP 工作进程在 12 秒、24 次只读采样中，全部阻塞于共享盘进度文件的 fsync；独立候选补丁通过 8 项检查和 Linux 小文件对照，尚未安装到实验 worker。
影响：实时进度强制持久化会阻塞逐包重放；可仅调整进度文件的持久化方式，保留科学输入、逐包顺序、状态演化、样本、模型、阈值与所有验收门。
下一步：由小anti复核候选补丁的路径范围与证据；之后在新版本中集成、重新封存并做真实 Linux 验收。本次作业不热改、不延时、不重投。

## 实测证据

- `LIVE_WORKER_PROC_DIAGNOSTIC.json`：工作进程 PID 1319780，24/24 样本 `osc_io_fsync_end`，系统调用 74，文件是 `outputs/gate_181645/replay_status/.REPLAY_HEARTBEAT.json.<uuid>.tmp`。12 秒内 CPU ticks 与 I/O 计数均未增长。
- `LIVE_PROC_DIAGNOSTIC.json` 是 supervisor，不是计算 worker：19/24 样本正常睡眠，5/24 运行。该窗口 supervisor CPU 消耗 2.07 秒，约占一个核心的 17%；重复进程树监测值得后续单独计时，目前不改资源守卫。
- `PROGRESS_AT_DIAGNOSIS.json`：UDP 777,593 / 3,215,732 帧；角色耗时 3,215.61 秒，状态 append 913.71 秒，解码 64.31 秒，剩余 2,237.59 秒未单独归因。**不能把这部分全部记为 fsync 时间**。
- UDP 的大量不同 namespace 导致约 68 万次状态溢写，确有成本。但解码仅约 2%，且实际抓到的长时间停顿发生在共享盘进度文件，不是节点本地 SQLite。
- `LINUX_TELEMETRY_BENCHMARK.json`：在同一作业分配、同一共享文件系统进行 4 次 1203 字节写入；原写法 0.1815 / 0.2614 秒，候选 0.00128 / 0.00112 秒，文件 SHA 全相同。短测未复现 12 秒尾延迟；**不可据此声称整场实验提速相同倍数或一定能在 2 小时内完成**。

## 最小候选改动

`progress_io.py` 仅路由两个精确绝对路径：当前 output 的 `PROGRESS.json` 和 `replay_status/REPLAY_HEARTBEAT.json`。保持 JSON 编码及同目录临时文件原子替换，取消这两处的 file/directory fsync。断电可能丢失最后一条进度显示；这些文件不作为科学复用或 PASS 的权威凭据。

其他路径仍调用原 durable writer，包括 REPLAY_STOP、COMPLETE、REPLAY_COVERAGE、CURRENT_ENGINEERING_ATTEMPT、CANDIDATE、批次、授权及最终验收。没有全局替换 `os.fsync`、checkpoint 或 runtime_control。输入核心、SpillMap、快照生成、选择和模型代码不变；心跳频率也不变。

`INTEGRATION.patch` 是**未应用**的 worker 两处集成差异；`git apply --check` 和编译检查通过。未来在独立新版本中同时放入该 helper 并更新代码封存/执行卡；不可在已冻结 v2 目录直接应用，也不可把本候选当作已通过科学数值对齐或完整 Linux gate。

## 验证与预算

8 项测试覆盖：原写法字节相等、两条进度路径无 fsync、权威回执保留 fsync、同名异目录不误路由、异常后恢复原 writer、非有限数值拒绝、替换失败保留旧文件并清理本次临时文件、真实 frozen replay.status 回调与计数一致。

两个 12 秒只读 `/proc` 采样和一个最多 1 分钟的小文件对照，均使用 `srun --jobid=181645 --overlap --exact -n 1 -c 1` 在已有分配内执行；没有 sbatch、新实验作业、模型调用、原包再处理或预算延长。诊断文件保存在独立目录，未修改工作进程、封存源码或数值状态。只通过用户已连接的 SSH 隧道取回小型回执。

小anti复核重点：两条路径是否确属非权威进度；STOP/PASS 发布次序与持久化是否保留；异常恢复与模块作用域是否安全；新版本绑定是否覆盖 helper；后续完整 Linux 同值/恢复验证是否真实完成。
