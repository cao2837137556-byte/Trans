# Issue16 harder-holdout / second-environment 可行性盘点总结

## 1. 本轮范围

本轮只做 harder holdout / second environment 的可行性盘点与最小验证设计。没有训练模型、没有调参、没有修改既有结果、没有修改论文主稿，也没有执行正式验证。

## 2. 当前状态

- issue13/14b/15 已经支持当前 primary low-OOD split 下的系统机制：GDA-minimal 作为 adaptation mode 的 high-priority alerting channel，base detector 通过 bounded review 作为可选 safety net。
- 当前最稳主方法仍是 `original100 fixed guard LR 32-shot`。
- 但项目还没有完成正式 harder-holdout 或 second-environment 泛化验证。

## 3. harder-holdout 候选

最接近可用的候选是已有 v7.4 paired hard-holdout pack：

`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_4_paired_holdout_fairness_2026-04-22`

该资产包含 `chrono_late_train_early_eval`、`holdout_bin_2` 等跨窗口设置。它适合作为 issue16b 的第一优先级候选，但不是“零风险、可立即 tiny validation”的对象，因为当前 GDA-minimal 的 fixed-guard model/scaler/row-level score 不能直接迁移到这些 holdout 窗口。正确做法是把它作为单独的 fixed-config hard-holdout validation，并重新输出 support / threshold provenance。

## 4. second-environment 候选

本地找到了 BoT-IoT 与 TON-IoT 资产，但都不能直接作为当前 same-protocol second environment：

- BoT-IoT 在上一轮 E4 中被 benign support 规模卡死，不适合强行构造当前 low-OOD 协议。
- TON-IoT 有本地 16 维 split/cache，但与 current original100/source_rich/GDA 特征空间不一致。

本轮没有下载或转换任何外部数据。

## 5. tiny validation

未执行 tiny validation。原因是没有候选同时满足：已有 original100/GDA 特征、完整 label、row-id 对齐、可复用 current model/scaler/threshold、且不需要重新训练或调参。

## 6. 下一步建议

如果继续泛化验证，建议启动 `issue16b_harder_holdout_fixed_guard_validation_2026-05-15`：预注册 `chrono_late_train_early_eval` 和一个 bin holdout，固定 OOD weight=2，不搜索超参，完整输出 support / threshold provenance。

如果 v7.4 recovery 失败，不建议马上升级 LR；应先做 second-environment acquisition / protocol conversion 计划。

## 7. 安全检查

- 修改论文主稿：False。
- 修改既有实验数字：False。
- 训练模型：False。
- 超参搜索：False。
- tiny validation：False。
- 新增泛化 claim：False。
