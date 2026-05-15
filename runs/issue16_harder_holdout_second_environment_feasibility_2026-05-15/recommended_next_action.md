# 下一步建议

## 1. 当前决策

暂时不要升级 adapter。只有在恢复 v7.4 hard-holdout 资产的固定配置 feature/model/scaler/score pipeline 后，才启动 `issue16b_harder_holdout_fixed_guard_validation_2026-05-15`。

## 2. 如果使用 v7.4

建议 issue16b 的最小设计为：

1. 预注册候选：`chrono_late_train_early_eval` 和 `holdout_bin_2`。
2. 运行 original100 fixed-guard LR，32-shot，OOD weight = 2；如成本允许，使用 seeds 42-51。
3. 加入 original100 plain LR 作为 paired no-guard control。
4. source_rich 只作为 secondary，因为 issue11 已显示 source_rich 不是稳定主驱动。
5. 必须先输出 support provenance 和 threshold provenance，再解释指标。

## 3. 如果 v7.4 recovery 失败

停止并输出 recovery report。不要强行把 BoT-IoT 或 TON-IoT 塞进当前协议。

## 4. 如果没有 harder-holdout 候选可用

转向 second-environment asset acquisition / protocol conversion 计划，先定义 role manifest 与 feature extraction，再做任何模型实验。

## 5. 论文边界

在 issue16b 或干净第二环境完成前，论文只能说当前机制已经在 primary split 和已有 hard-holdout audit 中获得支持；不能写成完整 external validity 已证明。
