# 超算预检脚本修复与独立验收 r2（2026-10-26）

本轮针对用户反馈的准备页异常，修复已授权技术准备中的错误。不启动正式训练、生产MI15、补编码或A/B评价。

**最终结论：TECHNICAL_READINESS_PASS。** 独立179404/node185于15:30正常完成，Slurm `COMPLETED|0:0`、耗时73秒、最终退出回执0。环境/TShark/CPU数值验算通过；169/169 raw与8/8 core完整SHA一致，NumPy公共构建信息也实际采集成功。模型前向/编码行/优化器更新均0；源文件重传0。见 [最终验收及逐件SHA](../../hpc_readiness_preparation_v1_20261026/repair_v2/TECHNICAL_READINESS_ACCEPTANCE.json)。下方15:30 raw进行中属于此前启动验收快照，不代表仍在运行。

## 已定位根因与旧现场

原技术作业 **179403 / node185** 于15:17:20以exit1停止，持续59秒。TShark/module阶段exit0，Python3.11.11、Torch2.5.1、NumPy1.26.4及其余vendor依赖版本和导入都已通过。CPU矩阵代码之后收集构建信息时，`np.__config__.get_info('blas_opt_info')`抛`AttributeError`；该NumPy构建没有这个接口。属于本轮预检脚本兼容性错误，不能归为模型故障、原始数据损坏或超算硬件失败。

原远端目录 `/public/home/jiangxinwei.zr/work/paper04/runs/hpc_readiness_v1_20261026` 未覆盖。其5个源文件共2,577,743,446 bytes已完成整文件SHA验证；raw/core阶段尚未运行。

原本地回执和日志保存在 [179403归档](../../hpc_readiness_preparation_v1_20261026/repair_v2/original_179403/status.json) 与同目录其他文件。原技术部署包和原SHA属于历史版本，不能再当修复后入口使用。

## 修复与回归验证

`probe_environment.py`改用公共`np.show_config()`捕获构建信息；NumPy与Torch的非关键构建信息采集隔离，失败明确记`UNAVAILABLE`，不影响已通过的核心验算。版本、导入、Python版本和CPU矩阵数值检查仍严格失败即停，未放宽数值容差。

本地12项测试通过，包括无`get_info`但`show_config`可用、构建信息采集失败、空输出，以及数值错误和依赖版本不匹配仍必须FAIL。没有用本地fixture代替目标端真实验收。

修复后探针SHA256：`6810452a858634e2e95557827222415bb297f392b7f5ab53833887a04f95b216`。完整独立输入/脚本绑定见 [r2准备回执](../../hpc_readiness_preparation_v1_20261026/repair_v2/REPAIR_PREPARATION_RECEIPT.json)。

## 独立技术验收

新目录 `/public/home/jiangxinwei.zr/work/paper04/runs/hpc_readiness_v1_20261026_r2`，作业 **179404 / node185**。复用原目录已封存的5个源文件，通过新目录assets符号链接读取，新增源数据上传0；core阶段仍对实际文件完整SHA复验。旧作业未重提、未覆盖、没有自动重试。

当前目标：环境实际导入与数值检查 → 169个源capture完整SHA → 5源文件及checkpoint/raw_map/environment共8项SHA → exit0与Slurm终态。资源仍为amd、4CPU、4GiB、20分钟，内部阶段预算18分钟；没有模型前向、编码行或优化器更新。

本地当前状态见 [status.json](../../hpc_readiness_preparation_v1_20261026/status.json)，本次原始下载结果位于`repair_v2/`。15:30页面验收时依赖/TShark/CPU已COMPLETE，raw进行中（53/169），尚未据此登记整体验收完成。最终状态以 [r2退出回执](../../hpc_readiness_preparation_v1_20261026/repair_v2/preparation_exit.json)、[环境报告](../../hpc_readiness_preparation_v1_20261026/repair_v2/environment.json)、[raw核查](../../hpc_readiness_preparation_v1_20261026/repair_v2/raw_inventory.json)、[core核查](../../hpc_readiness_preparation_v1_20261026/repair_v2/core_validation.json)为准。

## 页面修复

18766页和服务均为r3。当前状态与历史179403失败分别展示；错误取已绑定当前作业的内层原因，旧报告不能覆盖新作业。终态无需持续心跳，运行态120秒过期才提示未知；普通程序30秒同步、浏览器10秒刷新。没有AI轮询或自动重跑。原18765实验页保留。

基础环境验收通过不代替新源trainer/MI15生产提取器/完整矩阵runner、科学口径收敛或训练授权，也不代替原104 E3字节门禁。
