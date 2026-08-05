# CKBW 实现接管交接文档（Kimi 续写，2026-08-05）

> 状态：**实现已完成本地验证；未构建 bundle、未提交 HPC、未经 Codex 复审**。
> 背景：Codex 在 2026-08-05 写至断点（核心损失/双阈值/冻结分数合同已就绪，
> 缺管线接入）后 token 耗尽。用户授权 Kimi 按三方既定约束续写：
> 不重设计、不改 Codex 核心逻辑、数据装配复用 CKBU 已验证函数、每步留证据、
> 不打 bundle、不上 HPC。本文档是 Codex 复审的入口。

## 1. 断点确认

- 断点文件：`repo/ood/issue27ckbw_tail_margin_dual_control_v1.py`（954 行，未跟踪）。
- 断点 HEAD：`07de4770c9776e5ef79d1f33eda2cd0675117ace`（FROZEN 预注册）。
- 断点处已有：`FrozenScoreBundle`、`select_epoch_tails`、`family_balanced_row_weights`、
  `tail_losses`、`choose_dual_gate`、`apply_dual_control`、`one_sided_or`、
  `TailMarginTabM.fit_candidate`（完整训练循环）、`--contract-unit`、`--validate-frozen`。
- 缺：`--formal` 管线（装配 → 训练驱动 → 8 臂评估 → §11 审计 → GO/NO_GO）。

## 2. 本次新增（全部为追加，文件现 2,745 行）

新增管线段（约 1,780 行，追加在原 954 行之后）：

- 常量：`EXPECTED_PROTOCOLS`、`HELD_OOD_FAMILIES`、门槛常量、`TABM_CONFIG`（§14.1 五处一致硬门）。
- 装配：`assemble_protocol`（逐行镜像 `ckbu.run_protocol` 的数据装配段：
  `ckbo.fit_c1_attack_preserving` → `ckbo.collect_formal_sets` → aux/ToN 过滤 →
  `ckbu.unique`）、`assert_global_pool_contract`（18,398/4,385/14,013/12 族/69/7,000=3,000+4,000）。
- 单评分器合法性：`assert_protocol_identity`——逐协议断言 fit/select 的 uid 序列与 GLOBAL
  完全一致（见 §3 证据），把"各协议模型相同"从经验事实变成强制合同。
- 冻结对齐：`frozen_aligned_frame`（`assert_exact_uid_coverage`）、
  `fresh_c1_vs_frozen_audit`（新鲜装配的 C1 决策必须逐行等于 154917 冻结帧）。
- 双门控审计：`dual_scope_audit_rows`（§7.4：mixed 7,000 / aux 3,000 / ToN 4,000
  四个原始量 + 两个恒等式逐组断言）。
- 训练驱动：`train_tail_margin_candidates`（λ 网格 2×2、每候选独立 `TailMarginTabM(SEED)`、
  `replay_candidate_best` 复现词典序选择并与 `fit_candidate` 自报 gate 交叉核对、
  winner 加载 `best_state` 并取 `model_hash`）。
- 评估：`evaluate_arms`（直接复用 `ckbj.metric_rows/attack_summary_rows/strict_level2_summary`，
  调用方式与 CKBU 完全一致）。
- §11.3：`transition_matrix_rows`（Frozen×PRIMARY 逐行转换矩阵，含每 family kept/rescued/suppressed）。
- §8：`udp_scan_diagnostic_rows`（只诊断，`selection_use="none"`）。
- §9：`scientific_outcome`（只评 PRIMARY；攻击 0.5pp/族 2pp/support 69/69、
  OOD macro≤0.302722、族恶化≤+2pp、族≤0.90、multi-held 不得缺失、合同门）。
- `run_formal`：完整管线 + 22 个输出文件（清单见 §5）。
- 本地验证模式：`--frozen-arm-preview`、`--smoke-store`、`--smoke-formal`。

对 Codex 已有代码的 4 处**纯追加式**修改（请重点复审）：

1. `fit_candidate` 的 `histories.append` 增加 `tail_selection_audit` 字段
   （§11.2 要求逐 epoch 的 n_f/k_f/pair 数与 benign tail 源构成；训练数学零改动）。
