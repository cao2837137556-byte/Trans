# 任务知识迁移：T V1 工程停止与 V2 修复验收

日期：2026-09-11。当前状态：P COMPLETE；T V1 STOP；E 未启动；V2 实现已封存，等待一次新的真实 T→E 授权。

## 本次真实执行结果

用户“动手下一步授权”已用于一次 P→T→E。P 在 6.109 秒完成并封存 9,379×128 float32 教师贡献，身份、缺失语义及数值检查通过。P 不需要重做。

T V1 在 39.313 秒停止：C0 第 1 轮完成 174 次优化器更新、348 次 student forward；没有最终候选 checkpoint，E 评估目标数为 0，重试次数为 0。控制器 37280 和训练进程 41868 均已退出。最后一份进度快照落后于实际完成量；174 以 access.json 和训练日志为准。

异常链为 `train → fit → Budget.check → atomic_json → os.replace(progress.json.tmp, progress.json)`，Windows 返回 `PermissionError: [WinError 5]`。这属于我们实现的进度读写缺陷，不是模型能力失败，也没有数值发散的证据。

## 原因与修复

生成数据的并发夹具已复现相同 WinError 5：普通读句柄持有目标文件时，Windows 会拒绝替换。无法追认真实失败瞬间具体是哪一个读取者持锁；但该竞态机制可复现。

V2 将机器进度改为追加完整行的 `progress.jsonl`，不再反复替换被读取的进度文件。`progress.json` 仅为不变的兼容指针。读取器取最后一条完整记录，忽略尚未写完的尾行，对完整但损坏的 JSON 报错。状态 Markdown/HTML 直接写入，机器日志为权威进度；人类视图短暂未写完时可刷新。没有增加 I/O 重试或训练重试。

V2 是独立运行覆盖层，原 V1 模型、损失、训练和评估数值代码保持原字节。数据、分母、seed、学习率、20 轮预算、末轮端点与判定阈值均不变。三个训练臂仍从封存 A 独立初始化：C0 普通 A+B 训练，C1 增加 A 排序保护，C2 再增加 P2 贡献蒸馏。P2 投影仅用于训练。

## 验收与封存身份

57/57 生成数据测试通过：原有 43 项及新增 14 项回归，包括原错误复现、持有多个读句柄时追加、250 次并发更新、完整/不完整尾行处理、人类视图并发读取，以及隔离 Windows Job 监督器写出 500 次进度后完成封存。验收过程真实模型 forward、教师计算、优化器更新均为 0。两份 PowerShell 脚本语法通过；封存后的 `check-implementation` 通过，V2 T/E 状态均为 NOT_STARTED。

| 产物 | SHA256 |
|---|---|
| V1 P SHA256SUMS | `80019634c8b158e901678f55b369476fc488104b4bf1177193750432b83d567d` |
| V1 T STOP SHA256SUMS | `e54daa468f3bc24a8186969f6cd373e50cf20067e085d146074f3c3431606195` |
| V2 实现 SHA256SUMS | `5490d9de933ffebe2d398501f1b3d64c61c915f91beea19d7777c1fda92bd895` |
| V2 config.json | `990543728e89065c9dca4f9a64cd24b11295840eb627e52c9e415a9068bc1154` |
| V2 acceptance.json | `91b2f047140ab10ed9ca11000d375aa3de3e12d4d9e7754253a6de6c125c1289` |

V2 包：`runs/frontend_task_knowledge_transfer_implementation_v2_20260911/`，固定 47 项代码、依赖、脚本和协议身份。分支仍为 `codex/exp-mainline`，HEAD 仍为 `4b28747b09480471e2bac1beb3a9badf27280efb`；8 个无关受跟踪修改的 SHA 均未改变。

## 下一次执行边界与入口

修复已完成，不需要再走一轮实现授权。建议一次明确授权：复用成功 P，在独立 V2 目录从固定 A 开始三臂 T，三臂最终端点全部封存后自动 E；异常停止、零自动重试。不得把旧 STOP 静默恢复为继续运行。当前尚未取得这次新的真实执行授权。

授权后在主工作目录用 PowerShell 执行：

```powershell
./scripts/start_frontend_task_knowledge_transfer_v2.ps1 -Stage TE -AuthorizeNewTrainingAttempt -AuthorizeEndpointEvaluation
```

查看状态，无需语言模型持续轮询：

```powershell
./scripts/show_frontend_task_knowledge_transfer_v2.ps1
```

新输出为 `runs/frontend_task_knowledge_transfer_t_v2_20260911/` 和 `runs/frontend_task_knowledge_transfer_e_v2_20260911/`，目前两者不存在。运行时各有自动刷新的 status.html、status.md 和 progress.jsonl；结束后以 supervisor_terminal.json 与 SHA256SUMS 为准。E 完成才会产生 result.md/comparison.json。

T 上限 4 小时，E 上限 30 分钟；两者各限 8 GiB 内存及 512 MiB 输出。本地监督器负责监测、停止和封存，无需定时 LLM 任务。不访问未授权数据，不解码原始包，不下载、不上 HPC、不搜索超参。所有结果仍只是开发证据，教师历史暴露限制与既有科学 FAIL 保留。修复测试 PASS 不等于继承能力 PASS。

solved: 已定位可复现的进度替换竞态并封存修复。
changed_mainline: no（科学方案不变）。
active_blocker: 一次新的真实 T→E 执行授权。
frozen: V1 成功 P、失败 T、原数值代码及科学协议，V2 验收包。
superseded: 启动快照中的 T 正在运行状态；修复草稿中的读取共享删除方案。
next_action: 明确授权后仅执行一次 V2 T→E，复用 P，异常停止且不重试。
