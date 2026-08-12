# CKDA D1 FROZEN 一致性复核 — Kimi

- 日期：2026-08-12
- 对象：`ckda_d1_frozen_representation_probe_preregistered_20260812.md`（commit `517e600`）

## 结论：FROZEN PASS

1. **哈希独立复算**：`ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`，与侧车一致。
2. **与已审草案（`f762650`，Kimi PASS `734625d`）逐行 diff**：差异仅 4 处，全部为标题、状态行（DRAFT→FROZEN）、冻结授权引用（`734625d`）和授权说明文字；科学正文、参数、分母、门槛、状态机、禁改清单**零变化**。

## 授权边界

- D1 协议自此冻结。本 PASS 不授权实现/训练/embedding/HPC。
- D1 实现需用户明确授权后由 Codex 开始；实现完成后我按惯例做实现审查、bundle 审查、结果终审三道门。
