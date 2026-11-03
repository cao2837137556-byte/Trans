# Q/R 迁移实现与合成验收

2026-09-12。状态：IMPLEMENTATION_COMPLETE_SYNTHETIC_PASS。用户在确认“下一步是实现与合成验证”后授权“授权动手下一步”；本次完成该范围，没有启动真实 P、T、E。

**42/42 合成测试通过，生成数据 P→T→E 全流程通过，实现包已封存；实现入口检查通过。科学目标仍未达标，本轮没有新性能结果。**

## 冻结身份与保护

- 工作区：`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`。
- 分支 `codex/exp-mainline`，HEAD `4b28747b09480471e2bac1beb3a9badf27280efb`。
- 方案 SHA256：`605c10098b65f19b6e902b90fc1673c3f0509d2ee99f3558661afe74692a893b`。
- 配方 SHA256：`540c2e4d71ce9621965f981d47b4e5f68eb5f148cfd13b4c5d59fa4b2b725702`。
- 实现包：`runs/frontend_task_aligned_transfer_implementation_v1_20260912/`。
- 实现包 SHA256SUMS 的 SHA256：`1b6a30f52137ca8ca6b9451d8d2facdb0778bcd1a2510df346fc8c85fdfde00e`。
- 44 项代码/文档/启动脚本身份纳入实现配置；依赖、Python/runtime 和八个无关修改按既有配置校验。

冻结方案与原始代码没有原地修改。没有切换分支、新建 worktree、重置、提交、下载、HPC 或历史实验重跑。八个 `issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12` 无关修改保持原 hash。工作区原有其他文件保持。

## 已完成的实现

| 部分 | 新文件（相对 repo/ood） | 行为 |
|---|---|---|
| 数值目标 | `issue27frontend_aligned_model_v1.py` | 复用原 Student、label、guard、AdamW；新增真实 qS 的对称有限 margin 目标，以及先投影再 sum128 Huber/127 的 R 项。D 全零且不消费 RNG；部署保留原 qS。 |
| 派生 P | `issue27frontend_aligned_prepare_v1.py` | 只复用封存 TRAIN 教师与 guard；核对 row/UID/context/label，派生 float64 margin/尺度及一次 float32 转换。任一硬判边界不一致 STOP，不丢行。无教师/学生 forward 或优化器。 |
| 双臂 T | `issue27frontend_aligned_train_v1.py` | Q/R 分别从同一 A 独立开始；固定数据、20×197 更新、301460 目标呈现/臂，合计7880更新；记录损失、任务误差、裁剪和覆盖。两臂全部终点封存后才可 E。 |
| 终点 E | `issue27frontend_aligned_evaluate_v1.py` | 仅新 Q/R 前向，合计560632目标；复用 A/AB/P2/C0/C1/C2 分数，保留固定点、低FPR、逐族逐池、A/B、ID和翻转。TRAIN原前向同时记录迁移拟合；无额外学生前向或分任务梯度探针。 |
| 验证/监督 | `issue27frontend_aligned_verify_v1.py`、`issue27frontend_aligned_control_v1.py`、`issue27frontend_aligned_support_v1.py` | 阶段产品读回复核、Windows 单 worker Job、资源上限、异常停止、零重试。沿用追加式进度；终态显示保留最后完成量。 |
| 验收/封存 | `issue27frontend_aligned_fixture_v1.py`、`issue27frontend_aligned_tests_v1.py`、`issue27frontend_aligned_build_v1.py` | 生成数据、禁止真实 run 文件访问的审计钩子、数值与监督验收、依赖闭包和实现封存。 |

未来 P 的真实输入仍为9379条训练教师；此时真实 s_q 尚未派生。prepare 的读回验证会确定性重算并比对派生值，T/E 同样核对封存值一致性；不能用重算改变尺度或目标。R不对剩余能量再次归一化。

缓存 guard 中原本只含简化字段；实现通过精确 TRAIN UID/上下文连接补回已有攻击族信息，使终点 guard 审计保留族明细，不改变配对、margin或目标。

## 合成验证与审查范围

