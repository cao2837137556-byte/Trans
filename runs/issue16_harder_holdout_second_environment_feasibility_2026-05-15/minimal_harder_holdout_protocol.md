# 最小 harder-holdout 验证协议草案

## 1. 推荐的首个正式候选

优先使用 `frontend_f2_v7_4_paired_holdout_fairness_2026-04-22`。其中 `chrono_late_train_early_eval` 适合作为代表性跨时间窗口 holdout，`holdout_bin_2` 适合作为补充 bin holdout。

## 2. 模型与固定配置

- 主方法：original100 fixed-guard LR，32-shot。
- 固定 OOD guard：OOD weight = 2，attack weight = 1，ID benign weight = 1。
- 不搜索 OOD weight、C、seed、support pool、threshold 或 scaler。
- source_rich 和 Transformer hidden 只能作为预注册的 secondary/sensitivity，不应作为默认主线。

## 3. 两种评估模式必须区分

1. Strict threshold transfer：
   - 只有当 score generation 与 calibration 语义完全一致时，才复用已有 threshold。
   - 需要明确报告为 strict transfer，并允许结果变差。

2. Protocol-recalibrated hard holdout：
   - 在 hard-holdout train side 上按固定配置重新训练 adapter。
   - threshold 只能来自 ID calibration + OOD validation。
   - final OOD 与 hard-holdout attack evaluation 只用于最终评估。
   - 这是一个单独的 hard-holdout setting，不是当前 row-level score 的直接迁移。

## 4. issue16b 必须输出

- `support_id_provenance.csv`：证明 support 与 eval 窗口 disjoint。
- `threshold_provenance.csv`：证明 final OOD / attack eval 未参与阈值选择。
- `method_comparison_summary.csv`：至少包含 original100 plain、original100 fixed guard，可选 source_rich/hidden fixed guard。
- 如果后续要做 arbitration，还必须输出 row-level score。

## 5. 泄漏控制

- 不从 attack eval window 抽 support。
- 不在 final OOD eval 或 attack eval 上 fit scaler。
- 不在看过 final metric 后选择 holdout window。
- negative 或 infeasible 结果也应作为边界证据如实记录。