2. `parse_args` 扩展新参数（原 4 个参数行为不变）。
3. `main` 扩展新分支（原两个分支行为不变）。
4. `if __name__ == "__main__"` 块从文件中部移到末尾
   （否则模块执行到该块时追加段常量尚未定义，`NameError`）。

## 3. 关键设计事实（实现依据，均有本地实证）

1. **各协议冻结分数逐位相同**：154917 冻结帧中同一 uid 在 5 个协议下的
   `tabm_process_score`/`extra_process_score` 最大跨协议差 = 0.0（7,069 个 select uid 全量核对）。
   原因：合法 fit/select 池不含任何 held 族行，各协议模型训练数据逐位相同。
   因此 CKBW 只训**一个共享评分器**，`assert_protocol_identity` 在运行时强制这一点。
2. **select 池无 held 泄漏**：support_val 69 行设备族 = city-power/combined-cycle/ip-camera-museum；
   aux_select 3,000 = building-monitor/combined-cycle/combined-cycle-tls/domotic-monitor；
   均不含 4 个 held 族。门控选择只在 GLOBAL select 进行一次，对全部协议合法。
3. **冻结帧自带连续分数**：`tabm_process_score`/`extra_process_score` 覆盖全部 297,326 行，
   有限、UID 唯一、模型哈希与审计一致（`--validate-frozen` 通过）。
   故 M5/A4 零重训，直接复用（预注册 §4.2）。
4. **raw51 mask 不打到任何已评分行**：冻结帧 `raw51_observable` 全 True
   （masked 1,353 个 target 不在任何 select/report 池）；代码仍保留 fail-closed 守卫与审计。
5. **ToN 基线约定**：20,000 个 ton 行 `c1_hard=True`、`frozen_ckbq_hard=False`（保守口径），
   与 CKBU 写出逻辑一致。

## 4. 本地验证证据（全部真实执行）

| 验证 | 结果 |
|---|---|
| `py_compile` | OK |
| `--contract-unit` | `CKBW_CONTRACT_UNIT_PASS`（无回归） |
| `--validate-frozen`（本地拉回帧+审计） | `CKBW_FROZEN_SCORE_CONTRACT_PASS`（三哈希一致） |
| `--frozen-arm-preview`（真实 154917 分数） | 完成：CE/A4 门控 + 6 臂 5 协议评估，见 §6 |
| `--smoke-store`（合成小缓存） | `CKBW_SMOKE_STORE_PASS`（28 行×51D 接线/预处理/变换） |
| `--smoke-formal`（外挂 harness 将 EPOCHS=2、λ 单点；repo 文件零改动） | `CKBW_SMOKE_FORMAL_PASS`：训练循环、frontier replay、winner、scope 对账、输出落盘全通；epoch2 `tail_selection_audit` 含 12 攻击组（k_f/pairs≥128）与 16 条 benign tail（15 源均衡） |

冒烟 harness：`_kimi_review/ckbw_smoke_harness.py`（仓外脚手架，不进入交付）。

## 5. `--formal` 输出清单（对应预注册 §11）

科研指标：`ckbw_all_metrics.csv`、`ckbw_per_attack_family_metrics.csv`、
`ckbw_attack_preservation_summary.csv`、`ckbw_strict_level2_summary.csv`、
`ckbw_record_predictions.csv.gz`（8 臂逐行决策+分数+阈值）。
训练审计：`ckbw_tail_training_loss.csv`（含 tail_audit/tail_selection_audit）、
`ckbw_tail_candidate_selection.csv`、`ckbw_group_balance_audit.csv`、
`ckbw_preprocessing_audit.csv`、`ckbw_support_training_usage.csv`（385×24）、
`ckbw_model_audit.csv`。
阈值与决策审计：`ckbw_dual_gate_frontier.csv`、`ckbw_dual_gate_scope_audit.csv`、
`ckbw_transition_matrix.csv`、`ckbw_raw51_mask_audit.csv`、
`ckbw_c1_fresh_vs_frozen_audit.csv`、`ckbw_protocol_scope_audit.csv`、
`ckbw_role_usage_audit.csv`。
其他：`ckbw_udp_scan_diagnostic.csv`、`ckbw_permanent_report_only_audit.csv`、
`ckbw_frozen_model_scope_audit.csv`、`ckbw_review_audit.csv`、
`ckbw_single_seed_go_no_go.json`、`ckbw_environment.json`、`run_spec.json`、`ckbw_readout.md`。