最终42项验收用时约22.41秒；详细清单、执行结果和当时源代码hash见实现包 `acceptance.json`。生成数据经过实际 prepare/train/evaluate 与 stage verifier，模型与缓存都在独立临时测试目录产生。数值测试不允许访问 `runs/mainline_docs` 以外的真实 run 文件，连真实教师索引 JSON 也会阻止。

已覆盖：

- 原前向逐 bit 一致、早期目标因果性、零初始化 D 不消耗 RNG、部署参数口径。
- Q 教师项为零时与原 C1 两步更新后的模型状态完全相同；label/guard/optimizer 直接复用原函数。
- Q 梯度作用于实际 head/encoder；过冲约束与 BCE 反向属预期；R 首步 encoder 梯度为零、之后非零、没有直接 head 梯度。
- 不均衡类别/上下文的权重、跨桶总量、先投影后 Huber、sum128/127及共同加性偏移的数值容差不变性。
- 白名单、B/错误 A 排除范围、row连接、有限性、阈值转换边界 STOP、float32字节一致、派生文件损坏拒绝。
- 生成 P 不调用任何 module forward 或 AdamW；T读取范围只为 TRAIN 前缀。两臂初始化/更新/呈现一致，终点文件和评价往返一致。
- TPR的整组ties、整数误报边界、一个全局阈值、AUROC、正负翻转不相消。
- 缺失或旧授权不能启动新尝试，已存在尝试不得重启，PTE链首个失败即停止。
- Windows真实Job监督下的生成数据进度、完成/失败封存、并发读者、半截日志处理、终态完成量和失败原因显示。

首次合成验收中，测试夹具的监控父进程过早 import 了 torch，触发既有512MiB父进程内存限制；改为按需导入，保留原资源限制。随后补上完成显示的回归覆盖并全套通过。这是实现验收中的测试夹具修正，未运行或重试真实实验、未做资源试验，也没有修改科学配方。

启动与状态 PowerShell 脚本通过语法检查。本轮自行核对新旧数值代码、缓存接口、预算与继承字段；没有另行调用子代理，不将上轮方案的独立审查冒充本轮独立实现审查。

## 当前可用入口与真实执行边界

实现入口已实际返回 `IMPLEMENTATION_READY_NO_REAL_EXECUTION`。状态脚本实际返回：

```json
[{"stage":"P","status":"NOT_STARTED"},{"stage":"T","status":"NOT_STARTED"},{"stage":"E","status":"NOT_STARTED"}]
```

人用状态入口：`scripts/show_frontend_task_aligned_transfer_v1.ps1`。未来各阶段运行后会生成对应 `status.html`、`status.md`、追加式 `progress.jsonl`、`supervisor_terminal.json` 和 `SHA256SUMS`；完成必须同时有终态与封存核验，启动PID不等于完成。无需LLM定时轮询。

启动入口：`scripts/start_frontend_task_aligned_transfer_v1.ps1`；默认阶段链PTE，但需要相应明确授权开关。此报告不发出启动命令、不生成真实执行授权。未来可以一次授权“P派生预检通过后直接执行Q/R双臂T，再做一次E；异常停止且零重试”，收到该范围后正常阶段间无需再问。

下一步已经是新的真实 P→T→E 执行范围，不再需要重新设计或重复当前合成验收。P只准备合法训练目标，P通过后T才是训练，T封存后E才有新检测效果可看。若P发现真实身份/语义问题必须STOP并说明，不能擅改门槛继续。

solved: Q/R实现与42项合成验收完成，实现封存、入口核验和状态查看通过。
changed_mainline: yes（从设计就绪进入实现就绪，真实执行尚未启动）。
active_blocker: 新真实P/T/E尚未授权；联合攻击/OOD能力仍待真实终点评价。
frozen: Q/R方案和配方、原实验/FAIL、旧代码、当前实现包及验收证据。
superseded: “Q/R尚未实现”的状态；未改变科学结论。
next_action: 在明确真实P/T/E授权后按既定链执行；异常停止、零重试，不自动重训或扩数据。
