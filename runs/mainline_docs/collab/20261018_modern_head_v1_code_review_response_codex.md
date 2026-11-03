# 现代检测头 v1 代码复核回应与 v1r1 交付回执

日期：2026-10-18。回应 [原复核](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261018_modern_head_v1_code_review.md) 的 P1–P7。七项均已处理，并以新目录、新归档交付；原复核和旧封存包保持原样。

当前状态：`LOCAL_REVISION_PASS_TARGET_VERIFICATION_PENDING`。本轮完成工程修复、合成与交付验证，真实实验仍为 `NOT_STARTED`，没有新增检测性能结论。未连接、上传或提交超算，未做真实 PCAP 解码、E3、训练或目标评分。

## 1. 交付身份

- [新版说明](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/README.md)
- [最终验证回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/validation.json)
- [源码与支持证据清单](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/source_manifest.json)
- [将来运行与回传命令](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/OPERATE_HPC.md)

| 对象 | 身份 |
| --- | --- |
| 新归档 | `modern_head_comparison_v1r1_20261018.tar.gz`，42,368,748 字节 |
| 新归档 SHA256 | `ad2454fa3766d3862d98e90370fb9dc1fa8b5d67afd20123863182123f71d4d3` |
| 包内 SHA256SUMS 的 SHA256 | `c9f526e6e0ac6a991b0070a374bd56b6cc03e8ebb7897ec9674ed94df88fbe13` |
| 新 experiment_contract SHA256 | `729f923fa4613b0edeff45c99ddf6efaf6ac6435c2dd9b4b6b0a16725d7ff93c` |
| 新 resource_plan SHA256 | `a211be78e633db19cddcb21295f67784cc74eb4cee33d2b77383b77657ac900b` |
| 旧 v1 归档 SHA256，已核实保持 | `635d617637d8dbf2de7ce46cdbceda88e24286f36b371db1d71ed5d534c0dfc4` |

原 QUERY_TAIL v2r3、入网 v1r1 归档及科学合同保持。新合同仅修正 P5 的范围说明；训练配方、seed、数字验收规则不变。资源计划仅更新新合同的身份绑定，既有资源预算直接继承。`build_receipt.json` 保留构建时 pending 状态，最终状态以 `validation.json` 为准。

## 2. P1：允许合法自然停止，分开记录请求、回调与实际树数——已修复

位置：[modern_head_train_v1.py:165](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_train_v1.py:165)。原 `counter == rounds` 改为 `0 < callback_iterations <= requested_rounds` 且 `0 < effective_tree_iterations <= callback_iterations`。endpoint 与 training_log 同时保存 `requested_rounds`、`callback_iterations`、`effective_tree_iterations`、`native_stop`，并明确旧 `boosting_rounds` 字段表示请求预算、`updates` 表示回调次数。无有效轮数或非有限损失仍拒绝。

**对原复核的一处事实更正：** 本地 LightGBM 4.6.0 常数特征 fixture 实测为请求 500 / 回调 500 / 实际树轮数 1，原回调相等断言在这个 fixture 上不会失败。因此不把原文“天然无法分裂时回调也会少于 500”写成已复现事实。新版既允许合法的回调不足，也如实报告回调满额但实际少树的情况；`native_stop` 明确定义为保留树轮数少于请求预算，不等同于 Python 循环提前退出。

验证：[NativeStopTests](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/test_modern_head_revision_train_v1.py:20) 的两项真实 LightGBM 合成检查涵盖常数特征保存/加载回放，以及完整 500 请求的独立计数。生产仍请求固定 500 轮，没有 early stopping 或根据目标结果选轮数。日志见第 9 节 L1；回执 `review_findings.P1`。

## 3. P2：P/T/K 与入网完成度解耦——已修复

位置：[modern_head_runner_v1.py:86](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_runner_v1.py:86) 的 `inputs_head`、105 行 `inputs_module`、127 行 `verified_heads`、142 行 `preflight`、309 行 `run`。

| 运行方式 | 输入要求与执行范围 |
| --- | --- |
| `--heads-only` | 只要求完整 QUERY_TAIL 及其父资产；执行 P/T/K，不读取入网目录。完成后写 HEADS_COMPLETE 和独立 head_status，根状态为 HEADS_COMPLETE_MODULES_PENDING。 |
| `--modules-only` | 要求同包已完成并封存的 P/T/K、入网完成回执及六库；只执行预先指定的 M_TabM/M_LightGBM，不训练或重跑 P/T/K。 |
| 默认 full | 保留一次全链能力，开始时仍须具备两类输入。与拆分方式互斥。 |

