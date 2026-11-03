# C4：追加预算已授权，恢复流程已启动

用户于 2026-11-02 回复“追加啊”，批准上一轮明确请求的新增 18000 秒（5 小时）及完整 DEV→条件单次 A/B 验收。原 180670 失败现场保留，不改写旧结果。

**实际提交与启动已确认：作业 180772，RUNNING。** 远端预检 33.270806 秒 PASS，134/134 工程检查通过，`sbatch` 返回 180772 / exit 0；北京时间 12:54:50 开始计算。启动核查时，三设备完整编码已复用，Netatmo 完整准备产物已校验复用，正在启动冻结编码 worker，峰值 RSS 约 2.17 GiB，尚无新距离对或科学成绩。右侧页正常，普通程序继续；本轮到此结束，不持续 AI 监测。

## 当前执行入口

- 科学包：`runs/history_sample_coverage_c4_batch_resume_v1_20261102`
- 执行卡 SHA256：`a37cc58027e554980a3962db99fb3fbc79cc904f91229623f1efc2b501b68614`
- 部署：`runs/history_sample_coverage_c4_budget_deployment_20261102`
- 普通执行程序 PID：21308。已启动代码上传→安装→远端预检→唯一一次提交→取回→本地 DEV/条件 A/B→独立验收的自动流程。
- 实际作业号由新部署 `SUBMIT_RECEIPT.json` 确认是 180772；启动状态及进度页核查见 `STARTUP_VERIFICATION.json`。
- 用户右侧页仍为 `http://127.0.0.1:18789/`，已显示新阶段和预算说明；不持续 AI 监测。

## 恢复与资源账

原三设备 20480 条完整编码继续校验复用。Netatmo 直接复用 180670 已保存的 12288 份快照和对应候选/角色/选点回执，跳过原包扫描和连续上下文重放。源文件只读校验后白名单复用，旧 `encoded/` 中只有日志的 4658 条不继承；它们没有实际 E3 数组，需要重新计算 Netatmo 12288 条。

新 E3 采用每批真实数组、输入/模型/UID pin、SHA 回执、文件和目录同步；完成进度只在批次持久化之后增长。完整 E3 与 DEV 头分数分开原子保存。旧现场与新运行目录分开，单次尝试失败仍停止，不自动重投。

旧累计保守扣费 28861 秒保留，新增额度 18000 秒，新累计账上限 46861 秒。远端实际开始之后，取回、本地评价和独立核验共用同一 18000 秒截止，排队不计入计算预算。

旧逻辑 forward 已扣 25154，本次最多新增 12288，累计 charged 上限 37442；其中包括旧丢失计算，不能当成独立样本数。唯一候选编码人口为 32768。三设备完整编码复用不会重复计为本次 forward。4 CPU / 8 GiB / 20 GiB 输出、距离对上限 10 亿保持。

## 预检与边界

本地科学包集成检查 103/103 通过（20.504 秒）；部署工程 31/31 通过（0.703 秒），远端注册合计 134 项。部署检查包含文件归档边界、无重复提交、提交状态不确定停机、累计截止、断点取回、预算/失败后的验收禁止。

远端使用固定 Python 3.11.11 / NumPy 2.0.1 / Torch 2.5.1，按阶段持久化预检状态；同时核冻结环境、源码、246 个真实包头、旧失败预算、完整 PREPARED 小回执及三设备完整编码。正式 worker 再核完整 SHA、角色/UID/物理源/q14 及确定性选点。新增门控、目标数据或模型调参均为 0。

科学方案继续固定选择器、salt、容量、模型、阈值、λ=.25 和 C2 SYN 守卫。必须先通过 HIST_DEV，再评价一次 A/B；A/B 仍标 `CONSUMED_DEVELOPMENT_ONLY`。工程检查通过不代表科学通过，无本轮新成绩。

## 本地存储

本次只传约 4.84 MB 代码包，原始数据传输 0 字节。大候选 SQLite、原包、时序副本留在超算；只取回完整验收所需的编码、真实批次、回执及日志，硬上限 512 MiB，本地取回前至少检查 1 GiB 可用空间。不会把原始包和 SQLite 取回 D 盘。本轮没有删除或移动既有本地科学输入。

## 回执

- 科学包：`EXECUTION_AUTHORIZATION.json`、`BUDGET_SEAL_RECEIPT.json`、`IMPLEMENTATION_CHECK.json`。
- 新部署：`DEPLOYMENT_ENGINEERING_RECEIPT.json`、`DELIVERY_MANIFEST.json`、`INSTALL_RECEIPT.json`、`PREFLIGHT_PROGRESS.json`。
- 后续作业：`SUBMIT_RECEIPT.json`、`STATE_RECEIPT.json`；流程异常：`PIPELINE_ERROR.json`。
- 最终仅以科学包 `FINAL_ACCEPTANCE.json`、`outputs/evaluation/RESULT.json`、`outputs/verification/STAGE_RECEIPT.json` 及部署 `GLOBAL_BUDGET_RECEIPT.json` 为准。

预计补完约 2.5～3.5 小时、不含排队；5 小时为硬上限，形状较大的批次和共享超算吞吐可能延长耗时，不保证在预计区间结束。
