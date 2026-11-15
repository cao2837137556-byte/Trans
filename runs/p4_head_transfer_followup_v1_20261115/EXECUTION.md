# 检测头迁移补证

作业 184140 已提交并通过真实输入小切片。运行顺序为 TabM＋2D、CatBoost＋2D／3D、SLAD＋2D／3D。

基础分数与查询使用既有封存资产，按 UID 及标签对齐，先复现各头 RAW 和 TabM＋3D。2D／3D 共享每个头的原源阈值、自身尺度、完整参考库和三种子平均。修正固定 p=4、λ=0.25 和 SYN 无 ACK 旁路。

CatBoost 使用完整源 FIT 的 RawFormulaVal 和已封存的逐行权重，SLAD 使用修复后的原生入口和源正常 FIT，原权重按正常行对齐并归一到一。以每头的加权 Q90−Q10 做尺度。最终逐查询检查 2D ⊆ 3D ⊆ RAW、旁路一致性和三头的 UNSW 冻结攻击告警数。

[资产和既有回执](HEAD_ASSETS.json) · [运行包清单](PACKAGE_MANIFEST.json)