模块启动验证 config、decision 和 `heads/SHA256SUMS` 身份，并以 `MODULES_STARTED.json` 绑定头封存与 banks manifest。模块状态与产物写在头封存子树之外，失败保留头结果且阻止重复启动。生产提交额外要求 `status/heads/exit_code.txt == 0`，确保头导出和最终收尾完成后才进入模块；导出失败需要单独恢复回执，不能覆盖原失败状态或自动重提。

提交脚本使用按模式区分的日志、状态、job id 和 claim；full 与 heads 共享训练 claim，避免重复训练。分阶段回传分别使用 `modern_heads_pullback.tar.gz`、`modern_modules_pullback.tar.gz`；后续导出保留全部模型、评价及之前的 manifest/SHA，不嵌套前一归档本体。PowerShell 回传增加 `-Phase heads|modules|full`。

验证：[RevisionRunnerTests](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/test_modern_head_revision_runner_v1.py:14) 覆盖缺入网仍可头预检、M/full 仍要求 banks、拆分执行不重训/不改头封存、缺失/篡改头拒绝、重复和失败后重启拒绝；Linux 模拟提交还覆盖收尾竞态与独立状态，导出检查覆盖不嵌套/不覆盖。日志 L3、L4、L7–L9；回执 `review_findings.P2`、`linux_delivery`、`windows_export`。

## 4. P3：复用证据来自实际回放，前置条件完整检查——已修复

位置：[adapter:154](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_query_tail_adapter_v2.py:154)、[runner:167](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_runner_v1.py:167)、[train:221](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_train_v1.py:221)。

adapter 返回三池实际回放证据：每 seed/ensemble 的 score/decision 比较、RECENT 比较、行数与 UID 顺序摘要、shape/dtype、数组与保存文件 SHA。runner 落盘 `heads/reuse_adapter_replay.json`，每个 proof 的布尔值从对应比较结果计算，并绑定该证据 SHA；不再填写固定 True。原 `_verify_saved_pool` 返回值保持，新增可选 recorder。

共享只读 `reuse_mlp_preconditions` 在 P 阶段检查实际 adopt 所需身份、配方、预算、模型、runtime 与回放 proof 后，才可登记 REUSE_VERIFIED。缺复用证据或条件不兼容记录 TRAIN_REQUIRED 与原因；T 阶段只捕获专属 `ReuseIneligible`，在尚未生成采用输出时记 fallback 并训练。封存/模型哈希损坏、非有限权重及其他未分类异常仍硬停，不能通过重训掩盖。

验证：13 项 ReusePreconditionsTests、7 项 ReplayEvidenceTests、runner 中 3 项复用证据/前置条件检查，以及选取的原 adoption/adapter 回归检查。覆盖 signed-zero、dtype、决定、UID 漂移，缺字段/配方/模型形状不兼容与损坏硬停的区别。日志 L1–L3、L5–L6；回执 `review_findings.P3`。原运行通常缺完整 numeric_runtime 指纹，仍按最多九个新终点准备，未宣称本轮已复用或省下训练。

## 5. P4：模块 endpoint 补查 CAL_used——已修复

位置：[modern_head_onboarding_v1.py:36](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_onboarding_v1.py:36)。与 DEV/reference 一起要求 `CAL_used is False`，字段缺失也拒绝。

验证：EndpointCalScopeTests 覆盖 false 通过、true/缺失拒绝，并重跑所选原 adapter 回归检查。日志 L2、L6；回执 `review_findings.P4`。

## 6. P5：现代头合同范围文字覆盖所有 family——已修复

位置：[modern_head_evaluate_v1.py:23](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_evaluate_v1.py:23) 的 `modern_gates` 及新包 `experiment_contract.json`。`additional_regression.applies_to` 改为 `Each seed and ensemble of every family: MLP_QUERY_BCE, TabM, LightGBM`。只对深拷贝的现代头门槛对象改说明，原 QUERY_TAIL 合同字节保持。

验证：2 项 ScopeTextTests 核对仅说明改变、所有数字规则仍被绑定，并拒绝旧的窄范围文字；选取的官方指标/门槛/端到端评价回归保持。日志 L3、L6；回执 `review_findings.P5.numeric_gates_unchanged=true`。

## 7. P6：M 阶段显式保护零训练更新——已修复

位置：[modern_head_runner_v1.py:279](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/modern_head_runner_v1.py:279)。M 返回后要求 `result.get('optimizer_updates') == 0`；缺字段或非零不能被当成成功。

