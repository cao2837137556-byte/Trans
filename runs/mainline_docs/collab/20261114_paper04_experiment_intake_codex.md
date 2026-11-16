# paper04 三项实验交接

**结果** 统一参考库正式重放 184138 已完成。CIC 集成误报 18 降至 0，UNSW 误报 130 增至 136，因此统一库未通过原零退化验收。用户随后选择统一库作为论文主库。检测头迁移 184140 的五个配置已完成验收。攻击覆盖待 anti 复核后商定。

**影响** 论文主结果使用 MLP p=4 与 `P4_UNIFIED_HIST_K8192_V1` 统一参考库。原库保留为既有对照基准。

**下一步** 论文主表取 184138 结果，已有对照保留其实际使用的库身份。

## 1. 统一参考库规则

按 acfe0a1 比较统一的 K8192 建库候选与现行 P4。184136 复用原产物通过真实预检，184138 完成唯一正式配对重放。四头原攻击告警全部保留。用户优先采用统一的历史参考准入规则，论文主表使用统一库的实际结果。

[主参考库选择](20261115_paper04_main_reference_selection_codex.md) · [冻结卡](20261113_unified_reference_bank_k8192_freeze_codex.md) · [184105 修复与续跑](../../unified_reference_bank_k8192_v1_20261113_uidfix_184105/RECOVERY.md)

## 2. 检测头迁移补证

本项检验同一个正常参考修正机制能否迁移到不同基础检测头。固定五个新增配置及顺序。

1. TabM＋2D，与已验收的 TabM RAW 和 TabM＋3D 配对。
2. CatBoost＋2D、CatBoost＋3D，与已有 CatBoost RAW 配对。
3. SLAD＋2D、SLAD＋3D，与已有 SLAD RAW 配对。

本轮迁移对照复用原完整参考库。各配置独立输出，复用原训练权重、冻结查询、分组权重、评价视图和源阈值。固定 p=4、λ=0.25 和 SYN 无 ACK 旁路。同头 2D／3D 使用同一基础分数与原生扣分尺度，唯一的匹配差异是设备上下文。逐种子扣分后按原顺序求集成均值，使用各头已封存的集成阈值。

先核对模型和原缓存、完整库 support2／support3、查询 UID 顺序及阈值，用缓存复现三种 RAW 和已有 TabM＋3D。TabM 复用三个种子的概率、源尺度和阈值，修正后的实数分数继续参与阈值比较。CatBoost 冻结三个 model.cbm，使用 RawFormulaVal 和源 FIT 的 617,908 条完整行，按逐行对齐、正常攻击各占一半的权重计算加权 Q90−Q10。SLAD 冻结三个已验收 checkpoint.pt，通过修复后的原生入口，仅用 134,493 条源正常训练行及逐 UID 对齐的正常分层权重计算加权 Q90−Q10。CatBoost、SLAD 各自的一次源打分服务于同头两种修正。

逐查询核对各头的 2D 告警集合 ⊆ 3D 告警集合 ⊆ RAW 告警集合，旁路告警一致。UNSW 三方法各保留原有攻击告警 72,412、34,422、54,003，重点比较正常误报。CIC 和 Edge 同时报非旁路攻击的配对变化。三个种子与集成全部报告，CIC／UNSW 各保留完整与建档后视图，Edge 使用原选中查询。回传普通率、分层加权率、适用 HT、三组比较的增撤警、尺度来源与 Q10／Q90、验收和资产 SHA。大数组留超算。

184140 已复现三头 RAW 与 TabM＋3D，五个新增配置全部通过验收。回传文件的哈希通过本地核对。见[结果入口](../../p4_head_transfer_followup_v1_20261115/EXECUTION.md)。

本地封装和真实小切片须覆盖实际缓存及打分路径。SLAD 小切片含修复后的 checkpoint 重载与原生打分。通过后使用已建立超算通道提交结果作业，按原进度页和验收流程交接。

[TabM p4 正式验收](../../p4_tabm_acceptance_v1_20261111/FORMAL_ACCEPTANCE.json) · [CatBoost RAW](../../baseline_author_defaults_v1_20261108/CatBoost_COMPLETE.json) · [SLAD 重载验收](../../baseline_slad_eval_repair_v1_20261108/CLEAN_PREDICTOR_GATE.json) · [源数组回执](../../baseline_training_readiness_v6_20261107/SOURCE_RESULT.json)

## 3. 攻击覆盖

本项考虑非泛洪攻击下是否还能保留原攻击告警。已复核 CIC 主评价的 79,056 条攻击查询均来自 11 份洪泛采集。HeimVision 的 RTSP 认证攻击已登记为可核验候选。等待 anti 复核后确定测试场景和验收口径。

[CIC 冻结查询](../../diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/CIC_DEV.jsonl.gz) · [HeimVision 候选登记](20261031_well_history_normal_reference_execution_plan_r2_for_codex.md)