CLI 资产参数与 `ckbu.parse_args` 同名（6 个显式 runtime 资产 + 7 个统一缓存/冻结路径
+ raw51 mask 两参），installer/Slurm 可按 CKBV 模式一比一适配（**未构建**）。

## 6. 真实数据预览（preview 口径，非正式结果）

preview 用真实 154917 分数跑双门控 + 6 冻结分数臂评估（CI 聚类降级为 source 级，
点估计精确；无 tail-margin 臂）：

- CE-Dual 门：τ_normal=0.853938、τ_attack=1.000000（rescue=0，即纯抑制型控制）；
  ExtraTrees-Dual 门：τ_normal=0.489414、τ_attack=1.000000。support_val 69/69 保持。
- select 对账：mixed 7,000 中 frozen_hard=27（全部在 aux 3,000；ToN 4,000 为 0），
  两臂均 suppress 27、rescue 0、net +27。
- **OOD 侧**：CE-Dual 四族 = 0 / 0 / 2.69% / 0.17%（macro≈0.72%）；
  ExtraTrees-Dual = 0 / 6.47% / 2.94% / 26.37%（macro≈8.95%）。
  双边控制对良性 OOD 抑制极强。
- **攻击侧代价**：CE-Dual GLOBAL 总召回 80.88%（vs C1 −10.42pp，阈值τ_normal 误伤攻击）；
  ExtraTrees-Dual 83.51%（−7.79pp）。均远超 §9.1 的 −0.5pp 门槛。
- 结论：预览精确复现了预注册 §1 的核心矛盾——dual control 能压 OOD，
  但 CE 尾部边界会牺牲攻击；这正是 tail-pair margin 要解决的问题
  （把攻击尾部 q 推离 τ_normal）。PRIMARY 的胜负手在 tail-margin 训练后的支持族
  worst-margin，正式结果只能来自 HPC 的 `--formal`。

## 7. 已知风险 / 待 Codex 复审项

1. `--formal` 的装配段逐行镜像 CKBU 但**只能在 HPC 全资产下首跑**；本地无法覆盖
   `prepare_inputs/collect_formal_sets/UnifiedFeatureStore` 真数据路径
   （已用 smoke-store 覆盖接线用法，preview/smoke-formal 覆盖其余）。
2. 训练时长：每 epoch 一次全拟合可微 margin 更新 + fit/select 评分，
   单候选约数分钟 CPU 级；4 候选 × 24 epoch 需在 Slurm 资源请求中留足（建议先单候选计时）。
3. `torch.use_deterministic_algorithms(True)` 已按 CKBU 惯例开启。
4. `assert_protocol_identity` 对 uid 序列顺序敏感；若 CKBO 未来改变记录顺序会误判——
   当前数据下两协议序列逐位相同。
5. preview 显示冻结分数下 τ_attack=1.0（rescue=0）：OR 臂（M6）在 tail 分数下可能同样
   rescue≈0，使 M6≈M1；这是合法结果，不是 bug，但 §11.4 归因解读时需注意。
6. `scientific_outcome` 的族门用 `rows>=15`（§9.1）；UDP Scan 保留逐族报告但不设放行条件（§8）。
7. `records_from_frozen_frame` 仅供 preview/smoke，`episode_id` 降级为 source；
   formal 评估用真实装配记录（episode 谱系完整）。

## 8. 边界声明

- 未修改：任何科学面（features/targets/roles/mask/threshold/model/seed/review/分母）。
- 未做：bundle 构建、上传、HPC 提交、seed 37/47、cooler-motor、PCAP 重解码。
- 下一步：Codex 复审本文件与代码 → 用户授权 → 构建 CKBW bundle（installer/Slurm 适配）
  → HPC `--formal` 首跑 → 按 §9 判定。
