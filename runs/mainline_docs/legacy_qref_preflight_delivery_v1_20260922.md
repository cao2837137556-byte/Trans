# Q normal-reference verifier：真实预检授权与交付

2026-09-22。用户“允许”承接真实预检范围。工程交付已完成，尚未上传、提交或运行；不是科学结果。

仅授权目标环境合成测试、已有 E3 缓存身份核对及冻结 Q 在原 LEARN/DEV 的精确 float32 重放。独立入口不调用 run_chain；预检通过即 PREFLIGHT_PASS_TRAINING_NOT_STARTED，失败 STOPPED_NO_RETRY。无真实训练、校准、新方法 DEV 评估、HOLDOUT、PCAP 解码或 E3 重算。冻结实现与原大包未改。

交付目录：runs/legacy_qref_preflight_delivery_v1_20260922；操作入口 OPERATE_PREFLIGHT.md。用户负责上传/提交/拉回。4 CPU、64 GiB、2 小时时限、零重试；时限不是耗时预测。上传约 232 MiB，复用远端缓存，无原始数据重传。脚本显示上传进度、不可变推理批次进度、作业状态；失败导出日志，强制终止可能无法导出。

验证：7/7 Python 3.9 授权/停止边界测试；2/2 PowerShell 语法；5/5 Linux Bash 语法；Linux 封存哈希；模拟 sbatch 提交及重复拒绝；缺失环境时失败导出及回传 SHA 均 PASS。Linux 检查仅本地 WSL stdlib，无真实 sbatch/SSH。一次内联 Bash 检查因跨 shell 引号传递失败，已改为独立 Python 检查文件并通过；不是实验失败或重试。

目标 Linux 数值兼容及真实缓存/Q 重放仍待运行。64 项原合成单测和完整合成链将在计算节点先运行，然后才核对真实缓存。合成更新与真实更新分开记录，真实优化器步数必须为 0。没有改变冻结数据、门槛、模型或损失。旧 job172780 FAILED、M/C gate FAIL、HOLDOUT CLOSED 保留。

下一步：用户按操作指南上传并一次提交预检，拉回后核验；真实训练需要后续单独授权。
