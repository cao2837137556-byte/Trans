# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **诊断完成**：182560/182561/182562均COMPLETED/0:0，累计3:14；1CPU/8GiB，进程采样峰值1.684GiB。诊断验收PASS，原锚定模型科学FAIL保留，无新作业。
2. **8维确实使用**：Edge UDP原融合8维贡献中位数+5.91，置零召回98.66%→0；锚定贡献仅+0.64，置零基底裕量−1.45→−18.13，真实裕量−17.49。
3. **目标机制**：第1轮三个种子全参数/8列平均梯度均冲突；末轮8列锚定/分类梯度比1.23e5—3.47e6，完整日志锚定占loss>99.99%。非全程反向，未重放Adam，127不是唯一问题。
4. **下一方向**：保留原FUSION790，撤销全样本模仿弱782教师具体分数；先设计源域正常风险＋攻击裕量保护小试，核对硬负例覆盖。具体新目标未封存、未训练，不能直接减λ或只锚正常。
5. **证据/存储**：[验收报告](collab/20261106_context_anchor_diagnosis_acceptance_codex.md)，`runs/context_anchor_diagnosis_v1_20261105/FINAL_DIAGNOSIS_ACCEPTANCE.json`；1408项干预检查通过，大数组/逐批明细留超算，[验收页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
