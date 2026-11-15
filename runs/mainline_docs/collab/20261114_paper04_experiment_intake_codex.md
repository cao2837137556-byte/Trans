# paper04 三项实验交接

**结果** 统一参考库的真实预检 184136 已通过，正式重放由 184138 执行。检测头迁移 184140 的五个配置已完成验收。攻击覆盖待 anti 复核后商定。

**影响** 统一参考的建法、跨检测头迁移、攻击场景覆盖各自有独立的比较问题。论文主结果使用已验收的完整库 MLP p=4。

**下一步** 统一参考库按冻结线验收，检测头迁移使用已回传的指标和配对表。

## 1. 统一参考库规则

按 acfe0a1 比较统一的 K8192 建库候选与现行 P4。保持原两小时库，每设备×协议历史上限 8,192，固定物理包身份哈希。184105 的候选特征已封存，查询 UID 表示问题修复后，由 184136 复用原产物通过预检。184138 做唯一正式配对重放，按原零退化要求验误报、加权误报率和逐查询攻击撤警。

[冻结卡](20261113_unified_reference_bank_k8192_freeze_codex.md) · [184105 修复与续跑](../../unified_reference_bank_k8192_v1_20261113_uidfix_184105/RECOVERY.md)

## 2. 检测头迁移补证

本项检验同一个正常参考修正机制能否迁移到不同基础检测头。固定五个新增配置及顺序。

1. TabM＋2D，与已验收的 TabM RAW 和 TabM＋3D 配对。
2. CatBoost＋2D、CatBoost＋3D，与已有 CatBoost RAW 配对。
3. SLAD＋2D、SLAD＋3D，与已有 SLAD RAW 配对。

完整库 MLP p=4 为只读主结果。各配置独立输出，复用原训练权重、完整参考库、冻结查询、分组权重、评价视图和源阈值。固定 p=4、λ=0.25 和 SYN 无 ACK 旁路。同头 2D／3D 使用同一基础分数与原生扣分尺度，唯一的匹配差异是设备上下文。逐种子扣分后按原顺序求集成均值，使用各头已封存的集成阈值。

先核对模型和原缓存、完整库 support2／support3、查询 UID 顺序及阈值，用缓存复现三种 RAW 和已有 TabM＋3D。TabM 复用三个种子的概率、源尺度和阈值，修正后的实数分数继续参与阈值比较。CatBoost 冻结三个 model.cbm，使用 RawFormulaVal 和源 FIT 的 617,908 条完整行，按逐行对齐、正常攻击各占一半的权重计算加权 Q90−Q10。SLAD 冻结三个已验收 checkpoint.pt，通过修复后的原生入口，仅用 134,493 条源正常训练行及逐 UID 对齐的正常分层权重计算加权 Q90−Q10。CatBoost、SLAD 各自的一次源打分服务于同头两种修正。

逐查询核对各头的 2D 告警集合 ⊆ 3D 告警集合 ⊆ RAW 告警集合，旁路告警一致。UNSW 三方法各保留原有攻击告警 72,412、34,422、54,003，重点比较正常误报。CIC 和 Edge 同时报非旁路攻击的配对变化。三个种子与集成全部报告，CIC／UNSW 各保留完整与建档后视图，Edge 使用原选中查询。回传普通率、分层加权率、适用 HT、三组比较的增撤警、尺度来源与 Q10／Q90、验收和资产 SHA。大数组留超算。

184140 已复现三头 RAW 与 TabM＋3D，五个新增配置全部通过验收。回传文件的哈希通过本地核对。见[结果入口](../../p4_head_transfer_followup_v1_20261115/EXECUTION.md)。

本地封装和真实小切片须覆盖实际缓存及打分路径。SLAD 小切片含修复后的 checkpoint 重载与原生打分。通过后使用已建立超算通道提交结果作业，按原进度页和验收流程交接。

[TabM p4 正式验收](../../p4_tabm_acceptance_v1_20261111/FORMAL_ACCEPTANCE.json) · [CatBoost RAW](../../baseline_author_defaults_v1_20261108/CatBoost_COMPLETE.json) · [SLAD 重载验收](../../baseline_slad_eval_repair_v1_20261108/CLEAN_PREDICTOR_GATE.json) · [源数组回执](../../baseline_training_readiness_v6_20261107/SOURCE_RESULT.json)

## 3. 攻击覆盖

本项考虑非泛洪攻击下是否还能保留原攻击告警。已复核 CIC 主评价的 79,056 条攻击查询均来自 11 份洪泛采集。HeimVision 的 RTSP 认证攻击已登记为可核验候选。等待 anti 复核后确定测试场景和验收口径。

[CIC 冻结查询](../../diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/CIC_DEV.jsonl.gz) · [HeimVision 候选登记](20261031_well_history_normal_reference_execution_plan_r2_for_codex.md)
