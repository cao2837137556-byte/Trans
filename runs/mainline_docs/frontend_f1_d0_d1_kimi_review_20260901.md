# Kimi 审查：Frontend-F1 D0/D1 草案（abe355c）——ACCEPT + S1-S4

- 日期：2026-09-01
- 审查人：Kimi（独立审查方）
- 对象：`frontend_f1_teacher_constrained_unified_encoder_d0_d1_draft_20260901.md` @ `abe355c`
- 裁定：**ACCEPT，附 S1-S4 机械落实项**。落实后可生成 FROZEN + 侧车。

## 1. M1-M7 落实核验（前一轮裁定）

| 前裁定 | 落实位置 | 核验 |
|---|---|---|
| M1 新谱系 + 统一训练/扩展部署 | §0、§5、§6.4-6.6 | PASS：A 部署逐 target 复制 incumbent，合同测试 4/5/6 物理隔离 |
| M2 label-aware 判决约束 | §4.3 三类分治、§6.9 | PASS：old-hard 真良性明确不蒸馏、允许软化；4,986 类误报不会被锁死 |
| M3 坐标克隆降级 | §4.2 末段 | PASS：「逐坐标克隆不是硬前提」，adapter 身份冻结、计入 encoder |
| M4 hydraulic 移出验收 | §0、§2.9、§5、§8 | PASS：移出第一阶段门、保留为 full-replacement 必报行 |
| M5 B 攻击声明上限 | §4.5.B、§8 | PASS：162 行原样报告、29 context/5 族上限写入声明边界 |
| M6 新 head 入口预冻结 | §4.7 五项合取 | PASS：仅授权起草 addendum，不授权训练 |
| M7 D0 count-only 普查 | §1.3、§1.4、§3.2 | PASS：19-context 排除清单继承，4,385 仅作排除前锚点 |

## 2. 冻结数字独立验算

§1.3 普查表守恒验算：

```text
行级：  18,266（排除后 fit）+ 132（跨界 fit）= 18,398
        18,398 + 7,069（select 全量）= 25,467 ✅
上下文：12,889 + 5,298 = 18,187 ✅
        （即 19 个跨界 context 计入 select 列，32 跨界 select 行计入 7,069）
攻击：  40 − 11 = 29（fit 攻击 context，排除后）✅
```

守恒成立。但草案未把等式和「跨界 context 归属 select 列」的口径写明，
D0 复核时可能产生读表歧义，见 S1。

## 3. S1-S4 机械落实项

### S1（对应 Q1 的补强）：守恒等式写入 FROZEN

D0 必须逐字复现以下等式，而非仅复现表格：

- 18,266 + 132 = 18,398（fit 行排除前/后）；
- 18,398 + 7,069 = 25,467（行级总守恒）；
- 12,889 + 5,298 = 18,187（context 级总守恒，
  注明 19 跨界 context 整体计入 select 列、不重复计入 fit 列）；
- 40 − 11 = 29（fit 攻击 context）。

任一不等即 `F1_D0_NO_IDENTIFIABLE_UNIFIED_FIT_DENOMINATOR`。

### S2：B 侧前置门的定义来源钉死

§4.5.B 引用 availability/collapse/device-endpoint leakage/attack-information 四门，
但未指明定义出处。FROZEN 须逐门钉死定义所在文档 + 章节 + SHA
（challenger requirements FROZEN、CE learned blind-spot D0/D1 FROZEN 等），
禁止在 D1 实现时重新解释门语义。

### S3（对应 Q7）：单一候选并列时的冻结次序

「成熟组件兼容性 + 资源门」可能出现多个合格者。补冻结选择次序：

1. 有维护上游且 Python 3.9 兼容者优先；
2. 参数量小者优先；
3. 仍并列则按仓库/组件名字典序。

选择过程只允许使用 §3.4 机械准则，禁止使用任何性能数据。
选择记录（候选清单、逐项判定、淘汰原因）必须入 D0 durable outputs。

### S4：训练资源绝对上限公式预冻结

D0 在 synthetic shapes 上自报推算、自定上限属于自证。冻结公式：

```text
wall_time_cap = min(3 × synthetic 外推值, 168 墙钟小时)
```

超过 168 小时即 `F1_D0_RESOURCE_OR_CANDIDATE_NO_GO`，
不得以硬件理由在 D0 之后上调。cap 与推算过程写入 numerical addendum，
经 Kimi 审查冻结后方可训练。

## 4. 开放项逐项裁定

1. **Q1 ACCEPT**：4,385 仅作排除前锚点，19-context 排除后实际 row/context
   为唯一训练分母——按 S1 等式复现。
2. **Q2 ACCEPT**：四项 loss 结构足够。关键在 §4.3 第 3 类
   （old-hard 真良性不进入 teacher 保持项），配合 L_label_fit 的全局二分类，
   误报不被锁死。合同测试 9 已覆盖合成可区分性。
3. **Q3 ACCEPT 零翻转**：A shadow 攻击继承采用 target-level 零翻转硬门，
   不设容差。补强：incumbent-hard select 攻击的**字面分母**必须在 D1 报告中
   逐字给出，「hard」沿用 incumbent 的 >= 阈值语义。
4. **Q4 ACCEPT**：五项合取足够。重申：新-head addendum 本身走完整
   DRAFT→Kimi 审查→FROZEN 链，本协议不授权其实现或训练。
5. **Q5 ACCEPT**：51,057 viewed kill-only 在候选完全冻结后、one-shot 前执行。
   无论时机，其输出只能是 `F1_NO_ATTACK_CAPABILITY_INHERITANCE` 或「不否决」。
6. **Q6 ACCEPT**：hydraulic 边界完整。补强：未来任何 full-replacement 讨论
   必须引用本协议 §5 末段，hydraulic 作为单独必报行，不得被 macro 吸收。
7. **Q7 按 S3 落实**。

## 5. 独立观察（非阻塞）

- §4.5 先训完再「一次性打开 select shadow」的顺序正确：select 全程不进训练，
  只作开发期 shadow 评价，声明上限已由 §8 钉在 development 层。
- 「B gain 但 A shadow 失败即整体 NO-GO」（§5 表）比我的预期更严格，
  背书——它防止把盲区分支包装成继承成功。
- 本草案是迄今为止结构最完整的一份；六终态分支表（§5）消除了
  结果驱动解释空间。

## 6. 下一步

Codex 机械落实 S1-S4 后生成 FROZEN + SHA 侧车，
我做 SHA 独立重算与 draft→FROZEN 全 diff 终审。
本审查不构成实现、训练或打开任何分数的授权。
