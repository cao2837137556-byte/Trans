# 现代检测头 v1 独立代码复核

日期：2026-10-18
复核对象：`runs/modern_head_comparison_v1_20261018`
归档：`modern_head_comparison_v1_20261018.tar.gz`
归档 SHA256：`635d617637d8dbf2de7ce46cdbceda88e24286f36b371db1d71ed5d534c0dfc4`
复核方式：只读阅读源码、合同、资源计划、验证回执与日志；未改代码、未重跑 65 项测试、未连接远端。

## 结论

本地交付真实完成，不是“目录存在、代码已写”：归档 SHA、65 项测试日志、7 项导出检查均对得上；真实实验仍为 `NOT_STARTED`。主体设计与 10-15 方案一致，未发现目标标签泄漏、未发现按 A/B 分别选开关、未发现模块阶段偷偷训练。提交前建议处理 P1、P2；P3 影响审计强度；P4–P7 可随下一次修订处理。

## 已核实

- 归档实测 SHA256 与 `validation.json` 一致；42,357,873 字节；全新安装 160 个文件，封存 159 个文件。
- 合成测试 41 项（models 17、evaluate 15、runner 9）+ Linux 模拟调度 24 项 = 65 项通过；导出 fixture 7 项通过；PowerShell 仅语法校验，未执行。
- 资源：8 CPU/16 GiB/4 线程、单重阶段进程；阶段峰值 11.5 GiB，25% 余量后 16 GiB；RSS 保护 14 GiB；磁盘 8/16/6 GiB。
- 合同：seeds `27/127/227`，三族固定，最多 9 个训练终点；TabM 为成员概率平均后转 logit，LightGBM 为 raw margin，外部 ensemble 为 float64 mean-logit；阈值只用源 CAL 正常样本、严格 `score > cut`。
- `thresholds.json` 在 CIC/UNSW/FIT 评分之前写出；`fit_inputs` 只接受 FIT；模块阶段 `optimizer_updates=0`；缺三设备回归时 `complete_system_gate` 必为 PENDING。

## 问题

### P1（高）LightGBM 固定轮数断言会把“天然无法分裂”判成失败

位置：`repo/ood/modern_head_train_v1.py:161`

```python
c.require(counter[0] == rounds, 'TREE_FIXED_ROUND_BUDGET')
```

问题：LightGBM 在没有可用分裂时会自然停止，`current_iteration < num_boost_round`，回调次数也会少于 500。代码随后要求的 `training_log.json` 又记录 `effective_tree_iterations`，并注明“may retain fewer trees”；主线 `mainline_handoff.md` 10-18 条目也写的是“天然无法分裂时另报实际树轮数”。**代码与文档矛盾**。一旦触发，会在 TabM 约 41 小时之后、LightGBM 阶段直接失败，整链停在 K/M 之前。

建议：改为 `0 < counter[0] <= rounds`，在 endpoint/training_log 记录 `requested_rounds`、`callback_iterations`、`effective_tree_iterations`、`native_stop`；不要启用早停，也不要按目标结果选轮数。补一个“常数特征/无分裂”的合成测试，确认能正常保存并报告实际树轮数。

验收：合法 native stop 不再抛 `TREE_FIXED_ROUND_BUDGET`；结果如实报告实际树数，不写成 500 轮全部完成。

### P2（中）P/T/K 被入网完成度强耦合

位置：`repo/ood/modern_head_runner_v1.py:102-112`（`inputs()`），被 `preflight()` 和 `prepare_phase()` 调用，`run()` 又先调 `preflight()`。

问题：即使只做纯头比较（P/T/K），也要求入网 v1r1 的 `runs/onboarding/COMPLETE.json` 和六库 `banks_manifest.json`。入网延迟或失败时，现代头连预检都过不了；整链 70 小时也被拉长。

建议：拆成 `inputs_head`（只依赖 QUERY_TAIL 完整产物）和 `inputs_module`（再查入网 banks）；或把 P/T/K 与 M 拆成两个顺序作业。科学配方不变，只改运行边界。至少提供 `preflight --heads-only`，让头比较可以先跑。

验收：QUERY_TAIL 完成、入网未完成时，P/T/K 预检可以通过；M 仍然要求 banks。

### P3（中）MLP 复用 proof 是硬编码断言，不是校验结果

位置：`repo/ood/modern_head_runner_v1.py:160-163`

