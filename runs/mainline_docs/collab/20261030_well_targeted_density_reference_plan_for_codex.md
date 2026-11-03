# 定向补密度参考 + 逐设备攻击保护门：实验方案（给 Codex）

状态：`DESIGN_V1_IMPLEMENTATION_PENDING`。**本文不构成运行授权，运行需用户明确授权；Codex 同意不算授权。**
作者：Jax Well，2026-10-30。

## 0. 事实来源（只读，SHA 为文件前12位）
- R1 `runs/ab_reachable_bounds_readonly_v1_20261028/RESULT_REVIEW.md`（bdb99f2947f1）
- R2 `runs/mainline_docs/CURRENT_PROBLEM_BRIEF_20261025.md`（62bb3f32eee2）；R3 `NEW_CHAT_START_HERE.md`（eb4c337331ee）
- R4 `collab/20261030_reference_attack_competition_after_source_fail_for_grok.md`（1ad8c68fd69e）

已查明：
1. V3 dense 参考（179602）：新增合法参考 21,660 条，实际 21,764 逻辑行／22,514 物理位置；三库 26,549 行（R2 L73–75）。λ=.25，主 ε=.1pp（R1 L11）。**参考池来源字段、k、半径/距离、选点规则：未知**（本次未读到 `dense_reference_matrix_v1_20261027/EXECUTION_CARD.md`）。
2. 179700 残留 FP：A 共 64 条、B 共 14,741 条（R1 L36）。按设备数量/权重/support 明细：**未知**。已知设备级下界：A HeimVision 单组件扩展后仍 2.512194%；B TP Link 在“单组件＋正 support”下仍 7.230553%，免费消掉正支持与单组件全部 FP 仍 6.869728%（R1 L28–34）。
3. 上限盘点结论（R1 L26–36）：仅增强正 support 排除（A 2.91%/B 8.59%）；只有“单组件＋正 support”（A 0.173727%）和“单组件＋全部合格双组件”（A 0.173727%/B 0.421761%）尚未排除；最大组合剩 A 4 条、B 844 条 FP。最大组合潜在可撤回 TP：A 1,202 条/0.366159pp，B 2,915 条/6.004144pp；Samsung 设备暴露 17.546136pp；seed127 HeimVision 1.471271pp（>1pp 门）（R1 L58–68）。
4. FIT 正常候选按设备数量及近 cut 数量：**未知**。
5. 近边界攻击按设备分布：**未知**。仅知 CAL OTHER 最小 TP margin≈31.02，HELD∩FIT 中可低至 0.002471（R1 L70）；P1 也有“CAL 攻击远离边界、HELD 攻击靠近边界”证据（R4 L38）。

## 1. 假说
在合法 FIT 中，向残留 FP 设备的近 cut 正常区定向补 V3 式 dense 参考，可让这些查询从零/低 support 变为正 support，从而降 FPR；同时以近边界攻击禁区保证补点不覆盖攻击。
- 对 V3：V3 是全局补密，本方案只补残留设备与近 cut 区，并加攻击禁区。
- 对 HARD/CTX：不训练新模块，不改头、λ、scale、cut。
- 对局部几何（B1/v2）：不改 support 的几何定义，只改参考库存。
- 对参考竞争（180228）：不引入攻击参考对冲，不改判分；保护靠事先固定禁区和含近边界攻击的校准集。

## 2. 补点规则
- 目标设备：A＝HeimVision；B＝TP Link、Samsung、WEMO；另加 179700 中按权重 FP 贡献排前、且合计覆盖该池 ≥90% 残留加权 FP 的设备（Codex 只读核实，名单在运行前冻结）。
- 候选：只取 FIT 正常点，且 RAW 集成分数在 `[cut−δ, cut+δ]`，默认 δ 取该设备 FIT 正常分数在 cut 附近的 10% 分位宽度（待核实）。不得取 HELD、CAL、S、A、B 中的点。
- 每设备上限：`min(档位上限, 该设备近 cut 候选数)`；档位见 §4。
- 去重：与现有 26,549 行参考及已选点的 E3 距离 ≤ τ_dup 时丢弃（默认 τ_dup＝V3 所用 support 半径的 0.5 倍；V3 半径待核实）。时间上同一流/会话只留 1 点。
- 攻击排除：候选与 FIT 中任一攻击的距离必须 > r_atk（默认 r_atk＝V3 support 半径 ×2）。

## 3. 攻击保护
- 近边界攻击禁区（运行前冻结）：FIT 中 RAW margin 低于该设备攻击 margin 10% 分位的攻击点，各取半径 r_atk 邻域；补点不得落入。
- 校准集：CAL＋HELD∩FIT 中的近边界攻击（按上述定义）必须显式加入，每设备至少 min(50, 可用数) 条；不足则在报告中标为覆盖不足。
- 源侧门（FIT/HELD∩FIT 上评估）：逐设备撤回 ≤1pp；逐活动 ≤5pp；若 RAW 召回已 <99%，禁止撤回任何原 TP。任一门失败即该档位不合格。

## 4. 选型
- 只在 FIT 或 HELD∩FIT 上选。三个预登记档位：每目标设备上限 D1＝500、D2＝2,000、D3＝5,000 点（默认值，Codex 核实候选量后可按比例缩放但须在运行前冻结）。
- 唯一规则：在通过全部源侧门的档位中，选 HELD∩FIT 加权 FPR 最低者；并列取点数最少者；无档位通过则结项。
- 冻结后 S 看一次；A/B 各看一次。

## 5. 主终点与判据
- 通过：A、B 加权 FPR 均 ≤2%，召回均 ≥99%，逐设备撤回 ≤1pp、逐活动 ≤5pp。
- 记录：TP Link 零支持行数及其中转为正 support 的比例；HeimVision 组件不足/正支持不足各自的 FP 变化；Samsung、WEMO 的 FP 变化。

## 6. 资源
4CPU / 8GiB；源侧 ≤4h＋目标 ≤4h；单次运行，0 自动重试。

## 7. 停止条件
- 源侧门失败即结项，不调档、不改禁区。
- A/B 未达标但有改善：记录 `IMPROVED_NOT_PASS`，报池/设备 FPR 及与 179700 的差值，不再迭代。
- 本候选失败后转写论文边界章节。

## 8. 披露
S 与 A/B 已被多轮开发接触，结论降级为“开发集上的观察”，不得称独立确认。

## 9. 给 Codex 的只读核实问题（最多3个）
1. V3 dense 参考的池来源、k、support 半径/距离和选点规则（EXECUTION_CARD 及 179602 产物）。
2. 179700 中 A/B 残留 FP 按设备的行数、权重和 support 分布；FIT 正常近 cut 候选按设备的数量。
3. FIT/HELD∩FIT 中近边界攻击按设备的数量和 margin 分布，用于冻结 δ、r_atk 和禁区。
