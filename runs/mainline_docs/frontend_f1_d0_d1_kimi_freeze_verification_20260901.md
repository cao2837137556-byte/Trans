# Kimi 冻结终审：Frontend-F1 D0/D1 协议（FROZEN @ 59d9705）——PASS

- 日期：2026-09-01
- 终审人：Kimi（独立审查方）
- 对象：`frontend_f1_teacher_constrained_unified_encoder_d0_d1_frozen_20260901.md`
- DRAFT 基线：`abe355c`；审查裁定：`77e8a21`（ACCEPT + S1-S4）；FROZEN 提交：`59d9705`

## 1. 终审结论

```text
F1_D0_D1_FREEZE_VERIFICATION: PASS
```

## 2. 独立核验记录

| 核验项 | 结果 |
|---|---|
| FROZEN SHA-256 独立重算 | `98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4` 与声明及侧车一致 PASS |
| draft→FROZEN 全 diff | 新增侧仅含 S1-S4 落实、§9 开放项转规范性裁定、状态/授权措辞；删除侧仅为 DRAFT 状态头、开放项问句、授权链措辞——科学规则、数值门、分母、终态名零漂移 PASS |
| S1 守恒等式 | 四条逐字写入（18,266+132=18,398；18,398+7,069=25,467；12,889+5,298=18,187；40−11=29），含 19 跨界 context 归 select 列口径与失败终态 PASS |
| S2 四门定义钉死 | availability/collapse/leakage/attack-information 均钉死文档+章节+SHA PASS |
| S3 候选并列次序 | 维护上游→参数量→字典序；禁性能数据；selection record 入 durable outputs PASS |
| S4 资源上限 | `wall_time_cap = min(3×synthetic 外推, 168h)`，D0 后禁止上调 PASS |
| Q3 补强 | A shadow 零翻转硬门 + incumbent-hard select 攻击字面分母逐字报告 PASS |
| 上游协议 SHA 独立重算 | challenger requirements `b46caf0d…`、CE learned blind-spot `016d61a9…`、CE `0b102b79…` 三者 MATCH PASS |

## 3. 冻结后状态与授权边界

- 本协议自此进入不可变状态；任何修改只能走具名 erratum + 独立审查。
- 当前不授权实现或执行 D0/D1，不授权训练、不授权打开任何真实
  representation/score/checkpoint/PCAP。
- 合法下一步：用户明确授权 D0（count-only 普查 + synthetic-only 资源试测）。
- D0 的 `F1_D0_CENSUS_PASS` 只授权 numerical addendum 起草，
  addendum 须经独立审查冻结后才可授权 D1 训练。

## 4. 风险提示（非阻塞）

D0 普查若显示排除后合法 fit 攻击 context 或教师覆盖远低于预期，
应在 numerical addendum 阶段如实降级声明上限，不得在 D1 中途补救。
