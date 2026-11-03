# monitor/runtime 最终独立复核

2026-10-27。结论：**本地技术审阅与39项相关合成/回归测试通过；真实HPC运行仍待。** 未访问远端、启动HTTP服务、加载真实依赖/模型、编码、训练或评价。未改 chain/common/build_assets、旧封存包或任何科学公式。

## 审阅与修复

- `hpc/status_bridge.py` 只读固定job目录、根Slurm记录和原子JSON；失败的batch/extern行不冒充根job。launch失败或调度器失败优先于child COMPLETE；调度器完成但缺chain完成回执显示异常。child先COMPLETE而Slurm尚未完成时显示 `FINALIZING`，普通同步程序继续等外层终态，防止缓存过早冻结而漏掉后续异常。终态不依赖继续心跳。
- bridge附带worker原有 `status.json` 的实际子阶段与计数，显示原104、tokenize/补编码或源CAL臂，不从stage名称推测进度。只读取，不执行HPC控制命令。
- 调度器 `PENDING/CONFIGURING` 且尚无child回执时明确 `QUEUED`；Slurm `RUNNING` 但尚无child回执时为 `STARTING`，显示等待实验启动回执，不宣称科学任务正常运行。连接失效或快照过期仍覆盖为 `UNKNOWN`。
- `hpc/status_sync.py` 保持24小时普通程序生命周期、固定job/token/schema及长度校验。仅接受唯一已存在school-hpc SSH PID与本地listener配对，候选端口仍须同一远端身份验证后才能持久化；不新建SSH。拒绝schema/job/调度绑定/自动重试策略/时区时间异常。权限不足不能枚举listener时保留未知，不猜端口。
- `hpc/progress_server.py` 区分未提交、首快照尚未取得、运行、等待调度终态、连接未知、异常和完成。失联不伪装运行，首快照缺失不误称未提交；显示中文阶段、真实计数和科研状态。优先依 `evaluation_scope`、缺字段时依 `stages` 动态说明范围：当前仅环境检查/补编码/密源CAL，正式目标矩阵未运行且第三池证据缺失，前缀COMPLETE不称全实验完成；未来FULL_MATRIX新包可显示完整范围。页面只读本地cache；本轮未启动服务。
- `src/prepare_runtime.py` 仅把钉SHA的wheel离线安装到全新作业私有target，六版本配置不变；pip日志用受控文件上下文关闭。新解释器预置overlay后实际导入，不能替换共享NumPy。
- `src/runtime_probe.py` 校验NumPy实际模块和分发路径、Torch–NumPy转换及原translator导入的实际netFound四类。记录Torch构建/CPU能力和NumPy BLAS配置，仍明确104尚未验、未声称原硬件身份。
- `src/supervisor.py` 启动前先检查取消和剩余磁盘，禁止重叠输出目录；运行中保留全树RSS/wall/输出守卫。清理失败也写持久EXCEPTION_STOP和 `cleanup_confirmed=false`，不能异常跳出而留下假RUNNING。正常科学FAIL继续按技术完成处理。
- `hpc/run_dense.slurm` 静态核查：amd、4 CPU、16GiB、12小时、no-requeue、SIGTERM/EXIT保存失败、原环境SHA、包SHA和合成测试先行。正式入口固定为runtime→encode→source_cal前缀；第三池证据缺失时没有偷偷启动完整矩阵。本轮未执行bash/Slurm脚本。

`ENCODER_PORTABILITY_AUDIT` 中旧“整体wall求和阻塞”已更新为修复完成：各阶段共享≤43,200秒总cap，取剩余预算，不扩原上限。

## 本地验证

| 测试 | 通过 | 范围 |
| --- | ---: | --- |
| test_runtime_monitor.py | 22/22 | 排队/启动回执等待/失联、前缀/完整矩阵范围、外层终态与完成竞态、真实子stage、首快照、身份/时间、SSH listener归属、私有wheel接线/篡改、启动前取消/磁盘、清理异常回执 |
| test_progress.py | 5/5 | 旧完成记录失联保留、旧RUNNING过期为未知、调度失败可见、身份不匹配拒绝 |
| test_chain.py | 12/12 | 包/授权/路径、真实微型child、科学FAIL、停止/退出、12h总预算、matrix缺证据及授权前缀接线 |

环境为本地Windows/Python3.10；上述结果不代替真实Linux3.11/NumPy2.0.1 overlay依赖和数值验收。原104逐字节门、生产补编码、源CAL数值门、资源实测均未运行；任何真实技术异常继续停链留现场、不自动重跑。完整矩阵的第三池资产阻塞属于独立科研执行前置，未被本审阅豁免。
