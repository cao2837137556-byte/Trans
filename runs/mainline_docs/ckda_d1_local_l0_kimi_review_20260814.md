# CKDA D1 本地应急路线 L0 — Kimi 审查

- 日期：2026-08-14
- 对象：HEAD `9fe4319`；增补协议 `ckda_d1_local_contingency_draft_20260814.md`；L0 结果 `ckda_d1_local_precompute_result_20260814.md`
- 冻结合同：`ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`（不变）

## 总结论：四问全部 PASS —— 授权 L1（E3 fit/select embedding + 探针 + 阈值冻结，report 保持封存）

## 四问逐项裁定

**Q1 39 字段并集修复：PASS。** 实现为 `dict.fromkeys(CKBU 24 + D0 27)` 的确定性有序并集，双子集断言 fail-closed；`packet_limit` 强制因果 cutoff；缺失哨兵（None/"None"/空）统一归一为 Linux 空串约定；同一行喂给 CKBU 身份解析与 netFound 翻译两侧。只改"向 TShark 请求哪些字段"，不改任何值、包、目标、标签、顺序——是最小正确修复。重要加分：该缺陷在正式 HPC 链同样存在（`PRE_RESULT_FRONTEND_FIELDSET_INCOMPATIBILITY`），本地预检提前拦截，已要求未来 HPC 重放前纳入同一修复并独立审查。

**Q2 两遍过滤的因果语义：PASS。** pass1 只发现"哪些 canonical session 拥有冻结目标位置"（不改变任何包序）；pass2 从同一前缀头部重解码，仅对目标 session 保留状态，且在该 session 最后一个冻结目标后立即释放，末尾断言全释放（未释放即 raise）。session 间状态天然独立，丢弃非目标 session 不影响目标 session 的 current-inclusive 前缀内容。目标仍走同一 `BoundedNetfoundPrefix.flow()` 与冻结 batch 序。语义保持。

**Q3 32 真实目标 byte-identical 门：PASS（作为本地 fit/select 授权）。** checkpoint SHA 双侧一致（`f19c06ba…5161`）、768D 最大差 0.0、全部元数据数组逐字节相同——对行使路径证明了完全等价。其局限（不证明全部 25,467/262,050 行、不证明跨机浮点一致）已在协议中显式声明，且 **HPC 正式重放确认仍是论文声明的强制前提**。本地结果定位为 contingency evidence，不冒充正式结果——边界正确。

**Q4 L0/L1/L2 隔离：PASS。** L0 停止点七个计数器全部为 0/false（embedding、report、label、FINAL 等）；L1 止于阈值冻结、report 封存；L2 需独立门。阈值标记 `NOT_OPENED` 在案。一次性 report 隔离完整。

## 独立复验记录

- 路径重绑定：以 D0 正式清单（SHA `9184cd01…9689`，从 158210 拉回包重提取）逐格比对本地派生——**27/27 仅 `container_path` 变化，其余六列零差异**，与审计 JSON 一致。（初次用 D0 本地彩排副本比对出现 lineage_source 全列差异，已查明是我用错参照物，非实现问题。）
- 良性 census：8,735 sessions / 697,387 tokens，双门 FAIL；与我此前独立复算的可见包上限 2,182,190 一致（tokens ≤ 上限）。I1 未训练、`CKDA_D1_PRIMARY_PRECONDITION_FAILED` → E3 合法转进，是冻结状态机的预注册路径，非事后选候选。
- 两个保留的工程失败（路径重绑定误用正式字节哈希、PowerShell 5.1 把 FutureWarning 当致命）均记录在案、null verdict、未触及 embedding/report/FINAL。透明，接受。

## 授权边界

- 授权 L1：复用 L0，生成 25,467 条 E3 fit/select embedding，拟合 G0/P1/P2，冻结阈值，**止于 report 封存**。
- L2（report 计划/embedding/评分/bootstrap/判决）需 L1 产物独立审查后另行授权。
- 本授权仅限本地 contingency；论文级声明仍须 HPC 正式重放确认。