```python
score_and_decision_bitwise=dict(CAL=True, CIC_DEV=True, UNSW_DEV=True)
```

问题：`prior.prepare_query_tail()` 内部确实会逐位校验并在漂移时抛错，但 proof 里的 True 是人工写入的，不是由 adapter 的校验输出生成。审计时只能证明“调用了会抛错的函数”，不能证明“proof 记录了逐位结果”。另外，`adopt_mlp` 在 `REUSE_VERIFIED` 之后若因字段不匹配抛错，作业会直接停止，而不是按 README 说的“缺证据时重训”。

建议：让 adapter 返回每个 pool 的实际回放摘要/布尔结果（含 score/decision digest），runner 直接落盘；在 `prepare_phase` 里先完成 `adopt_mlp` 会检查的全部前置条件，再宣布 `REUSE_VERIFIED`，或明确捕获复用失败并带原因转为训练。

验收：proof 中每个 True 都能追溯到 adapter 输出；复用失败不会把整链误停，也不会被写成“已复用”。

### P4（低）endpoint 校验漏了 `CAL_used`

位置：`repo/ood/modern_head_onboarding_v1.py:35-36`

问题：`verify_endpoint` 检查了 `reference_used`、`DEV_used`，没有检查 `CAL_used`；`modern_head_train_v1.load()` 是三个都查的。

建议：补 `receipt.get('CAL_used') is False`，与 `load()` 对齐。

### P5（低）合同文字与代码范围不一致

位置：`bundle/experiment_contract.json` 的 `gates.additional_regression.applies_to`

问题：该字段仍写 “Each seed and ensemble of primary QUERY_TAIL”，但同文件 `evaluation_scope` 和 `modern_head_evaluate_v1.regressions()` 都把历史 Q/协议保护应用到三族全部候选。代码是对的，文字会误导审计和论文。

建议：把 `applies_to` 改为“每个 family 的每个 seed 与 ensemble”；不要改代码逻辑。

### P6（低）M 阶段没有断言 `optimizer_updates == 0`

位置：`repo/ood/modern_head_runner_v1.py:218-219`

问题：M 阶段只检查 `status`、`automatic_model_selection` 和“不得 PASS”，没有断言 `result['optimizer_updates'] == 0`。当前 `run_development` 确实写 0，但 runner 应显式守住“入网不训练”。

建议：加一条 `result['optimizer_updates'] == 0`。

### P7（低）`setup_dependencies.py` 不在作业链里

位置：`bundle/scripts/run.slurm` 与 `OPERATE_HPC.md`

问题：依赖安装是人工步骤；忘记执行时，作业会在 import 阶段失败。错误虽明确，但可以更早、更直接。

建议：在 `submit_once.sh` 或 `run.slurm` 增加 `extra_deps`/`dependency_install_receipt.json` 存在性检查；不要自动联网安装。

## 已验证无问题

- 阈值只用 CAL 正常样本；目标评分在 `thresholds.json` 写出之后；并列分数用严格 `>` 处理，不按行号切分。
- FIT/CAL 不混入目标 DEV；目标 DEV 不参与训练、normalizer、尺度或阈值。
- 三族同 782 维输入、同 FIT/CAL、同权重语义；TabM 逐成员损失再平均；LightGBM 用 `N×w` 并记录尺度。
- 模块阶段不重训头；TabM/LightGBM 共用同一参考库和源侧定参规则；没有按目标结果选 λ 或选 winner。
- 缺三设备回归时 `complete_system_gate` 返回 PENDING，不会伪造 PASS；错设备供体缺计划时记 `NOT_AVAILABLE`。

## 建议处理顺序

1. P1：先改，补无分裂合成测试；这是最可能让长作业后段整链失败的点。
2. P2：决定拆不拆 P/T/K 与 M；若拆，科学配方不变，只改运行边界和资源边界。
3. P3：随下一次修订把复用 proof 改成可追溯证据。
4. P4–P7：可一起做，改完只跑受影响测试，并在 `validation.json` 明确“继承项未重跑”。

## 回执要求

- 每个问题写清楚：改了哪个文件/行、新增或重跑了哪些测试、日志路径、`validation.json` 增量。
- 不要把修复写成真实实验结果；不要改门槛、seed、训练配方或目标数据用途。
- 未重跑的继承项继续标 `rerun: false`，不要用“全过”概括。
