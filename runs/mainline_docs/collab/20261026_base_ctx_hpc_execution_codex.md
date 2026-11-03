# BASE/CTX 源侧对照正式运行回执：179422

2026-10-26 16:47（北京时间）初始核验快照。**用户已授权，已部署并实际进入生产源侧训练；当前仍在跑且正常。** 后续状态以普通进度页与同作业终态回执为准，本文件不是持续心跳。

## 授权与执行范围

用户明确回复「允许，我还是需要清晰看到进度」。本次执行封存的 [BASE/CTX 实验包](../../source_controls_base_ctx_v1_20261026/README.md)，沿用 [交付与预算](20261026_base_ctx_experiment_package_codex.md) 的科学合同：先 BASE6 与 S0，再按登记分支执行因果 MI15 和 CTX6，最多 12 端点。COV/CNT 暂缓；无新 E3、无 A/B 评价、无入网 λ 搜索。此前文档中的“待授权／远端操作0／正式训练0”是本次授权前的历史状态。

## 实际部署与提交

- 仅传输 564,973 字节代码归档，原已验收的 5 个大源文件与 169 个 raw capture 直接复用。
- 归档 SHA256：`4f5e298a9b5a98d2b7e1590db636ac725a07046801076db8318600631d2a68f3`。
- Manifest SHA256：`71f03266a506c1068b2ede45f6dd978960d01f66e0037c35ea01e95ef5d6500c`。
- 远端 43/43 封存文件 SHA 验证通过；科学文件与封存归档未改。
- 远端根：`/public/home/jiangxinwei.zr/work/paper04/runs/source_controls_base_ctx_v1_20261026`。
- 提交一次 `sbatch --export=NONE hpc/run_source_controls.slurm`，成功返回 `Submitted batch job 179422`，exit0。
- 单次提交锁在 sbatch 前落盘，超时或不明结果禁止自动重提。代码部署接口仅允许固定归档、固定脚本的一次提交和固定作业监控配置，loopback 18771，1小时后自行结束。
- [部署回执](../../source_controls_base_ctx_deployment_20261026/DEPLOYMENT.json)、[提交回执](../../source_controls_base_ctx_deployment_20261026/SUBMISSION.json)、[离线部署审阅](../../source_controls_base_ctx_deployment_20261026/DEPLOYMENT_AUDIT.md)。部署保护测试7/7通过。

## 初始健康证据

Slurm allocation 为 **179422 / RUNNING / node185**。生产 supervisor 为 RUNNING，`worker_alive=true`，worker PID110399。输入与身份核查阶段 COMPLETE；当前 `S0_BASE6` / `G0_BASE_27` 正在训练及其分批评分流程。未产生最终科学指标。

生产入口严格顺序执行环境、SHA、同HPC单元测试及人工小数据集成门；只有这些命令成功退出才启动生产 supervisor。本次已进入生产，故这些训练前门均已通过。运行证据见 [首次展示快照](../../source_controls_base_ctx_deployment_20261026/INITIAL_STATUS_VIEW.json)，原始证据持续由封存同步程序保存到 `runs/source_controls_base_ctx_v1_20261026/remote_progress/job_179422/remote_bundle.json`。初始采样树RSS峰值 4,421,435,392 字节（约4.12GiB），新增输出约10.5MiB，无异常终态。

资源不变：amd / 4 CPU线程 / 无GPU，Slurm16GiB、6小时；内部5小时50分钟、采样RSS8GiB、新输出2GiB、可用空间4GiB下限。整体2–4小时仍是计划估计，未据此伪造剩余时间；个人磁盘配额仍未独立证明。

## 用户可见进度

主进度页：**<http://127.0.0.1:18769/>**，已在应用浏览器打开并保留。本地服务和同步程序用 `pythonw.exe` 隐藏启动，无弹出系统终端。旧18765与18766历史页保留，18766新增本轮进度入口。

- 普通同步器每5秒读取固定作业，页面每3秒读取本地快照；最长24小时。没有AI轮询或AI自动化。
- 页面明确区分排队、资源分配、训练前检查、BASE6、S0、MI15、CTX6、完成、异常停止和未知。
- 展示当前端点、epoch/优化更新或本次评分行数、采样内存及输出；不把评分局部计数当整体进度，不编造总体耗时百分比。
- 封存 runner 的原始端点计数在进入G1时按折重置；封存包外的只读展示按登记固定顺序与阶段回执计算已完成前驱端点，未改变科学结果。
- 同步错误会停止同步并显示远端未知，保留最后证据；远端作业不会因此被取消或重跑。明确终态无需后续心跳。调度器显示COMPLETED但无exit回执仍为未知。
- 页面展示测试13/13及JS语法检查通过，实际浏览器显示与API一致。服务PID与绑定见 [进程回执](../../source_controls_base_ctx_deployment_20261026/LOCAL_PROCESSES.json)。

运行策略不变：科学FAIL继续登记配对；身份、数据、数值、I/O或资源异常停止并保留，不自动重跑。S0不足3%的分支是正常 NOT_INFORMATIVE，不得解释为CTX无效。已启动作业交由普通程序继续，当前不再持续调用AI查询。
