# E5 Label-Budget / Label-Purity Sensitivity Feasibility Inventory

## 1. 任务边界

本轮只做 feasibility inventory，不做正式实验、不训练模型、不重算指标、不修改论文主稿、不改图表、不 push、不建 issue。所有写入仅限：

`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\e5_label_budget_purity_feasibility_inventory_2026-05-08\`

额外执行约束：

- E5 只能服务于 few-shot target alignment 的敏感性与边界验证。
- E5-A 不能把论文改成预算曲线论文。
- E5-B contamination 只能写成 controllable purity stress test，不能写成真实部署标签噪声定律。
- `source_rich` 不进入 E5 主线必跑项，避免角色从 hard-holdout robustness / auditability 漂移成新主方法。
- main text 默认只保留 guarded policy；fixed policy 如做，只放 appendix。

## 2. 可复用资产结论

已找到可复用资产：

- original100 feature cache：
  - `runs\frontend_f2_crosscapture_stage1_2026-04-13\data\id_source_100.npy`
  - `runs\frontend_f2_crosscapture_stage1_2026-04-13\data\ood_benign_source_100.npy`
  - `runs\frontend_f2_attack_source_2026-04-13\data\attack_source_100.npy`
- source_rich feature cache：
  - `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_source_rich_crosscapture_stage1_2026-04-20\data\*_source_expression_source_rich_v1_260.npy`
  - `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_source_rich_attack_source_2026-04-20\data\attack_source_expression_source_rich_v1_260.npy`
- original100 official control：
  - `runs\original100_fewshot_official_control_2026-04-22\results.csv`
  - `config.json`
  - `diagnostics.json`
  - `selected_positive_samples.csv`
- source_rich v7.2：
  - `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_2_fairness_validation_2026-04-22\results.csv`
  - already includes 16/32/64-shot under fixed and guarded policies.
- E2 seed stability pack：
  - `runs\fewshot_seed_stability_pack_2026-04-30\seed_summary.csv`
  - `paper_facing_table.csv`
- E3/E3-b protocol and support provenance：
  - `runs\fewshot_protocol_audit_2026-04-30\threshold_provenance.csv`
  - `support_split_audit.csv`
  - `support_id_provenance\selected_support_ids_full.csv`
- stage2 attack purity metadata：
  - `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage2_2026-04-01\attack_manifest_stage2.json`
  - contains `stage2_high_purity_attack=6871` and `stage2_boundary_mixed_attack=1297`.

未找到：

- 当前没有专门的 original100 contamination-positive 脚本。
- 当前没有已经完成的 original100 4/8/64-shot results。
- 当前没有 E5 budget/purity sensitivity run。

## 3. E5-A label-budget sensitivity 可行性

结论：

`E5-A feasible and recommended`

推荐最小设计：

- representation: `original100`
- budgets: `4, 8, 16, 32, 64`
- threshold: `guarded_id_calib_and_ood_val_target1pct`
- seeds: `42,43,44,45,46`
- model: same L2 LogisticRegression head

可行性依据：

- `repo\ood\original100_fewshot_official_control.py` 已支持 `--positive-budgets` 与 `--sample-seeds`。
- 当前 primary split 和 feature cache 已就绪。
- 16/32-shot 结果已存在，可作为 continuity check。
- 4/8/64-shot 需要正式 E5 时轻量重跑 LR head，不需要新 backbone 或新模型路线。
- E3/E3-b 的 provenance 逻辑可扩展到 4/8/64-shot。

不建议默认扩展：

- 不默认做 10 seeds。
- 不默认把 fixed policy 放进主文。
- 不默认把 source_rich 放进主线 E5-A。

## 4. E5-B label-purity sensitivity 可行性

结论：

`E5-B feasible with a new minimal wrapper/script`

推荐最小设计：

- representation: `original100`
- budgets: `16, 32`
- contamination rates: `0%, 10%, 25%, 50%`
- contamination source: OOD benign
- threshold: `guarded_id_calib_and_ood_val_target1pct`
- seeds: `42,43,44,45,46`

可行性依据：

- ID/OOD/attack feature cache 都存在。
- support sampling rule 已固定：
  - `rng = np.random.default_rng(seed + int(budget) * 1009)`
  - sampling without replacement from attack train pool.
- E3-b 可作为 contaminated support provenance 的模板。

需要新增的最小工程：

- contamination-aware support builder；
- contaminated support provenance log；
- purity sensitivity result aggregator；
- degradation relative to 0% contamination table/curve。

边界：

- 这是 controllable purity stress test，不是真实 SOC 标签噪声完整模型。
- replacement positives 训练时被故意标为 positive，只用于测试 high-purity-positive 假设被破坏时的敏感性。
- contaminants 不得来自 final OOD eval。

Design 2 lower-purity positives：

- stage2 manifest 中存在 `stage2_boundary_mixed_attack=1297` metadata。
- 但 lower-purity candidate row-id 构造需要单独审计，不建议作为默认 E5-B。

## 5. 是否需要 source_rich

不需要作为 E5 主线。

推荐策略：

- E5 main: original100 only。
- source_rich: 只作为 appendix candidate。
- 现有 v7.2 已有 source_rich 16/32/64-shot，可在需要时作为补充，不建议重跑完整 source_rich E5。

理由：

- 当前论文中 `original100` 是 few-shot target alignment 的主控制表示。
- `source_rich` 的角色已经限定为 hard-holdout robustness + auditability。
- 将 source_rich 放入 E5 主线会增加角色混乱风险。

## 6. 是否需要 fixed threshold

主文不需要。

推荐策略：

- main E5 tables/figures: guarded only。
- fixed ID q99: appendix optional。

理由：

- 当前 paper center 是 strict low-OOD-alarm guarded operating region。
- fixed + guarded 同时展开会使表格过大，削弱主线。

## 7. 是否需要 10 seeds

默认不需要。

推荐策略：

- 先沿用 seeds `42,43,44,45,46`。
- 只有当 4-shot 或 contamination 曲线明显波动过大，才考虑扩到 10 seeds。

## 8. 预计工作量

- E5-A original100: 低。
- E5-B original100 OOD contamination: 中。
- source_rich appendix: 低到中，取决于是否只复用 16/32/64 还是补 4/8。

## 9. 最大风险

最大风险是 E5-B 被误读成真实标签噪声建模，或 E5-A 预算曲线过多导致论文中心从 target alignment 变成 curve benchmark。

缓解方式：

- E5-A 只用 original100 + guarded 作为主文核心。
- E5-B 明确写成 controllable positive-purity stress test。
- source_rich 和 fixed policy 放 appendix 或不做。
- 每个新增 setting 都必须带完整 support / contamination provenance。

## 10. 是否建议正式进入 E5

结论：

`recommend_start_minimal_e5_after_user_approval`

最小推荐实验组合：

- E5-A:
  - original100
  - budgets `4/8/16/32/64`
  - guarded threshold
  - seeds `42-46`
- E5-B:
  - original100
  - budgets `16/32`
  - OOD benign contamination `0/10/25/50%`
  - guarded threshold
  - seeds `42-46`

该计划不改变当前论文主线，只补充 label-budget 与 label-purity sensitivity 证据。

## 11. 输出文件

- `summary.md`
- `reusable_asset_table.csv`
- `budget_sensitivity_feasibility.csv`
- `purity_sensitivity_feasibility.csv`
- `engineering_cost_table.csv`
- `scientific_value_table.csv`
- `risk_register.csv`
- `recommended_e5_plan.md`
