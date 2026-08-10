# CKCZ job 158015 lineage 修复审查 — Kimi

日期：2026-08-10 | 审查者：Kimi | 对象：erratum `698b7e2` + 实现 `f534775`

**总体结论：PASS。授权构建 r2 bundle；新 HPC 提交仍需用户再次明确授权。**

---

## 1. 对根因定性的独立确认

我在本地真实工件上复核了根因：`support_val:select:0` 的 UID 尾段是 `0`，而其真实 `recorded_index` 是 **16621**——r1 拿 0 去 join cache，必然 fail-closed。Codex 的根因定性（UID 尾段是 frozen role-frame 行号而非 recorded_index）**正确**。失败停在 join_predictions、无科学输出、无 partial 复用，失败语义干净。

## 2. 逐项审查结论（全部本地实测）

| 审查项（交接文档 §5） | 证据 | 结论 |
|---|---|---|
| 1. snapshot 是否合法 lineage 而非新增选择信息 | 该快照即 CKBY 已冻结工件（SHA 本地重算 `b2ef1f7d…` 一致），其 `uid/source/role/m1_phase/recorded_index` 是 CKBW 装配半段的既有 Record 构造事实，正是 FROZEN §5 要求的"现有 Record 构造合同"；不引入任何新的选择自由度 | PASS |
| 2. 是否只读五个数组 | `load_gotham_lineage` 只 `np.asarray` 五个列名；audit 固定 `forbidden_arrays_read=[]`；`x/label/family/global_pool` 虽同容器但从不访问 | PASS |
| 3. exact key 与 CKBJ 构造一致性 | 我用真实预测表全量验证：253,326 个 Gotham 行的 UID role/phase 段与列值 **0 不匹配**；`(uid, source_group, role, phase)` 四键 exact many-to-one join，与勘误 §3 逐字一致 | PASS |
| 4. 19 项测试 + 真实覆盖是否永久阻断 r1 根因 | 我独立复跑 19 项合同测试全 PASS，新增 `exact_lineage_join_with_nonindex_uid_suffix` 正例（uid 尾段 0 vs recorded_index 10）让"再解析 UID 尾段"的实现必失败；真实工件我复算：lineage 287,448 行、键唯一、**lineage miss = 0**、matched 277,326 = 253,326+24,000、ToN expected missing 20,000、unexpected 0 | PASS |
| 5. 四脚本+builder 接线 | builder 改 r2 名、勘误及侧车入包、勘误 SHA 断言；installer/slurm 双钉 snapshot+erratum SHA；installer 在 `sbatch --test-only` 前对**真实** CKBW+CKBY 工件跑完整 lineage coverage gate；validator 新增 lineage audit/erratum SHA/287,448 行/ToN 恰 20,000 断言 | PASS |

另复核：勘误文档 SHA `9dfa6f1c…` 本地重算与侧车一致；r1 bundle 文档标题已标"已作废"；旧 job-id 不复用。

## 3. 科学合同未变确认

diff 不涉及四 scalar、exact cut、门槛、16-family/4-pool 分母、200-rep bootstrap、FINAL 隔离。本修复为纯工程 lineage 修复，科学协议零漂移。

## 4. 授权边界

- 授权：构建 r2 bundle（含勘误文档与侧车），bundle 构建后按惯例我再审一次包。
- **HPC 重新提交需用户再次明确授权**（原授权随 job 158015 失效，不自动延续）。
