# CKCZ 实现完成稿：提交 Kimi 独立审查（2026-08-09）

状态：**IMPLEMENTATION COMPLETE LOCALLY — KIMI REVIEW REQUIRED BEFORE BUNDLE — HPC NOT SUBMITTED**

## 1. 实现边界

实现文件：

- `repo/ood/issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py`；
- `repo/ood/issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py`。

实现严格执行 CKCZ FROZEN：只读 CKBV 154917 cache 与 CKBW 157624 predictions，不训练、
不重解码 PCAP、不读取 cooler-motor 或 seed 37/47、不产生 family/source patch。

## 2. 已完成的正式合同

- FROZEN prereg SHA、两个 manifest SHA、预测表 SHA、两个 allowlist SHA 全钉；
- 正向 source allowlist 在打开任何 NPZ 前与 manifest 做 exact subset、source/row count 断言；
- 每个 allowlisted NPZ 逐文件 SHA、精确字段集合、shape、target index uniqueness 验证；
- Gotham `recorded_index` 与 auxiliary 冻结 UID exact join；ToN 无 endpoint metadata 行固定
  保持 M7，不插值、不回填；
- 每个 `held_value` 独立构造 member-local 有向 endpoint-pair state；
- 四个且仅四个 current-inclusive scalar；state 构造函数不含 label/role/family 字段；
- VIEWED exact cut 全 frontier，cut 全标记 `FORBIDDEN_FOR_SELECTION`；
- 244,050 全角色攻击分母、16 family、future 131,391、support 69、四 OOD 池口径冻结；
- source 与 pair 两种 cluster bootstrap，默认 200 reps；每个 frontier 点均输出 overall/future/
  same-file/sealed/support/OOD-macro 的 95% CI；
- first-trigger 前 conflict misses、attack-pair mean time-to-first-veto、rescued rows；
- member timestamp monotonicity/span、conflict delta-time median/MAD/raw ECDF、pair Gini；
- DataFrame 大表流式/原子写出，heterogeneous CSV deterministic union schema，逐文件 readback，
  最终 `SHA256SUMS`；
- 任一工程失败写 `job_failure.txt`、删除科学 verdict；输出目录必须初始为空。

## 3. 正向 allowlist

| allowlist | sources | SHA-256 |
|---|---:|---|
| `ckcz_gotham_source_allowlist_20260809.csv` | 24 | `65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7` |
| `ckcz_auxiliary_source_allowlist_20260809.csv` | 31 | `be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49` |

Gotham 24 的成员来源是冻结 C1 base plan 26，精确删除 5 个 FINAL cooler source 与已知
raw51 masked `hydraulic-system-1`，再加入 CKBW run_spec 钉住的 4 个 report extension source。
Auxiliary 31 与冻结 CKBQ `ckbo_auxiliary_benign_manifest.csv` source 集合 exact 相等。

这也修正了 Kimi review 中一个不影响 PASS 但论证不严的旁证：CKBY snapshot 的 55 source
不能用 `24+31` 直接证明，因为该 snapshot 实际含 20 processed + 31 auxiliary + 4 ToN。
当前 allowlist 使用真实冻结 lineage，不依赖该总数巧合。

Allowlist 只列 `source_group`；完整 source_cache_key/target_rows/cache_sha256 由已钉 SHA 的
154917 manifest 提供，并在任何 NPZ 打开前 exact join。这样既保持正向边界，也不复制可能
漂移的派生 metadata。

## 4. 验证结果

### 4.1 自包含 contract suite

```text
python repo/ood/issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py
status = PASS
```

覆盖 18 项，包括完整 synthetic pipeline 终态、source-only allowlist→manifest→NPZ、
Gotham/aux UID join、协议/member 隔离、标签不变性、bootstrap 每点覆盖、first-trigger、
原子输出、工程失败无科学 verdict。

### 4.2 冻结 CKBW 297,326 行真实分母回放

在 metadata 全缺失故障注入下，四个 scalar 均只能有显式 no-veto 点：

- 16 attack family 与 4 OOD pool 全部完整产出；
- `rescued_viewed_rows=0`；
- M7 overall attack recall=`77.7087%`；
- M7 四池 OOD macro=`0.1528%`；
- 四个 scalar 均不误报 oracle feasible；
- 真实 244,050/131,391/2,486/110,104/69/四 OOD 分母上的 20-rep source/pair
  bootstrap smoke PASS。

该回放只验证指标/失败语义，不是 CKCZ 科学结果。

## 5. 仍未发生的动作

- 尚未在 154917 在线 cache 上运行正式任务；
- 尚未构建 HPC bundle；
- 尚未提交 Slurm；
- 尚未产生 CKCZ oracle 科学裁决。

按 FROZEN §6，bundle 构建前必须由 Kimi 独立确认两个 allowlist 与实现合同。Kimi PASS 后，
Codex 才继续写 Slurm/installer/validator、构建包并给用户提交命令；提交仍需用户单独授权。

## 6. 请求 Kimi 重点审查

1. Gotham 24 与 auxiliary 31 的 lineage/成员集合是否 PASS；
2. source-only positive allowlist + frozen-manifest SHA + pre-open exact join 是否满足 FROZEN §6；
3. current-inclusive state、exact-cut activation、first-trigger difference-array 是否有 off-by-one；
4. source/pair bootstrap 是否覆盖每个 frontier 点且未把记录行当独立 source；
5. 工程失败是否确实不能留下 `ckcz_verdict.json`；
6. 是否发现缺失的 FROZEN 输出或任何隐性 VIEWED selection。
