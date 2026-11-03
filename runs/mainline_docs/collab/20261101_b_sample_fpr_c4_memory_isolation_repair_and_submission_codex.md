# C4 内存隔离修复与重新提交

日期：2026-11-01。用户授权：修复问题并重新提交同一 C4 候选；确认启动及右侧进度正常后结束本轮，不持续 AI 监测。

## 故障与取证

旧作业 `180526` 在 Samsung 的 `ENDPOINT_CENSUS` 第一遍扫描期间触发 `RSS_BYTES_LIMIT`，Slurm `FAILED|70:0`。失败快照：已扫描 4,071,424 / 5,880,402 包，已编码 12,288 行，距离对 0，耗时 9,003.328841215 秒。TP Link 的 4,096 行和 WEMO Power 的 8,192 行已经完整编码并保留凭据；Samsung 的局部 census 未完成，不作为可恢复状态使用。尚未执行 HIST_DEV 候选门或候选 A/B。

内存限制按 Python 与 TShark 子进程合计 RSS 计算。旧实现跨设备保留编码器及其分配器，同时启动大捕获解码；这是本次隔离要消除的叠加。没有证据证明 Python RecentState 随长连接无限增长，也不能预先保证 TShark 单进程永远小于 8 GiB。

原始故障取证：`runs/history_sample_coverage_c4_deployment_repair_v1_20261101/STATE_RECEIPT.json`。旧现场、旧提交回执及旧执行卡均保留。

## 修复范围

独立实现目录：`runs/history_sample_coverage_c4_memory_repair_v1_20261101/`。

1. 每台剩余设备的数据准备、模型编码分别进入独立串行子进程；前一进程退出并被回收后才进入下一阶段。准备路径不导入 torch/transformers。
2. RSS 仍合计父进程与子进程，保持 4 CPU / 8 GiB，并增加逐进程 RSS 诊断。保持原 TShark 56 字段与解码选项、完整顺序上下文和单样本 1→16 克隆规则。
3. TP Link / WEMO Power 仅在完整回执、源材料关联、所有文件 SHA、选点元数据、NPZ UID/形状/dtype/有限性、逐行特征哈希及 batch ATTEMPT/COMPLETE 全部验证后复用。复用行计入 36,864 行总预算。Samsung 与 Netatmo 从原包第一帧准备。
4. 原失败耗时按 `ceil(9003.328841215) + 60 = 9064s` 保守计费，编码与后续验收合计剩余 `19736s`。新 Slurm 时限 `05:28:56`，评价继续扣除新编码实际耗时；总计仍不超过原 28,800 秒。
5. 候选、选择盐、容量、λ=0.25、模型、阈值、C2 守卫、一次 HIST_DEV 门及一次 A/B 验收规则不变；没有新参数搜索、训练或新候选评价。

执行卡 SHA256：`5e7033951cb496adae38905b570e28c7f15f2564fe591b7112a0121d2f001814`。

## 核验与交付

- 本地工程与边界检查 36/36、交付检查 8/8 通过（包含真实 Slurm 脚本 Linux 换行检查）。
- 32 项实现/输入文件 pin 与原 709 项共享科学输入 pin 验证通过。
- 独立只读代码复核确认复用凭据合同与原编码器一致，准备进程不导入模型运行时。
- 新代码包 4,229,120 字节。远端已有 Netatmo 原包和两个索引共 2,405,307,756 字节全部复用，未重复上传大数据。
- 第一修复部署 `runs/history_sample_coverage_c4_memory_deployment_20261101/` 已通过超算 Python 3.11.11 / NumPy 2.0.1 / Torch 2.5.1、两台复用凭据及 36 项检查，但 `sbatch` 因脚本 CRLF 换行拒绝，未产生作业号，未启动科学计算。失败回执完整保留。
- 当前部署：`runs/history_sample_coverage_c4_memory_submission_repair_20261101/`。只将 Slurm 脚本换行为 LF 并同步其执行卡校验；安装前验证远端原文件 SHA、确认无 ENCODE_ATTEMPT/outputs，其余 33 文件逐字节保持。自动流程重新预检、一次提交、普通程序进度刷新、完成后取回及原门验收；不自动重新提交实验。

## 当前提交状态

已实际提交作业 **180552**，Slurm `RUNNING|node185`，提交返回码 0；超算环境、两台真实复用凭据及 36 项工程检查全部通过。17:56:52 的普通进度快照显示 Samsung `ENDPOINT_CENSUS`，已扫描 16,384 / 5,880,402 包，复用编码计数 12,288，距离对 0，合计 RSS 703,680,512 字节。它只说明已启动，不代表最终内存峰值或科学验收通过。

真实提交及预检回执：`runs/history_sample_coverage_c4_memory_submission_repair_20261101/SUBMIT_RECEIPT.json`。原进度目录 `CURRENT_SUBMIT_RECEIPT.json` 已指向新部署。右侧进度页保持 `http://127.0.0.1:18789/`，由普通程序更新并在完成后自动取回、验收。按用户要求，确认启动与页面正常后结束本轮 AI，不持续监测。

最终科学结论以新实现目录 `FINAL_ACCEPTANCE.json` 为准；当前没有 C4 新成绩。A/B 继续标记 `CONSUMED_DEVELOPMENT_ONLY`，B 全部 SYN 守卫攻击不证明 ACK/UDP 型攻击保护。
