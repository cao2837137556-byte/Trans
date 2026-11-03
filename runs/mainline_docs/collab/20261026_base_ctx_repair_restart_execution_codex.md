# BASE/CTX 修复后的正式续跑启动回执

**最新：用户授权后已提交并启动独立作业 179460 / node185；启动验收正常，进入全量新 MI15，正式实验正在运行。**

北京时间 2026-10-26 20:01:11 左右启动；20:03 启动验收时 Slurm=RUNNING、supervisor=RUNNING、worker_alive=true、无 exit/EXCEPTION_STOP。源输入及身份核查通过，BASE6 严格复用审计再次通过，六端点已复制，复用 289,800 次旧更新、本次 BASE 新增更新 0。S0=INFORMATIVE，当前新提取 MI15，CTX6 尚未开始；后续由同一已授权串行程序自动完成 MI15→CTX6→配对报告。

用户本轮明确授权原话：**“修复完成后，自动重新运行。”** 已记录为独立授权文件并绑定最终 v2 包、179452 技术验收和 BASE6 审计摘要。一次提交获得 `Submitted batch job 179460`，原失败作业 179422 保留，没有盲目重提旧作业。

## 固定身份与范围

- 新远端 attempt：`/public/home/jiangxinwei.zr/work/paper04/runs/source_controls_base_ctx_repair_v2_20261026/runtime/job_179460`。
- v2 manifest：`00177a5b52b2ef5f046aa161f2977006498e3bd5afbfb1a16a59c6b2a0af28e5`；v1 原 43 件及 v2 的 18 件再次全部校验通过。
- 技术验收：179452 / PASS，回执 SHA256 `a4f2eb14f260520110713aee7585ee6ea83270c4571bb82908723959afc1fe7f`；远端原字节 SHA 与授权绑定值一致后才允许提交。
- BASE 审计摘要：`4fb5f4f743cef65fdb63a5d187d023b84ba1b4b4ecf74653f5dbcda9b0b34740`。
- 范围仍为 BASE6 复用 → 全部169 capture重新提取 MI15 → 原 CTX6；失败 MI 部分产物及诊断输出不复用。无新 E3、A/B 评价或入网 λ 搜索。
- Slurm 4 CPU / 16 GiB / 6 小时、单 capture 8 GiB / 600 秒、MI 7,200 秒、全树 12 GiB / 21,000 秒、新增输出 2 GiB及剩余空间 4 GiB保护均已实际传入。科学算法与判据不变。

## 进度与运行方式

实时页继续使用 <http://127.0.0.1:18769/>，已明确绑定新作业179460；旧179422显示为历史异常，诊断及授权卡显示历史记录，不再错误提示“正式未重启”。BASE 凭真实 `reused_from_job` 回执标为复用完成；MI 显示当前 capture，CTX 显示各端点进度，最终完成或失败以终态证据为准。

新增未封存监控适配器显式绑定 **v2/runtime**，避免旧 v1 CLI 固定路径读错作业。新缓存：`runs/source_controls_base_ctx_repair_v2_20261026/remote_progress/job_179460/`。原 v1 和 v2 科学封存文件未改。

远端只读桥端口18776、固定新job，已有 SSH SOCKS55895。普通隐藏 `pythonw.exe` 每5秒同步，页面每3秒读取本地文件；寿命24小时，终态自动结束。临时网络失联只对状态请求作最多12次有界恢复，期间明确 UNKNOWN，不重试科学作业；身份或协议异常不重试。进度服务和同步均无终端弹窗，无 AI 持续轮询。

监控适配器9/9测试、续跑页面38/38测试及JS语法检查通过，实际浏览器已验新作业、阶段、BASE复用和历史失败分离。当前尚无CTX效果结论；启动验收不替代最终科研结果。

## 证据与后续

`runs/source_controls_base_ctx_repair_v2_20261026/` 下：`RESTART_AUTHORIZATION_BINDING.json`、`RESTART_SUBMISSION.json`、`REMOTE_RESTART_RECEIPT.json`、`RESTART_EXECUTION_RECEIPT.json`、`authorizations/`及新 `remote_progress/job_179460/`。本地服务PID记录在部署目录的 `LOCAL_PROCESSES.json`。

普通程序继续完成已授权链即可。新的身份、数据、数值、I/O或资源异常仍停止并保留现场；单纯科学FAIL完成预登记配对。用户无需反复确认已授权的本次续跑，也无需依赖AI轮询查看状态。
