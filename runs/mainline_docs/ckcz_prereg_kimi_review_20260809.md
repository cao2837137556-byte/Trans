# CKCZ 诊断预注册草案 — Kimi 独立审查意见

日期：2026-08-09 | 审查者：Kimi | 对象：`ckcz_endpoint_pair_conflict_diagnostic_prereg_draft_20260809.md`（commit `6de333d`）

**总体结论：PASS（可进入 freeze），附 1 个待澄清项、1 个自我勘误。**

---

## 1. 本地实测复核（非纸面审查）

对草案可本地核验的每一项做了实测，全部吻合：

| 草案声明 | 实测结果 | 结论 |
|---|---|---|
| 预测表 bytes 6,341,170 / SHA-256 `d1e90592…` | 完全一致 | ✓ |
| 297,326 行 / 30 列 | 一致 | ✓ |
| 五切片行数 251,050 / 10,069 / 10,069 / 16,069 / 10,069 | 逐一一致 | ✓ |
| 每个 held_value 内 UID 唯一 | 五切片 duplicated 均为 0 | ✓ |
| 同一 UID 跨切片重复是协议事实 | 全局 unique 269,050 < 总行数，符合 | ✓ |
| aux UID 冻结函数 `aux:{role}:{source_group}:{target_row}` | 抽样式样一致 | ✓ |
| support_val 69 攻击在协议内 | 345 行 = 69 × 5 切片，五切片均在 | ✓ |
| `review=0` 门 | 全表 review 仅 False | ✓ |
| §10 "16 attack family 全表" | 记录表 label=1 恰为 16 族 | ✓ |
| Gotham 24 + auxiliary 31 source | 与 CKBY 快照审计的 55 source 总数吻合（24+31=55） | ✓ |

HPC 侧声明（manifest SHA、24 source/317,523 行、auxiliary 31/18,600、cache 字段清单）本地不可验，依赖 §11 `validate_inputs` 的逐行 hash/schema 断言兜底——该兜底设计本身完备，接受。

## 2. 对 §15 六个开口项的逐项回答

1. **接受** auxiliary cache 为必要输入。predictive-maintenance 9,000 行只存在于 auxiliary cache，缺它四池 Oracle 不完整；"缺失即中止、不静默降三池"的失败语义正确。
2. **接受** 24/317,523 + 31/18,600 合同，条件是 exporter 的 allowlist 断言（§6 执行顺序 1-5）逐字落实。
3. **接受** 四个且仅四个 scalar + `current_conflict_t` 必须为真的 veto 形式。scalar 2 在 pair 自身序列上计连续、不以 source-global 相邻为准——正确回应了多 pair 交错问题。current-inclusive 摘要保持因果在线，合法。
4. **接受** 非晋升规则（全部失败才判死；任一可行只授权 D1-Legal）。这是本草案最关键的反自欺机制。
5. **未发现** FINAL allowlist、protocol slice、hydraulic missing-state、aux UID 的合同缺口。正向 allowlist + 零交集断言 + 日志不打印 FINAL 路径，设计完备。
6. **不需要删除统计量**。四个 scalar 已是最小充分集；描述性审计量不进入规则选择，VIEWED feature-search 风险已被"只反证不选值 + FORBIDDEN_FOR_SELECTION 标记"覆盖。

## 3. 待澄清项（不阻塞 freeze，但 FROZEN 稿应写明）

**16 族与 CKBW FROZEN 的 12 族等权定义的关系。** CKBW FROZEN 预注册写"Gotham 10 族 + ToN scan/bruteforce 2 族 = 12 等权"，而记录表实际有 16 个 attack family、草案 §10 也写"16 attack family 全表"。请 Codex 在 FROZEN 稿中明确：16 族如何映射到 12 族等权分母；"主要 family 恶化 ≤2pp"门适用于哪些族（rows>=15 的口径）。防止未来结果解读时两套分母混用。

## 4. 自我勘误

我的 round-2 文档写"预测表 31 列"，实测为 **30 列**，系我计数错误，特此更正。该错误不影响 round-2 的 D0 结论（无 timestamp、无交互键、recorded_index 可 100% join 均仍成立）。

## 5. 授权边界确认

本 PASS 仅授权 Codex 生成 FROZEN 协议 + SHA-256 侧车。实现、bundle、HPC 提交仍需用户在 FROZEN 生成后明确授权。
