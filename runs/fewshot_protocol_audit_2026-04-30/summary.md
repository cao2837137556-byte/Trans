# Few-shot Protocol Audit Summary

## 1. 本实验目的

本实验只补 `protocol-evidence`，用于防守 few-shot target alignment 主线中的阈值来源、support split 与评估泄漏问题。它不改变当前论文主线，不新增方法 claim，不训练模型，不重跑 few-shot 实验，也不修改论文主稿。

当前审计目标是确认：
- 是否在 final OOD eval 上调阈值；
- 是否使用 attack eval 参与阈值选择；
- few-shot positive support 是否与 final attack eval 泄漏；
- `original100` 与 `source_rich` 的 threshold / split 口径是否一致。

## 2. 输入资产

主线 official control：
- run: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\original100_fewshot_official_control_2026-04-22\`
- key files: `results.csv`, `original100_fewshot_official_control_summary.csv`, `selected_positive_samples.csv`, `diagnostics.json`, `config.json`

source-rich v7.2 fairness validation：
- run: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_2_fairness_validation_2026-04-22\`
- key files: `results.csv`, `frontend_f2_v7_2_fairness_summary.csv`, `config.json`

辅助核查：
- v7.3: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_3_da_fairness_comparison_2026-04-22\`
- v7.4: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_4_paired_holdout_fairness_2026-04-22\`

v7.3 / v7.4 只用于确认 source-rich 分支延续了同类 threshold policy、seed set 和 final OOD eval non-leakage 标记，不扩大本轮 E3 主表。

## 3. 阈值来源审计

审计结论：
- `fixed_id_calib_q99`：只使用 ID calibration 的 q99 阈值。
- `guarded_id_calib_and_ood_val_target1pct`：使用 ID calibration + OOD validation guard，目标为 1% alarm。
- final OOD eval 与 attack eval never used for threshold selection。
- attack train positives 只用于训练 L2 LogisticRegression head，不用于阈值选择。

从 `original100` 与 `source_rich v7.2` 的 `results.csv` 中可见，两者使用同名 threshold policies：
- `fixed_id_calib_q99`
- `guarded_id_calib_and_ood_val_target1pct`

对应 `threshold_source` 字段均写明：
- `ID calibration q99 only; final OOD eval not used`
- `ID calibration + OOD validation guard; final OOD eval not used`

本轮已生成 `threshold_provenance.csv`，可作为 paper-facing threshold provenance 表。

## 4. Few-shot support split 审计

当前 final split：
- high-purity attack total: `6871`
- train candidate pool: `4122` rows
- validation: `1374` rows
- final attack eval: `1375` rows
- train first/last: `2921 / 7042`
- validation first/last: `7043 / 8416`
- eval first/last: `8417 / 9791`

positive sampling seeds：
- `42,43,44,45,46`

审计结论：
- 16-shot 与 32-shot support 都来自 high-purity attack train candidate pool。
- train candidate pool rows `2921-7042` 与 validation rows `7043-8416` 连续分离。
- train candidate pool rows `2921-7042` 与 final attack eval rows `8417-9791` 连续分离。
- `original100` 与 `source_rich` 使用相同 stage2 high-purity split、相同 positive budgets、相同 positive sampling seeds。

注意：
- `source_rich v7.2` 没有单独的 `selected_positive_samples.csv`，但 `results.csv` 记录了每个 budget/seed 的 `positive_train_count`、`positive_train_first_row`、`positive_train_last_row`。
- `original100` 的 `selected_positive_samples.csv` 也记录 support count 和 first/last selected row，不保存完整 support row-id list。
- 由于 documented train candidate pool 与 val/eval 是连续 disjoint split，且所有 persisted first/last selected rows 都落在 train pool 内，本轮 leakage check 判定为通过。

本轮已生成 `support_split_audit.csv`。其中 `source_rich 64-shot` 仅标为 appendix candidate，不进入主结论。

## 5. 审计结论

明确结论：
- `original100`：通过。
- `source_rich`：通过。
- 未发现 final OOD eval 被用于 threshold selection。
- 未发现 attack eval 被用于 threshold selection。
- 未发现 few-shot candidate train pool 与 final attack eval 的 overlap。
- 未发现 original100 与 source_rich 在 fixed / guarded threshold 口径上的不一致。

Warnings：
- source_rich v7.2 未保存单独 selected-positive 全量 row-id 文件；当前审计基于 config split、script policy、results 中的 support count/first/last row 以及连续 disjoint split。
- original100 selected_positive_samples.csv 也不是完整 row-id list，只记录 count 和 first/last。若审稿阶段需要每个 seed 的完整 support row IDs，可根据已固定脚本、seed 和 stage2 train pool 重新生成 provenance log；不需要重训模型。

总体裁决：

`fewshot_protocol_audit_passed`

## 6. 论文使用建议

建议用法：
- `threshold_provenance.csv` 可进入 appendix 或 protocol table，用于证明 threshold non-leakage。
- `support_split_audit.csv` 可进入 appendix，用于证明 few-shot support 与 validation / final eval 分离。
- 本 summary 中以下句子可写入 Experiment Setup 或 Threats to Validity：
  - “Final OOD evaluation and attack evaluation are never used for threshold selection.”
  - “Few-shot positives are sampled only from the high-purity attack training candidate pool, which is disjoint from both the attack validation split and the final attack evaluation split.”
  - “The same threshold policies, positive budgets, and positive sampling seeds are used for original100 and source_rich.”

