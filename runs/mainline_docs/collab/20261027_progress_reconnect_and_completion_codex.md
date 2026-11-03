# 进度连接恢复与 179460 完成回执

用户请求修复进度页与超算的连接。已修复并在页面核验终态；本次未重启、提交或控制实验。

## 断联原因与修复

VSCode 重连后，既有 `school-hpc` SSH 的本地 SOCKS 端口从 55895 变为 61873，原同步器仍使用旧端口，连续失败 12 次后退出。断联发生在本地传输层，不能据此判断远端作业失败。

通过新端口读取原只读桥接端口 18776，沿用原 token 与固定作业 179460，使用原 bundle 身份和终态校验后，仅更新私密配置的 `socks_port`。已恢复完整状态缓存和只读结果回执。当前页面：<http://127.0.0.1:18769/>。

未封存的本地监控适配器现支持：临时故障有界退避；最多每 30 秒识别唯一既有 SSH 通道；远端身份校验通过后才保存端口；身份、认证和 HTTP 4xx 错误停止；24 小时生命周期不延长。Windows 进程查询隐藏运行，不创建 SSH 会话或周期性弹窗。终态离线保留。19/19 离线测试通过，生产缓存 CLI 返回 `OK / terminal=true` 后立即退出；本次没有为已完成作业启动常驻同步。

实现与测试见 `../../source_controls_base_ctx_repair_v2_20261026/monitoring/repair_status_sync.py`、`test_repair_transport.py` 及 `TRANSPORT_RECOVERY.md`。

## 当前真实终态

- 作业 179460 / node185：Slurm `COMPLETED`，ExitCode `0:0`，耗时 `02:07:46`。
- supervisor `COMPLETE`，`returncode=0`，`worker_alive=false`，`cleanup_confirmed=true`。
- 完成时间：2026-10-26 北京时间 22:08:55；12/12 端点完成（BASE 六个复用，CTX 六个新增），MI15 169/169 captures 完成，三阶段隔离通过。
- 最后成功只读同步：2026-10-26T15:54:40.886838Z；远端观测时间 15:54:39.122578Z。
- 技术完成与科学结果分开：`RESULT.status=COMPLETE`，`scientific_status=FAIL`。源侧 G0 均值 FPR 10.197337%→10.820529%，G1 17.612028%→12.427822%；不能当 A/B 指标或入网模块新结果。完整结果拉回与分析另记。
- 原 179422 资源异常及修复验收历史保持；本次恢复连接没有新增训练、MI15、E3 或 A/B 评价，没有自动科研重试。

## 证据

- [当前终态缓存](../../source_controls_base_ctx_repair_v2_20261026/remote_progress/job_179460/sync.json)
- [原远端状态 bundle](../../source_controls_base_ctx_repair_v2_20261026/remote_progress/job_179460/remote_bundle.json)
- [只读结果回执](../../source_controls_base_ctx_repair_v2_20261026/REMOTE_RESTART_RECEIPT.json)
- [新通道恢复原始快照](../../source_controls_base_ctx_repair_v2_20261026/TRANSPORT_RECONNECT_REMOTE_SNAPSHOT.json)
- [完成页面截图](../../source_controls_base_ctx_deployment_20261026/RECONNECTED_COMPLETE_179460.png)

本回执只确认终态、连接恢复及已下载汇总；独立逐分数科学重算不由本回执冒充完成。无 AI 持续轮询。