验证：`test_module_optimizer_update_guard` 覆盖 0 通过、非零/缺失拒绝。日志 L3；回执 `review_findings.P6`。这是运行约束检查，不是“真实模块已经完成”的证据。

## 8. P7：缺离线依赖时在模型导入前明确退出——已修复

位置：[submit_once.sh:18](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/delivery_scripts/submit_once.sh:18)、[run.slurm:54](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/delivery_scripts/run.slurm:54)。两入口均先检查 `extra_deps` 目录与 `dependency_install_receipt.json`，缺少即给出离线安装提示，不自动安装或联网。存在性检查之外，原包 SHA、版本与运行身份检查仍执行。

验证：4 项缺目录/缺回执的模拟提交与作业检查，确认未启动模型 Python；作业失败仍保存退出与导出证据。日志 L7；回执 `review_findings.P7.automatic_installation=false`。

## 9. 验证范围与日志

最终归档已分别在 Windows、WSL 新目录安装，包封存与工作源码一致。受影响 Python 测试 **57 项**（新增修订测试 37 项、选取原测试 20 项）、Linux 模拟调度 **37 项**、分阶段导出 **3 项不同用例**通过，共 **97 项不同用例**。同 3 项导出用例在 Windows 与 Linux 各执行一次，最终安装包测试执行数为 **100**，不把跨平台重复说成新用例。PowerShell 7.6.5 只做 AST 解析，未执行传输。

| 编号 | 最终日志 | 范围 |
| --- | --- | --- |
| L1 | [revision_train](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/final_synthetic/test_modern_head_revision_train_v1.log) | 15 项 |
| L2 | [revision_replay](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/final_synthetic/test_modern_head_revision_replay_v1.log) | 8 项 |
| L3 | [revision_runner](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/final_synthetic/test_modern_head_revision_runner_v1.log) | 14 项 |
| L4 | [原 runner 回归](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/final_synthetic/test_modern_head_runner_v1.log) | 9 项 |
| L5 | [选取原 models 回归](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/final_synthetic/test_modern_head_models_v1.log) | 2 项 |
| L6 | [选取原 evaluate 回归](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/final_synthetic/test_modern_head_evaluate_v1.log) | 9 项 |
| L7 | [Linux 模拟调度](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/linux_validation/scheduler.log) | 37 项，含 Bash 语法 |
| L8 | [Linux 分阶段导出](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/linux_validation/export_phases.log) | 3 项 |
| L9 | [Windows 分阶段导出](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/windows_export_validation/export_phases.log) | 同 3 项跨平台复查 |

`validation.json` 保存各日志哈希、逐项选取清单与 `review_findings.P1` 至 `P7`。原 v1 的 41 项 Python 测试中，重跑 20 项，剩余 models 15/evaluate 6 共 21 项记 `rerun:false`；原完整 65 项套件未整套重跑。原 7 项导出 fixture 未重跑，本修订使用上述分阶段导出用例。QUERY_TAIL/入网旧完整套件（含旧 179 项）只继承哈希和原回执，`rerun:false`。本轮没有重复旧 G1–G4/D3 诊断。

最终核对发现回执测试类名误写为 NativeTreeTests，已更正为实际 NativeStopTests，并同步支持清单与回执哈希；仅外部元数据更正，封存包未变、测试未重跑。另做只读交付核对，P1/P2 说明与推荐命令未见阻塞。

## 10. 资源、限制与当前顺序

沿用 8 CPU / 16 GiB、4 数值线程、单重阶段进程、RSS 保护 14 GiB，未重新申请旧百 GiB 资源。72h Slurm / 70h 内部保护是**每个作业**上限；拆成两个作业后不再共享一个 70h 总预算，也不代表实际耗时已测得。

本地数值测试使用 Python 3.9 / NumPy 2.0.2 / Torch 2.8.0+cpu；目标 Python 3.9 / NumPy 2.0.1 / Torch 2.5.1 和 Linux x86_64/glibc≥2.28 尚未核验。WSL Python 3.12 只验证标准库安装/导出及模拟调度，不能据此声称目标模型运行兼容。完整真实峰值、实际时长和真实结果均待恢复后验证。三设备回归未接入，完整系统不得 PASS；零新增漏检仍是系统验收要求。

未来使用 v1r1：恢复父资产并完成 QUERY_TAIL 后，现代头 P/T/K 可先运行；入网 v1r1 完成六库与既定配对后，再用同包 `--modules-only` 接入两候选。本轮不等待新增多轮方案讨论，也不自动启动这些真实实验。
