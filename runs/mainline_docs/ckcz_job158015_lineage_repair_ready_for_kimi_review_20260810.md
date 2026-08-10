# CKCZ job 158015 lineage 修复：提交 Kimi 独立审查（2026-08-10）

状态：**IMPLEMENTATION REPAIRED LOCALLY — KIMI REVIEW REQUIRED — R2 BUNDLE NOT BUILT — HPC NOT AUTHORIZED**

## 1. 根因与修复边界

job 158015 的唯一根因是坐标误用：CKBJ UID 尾段是 frozen role-frame row index，CKCZ r1 却
将其当成 cache `recorded_index`。修复不放宽 join、不改变 scientific protocol，而是机械执行
FROZEN §5 与勘误 1：使用 CKBY 157930 的冻结 lineage snapshot 恢复真实 recorded_index。

新增输入：

- `ckby_drocc_feature_snapshot_seed27.npz`；
- rows 287,448；
- SHA-256 `b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c`；
- 代码只访问 `uid/source/role/m1_phase/recorded_index`，audit 固定
  `forbidden_arrays_read=[]`。

## 2. 实现改动

- `load_gotham_lineage`：snapshot exact fields/hash/rows/唯一键/FINAL source fail-closed；
- Gotham 预测先按 `(uid, source_group, role, phase)` exact many-to-one join lineage，再以
  `(source_group, recorded_index)` exact join metadata；
- auxiliary UID 函数与 ToN-only expected missing 原样保持；
- run_spec、input audit 与 required outputs 新增 lineage/erratum 身份；
- Slurm 与 installer 均钉 snapshot 路径/hash/287,448 行；
- installer 在 `sbatch --test-only` 前对真实 CKBW+CKBY 工件执行完整 lineage coverage gate；
- validator 要求 lineage audit、erratum SHA、禁止数组未读、ToN missing 恰为 20,000；
- builder 改为新名字 `..._20260810_r2`，旧 r1 不覆盖、不复用 job-id。

## 3. 永久回归证据

合同测试现为 19 项，全部 PASS。新增关键用例故意构造：

```text
uid = future_query:report:0
recorded_index = 10
```

若实现再次解析 UID 尾段，该用例必失败；当前 exact lineage join 恢复 target 10 并通过。

本地真实工件审计：

```text
prediction_rows       = 297326
Gotham protocol rows  = 253326
Gotham unique UIDs    = 253050
auxiliary rows        = 24000
ToN rows              = 20000
lineage rows           = 287448
metadata matched      = 277326
metadata unmatched    = 20000
ToN expected missing  = 20000
unexpected unmatched  = 0
support_val:select:0  -> recorded_index 16621
```

snapshot SHA 本地重算与冻结值一致，arrays-read audit 仅五个 lineage 数组。

## 4. 未改变的科学合同

- 四 scalar、exact cut frontier、门槛、16-family/4-pool 分母、200-rep source/pair bootstrap
  全未改变；
- 不训练、不重解码、不碰 FINAL、不增加 family/source patch；
- Oracle 有信息仍只授权 D1-Legal；Oracle 全失败才封口当前 endpoint-pair persistence；
- job 158015 partial files 不复用。

## 5. 请求 Kimi 审查

请重点核验：

1. CKBY snapshot 是否是 FROZEN §5 允许的现有 Record lineage，而非新增选择信息；
2. 实现是否确实只读取五个 lineage 数组；
3. exact key 是否与 CKBJ 构造逐字一致；
4. 19 项测试和真实 297,326 行 coverage 是否足以永久阻断 r1 根因；
5. Slurm/installer/validator/builder 是否全部钉住新输入与 r2 隔离。

Kimi PASS 后才允许构建 r2 bundle；新 HPC 提交仍需用户再次明确授权。
