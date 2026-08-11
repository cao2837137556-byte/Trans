# CKCZ seed-27 正式结果终审 — Kimi

日期：2026-08-11 | 审查者：Kimi | 对象：`ckcz_seed27_formal_result_20260810.md`（commit `2aadd56`，job 158078）

**总体结论：PASS。裁决 `CKCZ_ORACLE_NO_INFORMATION` 成立，endpoint-pair conflict-persistence Episode Attack Veto 路线封口，主线闭环。**

---

## 1. 独立验证明细（全部本地重算，非转述）

| 验证项 | 结果 |
|---|---|
| pullback 身份 | SHA-256 `ecc4f88f…cdb7` 重算一致；28 个顶层文件；26/26 内部哈希全 OK |
| verdict JSON | `CKCZ_ORACLE_NO_INFORMATION`、`scientific_verdict_valid=true`、`bootstrap_reps=200`、四 scalar 全 false ✓ |
| **裁决逻辑逐点重算** | 我对全部 **87,730 个 frontier 点**用预注册四门（future≥84.83%、worst-family Δ≥−2pp、support=100%、OOD macro≤30.27%）独立重算 `oracle_compatible`，与正式列**逐点完全一致**；四 scalar 均为 0 可行点 ✓ |
| 强化反证复核 | 独立重算"仅 future+OOD 两门"：四 scalar 同样 0 点通过——family 门加入前已无解，与报告 §3 一致 ✓ |
| 审计 CSV 对账 | `max_future_under_ood_cap`、`min_ood_at_future_gate` 等关键列与我从原始 frontier CSV 的重算值逐位一致（73.973/73.397、66.205/93.092、63.191/93.092、67.967/83.208）✓ |
| family/pool 覆盖 | 每点 16 family 行 + 4 pool 行，四 scalar 全部成立 ✓ |
| bootstrap 完整性 | 1,052,760 行；每点固定 12 行；cluster unit 仅 source/pair；reps 全为 200 ✓ |

## 2. 对报告措辞的审查

- 封口范围限定准确：只封"当前 interaction key + 四 scalar + M7-OR-veto 形态 + 冻结数据"，未夸大为"所有 episode 方法不可能"；bootstrap 不确定性 caveat（尤其 count 路线近门处区间跨门）如实标注 ✓
- 20,000 行 ToN metadata miss 按预注册保持 M7、未补状态，已在报告 §2 如实披露为能力缺口 ✓
- 569 次 event-position/timestamp 逆序的解释（稳定排序保证因果性、但限制时间间隔解释）合理 ✓
- "资源结论只用 sstat、不伪造 sacct 缺失值"——诚实处理，符合规范 ✓

## 3. 主线结论确认

1. 本次系统能力**未增强**——如实。
2. 获得的是**结论确定性**：一个看似合理的便宜补救机制被完整 exact oracle 上界否定（攻击冲突与良性 OOD 冲突的 persistence 高度重叠，救攻击必然放回 OOD 误报），此方向不应再烧算力。
3. 同意下一步：按预注册转向**预训练 flow/session representation 储备路线**，另起 Episode Design Review、另起问题定义与预注册；CKCZ 的 VIEWED frontier 数值不得带入新路线选择。
4. CKCZ 全部纪律项复核：未进 D1-Legal、未选 cut、未加 scalar/patch、未碰 seed 37/47 与 cooler-motor FINAL ✓

主线可将 CKCZ 标为**最终闭环**。
