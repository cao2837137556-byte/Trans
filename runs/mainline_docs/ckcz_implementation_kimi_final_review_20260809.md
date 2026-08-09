# CKCZ 实现终审意见 — Kimi

日期：2026-08-09 | 审查者：Kimi | 对象：commit `7be237b`（实现）+ FROZEN 协议（SHA-256 `dad55890…`，已本地复算一致）

**总体结论：PASS。授权 Codex 构建 Slurm bundle 并给用户提交命令；HPC 提交仍需用户单独授权。**

---

## 1. 审查方式声明

本次不是纸面审查。我做了四类独立验证：

1. **真实数据复核**（本地冻结工件）：`244,050` 攻击分母、四 role 组成（support 69 / same-file 2,486 / future 131,391 / sealed 110,104）、16 个 family 逐族行数——与澄清文档逐字一致；五切片行数与切片内 UID 唯一性复核通过。
2. **FROZEN vs DRAFT 全文 diff**：确认吸收了 16 族口径澄清、GPT 移出签字链、auxiliary cache 存在性 launch blocker；无静默改动。
3. **allowlist 逐项检查**：Gotham 24 / auxiliary 31 成员逐个过目，无 cooler-motor、无 masked hydraulic-system-1；两个 SHA 侧车与 FROZEN 文档 SHA 均本地重算一致。
4. **通读实现代码 1,274 行 + 独立运行合同套件**：`python repo/ood/issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py` 我亲自复跑，18 项检查 + `status=PASS` 全部确认（非转述 Codex 结果）。

## 2. 对 Codex 六个重点审查项的逐项结论

1. **allowlist lineage/成员：PASS**。Gotham 24 的 lineage（C1 base plan 26 − 5 FINAL cooler − 1 masked hydraulic + 4 report extension）与成员集合吻合；auxiliary 31 与冻结 CKBQ manifest 集相等的声明接受。**接受 Codex 对我"24+31=55"旁证的纠正**——该总数巧合不能作为论证，我的旁证不严谨，特此确认撤回。
2. **source-only 正向 allowlist + manifest SHA + pre-open exact join：PASS**。`validate_manifest` 在任何 NPZ 打开前完成 allowlist→manifest exact subset、source 数、行数断言；逐 NPZ 的 SHA/字段集/shape/target index 唯一性随后验证。执行顺序符合 FROZEN §6。
3. **off-by-one：PASS**。causal state 为 current-inclusive 累加，与 FROZEN §9 四 scalar 定义逐字对应；exact-cut 激活为 `>=` 语义，frontier index 0 是显式 no-veto（纯 M7 基线）点；first-trigger 的 difference-array 单调更新逻辑正确；合同测试 `current_inclusive_conflict_count`、`consecutive_resets_on_nonconflict`、`span_only_on_current_conflict`、`time_to_first_veto_updates_at_exact_cuts` 均独立复跑通过。
4. **bootstrap 覆盖：PASS**。每 scalar 每 frontier 点固定 12 行（2 cluster 单位 × 5 named metric + macro），并有 `expected_bootstrap_rows` 总数断言；cluster 重采样在 source/pair 粒度加权，记录行从不作为独立重复；macro CI 用各池独立重采样后逐 replicate 平均，方法学正确；metadata-missing 行按 uid 单例 cluster 处理，属保守选择。
5. **工程失败无科学 verdict：PASS**。`ckcz_verdict.json` 只在 `validate_outputs` 之后写入；异常路径删除 verdict、写 `job_failure.txt`、非零退出；合同测试 `engineering_failure_has_no_scientific_verdict` 独立复跑通过。
6. **缺失输出/隐性 VIEWED selection：PASS**。输出为 FROZEN §12 超集（多 3 个 §9 允许的描述性审计）；cut 只从 VIEWED 行枚举且每行标记 `FORBIDDEN_FOR_SELECTION`；support_val（LEGAL）不参与 cut 枚举；标签在 state 构造完成后才 join 回（`state_is_label_and_role_invariant` 测试确认）；feasibility 四门（future≥84.83%、family Δ≥−2pp、support==100%、OOD macro≤30.27%）与 FROZEN 数值逐字一致。

## 3. 非阻塞备注

- causal state 的逐行 Python 循环约 30 万行，HPC CPU 上预计分钟级到十几分钟，可接受；不需要为此改向量化而引入新风险。
- pair bootstrap 中 metadata-missing 行作单例 cluster，会使 pair 口径 CI 略宽，属保守方向，无需改。

## 4. 授权边界与 launch blocker 提醒

- 本 PASS 授权：Slurm 脚本、installer、validator、bundle 构建与验证。
- **HPC 提交仍需用户明确授权**。
- FROZEN 记录的 launch blocker 仍在：auxiliary cache 尚无登录节点在线存在性证据。建议提交前用户在登录节点执行一次只读检查（与 Gotham 同样的 `ls`/`du`），证据随提交记录归档。
